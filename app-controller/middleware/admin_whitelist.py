import ipaddress
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


DEFAULT_ALLOW_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]

READ_ONLY_METHODS = {"GET", "HEAD"}


class AdminWhitelistMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, trusted_proxies=None, **kwargs):
        super().__init__(app, **kwargs)
        self.allow_networks = list(DEFAULT_ALLOW_NETWORKS)
        if trusted_proxies:
            for cidr in trusted_proxies:
                try:
                    self.allow_networks.append(ipaddress.ip_network(cidr, strict=False))
                except ValueError:
                    pass

    def _is_allowed_ip(self, ip_str: str) -> bool:
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            host, _, err = ip_str.rpartition(":")
            if not err:
                try:
                    ip = ipaddress.ip_address(host)
                except ValueError:
                    return False
            else:
                return False

        for network in self.allow_networks:
            if ip in network:
                return True
        return False

    def _get_client_ip(self, request: Request) -> str:
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "127.0.0.1"

    async def dispatch(self, request: Request, call_next):
        client_ip = self._get_client_ip(request)

        if self._is_allowed_ip(client_ip):
            return await call_next(request)

        if request.method in READ_ONLY_METHODS:
            return await call_next(request)

        return JSONResponse(
            status_code=403,
            content={
                "error": "admin write operations require internal network access",
                "client_ip": client_ip,
            },
        )
