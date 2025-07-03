# How to add a new audit log category?

- In `src/audit/models.py`, create a new audit log class. It should inherit from base class `AuditLog`. Also create a new input class. It should inherit from base class `CreateLogInput`. The properties of these 2 new classes should match.
- In `src/audit/models.py`, add the new category to `CATEGORY_TO_MODEL_CLASS` mapping.
- Use `alembic` to create a new migration. Edit the new migration file to create a new table for this category. The new table should be partitioned like the other audit log tables.
- In `src/audit/routes/maintain.py`, import the newly created input class and create a new route endpoint that takes the input class as parameter.
- Run `python run.py openapi` to update the API documentation.

dummy doc
