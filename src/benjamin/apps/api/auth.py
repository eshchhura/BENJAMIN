from __future__ import annotations

import hmac
import os

from fastapi import Request

AUTH_MODE_ENV = "BENJAMIN_AUTH_MODE"
AUTH_TOKEN_ENV = "BENJAMIN_AUTH_TOKEN"
AUTH_HEADER = "X-BENJAMIN-TOKEN"
AUTH_COOKIE = "benjamin_token"


def get_auth_mode() -> str:
    return os.getenv(AUTH_MODE_ENV, "token").strip().casefold()


def is_auth_enabled() -> bool:
    return get_auth_mode() == "token"


def get_required_token() -> str:
    token = os.getenv(AUTH_TOKEN_ENV, "")
    if is_auth_enabled() and not token:
        raise RuntimeError("BENJAMIN_AUTH_TOKEN must be set when BENJAMIN_AUTH_MODE=token")
    return token


def extract_token(request: Request) -> str | None:
    header_token = request.headers.get(AUTH_HEADER)
    if header_token:
        return header_token
    cookie_token = request.cookies.get(AUTH_COOKIE)
    if cookie_token:
        return cookie_token
    return None


def is_request_authenticated(request: Request) -> bool:
    if not is_auth_enabled():
        return True
    required = get_required_token()
    provided = extract_token(request)
    if not provided:
        return False
    return hmac.compare_digest(provided, required)


def should_protect_chat_post() -> bool:
    return os.getenv("BENJAMIN_EXPOSE_PUBLIC", "off").strip().casefold() == "on"
