import asyncio
import httpx
import os
from fastapi import FastAPI

try:
    from importlib.metadata import entry_points, version
except ImportError:
    from importlib_metadata import entry_points, version

from cdislogging import get_logger
from gen3authz.client.arborist.async_client import ArboristClient

from . import logger
from .config import config, DEFAULT_CFG_PATH

# Load the configuration *before* importing modules that rely on it
try:
    if os.environ.get("AUDIT_SERVICE_CONFIG_PATH"):
        config.load(config_path=os.environ["AUDIT_SERVICE_CONFIG_PATH"])
    else:
        CONFIG_SEARCH_FOLDERS = [
            "/src",
            "{}/.gen3/audit-service".format(os.path.expanduser("~")),
        ]
        config.load(search_folders=CONFIG_SEARCH_FOLDERS)
except Exception:
    logger.warning("Unable to load config, using default config...", exc_info=True)
    config.load(config_path=DEFAULT_CFG_PATH)

from .models import db
from .pull_from_queue import pull_from_queue_loop


def load_modules(app: FastAPI = None) -> None:
    for ep in entry_points()["audit.modules"]:
        logger.info("Loading module: %s", ep.name)
        mod = ep.load()
        if app:
            init_app = getattr(mod, "init_app", None)
            if init_app:
                init_app(app)


def app_init() -> FastAPI:
    logger.info("Initializing app")
    config.validate(logger)

    debug = config["DEBUG"]
    app = FastAPI(
        title="Audit Service",
        version=version("audit"),
        debug=debug,
        root_path=config["DOCS_URL_PREFIX"],
    )
    app.add_middleware(ClientDisconnectMiddleware)
    app.async_client = httpx.AsyncClient()

    # Following will update logger level, propagate, and handlers
    get_logger("audit-service", log_level="debug" if debug == True else "info")

    logger.info("Initializing Arborist client")
    if os.environ.get("ARBORIST_URL"):
        app.arborist_client = ArboristClient(
            arborist_base_url=os.environ["ARBORIST_URL"],
            logger=logger,
        )
    else:
        app.arborist_client = ArboristClient(logger=logger)

    db.init_app(app)
    load_modules(app)

    @app.on_event("startup")
    async def startup_event():
        if (
            config["PULL_FROM_QUEUE"]
            and config["QUEUE_CONFIG"].get("type") == "aws_sqs"
        ):
            loop = asyncio.get_running_loop()
            loop.create_task(pull_from_queue_loop())
            loop.set_exception_handler(handle_exception)

    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("Closing async client.")
        await app.async_client.aclose()
        logger.info("[Completed] Closing async client.")

    def handle_exception(loop, context):
        """
        Whenever an exception occurs in the asyncio loop, the loop still continues to execute without crashing.
        Therefore, we implement a custom exception handler that will ensure that the loop is stopped upon an Exception.
        """
        msg = context.get("exception", context.get("message"))
        logger.error(f"Caught exception: {msg}")
        for index, task in enumerate(asyncio.all_tasks()):
            task.cancel()
        logger.info("Closed all tasks")

    return app


class ClientDisconnectMiddleware:
    def __init__(self, app):
        self._app = app

    async def __call__(self, scope, receive, send):
        loop = asyncio.get_running_loop()
        rv = loop.create_task(self._app(scope, receive, send))
        waiter = None
        cancelled = False
        if scope["type"] == "http":

            def add_close_watcher():
                nonlocal waiter

                async def wait_closed():
                    nonlocal cancelled
                    while True:
                        message = await receive()
                        if message["type"] == "http.disconnect":
                            if not rv.done():
                                cancelled = True
                                rv.cancel()
                            break

                waiter = loop.create_task(wait_closed())

            scope["add_close_watcher"] = add_close_watcher
        try:
            await rv
        except asyncio.CancelledError:
            if not cancelled:
                raise
        if waiter and not waiter.done():
            waiter.cancel()
