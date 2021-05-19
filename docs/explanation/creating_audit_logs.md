# Creating audit logs

## Async POST endpoint

The audit log creation endpoints is an async endpoint:
- POSTing audit logs does not impact the performance of the caller.
- Audit Service failures are not visible to users (for example, we don’t want to return a 500 error to users who are trying to download).

However, it's difficult to monitor errors when using this endpoints.

## Pulling from a queue

The audit service can also handle pulling audit logs from a queue, which allows for easier monitoring. This can be configured by turning on the `PULL_FROM_QUEUE` flag in the configuration file (enabled by default). Right now, only AWS SQS is integrated, but integrations for other types of queues can be added by adding code and extending the values accepted for the `QUEUE_CONFIG.type` field in the configuration file.
