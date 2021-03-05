from collections import defaultdict
from datetime import datetime
from fastapi import APIRouter, Body, Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel
from starlette.requests import Request
from starlette.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)
import time

from .. import logger
from ..auth import Auth
from ..config import config
from ..models import CATEGORY_TO_MODEL_CLASS, db


router = APIRouter()


@router.get("/log/{category}")
async def query_logs(
    request: Request,
    category: str,
    start: int = Query(None, description="Start timestamp"),
    stop: int = Query(None, description="Stop timestamp"),
    auth=Depends(Auth),
) -> list:
    """
    Queries the logs the current user has access to see. Returned data:

        {
            "nextTimeStamp": <timestamp or null>,
            "data": [<entry>, <entry>, ...],
        }

    This endpoint only returns up to a configured maximum number of entries
    at a time. If there are more entries to query, it returns a non-null
    "nextTimeStamp" which can be used to get the next page.

    The returned entries are ordered by increasing timestamp (least recent to
    most recent), so that new entries are at the end and there is no risk of
    skipping entries when getting the next page.

    Filters can be added as query strings. Accepted filters include all fields
    for the queried category, as well as the following special filters:
    - "groupby" to get counts
    - "start" to specify a starting timestamp (inclusive). Default: none
    - "stop" to specify an end timestamp (exclusive). Default: none

    If queries are time-boxed (depends on the configuration),
    ("stop" - "start") must be lower than the configured maximum.

    Without filters, this endpoint will return all data within the time-box.
    Add filters as query strings like this:

        GET /log/presigned_url?a=1&b=2

    This will match all records that have values containing all of:

        {"a": 1, "b": 2}

    Providing the same key with more than one value filters records whose
    value of the given key matches any of the given values. But values of
    different keys must all match. For example:

        GET /log/presigned_url?a=1&a2&b=3

    Matches these:

        {"a": 1, "b": 3}
        {"a": 2, "b": 3}

    But won't match these:

        {"a": 1, "b": 10}
        {"a": 10, "b": 3}

    groupby example:

        GET /log/presigned_url?a=1&groupby=b&groupby=c

        {"b": 1, "c": 2, "count": 5}
        {"b": 1, "c": 3, "count": 8}
    """
    logger.debug(f"Querying category {category}")

    # TODO if the category is `presigned_url`, we could implement more granular authz using the audit logs' `resource_paths`.
    resource_path = f"/services/audit/{category}"
    await auth.authorize("read", [resource_path])

    if category not in CATEGORY_TO_MODEL_CLASS:
        raise HTTPException(
            HTTP_400_BAD_REQUEST,
            f"Category '{category}' is not one of {list(CATEGORY_TO_MODEL_CLASS.keys())}",
        )
    model = CATEGORY_TO_MODEL_CLASS[category]

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

    query_params = defaultdict(set)
    groupby = set()
    for key, value in request.query_params.multi_items():
        if key in {"start", "stop"}:
            continue

        if key == "groupby":
            groupby.add(value)
            field = value
        else:
            query_params[key].add(value)
            field = key

        try:
            getattr(model, field)
        except AttributeError as e:
            raise HTTPException(
                HTTP_400_BAD_REQUEST,
                f"'{field}' is not allowed on category '{category}'",
            )

    if not config["QUERY_USERNAMES"] and (
        "username" in query_params or "username" in groupby
    ):
        raise HTTPException(
            HTTP_400_BAD_REQUEST,
            f"Querying by username is not allowed",
        )

    if groupby:
        logs = await query_logs_groupby(
            model, start_date, stop_date, query_params, groupby
        )
        next_timestamp = None
    else:
        logs, next_timestamp = await query_logs(
            model, start_date, stop_date, query_params
        )

    if not config["QUERY_USERNAMES"]:
        # TODO: excluding usernames from the query might be more efficient
        for log in logs:
            if "username" in log:
                del log["username"]

    return {
        "nextTimeStamp": next_timestamp,
        "data": logs,
    }


def add_filters(model, query, query_params, start_date=None, stop_date=None):
    if start_date:
        query = query.where(model.timestamp >= start_date)
    if stop_date:
        query = query.where(model.timestamp < stop_date)
    for field, values in query_params.items():
        # TODO for resource_paths, implement filtering in a way that
        # would return "/A/B" when querying "/A".
        if hasattr(getattr(model, field).type, "item_type"):  # ARRAY
            query = query.where(getattr(model, field).overlap(values))
        else:
            query = query.where(db.or_(getattr(model, field) == v for v in values))
    return query


async def query_logs(model, start_date, stop_date, query_params):
    # get all logs matching the filters and apply the page size limit
    query = add_filters(model, model.query, query_params, start_date, stop_date)
    query = query.order_by(model.timestamp)
    limit = config["QUERY_PAGE_SIZE"]
    query = query.limit(limit)
    logs = await query.order_by(model.timestamp).gino.all()

    if not logs:
        return [], None

    # if there are more logs with the same timestamp as the last queried
    # log, also return them
    last_timestamp = logs[-1].timestamp
    all_timestamps_query = add_filters(
        model, model.query, query_params, start_date, stop_date
    )
    all_timestamps_query = all_timestamps_query.order_by(model.timestamp)
    extra_logs = await all_timestamps_query.where(
        model.timestamp == last_timestamp
    ).gino.all()

    if len(extra_logs) > 1:
        # don't return duplicate logs: remove from `logs` items that are
        # in `extra_logs` before merging the 2
        logs = [l for l in logs if l.timestamp != last_timestamp]
        logs.extend(extra_logs)

    # get the next timestamp
    next_log = await all_timestamps_query.where(
        model.timestamp > last_timestamp
    ).gino.first()
    if next_log:
        next_timestamp = int(datetime.timestamp(next_log.timestamp))
    else:
        next_timestamp = None

    logs = [e.to_dict() for e in logs]
    return logs, next_timestamp


async def query_logs_groupby(model, start_date, stop_date, query_params, groupby):
    select_list = [getattr(model, field) for field in groupby]
    select_list.append(db.func.count(model.username).label("count"))
    query = db.select(select_list)
    for field in groupby:
        query = query.group_by(getattr(model, field))
    query = add_filters(model, query, query_params, start_date, stop_date)
    logs = await query.gino.all()
    return logs


def init_app(app: FastAPI):
    app.include_router(router, tags=["Query"])
