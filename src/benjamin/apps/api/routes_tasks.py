from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class TaskRequest(BaseModel):
    task: str


@router.post("/")
def create_task(request: TaskRequest) -> dict[str, str]:
    return {"task": request.task, "status": "queued"}
