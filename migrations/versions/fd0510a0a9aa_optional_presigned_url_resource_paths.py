"""optional presigned_url resource_paths

Revision ID: fd0510a0a9aa
Revises: d5b18185c458
Create Date: 2021-05-25 15:06:06.372742

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "fd0510a0a9aa"
down_revision = "d5b18185c458"
branch_labels = None
depends_on = None


table_name = "presigned_url"


def upgrade():
    op.alter_column(table_name, "resource_paths", nullable=True)


def downgrade():
    # replace null values with an empty array
    op.execute(
        f"UPDATE {table_name} SET resource_paths=ARRAY[]::VARCHAR[] WHERE resource_paths IS NULL"
    )
    op.alter_column(table_name, "resource_paths", nullable=False)
