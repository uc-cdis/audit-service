"""add ip to login table

Revision ID: 91d4d845c851
Revises: fd0510a0a9aa
Create Date: 2025-05-20 19:58:22.881579

"""
from alembic import op
import sqlalchemy as sa


revision = "91d4d845c851"
down_revision = "fd0510a0a9aa"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("login", sa.Column("ip", sa.String(), nullable=True))


def downgrade():
    op.drop_column("login", "ip")
