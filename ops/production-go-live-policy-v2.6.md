# Production go-live policy v2.6

- Public production authentication policy: OIDC required.
- `local-bearer` is allowed only while `advisor-production` has no public domain and `SHISHA_PUBLIC_GO_LIVE=false`.
- Current private production service must keep `/healthz` healthcheck enabled.
- Current runtime alert path: ChatGPT condition watch checks Railway hourly and notifies only on new unhealthy/failure conditions.
- Public go-live is blocked until real OIDC provider values are configured and validated.
- Off-volume backup and retention remain blocked until a live independent storage target is provisioned.
- Full Railway project/environment isolation remains blocked by the current workspace project limit unless explicitly waived.
- On-call and rollback decision ownership remain TBD and must be explicitly assigned.
