"""add pfb_export and user_data_library tables

Revision ID: 39d94c2bea56
Revises: 42692e47f254
Create Date: 2026-09-22 08:08:12.587466

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "39d94c2bea56"  # pragma: allowlist secret
down_revision = "42692e47f254"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SEQUENCE global_pfb_export_id_seq")
    op.execute("CREATE SEQUENCE global_user_data_library_id_seq")

    op.create_table(
        "pfb_export",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("request_url", sa.String, nullable=False),
        sa.Column("status_code", sa.Integer, nullable=False),
        sa.Column("timestamp", sa.DateTime, nullable=False),
        sa.Column("username", sa.String, nullable=False),
        sa.Column("sub", sa.Integer, nullable=True),
        sa.Column(
            "additional_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("programs", postgresql.ARRAY(sa.String), nullable=False),
        sa.Column("projects", postgresql.ARRAY(sa.String), nullable=False),
        sa.Column("node_count", sa.Integer, nullable=True),
        sa.Column("destination", sa.String, nullable=True),
        sa.Column("export_type", sa.String, nullable=False),
    )

    op.create_table(
        "user_data_library",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("request_url", sa.String, nullable=False),
        sa.Column("status_code", sa.Integer, nullable=False),
        sa.Column("timestamp", sa.DateTime, nullable=False),
        sa.Column("username", sa.String, nullable=False),
        sa.Column("sub", sa.Integer, nullable=True),
        sa.Column(
            "additional_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("action", sa.String, nullable=False),
        sa.Column("target_type", sa.String, nullable=False),
        sa.Column("list_id", sa.String, nullable=False),
        sa.Column("item_id", sa.String, nullable=True),
        sa.Column("item_dataset_ids", postgresql.ARRAY(sa.String), nullable=False),
        sa.Column("list_size_after", sa.Integer, nullable=True),
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

        ELSIF TG_TABLE_NAME = 'pfb_export' THEN
            EXECUTE format(
                'INSERT INTO %I (id, request_url, status_code, timestamp, username,
                                 sub, additional_data, programs, projects, node_count,
                                 destination, export_type)
                 VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)',
                partition)
            USING NEW.id, NEW.request_url, NEW.status_code, NEW.timestamp,
                  NEW.username, NEW.sub, NEW.additional_data,
                  NEW.programs, NEW.projects, NEW.node_count,
                  NEW.destination, NEW.export_type;

        ELSIF TG_TABLE_NAME = 'user_data_library' THEN
            EXECUTE format(
                'INSERT INTO %I (id, request_url, status_code, timestamp, username,
                                 sub, additional_data, action, target_type, list_id,
                                 item_id, item_dataset_ids, list_size_after)
                 VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)',
                partition)
            USING NEW.id, NEW.request_url, NEW.status_code, NEW.timestamp,
                  NEW.username, NEW.sub, NEW.additional_data,
                  NEW.action, NEW.target_type, NEW.list_id,
                  NEW.item_id, NEW.item_dataset_ids, NEW.list_size_after;

        ELSE
            RAISE EXCEPTION 'Unsupported table for partitioning: %', TG_TABLE_NAME;
        END IF;

        RETURN NULL;
    END;
    $$ LANGUAGE plpgsql VOLATILE;
    """)

    op.execute("""
    CREATE TRIGGER insert_pfb_export_trigger
        BEFORE INSERT ON pfb_export
        FOR EACH ROW EXECUTE PROCEDURE create_partition_and_insert();
    """)

    op.execute("""
    CREATE TRIGGER insert_user_data_library_trigger
        BEFORE INSERT ON user_data_library
        FOR EACH ROW EXECUTE PROCEDURE create_partition_and_insert();
    """)


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS insert_pfb_export_trigger ON pfb_export")
    op.execute(
        "DROP TRIGGER IF EXISTS insert_user_data_library_trigger ON user_data_library"
    )
    op.drop_table("pfb_export")
    op.drop_table("user_data_library")
    op.execute("DROP SEQUENCE IF EXISTS global_pfb_export_id_seq")
    op.execute("DROP SEQUENCE IF EXISTS global_user_data_library_id_seq")

    # revert trigger function to previous version (without pfb_export and user_data_library branches)
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
