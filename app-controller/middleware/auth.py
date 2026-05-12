import hmac
import os
from typing import Any, Iterable, Sequence

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


AUTHENTICATED_STATE_KEY = "authenticated"
AUTH_ENABLED_STATE_KEY = "auth_enabled"


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _as_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, Iterable):
        return [str(item) for item in value if str(item)]
    return []


def resolve_auth_tokens(config: dict[str, Any] | None = None) -> list[str]:
    """Resolve accepted admin tokens from environment and config."""
    config = config or {}
    app_cfg = config.get("app_controller", {}) if isinstance(config, dict) else {}
    auth_cfg = app_cfg.get("auth", {}) if isinstance(app_cfg, dict) else {}

    tokens: list[str] = []
    for env_name in ("AI_OS_ADMIN_TOKEN", "ADMIN_API_KEY", "AI_OS_API_KEY"):
        tokens.extend(_split_csv(os.getenv(env_name)))

    tokens.extend(_as_list(auth_cfg.get("api_key")))
    tokens.extend(_as_list(auth_cfg.get("api_keys")))

    unique_tokens: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        normalized = token.strip()
        if normalized and normalized not in seen:
            unique_tokens.append(normalized)
            seen.add(normalized)
    return unique_tokens


def is_auth_enabled(config: dict[str, Any] | None = None, tokens: Sequence[str] | None = None) -> bool:
    config = config or {}
    app_cfg = config.get("app_controller", {}) if isinstance(config, dict) else {}
    auth_cfg = app_cfg.get("auth", {}) if isinstance(app_cfg, dict) else {}

    env_enabled = os.getenv("AI_OS_AUTH_ENABLED")
    if env_enabled is not None:
        return env_enabled.lower() in {"1", "true", "yes", "on"}

    configured_enabled = auth_cfg.get("enabled")
    if configured_enabled is not None:
        return bool(configured_enabled)

    return bool(tokens if tokens is not None else resolve_auth_tokens(config))


def extract_request_token(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()

    api_key = request.headers.get("x-api-key") or request.query_params.get("api_key")
    return api_key.strip() if api_key else ""


def is_valid_token(token: str, allowed_tokens: Sequence[str]) -> bool:
    if not token:
        return False
    return any(hmac.compare_digest(token, allowed) for allowed in allowed_tokens)


def request_is_authenticated(request: Request) -> bool:
    return bool(getattr(request.state, AUTHENTICATED_STATE_KEY, False))


class AdminAuthMiddleware(BaseHTTPMiddleware):
    """Optional API-key/Bearer auth for admin surfaces.

    Auth is activated when AI_OS_AUTH_ENABLED=true or when at least one token is
    configured. If disabled, routes still get request.state.authenticated=False
    so high-risk endpoints can require explicit auth independently.
    """

    def __init__(
        self,
        app,
        config: dict[str, Any] | None = None,
        protected_prefixes: Sequence[str] | None = None,
        exempt_paths: Sequence[str] | None = None,
        **kwargs,
    ):
        super().__init__(app, **kwargs)
        self._tokens = resolve_auth_tokens(config)
        self._enabled = is_auth_enabled(config, self._tokens)
        self._protected_prefixes = tuple(protected_prefixes or ("/manage", "/ws"))
        self._exempt_paths = set(exempt_paths or ("/health", "/health/detailed", "/health/history", "/metrics"))

    async def dispatch(self, request: Request, call_next):
        setattr(request.state, AUTH_ENABLED_STATE_KEY, self._enabled)

        token = extract_request_token(request)
        authenticated = is_valid_token(token, self._tokens)
        setattr(request.state, AUTHENTICATED_STATE_KEY, authenticated)

        path = request.url.path
        protected = path not in self._exempt_paths and any(
            path == prefix or path.startswith(f"{prefix}/") for prefix in self._protected_prefixes
        )

        if self._enabled and protected and not authenticated:
            return JSONResponse(
                status_code=401,
                content={"error": "admin authentication required"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await call_next(request)
