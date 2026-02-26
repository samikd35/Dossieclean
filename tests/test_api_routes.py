"""Unit tests for HTTP routes in app.py."""

import json
import os
from io import BytesIO

import pytest


@pytest.mark.unit
def test_index_route_renders(client):
    """Landing page should render successfully."""
    response = client.get("/")

    assert response.status_code == 200
    assert b"Dossie" in response.data


@pytest.mark.unit
def test_api_extract_requires_file(client):
    """/api/extract should reject requests without a file."""
    response = client.post("/api/extract", data={})

    assert response.status_code == 400
    assert response.get_json()["error"] == "No file uploaded"


@pytest.mark.unit
def test_api_save_rejects_invalid_metadata(client):
    """/api/save should reject invalid JSON metadata payloads."""
    response = client.post(
        "/api/save",
        data={
            "pdf_file": (BytesIO(b"%PDF-1.4\n%"), "test.pdf"),
            "metadata": "{not-valid-json}",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Invalid metadata JSON"


@pytest.mark.unit
def test_api_save_returns_document_id_and_cleans_temp_file(client, monkeypatch):
    """/api/save should surface saved document id and remove local temp file."""
    import app as app_module

    captured = {}

    def fake_save_pdf_to_db(file_path, metadata):
        captured["file_path"] = file_path
        assert os.path.exists(file_path)
        assert metadata["title"] == "Sample"
        return {"success": True, "document_id": "doc-123"}

    monkeypatch.setattr(app_module, "save_pdf_to_db", fake_save_pdf_to_db)

    response = client.post(
        "/api/save",
        data={
            "pdf_file": (BytesIO(b"%PDF-1.4\n%"), "test.pdf"),
            "metadata": json.dumps({"title": "Sample"}),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "success"
    assert response.get_json()["document_id"] == "doc-123"
    assert not os.path.exists(captured["file_path"])
