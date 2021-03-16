# Deploying the Audit Service to a Gen3 Data Commons

- Add `audit-service` to the Data Commons' manifest, in the `versions` section
- For login events and presigned URL events: in the Fence configuration file, configure `ENABLE_AUDIT_LOGS` (for each category, the default is `false`):

```
ENABLE_AUDIT_LOGS:
  presigned_url: <true or false>
  login: <true or false>
```

## Notes

1. When adding audit log creation in a service for the first time, the `audit-service` deployment file `network-ingress` annotation (see [here](https://github.com/uc-cdis/cloud-automation/blob/27770776d239bc609bbbd23607689cf62de1bc66/kube/services/audit-service/audit-service-deploy.yaml#L6)) must be updated to allow the service to talk to `audit-service`.
