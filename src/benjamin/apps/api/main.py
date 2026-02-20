from fastapi import FastAPI
import uvicorn

from .deps import get_scheduler_service
from .routes_approvals import router as approvals_router
from .routes_chat import router as chat_router
from .routes_jobs import router as jobs_router
from .routes_integrations import router as integrations_router
from .routes_memory import router as memory_router
from .routes_tasks import router as tasks_router

app = FastAPI(title="Benjamin API")
app.include_router(chat_router, prefix="/chat", tags=["chat"])
app.include_router(tasks_router, prefix="/tasks", tags=["tasks"])
app.include_router(memory_router, prefix="/memory", tags=["memory"])
app.include_router(jobs_router, prefix="/jobs", tags=["jobs"])
app.include_router(integrations_router, prefix="/integrations", tags=["integrations"])
app.include_router(approvals_router, prefix="/approvals", tags=["approvals"])


@app.on_event("startup")
def startup() -> None:
    get_scheduler_service().start()


@app.on_event("shutdown")
def shutdown() -> None:
    get_scheduler_service().shutdown()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def run() -> None:
    uvicorn.run("benjamin.apps.api.main:app", reload=True, host="127.0.0.1", port=8000)
