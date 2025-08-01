"""add_image_generation_fields_to_dreams

Revision ID: 2c31c58121a2
Revises: 12bc4414d04e
Create Date: 2025-07-31 16:03:19.422623

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2c31c58121a2'
down_revision: Union[str, None] = '12bc4414d04e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add image generation fields to dreams table
    op.add_column('dreams', sa.Column('image_url', sa.String(500), nullable=True))
    op.add_column('dreams', sa.Column('image_prompt', sa.Text(), nullable=True))
    op.add_column('dreams', sa.Column('image_generated_at', sa.DateTime(), nullable=True))
    op.add_column('dreams', sa.Column('image_status', sa.String(20), nullable=True))
    op.add_column('dreams', sa.Column('image_metadata', sa.JSON(), nullable=True))


def downgrade() -> None:
    # Remove image generation fields from dreams table
    op.drop_column('dreams', 'image_metadata')
    op.drop_column('dreams', 'image_status')
    op.drop_column('dreams', 'image_generated_at')
    op.drop_column('dreams', 'image_prompt')
    op.drop_column('dreams', 'image_url')
