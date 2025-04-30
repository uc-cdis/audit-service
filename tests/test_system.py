from datetime import datetime
import pytest
from audit.db import get_data_access_layer
from sqlalchemy import text


def test_status_endpoint(client, db_session):
    res = client.get("/_status")
    assert res.status_code == 200


def test_version_endpoint(client):
    res = client.get("/_version")
    assert res.status_code == 200

    version = res.json().get("version")
    assert version


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
        async with get_data_access_layer() as dal:
            # insert a July 1789 entry. It should trigger the creation of a partition
            record_data["timestamp"] = date
            if category == "presigned_url":
                await dal.create_presigned_url_log(record_data)
            elif category == "login":
                await dal.create_login_log(record_data)

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
        print(f"Error getting table names: {e}")
        import traceback

        traceback.print_exc()
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

    # # after inserting the 3 entries, querying the table should return all 3
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
