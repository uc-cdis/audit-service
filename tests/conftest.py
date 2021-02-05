from alembic.config import main as alembic_main
import copy
import importlib
import os
import pytest
import requests
from starlette.config import environ
from starlette.testclient import TestClient
from unittest.mock import MagicMock, patch

# Set AUDIT_SERVICE_CONFIG_PATH *before* loading the configuration
CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))
environ["AUDIT_SERVICE_CONFIG_PATH"] = os.path.join(
    CURRENT_DIR, "test-audit-service-config.yaml"
)
from audit.config import config
from audit.app import app_init  # , db as ddb


@pytest.fixture(scope="session")
def app():
    app = app_init()
    return app


# TODO if deleting all data between the tests, put session scope back
@pytest.fixture(autouse=True)  # , scope="session")
def setup_test_database():
    """
    At teardown, restore original config and reset test DB.
    """
    saved_config = copy.deepcopy(config._configs)

    alembic_main(["--raiseerr", "upgrade", "head"])

    yield

    # restore old configs
    config.update(saved_config)

    if not config["TEST_KEEP_DB"]:
        alembic_main(["--raiseerr", "downgrade", "base"])


# @pytest.fixture(scope="session")
# def db(app, request):
#     """
#     Define pytest fixture for database engine (session-scoped).
#     When the tests are over, drop everything from the test database.
#     """

#     # def drop_all():
#     #     models.Base.metadata.drop_all(app.db.engine)

#     # request.addfinalizer(drop_all)
#     # TODO

#     return ddb


# @pytest.fixture(scope="function")
# def db_session(db):
#     """
#     Define fixture for database session (function-scoped).
#     At the end of the function, roll back the session to its initial state.
#     """
#     connection = db.engine.connect()
#     transaction = connection.begin()
#     session = db.Session(bind=connection)

#     # patch_app_db_session(session)

#     yield session

#     session.close()
#     transaction.rollback()
#     connection.close()


@pytest.fixture()
def client():
    with TestClient(app_init()) as client:
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


# TODO
# @pytest.fixture(autouse=True)
# def clean_db(client):
#     before each test, delete all existing requests from the DB
#     fake_jwt = "1.2.3"
#     res = client.get("/request", headers={"Authorization": f"bearer {fake_jwt}"})
#     assert res.status_code == 200
#     for r in res.json():
#         res = client.delete(
#             "/request/" + r["request_id"],
#             headers={"Authorization": f"bearer {fake_jwt}"},
#         )

#     yield


@pytest.fixture(scope="function")
def mock_arborist_requests(request):
    """
    This fixture returns a function which you call to mock the call to
    arborist client's auth_request method.
    By default, it returns a 200 response. If parameter "authorized" is set
    to False, it raises a 401 error.
    """

    def do_patch(authorized=True):
        # URLs to reponses: { URL: { METHOD: ( content, code ) } }
        urls_to_responses = {
            "http://arborist-service/auth/request": {
                "POST": ({"auth": authorized}, 200)
            },
            "http://arborist-service/user/audit-service_user/policy": {
                "POST": ({}, 204 if authorized else 403)
            },
            "http://arborist-service/auth/mapping": {
                "POST": (
                    {"/": [{"service": "*", "method": "*"}]} if authorized else {},
                    200,
                )
            },
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

        mocked_method = MagicMock(side_effect=make_mock_response)
        patch_method = patch(
            "gen3authz.client.arborist.client.httpx.Client.request", mocked_method
        )

        patch_method.start()
        request.addfinalizer(patch_method.stop)

    return do_patch


@pytest.fixture(autouse=True)
def arborist_authorized(mock_arborist_requests):
    """
    By default, mocked arborist calls return Authorized.
    To mock an unauthorized response, use fixture
    "mock_arborist_requests(authorized=False)" in the test itself
    """
    mock_arborist_requests()
