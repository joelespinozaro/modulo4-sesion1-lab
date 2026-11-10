"""Callbacks de observabilidad: imprimen en la terminal cada paso interno del agente.

Complementan lo que ves en adk web (pestañas Events y Trace) con una línea por paso:
qué tool llamó, con qué argumentos, cuánto tardó, cuántos tokens gastó el modelo.
También aplican un guardrail: bloquean SQL destructivo aunque el MCP esté en modo escritura.
"""
import json
import time

from src.utils.logger import get_logger

logger = get_logger("traza")
_inicio = {}
_PELIGROSO = ("drop ", "truncate ", "alter ", "delete from ", "grant ", "revoke ")


def before_tool(tool, args, tool_context):
    """Se ejecuta antes de cada tool. Si devuelve un dict, la tool NO se ejecuta y el modelo recibe ese dict."""
    _inicio[tool_context.function_call_id] = time.time()
    logger.info("tool_inicio", extra={"agente": tool_context.agent_name, "tool": tool.name, "argumentos": json.dumps(args, ensure_ascii=False)[:300]})
    sql = str(args.get("sql", "")).lower()
    if any(p in sql for p in _PELIGROSO):
        logger.warning("guardrail_sql_bloqueado", extra={"sql": sql[:200]})
        return {"error": "Sentencia bloqueada por política: el asistente no puede borrar ni modificar la estructura de la base de datos."}
    return None


def after_tool(tool, args, tool_context, tool_response):
    ms = round((time.time() - _inicio.pop(tool_context.function_call_id, time.time())) * 1000)
    logger.info("tool_fin", extra={"tool": tool.name, "ms": ms, "resultado": str(tool_response)[:300]})
    return None


def after_model(callback_context, llm_response):
    u = llm_response.usage_metadata
    partes = llm_response.content.parts if llm_response.content and llm_response.content.parts else []
    pide = [p.function_call.name for p in partes if p.function_call]
    logger.info("modelo", extra={
        "agente": callback_context.agent_name,
        "decision": ("llamar: " + ", ".join(pide)) if pide else "responder",
        "tokens_entrada": u.prompt_token_count if u else None,
        "tokens_salida": u.candidates_token_count if u else None,
    })
    return None
