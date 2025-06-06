from datetime import datetime
from fastapi import HTTPException
from starlette.status import HTTP_400_BAD_REQUEST
import time

from .. import logger
from ..config import config


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
        # to rows without timestamp, and is defaulted to None.
        # Setting it to the current date and time.
        data["timestamp"] = datetime.now()


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


def validate_and_normalize_times(start, stop):
    """
    Validate the `start` and `stop` parameters, raise exceptions if the
    validation fails, and return:
    - start: if parameter `start` was None, override with default
    - start_date: `start` as datetime
    - stop: if parameter `stop` was None, override with default
    - stop_date: `stop` as datetime
    """
    # don't just overwrite `stop` with the current timestamp, because the
    # `stop` param is exclusive and when we don't specify it, we want to
    # be able to query logs we just created
    effective_stop = stop or int(time.time())

    timebox_max_seconds = None
    if config["QUERY_TIMEBOX_MAX_DAYS"]:
        timebox_max_seconds = config["QUERY_TIMEBOX_MAX_DAYS"] * 86400

        # if the query is time-boxed and `stop` was not specified,
        # set `stop` to the newest allowed timestamp
        if start and not stop:
            stop = start + timebox_max_seconds
            effective_stop = stop

        # if the query is time-boxed and `start` was not specified,
        # set `start` to the oldest allowed timestamp
        if not start:
            start = max(effective_stop - timebox_max_seconds, 0)

    start_date = None
    stop_date = None
    try:
        if start:
            start_date = datetime.fromtimestamp(start)
        if stop:
            stop_date = datetime.fromtimestamp(stop)
    except Exception as e:
        msg = f"Unable to convert timestamps '{start}' and/or '{stop}' to datetimes"
        logger.error(f"{msg}:\n{e}")
        raise HTTPException(HTTP_400_BAD_REQUEST, msg)

    if start and stop and start > stop:
        raise HTTPException(
            HTTP_400_BAD_REQUEST,
            f"The start timestamp '{start}' ({start_date}) should be before the stop timestamp '{stop}' ({stop_date})",
        )

    if timebox_max_seconds and effective_stop - start > timebox_max_seconds:
        raise HTTPException(
            HTTP_400_BAD_REQUEST,
            f"The difference between the start timestamp '{start}' ({start_date}) and the stop timestamp '{stop}' ({stop_date}) is greater than the configured maximum of {config['QUERY_TIMEBOX_MAX_DAYS']} days",
        )

    return start, start_date, stop, stop_date
