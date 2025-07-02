from fastapi import APIRouter, FastAPI, Request, Depends
from typing import Union, get_args, get_origin

from ..db import DataAccessLayer, get_data_access_layer

from ..models import CreateLoginLogInput, CreatePresignedUrlLogInput

router = APIRouter()

# Increment versions on schema/model change.
CURRENT_SCHEMA_VERSIONS = {
    "login": 2,
    "presigned_url": 1,
}


def _pretty_type(t) -> str:
    """
    Human-readable short type name

    str                -> "str"
    list[str]          -> "list"
    Union[str, None]   -> "str?"
    """
    origin = get_origin(t)

    # handle Optional types (Union types with None)
    if origin is Union and type(None) in get_args(t):
        # filter out NoneType and assume first remaining arg as base, or fallback to object
        non_none_args = [a for a in get_args(t) if a is not type(None)]
        base = non_none_args[0] if non_none_args else object
        return f"{getattr(base, '__name__', str(base))}?"

    # handle parameterized generic type
    if origin is not None:
        return getattr(origin, "__name__", str(origin))

    # handle regular unparameterized types
    return getattr(t, "__name__", str(t))


def _get_pydantic_model(model_class) -> dict[str, str]:
    """
    Return {"field_name": "type"} for every field in a Pydantic model
    """
    raw_pydantic_fields = getattr(model_class, "model_fields", {})

    model = {}
    for name, field in raw_pydantic_fields.items():
        annotation = getattr(field, "annotation", None)
        model[name] = _pretty_type(annotation)
    return model


@router.get("/_schema")
def get_schema() -> dict:
    """
    GET audit service schema model versions and details.
    404s should assume legacy model.
    """
    return {
        "login": {
            "version": CURRENT_SCHEMA_VERSIONS["login"],
            "model": _get_pydantic_model(CreateLoginLogInput),
        },
        "presigned_url": {
            "version": CURRENT_SCHEMA_VERSIONS["presigned_url"],
            "model": _get_pydantic_model(CreatePresignedUrlLogInput),
        },
    }


@router.get("/_version")
def get_version(request: Request) -> dict:
    return dict(version=request.app.version)


@router.get("/")
@router.get("/_status")
async def get_status(
    data_access_layer: DataAccessLayer = Depends(get_data_access_layer),
) -> dict:
    await data_access_layer.test_connection()
    return dict(status="OK")


def init_app(app: FastAPI) -> None:
    app.include_router(router, tags=["System"])
