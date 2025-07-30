"""add onboarding journey to user preferences

Revision ID: f3a2b1c4d5e6
Revises: a2385c74dc20
Create Date: 2024-01-30 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'f3a2b1c4d5e6'
down_revision = 'a2385c74dc20'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add onboarding_journey column to user_preferences table
    op.add_column(
        'user_preferences',
        sa.Column(
            'onboarding_journey',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment='Complete onboarding interaction data'
        )
    )


def downgrade() -> None:
    # Remove onboarding_journey column
    op.drop_column('user_preferences', 'onboarding_journey')