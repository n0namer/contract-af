"""Tests for FastAPI endpoints, CLI, and document loader."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# contract_af.api imports contract_af.app which needs agentfield.
# The try/except in api.py handles missing AgentField gracefully,
# so agent_app will be None when agentfield is not installed.
from contract_af.api import app, _jobs
from contract_af.utils.document_loader import load_document, _SUPPORTED_SUFFIXES


# ---------------------------------------------------------------------------
# Document loader tests
# ---------------------------------------------------------------------------


class TestDocumentLoader:
    """Tests for contract_af.utils.document_loader."""

    def test_load_txt_file(self, tmp_path: Path):
        f = tmp_path / "contract.txt"
        f.write_text("Section 1. Definitions.\nSection 2. Obligations.", encoding="utf-8")

        full_text, pages = load_document(str(f))

        assert "Section 1" in full_text
        assert "Section 2" in full_text
        assert len(pages) == 1

    def test_load_md_file(self, tmp_path: Path):
        f = tmp_path / "contract.md"
        f.write_text("# Title\n\nBody text here.", encoding="utf-8")

        full_text, pages = load_document(str(f))

        assert "# Title" in full_text
        assert len(pages) == 1

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError, match="File not found"):
            load_document("/nonexistent/path/contract.txt")

    def test_unsupported_extension_raises(self, tmp_path: Path):
        f = tmp_path / "contract.xlsx"
        f.write_text("data", encoding="utf-8")

        with pytest.raises(ValueError, match="Unsupported file type"):
            load_document(str(f))

    def test_supported_suffixes_frozen(self):
        assert isinstance(_SUPPORTED_SUFFIXES, frozenset)
        assert ".txt" in _SUPPORTED_SUFFIXES
        assert ".pdf" in _SUPPORTED_SUFFIXES
        assert ".docx" in _SUPPORTED_SUFFIXES

    def test_load_accepts_path_object(self, tmp_path: Path):
        f = tmp_path / "contract.text"
        f.write_text("content", encoding="utf-8")

        full_text, pages = load_document(f)

        assert full_text == "content"

    def test_load_pdf_mocked(self, tmp_path: Path):
        """Mock pdfplumber to test PDF loading path without a real PDF."""
        f = tmp_path / "contract.pdf"
        f.write_bytes(b"fake pdf")

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Page 1 text"

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with patch("contract_af.utils.document_loader.pdfplumber") as mock_plumber:
            mock_plumber.open.return_value = mock_pdf
            full_text, pages = load_document(str(f))

        assert full_text == "Page 1 text"
        assert pages == ["Page 1 text"]

    def test_load_docx_mocked(self, tmp_path: Path):
        """Mock python-docx to test DOCX loading path."""
        f = tmp_path / "contract.docx"
        f.write_bytes(b"fake docx")

        para1 = MagicMock()
        para1.text = "First paragraph"
        para2 = MagicMock()
        para2.text = "Second paragraph"
        para3 = MagicMock()
        para3.text = "   "  # whitespace-only, should be skipped

        mock_doc = MagicMock()
        mock_doc.paragraphs = [para1, para2, para3]

        with patch("contract_af.utils.document_loader.Document", return_value=mock_doc):
            full_text, pages = load_document(str(f))

        assert "First paragraph" in full_text
        assert "Second paragraph" in full_text
        assert full_text.strip().count("   ") == 0  # whitespace para excluded
        assert len(pages) == 1


# ---------------------------------------------------------------------------
# FastAPI endpoint tests
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    def test_health_returns_ok(self):
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "contract-af"


class TestAnalyzeEndpoint:
    def test_unsupported_file_type_returns_400(self):
        client = TestClient(app)
        resp = client.post(
            "/analyze",
            files={"file": ("contract.xlsx", b"data", "application/octet-stream")},
            data={"user_context": ""},
        )
        assert resp.status_code == 400
        assert "Unsupported" in resp.json()["detail"]

    def test_upload_txt_starts_job(self):
        client = TestClient(app)
        _jobs.clear()

        with patch("contract_af.api._run_analysis", new_callable=AsyncMock):
            resp = client.post(
                "/analyze",
                files={"file": ("contract.txt", b"Section 1. Test.", "text/plain")},
                data={"user_context": "I am the customer"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "job_id" in data
        assert data["status"] == "running"

    def test_get_nonexistent_job_returns_404(self):
        client = TestClient(app)
        _jobs.clear()

        resp = client.get("/analyze/nonexistent-id")
        assert resp.status_code == 404

    def test_get_completed_job(self):
        client = TestClient(app)
        _jobs.clear()

        _jobs["test-job"] = {
            "status": "completed",
            "result": {
                "risk_report_md": "# Report\n\nNo issues found.",
                "findings": [],
            },
            "error": None,
        }

        resp = client.get("/analyze/test-job")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["result"]["risk_report_md"].startswith("# Report")

    def test_get_report_for_completed_job(self):
        client = TestClient(app)
        _jobs.clear()

        _jobs["test-job"] = {
            "status": "completed",
            "result": {"risk_report_md": "# Full Report"},
            "error": None,
        }

        resp = client.get("/analyze/test-job/report")
        assert resp.status_code == 200
        assert resp.json()["markdown"] == "# Full Report"

    def test_get_report_for_running_job_returns_400(self):
        client = TestClient(app)
        _jobs.clear()

        _jobs["running-job"] = {"status": "running", "result": None, "error": None}

        resp = client.get("/analyze/running-job/report")
        assert resp.status_code == 400
        assert "not ready" in resp.json()["detail"]

    def test_get_report_nonexistent_returns_404(self):
        client = TestClient(app)
        _jobs.clear()

        resp = client.get("/analyze/no-such-job/report")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class TestCLI:
    def test_main_no_args_exits(self):
        from contract_af.cli import main

        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", ["contract-af"]):
                main()
        assert exc_info.value.code == 1

    def test_analyze_command_loads_and_runs(self, tmp_path: Path):
        from contract_af.cli import _analyze

        f = tmp_path / "test.txt"
        f.write_text("Section 1. Test contract.", encoding="utf-8")

        mock_report = MagicMock()
        mock_report.risk_report_md = "# Test Report"
        mock_report.structured_json = {"findings": []}

        args = MagicMock()
        args.file = str(f)
        args.context = ""
        args.output_format = "markdown"
        args.output = None

        with patch(
            "contract_af.pipeline.orchestrator.analyze_contract",
            new_callable=AsyncMock,
            return_value=mock_report,
        ):
            import asyncio

            asyncio.run(_analyze(args))

    def test_analyze_json_format(self, tmp_path: Path):
        from contract_af.cli import _analyze

        f = tmp_path / "test.txt"
        f.write_text("Test contract", encoding="utf-8")
        out = tmp_path / "output.json"

        mock_report = MagicMock()
        mock_report.structured_json = {"contract_type": "nda", "findings": []}

        args = MagicMock()
        args.file = str(f)
        args.context = ""
        args.output_format = "json"
        args.output = str(out)

        with patch(
            "contract_af.pipeline.orchestrator.analyze_contract",
            new_callable=AsyncMock,
            return_value=mock_report,
        ):
            import asyncio

            asyncio.run(_analyze(args))

        import json

        result = json.loads(out.read_text())
        assert result["contract_type"] == "nda"
