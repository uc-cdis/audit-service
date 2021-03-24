# Async POST endpoint

This is an async endpoint:
- POSTing audit logs does not impact the performance of the caller.
- Audit Service failures are not visible to users (for example, we don’t want to return a 500 error to users who are trying to download).

How to alert the team if for some reason (bug, full DB) we’re not recording audit logs anymore? TODO (PXP-7805)
