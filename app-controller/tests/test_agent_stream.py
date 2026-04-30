import pytest


class TestAgentAPI:
    def test_list_tools(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/agent/tools")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, (list, dict))
        if isinstance(data, list) and len(data) > 0:
            assert "name" in data[0]

    def test_get_tool_detail(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/agent/tools")
        if resp.status_code != 200:
            pytest.skip("Agent tools not available")
        data = resp.json()
        tools = data if isinstance(data, list) else data.get("tools", [])
        if not tools:
            pytest.skip("No tools available")
        tool_entry = tools[0]
        tool_name = tool_entry.get("name", tool_entry) if isinstance(tool_entry, dict) else tool_entry
        resp2 = py_client.get(
            f"{py_client.base_url}/manage/agent/tools/{tool_name}"
        )
        assert resp2.status_code in (200, 404)

    def test_agent_history(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/agent/history")
        assert resp.status_code == 200

    def test_agent_sessions_list(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/agent/sessions")
        assert resp.status_code == 200


class TestSSEAPI:
    def test_sse_categories(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/sse/categories")
        assert resp.status_code == 200

    def test_sse_connections(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/sse/connections")
        assert resp.status_code == 200

    def test_sse_stats(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/sse/stats")
        assert resp.status_code == 200


class TestCommandAPI:
    def test_command_validate(self, py_client):
        resp = py_client.post(
            f"{py_client.base_url}/manage/command/validate",
            json={"command": "ls -la"},
        )
        assert resp.status_code == 200

    def test_command_list(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/command/list")
        assert resp.status_code == 200

    def test_command_history(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/command/history")
        assert resp.status_code == 200

    def test_command_stats(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/command/stats")
        assert resp.status_code == 200

    def test_command_system_info(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/command/system-info")
        assert resp.status_code == 200


class TestIntegrationAPI:
    def test_integration_status(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/api/v1/status")
        assert resp.status_code == 200

    def test_prometheus_metrics(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/metrics")
        assert resp.status_code == 200

    def test_metrics_metadata(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/metrics/metadata")
        assert resp.status_code == 200

    def test_logs_test(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/logs/test")
        assert resp.status_code in (200, 500)
