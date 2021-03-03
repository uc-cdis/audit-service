import uuid

from asyncpg.exceptions import UniqueViolationError
from datetime import datetime
from enum import Enum
from fastapi import APIRouter, BackgroundTasks, Body, Depends, FastAPI, HTTPException
from gino.exceptions import NoSuchRowError
from starlette.requests import Request
from starlette.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
    HTTP_409_CONFLICT,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

from .. import logger
from ..auth import Auth
from ..config import config
from ..models import (
    CATEGORY_TO_MODEL_CLASS,
    db,
    CreateLoginLogInput,
    CreatePresignedUrlLogInput,
)


router = APIRouter()


async def insert_row(category, data):
    """
    GINO returns the row after inserting it:
    `insert into (...) values (...) returning (all the columns)`
    Because the table is partitioned with a trigger that returns null (see
    migration script d5b18185c458), GINO does not get the row back after
    inserting like it expects.
    In GINO v1.0.1, this results in the following error:
        > for k, v in row.items():
        E  AttributeError: 'NoneType' object has no attribute 'items'
    In later versions, it results in a `NoSuchRowError` exception
    (https://github.com/python-gino/gino/blob/v1.1.0b2/src/gino/crud.py#L858).
    However, at the time of writing this update has only been pre-released.

    According to this doc
    https://wiki.postgresql.org/wiki/INSERT_RETURNING_vs_Partitioning, we could
    implement a workaround. But since we do not currently need GINO to return
    the inserted statement, and the row does get inserted before the exception
    is raised, we just catch and ignore it.

    TODO Once a newer version of GINO is released, upgrade and catch
    `NoSuchRowError` instead of `AttributeError`.
    """
    try:
        await CATEGORY_TO_MODEL_CLASS[category].create(**data)
    except AttributeError:
        pass


# TODO maybe rename endpoint with "internal" or something, in case we need an external endpoint with authz later
# TODO maybe return something?
@router.post("/log/presigned_url", status_code=HTTP_201_CREATED)
async def create_presigned_url_log(
    body: CreatePresignedUrlLogInput,
    background_tasks: BackgroundTasks,
    auth=Depends(Auth),
) -> dict:
    """
    Create a new `presigned_url` audit log.
    This endpoint does not include any authorization checks, but it is not
    exposed and is only meant for internal use.
    The response is returned _before_ inserting the new audit log in the
    database, so that POSTing audit logs does not impact the performance of
    the caller and audit-service failures are not visible to users.
    """
    data = body.dict()
    logger.debug(f"Creating `presigned_url` audit log. Received body: {data}")

    allowed_actions = ["download", "upload"]
    if data["action"] not in allowed_actions:
        raise HTTPException(
            HTTP_400_BAD_REQUEST,
            f"Action '{data['action']}' is not allowed ({allowed_actions})",
        )

    # take a timestamp as input, store a datetime in the database
    if data["timestamp"]:
        data["timestamp"] = datetime.fromtimestamp(data["timestamp"])
    else:
        # timestamp=now is automatically added to rows without timestamp,
        # but we have to remove the key from the data dict
        del data["timestamp"]

    background_tasks.add_task(insert_row, "presigned_url", data)


@router.post("/log/login", status_code=HTTP_201_CREATED)
async def create_login_log(
    body: CreateLoginLogInput,
    background_tasks: BackgroundTasks,
    auth=Depends(Auth),
) -> dict:
    """
    Create a new `login` audit log.
    This endpoint does not include any authorization checks, but it is not
    exposed and is only meant for internal use.
    The response is returned _before_ inserting the new audit log in the
    database, so that POSTing audit logs does not impact the performance of
    the caller and audit-service failures are not visible to users.
    """
    data = body.dict()
    logger.debug(f"Creating `login` audit log. Received body: {data}")

    # take a timestamp as input, store a datetime in the database
    if data["timestamp"]:
        data["timestamp"] = datetime.fromtimestamp(data["timestamp"])
    else:
        # timestamp=now is automatically added to rows without timestamp,
        # but we have to remove the key from the data dict
        del data["timestamp"]

    background_tasks.add_task(insert_row, "login", data)


def init_app(app: FastAPI):
    app.include_router(router, tags=["Maintain"])
