import asyncio
import boto3
import json
import traceback

from . import logger
from .config import config
from .models import CATEGORY_TO_MODEL_CLASS
from .utils.route_utils import validate_presigned_url_log, validate_login_log
from .db import get_data_access_layer


async def process_log(
    data,
    timestamp,
):
    # check log category
    category = data.pop("category")
    assert (
        category and category in CATEGORY_TO_MODEL_CLASS
    ), f"Unknown log category {category}"

    # if the timestamp was not provided, default to the message's SentTimestamp
    if not data.get("timestamp"):
        data["timestamp"] = timestamp

    async with get_data_access_layer() as dal:
        # validate log
        if category == "presigned_url":
            validate_presigned_url_log(data)
            dal.create_presigned_url_log(data)
        elif category == "login":
            validate_login_log(data)
            dal.create_login_log(data)

    # insert log in DB
    # await insert_row(category, data)


async def pull_from_queue(sqs):
    failed = False
    messages = []
    try:
        response = sqs.receive_message(
            QueueUrl=config["QUEUE_CONFIG"]["aws_sqs_config"]["sqs_url"],
            MaxNumberOfMessages=10,  # 10 is the max allowed by AWS
            AttributeNames=["SentTimestamp"],
        )
        messages = response.get("Messages", [])
    except Exception as e:
        failed = True
        logger.error(f"Error pulling from queue: {e}")
        traceback.print_exc()

    for message in messages:
        data = json.loads(message["Body"])
        receipt_handle = message["ReceiptHandle"]
        # when the message was sent to the queue
        sent_timestamp = message["Attributes"]["SentTimestamp"]
        timestamp = int(int(sent_timestamp) / 1000)  # ms to s
        try:
            await process_log(data, timestamp)
        except Exception as e:
            failed = True
            logger.error(f"Error processing audit log: {e}")
            traceback.print_exc()
        else:
            # delete message from queue once successfully processed
            try:
                sqs.delete_message(
                    QueueUrl=config["QUEUE_CONFIG"]["aws_sqs_config"]["sqs_url"],
                    ReceiptHandle=receipt_handle,
                )
            except Exception as e:
                failed = True
                logger.error(f"Error deleting message from queue: {e}")
                traceback.print_exc()

    # if the queue is empty, or we failed to process a message: sleep
    should_sleep = not messages or failed
    return should_sleep


async def pull_from_queue_loop():
    """
    Note that `pull_from_queue_loop` and `pull_from_queue` only handle
    AWS SQS right now.
    """
    logger.info("Starting to pull from queue...")
    aws_sqs_config = config["QUEUE_CONFIG"]["aws_sqs_config"]
    # we know the cred is in AWS_CREDENTIALS (see `AuditServiceConfig.validate`)
    aws_creds = (
        config["AWS_CREDENTIALS"][aws_sqs_config["aws_cred"]]
        if "aws_cred" in aws_sqs_config and aws_sqs_config["aws_cred"]
        else {}
    )
    if (
        not aws_creds
        and "aws_access_key_id" in aws_sqs_config
        and "aws_secret_access_key" in aws_sqs_config
    ):
        # for backwards compatibility
        aws_creds = {
            "aws_access_key_id": aws_sqs_config["aws_access_key_id"],
            "aws_secret_access_key": aws_sqs_config["aws_secret_access_key"],
        }
    sqs = boto3.client(
        "sqs",
        region_name=aws_sqs_config["region"],
        aws_access_key_id=aws_creds.get("aws_access_key_id"),
        aws_secret_access_key=aws_creds.get("aws_secret_access_key"),
    )
    sleep_time = config["PULL_FREQUENCY_SECONDS"]
    while True:
        should_sleep = await pull_from_queue(sqs)
        if should_sleep:
            logger.info(f"Sleeping for {sleep_time} seconds...")
            await asyncio.sleep(sleep_time)
