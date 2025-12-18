# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Open source preparation files (CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md)
- Comprehensive .gitignore for Python/Flask projects
- Enhanced .env.example with detailed documentation
- MIT License

### Changed
- Improved documentation structure

### Security
- Added security policy and vulnerability reporting guidelines

## [1.0.0] - 2025-01-01

### Added
- Initial release of DossieClean
- PDF upload and processing functionality
- AI-powered metadata extraction using OpenAI GPT-4o-mini
- Vector embeddings generation using text-embedding-3-small
- Azure Blob Storage integration for PDF file storage
- Qdrant vector database integration for semantic search
- Batch upload and processing with real-time progress tracking
- Dashboard with document statistics
- Document viewer with chunk details
- Light/dark theme support
- Configurable chunk size and overlap settings
- RESTful API endpoints for metadata extraction and document saving

### Technical Features
- Flask-based web application
- PyPDF2 for PDF text extraction
- Chunked upload support for large files (>10MB)
- Memory-optimized PDF processing
- Comprehensive logging system

### Infrastructure
- Azure Blob Storage for scalable PDF storage
- Qdrant Cloud for vector storage and similarity search
- Environment-based configuration

---

## Version History Summary

| Version | Date       | Description                    |
|---------|------------|--------------------------------|
| 1.0.0   | 2025-01-01 | Initial public release         |

## How to Update This Changelog

When making changes to the project:

1. Add your changes under the `[Unreleased]` section
2. Use the appropriate category:
   - **Added** for new features
   - **Changed** for changes in existing functionality
   - **Deprecated** for soon-to-be removed features
   - **Removed** for now removed features
   - **Fixed** for any bug fixes
   - **Security** for vulnerability fixes
3. When releasing, move unreleased changes to a new version section
4. Update the version number following semantic versioning

[Unreleased]: https://github.com/samikd35/Dossieclean_pdfvault/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/samikd35/Dossieclean_pdfvault/releases/tag/v1.0.0
