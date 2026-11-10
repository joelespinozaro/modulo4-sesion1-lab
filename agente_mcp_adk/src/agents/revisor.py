"""Revisor de cifras: un agente que otro agente usa como tool (AgentTool).

No conversa con el usuario. Recibe un borrador y la evidencia (los resultados SQL) y dice si cada número
del borrador está respaldado. Es el patrón Reflexion en pequeño: un segundo par de ojos con un criterio claro.
"""
from google.adk.agents import LlmAgent

from src.agents.modelo import modelo
from src.callbacks.observabilidad import after_model

revisor_cifras = LlmAgent(
    name="revisor_cifras",
    model=modelo(),
    description="Verifica que cada cifra de un borrador esté respaldada por los resultados SQL que se le entregan.",
    instruction="""Eres un auditor de datos. Recibes un BORRADOR de respuesta y la EVIDENCIA (resultados de consultas SQL).

Revisa cada número del borrador (cantidades, montos, rankings, fechas):
- Si aparece en la evidencia o se calcula directamente de ella, está respaldado.
- Si no aparece o no coincide, es un error.

Responde SOLO con este JSON, sin texto adicional:
{"aprobado": true|false, "observaciones": ["..."]}
Si todo está respaldado, observaciones va vacía.""",
    after_model_callback=after_model,
)
