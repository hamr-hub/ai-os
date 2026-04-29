import asyncio
import os
import signal
import socket
import subprocess
import time
import httpx
import logging
import uuid
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

logger = logging.getLogger("ai_controller.model_switch_orchestrator")


class SwitchPhase(str, Enum):
    IDLE = "idle"
    PHASE1 = "phase1"
    PHASE2 = "phase2"
    PHASE3 = "phase3"
    PHASE4 = "phase4"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"
    COMPLETED = "completed"
    FAILED = "failed"


class PhaseStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PhaseDetail:
    phase: int
    name: str
    status: PhaseStatus = PhaseStatus.PENDING
    progress: int = 0
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    logs: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase,
            "name": self.name,
            "status": self.status.value,
            "progress": self.progress,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "logs": self.logs[-50:],
            "error": self.error,
        }


@dataclass
class SwitchSession:
    session_id: str
    target_model: str
    target_model_path: str
    previous_model: Optional[str]
    previous_model_path: Optional[str]
    started_at: str
    finished_at: Optional[str] = None
    overall_phase: SwitchPhase = SwitchPhase.IDLE
    phases: List[PhaseDetail] = field(default_factory=lambda: [
        PhaseDetail(1, "停止旧服务"),
        PhaseDetail(2, "强制清理进程"),
        PhaseDetail(3, "启动新服务"),
        PhaseDetail(4, "冒烟测试"),
    ])
    error: Optional[str] = None
    rollback_reason: Optional[str] = None
    completed_successfully: bool = False

    def _calc_overall_progress(self) -> int:
        weights = [25, 25, 25, 25]
        total = 0
        for i, p in enumerate(self.phases):
            if p.status == PhaseStatus.SUCCESS:
                total += weights[i]
            elif p.status == PhaseStatus.RUNNING:
                total += int(weights[i] * p.progress / 100)
            elif p.status == PhaseStatus.SKIPPED:
                total += weights[i]
        return min(total, 100)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "target_model": self.target_model,
            "previous_model": self.previous_model,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "overall_phase": self.overall_phase.value,
            "overall_progress": self._calc_overall_progress(),
            "phases": [p.to_dict() for p in self.phases],
            "error": self.error,
            "rollback_reason": self.rollback_reason,
            "completed_successfully": self.completed_successfully,
        }


class _SwitchAborted(Exception):
    pass


