wsgi_app = "deployment.wsgi.wsgi:app"
bind = "0.0.0.0:8000"
workers = 1
timeout = 300
worker_class = "uvicorn.workers.UvicornWorker"
