"""empty message

Revision ID: 0bb8936015e3
Revises: 5e5e5ad480ea
Create Date: 2025-07-06 11:20:24.562005

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0bb8936015e3'
down_revision: Union[str, None] = '5e5e5ad480ea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('dreams', sa.Column('created_at', sa.DateTime(), nullable=True))
    op.drop_column('dreams', 'created')
    op.alter_column('interpretation_answers', 'answered_at',
               existing_type=postgresql.TIMESTAMP(),
               nullable=True)
    op.drop_index(op.f('ix_interpretation_answers_question_id'), table_name='interpretation_answers')
    op.drop_index(op.f('ix_interpretation_answers_user_id'), table_name='interpretation_answers')
    op.drop_constraint(op.f('uq_user_question_answer'), 'interpretation_answers', type_='unique')
    op.drop_index(op.f('ix_interpretation_choices_question_id'), table_name='interpretation_choices')
    op.add_column('interpretation_questions', sa.Column('created_at', sa.DateTime(), nullable=True))
    op.drop_index(op.f('ix_interpretation_questions_dream_id'), table_name='interpretation_questions')
    op.drop_column('interpretation_questions', 'created')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('interpretation_questions', sa.Column('created', postgresql.TIMESTAMP(), autoincrement=False, nullable=False))
    op.create_index(op.f('ix_interpretation_questions_dream_id'), 'interpretation_questions', ['dream_id'], unique=False)
    op.drop_column('interpretation_questions', 'created_at')
    op.create_index(op.f('ix_interpretation_choices_question_id'), 'interpretation_choices', ['question_id'], unique=False)
    op.create_unique_constraint(op.f('uq_user_question_answer'), 'interpretation_answers', ['question_id', 'user_id'], postgresql_nulls_not_distinct=False)
    op.create_index(op.f('ix_interpretation_answers_user_id'), 'interpretation_answers', ['user_id'], unique=False)
    op.create_index(op.f('ix_interpretation_answers_question_id'), 'interpretation_answers', ['question_id'], unique=False)
    op.alter_column('interpretation_answers', 'answered_at',
               existing_type=postgresql.TIMESTAMP(),
               nullable=False)
    op.add_column('dreams', sa.Column('created', postgresql.TIMESTAMP(), autoincrement=False, nullable=True))
    op.drop_column('dreams', 'created_at')
    # ### end Alembic commands ###
