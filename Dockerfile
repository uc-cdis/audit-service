FROM quay.io/cdis/python:python3.10-buster-pybase3-3.0.2 as base

FROM base as builder
RUN apk add --no-cache --virtual .build-deps gcc musl-dev libffi-dev openssl-dev make postgresql-dev git curl vim
RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python
COPY . /src/
WORKDIR /src
RUN python -m venv /env && . /env/bin/activate && $HOME/.poetry/bin/poetry install --no-dev --no-interaction

FROM base
RUN apk add --no-cache postgresql-libs
COPY --from=builder /env /env
COPY --from=builder /src /src
WORKDIR /src
CMD ["/env/bin/gunicorn", "audit.asgi:app", "-b", "0.0.0.0:80", "-k", "uvicorn.workers.UvicornWorker"]
