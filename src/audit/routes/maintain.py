from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException
from starlette.status import (
    HTTP_201_CREATED,
    HTTP_400_BAD_REQUEST,
)

from .. import logger
from ..auth import Auth
from ..utils.validate_utils import (
    validate_login_log,
    validate_presigned_url_log,
)
from ..db import DataAccessLayer, get_dal_dependency
from ..models import (
    CreateLoginLogInput,
    CreatePresignedUrlLogInput,
)

router = APIRouter()


@router.post("/log/presigned_url", status_code=HTTP_201_CREATED)
async def create_presigned_url_log(
    body: CreatePresignedUrlLogInput,
    background_tasks: BackgroundTasks,
    auth=Depends(Auth),
    dal: DataAccessLayer = Depends(get_dal_dependency),
) -> None:
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
    data = body.model_dump()
    validate_presigned_url_log(data)
    try:
        await dal.create_presigned_url_log(data)
    except Exception as e:
        logger.error(
            f"Failed to insert presigned_url audit log for URL {data.get('request_url')} at {data.get('timestamp')}"
        )
        raise


@router.post("/log/login", status_code=HTTP_201_CREATED)
async def create_login_log(
    body: CreateLoginLogInput,
    background_tasks: BackgroundTasks,
    auth=Depends(Auth),
    dal: DataAccessLayer = Depends(get_dal_dependency),
) -> None:
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
    data = body.model_dump()
    validate_login_log(data)
    try:
        await dal.create_login_log(data)
    except Exception as e:
        logger.error(
            f"Failed to insert login audit log for URL {data.get('request_url')} at {data.get('timestamp')}"
        )
        raise


def init_app(app: FastAPI):
    app.include_router(router, tags=["Maintain"])
