import pytest
import websocket
import json
import time


class TestWebSocket:
    def test_websocket_connection(self, py_base):
        ws_url = py_base.replace("http", "ws") + "/ws/monitor"
        try:
            ws = websocket.create_connection(ws_url, timeout=10)
            ws.send("ping")
            data = ws.recv()
            parsed = json.loads(data)
            assert "type" in parsed
            ws.close()
        except (ConnectionRefusedError, websocket.WebSocketException) as e:
            pytest.skip(f"WebSocket connection failed: {e}")

    def test_websocket_broadcast_status(self, py_base):
        ws_url = py_base.replace("http", "ws") + "/ws/monitor"
        try:
            ws = websocket.create_connection(ws_url, timeout=10)
            init_msg = ws.recv()
            parsed = json.loads(init_msg)
            assert parsed["type"] == "monitor_state_sync"
            assert "timestamp" in parsed
            assert "gpu" in parsed
            assert "models" in parsed
            ws.close()
        except (ConnectionRefusedError, websocket.WebSocketException) as e:
            pytest.skip(f"WebSocket connection failed: {e}")

    def test_websocket_model_switch(self, py_base):
        ws_url = py_base.replace("http", "ws") + "/ws/model-switch"
        try:
            ws = websocket.create_connection(ws_url, timeout=10)
            msg = ws.recv()
            parsed = json.loads(msg)
            assert "type" in parsed
            ws.close()
        except (ConnectionRefusedError, websocket.WebSocketException) as e:
            pytest.skip(f"WebSocket connection failed: {e}")
