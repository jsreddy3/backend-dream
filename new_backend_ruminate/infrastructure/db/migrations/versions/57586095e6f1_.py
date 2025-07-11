"""empty message

Revision ID: 57586095e6f1
Revises: 0bb8936015e3
Create Date: 2025-07-06 16:39:52.374945

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '57586095e6f1'
down_revision: Union[str, None] = '0bb8936015e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index(op.f('ix_dreams_created_at'), 'dreams', ['created_at'], unique=False)
    op.create_index('ix_dreams_user_created', 'dreams', ['user_id', sa.literal_column('created_at DESC')], unique=False)
    op.create_index(op.f('ix_dreams_user_id'), 'dreams', ['user_id'], unique=False)
    op.create_index(op.f('ix_segments_dream_id'), 'segments', ['dream_id'], unique=False)
    op.create_index('ix_segments_dream_order', 'segments', ['dream_id', 'order'], unique=False)
    op.create_index(op.f('ix_segments_user_id'), 'segments', ['user_id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_segments_user_id'), table_name='segments')
    op.drop_index('ix_segments_dream_order', table_name='segments')
    op.drop_index(op.f('ix_segments_dream_id'), table_name='segments')
    op.drop_index(op.f('ix_dreams_user_id'), table_name='dreams')
    op.drop_index('ix_dreams_user_created', table_name='dreams')
    op.drop_index(op.f('ix_dreams_created_at'), table_name='dreams')
    # ### end Alembic commands ###
