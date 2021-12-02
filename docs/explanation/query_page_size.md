# Query response page size

The query endpoint only returns up to a configured maximum number of entries at a time (`QUERY_PAGE_SIZE` configuration variable). If there are more entries to query, it returns a non-null `nextTimeStamp` field, which can be used to get the next page:

```
{
	"data": list of entries, or int if using "count” parameter
	"nextTimestamp": null or string
}
```

Note that this is only the case for queries with NO `groupby` or `count` parameters.

## Page size edge case

However, if the `QUERY_PAGE_SIZE`th audit log has the same timestamp as the `QUERY_PAGE_SIZE+1`th audit log, the response could contain more than the configured `QUERY_PAGE_SIZE`.

For example, if `QUERY_PAGE_SIZE == 3` and the database contains the following logs:

```
[
    log with timestamp 1900,
    log with timestamp 1900,
    log with timestamp 1999,
    log with timestamp 1999,
    log with timestamp 2000
]
```

The query response will contain 4 logs:

```
{
    "data": [
        log with timestamp 1900,
        log with timestamp 1900,
        log with timestamp 1999,
        log with timestamp 1999,
    ],
    "nextTimestamp": timestamp 2000
}
```

This technical decision was made to avoid an awkward user experience when using parameter `start=nextTimestamp`, where logs that were already returned in the previous page could be returned again. This also avoids being stuck in an infinite querying loop if there are more than `QUERY_PAGE_SIZE` logs with an identical timestamp.
