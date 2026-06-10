"""Application configuration.

All settings are read from environment variables (see .env.example at the
repo root). Defaults are chosen to be safe: the shell tool is DISABLED by
default and the data directory is sandboxed under the repo's ./data folder.
"""
from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings


def _default_data_dir() -> str:
    # Repo-root/data — created on demand. All filesystem tools are scoped here.
    return str(Path(os.environ.get("AURELIA_HOME", Path.cwd())) / "data")


class Settings(BaseSettings):
    """Runtime settings. Environment prefix: AURELIA_."""

    app_name: str = "AURELIA"
    host: str = "127.0.0.1"
    port: int = 8484
    data_dir: str = _default_data_dir()
    db_filename: str = "aurelia.db"
    # SECURITY: shell tool is off unless the user explicitly opts in.
    enable_shell_tool: bool = False
    # LLM-driven tool selection: when a capable provider (Ollama) handles the
    # turn, the model itself decides which tool to call via a constrained
    # JSON decision pass. Regex routing remains the fallback. Set
    # AURELIA_LLM_TOOL_SELECTION=false to force regex-only routing.
    llm_tool_selection: bool = True
    # Default model provider: "mini" (from-scratch tiny LLM, if trained),
    # "echo" (rule-based fallback), or "ollama" (optional external runtime).
    default_provider: str = "echo"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2"
    log_level: str = "INFO"

    model_config = {"env_prefix": "AURELIA_", "env_file": ".env", "extra": "ignore"}

    @property
    def db_path(self) -> Path:
        d = Path(self.data_dir)
        d.mkdir(parents=True, exist_ok=True)
        return d / self.db_filename


settings = Settings()
