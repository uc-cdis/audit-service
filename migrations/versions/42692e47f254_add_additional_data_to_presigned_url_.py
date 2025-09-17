"""Add 'additional_data' to presigned_url and login

Revision ID: 42692e47f254
Revises: 45aae42015e8
Create Date: 2025-08-25 12:08:58.718176

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "42692e47f254"
down_revision = "45aae42015e8"
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
    """
    )


def downgrade():
    """Remove the 'additional_data' column"""
    op.drop_column("presigned_url", "additional_data")
    op.drop_column("login", "additional_data")

    # revert trigger function
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
