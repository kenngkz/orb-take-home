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


async def retrieve_chunks(
    session: AsyncSession,
    conversation_id: str,
    query: str,
    *,
    top_k: int = 20,
    min_results: int = 3,
    max_token_budget: int = 80_000,
) -> list[ChunkResult]:
    """Retrieve relevant chunks for a query using PostgreSQL full-text search.

    Strategy:
    1. Run FTS ranked search scoped to the conversation.
    2. If FTS returns >= min_results, use those (top-k by rank).
    3. Otherwise fall back to ALL chunks in reading order (broad queries,
       summarisation requests, etc.).
    4. In both paths, enforce a token budget so we never blow the context window.
    """
    ts_query = func.plainto_tsquery("english", query)
    ts_vector = func.to_tsvector("english", DocumentChunk.content)

    # --- FTS ranked search ---
    fts_stmt = (
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

    result = await session.execute(fts_stmt)
    fts_rows = result.all()

    if len(fts_rows) >= min_results:
        chunks = [
            ChunkResult(
                document_id=row.document_id,
                document_filename=row.filename,
                page_number=row.page_number,
                content=row.content,
                rank=float(row.rank),
            )
            for row in fts_rows
        ]
        logger.info(
            "FTS retrieval",
            conversation_id=conversation_id,
            query=query[:80],
            results=len(chunks),
        )
    else:
        # --- Fallback: all chunks in reading order ---
        fallback_stmt = (
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
        fallback_result = await session.execute(fallback_stmt)
        fallback_rows = fallback_result.all()
        chunks = [
            ChunkResult(
                document_id=row.document_id,
                document_filename=row.filename,
                page_number=row.page_number,
                content=row.content,
                rank=0.0,
            )
            for row in fallback_rows
        ]
        logger.info(
            "FTS fallback to full context",
            conversation_id=conversation_id,
            query=query[:80],
            fts_hits=len(fts_rows),
            total_chunks=len(chunks),
        )

    # --- Apply token budget ---
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
