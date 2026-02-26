# DossieClean

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/flask-3.0+-green.svg)](https://flask.palletsprojects.com/)
[![CI](https://github.com/samikd35/Dossieclean_pdfvault/actions/workflows/ci.yml/badge.svg)](https://github.com/samikd35/Dossieclean_pdfvault/actions/workflows/ci.yml)

DossieClean is a Flask application for PDF ingestion, AI-assisted metadata extraction, and vector-based document retrieval.

It stores PDFs in Azure Blob Storage and vector embeddings/metadata in Qdrant.

## Features

- PDF upload and batch upload flows
- Metadata extraction with OpenAI models
- Configurable text chunking for embedding generation
- Vector search and document dashboard
- Azure Blob Storage integration for source files
- Qdrant integration for vector indexing and retrieval

## Architecture

High-level flow:

1. Upload PDF (`/upload` or batch endpoints)
2. Extract text and metadata
3. Upload original PDF to Azure Blob Storage
4. Generate embeddings and store payloads in Qdrant
5. Query and browse documents from the dashboard

Detailed docs:

- [Architecture](docs/ARCHITECTURE.md)
- [Deployment](docs/DEPLOYMENT.md)

## Quick Start

```bash
# Clone
git clone https://github.com/samikd35/Dossieclean_pdfvault.git
cd Dossieclean_pdfvault

# Create virtual env
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# edit .env values

# Run app
python app.py
```

Open `http://localhost:5000`.

## Configuration

Required environment variables:

- `OPENAI_API_KEY`
- `AZURE_STORAGE_CONNECTION_STRING`
- `AZURE_CONTAINER_NAME`
- `QDRANT_URL`
- `QDRANT_API_KEY`
- `SECRET_KEY`

Optional environment variables:

- `COLLECTION_NAME` (default: `AAU_PDF`)
- `CHUNK_SIZE` (default: `512`)
- `CHUNK_OVERLAP` (default: `50`)
- `MAX_UPLOAD_SIZE_MB` (default: `100`)
- `PORT` (default: `5000`)
- `FLASK_DEBUG` (default: `False`)
- `DOSSIECLEAN_INIT_STORAGE` (set to `false` for tests/CI)

See [.env.example](.env.example) for a complete template.

## Development

```bash
pip install -r requirements-dev.txt
pytest -v
```

Code quality tools:

```bash
black tests/
isort tests/
flake8 tests/
```

## Testing Strategy

- `tests/` contains deterministic unit tests that run offline in CI.
- `scripts/manual_checks/` is reserved for optional local diagnostics and is intentionally not part of CI.

## Security and Disclosure

- Read [SECURITY.md](SECURITY.md) for vulnerability reporting.
- Do not commit `.env` or production credentials.
- This app does not implement built-in user auth; secure public deployments behind an auth layer.

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), and [SUPPORT.md](SUPPORT.md).

## License

MIT. See [LICENSE](LICENSE).
