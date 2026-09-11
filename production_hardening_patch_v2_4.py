from __future__ import annotations
from pathlib import Path

BASE = Path('/app')


def patch_service():
    p = BASE / 'shisha_hardened_service_v1_7.py'
    s = p.read_text(encoding='utf-8')
    if 'import os\n' not in s:
        s = s.replace('import json\n', 'import json\nimport os\n', 1)

    old = '''            if method == "GET" and clean_path == "/metrics":\n                text = self.metrics.prometheus_text()\n                return 200, {"Content-Type": "text/plain; version=0.0.4; charset=utf-8"}, text\n\n            principal = self._principal(headers)\n'''
    new = '''            if method == "GET" and clean_path == "/metrics":\n                metrics_mode = os.environ.get("SHISHA_METRICS_MODE", "disabled").strip().lower()\n                if metrics_mode == "disabled":\n                    return response(404, error={\n                        "code": "NOT_FOUND",\n                        "message": "Metrics endpoint is disabled.",\n                        "retryable": False,\n                    }, request_id=request_id)\n                if metrics_mode == "authenticated":\n                    metrics_principal = self._principal(headers)\n                    principal_id = metrics_principal["principal_id"]\n                elif metrics_mode != "public":\n                    return response(503, error={\n                        "code": "METRICS_MODE_INVALID",\n                        "message": "Metrics endpoint configuration is invalid.",\n                        "retryable": False,\n                    }, request_id=request_id)\n                text = self.metrics.prometheus_text()\n                return 200, {"Content-Type": "text/plain; version=0.0.4; charset=utf-8"}, text\n\n            principal = self._principal(headers)\n'''
    if old not in s:
        if 'SHISHA_METRICS_MODE' in s:
            return
        raise RuntimeError('metrics block not found')
    s = s.replace(old, new, 1)
    p.write_text(s, encoding='utf-8')


if __name__ == '__main__':
    patch_service()
    print('production_hardening_patch=APPLIED')
