import logging
import os
from datetime import datetime

from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient

logger = logging.getLogger(__name__)


@tool
def get_current_date() -> str:
    """Retorna la fecha y hora actual en formato ISO 8601."""
    return datetime.now().isoformat()


LOCAL_TOOLS = [get_current_date]


def create_retrieve_context_tool(qdrant_store):
    """Factory que crea la tool retrieve_context con acceso al qdrant_store."""
    @tool
    def retrieve_context(query: str) -> str:
        """Busca informacion en la base de conocimiento. Usala cuando el usuario pregunte sobre cursos, docentes, graduados, horarios, matriculas, programas, sedes o cualquier informacion relacionada a la academia."""
        retrieved_docs = qdrant_store.similarity_search(query, k=5)
        serialized = "\n\n".join(
            (f"Fuente: {doc.metadata}\nContenido: {doc.page_content}")
            for doc in retrieved_docs
        )
        return serialized if serialized else "No se encontro informacion relevante."
    return retrieve_context


async def load_neon_tools() -> tuple[list, object | None]:
    """Conecta al MCP de Neon y retorna (tools, client). Retorna ([], None) si NEON_API_KEY no está configurado."""
    neon_api_key = os.getenv("NEON_API_KEY")
    if not neon_api_key:
        logger.info("NEON_API_KEY no configurado — omitiendo integración Neon MCP")
        return [], None

    client = MultiServerMCPClient(
        {
            "neon": {
                "transport": "streamable_http",
                "url": "https://mcp.neon.tech/mcp",
                "headers": {
                    "Authorization": f"Bearer {neon_api_key}"
                },
            }
        }
    )
    tools = await client.get_tools()
    return tools, client


def get_all_tools(mcp_tools: list | None = None, rag_tool=None) -> list:
    """Retorna las tools locales combinadas con las MCP y la tool RAG opcionales."""
    all_tools = list(LOCAL_TOOLS)
    if rag_tool is not None:
        all_tools.append(rag_tool)
        logger.info("Tool RAG '%s' agregada al registro", rag_tool.name)
    if mcp_tools:
        all_tools.extend(mcp_tools)
        logger.info("Cargadas %d tool(s) de Neon MCP: %s", len(mcp_tools), [t.name for t in mcp_tools])
    return all_tools
