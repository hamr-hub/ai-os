import uuid
import logging
import asyncio
import time
import os
import shutil
from typing import Dict, Optional, List, Callable, Any
from dataclasses import dataclass, field

logger = logging.getLogger("ai_controller.download_manager")


@dataclass
class DownloadTask:
    task_id: str
    model_name: str
    source: str
    status: str = "pending"
    progress_pct: float = 0.0
    speed_mbps: float = 0.0
    eta_seconds: int = 0
    downloaded_bytes: int = 0
    total_bytes: int = 0
    local_path: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error_message: Optional[str] = None
    async_task: Optional[asyncio.Task] = None
    retry_count: int = 0
    max_retries: int = 3
    checksum: Optional[str] = None
    save_dir: Optional[str] = None
    hf_token: Optional[str] = None
    allow_patterns: Optional[List[str]] = None
    ignore_patterns: Optional[List[str]] = None
    max_workers: Optional[int] = None
    force_download: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "model_name": self.model_name,
            "source": self.source,
            "status": self.status,
            "progress_pct": round(self.progress_pct, 1),
            "speed_mbps": round(self.speed_mbps, 2),
            "eta_seconds": self.eta_seconds,
            "downloaded_bytes": self.downloaded_bytes,
            "total_bytes": self.total_bytes,
            "local_path": self.local_path,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "allow_patterns": self.allow_patterns,
            "ignore_patterns": self.ignore_patterns,
        }


