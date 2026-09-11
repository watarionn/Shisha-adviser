from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from shisha_backup_v1_6 import create_backup, restore_backup, verify_backup
from shisha_hardened_service_v1_7 import Handler, HardenedAdvisorService
from shisha_multisession_store_v1_7 import SQLiteMultiSessionStore, now_ts, state_sha256, token_hash
from http.server import ThreadingHTTPServer

BASE = Path(os.environ.get("SHISHA_BASE_DIR", "/app"))
DB = Path(os.environ.get("SHISHA_DB_PATH", "/tmp/shisha/shisha_advisor.db"))
REPORT = Path(os.environ.get("STAGING_E2E_REPORT", "/tmp/shisha/remote_e2e_v2_1_report.json"))
BACKUP = Path(os.environ.get("STAGING_E2E_BACKUP", "/tmp/shisha/remote_e2e_v2_1_backup.sqlite"))
RECOVERED = Path(os.environ.get("STAGING_E2E_RECOVERED", "/tmp/shisha/recovery_v2_1/recovered.sqlite"))
TOKEN = os.environ.get("STAGING_E2E_TOKEN", "")
PRINCIPAL_ID = "prn_staging_e2e_v21"
DISPLAY_NAME = "staging-e2e-v2.1"
PORT = int(os.environ.get("STAGING_E2E_PORT", "18791"))


def emit(status: str, **fields):
    payload = {"event": "REMOTE_AUTH_E2E_BACKUP_RECOVERY", "status": status, **fields}
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True), flush=True)


def atomic_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def bootstrap_principal(store: SQLiteMultiSessionStore):
    if not TOKEN:
        emit("SKIPPED_NO_TOKEN")
        raise SystemExit(0)
    th = token_hash(TOKEN)
    ts = now_ts()
    with store.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        existing_hash = con.execute(
            "SELECT principal_id FROM principals WHERE token_hash=?", (th,)
        ).fetchone()
        existing_id = con.execute(
            "SELECT principal_id FROM principals WHERE principal_id=?", (PRINCIPAL_ID,)
        ).fetchone()
        if existing_hash and existing_hash["principal_id"] != PRINCIPAL_ID:
            con.execute("ROLLBACK")
            raise RuntimeError("staging token hash already belongs to another principal")
        if existing_id:
            con.execute(
                "UPDATE principals SET display_name=?,token_hash=?,is_active=1 WHERE principal_id=?",
                (DISPLAY_NAME, th, PRINCIPAL_ID),
            )
        else:
            con.execute(
                "INSERT INTO principals(principal_id,display_name,token_hash,is_active,created_at) VALUES(?,?,?,?,?)",
                (PRINCIPAL_ID, DISPLAY_NAME, th, 1, ts),
            )
        con.execute("COMMIT")
    return store.authenticate(TOKEN)


def request(method: str, path: str, body=None, etag=None):
    url = f"http://127.0.0.1:{PORT}{path}"
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    if etag:
        headers["If-Match"] = etag
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
            payload = json.loads(raw) if raw else None
            return resp.status, resp.headers.get("ETag"), payload
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        payload = json.loads(raw) if raw else None
        raise RuntimeError(f"HTTP {e.code} {path}: {payload}") from e


def verify_existing(store: SQLiteMultiSessionStore, report):
    principal = store.authenticate(TOKEN)
    sid = report["session_id"]
    live = store.load_session(principal["principal_id"], sid)
    live_sha = state_sha256(live["state"])
    if live_sha != report["state_sha256"]:
        raise RuntimeError("live state hash changed since validation")
    verification = verify_backup(BACKUP)
    if not verification["ok"]:
        raise RuntimeError("stored backup verification failed")
    recovered_store = SQLiteMultiSessionStore(RECOVERED)
    recovered_principal = recovered_store.authenticate(TOKEN)
    recovered = recovered_store.load_session(recovered_principal["principal_id"], sid)
    recovered_sha = state_sha256(recovered["state"])
    if recovered_sha != live_sha:
        raise RuntimeError("recovered state hash differs from live state")
    emit(
        "EXISTING_VALIDATED",
        session_id=sid,
        selected_flavor_id=report["selected_flavor_id"],
        live_state_sha256=live_sha,
        recovered_state_sha256=recovered_sha,
        backup_sha256=verification["actual_sha256"],
        profile_like_verified=True,
    )


