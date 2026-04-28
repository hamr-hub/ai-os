import asyncio
import json
import signal
import socket
import subprocess
import time
import httpx
import logging
import uuid
import os
import sys
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

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
from core.cache_service import cache_service

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
    health_delay_seconds: int = 2
    pid: int = 99999


mock_state = MockVLLMState()


def mock_stop_vllm_service() -> bool:
    logger.info("[MOCK] stop_vllm_service called")
    mock_state.running = False
    return True


def mock_start_vllm_service() -> bool:
    logger.info("[MOCK] start_vllm_service called, fail_mode=%s", mock_state.start_fail_mode)
    if mock_state.start_fail_mode:
        return False
    mock_state.running = True
    return True


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


original_imports = {}


def patch_vllm_manager_module():
    import core.vllm_manager as vm
    original_imports['stop'] = vm.stop_vllm_service
    original_imports['start'] = vm.start_vllm_service
    original_imports['update_script'] = vm._update_vllm_script
    original_imports['discover_port'] = vm.discover_vllm_port
    original_imports['refresh_cache'] = vm.refresh_vllm_port_cache

    vm.stop_vllm_service = mock_stop_vllm_service
    vm.start_vllm_service = mock_start_vllm_service
    vm._update_vllm_script = mock__update_vllm_script
    vm.discover_vllm_port = mock_discover_vllm_port
    vm.refresh_vllm_port_cache = mock_refresh_vllm_port_cache

    logger.info("Patched core.vllm_manager with mock functions")


def restore_vllm_manager_module():
    import core.vllm_manager as vm
    vm.stop_vllm_service = original_imports['stop']
    vm.start_vllm_service = original_imports['start']
    vm._update_vllm_script = original_imports['update_script']
    vm.discover_vllm_port = original_imports['discover_port']
    vm.refresh_vllm_port_cache = original_imports['refresh_cache']
    logger.info("Restored core.vllm_manager original functions")


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


def patch_orchestrator_internal_methods():
    orchestrator._check_vllm_logs_for_errors = lambda: None
    orchestrator._find_vllm_pids = lambda: []
    logger.info("Patched orchestrator internal methods (journalctl/pgrep mocked out)")


class WSCollector:
    def __init__(self):
        self.messages: List[Dict] = []

    async def broadcast(self, message, channel=None):
        self.messages.append(message)
        logger.info("[WS] channel=%s phase=%s progress=%s log=%s level=%s",
                    channel,
                    message.get("overall_phase"),
                    message.get("overall_progress"),
                    message.get("log"),
                    message.get("level"))


async def test_normal_switch():
    logger.info("=" * 60)
    logger.info("TEST 1: Normal model switch (all phases succeed)")
    logger.info("=" * 60)

    ws_collector = WSCollector()
    orchestrator._ws_manager = ws_collector
    mock_state.running = True
    mock_state.start_fail_mode = False
    mock_state.chat_fail_mode = False

    mock_vllm_process = await _start_mock_vllm_server()

    await asyncio.sleep(1)

    try:
        session = await orchestrator.switch(
            target_model="Qwen3-235B",
            target_model_path="/mnt/pve_models/Qwen3-235B",
            previous_model="Qwen3.6-35B-A3B-NVFP4",
            previous_model_path="/mnt/pve_models/Qwen3.6-35B-A3B-NVFP4",
        )

        logger.info("Session result: phase=%s, success=%s, error=%s",
                    session.overall_phase.value, session.completed_successfully, session.error)

        for p in session.phases:
            logger.info("  Phase%d [%s]: status=%s progress=%s logs=%d error=%s",
                        p.phase, p.name, p.status.value, p.progress, len(p.logs), p.error)
            for log_entry in p.logs[-3:]:
                logger.info("    %s", log_entry)

        logger.info("WS messages collected: %d", len(ws_collector.messages))

        assert session.completed_successfully, f"Expected success, got: {session.error}"
        assert session.overall_phase == SwitchPhase.COMPLETED
        for p in session.phases:
            assert p.status == PhaseStatus.SUCCESS, f"Phase {p.phase} expected SUCCESS, got {p.status}"

        logger.info("TEST 1 PASSED")
        return True
    except Exception as e:
        logger.error("TEST 1 FAILED: %s", e)
        return False
    finally:
        _stop_mock_vllm(mock_vllm_process)
        orchestrator._current_session = None
        if orchestrator._global_lock.locked():
            orchestrator._global_lock.release()


