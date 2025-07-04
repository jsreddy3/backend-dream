"""add_interpretation_questions_and_answers

Revision ID: d808b78b2967
Revises: b9a8ed2a413a
Create Date: 2025-07-04 11:51:51.818750

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd808b78b2967'
down_revision: Union[str, None] = 'b9a8ed2a413a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create interpretation_questions table
    op.create_table('interpretation_questions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('dream_id', sa.UUID(), nullable=False),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('question_order', sa.Integer(), nullable=False),
        sa.Column('created', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['dream_id'], ['dreams.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_interpretation_questions_dream_id'), 'interpretation_questions', ['dream_id'], unique=False)
    
    # Create interpretation_choices table
    op.create_table('interpretation_choices',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('question_id', sa.UUID(), nullable=False),
        sa.Column('choice_text', sa.Text(), nullable=False),
        sa.Column('choice_order', sa.Integer(), nullable=False),
        sa.Column('is_custom', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['question_id'], ['interpretation_questions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_interpretation_choices_question_id'), 'interpretation_choices', ['question_id'], unique=False)
    
    # Create interpretation_answers table
    op.create_table('interpretation_answers',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('question_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('selected_choice_id', sa.UUID(), nullable=True),
        sa.Column('custom_answer', sa.Text(), nullable=True),
        sa.Column('answered_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['question_id'], ['interpretation_questions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['selected_choice_id'], ['interpretation_choices.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('question_id', 'user_id', name='uq_user_question_answer')
    )
    op.create_index(op.f('ix_interpretation_answers_question_id'), 'interpretation_answers', ['question_id'], unique=False)
    op.create_index(op.f('ix_interpretation_answers_user_id'), 'interpretation_answers', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_interpretation_answers_user_id'), table_name='interpretation_answers')
    op.drop_index(op.f('ix_interpretation_answers_question_id'), table_name='interpretation_answers')
    op.drop_table('interpretation_answers')
    op.drop_index(op.f('ix_interpretation_choices_question_id'), table_name='interpretation_choices')
    op.drop_table('interpretation_choices')
    op.drop_index(op.f('ix_interpretation_questions_dream_id'), table_name='interpretation_questions')
    op.drop_table('interpretation_questions')
