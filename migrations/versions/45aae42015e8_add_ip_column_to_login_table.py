"""add ip column to login table

Revision ID: 45aae42015e8
Revises: 7a838ea48eea
Create Date: 2025-06-11 02:43:06.077198

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text
from audit import logger

# revision identifiers, used by Alembic.
revision = "45aae42015e8"
down_revision = "7a838ea48eea"
branch_labels = None
depends_on = None


def _child_partitions(conn, parent: str) -> list[str]:
    """Return names of tables that inherit from parent"""
    res = conn.execute(
        text(
            """
            SELECT c.relname
            FROM pg_inherits
            JOIN pg_class   c ON c.oid = inhrelid
            JOIN pg_class   p ON p.oid = inhparent
            WHERE p.relname = :parent
            """
        ),
        {"parent": parent},
    )
    return [row[0] for row in res]


def upgrade():
    conn = op.get_bind()

    # add ip column to parent login table
    op.add_column("login", sa.Column("ip", sa.Text, nullable=True))

    # add to child partitions
    for child in _child_partitions(conn, "login"):
        logger.info(f"Adding ip column to partition {child}")
        op.execute(f'ALTER TABLE "{child}" ADD COLUMN IF NOT EXISTS ip TEXT;')

    # replace trigger so future partitions get the new column
    op.execute(
        """
    CREATE OR REPLACE FUNCTION create_partition_and_insert() RETURNS trigger AS
    $$
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
            -- unchanged
            EXECUTE format(
                'INSERT INTO %I (id, request_url, status_code, timestamp, username,
                                 sub, guid, resource_paths, action, protocol)
                 VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)',
                partition)
            USING NEW.id, NEW.request_url, NEW.status_code, NEW.timestamp,
                  NEW.username, NEW.sub, NEW.guid,
                  NEW.resource_paths, NEW.action, NEW.protocol;

        ELSIF TG_TABLE_NAME = 'login' THEN
            IF NEW.id IS NULL THEN
                NEW.id := nextval('global_login_id_seq');
            END IF;

            EXECUTE format(
                'INSERT INTO %I (id, request_url, status_code, timestamp, username,
                                 sub, idp, fence_idp, shib_idp, client_id, ip)
                 VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)',
                partition)
            USING NEW.id, NEW.request_url, NEW.status_code, NEW.timestamp,
                  NEW.username, NEW.sub, NEW.idp, NEW.fence_idp,
                  NEW.shib_idp, NEW.client_id, NEW.ip;
        ELSE
            RAISE EXCEPTION 'Unsupported table for partitioning: %', TG_TABLE_NAME;
        END IF;

        RETURN NULL;
    END;
    $$ LANGUAGE plpgsql VOLATILE;
    """
    )


def downgrade():
    conn = op.get_bind()

    # drop ip from parent table
    op.execute("ALTER TABLE login DROP COLUMN ip CASCADE;")

    # drop from child partitions
    for child in _child_partitions(conn, "login"):
        is_local = conn.execute(
            text(
                f"""
                SELECT attislocal
                FROM pg_attribute
                WHERE attrelid = '{child}'::regclass
                  AND attname  = 'ip'
                  AND NOT attisdropped
                """
            )
        ).scalar()
        if is_local:
            logger.info(f"Dropping local ip column from {child}")
            op.execute(f'ALTER TABLE "{child}" DROP COLUMN ip;')

    # revert trigger function
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

    logger.info("Reverted trigger function to previous state.")
