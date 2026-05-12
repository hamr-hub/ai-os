from fastapi import FastAPI
from starlette.testclient import TestClient

from core.agent_system import AgentSystem
from middleware.auth import AdminAuthMiddleware


def test_admin_auth_rejects_missing_token(monkeypatch):
    monkeypatch.setenv("AI_OS_ADMIN_TOKEN", "secret-token")
    app = FastAPI()

    @app.get("/manage/protected")
    async def protected():
        return {"ok": True}

    app.add_middleware(AdminAuthMiddleware, config={})
    client = TestClient(app)

    resp = client.get("/manage/protected")
    assert resp.status_code == 401


def test_admin_auth_accepts_bearer_token(monkeypatch):
    monkeypatch.setenv("AI_OS_ADMIN_TOKEN", "secret-token")
    app = FastAPI()

    @app.get("/manage/protected")
    async def protected():
        return {"ok": True}

    app.add_middleware(AdminAuthMiddleware, config={})
    client = TestClient(app)

    resp = client.get("/manage/protected", headers={"Authorization": "Bearer secret-token"})
    assert resp.status_code == 200


def test_command_validation_rejects_shell_operators():
    system = AgentSystem({"feature_flags": {}})
    result = system.validate_command("ls -la; cat /etc/passwd")
    assert result["valid"] is False
    assert result["reason"] == "shell_operator_not_allowed"


def test_command_validation_blocks_docker_by_default():
    system = AgentSystem({"feature_flags": {}})
    result = system.validate_command(["docker", "ps"])
    assert result["valid"] is False
    assert result["reason"] == "command_blocked"


def test_command_validation_accepts_argv_form():
    system = AgentSystem({"feature_flags": {}})
    result = system.validate_command(["df", "-h", "/"])
    assert result["valid"] is True
    assert result["argv"] == ["df", "-h", "/"]
