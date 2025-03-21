from pydantic import BaseModel
import sqlalchemy
from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import declarative_base

from .config import config

# TODO: replace gino ORM (not ORM?) interface with sqlalchemy's
# Refer to the gen3 user data library for guidance on how to redesign this

# db = Gino(
#     dsn=config["DB_URL"],
#     pool_min_size=config["DB_POOL_MIN_SIZE"],
#     pool_max_size=config["DB_POOL_MAX_SIZE"],
#     echo=config["DB_ECHO"],
#     ssl=config["DB_SSL"],
#     use_connection_for_request=config["DB_USE_CONNECTION_FOR_REQUEST"],
#     retry_limit=config["DB_RETRY_LIMIT"],
#     retry_interval=config["DB_RETRY_INTERVAL"],
# )

# SQLAlchemy ORM classes
Base = declarative_base()


class AuditLog(Base):
    __abstract__ = True  # Prevents table creation
    request_url = Column(String, nullable=False)
    status_code = Column(Integer, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=sqlalchemy.func.now())
    username = Column(String, nullable=False)
    sub = Column(Integer, nullable=True)  # can be null for public data


# child audit log classes
class PresignedUrl(AuditLog):
    """
    `resource_paths` can be null if the user requested a file that
    doesn't exist.
    `protocol` can be null in the same case or if action=="upload"
    """

    __tablename__ = "presigned_url"

    guid = Column(String, nullable=False)
    resource_paths = Column(ARRAY(String), nullable=True)
    action = Column(String, nullable=False)
    protocol = Column(String, nullable=True)


class Login(AuditLog):
    __tablename__ = "login"

    idp = Column(String, nullable=False)
    fence_idp = Column(String, nullable=True)
    shib_idp = Column(String, nullable=True)
    client_id = Column(String, nullable=True)


# Pydantic input models for API endpoints
class CreateLogInput(BaseModel):
    request_url: str
    status_code: int
    # timestamp: we store DateTimes in the DB but the API takes
    # int timestamps as input
    timestamp: int = None
    username: str
    sub: int = None


class CreatePresignedUrlLogInput(CreateLogInput):
    guid: str
    resource_paths: list = None
    action: str
    protocol: str = None


class CreateLoginLogInput(CreateLogInput):
    idp: str
    fence_idp: str = None
    shib_idp: str = None
    client_id: str = None


# mapping for use by API endpoints
CATEGORY_TO_MODEL_CLASS = {
    "login": Login,
    "presigned_url": PresignedUrl,
}
