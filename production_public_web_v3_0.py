from __future__ import annotations

import argparse
import json
import os
import threading
import time
import uuid
from collections import defaultdict, deque
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from shisha_hardened_service_v1_7 import (
    HardenedAdvisorService,
    Handler as BaseHandler,
    response,
)
from shisha_identity_v1_6 import (
    LocalBearerAuthenticator,
    OIDCAuthenticator,
    OIDCConfig,
    OIDCVerifier,
)

TRUE = {"1", "true", "yes", "on"}
WEB_ROOT = Path(__file__).resolve().parent / "public_web_v3_0"


class HybridAuthenticator:
    def __init__(self, store, oidc_verifier):
        self.local = LocalBearerAuthenticator(store)
        self.oidc = OIDCAuthenticator(store, oidc_verifier)

    def authenticate(self, token):
        if token.startswith("sha_"):
            return self.local.authenticate(token)
        return self.oidc.authenticate(token)


class GuestRateGate:
    def __init__(self, per_key_limit=8, global_limit=240, window_seconds=3600):
        self.per_key_limit = max(1, int(per_key_limit))
        self.global_limit = max(1, int(global_limit))
        self.window_seconds = max(60, int(window_seconds))
        self.by_key = defaultdict(deque)
        self.global_events = deque()
        self.lock = threading.Lock()

    def _prune(self, q, now):
        cutoff = now - self.window_seconds
        while q and q[0] <= cutoff:
            q.popleft()

    def allow(self, key):
        now = time.time()
        key = str(key or "unknown")[:128]
        with self.lock:
            per_key = self.by_key[key]
            self._prune(per_key, now)
            self._prune(self.global_events, now)
            if len(per_key) >= self.per_key_limit or len(self.global_events) >= self.global_limit:
                retry_candidates = []
                if per_key:
                    retry_candidates.append(self.window_seconds - (now - per_key[0]))
                if self.global_events:
                    retry_candidates.append(self.window_seconds - (now - self.global_events[0]))
                retry = max(1, int(max(retry_candidates or [60])))
                return False, retry
            per_key.append(now)
            self.global_events.append(now)
            return True, 0


class PublicHandler(BaseHandler):
    server_version = "ShishaAdvisorPublic/3.0.1"

    def _client_key(self):
        forwarded = self.headers.get("X-Forwarded-For", "").split(",", 1)[0].strip()
        return forwarded or str(self.client_address[0])

    def _send(self, status, headers, payload):
        # Railway may weaken ETag when compressing (W/"...").
        # Carry the application revision token in JSON as a transformation-safe channel.
        etag_header = headers.get("ETag") or headers.get("etag")
        if etag_header and isinstance(payload, dict) and isinstance(payload.get("data"), dict):
            token = str(etag_header).strip()
            if token.startswith("W/"):
                token = token[2:].strip()
            token = token.strip('"')
            payload = {**payload, "data": {**payload["data"], "revision_token": token}}
        if isinstance(payload, bytes):
            data = payload
        elif isinstance(payload, str):
            data = payload.encode("utf-8")
        else:
            data = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        self.send_response(status)
        merged = dict(headers)
        merged.setdefault("Cache-Control", "no-store, no-transform")
        merged.setdefault("X-Content-Type-Options", "nosniff")
        merged.setdefault("Referrer-Policy", "no-referrer")
        merged.setdefault("X-Frame-Options", "DENY")
        merged.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
            "connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
        )
        for key, value in merged.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_home(self):
        target = WEB_ROOT / "index.html"
        if not target.is_file():
            return self._send(503, {"Content-Type": "text/plain; charset=utf-8"}, "Public UI unavailable.\n")
        return self._send(200, {"Content-Type": "text/html; charset=utf-8"}, target.read_bytes())

    def _create_guest(self):
        if not self.server.public_guest_enabled:
            return self._send(*response(404, error={
                "code": "NOT_FOUND", "message": "Not found.", "details": None
            }))
        allowed, retry_after = self.server.guest_gate.allow(self._client_key())
        if not allowed:
            status, headers, payload = response(429, error={
                "code": "GUEST_RATE_LIMITED",
                "message": "Guest registration rate limit exceeded.",
                "details": {"retry_after_seconds": retry_after},
            })
            headers["Retry-After"] = str(retry_after)
            return self._send(status, headers, payload)
        stats = self.server.advisor_service.db.stats()
        if stats["active_principals"] >= self.server.guest_max_principals:
            return self._send(*response(503, error={
                "code": "GUEST_CAPACITY_REACHED",
                "message": "Guest capacity is temporarily full.",
                "details": None,
            }))
        created = self.server.advisor_service.db.create_principal(
            "Guest-" + uuid.uuid4().hex[:8]
        )
        return self._send(*response(201, {
            "principal_id": created["principal_id"],
            "token": created["token"],
            "auth_type": "guest",
        }))

    def _handle(self):
        path = urlsplit(self.path).path
        if self.command == "GET" and path in {"/", "/index.html"}:
            return self._serve_home()
        if self.command == "POST" and path == "/v1/guest":
            return self._create_guest()
        return super()._handle()

    do_GET = _handle
    do_POST = _handle
    do_DELETE = _handle

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Allow", "GET, POST, DELETE, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()


