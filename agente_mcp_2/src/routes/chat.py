from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.controllers.chat_controller import handle_chat
from src.repositories import get_db

router = APIRouter()


class ChatRequest(BaseModel):
    question: str
    user: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    user: str
    answer: str
    session_id: str
    trace_id: str


@router.post("/api/chat", response_model=ChatResponse, tags=["chat"])
async def chat(request: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    result = await handle_chat(
        question=request.question,
        user=request.user,
        session_id=request.session_id,
        db=db,
    )
    return ChatResponse(**result)
