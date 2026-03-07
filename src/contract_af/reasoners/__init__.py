# pyright: reportMissingImports=false, reportImportCycles=false
from agentfield import AgentRouter

router = AgentRouter(tags=["legal", "contract", "risk-analysis"])

from . import pipeline  # noqa: E402,F401

__all__ = ["router"]
