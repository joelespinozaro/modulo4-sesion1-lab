"""Conexión al servidor MCP de Neon (base de datos PostgreSQL en la nube).

MCP (Model Context Protocol) es un estándar para que un agente use tools que viven en otro servidor.
Aquí el agente no tiene código SQL propio: le pide al servidor MCP de Neon que ejecute las consultas.

Buenas prácticas aplicadas:
- Mínimo privilegio: solo exponemos al modelo 4 tools de lectura, no las ~30 que ofrece Neon
  (entre ellas delete_project o create_branch).
- Modo solo lectura por defecto (?readonly=true).
- Si se habilita la escritura, cada sentencia que no sea de lectura pide aprobación humana (human-in-the-loop).
"""
from typing import Optional

from src.config import NEON_API_KEY, NEON_PROJECT_ID, NEON_READONLY
from src.utils.logger import get_logger

logger = get_logger(__name__)

NEON_MCP_URL = "https://mcp.neon.tech/mcp"

# Tools del MCP de Neon que el agente puede ver. Todo lo demás queda oculto.
TOOLS_PERMITIDAS = ["list_projects", "get_database_tables", "describe_table_schema", "run_sql"]

_LECTURA = ("select", "with", "show", "explain")


def requiere_aprobacion(**args) -> bool:
    """Decide si una llamada MCP necesita aprobación humana: cualquier SQL que no sea de lectura."""
    sql = str(args.get("sql", "")).strip().lower()
    return bool(sql) and not sql.startswith(_LECTURA)


def build_mcp_toolset() -> Optional[object]:
    """Crea el McpToolset para Neon. Retorna None si NEON_API_KEY no está configurado."""
    if not NEON_API_KEY:
        logger.info("NEON_API_KEY no configurado: MCP Neon deshabilitado")
        return None

    try:
        from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
        from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

        params = []
        if NEON_READONLY:
            params.append("readonly=true")
        if NEON_PROJECT_ID:
            params.append(f"projectId={NEON_PROJECT_ID}")
        url = NEON_MCP_URL + ("?" + "&".join(params) if params else "")

        toolset = McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=url,
                headers={"Authorization": f"Bearer {NEON_API_KEY}"},
                timeout=30,
            ),
            tool_filter=TOOLS_PERMITIDAS,
            # En modo escritura, ADK pausa y pide confirmación antes de ejecutar un INSERT, UPDATE o DELETE
            require_confirmation=False if NEON_READONLY else requiere_aprobacion,
        )
        logger.info("McpToolset Neon configurado", extra={"url": url, "tools": TOOLS_PERMITIDAS})
        return toolset

    except Exception as exc:
        logger.warning("Error configurando Neon MCP: %s. MCP deshabilitado", exc)
        return None
