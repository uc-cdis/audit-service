from datetime import datetime
import pytest
from audit.db import get_data_access_layer
from sqlalchemy import text
from typing import Union
from audit import logger
from audit.models import (
    CATEGORY_TO_MODEL_CLASS,
    CreateLoginLogInput,
    CreatePresignedUrlLogInput,
)
from audit.routes.system import (
    CURRENT_SCHEMA_VERSIONS,
    _pretty_type,
    _model_fingerprint,
)


@pytest.mark.parametrize(
    "category, pydantic_class",
    [
        ("login", CreateLoginLogInput),
        ("presigned_url", CreatePresignedUrlLogInput),
    ],
)
def test_model_fingerprint(category, pydantic_class):
    """
    Test to enforce that models and CURRENT_SCHEMA_VERSIONS are aligned.
    Changes to models will trigger a test failure here until fingerprint is updated.
    """
    assert CURRENT_SCHEMA_VERSIONS[category]["fingerprint"] == _model_fingerprint(
        pydantic_class
    )


@pytest.mark.parametrize(
    "annotation, expected",
    [
        (str, "str"),
        (int, "int"),
        (list[str], "list"),
        (Union[str, None], "str?"),
    ],
)
def test_pretty_type(annotation, expected):
    assert _pretty_type(annotation) == expected


def test_status_endpoint(client, db_session):
    res = client.get("/_status")
    assert res.status_code == 200


def test_version_endpoint(client):
    res = client.get("/_version")
    assert res.status_code == 200

    version = res.json().get("version")
    assert version


def test_schema_endpoint_basic(client):
    """
    Ensure schema endpoint returns version and model info for curent audit log types
    """
    resp = client.get("/_schema")
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert set(body) == {"login", "presigned_url"}

    for category, info in body.items():
        assert isinstance(info["version"], float)
        assert isinstance(info["model"], dict)


def test_schema_endpoint_login_details(client):
    """
    Ensure schema endpoint returns current version and fields types
    """
    log_fields = ["request_url", "status_code", "timestamp", "username", "sub"]
    login_fields = ["idp", "fence_idp", "shib_idp", "client_id", "ip"]
    presigned_url_fields = ["guid", "resource_paths", "action", "protocol"]

    resp = client.get("/_schema")
    body = resp.json()
    login_schema = body["login"]
    presigned_url_schema = body["presigned_url"]

    assert login_schema["version"] == 2.0
    model = login_schema["model"]

    optional_login_fields = ["fence_idp", "shib_idp", "client_id", "ip"]
    for field in log_fields + login_fields:
        assert field in model
        if field in optional_login_fields:
            assert model[field].endswith("?")

    assert presigned_url_schema["version"] == 1.0
    model = presigned_url_schema["model"]

    for field in log_fields + presigned_url_fields:
        assert field in model


def test_category_version_schema_alignment(client):
    """
    Tests that every category declared in CATEGORY_TO_MODEL_CLASS:
    - Has corresponding entry in CURRENT_SCHEMA_VERSIONS
    - Appears in the /_schema endpoint response with the same version.
    """
    assert set(CATEGORY_TO_MODEL_CLASS) == set(
        CURRENT_SCHEMA_VERSIONS
    ), "Expected all categories in CATEGORY_TO_MODEL_CLASS to have an entry in CURRENT_SCHEMA_VERSIONS"

    resp = client.get("/_schema")
    assert resp.status_code == 200, resp.text
    schema_body = resp.json()

    assert set(schema_body) == set(
        CATEGORY_TO_MODEL_CLASS
    ), "Expected all categories in CATEGORY_TO_MODEL_CLASS to appear in /_schema response"

    for category in CATEGORY_TO_MODEL_CLASS:
        expected_version = CURRENT_SCHEMA_VERSIONS[category]["version"]
        assert schema_body[category]["version"] == expected_version


@pytest.mark.asyncio
@pytest.mark.parametrize("category", ["login", "presigned_url"])
async def test_table_partitioning(db_session, category):
    """
    We can't create logs by using the `client` fixture because of this issue
    https://github.com/encode/starlette/issues/440, so inserting directly
    into the DB instead.
    """

    async def _get_table_names():
        result = await db_session.execute(
            text(
                f"select relname from pg_catalog.pg_class where relname like '{category}%' and relkind='r'"
            )
        )
        tables_data = result.fetchall()
        return [table_data[0] for table_data in tables_data]

    async def _get_records_from_table(table_name, use_only=False):

        result = await db_session.execute(
            text(
                f"select username, timestamp from only {table_name}"
                if use_only
                else f"select username, timestamp from {table_name}"
            )
        )
        return result.fetchall()

    async def _insert_record(record_data, date: datetime = None):
        async for data_access_layer in get_data_access_layer():
            record_data["timestamp"] = date
            if category == "presigned_url":
                await data_access_layer.create_presigned_url_log(record_data)
            elif category == "login":
                await data_access_layer.create_login_log(record_data)

    row_data = {
        "presigned_url": {
            "request_url": "request_url",
            "status_code": 200,
            "timestamp": None,
            "username": "user1",
            "sub": 10,
            "guid": "guid",
            "resource_paths": ["/my/resource/path1", "/path2"],
            "action": "action",
        },
        "login": {
            "request_url": "request_url",
            "status_code": 200,
            "timestamp": None,
            "username": "user1",
            "sub": 10,
            "idp": "idp",
            "fence_idp": None,
            "shib_idp": None,
            "client_id": None,
        },
    }

    # initially, we should only have 1 table, no partitions
    try:
        table_names = await _get_table_names()
    except Exception as e:
        logger.error(f"Error getting table names: {e}")
        raise
    assert table_names == [category]

    # insert a July 1789 entry. It should trigger the creation of a partition
    await _insert_record(row_data[category], datetime(1789, 7, 14))
    assert await _get_table_names() == [category, f"{category}_1789_07"]

    # insert another July 1789 entry. It should go in the existing partition
    await _insert_record(row_data[category], datetime(1789, 7, 30))
    assert await _get_table_names() == [category, f"{category}_1789_07"]

    # insert a Jan 2021 entry. It should trigger the creation of a partition
    await _insert_record(row_data[category], datetime(2021, 1, 5))
    assert await _get_table_names() == [
        category,
        f"{category}_1789_07",
        f"{category}_2021_01",
    ]

    # after inserting the 3 entries, querying the table should return all 3
    data = await _get_records_from_table(category)
    assert data == [
        ("user1", datetime(1789, 7, 14)),
        ("user1", datetime(1789, 7, 30)),
        ("user1", datetime(2021, 1, 5)),
    ]

    # there should be no data in the main table itself. All the data is in
    # the partitions
    data = await _get_records_from_table(category, use_only=True)
    assert data == []

    # querying the partition tables should only return the entries whose
    # timestamp is in each partition's range
    data = await _get_records_from_table(f"{category}_1789_07")
    assert data == [("user1", datetime(1789, 7, 14)), ("user1", datetime(1789, 7, 30))]

    data = await _get_records_from_table(f"{category}_2021_01")
    assert data == [("user1", datetime(2021, 1, 5))]
