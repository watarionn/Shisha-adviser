# Google-only production auth and backup plan (v2.7)

Status: implementation-prepared / external Google OAuth consent still required

## Decision

Use existing providers only:

- Authentication: Google OpenID Connect
- Independent backup: Google Drive API
- Runtime: Railway
- Source/evidence: GitHub
- Operational owner: `watarionn` for both on-call and rollback decision

Do not add Auth0 or Cloudflare R2 for the current production gate.

The production service must remain private until live Google ID-token validation, live Google Drive backup verification, notification delivery, and isolation/waiver are complete.

## Google OIDC values

Google's discovery metadata defines the production values below. The OAuth client ID is project-specific and must come from the real Google Cloud project.

```text
SHISHA_AUTH_MODE=oidc
SHISHA_OIDC_PROVIDER_ID=google
SHISHA_OIDC_ISSUER=https://accounts.google.com
SHISHA_OIDC_AUDIENCE=<GOOGLE_OAUTH_CLIENT_ID>
SHISHA_OIDC_JWKS_URL=https://www.googleapis.com/oauth2/v3/certs
SHISHA_PUBLIC_GO_LIVE=false
```

A real Google ID token must be validated against the private production service before any public Railway domain is attached.

## Google Drive backup values

The Google Drive worker uses the narrow `drive.file` OAuth scope and creates its own dedicated folder when `GOOGLE_DRIVE_FOLDER_ID` is not supplied. This avoids granting full-Drive access.

```text
SHISHA_BACKUP_ENABLED=true
SHISHA_BACKUP_PROVIDER=google-drive
GOOGLE_DRIVE_CLIENT_ID=<GOOGLE_OAUTH_CLIENT_ID>
GOOGLE_DRIVE_CLIENT_SECRET=<SECRET; Railway variable only>
GOOGLE_DRIVE_REFRESH_TOKEN=<SECRET; Railway variable only>
GOOGLE_DRIVE_FOLDER_NAME=Shisha Advisor Production Backups
SHISHA_BACKUP_PREFIX=production
SHISHA_BACKUP_RETENTION_COUNT=14
SHISHA_BACKUP_INTERVAL_SECONDS=86400
```

`GOOGLE_DRIVE_FOLDER_ID` is optional. Leave it unset for the first validated run so the same OAuth application creates a folder it can access with `drive.file`. After the first successful cycle, the returned/logged folder ID may be frozen into Railway configuration.

Never commit the Google client secret or refresh token to GitHub, issue comments, handoff files, or the memory vault.

## One Google OAuth client

To minimize administration, the OIDC audience and Drive backup can use one Google OAuth Web client in one Google Cloud project.

During private validation, a Google-owned temporary redirect such as OAuth 2.0 Playground may be used to obtain test credentials and the Drive refresh token. When public application routing is finalized, configure only the required production origins/redirects and remove temporary validation redirects that are no longer needed.

The Drive authorization request must use only:

```text
https://www.googleapis.com/auth/drive.file
```

The OIDC test request uses `openid email` (and `profile` only if the UI requires it).

## Backup acceptance test

A backup blocker closes only after a real Railway production cycle demonstrates all of the following:

1. SQLite online backup is created from `/data/shisha/shisha_advisor.db`.
2. Local backup verification passes.
3. SQLite file and manifest are uploaded to Google Drive.
4. Both files are downloaded again from Google Drive.
5. Downloaded SHA-256 matches the locally produced SHA-256.
6. SQLite integrity verification passes on the downloaded copy.
7. Retention enumerates only this application's backup generations and prunes generations beyond the configured count.

Expected successful worker event:

```text
status=UPLOADED_VERIFIED
provider=google-drive
remote_integrity=true
retention_count=14
```

## OIDC acceptance test

The OIDC blocker closes only after:

1. Google OAuth client is real and active.
2. A real Google-issued ID token is obtained for that client ID.
3. Token signature is validated using Google's JWKS.
4. `iss` resolves to Google's accepted issuer.
5. `aud` equals the configured Google OAuth client ID.
6. An authenticated production API request succeeds while the service is still private.
7. Missing/invalid/expired/wrong-audience tokens fail closed.

## Current gate

This implementation change does not change the production gate by itself.

- Public production: NO_GO
- Public Railway domains: keep at 0
- Google OAuth external values: pending
- Google Drive live backup evidence: pending
- Notification delivery: pending
- Operational owner: resolved (`watarionn`)
- Railway isolation or explicit waiver: pending
