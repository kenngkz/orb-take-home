"""add FTS GIN index on document_chunks

Revision ID: a3f1c9d00e21
Revises: 166481c702d0
Create Date: 2026-04-06 20:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a3f1c9d00e21"
down_revision: str | None = "166481c702d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX idx_chunks_fts ON document_chunks "
        "USING GIN(to_tsvector('english', content))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_chunks_fts")
