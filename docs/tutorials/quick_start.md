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

### Quickstart with Helm

You can now deploy individual services via Helm!

If you are looking to deploy all Gen3 services, that can be done via the Gen3 Helm chart.
Instructions for deploying all Gen3 services with Helm can be found [here](https://github.com/uc-cdis/gen3-helm#readme).

To deploy the audit service:
```bash
helm repo add gen3 https://helm.gen3.org
helm repo update
helm upgrade --install gen3/audit --set postgres.separate=true
```
These commands will add the Gen3 helm chart repo and install the audit service to your Kubernetes cluster. Supplying the "--set postgres.seperate=true" value will allow this chart to be deployed independant of other services as it will have its own instance of postgres.

Deploying audit this way will use the defaults that are defined in this [values.yaml file](https://github.com/uc-cdis/gen3-helm/blob/master/helm/audit/values.yaml)

You can learn more about these values by accessing the audit [README.md](https://github.com/uc-cdis/gen3-helm/blob/master/helm/audit/README.md)

If you would like to override any of the default values, simply copy the above values.yaml file into a local file and make any changes needed.
You can then supply your new values file with the following command:
```bash
helm upgrade --install gen3/audit --set postgres.separate=true -f values.yaml
```

If you are developing the service and you have built a new image, you can redeploy the service with the new image by replacing the .image.repository value with the name of your local image. You will also want to set the .image.pullPolicy to "never" if the image is only local. Here is an example:
```bash
image:
  repository: dockeruser/audit
  pullPolicy: Never
  # Overrides the image tag whose default is the chart appVersion.
  tag: ""
```
