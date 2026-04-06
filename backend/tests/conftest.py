from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from takehome.config import settings
from takehome.db.models import Base, Conversation, Document
from takehome.db.session import get_session
from takehome.web.app import app

# NullPool: each connection is created fresh, avoiding pool conflicts between
# test setup and app handlers.
engine = create_async_engine(settings.database_url, poolclass=NullPool)
test_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def setup_db() -> AsyncGenerator[None, None]:
    """Ensure tables exist before each test, truncate after."""
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(text(f"TRUNCATE TABLE {table.name} CASCADE"))


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    """Database session for direct DB operations in tests."""
    async with test_session_factory() as s:
        yield s


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client with overridden DB session."""

    async def _override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with test_session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Factory fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def conversation(session: AsyncSession) -> Conversation:
    """A pre-created conversation."""
    conv = Conversation(title="Test Conversation")
    session.add(conv)
    await session.commit()
    await session.refresh(conv)
    return conv


@pytest.fixture
async def document(session: AsyncSession, conversation: Conversation) -> Document:
    """A pre-created document attached to the conversation fixture."""
    doc = Document(
        conversation_id=conversation.id,
        filename="test.pdf",
        file_path="tests/fixtures/test.pdf",
        extracted_text=(
            "--- Page 1 ---\nThis is a commercial lease for 100 Bishopsgate.\n\n"
            "--- Page 2 ---\nThe tenant shall pay rent of £50,000 per annum."
        ),
        page_count=2,
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)
    return doc
