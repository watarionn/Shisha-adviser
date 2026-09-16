from __future__ import annotations

import json
import os
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit

import production_public_web_v3_0 as base


ASSETS = {
    "/flavor-details.js": ("flavor-details.js", "application/javascript; charset=utf-8"),
    "/flavor-mix-details.js": ("flavor-mix-details.js", "application/javascript; charset=utf-8"),
    "/flavor-details.json": ("flavor-details.json", "application/json; charset=utf-8"),
    **{
        f"/flavor-details-{index}.json": (
            f"flavor-details-{index}.json",
            "application/json; charset=utf-8",
        )
        for index in range(1, 6)
    },
}


class PublicHandler(base.PublicHandler):
    server_version = "ShishaAdvisorPublic/3.0.3"

    def _serve_home(self):
        target = base.WEB_ROOT / "index.html"
        if not target.is_file():
            return self._send(
                503,
                {"Content-Type": "text/plain; charset=utf-8"},
                "Public UI unavailable.\n",
            )
        html = target.read_text(encoding="utf-8")
        scripts = [
            '<script src="/flavor-details.js" defer></script>',
            '<script src="/flavor-mix-details.js" defer></script>',
        ]
        for marker in scripts:
            if marker not in html:
                html = html.replace("</body>", f"  {marker}\n</body>")
        return self._send(
            200,
            {"Content-Type": "text/html; charset=utf-8"},
            html,
        )

    def _serve_detail_asset(self, filename, content_type):
        target = base.WEB_ROOT / filename
        if not target.is_file():
            return self._send(
                404,
                {"Content-Type": "text/plain; charset=utf-8"},
                "Not found.\n",
            )
        return self._send(200, {"Content-Type": content_type}, target.read_bytes())

    def _handle(self):
        path = urlsplit(self.path).path
        if self.command == "GET" and path in ASSETS:
            filename, content_type = ASSETS[path]
            return self._serve_detail_asset(filename, content_type)
        return super()._handle()

    do_GET = _handle
    do_POST = _handle
    do_DELETE = _handle


def serve_public(service, host, port, guest_enabled):
    server = ThreadingHTTPServer((host, int(port)), PublicHandler)
    server.advisor_service = service
    server.public_guest_enabled = guest_enabled
    server.guest_max_principals = int(os.environ.get("SHISHA_GUEST_MAX_PRINCIPALS", "5000"))
    server.guest_gate = base.GuestRateGate(
        per_key_limit=int(os.environ.get("SHISHA_GUEST_IP_LIMIT_PER_HOUR", "8")),
        global_limit=int(os.environ.get("SHISHA_GUEST_GLOBAL_LIMIT_PER_HOUR", "240")),
        window_seconds=3600,
    )
    print(
        json.dumps(
            {
                "status": "SERVING",
                "version": "v3.0.3-mix-detail",
                "host": host,
                "port": int(port),
                "auth_mode": service.auth_mode,
                "public_guest_enabled": guest_enabled,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    server.serve_forever()


base.PublicHandler = PublicHandler
base.serve_public = serve_public


if __name__ == "__main__":
    base.main()
