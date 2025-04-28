from alembic.config import main as alembic_main
import copy
import os
import asyncio
import pytest
import pytest_asyncio
import requests
from starlette.config import environ
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch

# Set AUDIT_SERVICE_CONFIG_PATH *before* loading the configuration
CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))
environ["AUDIT_SERVICE_CONFIG_PATH"] = os.path.join(
    CURRENT_DIR, "test-audit-service-config.yaml"
)
from audit.config import config
from audit.app import app_init
from audit.db import get_db_engine_and_sessionmaker, initiate_db


@pytest.fixture(scope="session")
def app():
    app = app_init()
    return app


@pytest_asyncio.fixture(autouse=True)
async def setup_test_database():
    """
    At teardown, restore original config and reset test DB.
    """
    saved_config = copy.deepcopy(config._configs)

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, alembic_main, ["--raiseerr", "upgrade", "head"])

    yield

    # restore old configs
    config.update(saved_config)

    if not config["TEST_KEEP_DB"]:
        await loop.run_in_executor(
            None, alembic_main, ["--raiseerr", "downgrade", "base"]
        )


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """
    Creates a new async DB session with rolled-back transaction for each test.
    """
    await initiate_db()
    _, session_maker_instance = get_db_engine_and_sessionmaker()

    async with session_maker_instance() as session:
        yield session
        await session.rollback()  # clean up after each test


@pytest_asyncio.fixture
async def client(app):
    async with AsyncClient(app=app) as client:
        yield client


@pytest.fixture(autouse=True, scope="function")
def access_token_patcher(client, request):
    async def get_access_token(*args, **kwargs):
        return {"sub": "1", "context": {"user": {"name": "audit-service-user"}}}

    access_token_mock = MagicMock()
    access_token_mock.return_value = get_access_token

    access_token_patch = patch("audit.auth.access_token", access_token_mock)
    access_token_patch.start()

    yield access_token_mock

    access_token_patch.stop()


@pytest.fixture(scope="function")
def mock_arborist_requests(request):
    """
    This fixture returns a function which you call to mock the call to
    arborist client's auth_request method.
    By default, it returns a 200 response. If parameter "authorized" is set
    to False, it raises a 401 error.
    """

    def do_patch(authorized=True, urls_to_responses={}):
        # URLs to reponses: { URL: { METHOD: ( content, code ) } }
        urls_to_responses = {
            "http://arborist-service/auth/request": {
                "POST": ({"auth": authorized}, 200)
            },
            "http://arborist-service/auth/mapping": {
                "POST": (
                    {"/": [{"service": "*", "method": "*"}]} if authorized else {},
                    200,
                )
            },
            **urls_to_responses,
        }

        def make_mock_response(method, url, *args, **kwargs):
            method = method.upper()
            mocked_response = MagicMock(requests.Response)

            if url not in urls_to_responses:
                mocked_response.status_code = 404
                mocked_response.text = "NOT FOUND"
            elif method not in urls_to_responses[url]:
                mocked_response.status_code = 405
                mocked_response.text = "METHOD NOT ALLOWED"
            else:
                content, code = urls_to_responses[url][method]
                mocked_response.status_code = code
                if isinstance(content, dict):
                    mocked_response.json.return_value = content
                else:
                    mocked_response.text = content

            return mocked_response

        mocked_method = AsyncMock(side_effect=make_mock_response)
        patch_method = patch(
            "gen3authz.client.arborist.async_client.httpx.AsyncClient.request",
            mocked_method,
        )

        patch_method.start()
        request.addfinalizer(patch_method.stop)

    return do_patch


@pytest.fixture(autouse=True)
def arborist_authorized(mock_arborist_requests):
    """
    By default, mocked arborist calls return Authorized.
    To mock an unauthorized response, use fixture
    "mock_arborist_requests(authorized=False)" in the test itself.
    """
    mock_arborist_requests()
