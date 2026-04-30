import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import json
from datetime import datetime

class TestWebSocket:
    @pytest.fixture
    def client(self):
        with patch('core.monitor.GPUMonitor.get_gpu_status') as mock_gpu_status:
            mock_gpu_status.return_value = {
                "status": "available",
                "gpu_count": 1,
                "total_memory": 24 * 1024 ** 3,
                "used_memory": 5 * 1024 ** 3,
                "available_memory": 19 * 1024 ** 3,
                "name": "NVIDIA RTX 4090",
                "utilization": 0,
                "temperature": 45,
                "power_draw": 100,
                "power_limit": 350,
                "power_percent": 28,
                "memory_utilization": 20,
                "fan_speed": 0,
                "clock_sm": 0,
                "clock_mem": 0,
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

    def test_websocket_connection(self, client):
        with client.websocket_connect("/ws/monitor") as websocket:
            websocket.send_text("ping")
            data = websocket.receive_json()
            assert "type" in data

    def test_websocket_broadcast_status(self, client):
        with client.websocket_connect("/ws/monitor") as websocket:
            init_msg = websocket.receive_json()
            assert init_msg["type"] == "monitor_state_sync"
            assert "timestamp" in init_msg
            assert "gpu" in init_msg
            assert "models" in init_msg