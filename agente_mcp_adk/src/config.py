from decouple import config

OPENAI_API_KEY: str = config("OPENAI_API_KEY")
OPENAI_MODEL: str = config("OPENAI_MODEL", default="gpt-4o-mini")

DATABASE_URL: str | None = config("DATABASE_URL", default=None)
HISTORY_LIMIT: int = config("HISTORY_LIMIT", default=10, cast=int)

QDRANT_URL: str | None = config("QDRANT_URL", default=None)
QDRANT_API_KEY: str | None = config("QDRANT_API_KEY", default=None)
QDRANT_COLLECTION_NAME: str = config("QDRANT_COLLECTION_NAME", default="documents")

NEON_API_KEY: str | None = config("NEON_API_KEY", default=None)
# Opcional: limita el MCP a un solo proyecto de Neon (lo ves en la URL de la consola de Neon)
NEON_PROJECT_ID: str | None = config("NEON_PROJECT_ID", default=None)
# true: el MCP solo permite lecturas. false: permite escribir, pero cada escritura pide aprobación humana
NEON_READONLY: bool = config("NEON_READONLY", default=True, cast=bool)
