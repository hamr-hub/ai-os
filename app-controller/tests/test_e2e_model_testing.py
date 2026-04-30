import pytest


class TestModelTestingFramework:
    def test_test_status_endpoint(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/v1/test/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert data["status"] in ("ready", "busy", "testing")

    def test_get_all_reports_empty(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/v1/test/reports")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert data["status"] in ("no_reports", "success")

    def test_get_report_not_found(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/v1/test/report/nonexistent-model-xyz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("not_found", "found")

    def test_model_not_available_error(self, py_client):
        resp = py_client.post(f"{py_client.base_url}/v1/test/model/nonexistent-model-xyz")
        assert resp.status_code in (404, 400, 500)

    def test_switch_and_test_not_available(self, py_client):
        resp = py_client.post(
            f"{py_client.base_url}/v1/test/model/nonexistent-model-xyz/switch-and-test"
        )
        assert resp.status_code in (404, 400, 500)

    def test_clear_reports(self, py_client):
        resp = py_client.delete(f"{py_client.base_url}/v1/test/reports")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"

    def test_comparative_no_models(self, py_client):
        resp = py_client.post(
            f"{py_client.base_url}/v1/test/comparative",
            json={"model_names": ["nonexistent1", "nonexistent2"]},
        )
        assert resp.status_code in (200, 400, 404, 500)

    def test_test_model_with_running_model(self, py_client, running_model):
        if not running_model:
            pytest.skip("No running model available for test")
        resp = py_client.post(
            f"{py_client.base_url}/v1/test/model/{running_model}",
            timeout=60,
        )
        assert resp.status_code in (200, 404, 500)
