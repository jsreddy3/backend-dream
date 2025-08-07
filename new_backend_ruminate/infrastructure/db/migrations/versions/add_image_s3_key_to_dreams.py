"""add_image_s3_key_to_dreams

Revision ID: add_image_s3_key
Revises: 32fc74270dd0
Create Date: 2025-08-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_image_s3_key'
down_revision: Union[str, None] = '32fc74270dd0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add image_s3_key field to store the S3 key instead of presigned URL
    op.add_column('dreams', sa.Column('image_s3_key', sa.String(500), nullable=True))
    
    # Migrate existing data: extract S3 key from URLs
    # This handles URLs like: https://bucket.s3.region.amazonaws.com/dreams/user_id/dream_id/image_uuid.png
    op.execute("""
        UPDATE dreams 
        SET image_s3_key = CASE 
            WHEN image_url LIKE '%amazonaws.com/%' THEN 
                SUBSTRING(image_url FROM POSITION('.com/' IN image_url) + 5)
            ELSE NULL
        END
        WHERE image_url IS NOT NULL
    """)


def downgrade() -> None:
    # Remove image_s3_key field
    op.drop_column('dreams', 'image_s3_key')