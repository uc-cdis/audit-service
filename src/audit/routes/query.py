import uuid

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
from ..models import db, PresignedUrl


router = APIRouter()


# TODO config to return usernames or not
@router.get("/log/presigned_url")
async def query_presigned_url_logs(
    request: Request,
    # groupby: str = Query(None, description="TODO"),
    start: int = Query(None, description="Start timestamp"),
    stop: int = Query(None, description="Stop timestamp"),
    auth=Depends(Auth),
) -> list:
    """
    Queries the logs the current user has access to see.

    Filters can be added as query strings. Accepted filters include all fields
    for the queried category, as well as the following special filters:
    - "groupby" to get counts
    - # TODO count?
    - "start" to specify a starting timestamp. Default: the configured maximum
    - "stop" to specify an end timestamp. Default: now

    Queries are time-boxed: ("stop" - "start") must be lower than the
    configured maximum.

    Without filters, this will return all data within the time-box. Add filters as query strings like this:

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
    """
    timebox_max_seconds = config["QUERY_TIMEBOX_MAX_DAYS"] * 86400
    if not stop:
        stop = int(time.time())
    if not start:
        # default "start" = ("stop" - timebox maximum in seconds)
        start = max(stop - timebox_max_seconds, 0)

    if start > stop:
        raise HTTPException(
            HTTP_400_BAD_REQUEST,
            f"The start timestamp '{start}' should be before the stop timestamp '{stop}'",
        )

    try:
        start_date = datetime.fromtimestamp(start)
        stop_date = datetime.fromtimestamp(stop)
    except Exception as e:
        msg = f"Unable to convert timestamps '{start}' and '{stop}' to datetimes"
        logger.error(f"{msg}:\n{e}")
        raise HTTPException(HTTP_400_BAD_REQUEST, msg)

    if stop - start > timebox_max_seconds:
        raise HTTPException(
            HTTP_400_BAD_REQUEST,
            f"The difference between the start timestamp '{start}' ({start_date}) and the stop timestamp '{stop}' ({stop_date}) is greater than the configured maximum of {config['QUERY_TIMEBOX_MAX_DAYS']} days",
        )

    # TODO authz
    # # get the resources the current user has access to see
    # token_claims = await auth.get_token_claims()
    # username = token_claims["context"]["user"]["name"]
    # authz_mapping = await api_request.app.arborist_client.auth_mapping(username)
    # authorized_resource_paths = [
    #     resource_path
    #     for resource_path, access in authz_mapping.items()
    #     if any(
    #         e["service"] in ["audit", "*"] and e["method"] in ["read", "*"]
    #         for e in access
    #     )
    # ]

    # # filter requests with read access
    # requests = await RequestModel.query.gino.all()
    # authorized_requests = [
    #     r
    #     for r in requests
    #     if any(
    #         is_path_prefix_of_path(authorized_resource_path, r.resource_path)
    #         for authorized_resource_path in authorized_resource_paths
    #     )
    # ]
    # return [r.to_dict() for r in authorized_requests]

    limit = config["QUERY_PAGE_SIZE"]

    query_params = {}
    for key, value in request.query_params.multi_items():
        if key not in {"groupby", "start", "stop"}:
            # if key in <allowed>:  # TODO
            query_params.setdefault(key, []).append(value)
            # else:
            #     return 400

    # TODO only filters that are in DB model
    def add_filter(query):
        query = query.where(PresignedUrl.timestamp >= start_date).where(
            PresignedUrl.timestamp < stop_date
        )
        for field, values in query_params.items():
            if field == "resource_paths":  # TODO check type instead
                query = query.where(getattr(PresignedUrl, field).overlap(values))
            else:
                query = query.where(
                    db.or_(getattr(PresignedUrl, field) == v for v in values)
                )
        query = query.order_by(PresignedUrl.timestamp)
        # get 1 more log than the limit, so we can return `nextTimeStamp`:
        return query.limit(limit + 1)

    logs = [logs for logs in await add_filter(PresignedUrl.query).gino.all()]
    if len(logs) > limit:
        next_timestamp = int(datetime.timestamp(logs[-1].timestamp))
        logs = logs[:-1]
    else:
        next_timestamp = None
    return {
        "nextTimeStamp": next_timestamp,
        "data": [e.to_dict() for e in logs],
    }


def init_app(app: FastAPI):
    app.include_router(router, tags=["Query"])
