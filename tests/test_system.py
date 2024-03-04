from datetime import datetime
import pytest

from audit.models import db


def test_status_endpoint(client):
    res = client.get("/_status")
    assert res.status_code == 200


def test_version_endpoint(client):
    res = client.get("/_version")
    assert res.status_code == 200

    version = res.json().get("version")
    assert version

@pytest.mark.skip(reason="Gino and new version of pytest-asyncio doesn't play nicely so this test is doomed, but the functionality of the app is not affected")
@pytest.mark.asyncio
async def test_table_partitioning():
    """
    We can't create logs by using the `client` fixture because of this issue
    https://github.com/encode/starlette/issues/440, so inserting directly
    into the DB instead.
    """
    category = "presigned_url"

    async def get_table_names():
        tables_data = await db.all(
            db.text(
                f"select relname from pg_catalog.pg_class where relname like '{category}%'"
            )
        )
        return [table_data[0] for table_data in tables_data]

    insert_stmt = 'insert into {}("request_url", "status_code", "timestamp", "username", "sub", "guid", "resource_paths", "action") values (\'request_url\', 200, \'{}\', \'user1\', 10, \'guid\', ARRAY[\'/my/resource/path1\', \'/path2\'], \'action\')'

    # initially, we should only have 1 table, no partitions
    assert await get_table_names() == [category]

    # insert a July 1789 entry. It should trigger the creation of a partition
    await db.scalar(db.text(insert_stmt.format(category, "1789_07_14")))
    assert await get_table_names() == [category, f"{category}_1789_07"]

    # insert another July 1789 entry. It should go in the existing partition
    await db.scalar(db.text(insert_stmt.format(category, "1789_07_30")))
    assert await get_table_names() == [category, f"{category}_1789_07"]

    # insert a Jan 2021 entry. It should trigger the creation of a partition
    await db.scalar(db.text(insert_stmt.format(category, "2021_01_05")))
    assert await get_table_names() == [
        category,
        f"{category}_1789_07",
        f"{category}_2021_01",
    ]

    # after inserting the 3 entries, querying the table should return all 3
    data = await db.all(db.text(f"select username, timestamp from {category}"))
    assert data == [
        ("user1", datetime(1789, 7, 14)),
        ("user1", datetime(1789, 7, 30)),
        ("user1", datetime(2021, 1, 5)),
    ]

    # there should be no data in the main table itself. All the data is in
    # the partitions
    data = await db.all(db.text(f"select username, timestamp from only {category}"))
    assert data == []

    # querying the partition tables should only return the entries whose
    # timestamp is in each partition's range
    data = await db.all(db.text(f"select username, timestamp from {category}_1789_07"))
    assert data == [("user1", datetime(1789, 7, 14)), ("user1", datetime(1789, 7, 30))]

    data = await db.all(db.text(f"select username, timestamp from {category}_2021_01"))
    assert data == [("user1", datetime(2021, 1, 5))]
