"""change embedding dimension to 384

Revision ID: 9674b80d3794
Revises: 96b41769705c
Create Date: 2026-03-17 13:45:54.899932

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '9674b80d3794'
down_revision: Union[str, None] = '96b41769705c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE outputs DROP COLUMN embedding")
    op.execute("ALTER TABLE outputs ADD COLUMN embedding vector(384)")


def downgrade() -> None:
    op.execute("ALTER TABLE outputs DROP COLUMN embedding")
    op.execute("ALTER TABLE outputs ADD COLUMN embedding vector(1536)")
