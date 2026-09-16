from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

MOUNT = Path(os.environ.get('SHISHA_DATA_DIR', '/data/shisha'))
UID = 10001
GID = 10001

MOUNT.mkdir(parents=True, exist_ok=True)
if os.geteuid() == 0:
    for p in [MOUNT] + list(MOUNT.rglob('*')):
        try:
            os.chown(p, UID, GID)
        except FileNotFoundError:
            pass
    try:
        os.setgroups([])
    except PermissionError:
        pass
    os.setgid(GID)
    os.setuid(UID)

if os.environ.get('SHISHA_BACKUP_ENABLED', 'false').strip().lower() in {'1', 'true', 'yes'}:
    backup_provider = os.environ.get('SHISHA_BACKUP_PROVIDER', 's3').strip().lower()
    backup_workers = {
        's3': '/app/production_backup_worker_v2_5.py',
        'gcs-hmac': '/app/production_backup_worker_v2_5.py',
        'gcs_hmac': '/app/production_backup_worker_v2_5.py',
        'google-cloud-storage': '/app/production_backup_worker_v2_5.py',
        'google-drive': '/app/production_google_drive_backup_worker_v2_7.py',
        'google_drive': '/app/production_google_drive_backup_worker_v2_7.py',
    }
    backup_worker = backup_workers.get(backup_provider)
    if not backup_worker:
        raise SystemExit(
            'Unsupported SHISHA_BACKUP_PROVIDER. Expected one of: s3, gcs-hmac, google-drive'
        )
    subprocess.Popen([sys.executable, backup_worker])

port = os.environ.get('PORT', '8789')
auth_mode = os.environ.get('SHISHA_AUTH_MODE', 'local-bearer').strip().lower()
args = [
    sys.executable,
    '/app/shisha_hardened_service_v1_7.py',
    '--base-dir', '/app',
    '--db', str(MOUNT / 'shisha_advisor.db'),
    '--auth-mode', auth_mode,
    '--rate-limit', os.environ.get('SHISHA_RATE_LIMIT', '60'),
    '--rate-window-seconds', os.environ.get('SHISHA_RATE_WINDOW_SECONDS', '60'),
    '--log-path', str(MOUNT / 'service.jsonl'),
    '--host', '0.0.0.0',
    '--port', port,
]
if auth_mode == 'oidc':
    required = {
        '--oidc-provider-id': os.environ.get('SHISHA_OIDC_PROVIDER_ID', ''),
        '--oidc-issuer': os.environ.get('SHISHA_OIDC_ISSUER', ''),
        '--oidc-audience': os.environ.get('SHISHA_OIDC_AUDIENCE', ''),
        '--oidc-jwks-url': os.environ.get('SHISHA_OIDC_JWKS_URL', ''),
    }
    missing = [flag for flag, value in required.items() if not value]
    if missing:
        raise SystemExit('Missing required OIDC configuration: ' + ', '.join(missing))
    for flag, value in required.items():
        args.extend([flag, value])

probe_enabled = os.environ.get('SHISHA_OIDC_PROBE_ENABLED', 'false').strip().lower() in {
    '1', 'true', 'yes'
}
if probe_enabled:
    if auth_mode != 'oidc':
        raise SystemExit('SHISHA_OIDC_PROBE_ENABLED requires SHISHA_AUTH_MODE=oidc')
    subprocess.Popen([sys.executable, '/app/production_google_oidc_probe_v2_7.py'])

os.execv(sys.executable, args)
