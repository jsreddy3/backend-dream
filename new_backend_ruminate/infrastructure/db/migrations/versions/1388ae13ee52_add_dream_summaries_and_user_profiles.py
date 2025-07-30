"""add_dream_summaries_and_user_profiles

Revision ID: 1388ae13ee52
Revises: cdbbcaea639a
Create Date: 2025-07-29 12:11:40.281009

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision: str = '1388ae13ee52'
down_revision: Union[str, None] = 'cdbbcaea639a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create dream_summaries table for incremental statistics
    op.create_table(
        'dream_summaries',
        sa.Column('id', UUID, primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID, nullable=False),
        sa.Column('dream_count', sa.Integer, default=0, nullable=False),
        sa.Column('total_duration_seconds', sa.Integer, default=0, nullable=False),
        sa.Column('last_dream_date', sa.Date, nullable=True),
        sa.Column('dream_streak_days', sa.Integer, default=0, nullable=False),
        sa.Column('theme_keywords', JSONB, server_default='{}', nullable=False),
        sa.Column('emotion_counts', JSONB, server_default='{}', nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP, server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP, server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    
    # Add unique constraint and index on user_id
    op.create_unique_constraint('uq_dream_summaries_user_id', 'dream_summaries', ['user_id'])
    op.create_index('idx_dream_summaries_user_id', 'dream_summaries', ['user_id'])
    
    # Create user_profiles table for computed profile data
    op.create_table(
        'user_profiles',
        sa.Column('id', UUID, primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID, nullable=False),
        sa.Column('archetype', sa.String(50), nullable=True),
        sa.Column('archetype_confidence', sa.Float, nullable=True),
        sa.Column('archetype_metadata', JSONB, server_default='{}', nullable=False),
        sa.Column('emotional_landscape', JSONB, server_default='[]', nullable=False),
        sa.Column('top_themes', JSONB, server_default='[]', nullable=False),
        sa.Column('recent_symbols', JSONB, server_default='[]', nullable=False),
        sa.Column('calculation_version', sa.Integer, default=1, nullable=False),
        sa.Column('last_calculated_at', sa.TIMESTAMP, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP, server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP, server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    
    # Add constraints and indexes
    op.create_unique_constraint('uq_user_profiles_user_id', 'user_profiles', ['user_id'])
    op.create_index('idx_user_profiles_user_id', 'user_profiles', ['user_id'])
    op.create_check_constraint(
        'ck_archetype_confidence_range',
        'user_profiles',
        'archetype_confidence >= 0 AND archetype_confidence <= 1'
    )
    
    # Add foreign key constraints
    op.create_foreign_key(
        'fk_dream_summaries_user_id',
        'dream_summaries',
        'users',
        ['user_id'],
        ['id'],
        ondelete='CASCADE'
    )
    
    op.create_foreign_key(
        'fk_user_profiles_user_id',
        'user_profiles',
        'users',
        ['user_id'],
        ['id'],
        ondelete='CASCADE'
    )
    
    # Create a trigger to update the updated_at timestamp
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql'
    """)
    
    op.execute("""
        CREATE TRIGGER update_dream_summaries_updated_at BEFORE UPDATE
        ON dream_summaries FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
    """)
    
    op.execute("""
        CREATE TRIGGER update_user_profiles_updated_at BEFORE UPDATE
        ON user_profiles FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
    """)


def downgrade() -> None:
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS update_dream_summaries_updated_at ON dream_summaries")
    op.execute("DROP TRIGGER IF EXISTS update_user_profiles_updated_at ON user_profiles")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column")
    
    # Drop foreign keys
    op.drop_constraint('fk_user_profiles_user_id', 'user_profiles', type_='foreignkey')
    op.drop_constraint('fk_dream_summaries_user_id', 'dream_summaries', type_='foreignkey')
    
    # Drop tables
    op.drop_table('user_profiles')
    op.drop_table('dream_summaries')
