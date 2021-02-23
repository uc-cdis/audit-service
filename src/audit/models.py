import enum

from datetime import datetime
from gino.ext.starlette import Gino
import sqlalchemy
from sqlalchemy import Column, DateTime, Enum, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, TIMESTAMP

# import time

from .config import config

db = Gino(
    dsn=config["DB_URL"],
    pool_min_size=config["DB_POOL_MIN_SIZE"],
    pool_max_size=config["DB_POOL_MAX_SIZE"],
    echo=config["DB_ECHO"],
    ssl=config["DB_SSL"],
    use_connection_for_request=config["DB_USE_CONNECTION_FOR_REQUEST"],
    retry_limit=config["DB_RETRY_LIMIT"],
    retry_interval=config["DB_RETRY_INTERVAL"],
)


class AuditLog(db.Model):
    request_url = Column(String, nullable=False)
    status_code = Column(Integer, nullable=False)
    # TODO try storing timestamps to simplify code. how to partition?
    # timestamp = Column(DateTime, nullable=False, default=datetime.utcnow) #Column(TIMESTAMP, nullable=False, default=sqlalchemy.func.now())
    timestamp = Column(DateTime, nullable=False, default=sqlalchemy.func.now())
    username = Column(String, nullable=False)
    sub = Column(String, nullable=False)

    # __table_args__ = ({"postgresql_partition_by": "timestamp"})


class PresignedUrl(AuditLog):
    __tablename__ = "presigned_url"

    guid = Column(String, primary_key=True)
    resource_paths = Column(ARRAY(String), nullable=False)
    action = Column(String, nullable=False)
    protocol = Column(String, nullable=True)
