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


def _partitions():
    """
    First yield parent table (login), then child partition
    """
    yield "login"

    conn = op.get_bind()
    part_query = """
        SELECT child.relname
        FROM pg_inherits
        JOIN pg_class AS child  ON inhrelid  = child.oid
        JOIN pg_class AS parent ON inhparent = parent.oid
        WHERE parent.relname = 'login'
    """
    for (relname,) in conn.execute(part_query):
        yield relname


def upgrade():
    ip_col = sa.Column("ip", sa.String(), nullable=True)

    for table in _partitions():
        op.add_column(table, ip_col.copy())


def downgrade():
    for table in _partitions():
        op.drop_column(table, "ip")
