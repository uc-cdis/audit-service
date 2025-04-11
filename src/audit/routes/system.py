from fastapi import APIRouter, FastAPI, Request, Depends

from ..models import PresignedUrl
from ..db import DataAccessLayer, get_dal_dependency


router = APIRouter()


@router.get("/_version")
def get_version(request: Request) -> dict:
    return dict(version=request.app.version)


@router.get("/")
@router.get("/_status")
async def get_status(dal: DataAccessLayer = Depends(get_dal_dependency)) -> dict:
    await dal.test_connection()
    return dict(status="OK")


def init_app(app: FastAPI) -> None:
    app.include_router(router, tags=["System"])
