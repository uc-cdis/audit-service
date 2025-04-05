from datetime import datetime
from fastapi import HTTPException
from starlette.status import HTTP_400_BAD_REQUEST

from .. import logger


def handle_timestamp(data):
    """
    If the timestamp is omitted from the request body, we use the current date
    and time. In most cases, services should NOT provide a timestamp when
    creating audit logs. The timestamp is only accepted in log creation
    requests to allow populating the audit database with historical data, for
    example by parsing historical logs from before the Audit Service was
    deployed to a Data Commons.
    """
    if "timestamp" not in data:
        return
    if data["timestamp"]:
        # we take a timestamp as input, but store a datetime in the database
        try:
            data["timestamp"] = datetime.fromtimestamp(data["timestamp"])
        except Exception as e:
            raise HTTPException(
                HTTP_400_BAD_REQUEST,
                f"Invalid timestamp '{data['timestamp']}'",
            )
    else:
        # when hitting the API endpoint, the "timestamp" key always exists
        # because it's defined in `CreateLogInput`. It is automatically added
        # to rows without timestamp, but we have to remove it from the dict
        # before inserting in the DB
        del data["timestamp"]


def validate_presigned_url_log(data):
    logger.debug(f"Creating `presigned_url` audit log. Received body: {data}")

    allowed_actions = ["download", "upload"]
    # `action` is a required field", but that's checked during the DB insert
    if "action" in data and data["action"] not in allowed_actions:
        raise HTTPException(
            HTTP_400_BAD_REQUEST,
            f"Action '{data['action']}' is not allowed ({allowed_actions})",
        )

    handle_timestamp(data)


def validate_login_log(data):
    logger.debug(f"Creating `login` audit log. Received body: {data}")
    handle_timestamp(data)
