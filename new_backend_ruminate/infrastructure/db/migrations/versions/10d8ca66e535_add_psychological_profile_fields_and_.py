"""add psychological profile fields and daily checkins table

Revision ID: 10d8ca66e535
Revises: 89cb17873dbd
Create Date: 2025-08-06 16:23:07.994372

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '10d8ca66e535'
down_revision: Union[str, None] = '89cb17873dbd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create daily_checkins table
    op.create_table(
        'daily_checkins',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('checkin_text', sa.Text(), nullable=False),
        sa.Column('mood_scores', sa.JSON(), nullable=True),
        sa.Column('insight_text', sa.Text(), nullable=True),
        sa.Column('insight_status', sa.String(length=20), nullable=False),
        sa.Column('insight_generated_at', sa.DateTime(), nullable=True),
        sa.Column('insight_type', sa.String(length=50), nullable=False),
        sa.Column('insight_version', sa.Integer(), nullable=False),
        sa.Column('context_metadata', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_daily_checkins_created_at'), 'daily_checkins', ['created_at'], unique=False)
    op.create_index(op.f('ix_daily_checkins_user_id'), 'daily_checkins', ['user_id'], unique=False)
    
    # Add psychological profile fields to user_preferences
    op.add_column('user_preferences', sa.Column('horoscope_data', sa.JSON(), nullable=True))
    op.add_column('user_preferences', sa.Column('mbti_type', sa.String(length=4), nullable=True))
    op.add_column('user_preferences', sa.Column('ocean_scores', sa.JSON(), nullable=True))


def downgrade() -> None:
    # Remove psychological profile fields from user_preferences
    op.drop_column('user_preferences', 'ocean_scores')
    op.drop_column('user_preferences', 'mbti_type')
    op.drop_column('user_preferences', 'horoscope_data')
    
    # Drop daily_checkins table
    op.drop_index(op.f('ix_daily_checkins_user_id'), table_name='daily_checkins')
    op.drop_index(op.f('ix_daily_checkins_created_at'), table_name='daily_checkins')
    op.drop_table('daily_checkins')
