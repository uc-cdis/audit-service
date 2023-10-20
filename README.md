# Audit Service

![version](https://img.shields.io/github/release/uc-cdis/audit-service.svg) [![Apache license](http://img.shields.io/badge/license-Apache-blue.svg?style=flat)](LICENSE) [![Coverage Status](https://coveralls.io/repos/github/uc-cdis/audit-service/badge.svg?branch=master)](https://coveralls.io/github/uc-cdis/audit-service?branch=master)

The Audit Service exposes an API to create and query audit logs. It allows us to answer questions such as:
- How many times did `userA` download `file1` this month?
- When did `userA` download `file1`?
- Which files from dataset `D` were downloaded yesterday?
- How many times were files from dataset `D` downloaded yesterday?
- How many users downloaded data last year?
- How many unique users logged in since the creation of the Data Commons?
- How many users logged in via identity provider `X` last year?

The server is built with [FastAPI](https://fastapi.tiangolo.com/) and packaged with [Poetry](https://poetry.eustace.io/).

## Key documentation

The documentation can be browsed in the [docs](docs) folder, and key documents are linked below.

* [Detailed API Documentation](http://petstore.swagger.io/?url=https://raw.githubusercontent.com/uc-cdis/audit-service/master/docs/openapi.yaml)
* [API example requests](docs/tutorials/api_examples.md)
* [Quick start](docs/tutorials/quick_start.md)
* [Local installation](docs/how-to/local_installation.md)
* [Deploying the Audit Service to a Gen3 Data Commons](docs/how-to/deployment.md)
* [Architecture](docs/reference/architecture.md)
* [Query response page size](docs/explanation/query_page_size.md)
* [Creating audit logs](docs/explanation/creating_audit_logs.md)
* [How to add a new audit log category?](docs/how-to/add_log_category.md)
