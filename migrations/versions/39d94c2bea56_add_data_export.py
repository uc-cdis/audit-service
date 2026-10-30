"""add export_data table

Revision ID: 39d94c2bea56
Revises: 42692e47f254
Create Date: 2026-09-22 08:08:12.587466

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "39d94c2bea56"  # pragma: allowlist secret
down_revision = "42692e47f254"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SEQUENCE global_export_data_id_seq")

    op.create_table(
        "export_data",
        # Without autoincrement=False, SQLAlchemy makes `id` a SERIAL with its
        # own sequence, which hands out ids that collide with the ones from
        # global_export_data_id_seq.
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("request_url", sa.String, nullable=False),
        sa.Column("status_code", sa.Integer, nullable=False),
        sa.Column(
            "timestamp", sa.DateTime, nullable=False, server_default=sa.func.now()
        ),
        sa.Column("username", sa.String, nullable=False),
        sa.Column("sub", sa.Integer, nullable=True),
        sa.Column(
            "additional_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("type", sa.String, nullable=False),
        sa.Column("resource_paths", sa.ARRAY(sa.String()), nullable=True),
        sa.Column("destination", sa.String, nullable=True),
    )

    op.execute("""
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
            EXECUTE format(
                'INSERT INTO %I (id, request_url, status_code, timestamp, username,
                                 sub, guid, resource_paths, action, protocol, additional_data)
                 VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)',
                partition)
            USING NEW.id, NEW.request_url, NEW.status_code, NEW.timestamp,
                  NEW.username, NEW.sub, NEW.guid,
                  NEW.resource_paths, NEW.action, NEW.protocol, NEW.additional_data;

        ELSIF TG_TABLE_NAME = 'login' THEN
            IF NEW.id IS NULL THEN
                NEW.id := nextval('global_login_id_seq');
            END IF;

            EXECUTE format(
                'INSERT INTO %I (id, request_url, status_code, timestamp, username,
                                 sub, idp, fence_idp, shib_idp, client_id, ip, additional_data)
                 VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)',
                partition)
            USING NEW.id, NEW.request_url, NEW.status_code, NEW.timestamp,
                  NEW.username, NEW.sub, NEW.idp, NEW.fence_idp,
                  NEW.shib_idp, NEW.client_id, NEW.ip, NEW.additional_data;

        ELSIF TG_TABLE_NAME = 'export_data' THEN
            EXECUTE format(
                'INSERT INTO %I (id, request_url, status_code, timestamp, username,
                                 sub, additional_data, type, resource_paths, destination)
                 VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)',
                partition)
            USING NEW.id, NEW.request_url, NEW.status_code, NEW.timestamp,
                  NEW.username, NEW.sub, NEW.additional_data, NEW.type,
                  NEW.resource_paths, NEW.destination;

        ELSE
            RAISE EXCEPTION 'Unsupported table for partitioning: %', TG_TABLE_NAME;
        END IF;

        RETURN NULL;
    END;
    $$ LANGUAGE plpgsql VOLATILE;
    """)

    op.execute("""
    CREATE TRIGGER insert_export_data_trigger
        BEFORE INSERT ON export_data
        FOR EACH ROW EXECUTE PROCEDURE create_partition_and_insert();
    """)


def _drop_table_with_partitions(table_name, trigger_name):
    op.execute(f"DROP TRIGGER IF EXISTS {trigger_name} ON {table_name}")
    conn = op.get_bind()
    res = conn.execute(
        text(
            f"SELECT child.relname FROM pg_inherits "
            f"JOIN pg_class AS child ON (inhrelid=child.oid) "
            f"JOIN pg_class AS parent ON (inhparent=parent.oid) "
            f"WHERE parent.relname='{table_name}'"
        )
    )
    for (partition,) in res.fetchall():
        op.drop_table(partition)
    op.drop_table(table_name)


def downgrade():
    _drop_table_with_partitions("export_data", "insert_export_data_trigger")
    op.execute("DROP SEQUENCE IF EXISTS global_export_data_id_seq")

    # revert trigger function to previous version (without data_export branches)
    op.execute("""
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
            EXECUTE format(
                'INSERT INTO %I (id, request_url, status_code, timestamp, username,
                                 sub, guid, resource_paths, action, protocol, additional_data)
                 VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)',
                partition)
            USING NEW.id, NEW.request_url, NEW.status_code, NEW.timestamp,
                  NEW.username, NEW.sub, NEW.guid,
                  NEW.resource_paths, NEW.action, NEW.protocol, NEW.additional_data;

        ELSIF TG_TABLE_NAME = 'login' THEN
            IF NEW.id IS NULL THEN
                NEW.id := nextval('global_login_id_seq');
            END IF;

            EXECUTE format(
                'INSERT INTO %I (id, request_url, status_code, timestamp, username,
                                 sub, idp, fence_idp, shib_idp, client_id, ip, additional_data)
                 VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)',
                partition)
            USING NEW.id, NEW.request_url, NEW.status_code, NEW.timestamp,
                  NEW.username, NEW.sub, NEW.idp, NEW.fence_idp,
                  NEW.shib_idp, NEW.client_id, NEW.ip, NEW.additional_data;
        ELSE
            RAISE EXCEPTION 'Unsupported table for partitioning: %', TG_TABLE_NAME;
        END IF;

        RETURN NULL;
    END;
    $$ LANGUAGE plpgsql VOLATILE;
    """)
