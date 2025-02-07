"""add passport to presigned_url

Revision ID: 21a74a628839
Revises: fd0510a0a9aa
Create Date: 2025-02-06 16:04:25.903077

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "21a74a628839"
down_revision = "fd0510a0a9aa"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    op.add_column("presigned_url", sa.Column("jti", sa.String(), nullable=True))
    op.add_column("presigned_url", sa.Column("passport", sa.Boolean(), nullable=True))


def downgrade():
    conn = op.get_bind()

    op.drop_column("presigned_url", "jti")
    op.drop_column("presigned_url", "passport")
