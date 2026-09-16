# Production Railway isolation waiver v2.6

Date: 2026-09-16
Status: accepted for the current production-hardening stage
Scope: `PROD-ISO` only

## Decision

Full Railway project/environment separation is waived for the current Shisha Advisor production path. `advisor-production` may remain in the existing `Shisha Advisor Staging` Railway project and `production` environment while the controls below remain true.

This waiver closes the production-isolation blocker by explicit documented risk acceptance. It does not waive authentication, backup, alerting, rollback, or secret-handling requirements.

## Current topology

- Railway project: `Shisha Advisor Staging` (`9d8b17cc-d535-44ca-a27a-5db34d4fd7ba`)
- Environment: `production` (`ab8bdcd9-9247-434c-a36b-d764d0088b2b`)
- Production service: `advisor-production` (`34916a60-58bc-4e7e-9e1f-9b703016535a`)
- Staging service: `advisor-staging` (`44234c27-1235-402f-9200-c9b74e1b1637`)
- Production volume: `advisor-production-data` mounted at `/data/shisha`, 500 MB
- Staging volume: `shisha-persistence` mounted at `/tmp/shisha`, 500 MB
- Production and staging do not share the same persistent volume.

## Rationale

Moving the live production service to a new Railway project would require coordinated recreation or migration of production configuration, credentials, service state, persistent storage, deployment linkage, and validation evidence. At the current private-production stage that migration introduces more immediate operational risk than the remaining shared project/environment boundary.

The current design already separates the production and staging services and persistent volumes, keeps production without a public domain, uses Google OIDC for production authentication, maintains verified off-volume GCS backups, and has an hourly health watch with proven Gmail delivery.

## Accepted residual risk

Because staging and production share a Railway project/environment, an operator can still affect production through a project-wide action, an incorrectly targeted service mutation, or future platform-level changes scoped above a single service. This waiver accepts that residual risk for the current architecture.

## Mandatory controls while the waiver is active

1. Production and staging service IDs must remain distinct.
2. Production and staging persistent volumes must remain distinct; staging must not be mounted to `/data/shisha`.
3. Deployment or configuration mutations must explicitly target `advisor-production` when production is intended and must not rely on ambiguous implicit service selection.
4. `SHISHA_AUTH_MODE=oidc` remains required for production.
5. `SHISHA_PUBLIC_GO_LIVE=false` and zero public production domains remain required until all other applicable public go-live blockers are closed.
6. Normal production metrics exposure remains disabled outside bounded validation probes.
7. Canonical production backup remains Google Cloud Storage through the verified `gcs-hmac` path, with a normal retention target of 14 generations.
8. The hourly `Shisha Prod Health` condition watch remains enabled and healthy checks remain silent; Gmail is sent only on qualifying failure conditions.
9. Secrets, tokens, HMAC credentials, OAuth client secrets, and bearer values must never be committed or logged.
10. Unrelated Railway services, projects, volumes, or environments must not be deleted as part of production maintenance.

## Re-evaluation triggers

Revisit this waiver if any of the following occurs:

- production and staging begin sharing storage, databases, or other mutable state;
- a Railway project-wide operation causes or nearly causes a production incident;
- the production topology grows materially beyond the current single application service plus dedicated volume;
- a clean project migration can be performed without risking state loss or secret exposure;
- the risk model or public exposure changes enough that the shared boundary is no longer acceptable.

## Relationship to the production gate

`PROD-ISO` is satisfied by this documented waiver. Public go-live remains independently gated by the Google authentication readiness requirement if general external Google sign-in is required, plus any other gate item introduced after this waiver.
