"""
Agente ADK de la academia: un equipo de agentes que se ve trabajar en adk web.

    usuario ──► Pan (coordinador)
                 ├─ transfer_to_agent ─► asesor_academico   RAG en Qdrant
                 ├─ transfer_to_agent ─► analista_ventas    MCP de Neon (solo lectura)
                 │                         └─ AgentTool ─► revisor_cifras
                 └─ transfer_to_agent ─► operaciones        escribe en la BD con aprobación humana

Ejecutar la interfaz desde la raíz del repositorio:
    adk web
y elegir "agente_mcp_adk" en el selector de la izquierda.

Obligatorio: OPENAI_API_KEY. Lo demás es opcional (ver .env.example): si falta una pieza,
ese especialista trabaja sin ella o no se crea, y el resto del equipo sigue funcionando.
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root))
load_dotenv(_project_root / ".env")

from google.adk.agents import LlmAgent  # noqa: E402

from src.agents.academico import crear_academico  # noqa: E402
from src.agents.analista import crear_analista  # noqa: E402
from src.agents.modelo import MODEL_ID, modelo  # noqa: E402
from src.agents.operaciones import crear_operaciones  # noqa: E402
from src.callbacks.history_callback import build_history_callback  # noqa: E402
from src.callbacks.observabilidad import after_model, after_tool, before_tool  # noqa: E402
from src.config import DATABASE_URL  # noqa: E402
from src.tools.local_tools import get_current_date  # noqa: E402
from src.tools.mcp_setup import build_mcp_toolset  # noqa: E402
from src.tools.rag_tool import build_rag_tool  # noqa: E402
from src.utils.logger import get_logger  # noqa: E402

logger = get_logger(__name__)

# Historial: el mismo callback en todos los agentes que hablan con el usuario.
# Guarda una sola fila por turno, la del agente que dio la respuesta final.
_historial = build_history_callback()

especialistas = [
    crear_academico(build_rag_tool(), _historial),
    crear_analista(build_mcp_toolset(), _historial),
]
if DATABASE_URL:
    especialistas.append(crear_operaciones(_historial))
else:
    logger.info("DATABASE_URL vacío: el agente de operaciones no se crea")

_nombres = ", ".join(a.name for a in especialistas)

root_agent = LlmAgent(
    name="Pan",
    model=modelo(),
    description="Coordinador del asistente de la academia y su tienda de tecnología.",
    instruction=f"""Eres Pan, el coordinador del asistente de la academia. Respondes en español.

No respondes preguntas de fondo: decides qué especialista las atiende y le transfieres la conversación.
Especialistas disponibles: {_nombres}.
- asesor_academico: programas, cursos, docentes, horarios, sedes, matrícula, reglamento.
- analista_ventas: preguntas de datos sobre ventas, productos, stock, clientes y vendedores.
- operaciones: registrar un pedido o ajustar stock (si no está en la lista, di que esa función no está habilitada).

Solo respondes tú mismo saludos, la fecha (get_current_date) o qué puedes hacer.
Si la pregunta es ambigua, haz una pregunta corta para aclararla antes de transferir.""",
    tools=[get_current_date],
    sub_agents=especialistas,
    before_tool_callback=before_tool,
    after_tool_callback=after_tool,
    after_model_callback=after_model,
    after_agent_callback=_historial,
)

logger.info("Equipo de agentes inicializado", extra={"model": MODEL_ID, "especialistas": _nombres, "historial": _historial is not None})
