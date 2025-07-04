"""add_analysis_fields_to_dreams

Revision ID: 834823ff4679
Revises: 3fc55f8ba128
Create Date: 2025-07-04 12:48:48.570307

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '834823ff4679'
down_revision: Union[str, None] = '3fc55f8ba128'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add analysis fields to dreams table
    op.add_column('dreams', sa.Column('analysis', sa.Text(), nullable=True))
    op.add_column('dreams', sa.Column('analysis_generated_at', sa.DateTime(), nullable=True))
    op.add_column('dreams', sa.Column('analysis_metadata', sa.JSON(), nullable=True))


def downgrade() -> None:
    # Remove analysis fields from dreams table
    op.drop_column('dreams', 'analysis_metadata')
    op.drop_column('dreams', 'analysis_generated_at')
    op.drop_column('dreams', 'analysis')