class ModelSwitchOrchestrator:
    PHASE1_STOP_TIMEOUT = 30
    PHASE1_PORT_CHECK_TIMEOUT = 15
    PHASE2_KILL_TIMEOUT = 60
    PHASE2_VERIFY_TIMEOUT = 15
    PHASE3_START_TIMEOUT = 600  # 大模型可能需要 5-10 分钟加载
    PHASE4_TEST_RETRIES = 3
    PHASE4_TEST_TIMEOUT = 15

    FATAL_KEYWORDS = [
        "cuda out of memory",
        "runtimeerror",
        "torch.cuda.outofmemoryerror",
        "failed to initialize",
        "killed",
        "oom",
        "out of memory",
    ]

    def __init__(self, ws_manager, vllm_service_name: str, vllm_port: int, model_base_path: str):
        self._ws_manager = ws_manager
        self._vllm_service_name = vllm_service_name
        self._vllm_port = vllm_port
        self._model_base_path = model_base_path
        self._global_lock = asyncio.Lock()
        self._current_session: Optional[SwitchSession] = None
        self._cancel_requested = False

    @property
    def is_switching(self) -> bool:
        return self._global_lock.locked()

    @property
    def current_session(self) -> Optional[SwitchSession]:
        return self._current_session

    def request_cancel(self):
        self._cancel_requested = True

    async def switch(
        self,
        target_model: str,
        target_model_path: str,
        previous_model: Optional[str] = None,
        previous_model_path: Optional[str] = None,
    ) -> SwitchSession:
        if self._global_lock.locked():
            raise RuntimeError("Model switch already in progress")

        async with self._global_lock:
            self._cancel_requested = False
            session = SwitchSession(
                session_id=str(uuid.uuid4()),
                target_model=target_model,
                target_model_path=target_model_path,
                previous_model=previous_model,
                previous_model_path=previous_model_path,
                started_at=datetime.now().isoformat(),
            )
            self._current_session = session

            try:
                # 简化流程：更新配置 → 重启服务 → 测试
                session.overall_phase = SwitchPhase.PHASE1
                await self._phase1_update_config_and_restart(session)

                session.overall_phase = SwitchPhase.PHASE2
                await self._phase2_smoke_test(session)

                session.overall_phase = SwitchPhase.COMPLETED
                session.completed_successfully = True
                session.finished_at = datetime.now().isoformat()
                await self._broadcast(session, phase=2, progress=100,
                                      log="模型切换完成，所有测试通过", level="success", final=True)

            except _SwitchAborted:
                logger.error("Switch aborted")

            except Exception as exc:
                logger.exception("Unexpected error during switch: %s", exc)
                session.error = str(exc)
                await self._rollback(session, f"意外错误: {exc}", from_exception=True)

            finally:
                session.finished_at = session.finished_at or datetime.now().isoformat()

            return session

    async def _phase1_update_config_and_restart(self, session: SwitchSession):
        """Phase 1: 更新配置并重启服务"""
        phase = session.phases[0]
        phase.status = PhaseStatus.RUNNING
        phase.started_at = datetime.now().isoformat()

        await self._log(session, phase, f"更新模型配置: {session.target_model}")
        phase.progress = 10
        await self._broadcast(session, phase=1, progress=10, log="更新模型配置")

        from core.vllm_manager import _update_vllm_script, refresh_vllm_port_cache
        script_ok = _update_vllm_script(session.target_model_path, session.target_model)
        if not script_ok:
            error_msg = "更新模型路径配置失败"
            phase.status = PhaseStatus.FAILED
            phase.error = error_msg
            phase.finished_at = datetime.now().isoformat()
            await self._rollback(session, error_msg)
            raise _SwitchAborted(error_msg)

        await self._log(session, phase, "模型配置更新成功")
        refresh_vllm_port_cache()

        phase.progress = 30
        await self._broadcast(session, phase=1, progress=30, log="重启 vLLM 服务")
        await self._log(session, phase, "重启 vLLM 服务...")

        from core.vllm_manager import restart_vllm_service
        restart_ok = restart_vllm_service()
        if not restart_ok:
            error_msg = "systemctl restart 失败"
            phase.status = PhaseStatus.FAILED
            phase.error = error_msg
            phase.finished_at = datetime.now().isoformat()
            await self._rollback(session, error_msg)
            raise _SwitchAborted(error_msg)

        await self._log(session, phase, "vLLM 服务重启指令已发送")

        start_time = time.time()
        poll_interval = 3.0
        while time.time() - start_time < self.PHASE3_START_TIMEOUT:
            if self._cancel_requested:
                await self._rollback(session, "用户请求取消")
                raise _SwitchAborted("Cancelled")

            elapsed = int(time.time() - start_time)
            progress = 35 + int(55 * elapsed / self.PHASE3_START_TIMEOUT)
            phase.progress = min(progress, 90)

            from core.vllm_manager import discover_vllm_port
            port = discover_vllm_port()
            health_url = f"http://localhost:{port}/health"
            try:
                async with httpx.AsyncClient(timeout=3) as client:
                    resp = await client.get(health_url)
                    if resp.status_code == 200:
                        phase.status = PhaseStatus.SUCCESS
                        phase.progress = 100
                        phase.finished_at = datetime.now().isoformat()
                        await self._log(session, phase, f"vLLM 服务就绪 (耗时 {elapsed}s)")
                        await self._broadcast(session, phase=1, progress=100,
                                              log="vLLM 服务就绪", level="success")
                        return
            except Exception:
                pass

            await self._broadcast(session, phase=1, progress=phase.progress,
                                  log=f"等待服务就绪... ({elapsed}s)")
            await asyncio.sleep(poll_interval)
            poll_interval = min(poll_interval * 1.3, 8)

        error_msg = f"vLLM 服务在 {self.PHASE3_START_TIMEOUT}s 内未就绪"
        phase.status = PhaseStatus.FAILED
        phase.error = error_msg
        phase.finished_at = datetime.now().isoformat()
        await self._rollback(session, error_msg)
        raise _SwitchAborted(error_msg)

    async def _phase2_smoke_test(self, session: SwitchSession):
        """Phase 2: 冒烟测试"""
        phase = session.phases[1]
        phase.status = PhaseStatus.RUNNING
        phase.started_at = datetime.now().isoformat()

        await self._log(session, phase, "开始冒烟测试...")
        phase.progress = 10
        await self._broadcast(session, phase=2, progress=10, log="冒烟测试")

        from core.vllm_manager import discover_vllm_port
        port = discover_vllm_port()
        url = f"http://localhost:{port}/v1/chat/completions"

        # 先查询 vLLM 实际注册的模型 ID，确保冒烟测试使用正确的 model 名称
        actual_model_id = session.target_model_path
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                models_resp = await client.get(f"http://localhost:{port}/v1/models")
                if models_resp.status_code == 200:
                    models_data = models_resp.json()
                    registered_ids = [m.get("id", "") for m in models_data.get("data", [])]
                    if registered_ids:
                        actual_model_id = registered_ids[0]
                        if actual_model_id != session.target_model_path:
                            await self._log(session, phase,
                                           f"vLLM 模型ID: {actual_model_id} (配置路径: {session.target_model_path})")
        except Exception as e:
            await self._log(session, phase, f"查询模型ID失败，使用路径: {e}")

        payload = {
            "model": actual_model_id,
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 5,
            "temperature": 0.0,
        }

        await self._log(session, phase, f"冒烟测试 model={actual_model_id}")

        for attempt in range(1, self.PHASE4_TEST_RETRIES + 1):
            progress = int(20 * attempt / self.PHASE4_TEST_RETRIES)
            phase.progress = max(phase.progress, progress)
            await self._broadcast(session, phase=2, progress=phase.progress,
                                  log=f"冒烟测试第 {attempt}/{self.PHASE4_TEST_RETRIES} 次")
            try:
                async with httpx.AsyncClient(timeout=self.PHASE4_TEST_TIMEOUT) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        if content.strip():
                            phase.status = PhaseStatus.SUCCESS
                            phase.progress = 100
                            phase.finished_at = datetime.now().isoformat()
                            await self._log(session, phase,
                                           f"冒烟测试通过 (第{attempt}次)")
                            await self._broadcast(session, phase=2, progress=100,
                                                  log="冒烟测试通过", level="success")
                            return
                        else:
                            await self._log(session, phase,
                                           f"第{attempt}次: 模型返回空内容, resp={data}")
                    else:
                        await self._log(session, phase,
                                       f"第{attempt}次: HTTP {resp.status_code}, body={resp.text[:200]}")
            except Exception as e:
                await self._log(session, phase, f"测试第{attempt}次异常: {e}")

            if attempt < self.PHASE4_TEST_RETRIES:
                await asyncio.sleep(5)

        error_msg = f"冒烟测试在 {self.PHASE4_TEST_RETRIES} 次重试后失败"
        phase.status = PhaseStatus.FAILED
        phase.error = error_msg
        phase.finished_at = datetime.now().isoformat()
        await self._rollback(session, error_msg)
        raise _SwitchAborted(error_msg)


    async def _rollback(self, session: SwitchSession, reason: str, from_exception: bool = False):
        session.overall_phase = SwitchPhase.ROLLING_BACK
        session.rollback_reason = reason
        session.error = reason

        await self._broadcast(session, phase=0, progress=0,
                              log=f"开始回滚: {reason}", level="warning",
                              event_type="rollback_started")

        from core.vllm_manager import _cleanup_runtime_override
        _cleanup_runtime_override()

        if session.previous_model_path:
            from core.vllm_manager import _update_vllm_script, start_vllm_service

            logger.info("Rolling back to: %s", session.previous_model_path)
            await self._broadcast(session, phase=0, progress=20,
                                  log=f"恢复旧模型配置: {session.previous_model}",
                                  level="warning")

            script_ok = _update_vllm_script(
                session.previous_model_path, session.previous_model
            )
            if not script_ok:
                logger.error("Rollback config restore failed")
                await self._broadcast(session, phase=0, progress=30,
                                      log="旧模型配置恢复失败，尝试直接启动", level="error")

            start_ok = start_vllm_service()
            if start_ok:
                await self._broadcast(session, phase=0, progress=80,
                                      log="旧服务重启指令已发送，等待就绪", level="warning")
                for _ in range(10):
                    await asyncio.sleep(3)
                    try:
                        from core.vllm_manager import discover_vllm_port
                        port = discover_vllm_port()
                        async with httpx.AsyncClient(timeout=3) as client:
                            resp = await client.get(f"http://localhost:{port}/health")
                            if resp.status_code == 200:
                                await self._log(session, session.phases[0],
                                               "旧模型服务已恢复就绪")
                                break
                    except Exception:
                        pass
            else:
                logger.error("Rollback start service failed")
        else:
            await self._broadcast(session, phase=0, progress=50,
                                  log="无旧模型记录，服务保持停止状态", level="warning")

        session.overall_phase = SwitchPhase.ROLLED_BACK
        session.finished_at = datetime.now().isoformat()

        await self._broadcast(session, phase=0, progress=100,
                              log=f"回滚完成，原因: {reason}", level="error",
                              final=True, event_type="rollback_completed")

    async def _broadcast(
        self,
        session: SwitchSession,
        phase: int,
        progress: int,
        log: str,
        level: str = "info",
        event_type: str = "switch_progress",
        final: bool = False,
    ):
        message = {
            "type": event_type,
            "timestamp": datetime.now().isoformat(),
            "session_id": session.session_id,
            "overall_phase": session.overall_phase.value,
            "overall_progress": session._calc_overall_progress(),
            "current_phase": phase,
            "phase_progress": progress,
            "log": log,
            "level": level,
            "final": final,
            "target_model": session.target_model,
            "previous_model": session.previous_model,
            "session": session.to_dict(),
        }
        try:
            await self._ws_manager.broadcast(message, channel="model_switch")
        except Exception as e:
            logger.warning("WS broadcast failed: %s", e)

    async def _log(self, session: SwitchSession, phase: PhaseDetail, log: str):
        phase.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {log}")
        logger.info("[Phase%d] %s", phase.phase, log)

    def _is_port_alive(self, port: int) -> bool:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            return result == 0
        except Exception:
            return False

    def _find_pids_on_port(self, port: int) -> List[int]:
        pids = []
        try:
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.strip().splitlines():
                try:
                    pids.append(int(line.strip()))
                except ValueError:
                    pass
        except Exception:
            pass
        return list(set(pids))

    def _find_vllm_pids(self) -> List[int]:
        pids = []
        try:
            result = subprocess.run(
                ["lsof", "-ti", f":{self._vllm_port}"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.strip().splitlines():
                try:
                    pids.append(int(line.strip()))
                except ValueError:
                    pass
        except Exception:
            pass

        if not pids:
            try:
                result = subprocess.run(
                    ["pgrep", "-f", "vllm"],
                    capture_output=True, text=True, timeout=5
                )
                for line in result.stdout.strip().splitlines():
                    try:
                        pid = int(line.strip())
                        # Exclude go-vllm-api process to avoid killing our own proxy
                        cmd = subprocess.run(
                            ["cat", f"/proc/{pid}/cmdline"],
                            capture_output=True, text=True, timeout=2
                        ).stdout.replace("\x00", " ")
                        if "go-vllm-api" not in cmd and "go_vllm_api" not in cmd:
                            pids.append(pid)
                    except ValueError:
                        pass
            except Exception:
                pass

        return list(set(pids))

    def _check_vllm_logs_for_errors(self) -> Optional[str]:
        try:
            result = subprocess.run(
                ["journalctl", "-u", self._vllm_service_name, "-n", "50",
                 "--no-pager", "--output=short"],
                capture_output=True, text=True, timeout=5
            )
            for keyword in self.FATAL_KEYWORDS:
                if keyword.lower() in result.stdout.lower():
                    matched_lines = [line for line in result.stdout.splitlines()
                                     if keyword.lower() in line.lower()]
                    return matched_lines[-1] if matched_lines else keyword
        except Exception:
            pass
        return None
