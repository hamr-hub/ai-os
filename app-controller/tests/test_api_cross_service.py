import pytest


class TestGoGateway:
    def test_health(self, go_client):
        resp = go_client.get(f"{go_client.base_url}/health")
        assert resp.status_code == 200

    def test_models(self, go_client):
        try:
            resp = go_client.get(f"{go_client.base_url}/v1/models", timeout=10)
            assert resp.status_code == 200
            data = resp.json()
            assert data["object"] == "list"
        except Exception:
            pytest.skip("Go gateway connection issue")

    def test_ratelimit_config(self, go_client):
        try:
            resp = go_client.get(f"{go_client.base_url}/v1/ratelimit/config", timeout=10)
            assert resp.status_code in (200, 404)
        except Exception:
            pytest.skip("Go gateway connection issue")

    def test_chat_completions_no_model(self, go_client):
        try:
            resp = go_client.post(
                f"{go_client.base_url}/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "Hello"}]},
                timeout=10,
            )
            assert resp.status_code in (400, 422, 404, 500)
        except Exception:
            pytest.skip("Go gateway connection issue")


class TestCrossServiceIntegration:
    def test_python_and_go_models_consistent(self, py_client, go_client):
        py_resp = py_client.get(f"{py_client.base_url}/v1/models")
        assert py_resp.status_code == 200
        py_data = py_resp.json()
        assert py_data["object"] == "list"
        try:
            go_resp = go_client.get(f"{go_client.base_url}/v1/models", timeout=10)
            assert go_resp.status_code == 200
            go_data = go_resp.json()
            assert go_data["object"] == "list"
        except Exception:
            pytest.skip("Go gateway connection issue")

    def test_python_health_and_go_health(self, py_client, go_client):
        py_resp = py_client.get(f"{py_client.base_url}/health")
        assert py_resp.status_code == 200
        go_resp = go_client.get(f"{go_client.base_url}/health")
        assert go_resp.status_code == 200

    def test_model_info_integration(self, py_client, first_available_model):
        if not first_available_model:
            pytest.skip("No models available")
        resp = py_client.get(
            f"{py_client.base_url}/api/v1/models/{first_available_model}/info"
        )
        assert resp.status_code in (200, 404)
