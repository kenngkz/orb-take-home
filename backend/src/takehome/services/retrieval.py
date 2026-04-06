from __future__ import annotations

from dataclasses import dataclass

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from takehome.db.models import Document, DocumentChunk

logger = structlog.get_logger()


@dataclass
class ChunkResult:
    """A retrieved chunk with its document metadata."""

    document_id: str
    document_filename: str
    page_number: int
    content: str
    rank: float


# ---------------------------------------------------------------------------
# Internal search functions
# ---------------------------------------------------------------------------


async def _fts_search(
    session: AsyncSession,
    conversation_id: str,
    query: str,
    top_k: int,
) -> list[ChunkResult]:
    """Full-text search using PostgreSQL tsvector/tsquery."""
    ts_query = func.plainto_tsquery("english", query)
    ts_vector = func.to_tsvector("english", DocumentChunk.content)

    stmt = (
        select(
            DocumentChunk.document_id,
            Document.filename,
            DocumentChunk.page_number,
            DocumentChunk.content,
            func.ts_rank(ts_vector, ts_query).label("rank"),
        )
        .join(Document)
        .where(Document.conversation_id == conversation_id)
        .where(ts_vector.op("@@")(ts_query))
        .order_by(func.ts_rank(ts_vector, ts_query).desc())
        .limit(top_k)
    )
    result = await session.execute(stmt)
    return [
        ChunkResult(
            document_id=row.document_id,
            document_filename=row.filename,
            page_number=row.page_number,
            content=row.content,
            rank=float(row.rank),
        )
        for row in result.all()
    ]


async def _vector_search(
    session: AsyncSession,
    conversation_id: str,
    query_embedding: list[float],
    top_k: int,
) -> list[ChunkResult]:
    """Cosine similarity search using pgvector."""
    distance = DocumentChunk.embedding.cosine_distance(query_embedding)

    stmt = (
        select(
            DocumentChunk.document_id,
            Document.filename,
            DocumentChunk.page_number,
            DocumentChunk.content,
            distance.label("distance"),
        )
        .join(Document)
        .where(Document.conversation_id == conversation_id)
        .where(DocumentChunk.embedding.isnot(None))
        .order_by(distance)
        .limit(top_k)
    )
    result = await session.execute(stmt)
    return [
        ChunkResult(
            document_id=row.document_id,
            document_filename=row.filename,
            page_number=row.page_number,
            content=row.content,
            rank=1.0 - float(row.distance),  # convert distance to similarity
        )
        for row in result.all()
    ]


async def _all_chunks(
    session: AsyncSession,
    conversation_id: str,
) -> list[ChunkResult]:
    """Return all chunks for a conversation in reading order."""
    stmt = (
        select(
            DocumentChunk.document_id,
            Document.filename,
            DocumentChunk.page_number,
            DocumentChunk.content,
        )
        .join(Document)
        .where(Document.conversation_id == conversation_id)
        .order_by(Document.uploaded_at.asc(), DocumentChunk.page_number.asc())
    )
    result = await session.execute(stmt)
    return [
        ChunkResult(
            document_id=row.document_id,
            document_filename=row.filename,
            page_number=row.page_number,
            content=row.content,
            rank=0.0,
        )
        for row in result.all()
    ]


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion
# ---------------------------------------------------------------------------


def rrf_merge(
    *result_lists: list[ChunkResult],
    k: int = 60,
) -> list[ChunkResult]:
    """Merge multiple ranked lists using Reciprocal Rank Fusion.

    RRF score = Σ 1/(k + rank_position) across all lists.
    Uses rank position (0-indexed), not the score value.
    """
    scores: dict[tuple[str, int], float] = {}
    chunk_map: dict[tuple[str, int], ChunkResult] = {}

    for result_list in result_lists:
        for position, chunk in enumerate(result_list):
            key = (chunk.document_id, chunk.page_number)
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + position + 1)
            if key not in chunk_map:
                chunk_map[key] = chunk

    sorted_keys = sorted(scores, key=lambda x: scores[x], reverse=True)
    return [
        ChunkResult(
            document_id=chunk_map[key].document_id,
            document_filename=chunk_map[key].document_filename,
            page_number=chunk_map[key].page_number,
            content=chunk_map[key].content,
            rank=scores[key],
        )
        for key in sorted_keys
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _apply_token_budget(
    chunks: list[ChunkResult], max_token_budget: int
) -> list[ChunkResult]:
    """Trim chunk list to fit within an estimated token budget."""
    budgeted: list[ChunkResult] = []
    tokens_used = 0
    for chunk in chunks:
        estimated_tokens = len(chunk.content) // 4
        if tokens_used + estimated_tokens > max_token_budget and budgeted:
            break
        budgeted.append(chunk)
        tokens_used += estimated_tokens

    if len(budgeted) < len(chunks):
        logger.info(
            "Token budget cap applied",
            total_chunks=len(chunks),
            included_chunks=len(budgeted),
            estimated_tokens=tokens_used,
        )
    return budgeted


async def retrieve_chunks(
    session: AsyncSession,
    conversation_id: str,
    query: str,
    *,
    top_k: int = 20,
    min_results: int = 3,
    max_token_budget: int = 80_000,
) -> list[ChunkResult]:
    """Retrieve relevant chunks using hybrid search (FTS + vector) with RRF.

    Strategy:
    1. Run FTS keyword search.
    2. Run vector similarity search (if embeddings exist).
    3. Merge results with Reciprocal Rank Fusion.
    4. If combined results < min_results, fall back to all chunks.
    5. Apply token budget.
    """
    # --- FTS search ---
    fts_results = await _fts_search(session, conversation_id, query, top_k)

    # --- Vector search (best-effort) ---
    vector_results: list[ChunkResult] = []
    try:
        from takehome.services.embedding import embed_query

        query_embedding = embed_query(query)
        vector_results = await _vector_search(
            session, conversation_id, query_embedding, top_k
        )
    except Exception:
        logger.debug("Vector search unavailable, using FTS only")

    # --- Merge ---
    if fts_results or vector_results:
        sources = [r for r in [fts_results, vector_results] if r]
        merged = rrf_merge(*sources) if len(sources) > 1 else sources[0]

        if len(merged) >= min_results:
            logger.info(
                "Hybrid retrieval",
                conversation_id=conversation_id,
                query=query[:80],
                fts_hits=len(fts_results),
                vector_hits=len(vector_results),
                merged=len(merged),
            )
            return _apply_token_budget(merged[:top_k], max_token_budget)

    # --- Fallback: all chunks in reading order ---
    all_results = await _all_chunks(session, conversation_id)
    logger.info(
        "Retrieval fallback to full context",
        conversation_id=conversation_id,
        query=query[:80],
        fts_hits=len(fts_results),
        vector_hits=len(vector_results),
        total_chunks=len(all_results),
    )
    return _apply_token_budget(all_results, max_token_budget)
