"""FastAPI application entrypoint."""

from __future__ import annotations

import logging

from fastapi import FastAPI

from apps.api.routes_chat import router as chat_router

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="BENJAMIN MVP", version="0.1.0")
app.include_router(chat_router)
