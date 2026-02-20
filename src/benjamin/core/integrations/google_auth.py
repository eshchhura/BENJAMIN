from __future__ import annotations

from pathlib import Path


class GoogleDependencyError(RuntimeError):
    pass


class GoogleTokenError(RuntimeError):
    pass


def build_google_service(service_name: str, version: str, token_path: str):
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError as exc:  # pragma: no cover - handled in integration status/tests via disabled path
        raise GoogleDependencyError(
            "Google integration dependencies are missing; install with pip install -e .[google]."
        ) from exc

    token_file = Path(token_path).expanduser()
    if not token_file.exists():
        raise GoogleTokenError("Google token not found; run auth bootstrap externally.")

    creds = Credentials.from_authorized_user_file(str(token_file))
    return build(service_name, version, credentials=creds, cache_discovery=False)
