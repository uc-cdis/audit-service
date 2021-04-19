import asyncio
import boto3
import json
import traceback

from .config import config
from .models import CATEGORY_TO_MODEL_CLASS
from .routes.maintain import insert_row, validate_presigned_url_log, validate_login_log


async def process_log(data):
    # check log category
    category = data.pop("category")
    assert category and category in CATEGORY_TO_MODEL_CLASS, "TODO error msg"

    # validate log
    if category == "presigned_url":
        validate_presigned_url_log(data)
    elif category == "login":
        validate_login_log(data)

    # insert log in DB
    await insert_row(category, data)


async def pull_from_queue_loop():
    # TODO validate QUEUE_CONFIG
    sqs = boto3.client(
        "sqs",
        region_name=config["QUEUE_CONFIG"]["region"],
        aws_access_key_id=config["QUEUE_CONFIG"]["aws_access_key_id"],
        aws_secret_access_key=config["QUEUE_CONFIG"]["aws_secret_access_key"],
    )
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
            print(f"ERROR: {e}")  # TODO use logger instead of print

        for message in messages:
            data = json.loads(message["Body"])
            receipt_handle = message['ReceiptHandle']
            try:
                await process_log(data)
            except Exception as e:
                failed = True
                print(f"ERROR: {e}")  # TODO use logger instead of print
                traceback.print_exc()
            else:
                # delete message from queue once successfully processed
                sqs.delete_message(
                    QueueUrl=config["QUEUE_CONFIG"]["sqs_url"],
                    ReceiptHandle=receipt_handle
                )

        if not messages or failed:  # queue is empty: sleep
            print("sleeping...")
            await asyncio.sleep(3)  # TODO remove
            # await asyncio.sleep(config["PULL_FREQUENCY_SECONDS"])
