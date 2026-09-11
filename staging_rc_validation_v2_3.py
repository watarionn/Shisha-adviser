from __future__ import annotations

import json
import os
import socket
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from shisha_backup_v1_6 import create_backup, restore_backup, verify_backup
from shisha_hardened_service_v1_7 import Handler, HardenedAdvisorService
from shisha_multisession_store_v1_7 import SQLiteMultiSessionStore, state_sha256

BASE = Path(os.environ.get("SHISHA_APP_BASE", "/app"))
MOUNT = Path(os.environ.get("SHISHA_MOUNT_PATH", "/tmp/shisha"))
LIVE_DB = MOUNT / "shisha_advisor.db"
REPORT = MOUNT / "rc_validation_v2_3.json"
BACKUP = MOUNT / "rc_validation_v2_3_backup.sqlite"
RECOVERED = MOUNT / "rc_recovery_v2_3" / "recovered.sqlite"
EXPECTED_DATASET_FINGERPRINT = "c2dd0663fd2b9aa0aa85ac71b1e9f08036a9b6a5438f1a266c0e26d9e9dc9fea"


def emit(status, **extra):
    print(json.dumps({"rc_validation": status, **extra}, ensure_ascii=False), flush=True)


def http_json(method, url, token=None, body=None, etag=None):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if etag:
        headers["If-Match"] = etag
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
            return resp.status, resp.headers.get("ETag"), payload
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        payload = json.loads(raw) if raw else {}
        return e.code, e.headers.get("ETag"), payload


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def verify_existing(store, report):
    assert report["dataset_fingerprint"] == EXPECTED_DATASET_FINGERPRINT
    live = store.load_session(report["principal_id"], report["session_id"])
    assert state_sha256(live["state"]) == report["state_sha256"]
    assert live["state"]["turn_no"] == report["turn_no"]
    assert report["selected_flavor_id"] in live["state"]["profile"].get("liked_flavors", [])

    verify = verify_backup(BACKUP)
    assert verify["ok"] is True
    recovered = SQLiteMultiSessionStore(RECOVERED)
    restored = recovered.load_session(report["principal_id"], report["session_id"])
    assert state_sha256(restored["state"]) == report["state_sha256"]

    emit(
        "RC_EXISTING_VALIDATED",
        session_id=report["session_id"],
        state_sha256=report["state_sha256"],
        dataset_fingerprint=report["dataset_fingerprint"],
        selected_flavor_id=report["selected_flavor_id"],
    )


def run_new(store):
    credential = store.create_principal("rc-v2.3-synthetic")
    principal_id = credential["principal_id"]
    token = credential["token"]

    svc = HardenedAdvisorService(BASE, LIVE_DB, auth_mode="local-bearer", rate_limit=100)
    assert svc.dataset_fingerprint == EXPECTED_DATASET_FINGERPRINT

    port = free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.advisor_service = svc
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    root = f"http://127.0.0.1:{port}"

    try:
        st, _, ready = http_json("GET", root + "/readyz")
        assert st == 200
        assert ready["data"]["dataset_fingerprint"] == EXPECTED_DATASET_FINGERPRINT
        assert ready["service_version"] == "v2.3-rc"

        st, etag, body = http_json("POST", root + "/v1/sessions", token, {})
        assert st == 201 and etag
        session_id = body["data"]["session_id"]

        st, etag, body = http_json(
            "POST", root + f"/v1/sessions/{session_id}/recommend",
            token, {"text": "甘めがいい"}, etag.strip('"')
        )
        assert st == 200 and body["data"]["recommendation_generated"]

        st, etag, body = http_json(
            "POST", root + f"/v1/sessions/{session_id}/select",
            token, {"rank": 1}, etag.strip('"')
        )
        assert st == 200 and body["data"]["status"] == "SELECTED"
        selected = body["data"]["flavor_id"]

        st, etag, body = http_json(
            "POST", root + f"/v1/sessions/{session_id}/feedback",
            token, {"text": "これは好き"}, etag.strip('"')
        )
        assert st == 200 and body["data"]["profile_updated"]

        st, _, body = http_json(
            "GET", root + f"/v1/sessions/{session_id}/profile", token
        )
        assert st == 200
        assert selected in body["data"]["profile"].get("liked_flavors", [])

        live = store.load_session(principal_id, session_id)
        state_hash = state_sha256(live["state"])
        turn_no = live["state"]["turn_no"]

        create_backup(LIVE_DB, BACKUP)
        verify = verify_backup(BACKUP)
        assert verify["ok"] is True

        RECOVERED.parent.mkdir(parents=True, exist_ok=True)
        restore_backup(BACKUP, RECOVERED, "RESTORE")
        recovered = SQLiteMultiSessionStore(RECOVERED)
        recovered_state = recovered.load_session(principal_id, session_id)
        assert state_sha256(recovered_state["state"]) == state_hash

        store.revoke_principal(principal_id)

        report = {
            "status": "RC_CREATED_VALIDATED",
            "principal_id": principal_id,
            "session_id": session_id,
            "selected_flavor_id": selected,
            "turn_no": turn_no,
            "state_sha256": state_hash,
            "dataset_fingerprint": EXPECTED_DATASET_FINGERPRINT,
            "backup_sha256": verify["actual_sha256"],
            "credential_revoked": True,
        }
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        emit(
            "RC_CREATED_VALIDATED",
            session_id=session_id,
            state_sha256=state_hash,
            dataset_fingerprint=EXPECTED_DATASET_FINGERPRINT,
            selected_flavor_id=selected,
            credential_revoked=True,
        )
    finally:
        server.shutdown()
        server.server_close()


def main():
    MOUNT.mkdir(parents=True, exist_ok=True)
    store = SQLiteMultiSessionStore(LIVE_DB)
    if REPORT.exists():
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        verify_existing(store, report)
    else:
        run_new(store)


if __name__ == "__main__":
    main()
