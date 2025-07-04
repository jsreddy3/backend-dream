"""add transcription status to segments

Revision ID: 7d8f9e1a2b3c
Revises: 2c910be93274
Create Date: 2025-01-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7d8f9e1a2b3c'
down_revision: Union[str, None] = '2c910be93274'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add transcription_status column to segments table
    op.add_column('segments', sa.Column('transcription_status', sa.String(20), nullable=False, server_default='pending'))


def downgrade() -> None:
    # Remove transcription_status column from segments table
    op.drop_column('segments', 'transcription_status')