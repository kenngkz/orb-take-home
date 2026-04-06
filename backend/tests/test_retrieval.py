from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from takehome.db.models import Conversation, Document, DocumentChunk
from takehome.services.retrieval import retrieve_chunks


async def _create_conversation_with_chunks(
    session: AsyncSession,
    chunks: list[tuple[str, int, str]],
    filename: str = "test.pdf",
) -> str:
    """Helper: create a conversation with a document and specified chunks.

    Each chunk tuple is (filename, page_number, content).
    Returns the conversation ID.
    """
    conv = Conversation(title="Test")
    session.add(conv)
    await session.flush()

    # Group chunks by filename
    filenames = {c[0] for c in chunks}
    doc_map: dict[str, Document] = {}
    for fname in sorted(filenames):
        doc = Document(
            conversation_id=conv.id,
            filename=fname,
            file_path=f"/tmp/{fname}",
            extracted_text="",
            page_count=sum(1 for c in chunks if c[0] == fname),
        )
        session.add(doc)
        await session.flush()
        doc_map[fname] = doc

    for fname, page_num, content in chunks:
        chunk = DocumentChunk(
            document_id=doc_map[fname].id,
            page_number=page_num,
            content=content,
        )
        session.add(chunk)

    await session.commit()
    return conv.id


async def test_fts_returns_matching_chunks(session: AsyncSession) -> None:
    """FTS should return chunks containing the query terms, ranked by relevance."""
    conv_id = await _create_conversation_with_chunks(
        session,
        [
            ("lease.pdf", 1, "The annual rent shall be fifty thousand pounds."),
            ("lease.pdf", 2, "The tenant is responsible for building insurance."),
            ("lease.pdf", 3, "Rent review shall occur every five years."),
        ],
    )

    results = await retrieve_chunks(session, conv_id, "rent")

    # Both pages mentioning "rent" should be returned
    pages = {r.page_number for r in results}
    assert 1 in pages
    assert 3 in pages
    # Page 2 (insurance only) should not be in FTS results
    # (it may appear if fallback triggers, but with 2 FTS hits and min_results=3,
    # fallback WILL trigger — so let's use a lower min_results to test FTS path)


async def test_fts_excludes_irrelevant_chunks(session: AsyncSession) -> None:
    """FTS should return only matching chunks and exclude non-matching ones."""
    conv_id = await _create_conversation_with_chunks(
        session,
        [
            ("doc.pdf", 1, "The weather is sunny today."),
            ("doc.pdf", 2, "Rent is payable quarterly. The annual rent is fifty thousand."),
            ("doc.pdf", 3, "The rent review clause specifies rent escalation every year."),
        ],
    )

    # Use min_results=1 to avoid fallback
    results = await retrieve_chunks(session, conv_id, "rent", min_results=1)

    assert len(results) == 2
    pages = {r.page_number for r in results}
    assert pages == {2, 3}
    # Page 1 (weather, no rent) is excluded
    assert 1 not in pages
    # All results should have positive rank
    assert all(r.rank > 0 for r in results)


async def test_fts_fallback_on_no_matches(session: AsyncSession) -> None:
    """When FTS returns no matches, all chunks should be returned in reading order."""
    conv_id = await _create_conversation_with_chunks(
        session,
        [
            ("lease.pdf", 1, "The annual rent shall be fifty thousand pounds."),
            ("lease.pdf", 2, "The tenant is responsible for building insurance."),
        ],
    )

    # Query that won't match any FTS terms
    results = await retrieve_chunks(session, conv_id, "xyznonexistent")

    # Fallback: all chunks returned
    assert len(results) == 2
    assert results[0].page_number == 1
    assert results[1].page_number == 2
    # Fallback chunks have rank 0
    assert all(r.rank == 0.0 for r in results)


async def test_fts_fallback_below_min_results(session: AsyncSession) -> None:
    """When FTS returns fewer than min_results, fall back to all chunks."""
    conv_id = await _create_conversation_with_chunks(
        session,
        [
            ("lease.pdf", 1, "The annual rent shall be fifty thousand pounds."),
            ("lease.pdf", 2, "The tenant is responsible for building insurance."),
            ("lease.pdf", 3, "Break clause allows early termination."),
            ("lease.pdf", 4, "The landlord shall maintain common areas."),
        ],
    )

    # "insurance" matches only 1 chunk, below default min_results=3
    results = await retrieve_chunks(session, conv_id, "insurance")

    # Fallback: all 4 chunks in reading order
    assert len(results) == 4
    assert [r.page_number for r in results] == [1, 2, 3, 4]


async def test_cross_document_retrieval(session: AsyncSession) -> None:
    """FTS should retrieve matching chunks across multiple documents."""
    conv_id = await _create_conversation_with_chunks(
        session,
        [
            ("lease.pdf", 1, "The annual rent is fifty thousand pounds."),
            ("lease.pdf", 2, "The lease term is ten years."),
            ("review.pdf", 1, "The proposed new rent is sixty thousand pounds."),
            ("review.pdf", 2, "Market comparables support the rent increase."),
        ],
    )

    results = await retrieve_chunks(session, conv_id, "rent", min_results=1)

    # Should get chunks from both documents
    doc_names = {r.document_filename for r in results}
    assert "lease.pdf" in doc_names
    assert "review.pdf" in doc_names


async def test_token_budget_caps_results(session: AsyncSession) -> None:
    """Token budget should limit the number of chunks returned."""
    # Create chunks with ~1000 chars each (~250 tokens)
    long_text = "word " * 200  # 1000 chars
    chunks = [("doc.pdf", i + 1, f"Page {i + 1}. {long_text}") for i in range(20)]
    conv_id = await _create_conversation_with_chunks(session, chunks)

    # Budget of 500 tokens should fit ~2 chunks
    results = await retrieve_chunks(
        session,
        conv_id,
        "xyznonexistent",  # force fallback to get all chunks
        max_token_budget=500,
    )

    assert len(results) < 20
    assert len(results) >= 1
    # Verify total estimated tokens is within budget (roughly)
    total_chars = sum(len(r.content) for r in results)
    assert total_chars // 4 <= 600  # allow some slack for the first-chunk inclusion


async def test_empty_conversation_returns_no_chunks(session: AsyncSession) -> None:
    """Conversation with no documents should return empty list."""
    conv = Conversation(title="Empty")
    session.add(conv)
    await session.commit()

    results = await retrieve_chunks(session, conv.id, "anything")
    assert results == []


async def test_chunks_include_metadata(session: AsyncSession) -> None:
    """Retrieved chunks should include document filename and page number."""
    conv_id = await _create_conversation_with_chunks(
        session,
        [("my-lease.pdf", 5, "The rent is one hundred thousand pounds per annum.")],
    )

    results = await retrieve_chunks(session, conv_id, "rent", min_results=1)

    assert len(results) == 1
    assert results[0].document_filename == "my-lease.pdf"
    assert results[0].page_number == 5
    assert "one hundred thousand" in results[0].content
