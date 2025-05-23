from collections import defaultdict
from datetime import datetime
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from starlette.requests import Request
from starlette.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
)

from .. import logger
from ..auth import Auth
from ..config import config
from ..models import CATEGORY_TO_MODEL_CLASS
from ..db import DataAccessLayer, get_data_access_layer_dependency
from ..utils.validate_utils import validate_and_normalize_times


router = APIRouter()


@router.get("/log/{category}", status_code=HTTP_200_OK)
async def query_logs(
    request: Request,
    category: str,
    start: int = Query(None, description="Start timestamp"),
    stop: int = Query(None, description="Stop timestamp"),
    auth=Depends(Auth),
    data_access_layer: DataAccessLayer = Depends(get_data_access_layer_dependency),
) -> dict:
    """
    Queries the logs the current user has access to see. Returned data:

        {
            "nextTimeStamp": <timestamp or null>,
            "data": [<entry>, <entry>, ...] OR int if using `count` param,
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
    - "count" to get the number of rows instead of a list
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

        GET /log/presigned_url?a=1&a=2&b=3

    Matches these:

        {"a": 1, "b": 3}
        {"a": 2, "b": 3}

    But won't match these:

        {"a": 1, "b": 10}
        {"a": 10, "b": 3}

    `groupby` example:

        GET /log/presigned_url?a=1&groupby=b&groupby=c

        {"b": 1, "c": 2, "count": 5}
        {"b": 1, "c": 3, "count": 8}

    `count` example:

        GET /log/presigned_url?a=1&groupby=b&groupby=c&count

        Returns: 2 (see previous example returning 2 rows)
    """
    logger.debug(f"Querying category {category}")

    if category not in CATEGORY_TO_MODEL_CLASS:
        raise HTTPException(
            HTTP_400_BAD_REQUEST,
            f"Category '{category}' is not one of {list(CATEGORY_TO_MODEL_CLASS.keys())}",
        )
    model = CATEGORY_TO_MODEL_CLASS[category]

    # TODO if the category is `presigned_url`, we could implement more granular authz using the audit logs' `resource_paths`.
    resource_path = f"/services/audit/{category}"
    await auth.authorize("read", [resource_path])

    try:
        start, start_date, stop, stop_date = validate_and_normalize_times(start, stop)
    except ValueError as e:
        raise HTTPException(HTTP_400_BAD_REQUEST, str(e))

    query_params = defaultdict(set)
    groupby = set()
    count = False
    for key, value in request.query_params.multi_items():
        if key == "count":
            count = True

        if key in {"start", "stop", "count"}:
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

    try:
        if groupby:
            logs = await data_access_layer.query_logs_with_grouping(
                model, start_date, stop_date, query_params, groupby
            )
            next_timestamp = None
        else:
            logs, next_timestamp = await data_access_layer.query_logs(
                model, start_date, stop_date, query_params, count
            )
    except ValueError as e:
        raise HTTPException(HTTP_400_BAD_REQUEST, str(e))

    if not config["QUERY_USERNAMES"]:
        # TODO: excluding usernames from the query might be more efficient
        for log in logs:
            if "username" in log:
                del log["username"]

    return {
        "nextTimeStamp": next_timestamp,
        "data": len(logs) if count else logs,
    }


def init_app(app: FastAPI):
    app.include_router(router, tags=["Query"])
