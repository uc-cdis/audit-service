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
from typing import Any, Dict, AsyncGenerator, List, Tuple, Optional
from datetime import datetime
from sqlalchemy import text, select, func, or_
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from audit.config import config
from audit.models import PresignedUrl, Login

engine = None
async_sessionmaker_instance = None


async def initiate_db() -> None:
    """
    Initialize the database enigne.
    """
    global engine, async_sessionmaker_instance
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
    async_sessionmaker_instance = async_sessionmaker(
        bind=engine, expire_on_commit=False
    )


def get_db_engine_and_sessionmaker() -> tuple[AsyncEngine, async_sessionmaker]:
    """
    Get the db engine and sessionmaker instances.
    """
    global engine, async_sessionmaker_instance
    if engine is None or async_sessionmaker_instance is None:
        raise Exception("Database not initialized. Call initiate_db() first.")
    return engine, async_sessionmaker_instance


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

    def _apply_query_filters(
        self, model, query, query_params, start_date=None, stop_date=None
    ):
        """
        Apply filters to a SQLAlchemy query based on the provided parameters.
        Raises ValueError for invalid field values.
        """

        def _cast_field_value(model, field, value):
            field_type = getattr(model, field).type.python_type
            if field_type == datetime:
                try:
                    return datetime.fromtimestamp(int(value))
                except ValueError as e:
                    raise ValueError(
                        f"Unable to convert value '{value}' to datetime for field '{field}': {e}"
                    )
            try:
                return field_type(value)
            except ValueError as e:
                raise ValueError(
                    f"Value '{value}' is not valid for field '{field}': {e}"
                )

        if start_date:
            query = query.where(model.timestamp >= start_date)
        if stop_date:
            query = query.where(model.timestamp < stop_date)

        for field, values in query_params.items():
            column = getattr(model, field)

            # TODO for resource_paths, implement filtering in a way that
            # would return "/A/B" when querying "/A".
            if hasattr(column.type, "item_type"):  # ARRAY
                query = query.where(column.overlap(values))
            else:
                typed_values = [_cast_field_value(model, field, v) for v in values]
                query = query.where(or_(*(column == v for v in typed_values)))

        return query

    async def query_logs(
        self, model, start_date, stop_date, query_params, count
    ) -> Tuple[List[Dict[str, Any]], Optional[int]]:
        """
        Query logs from the database with pagination support.
        Returns a tuple of (logs, next_timestamp).
        """
        # get all logs matching the filters and apply the page size limit
        # Build initial query with filters
        base_query = select(model)
        base_query = self._apply_query_filters(
            model, base_query, query_params, start_date, stop_date
        )
        base_query = base_query.order_by(model.timestamp)
        if not count:
            base_query = base_query.limit(config["QUERY_PAGE_SIZE"])

        result = await self.db_session.execute(base_query)
        logs = result.scalars().all()

        if not logs or count:
            # `count` queries are not paginated: no next timestamp
            return logs, None

        # if there are more logs with the same timestamp as the last queried log, also return them.
        # We use timestamp as the primary key for our queries and sorting.
        # We'll have to add something like a request.uuid to the records if we want to enforce page sizes and sort order.
        last_timestamp = logs[-1].timestamp

        # Get extra logs with the same timestamp as the last one
        extra_query = select(model)
        extra_query = self._apply_query_filters(
            model, extra_query, query_params, start_date, stop_date
        )
        extra_query = extra_query.where(model.timestamp == last_timestamp).order_by(
            model.timestamp
        )
        extra_result = await self.db_session.execute(extra_query)
        extra_logs = extra_result.scalars().all()

        if len(extra_logs) > 1:
            logs = [log for log in logs if log.timestamp != last_timestamp]
            logs.extend(extra_logs)

        # Get the next timestamp
        next_query = select(model)
        next_query = self._apply_query_filters(
            model, next_query, query_params, start_date, stop_date
        )
        next_query = next_query.where(model.timestamp > last_timestamp).order_by(
            model.timestamp
        )
        next_result = await self.db_session.execute(next_query)
        next_log = next_result.scalars().first()

        next_timestamp = (
            int(datetime.timestamp(next_log.timestamp)) if next_log else None
        )

        logs = [log.to_dict() for log in logs]
        return logs, next_timestamp

    async def query_logs_with_grouping(
        self, model, start_date, stop_date, query_params, groupby
    ) -> List[Dict[str, Any]]:
        """
        Query logs from the database with grouping support.
        Returns a list of dictionaries containing the grouped data.
        """
        select_list = [getattr(model, field) for field in groupby]
        select_list.append(func.count(model.username).label("count"))
        query = select(*select_list)
        for field in groupby:
            query = query.group_by(getattr(model, field))
        query = self._apply_query_filters(
            model, query, query_params, start_date, stop_date
        )
        result = await self.db_session.execute(query)
        logs = result.all()
        return [dict(row._mapping) for row in logs]

    async def create_presigned_url_log(self, data: Dict[str, Any]) -> None:
        """
        Create a new `presigned_url` audit log.
        """
        result = await self.db_session.execute(
            text("SELECT nextval('global_presigned_url_id_seq')")
        )
        data["id"] = result.scalar()
        self.db_session.add(PresignedUrl(**data))
        await self.db_session.commit()

    async def create_login_log(self, data: Dict[str, Any]) -> None:
        """
        Create a new `login` audit log.
        """
        result = await self.db_session.execute(
            text("SELECT nextval('global_login_id_seq')")
        )
        data["id"] = result.scalar()
        self.db_session.add(Login(**data))
        await self.db_session.commit()


@asynccontextmanager
async def get_data_access_layer() -> AsyncGenerator[DataAccessLayer, Any]:
    """
    Create an AsyncSession and yield an instance of the Data Access Layer,
    which acts as an abstract interface to manipulate the database.

    Can be injected as a dependency in FastAPI endpoints.
    """
    async with async_sessionmaker_instance() as session:
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
