"""create presigned_url table

Revision ID: d5b18185c458
Revises:
Create timestamp: 2021-02-02 18:11:46.518674

"""
from alembic import op
from datetime import datetime
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d5b18185c458"
down_revision = None
branch_labels = None
depends_on = None


TABLE_NAME = "presigned_url"


def setup_table_partitioning(table_name):
    """
    Creates partitions with inheritance so we can create them automatically
    with a trigger.
    We partition the table by month: for example, rows with timestamp
    "2021_01_XX" are inserted into partition "<table name>_2021_01".
    """
    print("  Creating `create_partition_and_insert` function")
    procedure_stmt = """CREATE OR REPLACE FUNCTION create_partition_and_insert() RETURNS trigger AS
        $BODY$
            DECLARE
            partition_timestamp TEXT;
            partition TEXT;
            BEGIN
            partition_timestamp := to_char(NEW.timestamp,'YYYY_MM');
            partition := TG_RELNAME || '_' || partition_timestamp;
            IF NOT EXISTS(SELECT relname FROM pg_class WHERE relname=partition) THEN
                RAISE NOTICE 'A partition has been created %',partition;
                EXECUTE 'CREATE TABLE ' || partition || ' (check (timestamp >= ''' || NEW.timestamp || ''')) INHERITS (' || TG_RELNAME || ');';
            END IF;
            EXECUTE 'INSERT INTO ' || partition || ' SELECT(' || TG_RELNAME || ' ' || quote_literal(NEW) || ').* RETURNING username;';
            RETURN NULL;
            END;
        $BODY$
    LANGUAGE plpgsql VOLATILE
    COST 100;"""
    op.execute(procedure_stmt)

    trigger_name = f"{table_name}_partition_trigger"
    print(f"  Creating `{trigger_name}` trigger")
    trigger_stmt = f"""CREATE TRIGGER {trigger_name}
    BEFORE INSERT ON {table_name}
    FOR EACH ROW EXECUTE PROCEDURE create_partition_and_insert();"""
    op.execute(trigger_stmt)


def delete_table_partitioning(table_name):
    trigger_name = f"{table_name}_partition_trigger"
    print(f"  Deleting `{trigger_name}` trigger")
    op.execute(f"DROP TRIGGER {trigger_name} on {table_name}")

    print("  Deleting `create_partition_and_insert` function")
    op.execute("DROP FUNCTION create_partition_and_insert")

    stmt = f"""SELECT child.relname FROM pg_inherits JOIN pg_class AS child ON (inhrelid=child.oid) JOIN pg_class as parent ON (inhparent=parent.oid) where parent.relname='{table_name}'"""
    conn = op.get_bind()
    res = conn.execute(stmt)
    partition_names = [table_data[0] for table_data in res.fetchall()]
    for partition in partition_names:
        print(f"  Deleting `{table_name}` table partition `{partition}`")
        op.drop_table(partition)


def upgrade():
    print(f"  Creating `{TABLE_NAME}` table")
    op.create_table(
        TABLE_NAME,
        sa.Column("request_url", sa.String(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        # sa.Column("timestamp", nullable=False, sa.dialects.postgresql.TIMESTAMP, server_default=sa.func.now()),
        # sa.Column("timestamp", sa.DateTime, nullable=False, server_default=datetime.utcnow()),
        sa.Column(
            "timestamp", sa.DateTime, nullable=False, server_default=sa.func.now()
        ),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("sub", sa.String(), nullable=False),
        sa.Column("guid", sa.String(), nullable=False),
        sa.Column("resource_paths", sa.ARRAY(sa.String()), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("protocol", sa.String(), nullable=True),
        # postgresql_partition_by='RANGE (timestamp)',
    )
    setup_table_partitioning(TABLE_NAME)


def downgrade():
    delete_table_partitioning(TABLE_NAME)
    print(f"  Deleting `{TABLE_NAME}` table")
    op.drop_table(TABLE_NAME)
