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
    def __init__(self, app, trusted_proxies=None, allowed_ips=None, enabled=True, **kwargs):
        super().__init__(app, **kwargs)
        self.enabled = enabled
        self.allow_networks = list(DEFAULT_ALLOW_NETWORKS)
        self.trusted_proxy_networks = [
            ipaddress.ip_network("127.0.0.0/8"),
            ipaddress.ip_network("::1/128"),
        ]
        for source, target in (
            (allowed_ips or [], self.allow_networks),
            (trusted_proxies or [], self.trusted_proxy_networks),
        ):
            for cidr in source:
                try:
                    target.append(ipaddress.ip_network(cidr, strict=False))
                except ValueError:
                    pass

    def _parse_ip(self, ip_str: str):
        try:
            return ipaddress.ip_address(ip_str)
        except ValueError:
            host, _, port = ip_str.rpartition(":")
            if port and host:
                try:
                    return ipaddress.ip_address(host)
                except ValueError:
                    return None
        return None

    def _is_allowed_ip(self, ip_str: str) -> bool:
        ip = self._parse_ip(ip_str)
        if ip is None:
            return False

        for network in self.allow_networks:
            if ip in network:
                return True
        return False

    def _is_trusted_proxy(self, ip_str: str) -> bool:
        ip = self._parse_ip(ip_str)
        if ip is None:
            return False
        return any(ip in network for network in self.trusted_proxy_networks)

    def _get_client_ip(self, request: Request) -> str:
        remote_ip = request.client.host if request.client else "127.0.0.1"
        has_forwarded_headers = bool(
            request.headers.get("x-real-ip") or request.headers.get("x-forwarded-for")
        )

        if has_forwarded_headers and not self._is_trusted_proxy(remote_ip):
            return "untrusted-forwarded-for"

        real_ip = request.headers.get("x-real-ip")
        if real_ip and self._is_trusted_proxy(remote_ip):
            return real_ip
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for and self._is_trusted_proxy(remote_ip):
            return forwarded_for.split(",")[0].strip()
        return remote_ip

    async def dispatch(self, request: Request, call_next):
        if not self.enabled:
            return await call_next(request)

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
