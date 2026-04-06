from __future__ import annotations

import io

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
