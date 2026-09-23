from pydantic import BaseModel
import sqlalchemy
from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import declarative_base
from typing import Optional

from .config import config

# SQLAlchemy ORM classes
Base = declarative_base()


class AuditLog(Base):
    __abstract__ = True  # Prevents table creation
    request_url = Column(String, nullable=False)
    status_code = Column(Integer, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=sqlalchemy.func.now())
    username = Column(String, nullable=False)
    sub = Column(Integer, nullable=True)  # can be null for public data
    additional_data = Column(JSONB(), nullable=True)

    # Since declarative_base() has no default to_dict() method,
    def to_dict(self):
        return {
            column.name: getattr(self, column.name) for column in self.__table__.columns
        }


# child audit log classes
class PresignedUrl(AuditLog):
    """
    `resource_paths` can be null if the user requested a file that
    doesn't exist.
    `protocol` can be null in the same case or if action=="upload"
    """

    __tablename__ = "presigned_url"

    id = Column(Integer, primary_key=True, autoincrement=True)
    guid = Column(String, nullable=False)
    resource_paths = Column(ARRAY(String), nullable=True)
    action = Column(String, nullable=False)
    protocol = Column(String, nullable=True)


class Login(AuditLog):
    __tablename__ = "login"

    id = Column(Integer, primary_key=True, autoincrement=True)
    idp = Column(String, nullable=False)
    fence_idp = Column(String, nullable=True)
    shib_idp = Column(String, nullable=True)
    client_id = Column(String, nullable=True)
    ip = Column(String, nullable=True)


class PFBExport(AuditLog):
    __tablename__ = "pfb_export"
    id = Column(Integer, primary_key=True, autoincrement=True)
    programs = Column(ARRAY(String), nullable=False)
    projects = Column(ARRAY(String), nullable=False)
    node_count = Column(Integer, nullable=True)
    destination = Column(String, nullable=True)
    export_type = Column(String, nullable=False)


class UserDataLibraryEvent(AuditLog):
    __tablename__ = "user_data_library"
    id = Column(Integer, primary_key=True, autoincrement=True)
    action = Column(String, nullable=False)
    target_type = Column(String, nullable=False)
    list_id = Column(String, nullable=False)
    item_id = Column(String, nullable=True)
    item_dataset_ids = Column(ARRAY(String), nullable=False)
    list_size_after = Column(Integer, nullable=True)


# Pydantic input models for API endpoints
class CreateLogInput(BaseModel):
    request_url: str
    status_code: int
    # timestamp: we store DateTimes in the DB but the API takes
    # int timestamps as input
    timestamp: int = None
    username: str
    sub: int = None
    additional_data: Optional[dict] = None


class CreatePresignedUrlLogInput(CreateLogInput):
    guid: str
    resource_paths: list = None
    action: str
    protocol: str = None


class CreateLoginLogInput(CreateLogInput):
    idp: str
    fence_idp: Optional[str] = None
    shib_idp: Optional[str] = None
    client_id: Optional[str] = None
    ip: Optional[str] = None


class CreatePFBExportLogInput(CreateLogInput):
    programs: list[str]
    projects: list[str]
    node_count: Optional[int] = None
    destination: Optional[str] = None
    export_type: str


class CreateUserDataLibraryEventLogInput(CreateLogInput):
    action: str
    target_type: str
    list_id: str
    item_id: Optional[str] = None
    item_dataset_ids: list[str]
    list_size_after: Optional[int] = None


# mapping for use by API endpoints
CATEGORY_TO_MODEL_CLASS = {
    "login": Login,
    "presigned_url": PresignedUrl,
    "pfb_export": PFBExport,
    "user_data_library": UserDataLibraryEvent,
}
