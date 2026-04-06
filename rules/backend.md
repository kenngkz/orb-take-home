# Backend Patterns

Python 3.12 backend using FastAPI, SQLAlchemy (async), Pydantic, and Pydantic-AI.

## Project Structure

```
backend/src/takehome/
├── config.py              # Settings via pydantic-settings
├── db/
│   ├── models.py          # SQLAlchemy ORM models
│   └── session.py         # Async session factory
├── services/
│   ├── conversation.py    # CRUD operations
│   ├── document.py        # PDF extraction
│   └── llm.py             # Pydantic-AI agent + streaming
└── web/
    ├── app.py             # FastAPI app, CORS, lifespan
    └── routers/           # API route handlers
```

## SQLAlchemy Models

Use SQLAlchemy 2.0+ declarative style with `Mapped[]` type hints:

```python
class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uuid.uuid4().hex[:16])
    title: Mapped[str] = mapped_column(String, default="New Conversation")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
```

## Service Layer

Services are plain async functions that accept an `AsyncSession`:

```python
async def create_conversation(session: AsyncSession) -> Conversation:
    conversation = Conversation()
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation
```

No class-based services, no DI container. FastAPI's `Depends(get_session)` injects the session into routers.

## API Schemas

Pydantic models co-located in router files. Use `model_config = {"from_attributes": True}` for ORM compatibility:

```python
class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    model_config = {"from_attributes": True}
```

## Routers

All routes are prefixed with `/api/`. Routers use `APIRouter(tags=[...])`:

```python
router = APIRouter(tags=["messages"])

@router.get("/api/conversations/{conversation_id}/messages", response_model=list[MessageOut])
async def list_messages(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
) -> list[MessageOut]:
    ...
```

## Streaming

LLM responses stream via SSE (Server-Sent Events). The pattern:

1. Service yields `AsyncIterator[str]` chunks from Pydantic-AI `agent.run_stream()`
2. Router wraps in `StreamingResponse` with `media_type="text/event-stream"`
3. Events are JSON-encoded with `type` field: `"content"`, `"message"`, `"done"`

## Logging

Use structlog throughout:

```python
import structlog
logger = structlog.get_logger()
logger.info("message", key="value")
```

## Migrations

Alembic with autogenerate. Auto-applied on app startup via lifespan handler.

- Create: `just db-migrate "description"`
- Apply: `just db-upgrade`

## Linting & Type Checking

- Ruff: `docker compose exec backend uv run ruff check backend/src`
- Pyright: `docker compose exec backend uv run pyright backend/src` (strict mode)
- Format: `docker compose exec backend uv run ruff format backend/src`

## Testing

pytest with pytest-asyncio (`asyncio_mode = "auto"`). Tests in `backend/tests/`.
Run: `docker compose exec backend uv run pytest`
