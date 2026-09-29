# IAM notes for ERP ops (SSM + prod gates)

## ERP EC2 instance profile

Attach an instance profile that allows:

- `ssm:UpdateInstanceInformation`, `ssmmessages:*`, `ec2messages:*` (SSM agent)
- Pull from GCP Artifact Registry (WIF or SA key for `pip install nando-erp-ops`)
- Read/write `gs://nando-it-backups` (already used by backup sidecar)

## Lambda / laptop caller role

- `ssm:SendCommand` on the ERP instance ARN only
- `ssm:GetCommandInvocation` on `*`
- `ssm:ListCommandInvocations` (optional)

## Prod gate

Set `NANDO_ALLOW_PROD=1` only on the production-capable Lambda alias / IAM role.
Omit it on staging API deployments so `promote` / prod `backup` are denied in code
even if someone posts to the endpoint.

Additionally restrict IAM so only the deploy role can pass:

```
ssm:SendCommand
Condition: StringEquals
  ssm:parameter[commands] contains "nando-erp promote"
```

(Exact condition keys vary; prefer a thin wrapper script on the host
`/usr/local/bin/nando-promote` that is the only executable allowed.)

## Host install

```bash
sudo pip install nando-erp-ops --index-url https://...-python.pkg.dev/.../simple/
# or editable from the docker repo checkout on the host
sudo pip install -e /opt/nando_frappe_docker/tools/nando_erp_ops

export NANDO_DOCKER_REPO=/opt/nando_frappe_docker
# local executor on the host
export NANDO_EXECUTOR=local
```
