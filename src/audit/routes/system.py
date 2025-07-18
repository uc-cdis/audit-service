import json, hashlib
from pydantic import BaseModel
from typing import Type
from fastapi import APIRouter, FastAPI, Request, Depends
from typing import Union, get_args, get_origin

from ..db import DataAccessLayer, get_data_access_layer

from ..models import CreateLoginLogInput, CreatePresignedUrlLogInput

router = APIRouter()

# BE SURE TO UPDATE BOTH "version" AND "fingerprints" on schema/model change.
CURRENT_SCHEMA_VERSIONS = {
    "login": {
        "version": 2.0,
        "fingerprint": "082c72bdf11e278badb865c5018fdb353caa466619cc9c14de300c092b608273",  # pragma: allowlist-secret
    },
    "presigned_url": {
        "version": 1.0,
        "fingerprint": "bdd5092da16f39c59a0ce11d3c561ecbb5c2ca59dbba80dd83d409f4b850bcc1",  # pragma: allowlist-secret
    },
}


def _model_fingerprint(model_cls: Type[BaseModel]) -> str:
    """
    Takes a pydantic class model and returns a hash of the model's schema
    """
    schema_dict = model_cls.model_json_schema()
    schema_utf8 = json.dumps(schema_dict, sort_keys=True).encode(encoding="utf-8")
    return hashlib.sha256(schema_utf8).hexdigest()


def _pretty_type(t) -> str:
    """
    Human-readable short type name. Includes a question mark for optional fields.

    str                -> "str"
    list[str]          -> "list"
    Union[str, None]   -> "str?"
    """
    origin = get_origin(t)

    # handle Optional types (Union types with None)
    if origin is Union and type(None) in get_args(t):
        non_none_args = [a for a in get_args(t) if a is not type(None)]
        if not non_none_args:
            raise TypeError(
                "Optional type must include at least one non-None type, e.g. Union[str, None]"
            )
        base = non_none_args[0]
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
            "version": CURRENT_SCHEMA_VERSIONS["login"]["version"],
            "model": _get_pydantic_model(CreateLoginLogInput),
        },
        "presigned_url": {
            "version": CURRENT_SCHEMA_VERSIONS["presigned_url"]["version"],
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