def serve_public(service, host, port, guest_enabled):
    server = ThreadingHTTPServer((host, int(port)), PublicHandler)
    server.advisor_service = service
    server.public_guest_enabled = guest_enabled
    server.guest_max_principals = int(os.environ.get("SHISHA_GUEST_MAX_PRINCIPALS", "5000"))
    server.guest_gate = GuestRateGate(
        per_key_limit=int(os.environ.get("SHISHA_GUEST_IP_LIMIT_PER_HOUR", "8")),
        global_limit=int(os.environ.get("SHISHA_GUEST_GLOBAL_LIMIT_PER_HOUR", "240")),
        window_seconds=3600,
    )
    print(json.dumps({
        "status": "SERVING",
        "version": "v3.0.1-public-web",
        "host": host,
        "port": int(port),
        "auth_mode": service.auth_mode,
        "public_guest_enabled": guest_enabled,
    }, ensure_ascii=False), flush=True)
    server.serve_forever()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", default=".")
    ap.add_argument("--db", required=True)
    ap.add_argument("--auth-mode", choices=["local-bearer", "oidc"], default="local-bearer")
    ap.add_argument("--oidc-provider-id")
    ap.add_argument("--oidc-issuer")
    ap.add_argument("--oidc-audience")
    ap.add_argument("--oidc-jwks-url")
    ap.add_argument("--rate-limit", type=int, default=60)
    ap.add_argument("--rate-window-seconds", type=int, default=60)
    ap.add_argument("--log-path")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8789)
    args = ap.parse_args()

    guest_enabled = os.environ.get("SHISHA_PUBLIC_GUEST_ENABLED", "false").strip().lower() in TRUE
    verifier = None
    if args.auth_mode == "oidc":
        needed = [args.oidc_provider_id, args.oidc_issuer, args.oidc_audience, args.oidc_jwks_url]
        if any(not value for value in needed):
            raise SystemExit("OIDC mode requires provider-id, issuer, audience and jwks-url.")
        verifier = OIDCVerifier(OIDCConfig(
            provider_id=args.oidc_provider_id,
            issuer=args.oidc_issuer,
            audience=args.oidc_audience,
            jwks_url=args.oidc_jwks_url,
        ))

    service = HardenedAdvisorService(
        args.base_dir,
        args.db,
        auth_mode=args.auth_mode,
        oidc_verifier=verifier,
        rate_limit=args.rate_limit,
        rate_window_seconds=args.rate_window_seconds,
        log_path=args.log_path,
    )
    if guest_enabled and args.auth_mode == "oidc":
        service.authenticator = HybridAuthenticator(service.db, verifier)
    serve_public(service, args.host, args.port, guest_enabled)


if __name__ == "__main__":
    main()
