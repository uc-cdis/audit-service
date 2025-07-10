from fastapi import APIRouter, FastAPI, Request, Depends

from ..db import DataAccessLayer, get_data_access_layer


router = APIRouter()


@router.get("/_version")
def get_version(request: Request) -> dict:
    return dict(version=request.app.version)


@router.get("/")
@router.get("/_statusxxx")
async def get_status(
    data_access_layer: DataAccessLayer = Depends(get_data_access_layer),
) -> dict:
    await data_access_layer.test_connection()
    return dict(status="OK")


def init_app(app: FastAPI) -> None:
    app.include_router(router, tags=["System"])
