from __future__ import annotations

import io

import fitz  # PyMuPDF
from httpx import AsyncClient

from takehome.db.models import Conversation


def make_test_pdf() -> io.BytesIO:
    """Create a minimal valid PDF in memory."""
    pdf_bytes = (
        b"%PDF-1.0\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        b"xref\n0 4\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\n"
        b"startxref\n190\n%%EOF"
    )
    return io.BytesIO(pdf_bytes)


def make_multi_page_pdf(pages: list[str]) -> io.BytesIO:
    """Create a PDF with text content on each page using PyMuPDF."""
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text)  # type: ignore[union-attr]
    buf = io.BytesIO(doc.tobytes())
    doc.close()
    return buf


async def test_upload_document(client: AsyncClient, conversation: Conversation) -> None:
    resp = await client.post(
        f"/api/conversations/{conversation.id}/documents",
        files={"file": ("test.pdf", make_test_pdf(), "application/pdf")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["filename"] == "test.pdf"
    assert "page_count" in data


async def test_upload_multiple_documents(
    client: AsyncClient, conversation: Conversation
) -> None:
    resp1 = await client.post(
        f"/api/conversations/{conversation.id}/documents",
        files={"file": ("test.pdf", make_test_pdf(), "application/pdf")},
    )
    assert resp1.status_code == 201

    resp2 = await client.post(
        f"/api/conversations/{conversation.id}/documents",
        files={"file": ("test2.pdf", make_test_pdf(), "application/pdf")},
    )
    assert resp2.status_code == 201

    doc1 = resp1.json()
    doc2 = resp2.json()
    assert doc1["id"] != doc2["id"]
    assert doc1["filename"] == "test.pdf"
    assert doc2["filename"] == "test2.pdf"


async def test_list_documents(client: AsyncClient, conversation: Conversation) -> None:
    await client.post(
        f"/api/conversations/{conversation.id}/documents",
        files={"file": ("test.pdf", make_test_pdf(), "application/pdf")},
    )
    await client.post(
        f"/api/conversations/{conversation.id}/documents",
        files={"file": ("test2.pdf", make_test_pdf(), "application/pdf")},
    )

    resp = await client.get(f"/api/conversations/{conversation.id}/documents")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


async def test_delete_document(client: AsyncClient, conversation: Conversation) -> None:
    upload_resp = await client.post(
        f"/api/conversations/{conversation.id}/documents",
        files={"file": ("test.pdf", make_test_pdf(), "application/pdf")},
    )
    doc_id = upload_resp.json()["id"]

    delete_resp = await client.delete(f"/api/documents/{doc_id}")
    assert delete_resp.status_code == 204

    list_resp = await client.get(f"/api/conversations/{conversation.id}/documents")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 0


async def test_delete_nonexistent_document(client: AsyncClient) -> None:
    resp = await client.delete("/api/documents/nonexistent_id_12345")
    assert resp.status_code == 404


async def test_conversation_detail_includes_documents(
    client: AsyncClient, conversation: Conversation
) -> None:
    await client.post(
        f"/api/conversations/{conversation.id}/documents",
        files={"file": ("test.pdf", make_test_pdf(), "application/pdf")},
    )
    await client.post(
        f"/api/conversations/{conversation.id}/documents",
        files={"file": ("test2.pdf", make_test_pdf(), "application/pdf")},
    )

    resp = await client.get(f"/api/conversations/{conversation.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_document"] is True
    assert isinstance(data["documents"], list)
    assert len(data["documents"]) == 2


async def test_conversation_detail_no_documents(client: AsyncClient) -> None:
    created = (await client.post("/api/conversations")).json()

    resp = await client.get(f"/api/conversations/{created['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_document"] is False
    assert isinstance(data["documents"], list)
    assert len(data["documents"]) == 0


# --- Chunking tests ---


async def test_upload_creates_chunks(client: AsyncClient, conversation: Conversation) -> None:
    pdf = make_multi_page_pdf(["Page one content", "Page two content", "Page three content"])
    resp = await client.post(
        f"/api/conversations/{conversation.id}/documents",
        files={"file": ("test.pdf", pdf, "application/pdf")},
    )
    assert resp.status_code == 201
    doc_id = resp.json()["id"]

    chunks_resp = await client.get(f"/api/documents/{doc_id}/chunks")
    assert chunks_resp.status_code == 200
    chunks = chunks_resp.json()
    assert len(chunks) == 3
    assert chunks[0]["page_number"] == 1
    assert chunks[1]["page_number"] == 2
    assert chunks[2]["page_number"] == 3
    assert "Page one content" in chunks[0]["content"]
    assert "Page two content" in chunks[1]["content"]
    assert "Page three content" in chunks[2]["content"]


async def test_chunks_deleted_with_document(
    client: AsyncClient, conversation: Conversation
) -> None:
    pdf = make_multi_page_pdf(["Some text"])
    resp = await client.post(
        f"/api/conversations/{conversation.id}/documents",
        files={"file": ("test.pdf", pdf, "application/pdf")},
    )
    doc_id = resp.json()["id"]

    # Verify chunks exist
    chunks_resp = await client.get(f"/api/documents/{doc_id}/chunks")
    assert len(chunks_resp.json()) == 1

    # Delete doc — chunks should cascade
    await client.delete(f"/api/documents/{doc_id}")

    chunks_resp = await client.get(f"/api/documents/{doc_id}/chunks")
    assert chunks_resp.status_code == 200
    assert len(chunks_resp.json()) == 0


async def test_empty_page_not_chunked(client: AsyncClient, conversation: Conversation) -> None:
    """Pages with no text content should not create chunks."""
    # Create a PDF with one text page and one blank page
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Has content")  # type: ignore[union-attr]
    doc.new_page()  # blank page
    buf = io.BytesIO(doc.tobytes())
    doc.close()

    resp = await client.post(
        f"/api/conversations/{conversation.id}/documents",
        files={"file": ("test.pdf", buf, "application/pdf")},
    )
    assert resp.status_code == 201
    doc_id = resp.json()["id"]
    assert resp.json()["page_count"] == 2  # 2 pages in PDF

    chunks_resp = await client.get(f"/api/documents/{doc_id}/chunks")
    chunks = chunks_resp.json()
    assert len(chunks) == 1  # only the page with content
    assert chunks[0]["page_number"] == 1
