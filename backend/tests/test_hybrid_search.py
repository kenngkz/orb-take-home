from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from takehome.db.models import Conversation, Document, DocumentChunk
from takehome.services.embedding import embed_query, embed_texts
from takehome.services.retrieval import ChunkResult, retrieve_chunks, rrf_merge

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _chunk(doc_id: str, page: int, content: str, rank: float = 0.0) -> ChunkResult:
    """Build a ChunkResult for unit tests (no DB needed)."""
    return ChunkResult(
        document_id=doc_id,
        document_filename="test.pdf",
        page_number=page,
        content=content,
        rank=rank,
    )


async def _create_conversation_with_embedded_chunks(
    session: AsyncSession,
    chunks: list[tuple[str, int, str]],
) -> str:
    """Create a conversation with document chunks that have real embeddings.

    Each chunk tuple is (filename, page_number, content).
    Returns the conversation ID.
    """
    conv = Conversation(title="Test")
    session.add(conv)
    await session.flush()

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

    texts = [content for _, _, content in chunks]
    embeddings = await asyncio.to_thread(embed_texts, texts)

    for (fname, page_num, content), embedding in zip(chunks, embeddings, strict=True):
        chunk = DocumentChunk(
            document_id=doc_map[fname].id,
            page_number=page_num,
            content=content,
            embedding=embedding,
        )
        session.add(chunk)

    await session.commit()
    return conv.id


# ---------------------------------------------------------------------------
# 1. Unit tests for rrf_merge (pure function, no DB)
# ---------------------------------------------------------------------------


class TestRrfMerge:
    def test_overlapping_lists_rank_shared_items_higher(self) -> None:
        """Items appearing in both lists should score higher than items in one."""
        list_a = [
            _chunk("d1", 1, "shared item"),
            _chunk("d1", 2, "only in A"),
        ]
        list_b = [
            _chunk("d1", 3, "only in B"),
            _chunk("d1", 1, "shared item"),
        ]

        merged = rrf_merge(list_a, list_b)

        keys = [(r.document_id, r.page_number) for r in merged]
        # Shared item (d1, 1) appears in both lists so gets 2 RRF contributions
        assert keys[0] == ("d1", 1)
        # It should have a higher score than items appearing in only one list
        assert merged[0].rank > merged[1].rank
        assert merged[0].rank > merged[2].rank

    def test_disjoint_lists_all_items_present(self) -> None:
        """Two completely disjoint lists should produce a merged list with all items."""
        list_a = [
            _chunk("d1", 1, "A first"),
            _chunk("d1", 2, "A second"),
        ]
        list_b = [
            _chunk("d2", 1, "B first"),
            _chunk("d2", 2, "B second"),
        ]

        merged = rrf_merge(list_a, list_b)

        assert len(merged) == 4
        keys = {(r.document_id, r.page_number) for r in merged}
        assert keys == {("d1", 1), ("d1", 2), ("d2", 1), ("d2", 2)}
        # First-ranked items from each list tie in score (both at position 0)
        # so they should both rank above second-ranked items
        top_two_keys = {(merged[0].document_id, merged[0].page_number),
                        (merged[1].document_id, merged[1].page_number)}
        assert ("d1", 1) in top_two_keys
        assert ("d2", 1) in top_two_keys

    def test_single_list_passthrough(self) -> None:
        """A single list should preserve its original order."""
        items = [
            _chunk("d1", 1, "first"),
            _chunk("d1", 2, "second"),
            _chunk("d1", 3, "third"),
        ]

        merged = rrf_merge(items)

        assert len(merged) == 3
        assert [r.page_number for r in merged] == [1, 2, 3]

    def test_empty_lists_return_empty(self) -> None:
        """Empty input lists should produce an empty result."""
        merged = rrf_merge([], [])
        assert merged == []

        merged_single = rrf_merge([])
        assert merged_single == []

    def test_same_item_different_positions_correct_score(self) -> None:
        """An item at different positions in each list gets the correct RRF score."""
        k = 60  # default RRF constant

        # Item (d1, 1) is at position 0 in list_a and position 2 in list_b
        list_a = [
            _chunk("d1", 1, "target"),
            _chunk("d1", 2, "filler a"),
        ]
        list_b = [
            _chunk("d1", 3, "filler b1"),
            _chunk("d1", 4, "filler b2"),
            _chunk("d1", 1, "target"),
        ]

        merged = rrf_merge(list_a, list_b)

        target = next(r for r in merged if r.page_number == 1 and r.document_id == "d1")
        expected_score = 1.0 / (k + 0 + 1) + 1.0 / (k + 2 + 1)
        assert abs(target.rank - expected_score) < 1e-9


