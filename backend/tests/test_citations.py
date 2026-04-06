from __future__ import annotations

from takehome.services.citations import parse_citations, strip_citations
from takehome.services.retrieval import ChunkResult


def _chunk(doc_id: str, filename: str, page: int) -> ChunkResult:
    return ChunkResult(
        document_id=doc_id,
        document_filename=filename,
        page_number=page,
        content="dummy",
        rank=1.0,
    )


def test_basic_citation() -> None:
    """A single valid citation is extracted and matched to its chunk."""
    chunks = [_chunk("doc1", "lease.pdf", 3)]
    response = "The rent is due quarterly [lease.pdf, page 3]."

    result = parse_citations(response, chunks)

    assert len(result) == 1
    assert result[0] == {
        "document_id": "doc1",
        "filename": "lease.pdf",
        "page_number": 3,
    }


def test_multiple_citations_from_different_documents() -> None:
    """Citations from multiple documents are all extracted."""
    chunks = [
        _chunk("doc1", "lease.pdf", 3),
        _chunk("doc2", "report.pdf", 1),
    ]
    response = (
        "The rent is due quarterly [lease.pdf, page 3]. "
        "The valuation confirms this [report.pdf, page 1]."
    )

    result = parse_citations(response, chunks)

    assert len(result) == 2
    filenames = {c["filename"] for c in result}
    assert filenames == {"lease.pdf", "report.pdf"}


def test_deduplication() -> None:
    """The same citation referenced twice yields only one entry."""
    chunks = [_chunk("doc1", "lease.pdf", 3)]
    response = (
        "See [lease.pdf, page 3] for rent details. "
        "As noted in [lease.pdf, page 3], rent is quarterly."
    )

    result = parse_citations(response, chunks)

    assert len(result) == 1


def test_invalid_citation_filtered_out() -> None:
    """A citation whose filename does not appear in chunks is excluded."""
    chunks = [_chunk("doc1", "lease.pdf", 3)]
    response = "See [unknown.pdf, page 1] for details."

    result = parse_citations(response, chunks)

    assert result == []


def test_case_insensitive_filename_matching() -> None:
    """Filenames are matched case-insensitively, using the canonical name."""
    chunks = [_chunk("doc1", "Lease-Agreement.pdf", 5)]
    response = "See [lease-agreement.pdf, page 5]."

    result = parse_citations(response, chunks)

    assert len(result) == 1
    assert result[0]["filename"] == "Lease-Agreement.pdf"
    assert result[0]["page_number"] == 5


def test_no_citations_returns_empty_list() -> None:
    """A response with no citation patterns yields an empty list."""
    chunks = [_chunk("doc1", "lease.pdf", 3)]
    response = "The rent is due quarterly according to the lease."

    result = parse_citations(response, chunks)

    assert result == []


def test_page_variant_p_dot() -> None:
    """The abbreviated form [filename.pdf, p. 3] is recognised."""
    chunks = [_chunk("doc1", "lease.pdf", 3)]
    response = "Rent terms are in [lease.pdf, p. 3]."

    result = parse_citations(response, chunks)

    assert len(result) == 1
    assert result[0]["page_number"] == 3


def test_page_variant_p_no_dot() -> None:
    """The abbreviated form [filename.pdf, p 3] (no dot) is recognised."""
    chunks = [_chunk("doc1", "lease.pdf", 3)]
    response = "Rent terms are in [lease.pdf, p 3]."

    result = parse_citations(response, chunks)

    assert len(result) == 1
    assert result[0]["page_number"] == 3


def test_invalid_page_number_filtered_out() -> None:
    """A citation with a page number not in chunks is excluded."""
    chunks = [_chunk("doc1", "lease.pdf", 3)]
    response = "See [lease.pdf, page 99]."

    result = parse_citations(response, chunks)

    assert result == []


def test_empty_chunks_returns_empty() -> None:
    """When no chunks are provided, no citations can be validated."""
    response = "See [lease.pdf, page 3]."

    result = parse_citations(response, [])

    assert result == []


def test_strip_citations_removes_markers() -> None:
    """Raw citation markers are removed from display text."""
    text = "The rent is £50,000 [lease.pdf, page 3]. See also [report.pdf, p. 1]."
    assert strip_citations(text) == "The rent is £50,000. See also."


def test_strip_citations_cleans_whitespace() -> None:
    """Double spaces left by stripping are collapsed."""
    text = "According to [lease.pdf, page 3] the rent is due quarterly."
    assert strip_citations(text) == "According to the rent is due quarterly."
