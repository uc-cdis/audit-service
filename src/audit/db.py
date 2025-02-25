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
from typing import List, Optional, Tuple, Union, Any, Dict, AsyncGenerator
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, func, text, tuple_
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.future import select
from starlette import status

from gen3userdatalibrary import config

engine = create_async_engine(str(config["DB_URL"]), pool_pre_ping=True, echo=True)

# creates AsyncSession instances
async_sessionmaker = async_sessionmaker(engine, expire_on_commit=False)


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


async def get_data_access_layer() -> AsyncGenerator[DataAccessLayer, Any]:
    """
    Create an AsyncSession and yield an instance of the Data Access Layer,
    which acts as an abstract interface to manipulate the database.

    Can be injected as a dependency in FastAPI endpoints.
    """
    async with async_sessionmaker() as session:
        async with session.begin():
            yield DataAccessLayer(session)
