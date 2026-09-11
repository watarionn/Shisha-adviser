from __future__ import annotations
import os, subprocess, sys
from pathlib import Path

MOUNT = Path('/tmp/shisha')
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

subprocess.run([sys.executable, '/app/staging_persistence_canary.py'], check=True)
if os.environ.get('STAGING_E2E_TOKEN'):
    subprocess.run([sys.executable, '/app/staging_remote_e2e_v2_1.py'], check=True)

port = os.environ.get('PORT', '8789')
os.execv(sys.executable, [
    sys.executable,
    '/app/shisha_hardened_service_v1_7.py',
    '--base-dir', '/app',
    '--db', '/tmp/shisha/shisha_advisor.db',
    '--auth-mode', 'local-bearer',
    '--rate-limit', '60',
    '--rate-window-seconds', '60',
    '--log-path', '/tmp/shisha/service.jsonl',
    '--host', '0.0.0.0',
    '--port', port,
])
