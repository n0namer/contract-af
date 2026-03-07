"""Configuration schemas for Contract-AF."""

import os
import tempfile

from pydantic import BaseModel, Field


class AIIntegrationConfig(BaseModel):
    provider: str = Field(
        default_factory=lambda: os.getenv(
            "CONTRACT_AF_PROVIDER", os.getenv("HARNESS_PROVIDER", "opencode")
        )
    )
    harness_model: str = Field(
        default_factory=lambda: os.getenv(
            "CONTRACT_AF_MODEL",
            os.getenv("HARNESS_MODEL", "openrouter/moonshotai/kimi-k2.5"),
        )
    )
    ai_model: str = Field(
        default_factory=lambda: os.getenv(
            "CONTRACT_AF_AI_MODEL",
            os.getenv(
                "AI_MODEL",
                os.getenv("CONTRACT_AF_MODEL", "openrouter/moonshotai/kimi-k2.5"),
            ),
        )
    )
    max_turns: int = Field(
        default_factory=lambda: int(os.getenv("CONTRACT_AF_MAX_TURNS", "50"))
    )
    opencode_bin: str = Field(
        default_factory=lambda: os.getenv("CONTRACT_AF_OPENCODE_BIN", "opencode")
    )
    opencode_server: str | None = Field(
        default_factory=lambda: os.getenv(
            "CONTRACT_AF_OPENCODE_SERVER", os.getenv("OPENCODE_SERVER")
        ),
    )

    @classmethod
    def from_env(cls) -> "AIIntegrationConfig":
        return cls()

    def provider_env(self) -> dict[str, str]:
        env_keys = (
            "OPENROUTER_API_KEY",
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "GOOGLE_API_KEY",
        )
        env: dict[str, str] = {
            key: value for key in env_keys if (value := os.getenv(key))
        }
        xdg = os.getenv("XDG_DATA_HOME") or os.path.join(
            tempfile.gettempdir(), "opencode-shared-data"
        )
        os.makedirs(xdg, exist_ok=True)
        env["XDG_DATA_HOME"] = xdg
        return env
