# Deploying the Audit Service to a Gen3 Data Commons

- Add `audit-service` to the Data Commons' manifest, in the `versions` section
- For login events and presigned URL events: in the Fence configuration file, configure `ENABLE_AUDIT_LOGS` (for each category, the default is `false`):

```
ENABLE_AUDIT_LOGS:
  presigned_url: <true or false>
  login: <true or false>
```

The `PUSH_AUDIT_LOGS_CONFIG` field must also be configured.

## Deploying audit-service 1.1.0

- **Systems where the audit-service has been deployed previously:** Fence 5.1.0 or more recent might NOT work with audit-service < 1.0.0. Update audit-service, then run `kubectl delete secret audit-g3auto` and `gen3 kube-setup-audit-service`. Then configure [PUSH_AUDIT_LOGS_CONFIG](https://github.com/uc-cdis/fence/blob/5.1.0/fence/config-default.yaml#L632-L636) in the Fence config (run `gen3 sqs info $(gen3 api safe-name audit-sqs)` to get the SQS URL) and run `kubectl delete secret fence-config` and `gen3 kube-setup-fence`.
- **Systems where the audit-service has never been deployed:** run `gen3 kube-setup-audit-service`. Then configure [ENABLE_AUDIT_LOGS](https://github.com/uc-cdis/fence/blob/5.1.0/fence/config-default.yaml#L624-L626) and [PUSH_AUDIT_LOGS_CONFIG](https://github.com/uc-cdis/fence/blob/5.1.0/fence/config-default.yaml#L632-L636) in the Fence config (run `gen3 sqs info $(gen3 api safe-name audit-sqs)` to get the SQS URL) and run `kubectl delete secret fence-config` and `gen3 kube-setup-fence`.

When deploying with Gen3 cloud-automation, there is no need to configure `PUSH_AUDIT_LOGS_CONFIG.aws_sqs_config.aws_cred` in the Fence configuration.

See the [Fence default configuration file](https://github.com/uc-cdis/fence/blob/5.1.0/fence/config-default.yaml#L622-L638) for more details.

## Notes

1. When adding audit log creation in a service for the first time, the `audit-service` deployment file `network-ingress` annotation (see [here](https://github.com/uc-cdis/cloud-automation/blob/27770776d239bc609bbbd23607689cf62de1bc66/kube/services/audit-service/audit-service-deploy.yaml#L6)) must be updated to allow the service to talk to `audit-service`.
2. In most cases, services should **not** provide a timestamp when creating audit logs. See [Creating audit logs, Timestamps section](../explanation/creating_audit_logs.md#timestamps).
