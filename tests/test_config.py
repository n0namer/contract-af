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
