"""add_questions_and_analysis_status_fields

Revision ID: 5e5e5ad480ea
Revises: e19af9718abf
Create Date: 2025-07-04 16:22:30.650961

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5e5e5ad480ea'
down_revision: Union[str, None] = 'e19af9718abf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add questions_status column
    op.add_column('dreams', sa.Column('questions_status', sa.String(length=20), nullable=True))
    # Add analysis_status column
    op.add_column('dreams', sa.Column('analysis_status', sa.String(length=20), nullable=True))


def downgrade() -> None:
    # Remove analysis_status column
    op.drop_column('dreams', 'analysis_status')
    # Remove questions_status column
    op.drop_column('dreams', 'questions_status')
