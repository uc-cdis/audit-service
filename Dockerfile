FROM quay.io/cdis/python:python3.9-buster-2.0.0 as base

FROM base as builder
RUN pip install --upgrade pip poetry
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    build-essential gcc make musl-dev libffi-dev libssl-dev git curl
COPY . /src/
WORKDIR /src
RUN python -m venv /env && . /env/bin/activate && poetry install -vv --no-interaction

FROM base
RUN apt-get install curl
COPY --from=builder /env /env
COPY --from=builder /src /src
WORKDIR /src
CMD ["/env/bin/gunicorn", "audit.asgi:app", "-b", "0.0.0.0:80", "-k", "uvicorn.workers.UvicornWorker"]
