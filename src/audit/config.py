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
        if self["PULL_FROM_QUEUE"]:
            assert "QUEUE_CONFIG" in self, "Config is missing 'QUEUE_CONFIG'"
            queue_type = self["QUEUE_CONFIG"].get("type")
            if queue_type == "aws_sqs":
                assert (
                    "sqs_url" in self["QUEUE_CONFIG"]
                ), "Config is missing 'QUEUE_CONFIG.sqs_url'"
                assert (
                    "region" in self["QUEUE_CONFIG"]
                ), "Config is missing 'QUEUE_CONFIG.region'"
            else:
                raise Exception(
                    f"Config 'QUEUE_CONFIG.type': unknown queue type '{queue_type}'"
                )


config = AuditServiceConfig(DEFAULT_CFG_PATH)