# ---------------------------------------------------------------------------
# 2. Embedding pipeline tests
# ---------------------------------------------------------------------------


class TestEmbeddingPipeline:
    def test_embed_single_text(self) -> None:
        """embed_texts with a single string returns one vector of 384 floats."""
        vectors = embed_texts(["hello world"])

        assert len(vectors) == 1
        assert len(vectors[0]) == 384
        assert all(isinstance(v, float) for v in vectors[0])

    def test_embed_query_returns_384_floats(self) -> None:
        """embed_query returns a single list of 384 floats."""
        vector = embed_query("test query")

        assert len(vector) == 384
        assert all(isinstance(v, float) for v in vector)

    def test_embed_batch(self) -> None:
        """embed_texts with multiple strings returns the correct number of vectors."""
        vectors = embed_texts(["a", "b", "c"])

        assert len(vectors) == 3
        for vec in vectors:
            assert len(vec) == 384


# ---------------------------------------------------------------------------
# 3. Vector search integration tests (DB + real embeddings)
# ---------------------------------------------------------------------------


class TestVectorSearch:
    async def test_semantic_similarity_ranking(self, session: AsyncSession) -> None:
        """Semantically similar chunks should rank higher in vector search."""
        conv_id = await _create_conversation_with_embedded_chunks(
            session,
            [
                ("lease.pdf", 1, "The tenant must pay annual rent of fifty thousand pounds."),
                ("lease.pdf", 2, "The building has a car park with twenty spaces."),
                ("lease.pdf", 3, "Quarterly rent payments are due on the usual quarter days."),
            ],
        )

        results = await retrieve_chunks(
            session, conv_id, "how much is the rent", min_results=1
        )

        # Rent-related chunks (pages 1 and 3) should rank above the car park chunk
        top_two_pages = {r.page_number for r in results[:2]}
        assert 1 in top_two_pages
        assert 3 in top_two_pages

    async def test_vector_search_finds_semantic_match_without_keyword_overlap(
        self, session: AsyncSession
    ) -> None:
        """Vector search should find 'break clause' when querying 'termination',
        even though the keyword doesn't appear in the chunk text.
        This is the core value proposition of adding embeddings.
        """
        conv_id = await _create_conversation_with_embedded_chunks(
            session,
            [
                (
                    "lease.pdf",
                    1,
                    "The break clause permits the tenant to end the lease after "
                    "the third year by giving six months' written notice.",
                ),
                (
                    "lease.pdf",
                    2,
                    "The building has central heating and air conditioning "
                    "maintained by the landlord.",
                ),
                (
                    "lease.pdf",
                    3,
                    "Car parking spaces are allocated on a first-come "
                    "first-served basis.",
                ),
            ],
        )

        results = await retrieve_chunks(
            session, conv_id, "termination", min_results=1
        )

        # The break clause chunk (page 1) should be in results even though
        # the word "termination" never appears in its text
        pages = {r.page_number for r in results}
        assert 1 in pages, (
            "Vector search should find the break clause chunk via semantic "
            "similarity to 'termination'"
        )

        # It should rank above the irrelevant chunks
        page_ranks = {r.page_number: r.rank for r in results}
        assert page_ranks[1] > page_ranks.get(2, 0.0)
        assert page_ranks[1] > page_ranks.get(3, 0.0)


# ---------------------------------------------------------------------------
# 4. Hybrid retrieval integration test
# ---------------------------------------------------------------------------


class TestHybridRetrieval:
    async def test_hybrid_merges_fts_and_vector_results(
        self, session: AsyncSession
    ) -> None:
        """Hybrid retrieval should include chunks found by FTS AND chunks
        found by vector similarity, even when they don't overlap."""
        conv_id = await _create_conversation_with_embedded_chunks(
            session,
            [
                # FTS will match "rent" keyword
                (
                    "lease.pdf",
                    1,
                    "The annual rent is fifty thousand pounds payable quarterly.",
                ),
                # Vector search should find this via semantic similarity to "rent"
                # even though it doesn't contain the exact word "rent"
                (
                    "lease.pdf",
                    2,
                    "The financial obligations of the lessee include periodic "
                    "monetary payments to the lessor as consideration for "
                    "occupation of the premises.",
                ),
                # Irrelevant chunk
                (
                    "lease.pdf",
                    3,
                    "The car park has twenty allocated spaces for tenant use.",
                ),
            ],
        )

        results = await retrieve_chunks(
            session, conv_id, "rent", min_results=1
        )

        pages = {r.page_number for r in results}
        # Page 1 should definitely be found (FTS keyword match on "rent")
        assert 1 in pages
        # Page 2 should ideally be found via vector similarity (semantic match)
        # but we assert it's at least in the results
        assert 2 in pages
