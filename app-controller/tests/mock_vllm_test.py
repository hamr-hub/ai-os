import asyncio
import json
import os
import sys
import time
import httpx
import logging
import uuid
import subprocess
import signal
import socket

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.model_switch_orchestrator import (
    ModelSwitchOrchestrator,
    SwitchPhase,
    PhaseStatus,
    SwitchSession,
    PhaseDetail,
    _SwitchAborted,
)
from core.websocket_manager import WebSocketManager

MOCK_VLLM_PORT = 18888
MOCK_VLLM_SERVICE_NAME = "vllm-mock-test"

logger = logging.getLogger("mock_test")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")


class MockVLLMState:
    running: bool = False
    model_name: str = "Qwen3.6-35B-A3B-NVFP4"
    model_path: str = "/mnt/pve_models/Qwen3.6-35B-A3B-NVFP4"
    start_fail_mode: bool = False
    chat_fail_mode: bool = False
    server_process: subprocess.Popen = None
    health_delay_seconds: float = 0.5


mock_state = MockVLLMState()

mock_server_script = os.path.join(os.path.dirname(__file__), "mock_vllm_server.py")


def _start_mock_server(chat_fail=False):
    env = os.environ.copy()
    env["MOCK_VLLM_PORT"] = str(MOCK_VLLM_PORT)
    env["MOCK_CHAT_FAIL"] = str(int(chat_fail))
    env["MOCK_HEALTH_DELAY"] = str(mock_state.health_delay_seconds)

    proc = subprocess.Popen(
        [sys.executable, mock_server_script],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    for _ in range(20):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', MOCK_VLLM_PORT))
            sock.close()
            if result == 0:
                logger.info("Mock vLLM server started on port %d (PID=%d)", MOCK_VLLM_PORT, proc.pid)
                mock_state.server_process = proc
                mock_state.running = True
                return proc
        except Exception:
            pass
        time.sleep(0.5)

    stderr = proc.stderr.read().decode() if proc.stderr else ""
    logger.error("Mock vLLM server failed to start: %s", stderr[:500])
    raise RuntimeError("Mock vLLM server failed to start")


def _kill_mock_server():
    proc = mock_state.server_process
    if proc is None:
        mock_state.running = False
        return
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
            proc.wait(timeout=3)
        except Exception:
            pass
    mock_state.server_process = None
    mock_state.running = False

    for _ in range(10):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', MOCK_VLLM_PORT))
            sock.close()
            if result != 0:
                logger.info("Mock vLLM port %d confirmed free", MOCK_VLLM_PORT)
                return
        except Exception:
            return
        time.sleep(0.5)
    logger.warning("Mock vLLM port %d still not free after kill", MOCK_VLLM_PORT)


def mock_stop_vllm_service() -> bool:
    logger.info("[MOCK] stop_vllm_service called, killing mock server")
    _kill_mock_server()
    return True


def mock_start_vllm_service() -> bool:
    logger.info("[MOCK] start_vllm_service called, fail_mode=%s", mock_state.start_fail_mode)
    if mock_state.start_fail_mode:
        return False
    try:
        _start_mock_server(chat_fail=mock_state.chat_fail_mode)
        return True
    except Exception as e:
        logger.error("[MOCK] Failed to start mock server: %s", e)
        return False


def mock__update_vllm_script(model_path: str, model_name: str = None) -> bool:
    logger.info("[MOCK] _update_vllm_script(%s, %s)", model_path, model_name)
    mock_state.model_path = model_path
    if model_name:
        mock_state.model_name = model_name
    return True


def mock_discover_vllm_port() -> int:
    return MOCK_VLLM_PORT


def mock_refresh_vllm_port_cache():
    logger.info("[MOCK] refresh_vllm_port_cache called")


def patch_vllm_manager_module():
    import core.vllm_manager as vm
    vm.stop_vllm_service = mock_stop_vllm_service
    vm.start_vllm_service = mock_start_vllm_service
    vm._update_vllm_script = mock__update_vllm_script
    vm.discover_vllm_port = mock_discover_vllm_port
    vm.refresh_vllm_port_cache = mock_refresh_vllm_port_cache
    logger.info("Patched core.vllm_manager with mock functions")


ws_manager = WebSocketManager()

orchestrator = ModelSwitchOrchestrator(
    ws_manager=ws_manager,
    vllm_service_name=MOCK_VLLM_SERVICE_NAME,
    vllm_port=MOCK_VLLM_PORT,
    model_base_path="/mnt/pve_models",
)

orchestrator.PHASE1_STOP_TIMEOUT = 30
orchestrator.PHASE1_PORT_CHECK_TIMEOUT = 15
orchestrator.PHASE2_KILL_TIMEOUT = 30
orchestrator.PHASE2_VERIFY_TIMEOUT = 10
orchestrator.PHASE3_START_TIMEOUT = 60
orchestrator.PHASE4_TEST_RETRIES = 3
orchestrator.PHASE4_TEST_TIMEOUT = 10

orchestrator._check_vllm_logs_for_errors = lambda: None
orchestrator._find_vllm_pids = lambda: []
orchestrator._find_pids_on_port = lambda port: []
logger.info("Patched orchestrator internal methods")


class WSCollector:
    def __init__(self):
        self.messages: list = []

    async def broadcast(self, message, channel=None):
        self.messages.append(message)
        logger.info("[WS] ch=%s phase=%s prog=%s%% log=%s lvl=%s evt=%s",
                    channel,
                    message.get("overall_phase"),
                    message.get("overall_progress"),
                    message.get("log"),
                    message.get("level"),
                    message.get("event_type", "switch_progress"))


async def test_normal_switch():
    logger.info("=" * 60)
    logger.info("TEST 1: Normal model switch (all 4 phases succeed)")
    logger.info("=" * 60)

    ws = WSCollector()
    orchestrator._ws_manager = ws
    orchestrator._current_session = None
    orchestrator._cancel_requested = False
    mock_state.start_fail_mode = False
    mock_state.chat_fail_mode = False
    mock_state.health_delay_seconds = 0.3

    _start_mock_server(chat_fail=False)

    try:
        session = await orchestrator.switch(
            target_model="Qwen3-235B",
            target_model_path="/mnt/pve_models/Qwen3-235B",
            previous_model="Qwen3.6-35B-A3B-NVFP4",
            previous_model_path="/mnt/pve_models/Qwen3.6-35B-A3B-NVFP4",
        )

        logger.info("Result: phase=%s success=%s error=%s",
                    session.overall_phase.value, session.completed_successfully, session.error)
        for p in session.phases:
            logger.info("  Phase%d [%s]: status=%s progress=%d error=%s",
                        p.phase, p.name, p.status.value, p.progress, p.error)

        assert session.completed_successfully, f"Expected success, got: {session.error}"
        assert session.overall_phase == SwitchPhase.COMPLETED
        assert all(p.status in (PhaseStatus.SUCCESS, PhaseStatus.SKIPPED) for p in session.phases)

        logger.info("TEST 1 PASSED")
        return True
    except Exception as e:
        logger.error("TEST 1 FAILED: %s", e, exc_info=True)
        return False
    finally:
        _kill_mock_server()
        orchestrator._current_session = None
        if orchestrator._global_lock.locked():
            orchestrator._global_lock.release()


async def test_concurrent_switch():
    logger.info("=" * 60)
    logger.info("TEST 2: Concurrent switch (lock exclusion)")
    logger.info("=" * 60)

    ws = WSCollector()
    orchestrator._ws_manager = ws
    orchestrator._current_session = None
    orchestrator._cancel_requested = False
    mock_state.start_fail_mode = False
    mock_state.chat_fail_mode = False
    mock_state.health_delay_seconds = 0.3

    _start_mock_server(chat_fail=False)

    try:
        task1 = asyncio.create_task(
            orchestrator.switch(
                target_model="Model-A",
                target_model_path="/mnt/pve_models/Model-A",
                previous_model="Model-Old",
                previous_model_path="/mnt/pve_models/Model-Old",
            )
        )

        await asyncio.sleep(0.5)

        try:
            task2 = asyncio.create_task(
                orchestrator.switch(
                    target_model="Model-B",
                    target_model_path="/mnt/pve_models/Model-B",
                )
            )
            await task2
            logger.error("TEST 2 FAILED: Second switch should have been rejected")
            return False
        except RuntimeError as e:
            logger.info("Second switch correctly rejected: %s", e)

        session1 = await task1
        logger.info("First switch: phase=%s success=%s",
                    session1.overall_phase.value, session1.completed_successfully)

        assert session1.completed_successfully
        assert not orchestrator.is_switching

        logger.info("TEST 2 PASSED")
        return True
    except Exception as e:
        logger.error("TEST 2 FAILED: %s", e, exc_info=True)
        return False
    finally:
        _kill_mock_server()
        orchestrator._current_session = None
        if orchestrator._global_lock.locked():
            orchestrator._global_lock.release()


async def test_start_failure_rollback():
    logger.info("=" * 60)
    logger.info("TEST 3: Start failure triggers rollback")
    logger.info("=" * 60)

    ws = WSCollector()
    orchestrator._ws_manager = ws
    orchestrator._current_session = None
    orchestrator._cancel_requested = False
    mock_state.start_fail_mode = True
    mock_state.chat_fail_mode = False
    mock_state.health_delay_seconds = 0.3

    _start_mock_server(chat_fail=False)

    try:
        session = await orchestrator.switch(
            target_model="Bad-Model",
            target_model_path="/mnt/pve_models/Bad-Model",
            previous_model="Qwen3.6-35B-A3B-NVFP4",
            previous_model_path="/mnt/pve_models/Qwen3.6-35B-A3B-NVFP4",
        )

        logger.info("Result: phase=%s success=%s rollback=%s",
                    session.overall_phase.value, session.completed_successfully, session.rollback_reason)
        for p in session.phases:
            logger.info("  Phase%d [%s]: status=%s error=%s",
                        p.phase, p.name, p.status.value, p.error)

        assert not session.completed_successfully
        assert session.overall_phase in (SwitchPhase.ROLLED_BACK, SwitchPhase.FAILED)
        assert session.rollback_reason is not None

        logger.info("TEST 3 PASSED")
        return True
    except Exception as e:
        logger.error("TEST 3 FAILED: %s", e, exc_info=True)
        return False
    finally:
        mock_state.start_fail_mode = False
        _kill_mock_server()
        orchestrator._current_session = None
        if orchestrator._global_lock.locked():
            orchestrator._global_lock.release()


async def test_chat_smoke_failure_rollback():
    logger.info("=" * 60)
    logger.info("TEST 4: Chat smoke test failure triggers rollback")
    logger.info("=" * 60)

    ws = WSCollector()
    orchestrator._ws_manager = ws
    orchestrator._current_session = None
    orchestrator._cancel_requested = False
    mock_state.start_fail_mode = False
    mock_state.chat_fail_mode = True
    mock_state.health_delay_seconds = 0.3

    _start_mock_server(chat_fail=False)

    try:
        session = await orchestrator.switch(
            target_model="ChatFail-Model",
            target_model_path="/mnt/pve_models/ChatFail-Model",
            previous_model="Qwen3.6-35B-A3B-NVFP4",
            previous_model_path="/mnt/pve_models/Qwen3.6-35B-A3B-NVFP4",
        )

        logger.info("Result: phase=%s success=%s rollback=%s",
                    session.overall_phase.value, session.completed_successfully, session.rollback_reason)
        for p in session.phases:
            logger.info("  Phase%d [%s]: status=%s error=%s",
                        p.phase, p.name, p.status.value, p.error)

        assert not session.completed_successfully
        assert session.phases[3].status == PhaseStatus.FAILED
        assert session.overall_phase in (SwitchPhase.ROLLED_BACK, SwitchPhase.FAILED)

        logger.info("TEST 4 PASSED")
        return True
    except Exception as e:
        logger.error("TEST 4 FAILED: %s", e, exc_info=True)
        return False
    finally:
        mock_state.chat_fail_mode = False
        _kill_mock_server()
        orchestrator._current_session = None
        if orchestrator._global_lock.locked():
            orchestrator._global_lock.release()


async def test_cancel_switch():
    logger.info("=" * 60)
    logger.info("TEST 5: Cancel switch mid-process")
    logger.info("=" * 60)

    ws = WSCollector()
    orchestrator._ws_manager = ws
    orchestrator._current_session = None
    orchestrator._cancel_requested = False
    mock_state.start_fail_mode = False
    mock_state.chat_fail_mode = False
    mock_state.health_delay_seconds = 0.3

    _start_mock_server(chat_fail=False)

    try:
        switch_task = asyncio.create_task(
            orchestrator.switch(
                target_model="Cancel-Target",
                target_model_path="/mnt/pve_models/Cancel-Target",
                previous_model="Qwen3.6-35B-A3B-NVFP4",
                previous_model_path="/mnt/pve_models/Qwen3.6-35B-A3B-NVFP4",
            )
        )

        await asyncio.sleep(3)
        logger.info("Requesting cancel after 3s...")
        orchestrator.request_cancel()

        session = await switch_task

        logger.info("Result: phase=%s success=%s rollback=%s",
                    session.overall_phase.value, session.completed_successfully, session.rollback_reason)

        assert not session.completed_successfully
        assert session.overall_phase in (SwitchPhase.ROLLED_BACK, SwitchPhase.FAILED, SwitchPhase.IDLE)

        logger.info("TEST 5 PASSED")
        return True
    except Exception as e:
        logger.error("TEST 5 FAILED: %s", e, exc_info=True)
        return False
    finally:
        _kill_mock_server()
        orchestrator._current_session = None
        orchestrator._cancel_requested = False
        if orchestrator._global_lock.locked():
            orchestrator._global_lock.release()


async def test_status_api():
    logger.info("=" * 60)
    logger.info("TEST 6: Status tracking during/after switch")
    logger.info("=" * 60)

    ws = WSCollector()
    orchestrator._ws_manager = ws
    orchestrator._current_session = None
    orchestrator._cancel_requested = False
    mock_state.start_fail_mode = False
    mock_state.chat_fail_mode = False
    mock_state.health_delay_seconds = 0.3

    _start_mock_server(chat_fail=False)

    try:
        assert not orchestrator.is_switching
        assert orchestrator.current_session is None

        switch_task = asyncio.create_task(
            orchestrator.switch(
                target_model="Status-Model",
                target_model_path="/mnt/pve_models/Status-Model",
            )
        )

        await asyncio.sleep(1)
        assert orchestrator.is_switching
        assert orchestrator.current_session is not None
        logger.info("During switch: is_switching=%s session_id=%s",
                    orchestrator.is_switching, orchestrator.current_session.session_id)

        session = await switch_task
        assert not orchestrator.is_switching

        logger.info("TEST 6 PASSED")
        return True
    except Exception as e:
        logger.error("TEST 6 FAILED: %s", e, exc_info=True)
        return False
    finally:
        _kill_mock_server()
        orchestrator._current_session = None
        if orchestrator._global_lock.locked():
            orchestrator._global_lock.release()


async def run_all_tests():
    patch_vllm_manager_module()

    results = {}
    tests = [
        ("normal_switch", test_normal_switch),
        ("concurrent_switch", test_concurrent_switch),
        ("start_failure_rollback", test_start_failure_rollback),
        ("chat_smoke_failure_rollback", test_chat_smoke_failure_rollback),
        ("cancel_switch", test_cancel_switch),
        ("status_api", test_status_api),
    ]

    for name, test_func in tests:
        logger.info("\n")
        try:
            result = await test_func()
            results[name] = result
        except Exception as e:
            logger.error("Test %s crashed: %s", name, e)
            results[name] = False
        await asyncio.sleep(1)

    logger.info("\n" + "=" * 60)
    logger.info("FINAL RESULTS")
    logger.info("=" * 60)
    all_passed = True
    for name, result in results.items():
        status = "PASS" if result else "FAIL"
        logger.info("  %s: %s", name, status)
        if not result:
            all_passed = False

    logger.info("=" * 60)
    logger.info("ALL PASSED" if all_passed else "SOME FAILED")
    logger.info("=" * 60)

    return all_passed


if __name__ == "__main__":
    asyncio.run(run_all_tests())
