# Dossie

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/flask-3.0+-green.svg)](https://flask.palletsprojects.com/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A minimalist PDF processing and vector storage system built with Flask. Upload PDF documents, extract metadata using AI, and store both documents and vector embeddings for semantic search.

<p align="center">
  <img src="docs/images/screenshot-home.png" alt="DossieClean Home" width="600">
</p>

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Reference](#api-reference)
- [Architecture](#architecture)
- [Contributing](#contributing)
- [License](#license)

## Features

- **PDF Upload** - Upload single or batch academic/research PDF documents
- **AI Metadata Extraction** - Automatically extract title, authors, year, abstract, keywords using GPT-4o-mini
- **Metadata Editing** - Review and edit extracted metadata before saving
- **Smart Chunking** - Split PDFs into configurable chunks for efficient retrieval
- **Vector Embeddings** - Generate 1536-dimension embeddings using OpenAI text-embedding-3-small
- **Hybrid Storage** - Store PDFs in Azure Blob Storage, embeddings in Qdrant
- **Batch Processing** - Process multiple PDFs with real-time progress tracking
- **Dashboard** - View statistics about your document collection
- **Semantic Search** - Search across documents using natural language
- **Dark/Light Theme** - Toggle between minimalist themes

## Quick Start

```bash
# Clone the repository
git clone https://github.com/samikd35/Dossieclean_pdfvault.git
cd Dossieclean_pdfvault

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Run the application
python app.py
```

Then open http://localhost:5000 in your browser.

## Requirements

- **Python 3.8+**
- **Azure Blob Storage** account (for PDF storage)
- **Qdrant** account - cloud or self-hosted (for vector storage)
- **OpenAI API key** (for metadata extraction and embeddings)

## Installation

1. Clone this repository
2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file based on the `.env.template` and fill in your credentials:

```bash
cp .env.template .env
# Edit the .env file with your actual credentials
```

4. Run the application:

```bash
python app.py
```

5. Open your browser and navigate to `http://localhost:5000`

## Configuration

Copy `.env.example` to `.env` and configure the following:

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key for metadata extraction and embeddings | Yes |
| `AZURE_STORAGE_CONNECTION_STRING` | Azure Blob Storage connection string | Yes |
| `AZURE_CONTAINER_NAME` | Azure container name for PDF storage | Yes |
| `QDRANT_URL` | Qdrant cloud instance URL | Yes |
| `QDRANT_API_KEY` | Qdrant API key | Yes |
| `COLLECTION_NAME` | Qdrant collection name (default: `AAU_PDF`) | No |
| `CHUNK_SIZE` | Text chunk size in tokens (default: `512`) | No |
| `CHUNK_OVERLAP` | Overlap between chunks (default: `50`) | No |

See `.env.example` for detailed documentation of all options.

## Usage

### Uploading a Document

1. Navigate to the home page
2. Click "Choose PDF File" and select a PDF document
3. Click "Upload & Extract Metadata"
4. Review and edit the extracted metadata
5. Click "Save to Database" to store the document

### Searching Documents

1. Navigate to the Dashboard
2. Enter your search query in the search box
3. Select whether to search "Documents" or "Chunks"
4. View your search results

### Viewing Document Details

1. Click on a document title in the search results or dashboard
2. View detailed metadata and all document chunks
3. Use the filter box to search within chunks

### Adjusting Settings

1. Navigate to the Settings page
2. Adjust chunk size and overlap settings
3. Choose between light and dark theme

## API Reference

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Home page with upload form |
| `GET` | `/dashboard` | Document statistics and recent documents |
| `POST` | `/upload` | Upload single PDF with metadata preview |
| `POST` | `/process_document` | Direct upload and process (no preview) |
| `POST` | `/batch_upload` | Upload multiple PDFs for batch processing |
| `POST` | `/batch_upload_execute` | Execute batch processing |
| `GET` | `/api/batch_status/<id>` | Get batch processing status |
| `POST` | `/api/extract` | Extract metadata from PDF (returns JSON) |
| `POST` | `/api/save` | Save PDF with metadata to database |

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  PDF Upload │ ──▶ │ Text Extract │ ──▶ │ AI Metadata     │
│  (Flask)    │     │ (PyPDF2)     │     │ (GPT-4o-mini)   │
└─────────────┘     └──────────────┘     └─────────────────┘
                                                  │
                    ┌─────────────────────────────┘
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                    STORAGE LAYER                             │
├─────────────────────────────┬───────────────────────────────┤
│      Azure Blob Storage     │         Qdrant                │
│      (PDF Files)            │    (Vector Embeddings)        │
└─────────────────────────────┴───────────────────────────────┘
```

### Project Structure

```
dossieclean/
├── app.py                # Main Flask application
├── requirements.txt      # Python dependencies
├── .env.example          # Environment template
├── static/
│   ├── css/style.css     # Application styles (light/dark themes)
│   └── js/main.js        # Frontend JavaScript
├── templates/            # Jinja2 templates
│   ├── base.html         # Base layout
│   ├── index.html        # Home page
│   ├── dashboard.html    # Statistics dashboard
│   ├── batch_upload.html # Batch upload interface
│   └── ...               # Other templates
├── tests/                # Test files
├── docs/                 # Documentation
└── batch_status/         # Batch processing status files
```

For detailed architecture documentation, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

For deployment instructions, see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Setup Instructions

### Azure Blob Storage Setup

1. Create an Azure Storage account
2. Create a container for PDF storage
3. Get the connection string from Access Keys
4. Add to `.env` as `AZURE_STORAGE_CONNECTION_STRING`

### Qdrant Setup

1. Create a Qdrant account at [cloud.qdrant.io](https://cloud.qdrant.io/)
2. Create a new cluster (free tier available)
3. Create an API key
4. Add the URL and API key to your `.env` file

### OpenAI Setup

1. Get an API key from [platform.openai.com](https://platform.openai.com/api-keys)
2. Add to `.env` as `OPENAI_API_KEY`

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

- Read the [Code of Conduct](CODE_OF_CONDUCT.md)
- Check [open issues](https://github.com/samikd35/Dossieclean_pdfvault/issues) for ways to contribute
- Submit bug reports and feature requests via GitHub Issues

## Security

For security concerns, please see our [Security Policy](SECURITY.md).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgements

- [Flask](https://flask.palletsprojects.com/) - Web framework
- [OpenAI](https://openai.com/) - AI models for metadata extraction and embeddings
- [Azure Blob Storage](https://azure.microsoft.com/en-us/products/storage/blobs) - PDF file storage
- [Qdrant](https://qdrant.tech/) - Vector database for semantic search
- [PyPDF2](https://pypdf2.readthedocs.io/) - PDF text extraction

---

<p align="center">
  Made with ❤️ for the research community
</p>
