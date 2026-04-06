from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from alembic import command
from takehome.config import settings

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Ensure the Anthropic API key is available as an environment variable
    # so that pydantic-ai's Anthropic integration can pick it up.
    if settings.anthropic_api_key:
        os.environ.setdefault("ANTHROPIC_API_KEY", settings.anthropic_api_key)

    logger.info("Running database migrations...")
    alembic_cfg = Config("alembic.ini")
    # Run in a thread because alembic's env.py uses asyncio.run(),
    # which cannot nest inside the already-running event loop.
    await asyncio.to_thread(command.upgrade, alembic_cfg, "head")
    logger.info("Migrations complete")
    yield


app = FastAPI(title="Orbital Document Q&A", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from takehome.web.routers import conversations, documents, messages  # noqa: E402

app.include_router(conversations.router)
app.include_router(messages.router)
app.include_router(documents.router)
