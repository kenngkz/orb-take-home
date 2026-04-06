"""add pgvector embedding column to document_chunks

Revision ID: b7e2f4a11c03
Revises: a3f1c9d00e21
Create Date: 2026-04-06 21:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b7e2f4a11c03"
down_revision: str | None = "a3f1c9d00e21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("ALTER TABLE document_chunks ADD COLUMN embedding vector(384)")
    op.execute(
        "CREATE INDEX idx_chunks_embedding ON document_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_chunks_embedding")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding")
