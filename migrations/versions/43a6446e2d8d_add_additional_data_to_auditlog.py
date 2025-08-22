"""Add additional_data to AuditLog

Revision ID: 43a6446e2d8d
Revises: 7a838ea48eea
Create Date: 2025-08-22 09:51:15.370325

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "43a6446e2d8d"
down_revision = "7a838ea48eea"
branch_labels = None
depends_on = None


def upgrade():
    """Add the 'additional_data' column"""
    op.add_column(
        "login",
        sa.Column(
            "additional_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )
    op.add_column(
        "presigned_url",
        sa.Column(
            "additional_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )


def downgrade():
    """Remove the 'additional_data' column"""
    op.drop_column("presigned_url", "additional_data")
    op.drop_column("login", "additional_data")
