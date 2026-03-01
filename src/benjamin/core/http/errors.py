from __future__ import annotations


class BenjaminHTTPError(RuntimeError):
    """Base error for shared HTTP client operations."""


class BenjaminHTTPStatusError(BenjaminHTTPError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class BenjaminHTTPNetworkError(BenjaminHTTPError):
    """Raised when request retries are exhausted for transport errors."""
