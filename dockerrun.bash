#!/bin/bash

nginx
poetry run gunicorn -c "/audit/deployment/wsgi/gunicorn.conf.py" audit.asgi:app
