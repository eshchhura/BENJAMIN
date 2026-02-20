from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .deps import get_orchestrator
from benjamin.core.orchestration.orchestrator import Orchestrator

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


@router.post("/")
def chat(request: ChatRequest, orchestrator: Orchestrator = Depends(get_orchestrator)) -> dict[str, str]:
    response = orchestrator.run(request.message)
    return {"response": response.final_response}
