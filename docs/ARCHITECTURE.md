# DossieClean Architecture

This document provides a detailed technical overview of the DossieClean system architecture.

## Table of Contents

- [System Overview](#system-overview)
- [Components](#components)
- [Data Flow](#data-flow)
- [Storage Architecture](#storage-architecture)
- [API Design](#api-design)
- [Security Considerations](#security-considerations)
- [Extension Points](#extension-points)

## System Overview

DossieClean is a Flask-based web application for processing PDF documents, extracting metadata using AI, and storing both documents and their vector embeddings for semantic search.

### High-Level Architecture

```
                                    ┌─────────────────┐
                                    │   Web Browser   │
                                    └────────┬────────┘
                                             │
                                             ▼
┌────────────────────────────────────────────────────────────────────┐
│                         Flask Application                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │    Routes    │  │   Templates  │  │    Static Assets         │  │
│  │  (app.py)    │  │   (Jinja2)   │  │    (CSS/JS)              │  │
│  └──────┬───────┘  └──────────────┘  └──────────────────────────┘  │
│         │                                                           │
│  ┌──────▼───────────────────────────────────────────────────────┐  │
│  │                    Business Logic                             │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │  │
│  │  │ PDF Extract │  │  Chunking   │  │  Metadata Extract   │   │  │
│  │  │  (PyPDF2)   │  │             │  │    (OpenAI)         │   │  │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘   │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          │                         │                         │
          ▼                         ▼                         ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Azure Blob     │     │     Qdrant      │     │    OpenAI       │
│  Storage        │     │  Vector DB      │     │    API          │
│  (PDF Files)    │     │  (Embeddings)   │     │  (AI Models)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## Components

### 1. Flask Application (`app.py`)

The main application file containing all routes, business logic, and integrations.

**Key Responsibilities:**
- HTTP request handling
- File upload processing
- Session management
- Template rendering
- API endpoints

**Size:** ~2300 lines (monolithic design)

### 2. PDF Processing

**Text Extraction:**
- Uses PyPDF2 for text extraction
- Processes pages in batches (10 pages) to optimize memory
- Handles large files with garbage collection

**Chunking:**
- Splits text into configurable chunks
- Default: 512 tokens with 50 token overlap
- Paragraph-aware splitting

### 3. AI Integration (OpenAI)

**Metadata Extraction:**
- Model: `gpt-4o-mini`
- Extracts: title, authors, year, abstract, keywords, document type
- Processes first 5 pages for metadata

**Embeddings:**
- Model: `text-embedding-3-small`
- Dimension: 1536
- Used for semantic search

### 4. Storage Layer

**Azure Blob Storage:**
- Stores original PDF files
- Naming convention: `{title}_{author}_{year}.pdf`
- Supports chunked upload for large files (>10MB)

**Qdrant Vector Database:**
- Stores document metadata and embeddings
- Collection: Configurable (default: `AAU_PDF`)
- Distance metric: Cosine similarity

### 5. Frontend

**Templates (Jinja2):**
- `base.html` - Base layout with navigation
- `index.html` - Home page with upload form
- `dashboard.html` - Statistics and recent documents
- `batch_upload.html` - Batch processing interface
- `batch_status.html` - Real-time progress tracking

**Static Assets:**
- `style.css` - Light/dark theme support
- `main.js` - Theme toggle, file input enhancements

## Data Flow

### Single Document Upload

```
1. User uploads PDF
       │
       ▼
2. File saved to temp directory
       │
       ▼
3. Text extracted (PyPDF2)
       │
       ▼
4. Metadata extracted (OpenAI GPT-4o-mini)
       │
       ▼
5. User reviews/edits metadata
       │
       ▼
6. PDF uploaded to Azure Blob Storage
       │
       ▼
7. Text chunked (configurable size)
       │
       ▼
8. Embeddings generated for each chunk (OpenAI)
       │
       ▼
9. Document + chunks stored in Qdrant
       │
       ▼
10. Temp file cleaned up
```

### Batch Processing

```
1. User uploads multiple PDFs
       │
       ▼
2. Files saved, manifest created (batch_status/manifest_{id}.json)
       │
       ▼
3. Batch execution triggered
       │
       ▼
4. For each file:
   ├── Extract metadata
   ├── Upload to Azure
   ├── Generate embeddings
   ├── Store in Qdrant
   └── Update status file (batch_status/batch_{id}.json)
       │
       ▼
5. Frontend polls /api/batch_status/{id} for progress
       │
       ▼
6. Results displayed when complete
```

## Storage Architecture

### Qdrant Data Model

**Document Record:**
```json
{
  "id": "uuid",
  "vector": [0.1, 0.2, ...],  // 1536 dimensions
  "payload": {
    "document_id": "uuid",
    "page_content": "first chunk text",
    "metadata": {
      "title": "Document Title",
      "authors": ["Author, A."],
      "year": "2024",
      "journal_or_university": "University Name",
      "department": "Department",
      "abstract": "Abstract text...",
      "keywords": ["keyword1", "keyword2"],
      "document_type": "thesis",
      "page_count": 100,
      "file_size_kb": 2048.5,
      "azure_url": "https://...",
      "is_chunk": false,
      "upload_date": "2024-01-01T12:00:00"
    }
  }
}
```

**Chunk Record:**
```json
{
  "id": "uuid",
  "vector": [0.1, 0.2, ...],
  "payload": {
    "document_id": "parent-uuid",
    "chunk_index": 0,
    "page_content": "chunk text content",
    "metadata": {
      "title": "Document Title",
      "authors": ["Author, A."],
      "azure_url": "https://...",
      "is_chunk": true,
      "created_at": "2024-01-01T12:00:00"
    }
  }
}
```

### Azure Blob Structure

```
container/
├── document_title_author_2024.pdf
├── another_document_writer_2023.pdf
└── ...
```

## API Design

### REST Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Home page |
| GET | `/dashboard` | Statistics dashboard |
| POST | `/upload` | Single file upload |
| POST | `/process_document` | Direct processing |
| POST | `/batch_upload` | Batch file upload |
| POST | `/batch_upload_execute` | Execute batch |
| GET | `/api/batch_status/<id>` | Batch status |
| GET | `/api/batch_logs/<id>` | Batch logs |
| POST | `/api/extract` | Extract metadata |
| POST | `/api/save` | Save document |
| GET | `/document/<id>` | View document |
| POST | `/delete_document/<id>` | Delete document |

### Response Formats

**Success Response:**
```json
{
  "success": true,
  "message": "Operation completed",
  "data": { ... }
}
```

**Error Response:**
```json
{
  "success": false,
  "error": "Error description"
}
```

## Security Considerations

### Current Implementation

1. **File Validation:** Only PDF files accepted
2. **Secure Filenames:** Werkzeug's `secure_filename()` used
3. **Environment Variables:** Secrets stored in `.env`
4. **Session Management:** Flask sessions for temporary data

### Recommendations for Production

1. **Add Authentication:** Implement user authentication
2. **Rate Limiting:** Prevent API abuse
3. **Input Validation:** Sanitize all user inputs
4. **HTTPS:** Enable TLS in production
5. **CORS:** Configure appropriate CORS policies
6. **Audit Logging:** Track all document operations

## Extension Points

### Adding New Storage Backends

Implement these functions:
- `upload_pdf_to_<backend>(file_path, metadata)`
- `download_pdf_from_<backend>(document_id)`

### Adding New AI Models

Modify these functions:
- `extract_metadata_from_pdf()` - Change model in API call
- `generate_embedding()` - Change embedding model

### Adding New Document Types

1. Update `ALLOWED_EXTENSIONS` in config
2. Add text extraction logic for new type
3. Update metadata extraction prompt if needed

### Custom Metadata Fields

1. Update `metadata_prompt` in `app.py`
2. Update Qdrant payload structure
3. Update templates to display new fields

## Performance Considerations

### Current Optimizations

- Batch page processing (10 pages at a time)
- Garbage collection for large files
- Chunked Azure uploads for files >10MB
- Filtered logging for polling requests

### Potential Improvements

1. **Async Processing:** Use Celery for background tasks
2. **Caching:** Add Redis for frequently accessed data
3. **Connection Pooling:** Reuse database connections
4. **CDN:** Serve static assets via CDN
5. **Horizontal Scaling:** Containerize for Kubernetes
