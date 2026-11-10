"""Asesor académico: responde sobre la academia con RAG sobre Qdrant."""
from google.adk.agents import LlmAgent

from src.agents.modelo import modelo
from src.callbacks.observabilidad import after_model, after_tool, before_tool
from src.tools.local_tools import get_current_date


def crear_academico(rag_tool, after_agent=None) -> LlmAgent:
    tools = [get_current_date] + ([rag_tool] if rag_tool else [])
    return LlmAgent(
        name="asesor_academico",
        model=modelo(),
        description="Responde sobre programas, cursos, docentes, horarios, sedes, matrícula y reglamento de la academia.",
        instruction="""Eres el asesor académico de la academia. Respondes en español, claro y breve.

Usa siempre retrieve_context antes de responder y basa tu respuesta solo en lo que devuelve.
Si los documentos no lo dicen, responde que no tienes esa información y sugiere escribir a admisión.
Cita el programa o documento de donde sale el dato.

Si te preguntan por ventas, productos o stock, transfiere a analista_ventas.
Si te piden registrar un pedido, transfiere a operaciones.""",
        tools=tools,
        before_tool_callback=before_tool,
        after_tool_callback=after_tool,
        after_model_callback=after_model,
        after_agent_callback=after_agent,
    )
