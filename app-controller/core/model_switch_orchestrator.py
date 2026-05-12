import asyncio
import json
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

from core.gpu_memory_manager import _HEADROOM_GB, _SAFETY_RATIO
from core.vllm_manager import SYSTEMCTL_BIN

SWITCH_STATE_FILE = os.path.join(os.path.dirname(__file__), '..', 'scripts', '.switch_state.json')

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
    action: str = "switch"
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

    @classmethod
    def create_switch_phases(cls) -> List[PhaseDetail]:
        return [
            PhaseDetail(0, "GPU显存校验"),
            PhaseDetail(1, "更新配置并重启"),
            PhaseDetail(2, "冒烟测试"),
        ]

    @classmethod
    def create_start_phases(cls) -> List[PhaseDetail]:
        return [
            PhaseDetail(0, "GPU显存校验"),
            PhaseDetail(1, "停止旧服务"),
            PhaseDetail(2, "强制清理进程"),
            PhaseDetail(3, "启动新服务"),
            PhaseDetail(4, "冒烟测试"),
        ]

    @classmethod
    def create_stop_phases(cls) -> List[PhaseDetail]:
        return [
            PhaseDetail(1, "停止服务"),
            PhaseDetail(2, "强制清理进程"),
        ]

    def _calc_overall_progress(self) -> int:
        n = len(self.phases)
        if n == 0:
            return 0
        weight_each = 100 // n
        total = 0
        for p in self.phases:
            if p.status == PhaseStatus.SUCCESS:
                total += weight_each
            elif p.status == PhaseStatus.RUNNING:
                total += int(weight_each * p.progress / 100)
            elif p.status == PhaseStatus.SKIPPED:
                total += weight_each
        return min(total, 100)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "action": self.action,
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
    SWITCH_MAX_TIMEOUT = 600
    PHASE0_GPU_CHECK_TIMEOUT = 10
    PHASE1_STOP_TIMEOUT = 30
    PHASE1_PORT_CHECK_TIMEOUT = 15
    PHASE2_KILL_TIMEOUT = 60
    PHASE2_VERIFY_TIMEOUT = 15
    PHASE3_START_TIMEOUT = 480
    PHASE3_PORT_WAIT_TIMEOUT = 300
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
        "cuda error",
        "cuda failed",
        "fatal error",
        "assertion failed",
        "memory alloc",
    ]

    def __init__(self, ws_manager, vllm_service_name: str, vllm_port: int, model_base_path: str, gpu_memory_manager=None, engine_manager_mode: str = "systemd", config=None):
        self._ws_manager = ws_manager
        self._vllm_service_name = vllm_service_name
        self._vllm_port = vllm_port
        self._model_base_path = model_base_path
        self._gpu_memory_manager = gpu_memory_manager
        self._engine_manager_mode = engine_manager_mode
        self._config = config
        self._llm_service_manager = None
        self._global_lock = asyncio.Lock()
        self._current_session: Optional[SwitchSession] = None
        self._cancel_requested = False

    def _save_switch_state(self, session: SwitchSession):
        try:
            state = {
                "session_id": session.session_id,
                "action": session.action,
                "target_model": session.target_model,
                "target_model_path": session.target_model_path,
                "previous_model": session.previous_model,
                "previous_model_path": session.previous_model_path,
                "started_at": session.started_at,
                "overall_phase": session.overall_phase.value if isinstance(session.overall_phase, SwitchPhase) else session.overall_phase,
            }
            state_dir = os.path.dirname(SWITCH_STATE_FILE)
            if state_dir:
                os.makedirs(state_dir, exist_ok=True)
            with open(SWITCH_STATE_FILE, 'w') as f:
                json.dump(state, f, indent=2)
            logger.info("Saved switch state: target=%s", session.target_model)
        except Exception as e:
            logger.warning("Failed to save switch state: %s", e)

    def _clear_switch_state(self):
        try:
            if os.path.exists(SWITCH_STATE_FILE):
                os.remove(SWITCH_STATE_FILE)
                logger.info("Cleared switch state file")
        except Exception as e:
            logger.warning("Failed to clear switch state: %s", e)

    def load_pending_switch_state(self) -> Optional[Dict[str, Any]]:
        try:
            if os.path.exists(SWITCH_STATE_FILE):
                with open(SWITCH_STATE_FILE, 'r') as f:
                    state = json.load(f)
                logger.info("Found pending switch state: target=%s, phase=%s", state.get("target_model"), state.get("overall_phase"))
                return state
        except Exception as e:
            logger.warning("Failed to load switch state: %s", e)
        return None

    @property
    def is_switching(self) -> bool:
        return self._global_lock.locked()

    @property
    def current_session(self) -> Optional[SwitchSession]:
        return self._current_session

    def clear_completed_session(self):
        if self._current_session and not self.is_switching:
            self._current_session = None

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
                action="switch",
                phases=SwitchSession.create_switch_phases(),
            )
            self._current_session = session
            self._save_switch_state(session)

            try:
                session.overall_phase = SwitchPhase.IDLE
                try:
                    await asyncio.wait_for(
                        self._phase0_gpu_memory_check(session),
                        timeout=self.PHASE0_GPU_CHECK_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    session.error = f"GPU显存校验超时 ({self.PHASE0_GPU_CHECK_TIMEOUT}s)"
                    await self._rollback(session, session.error)
                    raise _SwitchAborted(session.error)

                session.overall_phase = SwitchPhase.PHASE1
                try:
                    await asyncio.wait_for(
                        self._phase1_update_config_and_restart(session),
                        timeout=self.SWITCH_MAX_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    session.error = f"切换超时 ({self.SWITCH_MAX_TIMEOUT}s)"
                    await self._rollback(session, session.error)
                    raise _SwitchAborted(session.error)

                session.overall_phase = SwitchPhase.PHASE2
                try:
                    await asyncio.wait_for(
                        self._phase2_smoke_test(session),
                        timeout=60,
                    )
                except asyncio.TimeoutError:
                    session.error = "冒烟测试超时 (60s)"
                    await self._rollback(session, session.error)
                    raise _SwitchAborted(session.error)

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
                self._clear_switch_state()

            return session

    async def start(
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
                action="start",
                phases=SwitchSession.create_start_phases(),
            )
            self._current_session = session

            try:
                session.overall_phase = SwitchPhase.IDLE
                try:
                    await asyncio.wait_for(
                        self._phase0_gpu_memory_check(session),
                        timeout=self.PHASE0_GPU_CHECK_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    session.error = f"GPU显存校验超时 ({self.PHASE0_GPU_CHECK_TIMEOUT}s)"
                    await self._rollback(session, session.error)
                    raise _SwitchAborted(session.error)

                session.overall_phase = SwitchPhase.PHASE1
                self._save_switch_state(session)
                try:
                    await asyncio.wait_for(
                        self._phase1_stop_and_verify(session),
                        timeout=self.SWITCH_MAX_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    session.error = f"停止服务超时 ({self.SWITCH_MAX_TIMEOUT}s)"
                    await self._rollback(session, session.error)
                    raise _SwitchAborted(session.error)

                session.overall_phase = SwitchPhase.PHASE2
                try:
                    await asyncio.wait_for(
                        self._phase2_force_kill_if_needed(session),
                        timeout=60,
                    )
                except asyncio.TimeoutError:
                    session.error = "清理进程超时 (60s)"
                    await self._rollback(session, session.error)
                    raise _SwitchAborted(session.error)

                session.overall_phase = SwitchPhase.PHASE3
                try:
                    await asyncio.wait_for(
                        self._phase3_start_and_check(session),
                        timeout=self.SWITCH_MAX_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    session.error = f"启动服务超时 ({self.SWITCH_MAX_TIMEOUT}s)"
                    await self._rollback(session, session.error)
                    raise _SwitchAborted(session.error)

                session.overall_phase = SwitchPhase.PHASE4
                try:
                    await asyncio.wait_for(
                        self._phase4_smoke_test(session),
                        timeout=60,
                    )
                except asyncio.TimeoutError:
                    session.error = "冒烟测试超时 (60s)"
                    await self._rollback(session, session.error)
                    raise _SwitchAborted(session.error)

                session.overall_phase = SwitchPhase.COMPLETED
                session.completed_successfully = True
                session.finished_at = datetime.now().isoformat()
                await self._broadcast(session, phase=4, progress=100,
                                      log="模型启动完成，所有测试通过", level="success", final=True)

            except _SwitchAborted:
                logger.error("Start aborted")

            except Exception as exc:
                logger.exception("Unexpected error during start: %s", exc)
                session.error = str(exc)
                await self._rollback(session, f"意外错误: {exc}", from_exception=True)

            finally:
                session.finished_at = session.finished_at or datetime.now().isoformat()
                self._clear_switch_state()

            return session

    async def stop(
        self,
        target_model: str,
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
                target_model_path=previous_model_path or "",
                previous_model=previous_model,
                previous_model_path=previous_model_path,
                started_at=datetime.now().isoformat(),
                action="stop",
                phases=SwitchSession.create_stop_phases(),
            )
            self._current_session = session
            self._save_switch_state(session)

            try:
                session.overall_phase = SwitchPhase.PHASE1
                try:
                    await asyncio.wait_for(
                        self._phase1_stop_and_verify(session),
                        timeout=self.SWITCH_MAX_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    session.error = f"停止服务超时 ({self.SWITCH_MAX_TIMEOUT}s)"
                    session.overall_phase = SwitchPhase.FAILED
                    session.finished_at = datetime.now().isoformat()
                    await self._broadcast(session, phase=1, progress=100,
                                          log=session.error, level="error", final=True)
                    raise _SwitchAborted(session.error)

                session.overall_phase = SwitchPhase.PHASE2
                try:
                    await asyncio.wait_for(
                        self._phase2_force_kill_if_needed(session),
                        timeout=60,
                    )
                except asyncio.TimeoutError:
                    session.error = "清理进程超时 (60s)"
                    session.overall_phase = SwitchPhase.FAILED
                    session.finished_at = datetime.now().isoformat()
                    await self._broadcast(session, phase=2, progress=100,
                                          log=session.error, level="error", final=True)
                    raise _SwitchAborted(session.error)

                session.overall_phase = SwitchPhase.COMPLETED
                session.completed_successfully = True
                session.finished_at = datetime.now().isoformat()
                await self._broadcast(session, phase=2, progress=100,
                                      log="模型停止完成", level="success", final=True)

            except _SwitchAborted:
                logger.error("Stop aborted")

            except Exception as exc:
                logger.exception("Unexpected error during stop: %s", exc)
                session.error = str(exc)
                session.overall_phase = SwitchPhase.FAILED
                session.finished_at = datetime.now().isoformat()
                await self._broadcast(session, phase=2, progress=100,
                                      log=f"模型停止失败: {exc}", level="error", final=True)

            finally:
                session.finished_at = session.finished_at or datetime.now().isoformat()
                self._clear_switch_state()

            return session

    def _get_phase(self, session: SwitchSession, phase_num: int) -> PhaseDetail:
        for p in session.phases:
            if p.phase == phase_num:
                return p
        raise ValueError(f"Phase {phase_num} not found in session")

    async def _kill_external_vllm_processes(self, session: SwitchSession, phase: PhaseDetail):
        import subprocess as _sp
        try:
            tracked_pids = set()
            if self._llm_service_manager:
                for svc in self._llm_service_manager.list_services():
                    p = self._llm_service_manager._processes.get(svc["service_name"])
                    if p and p.poll() is None:
                        tracked_pids.add(str(p.pid))
                        pgid = self._llm_service_manager._pgids.get(svc["service_name"])
                        if pgid and pgid > 0:
                            try:
                                os.killpg(pgid, signal.SIGINT)
                            except OSError:
                                pass
                        else:
                            p.send_signal(signal.SIGINT)
            result = _sp.run(
                ["pgrep", "-f", "vllm serve"],
                capture_output=True, text=True, timeout=5,
            )
            all_vllm_pids = [p for p in result.stdout.strip().split() if p]
            external_pids = [p for p in all_vllm_pids if p not in tracked_pids]
            if external_pids:
                await self._log(session, phase, f"发现外部vLLM进程: {external_pids}")
                for pid in external_pids:
                    try:
                        pgid = _sp.run(["ps", "-o", "pgid=", "-p", pid], capture_output=True, text=True, timeout=2).stdout.strip()
                        if pgid and int(pgid) > 0:
                            _sp.run(["kill", "-9", f"-{pgid}"], capture_output=True, timeout=3)
                        else:
                            _sp.run(["kill", "-9", pid], capture_output=True, timeout=3)
                    except Exception:
                        pass
                await self._log(session, phase, f"已强制终止外部vLLM进程: {external_pids}")
                await asyncio.sleep(5)
                remaining = _sp.run(["pgrep", "-f", "vllm serve"], capture_output=True, text=True, timeout=5)
                if remaining.stdout.strip():
                    await self._log(session, phase, f"警告: 仍有vLLM进程残留")
            else:
                await self._log(session, phase, "无外部vLLM进程需要终止")
        except Exception as e:
            await self._log(session, phase, f"清理外部进程失败: {e}")

    def _get_model_gpu_memory_utilization(self, model_name: str) -> float:
        default_gmu = 0.9
        if not self._config:
            return default_gmu
        models_dict = {}
        if hasattr(self._config, 'models'):
            models_dict = self._config.models if isinstance(self._config.models, dict) else {}
        elif isinstance(self._config, dict):
            models_dict = self._config.get('models', {})
        model_cfg = models_dict.get(model_name, {})
        vllm_params = model_cfg.get('vllm_params', {})
        if hasattr(model_cfg, 'vllm_params'):
            vp = model_cfg.vllm_params
            if hasattr(vp, 'gpu_memory_utilization'):
                return vp.gpu_memory_utilization
            elif isinstance(vp, dict):
                return vp.get('gpu_memory_utilization', default_gmu)
        gmu = vllm_params.get('gpu_memory_utilization', None)
        if gmu is not None:
            return gmu
        settings = {}
        if hasattr(self._config, 'settings'):
            settings = self._config.settings if isinstance(self._config.settings, dict) else {}
        elif isinstance(self._config, dict):
            settings = self._config.get('settings', {})
        return settings.get('default_gpu_memory_utilization', default_gmu)

    async def _phase0_gpu_memory_check(self, session: SwitchSession):
        phase = self._get_phase(session, 0)
        phase.status = PhaseStatus.RUNNING
        phase.started_at = datetime.now().isoformat()
        phase.progress = 10

        await self._log(session, phase, f"GPU显存校验: 模型 {session.target_model}")
        await self._broadcast(session, phase=0, progress=10, log="GPU显存校验")

        if not self._gpu_memory_manager:
            await self._log(session, phase, "无GPU显存管理器，跳过显存校验")
            phase.status = PhaseStatus.SKIPPED
            phase.progress = 100
            phase.finished_at = datetime.now().isoformat()
            await self._broadcast(session, phase=0, progress=100, log="显存校验跳过(无管理器)", level="warning")
            return

        model_name = session.target_model
        model_path = session.target_model_path

        previous_model = session.previous_model
        is_switch_action = session.action == "switch" and previous_model

        feasibility = self._gpu_memory_manager.check_model_feasibility(
            model_name, model_path=model_path
        )

        gmu = self._get_model_gpu_memory_utilization(model_name)
        await self._log(session, phase, f"模型 {model_name} gpu_memory_utilization={gmu}")

        should_check_with_release = (is_switch_action or (session.action == "start" and not feasibility.get("feasible"))) and not feasibility.get("feasible")
        if should_check_with_release:
            previous_model_path = session.previous_model_path
            info = self._gpu_memory_manager.checker.get_device_info(0)
            if info:
                model_weight_bytes = self._gpu_memory_manager.estimate_model_memory(
                    model_name, model_path=model_path
                )
                headroom = int(_HEADROOM_GB * 1024 ** 3)
                total_bytes = info.total_bytes
                total_available = int(total_bytes * _SAFETY_RATIO)
                vllm_required = int(total_bytes * gmu)
                total_gb = total_bytes / (1024 ** 3)
                model_weight_gb = model_weight_bytes / (1024 ** 3)
                vllm_required_gb = vllm_required / (1024 ** 3)
                safety_available_gb = total_available / (1024 ** 3)

                if is_switch_action and vllm_required > total_bytes:
                    feasibility = {
                        "feasible": False,
                        "reason": "gpu_memory_utilization_exceeds_total",
                        "available_gb": round(total_gb, 2),
                        "required_gb": round(vllm_required_gb, 2),
                        "safety_margin_gb": 0,
                        "gpu_available": True,
                        "note": f"vLLM gpu_memory_utilization={gmu} 需要 {vllm_required_gb:.2f}GB (GPU总×{gmu}), 超过GPU总显存 {total_gb:.2f}GB, 即使释放旧模型 {previous_model} 全部显存也无法运行",
                    }
                    await self._log(session, phase,
                                    f"显存校验失败: vLLM需要 {vllm_required_gb:.2f}GB (gpu_memory_utilization={gmu}), GPU总显存 {total_gb:.2f}GB")
                elif not is_switch_action and vllm_required > total_available:
                    feasibility = {
                        "feasible": False,
                        "reason": "gpu_memory_utilization_exceeds_safety",
                        "available_gb": round(safety_available_gb, 2),
                        "required_gb": round(vllm_required_gb, 2),
                        "safety_margin_gb": 0,
                        "gpu_available": True,
                        "note": f"vLLM gpu_memory_utilization={gmu} 需要 {vllm_required_gb:.2f}GB (GPU总×{gmu}), 但安全阈值仅 {safety_available_gb:.2f}GB (GPU总×{_SAFETY_RATIO}), 即即使释放旧模型 {previous_model} 全部显存也无法运行",
                    }
                    await self._log(session, phase,
                                    f"显存校验失败: vLLM需要 {vllm_required_gb:.2f}GB (gpu_memory_utilization={gmu}), 安全阈值 {safety_available_gb:.2f}GB (_SAFETY_RATIO={_SAFETY_RATIO})")
                elif is_switch_action and model_weight_bytes + headroom > total_bytes:
                    required_gb = model_weight_bytes / (1024 ** 3)
                    feasibility = {
                        "feasible": False,
                        "reason": "insufficient_memory_even_with_release",
                        "available_gb": round(total_gb, 2),
                        "required_gb": round(required_gb, 2),
                        "safety_margin_gb": 0,
                        "gpu_available": True,
                        "note": f"即使释放旧模型 {previous_model} 全部显存，模型权重 {model_weight_gb:.2f}GB + {_HEADROOM_GB}GB余量仍超过GPU总显存 {total_gb:.2f}GB",
                    }
                elif model_weight_bytes + headroom > total_available:
                    required_gb = model_weight_bytes / (1024 ** 3)
                    feasibility = {
                        "feasible": False,
                        "reason": "insufficient_memory_even_with_release",
                        "available_gb": round(safety_available_gb, 2),
                        "required_gb": round(required_gb, 2),
                        "safety_margin_gb": 0,
                        "gpu_available": True,
                        "note": f"即使释放旧模型 {previous_model} 全部显存，模型权重 {model_weight_gb:.2f}GB + {_HEADROOM_GB}GB余量仍超过可用 {safety_available_gb:.2f}GB",
                    }
                else:
                    current_effective = self._gpu_memory_manager.get_effective_free_bytes(0)
                    if is_switch_action:
                        available_for_check = total_bytes
                        available_gb_for_check = total_gb
                        safety_margin = total_bytes - model_weight_bytes - headroom
                    else:
                        available_for_check = total_available
                        available_gb_for_check = safety_available_gb
                        safety_margin = total_available - model_weight_bytes - headroom
                    await self._log(session, phase,
                                    f"显存校验(含旧模型释放): 停止旧模型后可用 {available_gb_for_check:.2f}GB, "
                                    f"模型权重 {model_weight_gb:.2f}GB, vLLM总需求 {vllm_required_gb:.2f}GB")
                    feasibility = {
                        "feasible": True,
                        "reason": None,
                        "available_gb": round(available_gb_for_check, 2),
                        "required_gb": round(model_weight_bytes / (1024 ** 3), 2),
                        "safety_margin_gb": round(max(safety_margin, 0) / (1024 ** 3), 2),
                        "gpu_available": True,
                        "note": f"停止旧模型 {previous_model} 后可用 {available_gb_for_check:.2f}GB, 模型权重 {model_weight_gb:.2f}GB + {_HEADROOM_GB}GB余量可满足 (vLLM实际占用约 {vllm_required_gb:.2f}GB)",
                    }

        phase.progress = 80
        await self._broadcast(session, phase=0, progress=80, log="显存校验计算完成")

        if not feasibility.get("feasible"):
            reason = feasibility.get("reason", "insufficient_memory")
            required_gb = feasibility.get("required_gb", 0)
            available_gb = feasibility.get("available_gb", 0)
            error_msg = f"GPU显存不足: 需要 {required_gb}GB, 可用 {available_gb}GB (原因: {reason})"
            phase.status = PhaseStatus.FAILED
            phase.error = error_msg
            phase.finished_at = datetime.now().isoformat()
            await self._log(session, phase, error_msg)
            await self._broadcast(session, phase=0, progress=100, log=error_msg, level="error")
            await self._rollback(session, error_msg)
            raise _SwitchAborted(error_msg)

        required_gb = feasibility.get("required_gb", 0)
        available_gb = feasibility.get("available_gb", 0)
        safety_margin_gb = feasibility.get("safety_margin_gb", 0)
        await self._log(session, phase, f"显存校验通过: 需要 {required_gb}GB, 可用 {available_gb}GB, 安全余量 {safety_margin_gb}GB")
        phase.status = PhaseStatus.SUCCESS
        phase.progress = 100
        phase.finished_at = datetime.now().isoformat()
        await self._broadcast(session, phase=0, progress=100, log="显存校验通过", level="success")

    async def _phase1_stop_and_verify(self, session: SwitchSession):
        phase = self._get_phase(session, 1)
        phase.status = PhaseStatus.RUNNING
        phase.started_at = datetime.now().isoformat()
        phase.progress = 10

        await self._log(session, phase, "停止 vLLM 服务...")
        await self._broadcast(session, phase=1, progress=10, log="停止旧服务")

        if self._engine_manager_mode == "subprocess" and self._llm_service_manager:
            for svc in self._llm_service_manager.list_services():
                self._llm_service_manager.stop_service(svc["service_name"])
                await self._log(session, phase, f"subprocess停止: {svc['service_name']}")

            port = self._vllm_port
            start_time = time.time()
            while time.time() - start_time < self.PHASE1_STOP_TIMEOUT:
                if self._cancel_requested:
                    raise _SwitchAborted("Cancelled")
                if not self._is_port_alive(port):
                    phase.status = PhaseStatus.SUCCESS
                    phase.progress = 100
                    phase.finished_at = datetime.now().isoformat()
                    await self._log(session, phase, "vLLM 服务已停止(subprocess)")
                    await self._broadcast(session, phase=1, progress=100, log="旧服务已停止", level="success")
                    return
                elapsed = int(time.time() - start_time)
                phase.progress = min(90, 10 + int(80 * elapsed / self.PHASE1_STOP_TIMEOUT))
                await self._broadcast(session, phase=1, progress=phase.progress, log=f"等待旧服务停止... ({elapsed}s)")
                await asyncio.sleep(1)

            error_msg = f"旧服务在 {self.PHASE1_STOP_TIMEOUT}s 内未停止"
            phase.status = PhaseStatus.FAILED
            phase.error = error_msg
            phase.finished_at = datetime.now().isoformat()
            await self._broadcast(session, phase=1, progress=100, log=error_msg, level="error")
            raise _SwitchAborted(error_msg)

        else:
            from core.vllm_manager import stop_vllm_service, discover_vllm_port
            stop_ok = stop_vllm_service()
            if not stop_ok:
                error_msg = "systemctl stop 失败"
                phase.status = PhaseStatus.FAILED
                phase.error = error_msg
                phase.finished_at = datetime.now().isoformat()
                await self._broadcast(session, phase=1, progress=100, log=error_msg, level="error")
                raise _SwitchAborted(error_msg)

            port = discover_vllm_port()
            start_time = time.time()
            while time.time() - start_time < self.PHASE1_STOP_TIMEOUT:
                if self._cancel_requested:
                    raise _SwitchAborted("Cancelled")
                if not self._is_port_alive(port):
                    phase.status = PhaseStatus.SUCCESS
                    phase.progress = 100
                    phase.finished_at = datetime.now().isoformat()
                    await self._log(session, phase, "vLLM 服务已停止")
                    await self._broadcast(session, phase=1, progress=100, log="旧服务已停止", level="success")
                    return
                elapsed = int(time.time() - start_time)
                phase.progress = min(90, 10 + int(80 * elapsed / self.PHASE1_STOP_TIMEOUT))
                await self._broadcast(session, phase=1, progress=phase.progress, log=f"等待旧服务停止... ({elapsed}s)")
                await asyncio.sleep(1)

            error_msg = f"旧服务在 {self.PHASE1_STOP_TIMEOUT}s 内未停止"
            phase.status = PhaseStatus.FAILED
            phase.error = error_msg
            phase.finished_at = datetime.now().isoformat()
            await self._broadcast(session, phase=1, progress=100, log=error_msg, level="error")
            raise _SwitchAborted(error_msg)

    async def _phase1_update_config_and_restart(self, session: SwitchSession):
        """Phase 1: 更新配置并重启服务"""
        phase = self._get_phase(session, 1)
        phase.status = PhaseStatus.RUNNING
        phase.started_at = datetime.now().isoformat()

        await self._log(session, phase, f"更新模型配置: {session.target_model}")
        phase.progress = 10
        await self._broadcast(session, phase=1, progress=10, log="更新模型配置")

        if self._engine_manager_mode == "subprocess" and self._llm_service_manager:
            await self._log(session, phase, "使用 subprocess 模式启动引擎")
            await self._broadcast(session, phase=1, progress=15, log="subprocess模式启动引擎")

            for svc in self._llm_service_manager.list_services():
                self._llm_service_manager.stop_service(svc["service_name"])
                await self._log(session, phase, f"已停止服务: {svc['service_name']}")

            await self._kill_external_vllm_processes(session, phase)

            if self._gpu_memory_manager:
                gpu_wait_start = time.time()
                gpu_wait_max = 30
                await self._log(session, phase, "等待GPU显存释放...")
                while time.time() - gpu_wait_start < gpu_wait_max:
                    try:
                        free_gb = self._gpu_memory_manager.get_effective_free_bytes(0) / (1024**3)
                        total_gb = 0
                        info = self._gpu_memory_manager.checker.get_device_info(0)
                        if info:
                            total_gb = info.total_bytes / (1024**3)
                        if free_gb >= total_gb * 0.8:
                            await self._log(session, phase, f"GPU显存已释放 (可用 {free_gb:.1f}GB / 总 {total_gb:.1f}GB)")
                            break
                        await self._log(session, phase, f"等待GPU释放... 可用 {free_gb:.1f}GB / 总 {total_gb:.1f}GB")
                    except Exception:
                        pass
                    await asyncio.sleep(2)
            else:
                await asyncio.sleep(5)

            result = self._llm_service_manager.start_service(
                session.target_model, session.target_model, "vllm", self._vllm_port,
                model_path=session.target_model_path,
            )
            if result.get("status") != "started":
                error_msg = f"subprocess启动失败: {result.get('message', 'unknown')}"
                phase.status = PhaseStatus.FAILED
                phase.error = error_msg
                phase.finished_at = datetime.now().isoformat()
                await self._rollback(session, error_msg)
                raise _SwitchAborted(error_msg)

            await self._log(session, phase, f"引擎进程已启动 (pid={result.get('pid')})")
        else:
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
        last_error_check = 0
        port_seen_alive = False
        while time.time() - start_time < self.PHASE3_START_TIMEOUT:
            if self._cancel_requested:
                await self._rollback(session, "用户请求取消")
                raise _SwitchAborted("Cancelled")

            elapsed = int(time.time() - start_time)
            progress = 35 + int(55 * elapsed / self.PHASE3_START_TIMEOUT)
            phase.progress = min(progress, 90)

            if self._engine_manager_mode == "subprocess":
                if elapsed - last_error_check >= 5:
                    svc_status = self._llm_service_manager.check_health(session.target_model) if self._llm_service_manager else False
                    if not svc_status and elapsed >= self.PHASE3_PORT_WAIT_TIMEOUT and not port_seen_alive:
                        phase.status = PhaseStatus.FAILED
                        phase.error = f"subprocess引擎在 {self.PHASE3_PORT_WAIT_TIMEOUT}s 内未就绪"
                        phase.finished_at = datetime.now().isoformat()
                        await self._rollback(session, phase.error)
                        raise _SwitchAborted(phase.error)
                    last_error_check = elapsed
            elif elapsed - last_error_check >= 5:
                error_msg = self._check_vllm_logs_for_errors()
                if error_msg:
                    phase.status = PhaseStatus.FAILED
                    phase.error = f"服务启动失败: {error_msg}"
                    phase.finished_at = datetime.now().isoformat()
                    await self._log(session, phase, f"检测到致命错误: {error_msg}")
                    await self._rollback(session, f"vLLM 服务致命错误: {error_msg}")
                    raise _SwitchAborted(f"Fatal error: {error_msg}")
                last_error_check = elapsed

            if self._engine_manager_mode == "subprocess":
                port = self._vllm_port
                health_url = f"http://127.0.0.1:{port}/health"
                base_url = f"http://127.0.0.1:{port}"
            else:
                from core.vllm_manager import discover_vllm_port, _build_vllm_health_url
                port = discover_vllm_port()
                health_url = _build_vllm_health_url(port)
                base_url = f"http://127.0.0.1:{port}"

            is_port_open = self._is_port_alive(port)
            if is_port_open:
                port_seen_alive = True
            elif elapsed >= self.PHASE3_PORT_WAIT_TIMEOUT and not port_seen_alive:
                phase.status = PhaseStatus.FAILED
                phase.error = f"服务重启后 {self.PHASE3_PORT_WAIT_TIMEOUT}s 内端口 {port} 未打开，服务可能未成功启动"
                phase.finished_at = datetime.now().isoformat()
                await self._log(session, phase, phase.error)
                await self._rollback(session, phase.error)
                raise _SwitchAborted(phase.error)

            try:
                async with httpx.AsyncClient(timeout=3) as client:
                    resp = await client.get(health_url)
                    if resp.status_code == 200:
                        try:
                            models_resp = await client.get(f"{base_url}/v1/models")
                            if models_resp.status_code == 200:
                                models_data = models_resp.json()
                                registered_ids = [m.get("id", "") for m in models_data.get("data", [])]
                                if registered_ids:
                                    actual_id = registered_ids[0]
                                    target_name = session.target_model
                                    if actual_id != session.target_model_path and (target_name not in actual_id):
                                        await self._log(session, phase,
                                                        f"模型ID不匹配: vLLM返回 {actual_id}, 目标 {target_name} ({session.target_model_path})")
                                        continue
                        except Exception as e:
                            await self._log(session, phase, f"模型ID验证失败(继续等待): {e}")
                            continue
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
        await self._do_smoke_test(session, 2)

    async def _do_smoke_test(self, session: SwitchSession, phase_num: int):
        phase = self._get_phase(session, phase_num)
        phase.status = PhaseStatus.RUNNING
        phase.started_at = datetime.now().isoformat()

        await self._log(session, phase, "开始冒烟测试...")
        phase.progress = 10
        await self._broadcast(session, phase=phase_num, progress=10, log="冒烟测试")

        if self._engine_manager_mode == "subprocess" and self._llm_service_manager:
            port = self._vllm_port
            base_url = f"http://127.0.0.1:{port}"
        else:
            from core.vllm_manager import discover_vllm_port, _build_vllm_base_url
            port = discover_vllm_port()
            base_url = _build_vllm_base_url(port)
        url = f"{base_url}/v1/chat/completions"

        actual_model_id = session.target_model_path
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                models_resp = await client.get(f"{base_url}/v1/models")
                if models_resp.status_code == 200:
                    models_data = models_resp.json()
                    registered_ids = [m.get("id", "") for m in models_data.get("data", [])]
                    if registered_ids:
                        actual_model_id = registered_ids[0]
                        if actual_model_id != session.target_model_path:
                            await self._log(session, phase,
                                           f"vLLM 模型ID: {actual_model_id} (配置路径: {session.target_model_path})")
                            target_model_name = session.target_model
                            if actual_model_id and target_model_name not in actual_model_id and actual_model_id != session.target_model_path:
                                error_msg = f"模型验证失败: vLLM加载的是 {actual_model_id}，但目标模型是 {target_model_name} ({session.target_model_path})"
                                phase.status = PhaseStatus.FAILED
                                phase.error = error_msg
                                phase.finished_at = datetime.now().isoformat()
                                await self._log(session, phase, error_msg)
                                await self._rollback(session, error_msg)
                                raise _SwitchAborted(error_msg)
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
            await self._broadcast(session, phase=phase_num, progress=phase.progress,
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
                            await self._broadcast(session, phase=phase_num, progress=100,
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

    async def _phase2_force_kill_if_needed(self, session: SwitchSession):
        phase = self._get_phase(session, 2)
        phase.status = PhaseStatus.RUNNING
        phase.started_at = datetime.now().isoformat()
        phase.progress = 10
        await self._log(session, phase, "检查并清理残留 vLLM 进程")
        await self._broadcast(session, phase=2, progress=10, log="强制清理进程")

        port = self._vllm_port
        pids = self._find_pids_on_port(port)
        if not pids:
            pids = self._find_vllm_pids()

        if not pids:
            phase.status = PhaseStatus.SUCCESS
            phase.progress = 100
            phase.finished_at = datetime.now().isoformat()
            await self._broadcast(session, phase=2, progress=100, log="未发现残留进程", level="success")
            return

        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
                await self._log(session, phase, f"已终止进程 {pid}")
            except ProcessLookupError:
                continue
            except Exception as exc:
                await self._log(session, phase, f"终止进程 {pid} 失败: {exc}")

        await asyncio.sleep(2)
        phase.status = PhaseStatus.SUCCESS
        phase.progress = 100
        phase.finished_at = datetime.now().isoformat()
        await self._broadcast(session, phase=2, progress=100, log="残留进程清理完成", level="success")

    async def _phase3_start_and_check(self, session: SwitchSession):
        phase = self._get_phase(session, 3)
        phase.status = PhaseStatus.RUNNING
        phase.started_at = datetime.now().isoformat()
        phase.progress = 10
        await self._log(session, phase, f"启动目标模型: {session.target_model}")
        await self._broadcast(session, phase=3, progress=10, log="启动新服务")

        if self._engine_manager_mode == "subprocess" and self._llm_service_manager:
            await self._log(session, phase, "subprocess模式启动引擎")
            result = self._llm_service_manager.start_service(
                session.target_model, session.target_model, "vllm", self._vllm_port,
                model_path=session.target_model_path,
            )
            if result.get("status") != "started":
                error_msg = f"subprocess启动失败: {result.get('message', 'unknown')}"
                phase.status = PhaseStatus.FAILED
                phase.error = error_msg
                phase.finished_at = datetime.now().isoformat()
                await self._rollback(session, error_msg)
                raise _SwitchAborted(error_msg)
            await self._log(session, phase, f"引擎进程已启动 (pid={result.get('pid')})")
        else:
            from core.vllm_manager import _update_vllm_script, refresh_vllm_port_cache, start_vllm_service, _build_vllm_health_url
            script_ok = _update_vllm_script(session.target_model_path, session.target_model)
            if not script_ok:
                error_msg = "更新模型路径配置失败"
                phase.status = PhaseStatus.FAILED
                phase.error = error_msg
                phase.finished_at = datetime.now().isoformat()
                await self._rollback(session, error_msg)
                raise _SwitchAborted(error_msg)

            refresh_vllm_port_cache()
            start_ok = start_vllm_service()
            if not start_ok:
                error_msg = "systemctl start 失败"
                phase.status = PhaseStatus.FAILED
                phase.error = error_msg
                phase.finished_at = datetime.now().isoformat()
                await self._rollback(session, error_msg)
                raise _SwitchAborted(error_msg)

        start_time = time.time()
        last_error_check = 0
        port_seen_alive = False
        while time.time() - start_time < self.PHASE3_START_TIMEOUT:
            if self._cancel_requested:
                await self._rollback(session, "用户请求取消")
                raise _SwitchAborted("Cancelled")

            elapsed = int(time.time() - start_time)
            phase.progress = min(95, 15 + int(80 * elapsed / self.PHASE3_START_TIMEOUT))

            if elapsed - last_error_check >= 5:
                error_msg = self._check_vllm_logs_for_errors()
                if error_msg:
                    phase.status = PhaseStatus.FAILED
                    phase.error = f"服务启动失败: {error_msg}"
                    phase.finished_at = datetime.now().isoformat()
                    await self._log(session, phase, f"检测到致命错误: {error_msg}")
                    await self._rollback(session, f"vLLM 服务致命错误: {error_msg}")
                    raise _SwitchAborted(f"Fatal error: {error_msg}")
                last_error_check = elapsed

            try:
                if self._engine_manager_mode == "subprocess":
                    port = self._vllm_port
                    health_url = f"http://127.0.0.1:{port}/health"
                else:
                    from core.vllm_manager import discover_vllm_port
                    port = discover_vllm_port()
                    health_url = _build_vllm_health_url(port)
                is_port_open = self._is_port_alive(port)
                if is_port_open:
                    port_seen_alive = True
                elif elapsed >= self.PHASE3_PORT_WAIT_TIMEOUT and not port_seen_alive:
                    phase.status = PhaseStatus.FAILED
                    phase.error = f"服务启动后 {self.PHASE3_PORT_WAIT_TIMEOUT}s 内端口 {port} 未打开"
                    phase.finished_at = datetime.now().isoformat()
                    await self._rollback(session, phase.error)
                    raise _SwitchAborted(phase.error)

                async with httpx.AsyncClient(timeout=3) as client:
                    resp = await client.get(health_url)
                    if resp.status_code == 200:
                        phase.status = PhaseStatus.SUCCESS
                        phase.progress = 100
                        phase.finished_at = datetime.now().isoformat()
                        await self._broadcast(session, phase=3, progress=100, log="新服务已就绪", level="success")
                        return
            except Exception:
                pass
            await self._broadcast(session, phase=3, progress=phase.progress, log=f"等待新服务就绪... ({elapsed}s)")
            await asyncio.sleep(3)

        error_msg = f"新服务在 {self.PHASE3_START_TIMEOUT}s 内未就绪"
        phase.status = PhaseStatus.FAILED
        phase.error = error_msg
        phase.finished_at = datetime.now().isoformat()
        await self._rollback(session, error_msg)
        raise _SwitchAborted(error_msg)

    async def _phase4_smoke_test(self, session: SwitchSession):
        await self._do_smoke_test(session, 4)


    async def _rollback(self, session: SwitchSession, reason: str, from_exception: bool = False):
        session.overall_phase = SwitchPhase.ROLLING_BACK
        session.rollback_reason = reason
        session.error = reason

        await self._broadcast(session, phase=0, progress=0,
                              log=f"开始回滚: {reason}", level="warning",
                              event_type="rollback_started")

        if self._engine_manager_mode == "subprocess" and self._llm_service_manager:
            from core.vllm_manager import _cleanup_runtime_override
            _cleanup_runtime_override()

            for svc in self._llm_service_manager.list_services():
                self._llm_service_manager.stop_service(svc["service_name"])
            await self._log(session, self._get_phase(session, 0), "rollback: 已停止所有追踪的服务")

            import subprocess as _sp
            try:
                result = _sp.run(["pgrep", "-f", "vllm serve"], capture_output=True, text=True, timeout=5)
                remaining_pids = [p for p in result.stdout.strip().split() if p]
                if remaining_pids:
                    await self._log(session, self._get_phase(session, 0), f"rollback: 发现残留vLLM进程 {remaining_pids}，正在终止")
                    for pid in remaining_pids:
                        try:
                            pgid = _sp.run(["ps", "-o", "pgid=", "-p", pid], capture_output=True, text=True, timeout=2).stdout.strip()
                            if pgid and int(pgid) > 0:
                                _sp.run(["kill", "-9", f"-{pgid}"], capture_output=True, timeout=3)
                            else:
                                _sp.run(["kill", "-9", pid], capture_output=True, timeout=3)
                        except Exception:
                            pass
                    await asyncio.sleep(5)
                    verify = _sp.run(["pgrep", "-f", "vllm serve"], capture_output=True, text=True, timeout=5)
                    if verify.stdout.strip():
                        await self._log(session, self._get_phase(session, 0), f"rollback: 警告 - 仍有残留进程")
                    else:
                        await self._log(session, self._get_phase(session, 0), "rollback: 残留进程已清理")
            except Exception as e:
                await self._log(session, self._get_phase(session, 0), f"rollback: 清理残留进程失败 {e}")

            gpu_wait_start = time.time()
            gpu_wait_max = 30
            if self._gpu_memory_manager:
                await self._log(session, self._get_phase(session, 0), "rollback: 等待GPU显存释放...")
                while time.time() - gpu_wait_start < gpu_wait_max:
                    try:
                        free_gb = self._gpu_memory_manager.get_effective_free_bytes(0) / (1024**3)
                        total_gb = 0
                        info = self._gpu_memory_manager.checker.get_device_info(0)
                        if info:
                            total_gb = info.total_bytes / (1024**3)
                        if free_gb >= total_gb * 0.8:
                            await self._log(session, self._get_phase(session, 0), f"rollback: GPU显存已释放 (可用 {free_gb:.1f}GB / 总 {total_gb:.1f}GB)")
                            break
                    except Exception:
                        pass
                    await asyncio.sleep(2)

            if session.action == "start":
                await self._broadcast(session, phase=0, progress=50,
                                      log="start action rollback: 不恢复旧模型，服务保持停止状态", level="warning")
            elif session.previous_model_path and session.previous_model:
                await self._broadcast(session, phase=0, progress=20,
                                      log=f"subprocess模式回滚: {session.previous_model}",
                                      level="warning")

                result = self._llm_service_manager.start_service(
                    session.previous_model, session.previous_model, "vllm", self._vllm_port,
                    model_path=session.previous_model_path,
                )
                if result.get("status") == "started":
                    await self._broadcast(session, phase=0, progress=80,
                                          log="旧模型subprocess已启动，等待就绪", level="warning")
                    rollback_wait_max = 120
                    rollback_start = time.time()
                    while time.time() - rollback_start < rollback_wait_max:
                        await asyncio.sleep(3)
                        try:
                            async with httpx.AsyncClient(timeout=3) as client:
                                resp = await client.get(f"http://127.0.0.1:{self._vllm_port}/health")
                                if resp.status_code == 200:
                                    await self._log(session, self._get_phase(session, 0),
                                                   "旧模型服务已恢复就绪(subprocess)")
                                    break
                        except Exception:
                            pass
                else:
                    logger.error("Rollback subprocess start failed: %s", result)
            else:
                await self._broadcast(session, phase=0, progress=50,
                                      log="无旧模型记录，服务保持停止状态", level="warning")
        else:
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
                            from core.vllm_manager import discover_vllm_port, _build_vllm_health_url
                            port = discover_vllm_port()
                            async with httpx.AsyncClient(timeout=3) as client:
                                resp = await client.get(_build_vllm_health_url(port))
                                if resp.status_code == 200:
                                    await self._log(session, self._get_phase(session, 0),
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
        if self._engine_manager_mode == "subprocess":
            return None

        try:
            result = subprocess.run(
                ["journalctl", "-u", self._vllm_service_name, "-n", "100",
                 "--no-pager", "--output=short", "--since", "2 min ago"],
                capture_output=True, text=True, timeout=5
            )
            logs = result.stdout
            for keyword in self.FATAL_KEYWORDS:
                if keyword.lower() in logs.lower():
                    matched_lines = [line for line in logs.splitlines()
                                     if keyword.lower() in line.lower()]
                    return matched_lines[-1] if matched_lines else keyword

            result = subprocess.run(
                [SYSTEMCTL_BIN, "is-failed", self._vllm_service_name],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0:
                status_result = subprocess.run(
                    [SYSTEMCTL_BIN, "status", self._vllm_service_name, "--no-pager", "-n", "20"],
                    capture_output=True, text=True, timeout=5
                )
                return f"服务处于 failed 状态: {status_result.stdout[:200]}"
        except Exception:
            pass
        return None
