from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from takehome.db.models import Conversation


async def test_create_conversation(client: AsyncClient) -> None:
    resp = await client.post("/api/conversations")
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["title"] == "New Conversation"


async def test_list_conversations(client: AsyncClient) -> None:
    await client.post("/api/conversations")
    await client.post("/api/conversations")

    resp = await client.get("/api/conversations")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_get_conversation(client: AsyncClient) -> None:
    created = (await client.post("/api/conversations")).json()

    resp = await client.get(f"/api/conversations/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


async def test_delete_conversation(client: AsyncClient, session: AsyncSession) -> None:
    created = (await client.post("/api/conversations")).json()

    resp = await client.delete(f"/api/conversations/{created['id']}")
    assert resp.status_code == 204

    row = await session.get(Conversation, created["id"])
    assert row is None


async def test_conversation_fixture(conversation: Conversation) -> None:
    assert conversation.id is not None
    assert conversation.title == "Test Conversation"
