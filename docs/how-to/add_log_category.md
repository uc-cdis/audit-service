# How to add a new audit log category?

- In `src/audit/models.py`, create a new audit log class. It should inherit from base class `AuditLog`. Also create a new input class. It should inherit from base class `CreateLogInput`. The properties of these 2 new classes should match.
- In `src/audit/models.py`, add the new category to `CATEGORY_TO_MODEL_CLASS` mapping.
- Use `alembic` to create a new migration. Edit the new migration file to create a new table for this category. The new table should be partitioned like the other audit log tables.
- Adding columns to tables `login` or `presigned_url` may require upgrading the existing trigger function. See Step 5 of migration [7a838ea48eea_add_pk_to_login_and_presigned_url.py](https://github.com/uc-cdis/audit-service/blob/287488874b27790090aeca8ec0b4a6cab1169a55/migrations/versions/7a838ea48eea_add_pk_to_login_and_presigned_url.py#L110) for an example of updating the trigger function.
- In `src/audit/routes/maintain.py`, import the newly created input class and create a new route endpoint that takes the input class as parameter.
- Run `python run.py openapi` to update the API documentation.
