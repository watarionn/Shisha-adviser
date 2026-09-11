from __future__ import annotations
import os
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

os.execv(sys.executable, args)
