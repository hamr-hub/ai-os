import pytest
from unittest.mock import MagicMock, patch
from starlette.testclient import TestClient
from fastapi import FastAPI, Request, Response


class TestAdminWhitelistMiddleware:
    def _create_middleware(self, trusted_proxies=None):
        from middleware.admin_whitelist import AdminWhitelistMiddleware
        mw = AdminWhitelistMiddleware(trusted_proxies=trusted_proxies or [])
        return mw

    def _create_app_with_middleware(self, trusted_proxies=None):
        app = FastAPI()

        @app.post("/manage/test")
        async def manage_post():
            return {"status": "ok"}

        @app.get("/manage/test")
        async def manage_get():
            return {"status": "ok"}

        @app.put("/manage/test")
        async def manage_put():
            return {"status": "ok"}

        @app.delete("/manage/test")
        async def manage_delete():
            return {"status": "ok"}

        @app.head("/manage/test")
        async def manage_head():
            return Response(status_code=200)

        mw = self._create_middleware(trusted_proxies=trusted_proxies)
        app.add_middleware(AdminWhitelistMiddleware, trusted_proxies=trusted_proxies or [])

        return app

    def test_loopback_ip_post_allowed(self):
        app = self._create_app_with_middleware()
        client = TestClient(app)
        resp = client.post("/manage/test", headers={"X-Real-IP": "127.0.0.1"})
        assert resp.status_code == 200

    def test_private_network_10_post_allowed(self):
        app = self._create_app_with_middleware()
        client = TestClient(app)
        resp = client.post("/manage/test", headers={"X-Real-IP": "10.0.0.1"})
        assert resp.status_code == 200

    def test_private_network_172_post_allowed(self):
        app = self._create_app_with_middleware()
        client = TestClient(app)
        resp = client.post("/manage/test", headers={"X-Real-IP": "172.16.0.1"})
        assert resp.status_code == 200

    def test_private_network_192_post_allowed(self):
        app = self._create_app_with_middleware()
        client = TestClient(app)
        resp = client.post("/manage/test", headers={"X-Real-IP": "192.168.1.100"})
        assert resp.status_code == 200

    def test_external_ip_post_blocked(self):
        app = self._create_app_with_middleware()
        client = TestClient(app)
        resp = client.post("/manage/test", headers={"X-Real-IP": "8.8.8.8"})
        assert resp.status_code == 403

    def test_external_ip_put_blocked(self):
        app = self._create_app_with_middleware()
        client = TestClient(app)
        resp = client.put("/manage/test", headers={"X-Real-IP": "8.8.8.8"})
        assert resp.status_code == 403

    def test_external_ip_delete_blocked(self):
        app = self._create_app_with_middleware()
        client = TestClient(app)
        resp = client.delete("/manage/test", headers={"X-Real-IP": "8.8.8.8"})
        assert resp.status_code == 403

    def test_external_ip_get_allowed(self):
        app = self._create_app_with_middleware()
        client = TestClient(app)
        resp = client.get("/manage/test", headers={"X-Real-IP": "8.8.8.8"})
        assert resp.status_code == 200

    def test_external_ip_head_allowed(self):
        app = self._create_app_with_middleware()
        client = TestClient(app)
        resp = client.head("/manage/test", headers={"X-Real-IP": "8.8.8.8"})
        assert resp.status_code == 200

    def test_trusted_proxy_cidr_extends_whitelist(self):
        app = self._create_app_with_middleware(trusted_proxies=["203.0.113.0/24"])
        client = TestClient(app)
        resp = client.post("/manage/test", headers={"X-Real-IP": "203.0.113.50"})
        assert resp.status_code == 200

    def test_ipv6_loopback_post_allowed(self):
        app = self._create_app_with_middleware()
        client = TestClient(app)
        resp = client.post("/manage/test", headers={"X-Real-IP": "::1"})
        assert resp.status_code == 200
