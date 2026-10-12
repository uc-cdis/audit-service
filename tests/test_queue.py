import copy
import json
import time
import pytest
from sqlalchemy import text

from audit.config import config
from audit.models import CATEGORY_TO_MODEL_CLASS
from audit.pull_from_queue import process_log, pull_from_queue
from audit import logger


async def get_table_results(db_session, table_name):
    """
    Helper function to get the results from a table.
    """
    result = await db_session.execute(text(f"select * from {table_name}"))
    return result.fetchall()


LOG_DATA = {
    "presigned_url": {
        "request_url": "/request_data/download/dg.hello/abc",
        "status_code": 200,
        "username": "audit-service_user",
        "sub": 10,
        "guid": "dg.hello/abc",
        "resource_paths": ["/my/resource/path1", "/path2"],
        "action": "download",
        "protocol": "s3",
        "additional_data": {"test_key": "test_val"},
    },
    "login": {
        "request_url": "/login",
        "status_code": 200,
        "username": "audit-service_user",
        "sub": 10,
        "idp": "google",
        "ip": "1.2.3.4",
        "additional_data": {"test_key": "test_val"},
    },
    "export_data": {
        "request_url": "/export",
        "status_code": 200,
        "username": "audit-service_user",
        "sub": 10,
        "type": "pfb_export",
        "additional_data": {"test_key": "test_val"},
    },
}

# a NOT NULL column for each category, used to test missing fields
REQUIRED_FIELD = {"presigned_url": "guid", "login": "idp", "export_data": "type"}


async def assert_no_rows_inserted(db_session):
    for category in CATEGORY_TO_MODEL_CLASS:
        data = await get_table_results(db_session, table_name=category)
        assert (
            len(data) == 0
        ), f"Nothing should have been inserted in table '{category}'"


@pytest.mark.asyncio
@pytest.mark.parametrize("category", list(LOG_DATA))
async def test_process_log_success(db_session, category):
    """
    Test that `process_log` properly inserts audit logs into the DB.

    We can't query logs by using the `client` fixture because of this issue
    https://github.com/encode/starlette/issues/440, so querying the DB directly
    instead.
    """
    message_data = {"category": category, **copy.deepcopy(LOG_DATA[category])}
    await process_log(message_data, int(time.time()))

    result = await db_session.execute(text(f"select * from {category}"))
    rows = [dict(row._mapping) for row in result]
    assert len(rows) == 1, f"1 row should have been inserted in table '{category}'"
    assert rows[0]["id"] == 1  # auto-incremented id

    # `process_log` mutates `message_data` (pops category, converts timestamp)
    for key, value in message_data.items():
        assert rows[0][key] == value, f"Unexpected value for '{key}'"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "category_data",
    [{}, {"category": None}, {"category": "this_does_not_exist"}],
    ids=["missing", "none", "unknown"],
)
async def test_process_log_unknown_category(db_session, category_data):
    """
    Test that `process_log` rejects logs with a missing or unknown category.
    """
    message_data = {**copy.deepcopy(LOG_DATA["login"]), **category_data}
    with pytest.raises(AssertionError, match="Unknown log category"):
        await process_log(message_data, int(time.time()))

    await assert_no_rows_inserted(db_session)


@pytest.mark.asyncio
@pytest.mark.parametrize("category", list(LOG_DATA))
async def test_process_log_missing_fields(db_session, category):
    """
    Test that `process_log` rejects logs that are missing required fields.
    """
    message_data = {"category": category, **copy.deepcopy(LOG_DATA[category])}
    del message_data[REQUIRED_FIELD[category]]
    with pytest.raises(Exception, match="null value in column"):
        await process_log(message_data, int(time.time()))

    await assert_no_rows_inserted(db_session)


class TestQueue:
    """
    This class mocks the boto3 SQS client
    """

    def __init__(self, messages=None) -> None:
        guid = "dg.hello/abc"
        if messages is None:
            self.messages = [
                {
                    "category": "presigned_url",
                    "request_url": f"/request_data/download/{guid}",
                    "status_code": 200,
                    "timestamp": int(time.time()),
                    "username": "audit-service_user",
                    "sub": 10,
                    "guid": guid,
                    "resource_paths": ["/my/resource/path1", "/path2"],
                    "action": "download",
                    "protocol": "s3",
                }
            ]
        else:
            self.messages = messages

    def receive_message(self, QueueUrl, MaxNumberOfMessages, AttributeNames):
        n_messages = min(MaxNumberOfMessages, len(self.messages))
        messages = [
            {
                "Body": json.dumps(message),
                "ReceiptHandle": "123",
                "Attributes": {"SentTimestamp": int(time.time())},
            }
            for message in self.messages[:n_messages]
        ]
        return {"Messages": messages}

    def delete_message(self, QueueUrl, ReceiptHandle):
        pass


TestQueue.__test__ = False  # prevent pytest from trying to collect it


@pytest.mark.asyncio
async def test_pull_from_queue_success(monkeypatch, db_session):
    """
    Test that `pull_from_queue` properly processes messages in the queue.
    """
    queue = TestQueue()
    monkeypatch.setitem(
        config, "QUEUE_CONFIG", {"aws_sqs_config": {"sqs_url": "some_queue_url"}}
    )
    monkeypatch.setitem(config, "PULL_FREQUENCY_SECONDS", 0)

    should_sleep = await pull_from_queue(queue)
    # `should_sleep` is True if the queue contains no messages (not the
    # case here) or if we failed to process a message (should not happen)
    assert not should_sleep, "Failed to process audit logs"

    # make sure `process_log` inserted a row
    data = await get_table_results(db_session, table_name="presigned_url")
    assert len(data) == 1, f"1 row should have been inserted in table 'presigned_url'"


@pytest.mark.asyncio
async def test_pull_from_queue_failure(monkeypatch, db_session):
    """
    Test that `pull_from_queue` fails when it should and sleeps when it should.
    """
    bad_message = {
        "category": "presigned_url",
        "request_url": f"/request_data/download/guid",
        "status_code": 200,
        "username": "audit-service_user",
        "action": "download",
    }
    for messages in [[bad_message], []]:
        logger.debug(f"Messages: {messages}")
        queue = TestQueue(messages=messages)
        monkeypatch.setitem(
            config, "QUEUE_CONFIG", {"aws_sqs_config": {"sqs_url": "some_queue_url"}}
        )
        monkeypatch.setitem(config, "PULL_FREQUENCY_SECONDS", 0)

        should_sleep = await pull_from_queue(queue)
        # `should_sleep` is True if the queue contains no messages (not the
        # case here) or if we failed to process a message (should happen)
        if not messages:
            err_msg = "Should not have processed any audit logs"
        else:
            err_msg = "Should have failed to process audit logs"
        assert should_sleep, err_msg

        # make sure `process_log` did not insert any rows
        data = await get_table_results(db_session, table_name="presigned_url")
        assert (
            len(data) == 0
        ), f"Nothing should have been inserted in table 'presigned_url'"
