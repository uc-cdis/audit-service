"""Add auto-increment primary key to presigned_url

Revision ID: 7a838ea48eea
Revises: fd0510a0a9aa
Create Date: 2025-04-05 11:03:07.597617

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = "7a838ea48eea"
down_revision = "fd0510a0a9aa"
branch_labels = None
depends_on = None

PARENT_TABLES = {
    "presigned_url": "global_presigned_url_id_seq",
    "login": "global_login_id_seq",
}


def upgrade():
    connection = op.get_bind()

    for parent_table, sequence_name in PARENT_TABLES.items():

        # Step 1: Create global sequences
        op.execute(f"CREATE SEQUENCE {sequence_name};")

        # Step 2: Add 'id' columns to parent tables
        op.add_column(parent_table, sa.Column("id", sa.Integer()))

        # Step 3: Add 'id' to existing child tables (INHERITS-based)

        # Get a list of all child tables inheriting from the parent table
        res = connection.execute(
            text(
                f"""
            SELECT c.relname
            FROM pg_inherits
            JOIN pg_class c ON c.oid = inhrelid
            JOIN pg_class p ON p.oid = inhparent
            WHERE p.relname = :parent_table
        """
            ),
            {"parent_table": parent_table},
        )

        # for each child table, add the 'id' column if it doesn't exist
        for row in res:
            child_table = row[0]
            print(f"Updating child table: {child_table}")
            # Check if the 'id' column already exists
            result = connection.execute(
                text(
                    """
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = :child_table AND column_name = 'id'
            """
                ),
                {"child_table": child_table},
            ).fetchone()

            if not result:
                op.execute(f"ALTER TABLE {child_table} ADD COLUMN id INTEGER;")

            # Backfill ID values
            connection.execute(
                text(
                    f"""
                UPDATE {child_table}
                SET id = nextval('{sequence_name}')
                WHERE id IS NULL;
            """
                )
            )
        # Step 4: Set primary key constraint
        # op.update_column(
        #     parent_table,
        #     sa.Column("id", sa.Integer(), nullable=False),
        # )
        op.execute(
            "ALTER TABLE {parent_table} ADD CONSTRAINT {parent_table}_pkey PRIMARY KEY (id);"
        )

    # Step 5: Replace trigger function to include id field for child tables
    op.execute(
        """
    CREATE OR REPLACE FUNCTION create_partition_and_insert() RETURNS trigger AS
    $BODY$
        DECLARE
            partition_timestamp TEXT;
            partition TEXT;
        BEGIN
            partition_timestamp := to_char(NEW.timestamp,'YYYY_MM');
            partition := TG_TABLE_NAME || '_' || partition_timestamp;


            IF NOT EXISTS(SELECT relname FROM pg_class WHERE relname = partition) THEN
                EXECUTE format('CREATE TABLE %I () INHERITS (%I);', partition, TG_TABLE_NAME);
            END IF;

            IF TG_TABLE_NAME = 'presigned_url' THEN
                NEW.id := nextval('global_presigned_url_id_seq');
                EXECUTE format(
                    'INSERT INTO %I (id, request_url, status_code, timestamp, username, sub, guid, resource_paths, action, protocol)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)',
                    partition
                )
                USING NEW.id, NEW.request_url, NEW.status_code, NEW.timestamp, NEW.username,
                        NEW.sub, NEW.guid, NEW.resource_paths, NEW.action, NEW.protocol;
            ELSIF TG_TABLE_NAME = 'login' THEN
                NEW.id := nextval('global_login_id_seq');
                EXECUTE format(
                    'INSERT INTO %I (id, request_url, status_code, timestamp, username, sub, idp, fence_idp, shib_idp, client_id)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)',
                    partition
                )
                USING NEW.id, NEW.request_url, NEW.status_code, NEW.timestamp, NEW.username,
                        NEW.sub, NEW.idp, NEW.fence_idp, NEW.shib_idp, NEW.client_id;
            ELSE
                RAISE EXCEPTION 'Unsupported table for partitioning: %', TG_TABLE_NAME;
            END IF;

            RETURN NULL;
        END;
    $BODY$
    LANGUAGE plpgsql VOLATILE;
    """
    )


def downgrade():
    for parent_table, seq_name in PARENT_TABLES.items():
        op.drop_constraint(f"{parent_table}_pkey", parent_table, type_="primary")
        op.drop_column(parent_table, "id")
        op.execute(f"DROP SEQUENCE IF EXISTS {seq_name};")
