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
            "data": [<entry>, <entry>, ...],
            "nextTimeStamp": <timestamp or null>
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
    - "start" to specify a starting timestamp. Default: the configured maximum
    - "stop" to specify an end timestamp. Default: now

    Queries are time-boxed: ("stop" - "start") must be lower than the
    configured maximum.

    Without filters, this will return all data within the time-box. Add
    filters as query strings like this:

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

    timebox_max_seconds = config["QUERY_TIMEBOX_MAX_DAYS"] * 86400
    if not stop:
        stop = int(time.time())
    if not start:
        start = max(stop - timebox_max_seconds, 0)

    try:
        start_date = datetime.fromtimestamp(start)
        stop_date = datetime.fromtimestamp(stop)
    except Exception as e:
        msg = f"Unable to convert timestamps '{start}' and '{stop}' to datetimes"
        logger.error(f"{msg}:\n{e}")
        raise HTTPException(HTTP_400_BAD_REQUEST, msg)

    if start > stop:
        raise HTTPException(
            HTTP_400_BAD_REQUEST,
            f"The start timestamp '{start}' ({start_date}) should be before the stop timestamp '{stop}' ({stop_date})",
        )

    if stop - start > timebox_max_seconds:
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


def add_filters(model, query, start_date, stop_date, query_params):
    query = query.where(model.timestamp >= start_date).where(
        model.timestamp < stop_date
    )
    for field, values in query_params.items():
        # TODO for resource_paths, implement filtering in a way that
        # would return "/A/B" when querying "/A".
        if hasattr(getattr(model, field).type, "item_type"):  # ARRAY
            query = query.where(getattr(model, field).overlap(values))
        else:
            query = query.where(db.or_(getattr(model, field) == v for v in values))
    return query


async def query_logs(model, start_date, stop_date, query_params):
    query = model.query
    query = add_filters(model, query, start_date, stop_date, query_params)
    query = query.order_by(model.timestamp)
    limit = config["QUERY_PAGE_SIZE"]
    # get 1 more log than the limit, so we can return `nextTimeStamp`:
    query = query.limit(limit + 1)
    logs = await query.gino.all()
    if len(logs) > limit:
        next_timestamp = int(datetime.timestamp(logs[-1].timestamp))
        logs = logs[:-1]
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
    query = add_filters(model, query, start_date, stop_date, query_params)
    logs = await query.gino.all()
    return logs


def init_app(app: FastAPI):
    app.include_router(router, tags=["Query"])
