from fastapi import APIRouter, HTTPException, Request

from middleware.auth import (
    extract_request_token,
    is_auth_enabled,
    is_valid_token,
    resolve_auth_tokens,
)
from core.deps import config


auth_router = APIRouter(prefix="/manage/auth")


@auth_router.get("/verify")
async def verify_auth(request: Request):
    tokens = resolve_auth_tokens(config)
    enabled = is_auth_enabled(config, tokens)

    if not enabled:
        return {"authenticated": True, "auth_enabled": False, "mode": "disabled"}

    if is_valid_token(extract_request_token(request), tokens):
        return {"authenticated": True, "auth_enabled": True, "mode": "token"}

    raise HTTPException(status_code=401, detail="Invalid API key")
