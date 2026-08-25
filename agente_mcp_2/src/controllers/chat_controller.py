from typing import Optional

from sqlalchemy.orm import Session

from src.services.agent_service import AgentService


async def handle_chat(
    question: str,
    user: str,
    session_id: Optional[str],
    db: Session,
) -> dict:
    service = AgentService(db)
    return await service.chat(question=question, user=user, session_id=session_id)
