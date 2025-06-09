"""add ip to login table

Revision ID: 5198001b2ab8
Revises: 7a838ea48eea
Create Date: 2025-06-09 01:40:17.421600

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "5198001b2ab8"
down_revision = "7a838ea48eea"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("login", sa.Column("ip", sa.String(), nullable=True))


def downgrade():
    op.drop_column("login", "ip")
