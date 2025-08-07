"""merge migration heads for psych profile

Revision ID: 89cb17873dbd
Revises: add_image_s3_key, d2a58c506d02
Create Date: 2025-08-06 16:23:01.328338

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '89cb17873dbd'
down_revision: Union[str, None] = ('add_image_s3_key', 'd2a58c506d02')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
