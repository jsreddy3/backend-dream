"""merge_heads

Revision ID: 12bc4414d04e
Revises: 32fc74270dd0, f3a2b1c4d5e6
Create Date: 2025-07-31 16:03:14.299934

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '12bc4414d04e'
down_revision: Union[str, None] = ('32fc74270dd0', 'f3a2b1c4d5e6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
