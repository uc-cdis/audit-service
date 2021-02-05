from cdislogging import get_logger


# Can't read config yet. Just set to debug for now.
# Later, in app.app_init(), will actually set level based on config
logger = get_logger("audit-service", log_level="debug")
