"""add_summary_status_to_dreams

Revision ID: e19af9718abf
Revises: 834823ff4679
Create Date: 2025-07-04 15:52:19.496125

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e19af9718abf'
down_revision: Union[str, None] = '834823ff4679'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add summary_status column
    op.add_column('dreams', sa.Column('summary_status', sa.String(length=20), nullable=True))


def downgrade() -> None:
    # Remove summary_status column
    op.drop_column('dreams', 'summary_status')
