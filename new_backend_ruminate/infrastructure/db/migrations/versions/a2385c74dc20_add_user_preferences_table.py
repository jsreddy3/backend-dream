"""add_user_preferences_table

Revision ID: a2385c74dc20
Revises: 1388ae13ee52
Create Date: 2025-07-29 19:31:00.313438

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision: str = 'a2385c74dc20'
down_revision: Union[str, None] = '1388ae13ee52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create user_preferences table
    op.create_table(
        'user_preferences',
        sa.Column('id', UUID, primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID, nullable=False),
        
        # Sleep patterns
        sa.Column('typical_bedtime', sa.Time, nullable=True),
        sa.Column('typical_wake_time', sa.Time, nullable=True),
        sa.Column('sleep_quality', sa.String(20), nullable=True),
        
        # Dream patterns
        sa.Column('dream_recall_frequency', sa.String(20), nullable=True),
        sa.Column('dream_vividness', sa.String(20), nullable=True),
        sa.Column('common_dream_themes', JSONB, server_default='[]', nullable=False),
        
        # Goals & interests
        sa.Column('primary_goal', sa.String(50), nullable=True),
        sa.Column('interests', JSONB, server_default='[]', nullable=False),
        
        # Notifications
        sa.Column('reminder_enabled', sa.Boolean, default=True, nullable=False),
        sa.Column('reminder_time', sa.Time, nullable=True),
        sa.Column('reminder_frequency', sa.String(20), default='daily', nullable=False),
        sa.Column('reminder_days', JSONB, server_default='[]', nullable=False),
        
        # Personalization
        sa.Column('initial_archetype', sa.String(50), nullable=True),
        sa.Column('personality_traits', JSONB, server_default='{}', nullable=False),
        sa.Column('onboarding_completed', sa.Boolean, default=False, nullable=False),
        
        # Timestamps
        sa.Column('created_at', sa.TIMESTAMP, server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP, server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    
    # Add unique constraint on user_id
    op.create_unique_constraint('uq_user_preferences_user_id', 'user_preferences', ['user_id'])
    
    # Add index on user_id for fast lookups
    op.create_index('idx_user_preferences_user_id', 'user_preferences', ['user_id'])
    
    # Add foreign key constraint to users table
    op.create_foreign_key(
        'fk_user_preferences_user_id',
        'user_preferences',
        'users',
        ['user_id'],
        ['id'],
        ondelete='CASCADE'
    )
    
    # Add check constraints for enum-like fields
    op.create_check_constraint(
        'ck_sleep_quality',
        'user_preferences',
        "sleep_quality IN ('poor', 'fair', 'good', 'excellent') OR sleep_quality IS NULL"
    )
    
    op.create_check_constraint(
        'ck_dream_recall_frequency',
        'user_preferences',
        "dream_recall_frequency IN ('never', 'rarely', 'sometimes', 'often', 'always') OR dream_recall_frequency IS NULL"
    )
    
    op.create_check_constraint(
        'ck_dream_vividness',
        'user_preferences',
        "dream_vividness IN ('vague', 'moderate', 'vivid', 'very_vivid') OR dream_vividness IS NULL"
    )
    
    op.create_check_constraint(
        'ck_primary_goal',
        'user_preferences',
        "primary_goal IN ('self_discovery', 'creativity', 'problem_solving', 'emotional_healing', 'lucid_dreaming') OR primary_goal IS NULL"
    )
    
    op.create_check_constraint(
        'ck_reminder_frequency',
        'user_preferences',
        "reminder_frequency IN ('daily', 'weekly', 'custom')"
    )
    
    # Use the existing trigger function for updating updated_at
    op.execute("""
        CREATE TRIGGER update_user_preferences_updated_at BEFORE UPDATE
        ON user_preferences FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
    """)


def downgrade() -> None:
    # Drop trigger
    op.execute("DROP TRIGGER IF EXISTS update_user_preferences_updated_at ON user_preferences")
    
    # Drop foreign key
    op.drop_constraint('fk_user_preferences_user_id', 'user_preferences', type_='foreignkey')
    
    # Drop check constraints
    op.drop_constraint('ck_sleep_quality', 'user_preferences', type_='check')
    op.drop_constraint('ck_dream_recall_frequency', 'user_preferences', type_='check')
    op.drop_constraint('ck_dream_vividness', 'user_preferences', type_='check')
    op.drop_constraint('ck_primary_goal', 'user_preferences', type_='check')
    op.drop_constraint('ck_reminder_frequency', 'user_preferences', type_='check')
    
    # Drop table
    op.drop_table('user_preferences')
