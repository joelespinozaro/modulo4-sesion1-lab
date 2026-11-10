"""Diagnóstico antes de clase: verifica cada conexión del agente y dice qué arreglar.

Uso, desde la carpeta agente_mcp_adk:
    python scripts/verificar_conexiones.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
from src import config as c  # noqa: E402

OK, FALTA, ERROR = "✅", "➖", "❌"


def openai():
    if not c.OPENAI_API_KEY or c.OPENAI_API_KEY.startswith("sk-..."):
        return ERROR, "OPENAI_API_KEY vacío en .env"
    try:
        from openai import OpenAI
        OpenAI(api_key=c.OPENAI_API_KEY).models.retrieve(c.OPENAI_MODEL.replace("openai/", ""))
        return OK, f"modelo {c.OPENAI_MODEL} disponible"
    except Exception as e:
        return ERROR, f"{type(e).__name__}: {str(e)[:120]}"


def qdrant():
    if not c.QDRANT_URL:
        return FALTA, "RAG deshabilitado (QDRANT_URL vacío)"
    try:
        from qdrant_client import QdrantClient
        n = QdrantClient(url=c.QDRANT_URL, api_key=c.QDRANT_API_KEY).count(c.QDRANT_COLLECTION_NAME).count
        return (OK if n else ERROR), f"colección '{c.QDRANT_COLLECTION_NAME}' con {n} puntos" + ("" if n else ". Ejecuta setup/qdrant-db.ipynb")
    except Exception as e:
        pista = ". ¿El nombre de la colección coincide con el del setup?" if "not found" in str(e).lower() else ". Revisa QDRANT_URL y QDRANT_API_KEY"
        return ERROR, f"{type(e).__name__}: {str(e)[:120]}{pista}"


def postgres():
    if not c.DATABASE_URL:
        return FALTA, "historial deshabilitado (DATABASE_URL vacío)"
    try:
        from sqlalchemy import create_engine, text
        with create_engine(c.DATABASE_URL).connect() as con:
            n = con.execute(text("select count(*) from history")).scalar()
        return OK, f"tabla history con {n} filas"
    except Exception as e:
        return ERROR, f"{type(e).__name__}: {str(e)[:120]}"


def operaciones():
    if not c.DATABASE_URL:
        return FALTA, "agente de operaciones deshabilitado (DATABASE_URL vacío)"
    try:
        from sqlalchemy import create_engine, text
        with create_engine(c.DATABASE_URL).connect() as con:
            n = con.execute(text("select count(*) from productos")).scalar()
            con.execute(text("select 1 from acciones_agente limit 1"))
        return OK, f"{n} productos y tabla acciones_agente lista"
    except Exception as e:
        return ERROR, f"{type(e).__name__}: {str(e)[:100]}. Ejecuta setup/database.sql en Neon"


async def neon():
    if not c.NEON_API_KEY:
        return FALTA, "MCP Neon deshabilitado (NEON_API_KEY vacío)"
    from src.tools.mcp_setup import build_mcp_toolset
    ts = build_mcp_toolset()
    try:
        tools = await ts.get_tools()
        await ts.close()
        nombres = [t.name for t in tools]
        return (OK if nombres else ERROR), f"tools visibles para el agente: {nombres}" + ("" if c.NEON_READONLY else " (modo escritura con aprobación)")
    except Exception as e:
        return ERROR, f"{type(e).__name__}: {str(e)[:120]}. Revisa NEON_API_KEY y tu conexión a mcp.neon.tech"


if __name__ == "__main__":
    print("Verificando conexiones del agente...\n")
    for nombre, (estado, detalle) in [("OpenAI", openai()), ("Qdrant (RAG)", qdrant()),
                                      ("PostgreSQL (historial)", postgres()), ("Operaciones (escritura)", operaciones()),
                                      ("Neon MCP", asyncio.run(neon()))]:
        print(f"{estado}  {nombre:<24} {detalle}")
    print("\n➖ = opcional y deshabilitado. El agente funciona sin esa pieza.")
