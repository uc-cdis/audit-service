"""
This file houses the database logic.
For schema/model of particular tables, go to `models.py`

OVERVIEW
--------

We're using SQLAlchemy's async support alongside FastAPI's dependency injection.

This file contains the logic for database manipulation in a "data access layer"
class, such that other areas of the code have simple `.create_list()` calls which
won't require knowledge on how to manage the session or interact with the db.
The session will be managed by dep injection of FastAPI's endpoints.
The logic that sets up the sessions is in this file.


DETAILS
-------
What do we do in this file?

- We create a sqlalchemy engine and session maker factory as globals
    - This reads in the db URL from config
- We define a data access layer class here which isolates the database manipulations
    - All CRUD operations go through this interface instead of bleeding specific database
      manipulations into the higher level web app endpoint code
- We create a function which yields an instance of the data access layer class with
  a fresh session from the session maker factory
    - This is what gets injected into endpoint code using FastAPI's dep injections
"""
from contextlib import asynccontextmanager
from typing import List, Optional, Tuple, Union, Any, Dict, AsyncGenerator
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, func, text, tuple_
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.future import select
from starlette import status

from audit.config import config
from audit.models import PresignedUrl, Login

print(f"DB_URL: {config['DB_URL']}")
engine = create_async_engine(
    url=config["DB_URL"],
    pool_size=config.get("DB_POOL_MIN_SIZE", 15),
    max_overflow=config["DB_POOL_MAX_SIZE"] - config["DB_POOL_MIN_SIZE"],
    echo=config["DB_ECHO"],
    connect_args={"ssl": config["DB_SSL"]} if config["DB_SSL"] else {},
    pool_pre_ping=True,
)


# creates AsyncSession instances
async_sessionmaker = async_sessionmaker(bind=engine, expire_on_commit=False)


class DataAccessLayer:
    """
    Defines an abstract interface to manipulate the database. Instances are given a session to
    act within.
    """

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def test_connection(self) -> None:
        """
        Ensure we can actually communicate with the db
        """
        await self.db_session.execute(text("SELECT 1;"))

    # TODO:
    # Implement the following methods:
    #  - query_audit_logs
    #  - create_logs (presigned_url, login)

    async def create_presigned_url_log(self, data: Dict[str, Any]) -> None:
        """
        Create a new `presigned_url` audit log.
        """
        self.db_session.add(PresignedUrl(**data))
        await self.db_session.commit()

    async def create_login_log(self, data: Dict[str, Any]) -> None:
        """
        Create a new `login` audit log.
        """
        self.db_session.add(Login(**data))
        await self.db_session.commit()


@asynccontextmanager
async def get_data_access_layer() -> AsyncGenerator[DataAccessLayer, Any]:
    """
    Create an AsyncSession and yield an instance of the Data Access Layer,
    which acts as an abstract interface to manipulate the database.

    Can be injected as a dependency in FastAPI endpoints.
    """
    async with async_sessionmaker() as session:
        async with session.begin():
            yield DataAccessLayer(session)


async def get_dal_dependency() -> AsyncGenerator[DataAccessLayer, None]:
    async with get_data_access_layer() as dal:
        yield dal


# NOTES TO BE DELETED ABOUT ALT DESIGN PATTERN TO REPLACE GINO

# async def get_db() -> AsyncSession:
#     async with AsyncSessionLocal() as session:
#         yield session
#
# # In FastAPI route:
# @app.get("/")
# async def read_data(session: AsyncSession = Depends(get_db)):
#     result = await session.execute(select(...))

# from tenacity import retry, stop_after_attempt, wait_fixed

# @retry(
#     stop=stop_after_attempt(config["DB_RETRY_LIMIT"]),
#     wait=wait_fixed(config["DB_RETRY_INTERVAL"])
# )
# async def safe_query(session: AsyncSession):
#     try:
#         result = await session.execute(select(...))
#         return result
#     except Exception as e:
#         await session.rollback()
#         raise

# db = Gino(
#     retry_limit=config["DB_RETRY_LIMIT"],
#     retry_interval=config["DB_RETRY_INTERVAL"],
# )
