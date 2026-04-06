"""add FK indexes on messages.conversation_id and documents.conversation_id

Revision ID: c5a8d3e19f47
Revises: b7e2f4a11c03
Create Date: 2026-04-06 23:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c5a8d3e19f47"
down_revision: str | None = "b7e2f4a11c03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        op.f("ix_messages_conversation_id"), "messages", ["conversation_id"], unique=False
    )
    op.create_index(
        op.f("ix_documents_conversation_id"), "documents", ["conversation_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_documents_conversation_id"), table_name="documents")
    op.drop_index(op.f("ix_messages_conversation_id"), table_name="messages")
