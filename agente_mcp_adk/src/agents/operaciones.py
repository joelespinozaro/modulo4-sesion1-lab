"""Operaciones: el único agente que cambia datos, y siempre con una persona que aprueba."""
from google.adk.agents import LlmAgent
from src.agents.modelo import modelo
from src.callbacks.observabilidad import after_model, after_tool, before_tool
from src.tools.operaciones_tools import (
    UMBRAL_AJUSTE,
    ajustar_stock,
    buscar_producto,
    registrar_pedido,
)


def crear_operaciones(after_agent=None) -> LlmAgent:
    return LlmAgent(
        name="operaciones",
        model=modelo(),
        description="Registra pedidos de venta y ajusta el stock de productos. Toda escritura pasa por aprobación humana.",
        instruction=f"""Eres el agente de operaciones de la tienda. Respondes en español.

Tools:
- buscar_producto: encuentra el id, precio y stock de un producto por su nombre.
- registrar_pedido: registra una venta. Necesita DNI del cliente, DNI del vendedor, id del producto y cantidad.
- ajustar_stock: suma o resta unidades al stock con un motivo. Más de {UMBRAL_AJUSTE} unidades requiere aprobación.

Reglas:
1. Si falta un dato (DNI del cliente, vendedor o cantidad), pregúntalo. No lo inventes.
2. Usa buscar_producto para obtener el id antes de registrar.
3. registrar_pedido siempre pausa para que una persona apruebe. Avisa al usuario que quedó pendiente de aprobación.
4. Las validaciones (stock, existencia del cliente) las hace el código. Si devuelve un error, explícalo tal cual.

Si te hacen preguntas de análisis (rankings, totales), transfiere a analista_ventas.""",
        tools=[
            buscar_producto,
            registrar_pedido,  # siempre pide aprobación, mostrando el total calculado
            ajustar_stock,  # pide aprobación solo si el ajuste supera el umbral
        ],
        before_tool_callback=before_tool,
        after_tool_callback=after_tool,
        after_model_callback=after_model,
        after_agent_callback=after_agent,
    )
