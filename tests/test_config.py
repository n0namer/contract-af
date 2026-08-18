from __future__ import annotations

import pytest

from contract_af.config import AIIntegrationConfig


def test_aforge_exec_is_the_default_harness(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "CONTRACT_AF_PROVIDER",
        "HARNESS_PROVIDER",
        "CONTRACT_AF_AFORGE_BIN",
        "AFORGE_BIN",
        "AGENTFIELD_AFORGE_COMMAND",
    ):
        monkeypatch.delenv(key, raising=False)

    config = AIIntegrationConfig.from_env()

    assert config.provider == "aforge"
    assert config.aforge_bin == "aforge"
    assert config.provider_env()["AGENTFIELD_AFORGE_COMMAND"] == "exec"


def test_opencode_remains_an_explicit_rollback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARNESS_PROVIDER", "opencode")

    assert AIIntegrationConfig.from_env().provider == "opencode"


def test_aforge_bin_override_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    """CONTRACT_AF_AFORGE_BIN wins over AFORGE_BIN, which wins over the default."""
    monkeypatch.delenv("CONTRACT_AF_AFORGE_BIN", raising=False)
    monkeypatch.setenv("AFORGE_BIN", "/opt/aforge/aforge")

    assert AIIntegrationConfig.from_env().aforge_bin == "/opt/aforge/aforge"

    monkeypatch.setenv("CONTRACT_AF_AFORGE_BIN", "/usr/local/bin/aforge")

    assert AIIntegrationConfig.from_env().aforge_bin == "/usr/local/bin/aforge"


def test_provider_env_forwards_provider_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """Harness subprocess env carries the LLM key AForge needs to reach OpenRouter."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-key")

    env = AIIntegrationConfig.from_env().provider_env()

    assert env["OPENROUTER_API_KEY"] == "sk-test-key"
