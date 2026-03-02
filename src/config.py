import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Always safe to compute
MCP_SERVER_PATH: Path = Path(__file__).parent.parent / "mural-mcp" / "dist" / "index.js"


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise EnvironmentError(f"Required env var {name!r} is not set. See .env.example.")
    return value


def model_provider() -> str:
    """Returns 'gemini' or 'anthropic'. Defaults to 'gemini'."""
    return os.getenv("MODEL_PROVIDER", "gemini").lower()


def gemini_api_key() -> str:
    return _require("GEMINI_API_KEY")


def anthropic_api_key() -> str:
    return _require("ANTHROPIC_API_KEY")


def mural_token() -> str:
    return _require("MURAL_TOKEN")


def mural_id() -> str:
    return _require("MURAL_ID")
