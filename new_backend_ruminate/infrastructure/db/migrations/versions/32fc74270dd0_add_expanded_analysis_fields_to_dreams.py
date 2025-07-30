"""add_expanded_analysis_fields_to_dreams

Revision ID: 32fc74270dd0
Revises: a2385c74dc20
Create Date: 2025-07-29 21:14:17.330949

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '32fc74270dd0'
down_revision: Union[str, None] = 'a2385c74dc20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add expanded analysis fields to dreams table
    op.add_column('dreams', sa.Column('expanded_analysis', sa.Text(), nullable=True))
    op.add_column('dreams', sa.Column('expanded_analysis_generated_at', sa.DateTime(), nullable=True))
    op.add_column('dreams', sa.Column('expanded_analysis_metadata', sa.JSON(), nullable=True))


def downgrade() -> None:
    # Remove expanded analysis fields from dreams table
    op.drop_column('dreams', 'expanded_analysis_metadata')
    op.drop_column('dreams', 'expanded_analysis_generated_at')
    op.drop_column('dreams', 'expanded_analysis')
