"""Un solo lugar para elegir el modelo de todos los agentes."""
import os

from google.adk.models.lite_llm import LiteLlm

from src.config import OPENAI_API_KEY, OPENAI_MODEL

os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY  # LiteLLM lo lee del entorno
MODEL_ID = OPENAI_MODEL if OPENAI_MODEL.startswith("openai/") else f"openai/{OPENAI_MODEL}"


def modelo() -> LiteLlm:
    return LiteLlm(model=MODEL_ID)
