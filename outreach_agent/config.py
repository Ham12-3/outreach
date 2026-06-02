"""Central configuration: loads environment variables and exposes typed settings.

Everything that depends on the environment (the Gemini model name, the MongoDB
connection string, the database/collection names) is read here in one place so
the rest of the code never touches os.environ directly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Project root = the folder that contains this package's parent.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load .env from the project root if present. (No error if it's missing — on
# Cloud Run the variables are injected directly into the environment instead.)
load_dotenv(PROJECT_ROOT / ".env")

# Where the offline seed leads live.
SEED_LEADS_PATH = PROJECT_ROOT / "data" / "seed_leads.json"


def _get(name: str, default: str = "") -> str:
    """Read an env var, trimming whitespace, falling back to a default."""
    return os.environ.get(name, default).strip()


@dataclass(frozen=True)
class Settings:
    """Resolved configuration for the agent."""

    # Gemini 3 model id (e.g. gemini-3.1-pro-preview).
    model: str
    # MongoDB connection string used by the MCP server.
    mongo_connection_string: str
    # Logical database + collection the agent operates on.
    database: str
    collection: str
    # Whether we're authenticating to Gemini through Vertex AI.
    use_vertexai: bool

    def describe(self) -> str:
        """Human-readable summary for startup logging (no secrets)."""
        auth = "Vertex AI" if self.use_vertexai else "AI Studio API key"
        mongo = "set" if self.mongo_connection_string else "MISSING"
        return (
            f"model={self.model} | auth={auth} | "
            f"db={self.database}.{self.collection} | "
            f"MDB_MCP_CONNECTION_STRING={mongo}"
        )


def load_settings() -> Settings:
    """Build a Settings object from the current environment."""
    use_vertexai = _get("GOOGLE_GENAI_USE_VERTEXAI", "TRUE").upper() in (
        "TRUE",
        "1",
        "YES",
    )
    return Settings(
        model=_get("GEMINI_MODEL", "gemini-3.1-pro-preview"),
        mongo_connection_string=_get("MDB_MCP_CONNECTION_STRING"),
        database=_get("MONGODB_DATABASE", "outreach"),
        collection=_get("MONGODB_COLLECTION", "leads"),
        use_vertexai=use_vertexai,
    )


# A single shared instance the rest of the app imports.
settings = load_settings()
