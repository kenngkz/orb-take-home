"""add citations column to messages

Revision ID: 8f8aa574b3d7
Revises: c5a8d3e19f47
Create Date: 2026-04-06 18:40:08.842998

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '8f8aa574b3d7'
down_revision: str | None = 'c5a8d3e19f47'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('messages', sa.Column('citations', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('messages', 'citations')
