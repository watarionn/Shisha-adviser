# Google Cloud Storage HMAC backup runbook (v2.8)

Status: prepared / live GCS credentials pending

## Purpose

Move the durable production backup path from Google Drive OAuth to Google Cloud Storage using HMAC credentials, while keeping Google OIDC for application authentication.

This avoids relying on an External + Testing OAuth refresh token for `drive.file`. Google Cloud Storage's XML API is interoperable with Amazon S3 tooling and can be used by the existing boto3 backup worker with an HMAC access ID and secret.

Google Drive remains enabled only as a temporary fallback until the first verified GCS cycle passes.

## Google Cloud setup

Use the same Google Cloud project already used for the Shisha Advisor OAuth client.

1. Create a private Cloud Storage bucket dedicated to production backups.
2. Keep Public Access Prevention enabled and use Uniform bucket-level access.
3. Create a dedicated service account, for example `shisha-backup`.
4. Grant that service account only `Storage Object Admin` on the backup bucket, not project-wide storage administration.
5. In Cloud Storage > Settings > Interoperability, create an HMAC key for that service account.
6. Store the HMAC access ID and secret directly in Railway. Never commit them to GitHub, issues, handoffs, or the memory vault.

The HMAC secret is shown only when the key is created. If it is lost, create a replacement key.

## Railway configuration

After the bucket and HMAC key exist, configure `advisor-production` with:

```text
SHISHA_BACKUP_ENABLED=true
SHISHA_BACKUP_PROVIDER=gcs-hmac
BACKUP_S3_ENDPOINT=https://storage.googleapis.com
BACKUP_S3_REGION=auto
BACKUP_S3_BUCKET=<PRIVATE_GCS_BUCKET_NAME>
BACKUP_S3_ACCESS_KEY_ID=<GCS_HMAC_ACCESS_ID>
BACKUP_S3_SECRET_ACCESS_KEY=<GCS_HMAC_SECRET>
SHISHA_BACKUP_PREFIX=production
SHISHA_BACKUP_RETENTION_COUNT=14
SHISHA_BACKUP_INTERVAL_SECONDS=86400
```

`gcs-hmac` intentionally maps to the existing `production_backup_worker_v2_5.py`. No duplicate backup implementation is introduced.

## Acceptance test

Do not remove the Drive fallback until a real Railway production cycle proves all of the following:

1. `provider=gcs-hmac` starts successfully.
2. SQLite online backup is created from `/data/shisha/shisha_advisor.db`.
3. Local verification passes.
4. Database and manifest upload to the private GCS bucket.
5. Both objects are downloaded from GCS again.
6. Downloaded SHA-256 matches the local backup.
7. SQLite integrity verification passes on the downloaded copy.
8. A temporary retention=1 probe creates a second verified generation and prunes only the previous generation.
9. Retention is restored to 14.
10. Production remains `SHISHA_AUTH_MODE=oidc`, `SHISHA_METRICS_MODE=disabled`, `SHISHA_PUBLIC_GO_LIVE=false`, with zero public domains until the remaining go-live blockers are closed.

Expected worker event:

```text
status=UPLOADED_VERIFIED
remote_integrity=true
retention_count=14
```

## Cutover cleanup

Only after the GCS acceptance test passes:

- remove `GOOGLE_DRIVE_CLIENT_SECRET` and `GOOGLE_DRIVE_REFRESH_TOKEN` from Railway if Drive is no longer retained as a fallback;
- revoke the old Google Drive OAuth grant if it is no longer needed;
- keep Google OIDC client metadata because authentication remains Google OIDC;
- keep the Drive worker implementation in source as a fallback unless a later cleanup explicitly removes it.

## Security notes

- HMAC credentials are Cloud Storage credentials, not Google OAuth refresh tokens.
- Scope the associated service account to the single backup bucket.
- Keep the bucket private.
- Never expose HMAC secret values in logs, GitHub, issue comments, or handoff files.
- Rotation path: create a second HMAC key, replace Railway variables, verify a successful cycle, then disable/delete the old key.
