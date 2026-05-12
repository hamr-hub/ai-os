import pytest
from unittest.mock import MagicMock, patch
from starlette.testclient import TestClient
from fastapi import FastAPI, Request, Response
from middleware.admin_whitelist import AdminWhitelistMiddleware


class TestAdminWhitelistMiddleware:
    def _create_app_with_middleware(self, trusted_proxies=None, allowed_ips=None):
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

        app.add_middleware(
            AdminWhitelistMiddleware,
            trusted_proxies=trusted_proxies or [],
            allowed_ips=allowed_ips,
        )

        return app

    def test_loopback_ip_post_allowed(self):
        app = self._create_app_with_middleware()
        client = TestClient(app, client=("127.0.0.1", 12345))
        resp = client.post("/manage/test")
        assert resp.status_code == 200

    def test_private_network_10_post_allowed(self):
        app = self._create_app_with_middleware()
        client = TestClient(app, client=("10.0.0.1", 12345))
        resp = client.post("/manage/test")
        assert resp.status_code == 200

    def test_private_network_172_post_allowed(self):
        app = self._create_app_with_middleware()
        client = TestClient(app, client=("172.16.0.1", 12345))
        resp = client.post("/manage/test")
        assert resp.status_code == 200

    def test_private_network_192_post_allowed(self):
        app = self._create_app_with_middleware()
        client = TestClient(app, client=("192.168.1.100", 12345))
        resp = client.post("/manage/test")
        assert resp.status_code == 200

    def test_external_ip_post_blocked(self):
        app = self._create_app_with_middleware()
        client = TestClient(app, client=("8.8.8.8", 12345))
        resp = client.post("/manage/test")
        assert resp.status_code == 403

    def test_external_ip_put_blocked(self):
        app = self._create_app_with_middleware()
        client = TestClient(app, client=("8.8.8.8", 12345))
        resp = client.put("/manage/test")
        assert resp.status_code == 403

    def test_external_ip_delete_blocked(self):
        app = self._create_app_with_middleware()
        client = TestClient(app, client=("8.8.8.8", 12345))
        resp = client.delete("/manage/test")
        assert resp.status_code == 403

    def test_external_ip_get_allowed(self):
        app = self._create_app_with_middleware()
        client = TestClient(app, client=("8.8.8.8", 12345))
        resp = client.get("/manage/test")
        assert resp.status_code == 200

    def test_external_ip_head_allowed(self):
        app = self._create_app_with_middleware()
        client = TestClient(app, client=("8.8.8.8", 12345))
        resp = client.head("/manage/test")
        assert resp.status_code == 200

    def test_allowed_forwarded_client_from_trusted_proxy(self):
        app = self._create_app_with_middleware(
            trusted_proxies=["127.0.0.0/8"],
            allowed_ips=["203.0.113.0/24"],
        )
        client = TestClient(app, client=("127.0.0.1", 12345))
        resp = client.post("/manage/test", headers={"X-Real-IP": "203.0.113.50"})
        assert resp.status_code == 200

    def test_ipv6_loopback_post_allowed(self):
        app = self._create_app_with_middleware()
        client = TestClient(app, client=("::1", 12345))
        resp = client.post("/manage/test")
        assert resp.status_code == 200

    def test_untrusted_forwarded_header_is_blocked_for_write(self):
        app = self._create_app_with_middleware()
        client = TestClient(app, client=("8.8.8.8", 12345))
        resp = client.post("/manage/test", headers={"X-Real-IP": "127.0.0.1"})
        assert resp.status_code == 403
