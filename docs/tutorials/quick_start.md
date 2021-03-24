# Quick start: run the Audit Service

Create a custom configuration file at `~/.gen3/audit-service/audit-service-config.yaml`. Add the following to your configuration file:

```
DB_DATABASE: audit_test
```

Create the database:

```bash
psql -U postgres -c "create database audit_test"
```

Run the database schema migration:

```bash
alembic upgrade head
```

Run the server with auto-reloading:

```bash
python run.py
OR
uvicorn audit.asgi:app --reload
```

Try out the API at: <http://localhost:8000/docs>.
