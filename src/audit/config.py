import os
from sqlalchemy.engine.url import make_url, URL

from gen3config import Config

DEFAULT_CFG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "config-default.yaml"
)

# dummy comment


class AuditServiceConfig(Config):
    def __init__(self, *args, **kwargs):
        super(AuditServiceConfig, self).__init__(*args, **kwargs)

    def post_process(self) -> None:
        # generate DB_URL from DB configs
        self["DB_URL"] = make_url(
            URL.create(
                drivername=os.environ.get("DB_DRIVER", self["DB_DRIVER"]),
                host=os.environ.get("DB_HOST", self["DB_HOST"]),
                port=os.environ.get("DB_PORT", self["DB_PORT"]),
                username=os.environ.get("DB_USER", self["DB_USER"]),
                password=os.environ.get("DB_PASSWORD", self["DB_PASSWORD"]),
                database=os.environ.get("DB_DATABASE", self["DB_DATABASE"]),
            ),
        )

    def validate(self, logger) -> None:
        """
        Perform a series of sanity checks on a loaded config.
        """
        if self["PULL_FROM_QUEUE"]:
            assert "QUEUE_CONFIG" in self, "Config is missing 'QUEUE_CONFIG'"
            queue_type = self["QUEUE_CONFIG"].get("type")
            if queue_type == "aws_sqs":
                aws_sqs_config = self["QUEUE_CONFIG"].get("aws_sqs_config")
                assert (
                    aws_sqs_config
                ), f"'PULL_FROM_QUEUE' is enabled with 'type' == 'aws_sqs', but config is missing 'QUEUE_CONFIG.aws_sqs_config'"
                for key in ["sqs_url", "region"]:
                    if not aws_sqs_config.get(key):
                        logger.warning(
                            f"'PULL_FROM_QUEUE' is enabled with 'type' == 'aws_sqs', but config is missing 'QUEUE_CONFIG.aws_sqs_config.{key}'"
                        )
                if "aws_cred" in aws_sqs_config and aws_sqs_config["aws_cred"]:
                    assert (
                        aws_sqs_config["aws_cred"] in config["AWS_CREDENTIALS"]
                    ), f"The 'QUEUE_CONFIG.aws_sqs_config.aws_cred' value '{aws_sqs_config['aws_cred']}' is not configured in 'AWS_CREDENTIALS'"
            else:
                raise Exception(
                    f"Config 'QUEUE_CONFIG.type': unknown queue type '{queue_type}'"
                )


config = AuditServiceConfig(DEFAULT_CFG_PATH)
