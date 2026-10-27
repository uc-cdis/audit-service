#!/bin/bash

nginx
exec gunicorn -c "/audit/deployment/wsgi/gunicorn.conf.py" audit.asgi:app
