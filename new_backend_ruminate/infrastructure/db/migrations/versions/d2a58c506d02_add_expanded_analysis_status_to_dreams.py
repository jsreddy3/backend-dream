"""add_expanded_analysis_status_to_dreams

Revision ID: d2a58c506d02
Revises: 2c31c58121a2
Create Date: 2025-08-05 19:10:28.107517

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2a58c506d02'
down_revision: Union[str, None] = '2c31c58121a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add expanded_analysis_status column to dreams table
    op.add_column('dreams', sa.Column('expanded_analysis_status', sa.String(20), nullable=True))


def downgrade() -> None:
    # Remove expanded_analysis_status column from dreams table  
    op.drop_column('dreams', 'expanded_analysis_status')
