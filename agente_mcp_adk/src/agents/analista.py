"""Analista de ventas: consulta la base de datos a través del servidor MCP de Neon.

Muestra dos ideas de la sesión:
- MCP: el agente no tiene código SQL de conexión, usa las tools que publica el servidor (filtradas a 4).
- Delegar a un agente como tool: antes de responder, llama al revisor_cifras (AgentTool).
"""
from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool

from src.agents.modelo import modelo
from src.agents.revisor import revisor_cifras
from src.callbacks.observabilidad import after_model, after_tool, before_tool


def crear_analista(mcp_toolset, after_agent=None) -> LlmAgent:
    tools = [AgentTool(agent=revisor_cifras)]
    if mcp_toolset is not None:
        tools.insert(0, mcp_toolset)
    return LlmAgent(
        name="analista_ventas",
        model=modelo(),
        description="Responde preguntas de datos sobre ventas, productos, stock, clientes y vendedores consultando la base de datos.",
        instruction="""Eres el analista de ventas de la tienda de tecnología de la academia. Respondes en español.

Base de datos (PostgreSQL vía MCP): clientes, vendedores, productos, ventas, detalle_ventas.
Cómo trabajas:
1. Si no conoces las columnas, usa get_database_tables y describe_table_schema.
2. Escribe SQL de solo lectura (SELECT) y ejecútalo con run_sql. Nunca inventes cifras.
3. Antes de responder con números, llama a revisor_cifras con tu BORRADOR y la EVIDENCIA (los resultados de run_sql).
   Si el revisor no aprueba, corrige con una nueva consulta. Máximo un reintento.
4. Responde en pocas líneas. Si hay ranking o lista, usa una tabla corta en markdown.

Si te piden registrar un pedido o cambiar stock, transfiere a operaciones.
Si te preguntan por cursos o la academia, transfiere a asesor_academico.
Si la base de datos no está disponible, dilo en una frase y no inventes.""",
        tools=tools,
        before_tool_callback=before_tool,
        after_tool_callback=after_tool,
        after_model_callback=after_model,
        after_agent_callback=after_agent,
    )
