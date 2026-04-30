import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import json

@pytest.fixture
def client():
    with patch('core.monitor.GPUMonitor.get_gpu_status') as mock_gpu_status:
        mock_gpu_status.return_value = {
            "status": "available",
            "gpu_count": 1,
            "total_memory": 24 * 1024 ** 3,
            "used_memory": 5 * 1024 ** 3,
            "available_memory": 19 * 1024 ** 3,
            "primary": {
                "total_memory": 24 * 1024 ** 3,
                "used_memory": 5 * 1024 ** 3,
                "available_memory": 19 * 1024 ** 3
            },
            "all_gpus": []
        }
        
        with patch('core.sys_ctl.SystemController.is_service_running') as mock_is_running:
            mock_is_running.return_value = True
            
            with patch('middleware.admin_whitelist.AdminWhitelistMiddleware._is_allowed_ip', return_value=True):  # Bypass whitelist in tests
                from main import app
                with TestClient(app) as client:
                    yield client

class TestIntegration:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert "status" in response.json()

    def test_list_models(self, client):
        response = client.get("/v1/models")
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "list"
        assert isinstance(data["data"], list)

    def test_chat_completions_model_not_found(self, client):
        with patch('core.scheduler.Scheduler.is_model_running') as mock_running:
            mock_running.return_value = False
            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": "unknown-model",
                    "messages": [{"role": "user", "content": "Hello"}]
                }
            )
            assert response.status_code in (404, 500)

    def test_chat_completions_too_many_requests(self, client):
        with patch('core.scheduler.Scheduler.acquire_request') as mock_acquire:
            mock_acquire.return_value = False
            
            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": "gemma-4-31b",
                    "messages": [{"role": "user", "content": "Hello"}]
                }
            )
            assert response.status_code in (429, 500)

    def test_get_gpu_status(self, client):
        response = client.get("/manage/gpu")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "available"

    def test_get_model_status(self, client):
        response = client.get("/manage/models")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_start_model_deprecated(self, client):
        response = client.post("/manage/models/gemma-4-31b/start")
        assert response.status_code == 410
        data = response.json()
        error_data = data.get("error", data)
        assert "replacement" in error_data

    def test_stop_model_deprecated(self, client):
        response = client.post("/manage/models/gemma-4-31b/stop")
        assert response.status_code == 410
        data = response.json()
        error_data = data.get("error", data)
        assert "replacement" in error_data

    def test_switch_model_deprecated(self, client):
        response = client.post("/manage/models/gemma-4-31b/switch?test_enabled=false")
        assert response.status_code == 410
        data = response.json()
        error_data = data.get("error", data)
        assert "replacement" in error_data

    def test_switch_model_atomic(self, client):
        with patch('core.deps.model_switch_orchestrator') as mock_orch:
            mock_orch.is_switching = False
            mock_orch.clear_completed_session = MagicMock()
            mock_orch.switch = AsyncMock(return_value=Mock(session_id="test", target_model="gemma-4-31b", status="switched"))
            with patch('core.scheduler.Scheduler.is_model_available') as mock_avail:
                mock_avail.return_value = True
                with patch('core.vllm_manager.get_current_model_info', return_value={'running': True, 'name': 'other'}):
                    with patch('os.path.exists', return_value=True):
                        response = client.post(
                            "/manage/switch/atomic",
                            json={"action": "switch", "model_name": "gemma-4-31b-abliterated"}
                        )
                        assert response.status_code == 200

    def test_switch_model_with_test(self, client):
        with patch('core.deps.model_switch_orchestrator') as mock_orch:
            mock_orch.is_switching = False
            mock_orch.clear_completed_session = MagicMock()
            mock_orch.switch = AsyncMock(return_value=Mock(session_id="test", target_model="gemma-4-31b", status="switched_and_tested"))
            with patch('core.scheduler.Scheduler.is_model_available') as mock_avail:
                mock_avail.return_value = True
                with patch('core.vllm_manager.get_current_model_info', return_value={'running': True, 'name': 'other'}):
                    with patch('os.path.exists', return_value=True):
                        response = client.post(
                            "/manage/switch/atomic",
                            json={"action": "switch", "model_name": "gemma-4-31b-abliterated", "test_enabled": True}
                        )
                        assert response.status_code == 200

    def test_queue_status(self, client):
        response = client.get("/manage/queue")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_preload_status(self, client):
        response = client.get("/manage/preload")
        assert response.status_code == 200
        data = response.json()
        assert "preloaded_models" in data
        assert "all_models" in data

    def test_preload_model(self, client):
        with patch('core.deps.model_switch_orchestrator') as mock_orch:
            mock_orch.is_switching = False
            mock_orch.clear_completed_session = MagicMock()
            mock_orch.start = AsyncMock(return_value=Mock(session_id="test", target_model="gemma-4-31b", status="started"))
            with patch('core.scheduler.Scheduler.is_model_available') as mock_avail:
                mock_avail.return_value = True
                with patch('core.vllm_manager.get_current_model_info', return_value=None):
                    with patch('os.path.exists', return_value=True):
                        response = client.post(
                            "/manage/switch/atomic",
                            json={"action": "start", "model_name": "gemma-4-31b-abliterated"}
                        )
                        assert response.status_code == 200

    def test_get_config(self, client):
        response = client.get("/manage/config")
        assert response.status_code == 200

    def test_health_check_has_health_score(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "health_score" in data
