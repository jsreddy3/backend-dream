"""add_additional_info_to_dreams

Revision ID: 3fc55f8ba128
Revises: d808b78b2967
Create Date: 2025-07-04 12:29:53.506059

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3fc55f8ba128'
down_revision: Union[str, None] = 'd808b78b2967'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add additional_info column to dreams table
    op.add_column('dreams', sa.Column('additional_info', sa.Text(), nullable=True))


def downgrade() -> None:
    # Remove additional_info column from dreams table
    op.drop_column('dreams', 'additional_info')
