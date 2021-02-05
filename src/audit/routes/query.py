import uuid

# from datetime import datetime
from fastapi import APIRouter, Body, Depends, FastAPI, HTTPException
from pydantic import BaseModel
from starlette.requests import Request
from starlette.status import (
    HTTP_200_OK,
    HTTP_404_NOT_FOUND,
)

from .. import logger
from ..auth import Auth
from ..config import config
from ..models import PresignedUrl


router = APIRouter()


@router.get("/log/presigned_url")
async def query_presigned_url_logs(
    request: Request,
    auth=Depends(Auth),
) -> list:
    """
    Queries the logs the current user has access to see.
    """
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

    # limit = min(limit, 2000)
    # query_params = {}
    # for key, value in request.query_params.multi_items():
    #     # if key not in {"data", "limit", "offset"}:
    #     query_params.setdefault(key, []).append(value)

    # def add_filter(query):
    #     for path, values in query_params.items():
    #         query = query.where(
    #             db.or_(Metadata.data[list(path.split("."))].astext == v for v in values)
    #         )
    #     return query.offset(offset).limit(limit)

    # if data:
    #     return {
    #         metadata.guid: metadata.data
    #         for metadata in await add_filter(Metadata.query).gino.all()
    #     }
    # else:
    #     return [
    #         row[0]
    #         for row in await add_filter(db.select([Metadata.guid]))
    #         .gino.return_model(False)
    #         .all()
    #     ]

    logs = await PresignedUrl.query.gino.all()
    return {
        "nextTimeStamp": None,  # TODO pagination
        "data": [e.to_dict() for e in logs],
    }
    # return len(logs)


def init_app(app: FastAPI):
    app.include_router(router, tags=["Query"])
