"""add_video_fields_to_dream

Revision ID: 6c4c4edd8d65
Revises: 5b732fce715c
Create Date: 2025-06-24 17:53:55.965745

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6c4c4edd8d65'
down_revision: Union[str, None] = '5b732fce715c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add video-related columns to dreams table
    op.add_column('dreams', sa.Column('video_job_id', sa.String(255), nullable=True))
    op.add_column('dreams', sa.Column('video_status', sa.String(20), nullable=True))
    op.add_column('dreams', sa.Column('video_url', sa.String(500), nullable=True))
    op.add_column('dreams', sa.Column('video_metadata', sa.JSON(), nullable=True))
    op.add_column('dreams', sa.Column('video_started_at', sa.DateTime(), nullable=True))
    op.add_column('dreams', sa.Column('video_completed_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    # Remove video-related columns from dreams table
    op.drop_column('dreams', 'video_completed_at')
    op.drop_column('dreams', 'video_started_at')
    op.drop_column('dreams', 'video_metadata')
    op.drop_column('dreams', 'video_url')
    op.drop_column('dreams', 'video_status')
    op.drop_column('dreams', 'video_job_id')
