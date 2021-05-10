import asyncio
import boto3
import json
import traceback

from . import logger
from .config import config
from .models import CATEGORY_TO_MODEL_CLASS
from .routes.maintain import insert_row, validate_presigned_url_log, validate_login_log


async def process_log(data):
    # check log category
    category = data.pop("category")
    assert (
        category and category in CATEGORY_TO_MODEL_CLASS
    ), f"Unknown log category {category}"

    # validate log
    if category == "presigned_url":
        validate_presigned_url_log(data)
    elif category == "login":
        validate_login_log(data)

    # insert log in DB
    await insert_row(category, data)


async def pull_from_queue_loop():
    logger.info("Starting to pull from queue...")
    sqs = boto3.client(
        "sqs",
        region_name=config["QUEUE_CONFIG"]["region"],
        aws_access_key_id=config["QUEUE_CONFIG"].get("aws_access_key_id"),
        aws_secret_access_key=config["QUEUE_CONFIG"].get("aws_secret_access_key"),
    )
    sleep_time = config["PULL_FREQUENCY_SECONDS"]
    while True:
        failed = False
        messages = []
        try:
            response = sqs.receive_message(
                QueueUrl=config["QUEUE_CONFIG"]["sqs_url"],
                MaxNumberOfMessages=10,  # 10 is the max
                # TODO check below fields
                # VisibilityTimeout=0,
                # WaitTimeSeconds=0
            )
            messages = response.get("Messages", [])
        except Exception as e:
            failed = True
            logger.error(f"Error pulling from queue: {e}")
            traceback.print_exc()

        for message in messages:
            data = json.loads(message["Body"])
            receipt_handle = message["ReceiptHandle"]
            try:
                await process_log(data)
            except Exception as e:
                failed = True
                logger.error(f"Error processing audit log: {e}")
                traceback.print_exc()
            else:
                # delete message from queue once successfully processed
                try:
                    sqs.delete_message(
                        QueueUrl=config["QUEUE_CONFIG"]["sqs_url"],
                        ReceiptHandle=receipt_handle,
                    )
                except Exception as e:
                    failed = True
                    logger.error(f"Error deleting message from queue: {e}")
                    traceback.print_exc()

        if not messages or failed:  # queue is empty: sleep
            logger.info(f"Sleeping for {sleep_time} seconds...")
            await asyncio.sleep(sleep_time)
