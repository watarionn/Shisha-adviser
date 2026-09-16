# Production go-live policy v2.6

- Public production authentication policy: OIDC required.
- `local-bearer` is allowed only while `advisor-production` has no public domain and `SHISHA_PUBLIC_GO_LIVE=false`.
- Current private production service must keep `/healthz` healthcheck enabled.
- Current runtime alert path: `Shisha Prod Health` checks Railway hourly and sends Gmail only on qualifying service/deployment/replica/new-backup-failure conditions; healthy checks remain silent.
- Real Google OIDC token validation has passed on private production. Google Auth Platform is still `Testing`, so publishing/branding remains a public-user sign-in blocker if general external Google authentication is required.
- Canonical production backup is Google Cloud Storage via the verified `gcs-hmac` path. Live upload, remote re-download, SHA-256 verification, SQLite integrity verification, and retention pruning have passed. Normal retention is 14 generations.
- Full Railway project/environment separation is waived under `ops/production-isolation-waiver-v2.6.md`. Production and staging remain separate services with separate persistent volumes, and the waiver's mandatory controls apply.
- On-call owner: `watarionn`.
- Rollback-decision owner: `watarionn`.
- `SHISHA_PUBLIC_GO_LIVE=false` and zero public production domains remain mandatory until all remaining applicable public go-live blockers are closed.
- Secrets, HMAC credentials, OAuth client secrets, refresh tokens, ID/bearer tokens, and equivalent credentials must never be committed or logged.
