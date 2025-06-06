"""Update primary key to use global id sequence for partitioned tables

Revision ID: 7a838ea48eea
Revises: fd0510a0a9aa
Create Date: 2025-04-05 11:03:07.597617

This migration adds a primary key constraint to the `presigned_url` and `login`
tables, which are partitioned using SQLAlchemy’s inheritance-based table
partitioning.

Background:
When using inheritance-based table partitioning in SQLAlchemy,
auto-increment behavior on the primary key (e.g., 'id') doesn't always
work as expected. Even if the base table has an auto-incrementing
primary key defined, the partitioned child tables do not automatically
inherit this behavior in practice.

This is because the insert occurs on the child (partitioned) table,
bypassing the base table's sequence or identity configuration. As a
result, the database may not generate the next ID correctly, leading to
null or duplicate values.

To resolve this:
- A global sequence is used to explicitly generate `id` values.
- The `id` column in each partitioned table is updated to use this sequence.
- A primary key constraint is added to ensure data integrity.

This change ensures that all inserts into partitioned tables receive
consistent and valid primary key values.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text
from audit import logger

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
            logger.info(f"Updating child table: {child_table}")
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
        op.execute(
            f"ALTER TABLE {parent_table} ADD CONSTRAINT {parent_table}_pkey PRIMARY KEY (id);"
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
                IF NEW.id IS NULL THEN
                    NEW.id := nextval('global_presigned_url_id_seq');
                END IF;
                EXECUTE format(
                    'INSERT INTO %I (id, request_url, status_code, timestamp, username, sub, guid, resource_paths, action, protocol)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)',
                    partition
                )
                USING NEW.id, NEW.request_url, NEW.status_code, NEW.timestamp, NEW.username,
                        NEW.sub, NEW.guid, NEW.resource_paths, NEW.action, NEW.protocol;
            ELSIF TG_TABLE_NAME = 'login' THEN
                IF NEW.id IS NULL THEN
                    NEW.id := nextval('global_login_id_seq');
                END IF;
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

    # TODO: In future, replace this hardcoded implementation and fetch the function body dynamically and revert to the previous state
    op.execute(
        """CREATE OR REPLACE FUNCTION create_partition_and_insert() RETURNS trigger AS
        $BODY$
            DECLARE
            partition_timestamp TEXT;
            partition TEXT;
            BEGIN
            partition_timestamp := to_char(NEW.timestamp,'YYYY_MM');
            partition := TG_RELNAME || '_' || partition_timestamp;
            IF NOT EXISTS(SELECT relname FROM pg_class WHERE relname=partition) THEN
                RAISE NOTICE 'Partition % has been created',partition;
                EXECUTE 'CREATE TABLE ' || partition || ' () INHERITS (' || TG_RELNAME || ');';
            END IF;
            EXECUTE 'INSERT INTO ' || partition || ' SELECT(' || TG_RELNAME || ' ' || quote_literal(NEW) || ').* RETURNING username;';
            RETURN NULL;
            END;
        $BODY$
    LANGUAGE plpgsql VOLATILE
    COST 100;"""
    )

    logger.info("Reverted trigger function to previous state.")
