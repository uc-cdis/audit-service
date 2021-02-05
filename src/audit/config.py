import os
from sqlalchemy.engine.url import make_url, URL

from gen3config import Config

DEFAULT_CFG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "config-default.yaml"
)


class AuditServiceConfig(Config):
    def __init__(self, *args, **kwargs):
        super(AuditServiceConfig, self).__init__(*args, **kwargs)

    def post_process(self) -> None:
        # generate DB_URL from DB configs
        self["DB_URL"] = make_url(
            URL(
                drivername=self["DB_DRIVER"],
                host=self["DB_HOST"],
                port=self["DB_PORT"],
                username=self["DB_USER"],
                password=self["DB_PASSWORD"],
                database=self["DB_DATABASE"],
            ),
        )

    def validate(self) -> None:
        """
        Perform a series of sanity checks on a loaded config.
        """
        pass


config = AuditServiceConfig(DEFAULT_CFG_PATH)
