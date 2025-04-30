import json
import time
import pytest
from sqlalchemy import text

from audit.config import config
from audit.models import CATEGORY_TO_MODEL_CLASS
from audit.pull_from_queue import process_log, pull_from_queue


async def get_table_results(db_session, table_name):
    """
    Helper function to get the results from a table.
    """
    result = await db_session.execute(text(f"select * from {table_name}"))
    return result.fetchall()


@pytest.mark.asyncio
async def test_process_log_success(db_session):
    """
    Test that `process_log` properly inserts audit logs into the DB.

    We can't query logs by using the `client` fixture because of this issue
    https://github.com/encode/starlette/issues/440, so querying the DB directly
    instead.
    """
    # create a log
    guid = "dg.hello/abc"
    category = "presigned_url"
    timestamp = int(time.time())
    message_data = {
        "category": category,
        "request_url": f"/request_data/download/{guid}",
        "status_code": 200,
        "username": "audit-service_user",
        "sub": 10,
        "guid": guid,
        "resource_paths": ["/my/resource/path1", "/path2"],
        "action": "download",
        "protocol": "s3",
    }
    await process_log(message_data, timestamp)

    data = await get_table_results(db_session, table_name=category)
    assert len(data) == 1, f"1 row should have been inserted in table '{category}'"

    assert data[0] == (
        message_data["request_url"],
        message_data["status_code"],
        message_data["timestamp"],
        message_data["username"],
        message_data["sub"],
        guid,
        message_data["resource_paths"],
        message_data["action"],
        message_data["protocol"],
        1,  # auto-incremented id
    )


@pytest.mark.asyncio
async def test_process_log_failure(db_session):
    """
    Test that `process_log` properly rejects bad audit logs.

    We can't query logs by using the `client` fixture because of this issue
    https://github.com/encode/starlette/issues/440, so querying the DB directly
    instead.
    """
    # attempt to create a log with a bad category
    guid = "dg.hello/abc"
    category = "this_does_not_exist"
    timestamp = int(time.time())
    message_data = {
        "category": category,
        "request_url": f"/request_data/download/{guid}",
        "status_code": 200,
        "username": "audit-service_user",
        "sub": 10,
        "guid": guid,
        "resource_paths": ["/my/resource/path1", "/path2"],
        "action": "download",
        "protocol": "s3",
    }
    with pytest.raises(AssertionError, match=f"Unknown log category {category}"):
        await process_log(message_data, timestamp)

    for category in CATEGORY_TO_MODEL_CLASS:
        data = await get_table_results(db_session, table_name=category)
        assert (
            len(data) == 0
        ), f"Nothing should have been inserted in table '{category}'"

    # attempt to create a log with missing fields
    category = "presigned_url"
    message_data = {
        "category": category,
        "request_url": f"/request_data/download/{guid}",
        "status_code": 200,
        "username": "audit-service_user",
        "action": "download",
    }
    with pytest.raises(Exception, match="null value in column"):
        await process_log(message_data, timestamp)

    # make sure `process_log` did not insert any rows
    for category in CATEGORY_TO_MODEL_CLASS:
        data = await get_table_results(db_session, table_name=category)
        assert (
            len(data) == 0
        ), f"Nothing should have been inserted in table '{category}'"


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
        print(f"Messages: {messages}")
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