async def test_concurrent_switch():
    logger.info("=" * 60)
    logger.info("TEST 2: Concurrent switch request (lock mutual exclusion)")
    logger.info("=" * 60)

    ws_collector = WSCollector()
    orchestrator._ws_manager = ws_collector
    mock_state.running = True
    mock_state.start_fail_mode = False
    mock_state.chat_fail_mode = False

    mock_vllm_process = await _start_mock_vllm_server()
    await asyncio.sleep(1)

    try:
        task1 = asyncio.create_task(
            orchestrator.switch(
                target_model="Model-A",
                target_model_path="/mnt/pve_models/Model-A",
                previous_model="Model-Old",
                previous_model_path="/mnt/pve_models/Model-Old",
            )
        )

        await asyncio.sleep(0.2)

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
        logger.info("First switch completed: phase=%s success=%s",
                    session1.overall_phase.value, session1.completed_successfully)

        assert session1.completed_successfully
        assert not orchestrator.is_switching

        logger.info("TEST 2 PASSED")
        return True
    except Exception as e:
        logger.error("TEST 2 FAILED: %s", e)
        return False
    finally:
        _stop_mock_vllm(mock_vllm_process)
        orchestrator._current_session = None
        if orchestrator._global_lock.locked():
            orchestrator._global_lock.release()


async def test_start_failure_rollback():
    logger.info("=" * 60)
    logger.info("TEST 3: Start failure triggers rollback")
    logger.info("=" * 60)

    ws_collector = WSCollector()
    orchestrator._ws_manager = ws_collector
    mock_state.running = True
    mock_state.start_fail_mode = True
    mock_state.chat_fail_mode = False

    mock_vllm_process = await _start_mock_vllm_server()
    await asyncio.sleep(1)

    try:
        session = await orchestrator.switch(
            target_model="Bad-Model",
            target_model_path="/mnt/pve_models/Bad-Model",
            previous_model="Qwen3.6-35B-A3B-NVFP4",
            previous_model_path="/mnt/pve_models/Qwen3.6-35B-A3B-NVFP4",
        )

        logger.info("Session result: phase=%s, success=%s, rollback_reason=%s",
                    session.overall_phase.value, session.completed_successfully, session.rollback_reason)

        for p in session.phases:
            logger.info("  Phase%d [%s]: status=%s error=%s",
                        p.phase, p.name, p.status.value, p.error)

        rollback_msgs = [m for m in ws_collector.messages if m.get("event_type") in ("rollback_started", "rollback_completed")]
        logger.info("Rollback WS messages: %d", len(rollback_msgs))
        for msg in rollback_msgs:
            logger.info("  %s: %s", msg.get("event_type"), msg.get("log"))

        assert not session.completed_successfully
        assert session.overall_phase in (SwitchPhase.ROLLED_BACK, SwitchPhase.FAILED)
        assert session.rollback_reason is not None

        logger.info("TEST 3 PASSED")
        return True
    except Exception as e:
        logger.error("TEST 3 FAILED: %s", e)
        return False
    finally:
        mock_state.start_fail_mode = False
        _stop_mock_vllm(mock_vllm_process)
        orchestrator._current_session = None
        if orchestrator._global_lock.locked():
            orchestrator._global_lock.release()


