from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException
from starlette.status import (
    HTTP_201_CREATED,
    HTTP_400_BAD_REQUEST,
)

from .. import logger
from ..auth import Auth
from ..models import (
    CATEGORY_TO_MODEL_CLASS,
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
    `gino.exceptions.NoSuchRowError` instead of `AttributeError`.
    """
    try:
        await CATEGORY_TO_MODEL_CLASS[category].create(**data)
    except AttributeError:
        pass
    except Exception:
        logger.error(
            f"Failed to insert {category} audit log for URL {data.get('request_url')} at {data.get('timestamp')}"
        )
        raise


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

    If the timestamp is omitted from the request body, the current date and
    time will be used.

    The response is returned _before_ inserting the new audit log in the
    database, so that POSTing audit logs does not impact the performance of
    the caller and audit-service failures are not visible to users.
    """
    data = body.dict()
    validate_presigned_url_log(data)
    background_tasks.add_task(insert_row, "presigned_url", data)


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

    If the timestamp is omitted from the request body, the current date and
    time will be used.

    The response is returned _before_ inserting the new audit log in the
    database, so that POSTing audit logs does not impact the performance of
    the caller and audit-service failures are not visible to users.
    """
    data = body.dict()
    validate_login_log(data)
    background_tasks.add_task(insert_row, "login", data)


def validate_login_log(data):
    logger.debug(f"Creating `login` audit log. Received body: {data}")
    handle_timestamp(data)


def init_app(app: FastAPI):
    app.include_router(router, tags=["Maintain"])
