# pyright: reportMissingImports=false, reportImportCycles=false
from agentfield import AgentRouter

router = AgentRouter(tags=["legal", "contract", "risk-analysis"])

from . import phases  # noqa: E402,F401
from . import harnesses  # noqa: E402,F401

__all__ = ["router"]
