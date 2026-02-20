from fastapi import FastAPI

from .routes_chat import router as chat_router
from .routes_tasks import router as tasks_router

app = FastAPI(title="Benjamin API")
app.include_router(chat_router, prefix="/chat", tags=["chat"])
app.include_router(tasks_router, prefix="/tasks", tags=["tasks"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
