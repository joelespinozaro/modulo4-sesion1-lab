import uuid
from typing import Callable, Optional

from src.config import DATABASE_URL
from src.repositories.database import get_session_factory
from src.repositories.history_repository import HistoryRepository
from src.repositories.models.history import History
from src.utils.logger import get_logger

logger = get_logger(__name__)


def build_history_callback() -> Optional[Callable]:
    """
    Crea el callback after_agent que persiste cada turno en PostgreSQL.
    Retorna None si DATABASE_URL no está configurado.
    """
    if not DATABASE_URL:
        logger.info("DATABASE_URL no configurado — historial no se persistirá")
        return None

    session_factory = get_session_factory()
    if session_factory is None:
        logger.warning("No se pudo inicializar la BD — historial no se persistirá")
        return None

    guardados: set[str] = set()  # invocaciones ya guardadas: una fila por turno aunque respondan varios agentes

    def after_agent_callback(callback_context) -> None:
        """Guarda el par pregunta/respuesta del turno actual en la BD."""
        try:
            invocation_id = getattr(callback_context, "invocation_id", None)
            if invocation_id in guardados:
                return None
            # Extraer pregunta del usuario
            user_content = callback_context.user_content
            if not user_content or not user_content.parts:
                return None

            question = "".join(
                part.text
                for part in user_content.parts
                if hasattr(part, "text") and part.text
            )
            if not question.strip():
                return None

            # Extraer respuesta del agente desde los eventos de la sesión
            session = callback_context.session
            answer = _extract_agent_answer(session.events, invocation_id)
            if not answer:
                return None  # este agente transfirió: guardará el que responda
            input_tokens, output_tokens = _sum_tokens(session.events, invocation_id)

            # Persistir en PostgreSQL
            db = session_factory()
            try:
                repo = HistoryRepository(db)
                repo.save(
                    History(
                        trace_id=str(uuid.uuid4()),
                        session_id=session.id,
                        question=question,
                        answer=answer or "(sin respuesta)",
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                    )
                )
                guardados.add(invocation_id)
                if len(guardados) > 1000:
                    guardados.clear()
                logger.info("Historial guardado", extra={"session_id": session.id})
            finally:
                db.close()

        except Exception as exc:
            logger.warning("Error al guardar historial: %s", exc)

        return None

    return after_agent_callback


def _extract_agent_answer(events: list, invocation_id: Optional[str]) -> str:
    """Busca el último texto que algún agente le dio al usuario en este turno."""
    for event in reversed(events):
        # Filtrar por invocación actual si está disponible
        if invocation_id and getattr(event, "invocation_id", None) != invocation_id:
            continue

        if event.author == "user" or getattr(event, "partial", False):
            continue

        if not event.content or not event.content.parts:
            continue

        for part in event.content.parts:
            if hasattr(part, "text") and part.text:
                return part.text

    return ""


def _sum_tokens(events: list, invocation_id: Optional[str]) -> tuple[int, int]:
    """Suma los tokens de todas las llamadas al modelo del turno actual."""
    entrada = salida = 0
    for event in events:
        if invocation_id and getattr(event, "invocation_id", None) != invocation_id:
            continue
        u = getattr(event, "usage_metadata", None)
        if u:
            entrada += u.prompt_token_count or 0
            salida += u.candidates_token_count or 0
    return entrada, salida
