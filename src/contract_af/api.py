"""FastAPI application for async contract analysis."""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any

import tempfile

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from contract_af.pipeline.orchestrator import analyze_contract
from contract_af.utils.document_loader import load_document, _SUPPORTED_SUFFIXES

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Contract-AF",
    description="Legal contract risk analyzer — finds dangerous clauses, proves exploitability",
)

# In-memory job store. Replace with Redis / DB for production deployments.
_jobs: dict[str, dict[str, Any]] = {}


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "service": "contract-af"}


@app.post("/analyze")
async def start_analysis(
    file: UploadFile = File(...),
    user_context: str = Form(""),
) -> dict[str, str]:
    """Upload a contract and start asynchronous analysis.

    Returns a ``job_id`` that can be polled via ``GET /analyze/{job_id}``.
    """
    suffix = Path(file.filename or "contract.txt").suffix.lower()
    if suffix not in _SUPPORTED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {suffix}. Supported: {', '.join(sorted(_SUPPORTED_SUFFIXES))}",
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "running", "result": None, "error": None}

    asyncio.create_task(_run_analysis(job_id, tmp_path, user_context))

    return {"job_id": job_id, "status": "running"}


async def _run_analysis(job_id: str, file_path: str, user_context: str) -> None:
    """Background task that runs the full pipeline and stores the result."""
    try:
        full_text, _ = load_document(file_path)

        # TODO: Initialize real AgentField app here.
        # For now this is a placeholder — replace with AgentField app instance.
        app_instance = None
        report = await analyze_contract(app_instance, full_text, user_context)

        _jobs[job_id] = {
            "status": "completed",
            "result": report.model_dump(),
            "error": None,
        }
    except Exception:
        logger.exception("Analysis failed for job %s", job_id)
        import traceback

        _jobs[job_id] = {
            "status": "failed",
            "result": None,
            "error": traceback.format_exc(),
        }
    finally:
        Path(file_path).unlink(missing_ok=True)


@app.get("/analyze/{job_id}")
async def get_analysis(job_id: str) -> dict[str, Any]:
    """Poll analysis status and retrieve results when complete."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return _jobs[job_id]


@app.get("/analyze/{job_id}/report")
async def get_report(job_id: str) -> dict[str, str]:
    """Retrieve the markdown risk report for a completed job."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = _jobs[job_id]
    if job["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job not ready — current status: {job['status']}",
        )

    return {"markdown": job["result"]["risk_report_md"]}
