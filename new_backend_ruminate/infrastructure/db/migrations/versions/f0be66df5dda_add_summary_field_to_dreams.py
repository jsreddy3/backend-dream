"""add_summary_field_to_dreams

Revision ID: f0be66df5dda
Revises: 7d8f9e1a2b3c
Create Date: 2025-07-04 09:15:27.199300

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f0be66df5dda'
down_revision: Union[str, None] = '7d8f9e1a2b3c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add summary column to dreams table
    op.add_column('dreams', sa.Column('summary', sa.Text(), nullable=True))


def downgrade() -> None:
    # Remove summary column from dreams table
    op.drop_column('dreams', 'summary')
