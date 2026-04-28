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
    PHASE3_START_TIMEOUT = 180
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
                session.overall_phase = SwitchPhase.PHASE1
                await self._phase1_stop_and_verify(session)

                session.overall_phase = SwitchPhase.PHASE2
                await self._phase2_force_kill_if_needed(session)

                session.overall_phase = SwitchPhase.PHASE3
                await self._phase3_start_and_check(session)

                session.overall_phase = SwitchPhase.PHASE4
                await self._phase4_smoke_test(session)

                session.overall_phase = SwitchPhase.COMPLETED
                session.completed_successfully = True
                session.finished_at = datetime.now().isoformat()
                await self._broadcast(session, phase=4, progress=100,
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

    async def _phase1_stop_and_verify(self, session: SwitchSession):
        phase = session.phases[0]
        phase.status = PhaseStatus.RUNNING
        phase.started_at = datetime.now().isoformat()

        await self._log(session, phase, "开始停止 vLLM 服务")
        await self._broadcast(session, phase=1, progress=10, log="停止 vLLM 服务中")

        from core.vllm_manager import stop_vllm_service
        stop_ok = stop_vllm_service()

        if not stop_ok:
            await self._log(session, phase, "systemctl stop 返回非零，继续检测端口")
        else:
            await self._log(session, phase, "systemctl stop 指令发送成功")

        await self._broadcast(session, phase=1, progress=30, log="检测端口是否释放")

        start_time = time.time()
        poll_interval = 1.0
        while time.time() - start_time < self.PHASE1_PORT_CHECK_TIMEOUT:
            if self._cancel_requested:
                await self._rollback(session, "用户请求取消")
                raise _SwitchAborted("Cancelled")

            if not self._is_port_alive(self._vllm_port):
                phase.progress = 90
                await self._log(session, phase, f"端口 {self._vllm_port} 已释放")
                await self._broadcast(session, phase=1, progress=90,
                                      log=f"端口 {self._vllm_port} 已释放")
                break
            elapsed = int(time.time() - start_time)
            await self._log(session, phase,
                           f"等待端口释放 ({elapsed}s/{self.PHASE1_PORT_CHECK_TIMEOUT}s)")
            await asyncio.sleep(poll_interval)
            poll_interval = min(poll_interval * 1.5, 3)

        if self._is_port_alive(self._vllm_port):
            await self._log(session, phase,
                           f"{self.PHASE1_PORT_CHECK_TIMEOUT}s 内端口未释放，进入强制清理阶段")

        phase.status = PhaseStatus.SUCCESS
        phase.progress = 100
        phase.finished_at = datetime.now().isoformat()
        await self._broadcast(session, phase=1, progress=100, log="阶段1完成")

    async def _phase2_force_kill_if_needed(self, session: SwitchSession):
        phase = session.phases[1]
        phase.status = PhaseStatus.RUNNING
        phase.started_at = datetime.now().isoformat()

        if not self._is_port_alive(self._vllm_port) and not self._find_vllm_pids():
            phase.status = PhaseStatus.SKIPPED
            phase.progress = 100
            phase.finished_at = datetime.now().isoformat()
            await self._log(session, phase, "无残留进程，跳过强制清理")
            await self._broadcast(session, phase=2, progress=100, log="无残留进程，跳过")
            return

        await self._broadcast(session, phase=2, progress=10,
                              log="发现残留 vLLM 进程，开始清理")

        pids = self._find_vllm_pids()
        await self._log(session, phase, f"发现 vLLM 进程: {pids}")

        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
                await self._log(session, phase, f"SIGTERM -> PID {pid}")
            except ProcessLookupError:
                pass

        await self._broadcast(session, phase=2, progress=30,
                              log=f"SIGTERM 已发送，等待进程退出（最多 {self.PHASE2_KILL_TIMEOUT}s）")

        start_time = time.time()
        poll_interval = 2.0
        while time.time() - start_time < self.PHASE2_KILL_TIMEOUT:
            if self._cancel_requested:
                await self._rollback(session, "用户请求取消")
                raise _SwitchAborted("Cancelled")

            alive = self._find_vllm_pids()
            if not alive:
                break
            elapsed = int(time.time() - start_time)
            progress = 30 + int(50 * elapsed / self.PHASE2_KILL_TIMEOUT)
            await self._broadcast(session, phase=2, progress=progress,
                                  log=f"等待进程退出... ({elapsed}s)")
            await asyncio.sleep(poll_interval)
            poll_interval = min(poll_interval * 1.2, 5)

        still_alive = self._find_vllm_pids()
        if still_alive:
            await self._log(session, phase, f"进程未响应 SIGTERM，执行 SIGKILL: {still_alive}")
            for pid in still_alive:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            await asyncio.sleep(2)

        start_verify = time.time()
        while time.time() - start_verify < self.PHASE2_VERIFY_TIMEOUT:
            remaining = self._find_vllm_pids()
            if not remaining and not self._is_port_alive(self._vllm_port):
                break
            await asyncio.sleep(2)

        remaining = self._find_vllm_pids()
        port_alive = self._is_port_alive(self._vllm_port)
        if remaining:
            error_msg = f"无法清理 vLLM 进程: {remaining}"
            phase.status = PhaseStatus.FAILED
            phase.error = error_msg
            phase.finished_at = datetime.now().isoformat()
            await self._log(session, phase, error_msg)
            await self._rollback(session, error_msg)
            raise _SwitchAborted(error_msg)

        if port_alive:
            await self._log(session, phase,
                           f"端口 {self._vllm_port} 仍有连接但无 vLLM 进程，可能是 TIME_WAIT 状态")
            port_pids = self._find_pids_on_port(self._vllm_port)
            if port_pids:
                await self._log(session, phase, f"端口上发现进程: {port_pids}，执行 SIGKILL")
                for pid in port_pids:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                await asyncio.sleep(3)
                if self._is_port_alive(self._vllm_port):
                    error_msg = f"端口 {self._vllm_port} 仍无法释放"
                    phase.status = PhaseStatus.FAILED
                    phase.error = error_msg
                    phase.finished_at = datetime.now().isoformat()
                    await self._log(session, phase, error_msg)
                    await self._rollback(session, error_msg)
                    raise _SwitchAborted(error_msg)

        phase.status = PhaseStatus.SUCCESS
        phase.progress = 100
        phase.finished_at = datetime.now().isoformat()
        await self._log(session, phase, "所有 vLLM 进程已清理")
        await self._broadcast(session, phase=2, progress=100,
                              log="进程清理完成", level="success")

    async def _phase3_start_and_check(self, session: SwitchSession):
        phase = session.phases[2]
        phase.status = PhaseStatus.RUNNING
        phase.started_at = datetime.now().isoformat()

        await self._log(session, phase, f"更新模型配置: {session.target_model_path}")
        await self._broadcast(session, phase=3, progress=5, log="更新模型配置")

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

        from core.vllm_manager import start_vllm_service
        await self._broadcast(session, phase=3, progress=10, log="启动 vLLM 服务")
        start_ok = start_vllm_service()
        if not start_ok:
            error_msg = "systemctl start 失败"
            phase.status = PhaseStatus.FAILED
            phase.error = error_msg
            phase.finished_at = datetime.now().isoformat()
            await self._rollback(session, error_msg)
            raise _SwitchAborted(error_msg)

        await self._log(session, phase, "vLLM 服务启动指令已发送")

        start_time = time.time()
        poll_interval = 2.0
        while time.time() - start_time < self.PHASE3_START_TIMEOUT:
            if self._cancel_requested:
                await self._rollback(session, "用户请求取消")
                raise _SwitchAborted("Cancelled")

            elapsed = int(time.time() - start_time)
            progress = 15 + int(75 * elapsed / self.PHASE3_START_TIMEOUT)

            error_in_logs = self._check_vllm_logs_for_errors()
            if error_in_logs:
                error_msg = f"vLLM 启动日志异常: {error_in_logs}"
                phase.status = PhaseStatus.FAILED
                phase.error = error_msg
                phase.finished_at = datetime.now().isoformat()
                await self._log(session, phase, error_msg)
                await self._rollback(session, error_msg)
                raise _SwitchAborted(error_msg)

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
                        await self._broadcast(session, phase=3, progress=100,
                                              log="vLLM 服务就绪", level="success")
                        return
            except Exception:
                pass

            await self._broadcast(session, phase=3, progress=min(progress, 90),
                                  log=f"等待服务就绪... ({elapsed}s/{self.PHASE3_START_TIMEOUT}s)")
            await asyncio.sleep(poll_interval)
            poll_interval = min(poll_interval * 1.3, 8)

        error_msg = f"vLLM 服务在 {self.PHASE3_START_TIMEOUT}s 内未就绪"
        phase.status = PhaseStatus.FAILED
        phase.error = error_msg
        phase.finished_at = datetime.now().isoformat()
        await self._rollback(session, error_msg)
        raise _SwitchAborted(error_msg)

    async def _phase4_smoke_test(self, session: SwitchSession):
        phase = session.phases[3]
        phase.status = PhaseStatus.RUNNING
        phase.started_at = datetime.now().isoformat()

        from core.vllm_manager import discover_vllm_port
        port = discover_vllm_port()
        url = f"http://localhost:{port}/v1/chat/completions"

        payload = {
            "model": session.target_model,
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 5,
            "temperature": 0.0,
        }

        for attempt in range(1, self.PHASE4_TEST_RETRIES + 1):
            progress = int(80 * attempt / self.PHASE4_TEST_RETRIES)
            await self._broadcast(session, phase=4, progress=progress,
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
                            await self._broadcast(session, phase=4, progress=100,
                                                  log="冒烟测试通过", level="success")
                            return
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
