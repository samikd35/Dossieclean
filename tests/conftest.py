"""
Pytest configuration and shared fixtures for DossieClean tests.
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================
# Environment Fixtures
# ============================================


@pytest.fixture(scope="session")
def test_env():
    """Set up test environment variables."""
    env_vars = {
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", "test-key"),
        "AZURE_STORAGE_CONNECTION_STRING": os.environ.get(
            "AZURE_STORAGE_CONNECTION_STRING",
            "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test;EndpointSuffix=core.windows.net",
        ),
        "AZURE_CONTAINER_NAME": os.environ.get("AZURE_CONTAINER_NAME", "test-container"),
        "QDRANT_URL": os.environ.get("QDRANT_URL", "http://localhost:6333"),
        "QDRANT_API_KEY": os.environ.get("QDRANT_API_KEY", "test-key"),
        "COLLECTION_NAME": "test_collection",
        "DB_NAME": "test_db",
        "CHUNK_SIZE": "512",
        "CHUNK_OVERLAP": "50",
        "SECRET_KEY": "test-secret-key",
        "DOSSIECLEAN_INIT_STORAGE": "false",
    }

    with patch.dict(os.environ, env_vars):
        yield env_vars


# ============================================
# Flask App Fixtures
# ============================================


@pytest.fixture(scope="session")
def app(test_env, tmp_path_factory):
    """Create Flask application for testing."""
    # Import here to ensure environment is set up first
    from app import app as flask_app

    upload_dir = tmp_path_factory.mktemp("uploads")
    flask_app.config.update(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "UPLOAD_FOLDER": str(upload_dir),
        }
    )

    yield flask_app


@pytest.fixture
def client(app):
    """Create Flask test client."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create Flask CLI test runner."""
    return app.test_cli_runner()


# ============================================
# File Fixtures
# ============================================


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_pdf(temp_dir):
    """Create a minimal sample PDF file for testing."""
    # Minimal PDF content
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT
/F1 12 Tf
100 700 Td
(Test PDF) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000206 00000 n
trailer
<< /Size 5 /Root 1 0 R >>
startxref
300
%%EOF"""

    pdf_path = temp_dir / "test_document.pdf"
    pdf_path.write_bytes(pdf_content)
    return pdf_path


@pytest.fixture
def sample_metadata():
    """Sample metadata dictionary for testing."""
    return {
        "title": "Test Document Title",
        "authors": ["Author, Test A.", "Writer, Sample B."],
        "year": "2024",
        "journal_or_university": "Test University",
        "department": "Computer Science",
        "abstract": "This is a test abstract for the document.",
        "keywords": ["testing", "python", "pdf"],
        "document_type": "thesis",
        "page_count": 10,
        "file_size_kb": 256.5,
    }


# ============================================
# Mock Fixtures
# ============================================


@pytest.fixture
def mock_openai():
    """Mock OpenAI API calls."""
    with patch("openai.OpenAI") as mock:
        # Mock chat completions
        mock_client = MagicMock()
        mock.return_value = mock_client

        # Mock metadata extraction response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[
            0
        ].message.content = """{
            "title": "Test Document",
            "authors": ["Test Author"],
            "year": "2024",
            "abstract": "Test abstract",
            "keywords": ["test"]
        }"""
        mock_client.chat.completions.create.return_value = mock_response

        # Mock embeddings response
        mock_embedding_response = MagicMock()
        mock_embedding_response.data = [MagicMock()]
        mock_embedding_response.data[0].embedding = [0.1] * 1536
        mock_client.embeddings.create.return_value = mock_embedding_response

        yield mock_client


@pytest.fixture
def mock_qdrant():
    """Mock Qdrant client."""
    with patch("qdrant_client.QdrantClient") as mock:
        mock_client = MagicMock()
        mock.return_value = mock_client

        # Mock collection operations
        mock_client.get_collection.return_value = MagicMock()
        mock_client.upsert.return_value = MagicMock()
        mock_client.search.return_value = []
        mock_client.scroll.return_value = ([], None)
        mock_client.count.return_value = MagicMock(count=0)

        yield mock_client


@pytest.fixture
def mock_azure_blob():
    """Mock Azure Blob Storage client."""
    with patch("azure.storage.blob.BlobServiceClient") as mock:
        mock_service = MagicMock()
        mock.from_connection_string.return_value = mock_service

        mock_container = MagicMock()
        mock_service.get_container_client.return_value = mock_container
        mock_container.exists.return_value = True

        mock_blob = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob
        mock_blob.url = "https://test.blob.core.windows.net/test/test.pdf"

        yield mock_service


# ============================================
# Markers
# ============================================


def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")
