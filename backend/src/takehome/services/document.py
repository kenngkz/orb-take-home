from __future__ import annotations

import asyncio
import os
import uuid

import fitz  # PyMuPDF
import structlog
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from takehome.config import settings
from takehome.db.models import Document, DocumentChunk
from takehome.services.embedding import embed_texts

logger = structlog.get_logger()

OVERLAP_SENTENCES = 3


def _extract_trailing_sentences(text: str, n: int = OVERLAP_SENTENCES) -> str:
    """Extract the last n sentence fragments from text for cross-page overlap."""
    parts = text.split(". ")
    if len(parts) <= n:
        return text
    trailing = ". ".join(parts[-n:])
    if not trailing.endswith("."):
        trailing += "."
    return trailing


def _add_page_overlap(page_texts: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Prepend trailing context from the previous page to each chunk.

    Captures clauses that span page boundaries while preserving the page number
    attribution for citations. The first page is returned unchanged.
    """
    if len(page_texts) <= 1:
        return page_texts

    result: list[tuple[int, str]] = [page_texts[0]]
    for i in range(1, len(page_texts)):
        prev_content = page_texts[i - 1][1]
        overlap = _extract_trailing_sentences(prev_content)
        page_num, content = page_texts[i]
        result.append((page_num, f"[...continued from previous page] {overlap}\n\n{content}"))
    return result


async def upload_document(
    session: AsyncSession, conversation_id: str, file: UploadFile
) -> Document:
    """Upload and process a PDF document for a conversation.

    Validates the file is a PDF, saves it to disk, extracts text using PyMuPDF,
    and stores metadata in the database.

    Raises ValueError if the file is not a PDF.
    """
    # Validate file type
    if file.content_type not in ("application/pdf", "application/x-pdf"):
        filename = file.filename or ""
        if not filename.lower().endswith(".pdf"):
            raise ValueError("Only PDF files are supported.")

    # Read file content
    content = await file.read()

    # Validate PDF magic bytes
    if not content[:5] == b"%PDF-":
        raise ValueError("File does not appear to be a valid PDF.")

    # Validate file size
    if len(content) > settings.max_upload_size:
        raise ValueError(
            f"File too large. Maximum size is {settings.max_upload_size // (1024 * 1024)}MB."
        )

    # Generate a unique filename to avoid collisions
    original_filename = file.filename or "document.pdf"
    unique_name = f"{uuid.uuid4().hex}.pdf"
    file_path = os.path.join(settings.upload_dir, unique_name)

    # Ensure upload directory exists
    os.makedirs(settings.upload_dir, exist_ok=True)

    # Save the file to disk
    with open(file_path, "wb") as f:
        f.write(content)

    logger.info("Saved uploaded PDF", filename=original_filename, path=file_path, size=len(content))

    # Extract text using PyMuPDF
    page_count = 0
    page_texts: list[tuple[int, str]] = []  # (page_number, text)
    try:
        doc = fitz.open(file_path)
        page_count = len(doc)
        for page_num in range(page_count):
            page = doc[page_num]
            text: str = page.get_text()  # type: ignore[union-attr]
            if text.strip():
                page_texts.append((page_num + 1, text.strip()))
        doc.close()
    except Exception:
        logger.exception("Failed to extract text from PDF", filename=original_filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        raise

    # Add cross-page overlap to capture clauses spanning page boundaries
    page_texts = _add_page_overlap(page_texts)

    logger.info(
        "Extracted text from PDF",
        filename=original_filename,
        page_count=page_count,
        chunk_count=len(page_texts),
    )

    # Create the document record
    try:
        document = Document(
            conversation_id=conversation_id,
            filename=original_filename,
            file_path=file_path,
            extracted_text=None,
            page_count=page_count,
        )
        session.add(document)
        await session.flush()  # get document.id before creating chunks

        # Embed and create per-page chunks
        embeddings: list[list[float]] | None = None
        try:
            embeddings = await asyncio.to_thread(
                embed_texts, [text for _, text in page_texts]
            )
        except Exception:
            logger.warning("Embedding failed, storing chunks without vectors")

        for i, (page_number, page_content) in enumerate(page_texts):
            chunk = DocumentChunk(
                document_id=document.id,
                page_number=page_number,
                content=page_content,
                embedding=embeddings[i] if embeddings else None,
            )
            session.add(chunk)

        await session.commit()
        await session.refresh(document)
    except Exception:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise
    return document


async def get_document(session: AsyncSession, document_id: str) -> Document | None:
    """Get a document by its ID."""
    stmt = select(Document).where(Document.id == document_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_documents_for_conversation(
    session: AsyncSession, conversation_id: str
) -> list[Document]:
    """Get all documents for a conversation, ordered by upload time."""
    stmt = (
        select(Document)
        .where(Document.conversation_id == conversation_id)
        .order_by(Document.uploaded_at.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_chunks_for_document(session: AsyncSession, document_id: str) -> list[DocumentChunk]:
    """Get all chunks for a document, ordered by page number."""
    stmt = (
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.page_number.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_chunks_for_conversation(
    session: AsyncSession, conversation_id: str
) -> list[DocumentChunk]:
    """Get all chunks across all documents in a conversation, ordered by document then page."""
    stmt = (
        select(DocumentChunk)
        .join(Document)
        .where(Document.conversation_id == conversation_id)
        .order_by(Document.uploaded_at.asc(), DocumentChunk.page_number.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def delete_document(session: AsyncSession, document_id: str) -> bool:
    """Delete a document by ID and remove the file from disk.

    Returns True if the document was found and deleted, False otherwise.
    """
    document = await get_document(session, document_id)
    if document is None:
        return False

    if os.path.exists(document.file_path):
        os.remove(document.file_path)
        logger.info("Removed document file from disk", path=document.file_path)

    await session.delete(document)
    await session.commit()
    return True