def run_new(store: SQLiteMultiSessionStore):
    svc = HardenedAdvisorService(
        BASE,
        DB,
        auth_mode="local-bearer",
        rate_limit=100,
        rate_window_seconds=60,
        log_path=DB.parent / "remote_e2e_http.jsonl",
    )
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    server.advisor_service = svc
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.15)
    try:
        status, etag, created = request("POST", "/v1/sessions", {})
        if status != 201 or not etag:
            raise RuntimeError("session creation failed")
        sid = created["data"]["session_id"]

        status, etag, recommended = request(
            "POST", f"/v1/sessions/{sid}/recommend", {"text": "甘めがいい"}, etag
        )
        if status != 200 or not etag or not recommended["data"].get("recommendation_generated"):
            raise RuntimeError("recommendation did not generate candidates")

        status, etag, selected = request(
            "POST", f"/v1/sessions/{sid}/select", {"rank": 1}, etag
        )
        if status != 200 or not etag or selected["data"].get("status") != "SELECTED":
            raise RuntimeError("candidate selection failed")
        selected_flavor_id = selected["data"]["flavor_id"]

        status, etag, feedback = request(
            "POST", f"/v1/sessions/{sid}/feedback", {"text": "これは好き"}, etag
        )
        if status != 200 or not etag or feedback["data"].get("route") not in {
            "FEEDBACK", "FEEDBACK_AND_RECOMMENDATION"
        }:
            raise RuntimeError("feedback route failed")

        status, profile_etag, profile_resp = request("GET", f"/v1/sessions/{sid}/profile")
        if status != 200 or not profile_etag:
            raise RuntimeError("profile fetch failed")
        profile = profile_resp["data"]["profile"]
        profile_text = json.dumps(profile, ensure_ascii=False, sort_keys=True)
        if selected_flavor_id not in profile_text:
            raise RuntimeError("selected liked flavor not present in profile")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    principal = store.authenticate(TOKEN)
    live = store.load_session(principal["principal_id"], sid)
    live_sha = state_sha256(live["state"])

    create_backup(DB, BACKUP)
    verification = verify_backup(BACKUP)
    if not verification["ok"]:
        raise RuntimeError("backup verification failed")

    if RECOVERED.exists():
        RECOVERED.unlink()
    recovered_manifest = RECOVERED.with_suffix(RECOVERED.suffix + ".manifest.json")
    if recovered_manifest.exists():
        recovered_manifest.unlink()
    restore_result = restore_backup(BACKUP, RECOVERED, "RESTORE")
    recovered_store = SQLiteMultiSessionStore(RECOVERED)
    recovered_principal = recovered_store.authenticate(TOKEN)
    recovered = recovered_store.load_session(recovered_principal["principal_id"], sid)
    recovered_sha = state_sha256(recovered["state"])
    if recovered_sha != live_sha:
        raise RuntimeError("recovered session state does not match live state")

    report = {
        "schema": "shisha-remote-e2e-recovery-v2.1",
        "validated_at_unix": int(time.time()),
        "principal_id": PRINCIPAL_ID,
        "session_id": sid,
        "revision": live["revision"],
        "turn_no": live["state"].get("turn_no"),
        "selected_flavor_id": selected_flavor_id,
        "state_sha256": live_sha,
        "backup_sha256": verification["actual_sha256"],
        "backup_integrity": verification["integrity"]["ok"],
        "restore_status": restore_result["status"],
        "recovered_state_sha256": recovered_sha,
        "profile_like_verified": True,
        "actual_http_localhost": True,
        "raw_token_logged": False,
    }
    atomic_json(REPORT, report)
    emit(
        "CREATED_VALIDATED",
        session_id=sid,
        revision=live["revision"],
        turn_no=live["state"].get("turn_no"),
        selected_flavor_id=selected_flavor_id,
        live_state_sha256=live_sha,
        recovered_state_sha256=recovered_sha,
        backup_sha256=verification["actual_sha256"],
        backup_integrity=True,
        restore_status=restore_result["status"],
        profile_like_verified=True,
        actual_http_localhost=True,
    )


def main():
    store = SQLiteMultiSessionStore(DB)
    bootstrap_principal(store)
    if REPORT.exists():
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        verify_existing(store, report)
    else:
        run_new(store)
    if os.environ.get("STAGING_E2E_REVOKE_AFTER_VALIDATE") == "1":
        with store.connect() as con:
            con.execute("UPDATE principals SET is_active=0 WHERE principal_id=?", (PRINCIPAL_ID,))
        emit("CREDENTIAL_REVOKED", principal_id=PRINCIPAL_ID)


if __name__ == "__main__":
    main()