class DownloadTaskManager:

    def __init__(
        self, config=None, model_hub=None, model_pool=None,
        ws_manager=None, sse_push=None,
    ):
        self._config = config
        self._model_hub = model_hub
        self._model_pool = model_pool
        self._ws_manager = ws_manager
        self._sse_push = sse_push
        self._tasks: Dict[str, DownloadTask] = {}
        self._active_count = 0
        self._max_concurrent = 3
        self._disk_warning_pct = 0.85
        self._disk_abort_pct = 0.95
        self._save_root = "/mnt/pve_models"
        self._progress_callbacks: List[Callable] = []
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._download_progress_refs: Dict[str, Any] = {}

        if config:
            if hasattr(config, 'vllm') and config.vllm:
                self._save_root = config.vllm.get("model_base_path", self._save_root)

    def initialize_semaphore(self):
        if not self._semaphore:
            self._semaphore = asyncio.Semaphore(self._max_concurrent)

    def add_progress_callback(self, callback: Callable):
        self._progress_callbacks.append(callback)

    def _fire_progress(self, task: DownloadTask):
        for cb in self._progress_callbacks:
            try:
                cb(task.to_dict())
            except Exception as e:
                logger.warning("Progress callback error: %s", e)
        self._notify_event("download_progress", task)

    def _check_disk_space(self, required_bytes: int = 0) -> Dict:
        try:
            import psutil
            disk = psutil.disk_usage(self._save_root)
            free_gb = disk.free / (1024 ** 3)
            pct = disk.percent
            if pct >= self._disk_abort_pct * 100:
                return {
                    "ok": False,
                    "reason": "disk_full",
                    "free_gb": round(free_gb, 2),
                    "pct": pct,
                }
            if pct >= self._disk_warning_pct * 100:
                return {
                    "ok": True,
                    "warning": True,
                    "free_gb": round(free_gb, 2),
                    "pct": pct,
                }
            return {"ok": True, "warning": False, "free_gb": round(free_gb, 2), "pct": pct}
        except ImportError:
            return {"ok": True, "warning": False, "reason": "psutil_not_available"}
        except Exception as e:
            return {"ok": True, "warning": False, "reason": str(e)}

    def create_task(
        self, model_name: str, source: str,
        save_dir: Optional[str] = None, auto_start: bool = True,
        hf_token: Optional[str] = None,
        allow_patterns: Optional[List[str]] = None,
        ignore_patterns: Optional[List[str]] = None,
        max_workers: Optional[int] = None,
        force_download: bool = False,
    ) -> Dict:
        disk_check = self._check_disk_space()
        if not disk_check.get("ok", True):
            return {
                "status": "error",
                "message": f"磁盘空间不足({disk_check.get('pct', 0):.1f}%)",
                "disk_check": disk_check,
            }

        short_name = model_name.split("/")[-1]
        if self._model_hub and not force_download and self._model_hub.is_model_local(model_name):
            local_path = self._model_hub.get_model_local_path(model_name)
            return {
                "status": "already_exists",
                "local_path": local_path,
                "model_name": short_name,
            }

        if self._active_count >= self._max_concurrent:
            return {
                "status": "queued",
                "message": f"并发下载已满({self._max_concurrent}), 任务将排队等待",
            }

        task_id = str(uuid.uuid4())[:12]
        task = DownloadTask(
            task_id=task_id,
            model_name=model_name,
            source=source,
            status="pending",
            save_dir=save_dir,
            hf_token=hf_token,
            allow_patterns=allow_patterns,
            ignore_patterns=ignore_patterns,
            max_workers=max_workers,
            force_download=force_download,
        )
        self._tasks[task_id] = task

        if auto_start:
            self._start_task_async(task)

        return {
            "task_id": task_id,
            "status": "pending",
            "model_name": model_name,
            "source": source,
        }

    def _start_task_async(self, task: DownloadTask):
        try:
            loop = asyncio.get_running_loop()
            self.initialize_semaphore()
            task.async_task = loop.create_task(self._execute_download(task))
        except RuntimeError:
            logger.info("No running asyncio loop, task will be started later")

    async def _execute_download(self, task: DownloadTask):
        self.initialize_semaphore()
        async with self._semaphore:
            task.status = "downloading"
            task.started_at = time.time()
            self._active_count += 1
            self._notify_event("download_start", task)

            source_map = {
                "hf": "hf", "huggingface": "hf",
                "ms": "ms", "modelscope": "ms",
                "oxl": "oxl", "openxlab": "oxl",
            }
            mapped_source = source_map.get(task.source, task.source)

            for attempt in range(task.max_retries + 1):
                try:
                    if self._model_hub:
                        def on_progress(pct: float):
                            task.progress_pct = pct
                            self._fire_progress(task)

                        result = self._model_hub.download_model(
                            task.model_name, mapped_source, task.save_dir,
                            hf_token=task.hf_token,
                            allow_patterns=task.allow_patterns,
                            ignore_patterns=task.ignore_patterns,
                            max_workers=task.max_workers,
                            force_download=task.force_download,
                            progress_callback=on_progress,
                        )
                        task.status = result.get("status", "error")
                        task.local_path = result.get("local_path")
                        task.error_message = result.get("message")

                        if task.status == "completed":
                            task.progress_pct = 100.0
                            task.completed_at = time.time()
                            if self._model_pool:
                                self._model_pool.register_from_download(
                                    model_name=task.model_name,
                                    local_path=task.local_path,
                                    source=mapped_source,
                                )
                            self._notify_event("download_complete", task)
                            self._fire_progress(task)
                            self._decrement_active_count()
                            return

                        if task.status == "already_exists":
                            task.progress_pct = 100.0
                            task.completed_at = time.time()
                            self._notify_event("download_complete", task)
                            self._decrement_active_count()
                            return

                        if attempt < task.max_retries:
                            task.retry_count = attempt + 1
                            task.status = "retrying"
                            logger.warning(
                                "Download task %s retry %d/%d",
                                task.task_id, attempt + 1, task.max_retries,
                            )
                            self._notify_event("download_retry", task)
                            await asyncio.sleep(5)
                            continue

                    else:
                        task.status = "error"
                        task.error_message = "No model hub configured"
                except asyncio.CancelledError:
                    task.status = "cancelled"
                    self._notify_event("download_cancelled", task)
                    self._decrement_active_count()
                    return
                except Exception as e:
                    task.status = "failed"
                    task.error_message = str(e)
                    logger.error("Download task %s failed: %s", task.task_id, e)
                    if attempt < task.max_retries:
                        task.retry_count = attempt + 1
                        task.status = "retrying"
                        await asyncio.sleep(5)
                        continue
                    self._notify_event("download_error", task)

            self._decrement_active_count()

    def get_status(self, task_id: str) -> Optional[Dict]:
        task = self._tasks.get(task_id)
        if not task:
            return None
        return task.to_dict()

    def cancel_task(self, task_id: str) -> Dict:
        task = self._tasks.get(task_id)
        if not task:
            return {"cancelled": False, "reason": "task_not_found"}
        if task.status in ("completed", "failed", "cancelled"):
            return {"cancelled": False, "reason": f"task_already_{task.status}"}
        if task.async_task and not task.async_task.done():
            task.async_task.cancel()
        task.status = "cancelled"
        self._notify_event("download_cancelled", task)
        return {"cancelled": True, "task_id": task_id}

    def retry_task(self, task_id: str) -> Dict:
        task = self._tasks.get(task_id)
        if not task:
            return {"success": False, "reason": "task_not_found"}
        if task.status not in ("failed", "error"):
            return {"success": False, "reason": f"task_status_{task.status}_not_retryable"}
        task.status = "pending"
        task.retry_count = 0
        task.error_message = None
        self._start_task_async(task)
        return {"success": True, "task_id": task_id}

    def list_tasks(self, status_filter: Optional[str] = None) -> List[Dict]:
        tasks = self._tasks.values()
        if status_filter:
            tasks = [t for t in tasks if t.status == status_filter]
        return [t.to_dict() for t in sorted(tasks, key=lambda t: t.created_at)]

    def get_active_count(self) -> int:
        return self._active_count

    def _decrement_active_count(self):
        self._active_count = max(0, self._active_count - 1)

    def get_stats(self) -> Dict:
        total = len(self._tasks)
        by_status = {}
        for t in self._tasks.values():
            by_status[t.status] = by_status.get(t.status, 0) + 1
        return {
            "total_tasks": total,
            "active_downloads": self._active_count,
            "max_concurrent": self._max_concurrent,
            "by_status": by_status,
        }

    def cleanup_completed(self, max_age_hours: int = 24) -> int:
        cutoff = time.time() - max_age_hours * 3600
        removed = 0
        for task_id in list(self._tasks.keys()):
            task = self._tasks[task_id]
            if task.status in ("completed", "failed", "cancelled"):
                if task.completed_at and task.completed_at < cutoff:
                    del self._tasks[task_id]
                    removed += 1
                elif task.created_at < cutoff:
                    del self._tasks[task_id]
                    removed += 1
        return removed

    def _notify_event(self, event_type: str, task: DownloadTask):
        payload = {
            "type": event_type,
            "task_id": task.task_id,
            "model_name": task.model_name,
            "status": task.status,
            "progress_pct": round(task.progress_pct, 1),
        }
        if self._ws_manager:
            try:
                self._ws_manager.broadcast("download", payload)
            except Exception as e:
                logger.warning("WS notification failed: %s", e)
        if self._sse_push:
            try:
                self._sse_push.push_event("download", payload)
            except Exception as e:
                logger.warning("SSE notification failed: %s", e)
