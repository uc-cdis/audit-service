"""Add additional_data to AuditLog

Revision ID: 43a6446e2d8d
Revises: 7a838ea48eea
Create Date: 2025-08-22 09:51:15.370325

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from audit import logger

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

    # Update the existing trigger function to include the new columns
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
                    'INSERT INTO %I (id, request_url, status_code, timestamp, username, sub, guid, resource_paths, action, protocol, additional_data)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)',
                    partition
                )
                USING NEW.id, NEW.request_url, NEW.status_code, NEW.timestamp, NEW.username,
                        NEW.sub, NEW.guid, NEW.resource_paths, NEW.action, NEW.protocol, NEW.additional_data;
            ELSIF TG_TABLE_NAME = 'login' THEN
                IF NEW.id IS NULL THEN
                    NEW.id := nextval('global_login_id_seq');
                END IF;
                EXECUTE format(
                    'INSERT INTO %I (id, request_url, status_code, timestamp, username, sub, idp, fence_idp, shib_idp, client_id, additional_data)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)',
                    partition
                )
                USING NEW.id, NEW.request_url, NEW.status_code, NEW.timestamp, NEW.username,
                        NEW.sub, NEW.idp, NEW.fence_idp, NEW.shib_idp, NEW.client_id, NEW.additional_data;
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
    """Remove the 'additional_data' column"""
    op.drop_column("presigned_url", "additional_data")
    op.drop_column("login", "additional_data")

    # Revert the trigger function previous state to not include the new columns
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
