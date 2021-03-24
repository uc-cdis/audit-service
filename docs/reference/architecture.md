# Audit Service architecture

![Architecture diagram](../img/architecture_diagram.png)

## Database

Logs are stored in a PostgreSQL database. The following columns are common to all the log tables:
- request_url
- status_code
- timestamp
- username
- sub

Each log category contains additional fields. For example, the `presigned_url` table includes the following additional columns:
- guid
- resource_paths
- action
- protocol

For query performance and scalability as data accumulates, the tables are partitioned by month. We could also add indexes in the future if needed.

## API

The query endpoint only returns up to a configured maximum number of entries at a time. If there are more entries to query, it returns a non-null `nextTimeStamp` field, which can be used to get the next page. [More details in the "Query response page size" documentation.](../explanation/query_page_size.md)

The returned entries are ordered by increasing timestamp (least recent to most recent), so that new entries are at the end and there is no risk of skipping entries when getting the next page.

Filters can be added as query strings. Accepted filters include all fields for the queried category, as well as the following special filters:
- "groupby" to get counts
- "start" to specify a starting timestamp. Default: none
- "stop" to specify an end timestamp. Default: none

If queries are time-boxed (depends on configuration variable `QUERY_TIMEBOX_MAX_DAYS`), (`stop` - `start`) must be lower than the configured maximum.

We can populate the Audit Service database with historical data by parsing logs and making POST requests to create audit entries, because the POST endpoint accepts the timestamp as an optional parameter.

About retention: for now, there is no planned mechanism to delete old entries.

## Authorization

The POST endpoint is not exposed. Only internal services can use it.

The GET endpoint is exposed and protected by Arborist policies on resources `/audit/<category>`. For presigned URLs, we could use `/audit/presigned_url/<resource_path>` if needed in the future.

The Audit Service can be deployed to a Data Commons without granting any users access to make queries: the audit data would only be available by direct database query by an administrator.
