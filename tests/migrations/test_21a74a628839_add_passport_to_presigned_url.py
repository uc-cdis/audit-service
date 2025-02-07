import pytest
from alembic.config import main as alembic_main
from alembic import op
from gino import Gino
from audit.config import config
from sqlalchemy import text
from audit.models import db


def get_tables(connection):
    res = connection.execute(
        "SELECT * FROM pg_catalog.pg_tables WHERE schemaname != 'pg_catalog' AND schemaname != 'information_schema';"
    ).fetchall()
    return {i[1] for i in res}


def create_presigned_url_log(connection, log_data):

    request_url = log_data["request_url"]
    status_code = log_data["status_code"]
    timestamp = log_data["timestamp"]  # Unix timestamp
    username = log_data["username"]
    sub = log_data["sub"]
    guid = log_data["guid"]
    resource_paths = log_data["resource_paths"]
    action = log_data["action"]
    protocol = log_data["protocol"]

    # Convert Unix timestamp to PostgreSQL timestamp format
    timestamp_sql = f"TO_TIMESTAMP({timestamp})"

    # Format resource_paths as a PostgreSQL array
    resource_paths_sql = (
        "ARRAY[" + ", ".join(f"'{path}'" for path in resource_paths) + "]"
    )

    sql_statement = f"""
    INSERT INTO presigned_url (request_url, status_code, timestamp, username, sub, guid, resource_paths, action, protocol)
    VALUES (
        '{request_url}',
        {status_code},
        {timestamp_sql},
        '{username}',
        {sub},
        '{guid}',
        {resource_paths_sql},
        '{action}',
        '{protocol}'
    );
    """.strip()
    connection.execute(sql_statement)


def create_partitioned_tables(connection):
    alembic_main(["--raiseerr", "downgrade", "base"])

    assert get_tables(connection) == {"alembic_version"}

    # Upgrade to the prior revision to test partitioned tables migrate correctly.
    alembic_main(["--raiseerr", "upgrade", "fd0510a0a9aa"])

    # Setup test data to test partitioned tables migrate as expected.
    guid = "dg.hello/abc"
    request_data = {
        "request_url": f"/request_data/download/{guid}",
        "status_code": 200,
        "timestamp": 1707345909,  # Wednesday, February 7, 2024 10:45:09 PM
        "username": "audit-service_user",
        "sub": 10,
        "guid": guid,
        "resource_paths": ["/my/resource/path1", "/path2"],
        "action": "download",
        "protocol": "s3",
    }
    create_presigned_url_log(connection, request_data)

    guid = "dg.hello/ab2c"
    request_data = {
        "request_url": f"/request_data/download/{guid}",
        "status_code": 200,
        "timestamp": 1709851509,  # Thursday, March 7, 2024 10:45:09 PM
        "username": "audit-service_user",
        "sub": 10,
        "guid": guid,
        "resource_paths": ["/my/resource/path1", "/path2"],
        "action": "download",
        "protocol": "s3",
    }
    create_presigned_url_log(connection, request_data)


def get_table_to_columns(connection):
    expected_presigned_url_tables = [
        "presigned_url",
        "presigned_url_2024_02",
        "presigned_url_2024_03",
    ]
    tables = get_tables(connection)
    table_to_columns = {}

    for table in expected_presigned_url_tables:
        assert table in tables
        cols = connection.execute(
            f"SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = 'public' AND table_name = '{table}'"
        )
        table_to_columns[table] = sorted([i for i in cols])
    return table_to_columns


def test_upgrade(connection, client):
    create_partitioned_tables(connection)

    # Test upgrade
    alembic_main(["--raiseerr", "upgrade", "head"])

    table_to_columns = get_table_to_columns(connection)

    expected_columns = [
        ("action", "character varying"),
        ("guid", "character varying"),
        ("jti", "character varying"),
        ("passport", "boolean"),
        ("protocol", "character varying"),
        ("request_url", "character varying"),
        ("resource_paths", "ARRAY"),
        ("status_code", "integer"),
        ("sub", "integer"),
        ("timestamp", "timestamp without time zone"),
        ("username", "character varying"),
    ]
    for columns in table_to_columns.values():
        assert columns == expected_columns


def test_downgrade(connection):
    create_partitioned_tables(connection)

    alembic_main(["--raiseerr", "upgrade", "head"])

    # Test Downgrade
    alembic_main(["--raiseerr", "downgrade", "fd0510a0a9aa"])

    table_to_columns = get_table_to_columns(connection)

    expected_columns = [
        ("action", "character varying"),
        ("guid", "character varying"),
        ("protocol", "character varying"),
        ("request_url", "character varying"),
        ("resource_paths", "ARRAY"),
        ("status_code", "integer"),
        ("sub", "integer"),
        ("timestamp", "timestamp without time zone"),
        ("username", "character varying"),
    ]
    for columns in table_to_columns.values():
        assert columns == expected_columns
