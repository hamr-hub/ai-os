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
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "unknown-model",
                "messages": [{"role": "user", "content": "Hello"}]
            }
        )
        
        assert response.status_code == 404

    def test_chat_completions_too_many_requests(self, client):
        with patch('core.rate_limiter.RateLimiter.is_available') as mock_is_available:
            mock_is_available.return_value = False
            
            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": "gemma-4-31b",
                    "messages": [{"role": "user", "content": "Hello"}]
                }
            )
            
            assert response.status_code == 429

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

    def test_start_model(self, client):
        with patch('core.sys_ctl.SystemController.get_process_info') as mock_process_info:
            mock_process_info.return_value = None
            
            with patch('core.sys_ctl.SystemController.start_service') as mock_start:
                mock_start.return_value = True
                
                response = client.post("/manage/models/gemma-4-31b/start")
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "starting"

    def test_stop_model(self, client):
        with patch('core.scheduler.Scheduler.is_model_running') as mock_is_running:
            mock_is_running.return_value = True

            with patch('core.scheduler.Scheduler.stop_model', new_callable=AsyncMock) as mock_stop:
                mock_stop.return_value = True

                response = client.post("/manage/models/gemma-4-31b/stop")

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "stopped"

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

    def test_switch_model(self, client):
        with patch('core.scheduler.Scheduler.switch_model') as mock_switch:
            mock_switch.return_value = True
            
            response = client.post("/manage/models/gemma-4-31b/switch?test_enabled=false")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "switched"

    def test_switch_model_with_test(self, client):
        with patch('core.scheduler.Scheduler.switch_model') as mock_switch:
            mock_switch.return_value = True
        
            with patch('main.switch_vllm_model_with_test') as mock_test:
                mock_test.return_value = {
                    "success": True,
                    "model": "gemma-4-31b",
                    "status": "switched_and_tested",
                    "test_result": {"success": True, "message": "Model test passed"}
                }
                
                response = client.post("/manage/models/gemma-4-31b/switch")
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "switched_and_tested"
                assert "test_result" in data

    def test_preload_model(self, client):
        with patch('core.scheduler.Scheduler.start_model') as mock_start:
            mock_start.return_value = True
            
            response = client.post("/manage/preload/gemma-4-31b")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "preloaded"

    def test_get_config(self, client):
        response = client.get("/manage/config")
        assert response.status_code == 200

    def test_health_check_has_health_score(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "health_score" in data