async def test_chat_smoke_failure_rollback():
    logger.info("=" * 60)
    logger.info("TEST 4: Chat smoke test failure triggers rollback")
    logger.info("=" * 60)

    ws_collector = WSCollector()
    orchestrator._ws_manager = ws_collector
    mock_state.running = True
    mock_state.start_fail_mode = False
    mock_state.chat_fail_mode = True

    mock_vllm_process = await _start_mock_vllm_server()
    await asyncio.sleep(1)

    try:
        session = await orchestrator.switch(
            target_model="ChatFail-Model",
            target_model_path="/mnt/pve_models/ChatFail-Model",
            previous_model="Qwen3.6-35B-A3B-NVFP4",
            previous_model_path="/mnt/pve_models/Qwen3.6-35B-A3B-NVFP4",
        )

        logger.info("Session result: phase=%s, success=%s, rollback_reason=%s",
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
        logger.error("TEST 4 FAILED: %s", e)
        return False
    finally:
        mock_state.chat_fail_mode = False
        _stop_mock_vllm(mock_vllm_process)
        orchestrator._current_session = None
        if orchestrator._global_lock.locked():
            orchestrator._global_lock.release()


async def test_cancel_switch():
    logger.info("=" * 60)
    logger.info("TEST 5: Cancel switch mid-process")
    logger.info("=" * 60)

    ws_collector = WSCollector()
    orchestrator._ws_manager = ws_collector
    mock_state.running = True
    mock_state.start_fail_mode = False
    mock_state.chat_fail_mode = False

    mock_vllm_process = await _start_mock_vllm_server()
    await asyncio.sleep(1)

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

        logger.info("Session result: phase=%s, success=%s, rollback_reason=%s",
                    session.overall_phase.value, session.completed_successfully, session.rollback_reason)

        assert not session.completed_successfully
        assert session.overall_phase in (SwitchPhase.ROLLED_BACK, SwitchPhase.FAILED, SwitchPhase.IDLE)

        logger.info("TEST 5 PASSED")
        return True
    except Exception as e:
        logger.error("TEST 5 FAILED: %s", e)
        return False
    finally:
        _stop_mock_vllm(mock_vllm_process)
        orchestrator._current_session = None
        orchestrator._cancel_requested = False
        if orchestrator._global_lock.locked():
            orchestrator._global_lock.release()


async def test_status_api():
    logger.info("=" * 60)
    logger.info("TEST 6: Status API during and after switch")
    logger.info("=" * 60)

    ws_collector = WSCollector()
    orchestrator._ws_manager = ws_collector
    mock_state.running = False
    mock_state.start_fail_mode = False
    mock_state.chat_fail_mode = False

    assert not orchestrator.is_switching
    assert orchestrator.current_session is None
    logger.info("Before switch: is_switching=%s, session=%s", orchestrator.is_switching, orchestrator.current_session)

    mock_vllm_process = await _start_mock_vllm_server()
    await asyncio.sleep(1)

    try:
        switch_task = asyncio.create_task(
            orchestrator.switch(
                target_model="Status-Model",
                target_model_path="/mnt/pve_models/Status-Model",
            )
        )

        await asyncio.sleep(1)
        is_switching_during = orchestrator.is_switching
        session_during = orchestrator.current_session
        logger.info("During switch: is_switching=%s, session_id=%s, phase=%s",
                    is_switching_during,
                    session_during.session_id if session_during else None,
                    session_during.overall_phase.value if session_during else None)

        session = await switch_task

        is_switching_after = orchestrator.is_switching
        logger.info("After switch: is_switching=%s", is_switching_after)

        assert is_switching_during
        assert not is_switching_after

        logger.info("TEST 6 PASSED")
        return True
    except Exception as e:
        logger.error("TEST 6 FAILED: %s", e)
        return False
    finally:
        _stop_mock_vllm(mock_vllm_process)
        orchestrator._current_session = None
        if orchestrator._global_lock.locked():
            orchestrator._global_lock.release()


mock_vllm_server_process = None


async def _start_mock_vllm_server():
    global mock_vllm_server_process

    script_path = os.path.join(os.path.dirname(__file__), "mock_vllm_server.py")
    env = os.environ.copy()
    env["MOCK_VLLM_PORT"] = str(MOCK_VLLM_PORT)
    env["MOCK_CHAT_FAIL"] = str(int(mock_state.chat_fail_mode))

    proc = subprocess.Popen(
        [sys.executable, script_path],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    mock_vllm_server_process = proc

    for _ in range(10):
        if orchestrator._is_port_alive(MOCK_VLLM_PORT):
            logger.info("Mock vLLM server started on port %d (PID=%d)", MOCK_VLLM_PORT, proc.pid)
            return proc
        await asyncio.sleep(0.5)

    logger.error("Mock vLLM server failed to start within 5s")
    stderr = proc.stderr.read().decode() if proc.stderr else ""
    logger.error("stderr: %s", stderr[:500])
    raise RuntimeError("Mock vLLM server failed to start")


def _stop_mock_vllm(proc):
    global mock_vllm_server_process
    if proc is None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    mock_vllm_server_process = None
    logger.info("Mock vLLM server stopped")


async def run_all_tests():
    patch_vllm_manager_module()
    patch_orchestrator_internal_methods()

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

        await asyncio.sleep(2)

    restore_vllm_manager_module()

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
    if all_passed:
        logger.info("ALL TESTS PASSED")
    else:
        logger.info("SOME TESTS FAILED")
    logger.info("=" * 60)

    return all_passed


if __name__ == "__main__":
    asyncio.run(run_all_tests())
