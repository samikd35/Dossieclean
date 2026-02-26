"""Unit tests for helper functions in app.py."""

import pytest


@pytest.mark.unit
def test_allowed_file_only_accepts_pdf(app):
    """Only .pdf files should be accepted for upload."""
    from app import allowed_file

    assert allowed_file("document.pdf")
    assert allowed_file("DOCUMENT.PDF")
    assert not allowed_file("document.txt")
    assert not allowed_file("document")


@pytest.mark.unit
def test_chunk_text_splits_long_content(app):
    """chunk_text should split long text into multiple non-empty chunks."""
    from app import chunk_text

    # Small max_tokens forces multiple chunks.
    text = "\n".join(["paragraph " + str(i) + " " + ("x" * 80) for i in range(20)])
    chunks = chunk_text(text, max_tokens=10)

    assert len(chunks) > 1
    assert all(chunk.strip() for chunk in chunks)


@pytest.mark.unit
def test_truncate_text_respects_limit(app):
    """truncate_text should return at most the requested length."""
    from app import truncate_text

    long_text = "a" * 100
    assert truncate_text(long_text, max_length=25) == "a" * 25
    assert truncate_text("short", max_length=25) == "short"
