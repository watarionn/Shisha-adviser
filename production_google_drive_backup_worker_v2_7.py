from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from shisha_backup_v1_6 import create_backup, verify_backup

FOLDER_MIME = "application/vnd.google-apps.folder"
DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"
TOKEN_URI = "https://oauth2.googleapis.com/token"


def _cfg():
    required = {
        "client_id": os.environ.get("GOOGLE_DRIVE_CLIENT_ID", ""),
        "client_secret": os.environ.get("GOOGLE_DRIVE_CLIENT_SECRET", ""),
        "refresh_token": os.environ.get("GOOGLE_DRIVE_REFRESH_TOKEN", ""),
    }
    missing = [k for k, value in required.items() if not value]
    if missing:
        raise RuntimeError("Missing Google Drive backup configuration: " + ", ".join(missing))
    required["folder_id"] = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "").strip()
    required["folder_name"] = (
        os.environ.get("GOOGLE_DRIVE_FOLDER_NAME", "Shisha Advisor Production Backups").strip()
        or "Shisha Advisor Production Backups"
    )
    required["prefix"] = os.environ.get("SHISHA_BACKUP_PREFIX", "production").strip("/") or "production"
    required["retention"] = max(1, int(os.environ.get("SHISHA_BACKUP_RETENTION_COUNT", "14")))
    required["interval"] = max(3600, int(os.environ.get("SHISHA_BACKUP_INTERVAL_SECONDS", "86400")))
    required["db"] = Path(os.environ.get("SHISHA_DB_PATH", "/data/shisha/shisha_advisor.db"))
    return required


def _service(cfg):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    credentials = Credentials(
        token=None,
        refresh_token=cfg["refresh_token"],
        token_uri=TOKEN_URI,
        client_id=cfg["client_id"],
        client_secret=cfg["client_secret"],
        scopes=[DRIVE_FILE_SCOPE],
    )
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def _escape_q(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _ensure_folder(service, cfg):
    if cfg["folder_id"]:
        folder = service.files().get(
            fileId=cfg["folder_id"], fields="id,name,mimeType,trashed"
        ).execute()
        if folder.get("mimeType") != FOLDER_MIME or folder.get("trashed"):
            raise RuntimeError("GOOGLE_DRIVE_FOLDER_ID is not a usable Drive folder")
        return folder["id"]

    name = _escape_q(cfg["folder_name"])
    q = f"name = '{name}' and mimeType = '{FOLDER_MIME}' and trashed = false"
    result = service.files().list(
        q=q,
        spaces="drive",
        fields="files(id,name,createdTime)",
        orderBy="createdTime asc",
        pageSize=10,
    ).execute()
    folders = result.get("files", [])
    if folders:
        return folders[0]["id"]

    created = service.files().create(
        body={
            "name": cfg["folder_name"],
            "mimeType": FOLDER_MIME,
            "appProperties": {
                "shisha_backup_root": "true",
                "shisha_backup_prefix": cfg["prefix"],
            },
        },
        fields="id",
    ).execute()
    return created["id"]


def _upload(service, local_path: Path, folder_id: str, name: str, cfg, kind: str, sha256: str | None = None):
    from googleapiclient.http import MediaFileUpload

    body = {
        "name": name,
        "parents": [folder_id],
        "appProperties": {
            "shisha_backup_kind": kind,
            "shisha_backup_prefix": cfg["prefix"],
        },
    }
    if sha256:
        body["appProperties"]["sha256"] = sha256
    media = MediaFileUpload(
        str(local_path), mimetype="application/octet-stream", resumable=True
    )
    request = service.files().create(
        body=body,
        media_body=media,
        fields="id,name,createdTime,size,appProperties",
    )
    response = None
    while response is None:
        _, response = request.next_chunk()
    return response


def _download(service, file_id: str, destination: Path):
    from googleapiclient.http import MediaIoBaseDownload

    request = service.files().get_media(fileId=file_id)
    with destination.open("wb") as handle:
        downloader = MediaIoBaseDownload(handle, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()


def _list_backup_files(service, folder_id: str, cfg):
    marker = _escape_q(f"{cfg['prefix']}__shisha_")
    q = f"'{_escape_q(folder_id)}' in parents and trashed = false and name contains '{marker}'"
    files = []
    page_token = None
    while True:
        result = service.files().list(
            q=q,
            spaces="drive",
            fields="nextPageToken,files(id,name,createdTime,size,appProperties)",
            orderBy="createdTime desc",
            pageSize=1000,
            pageToken=page_token,
        ).execute()
        files.extend(result.get("files", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            return files


def _remote_verify(service, backup_id: str, manifest_id: str, expected_sha: str):
    with tempfile.TemporaryDirectory(prefix="shisha_drive_verify_") as td:
        td = Path(td)
        backup = td / "download.sqlite"
        manifest = backup.with_suffix(".sqlite.manifest.json")
        _download(service, backup_id, backup)
        _download(service, manifest_id, manifest)
        result = verify_backup(backup)
        if not result["ok"] or result["actual_sha256"] != expected_sha:
            raise RuntimeError("Google Drive backup verification failed")
        return result


def _prune(service, folder_id: str, cfg):
    files = _list_backup_files(service, folder_id, cfg)
    sqlite_files = [
        item for item in files
        if item["name"].endswith(".sqlite")
        and item.get("appProperties", {}).get("shisha_backup_kind") == "sqlite"
    ]
    sqlite_files.sort(
        key=lambda item: (item.get("createdTime") or "", item["name"]),
        reverse=True,
    )
    removed = []
    by_name = {item["name"]: item for item in files}
    for item in sqlite_files[cfg["retention"]:]:
        manifest_name = item["name"] + ".manifest.json"
        manifest = by_name.get(manifest_name)
        service.files().delete(fileId=item["id"]).execute()
        if manifest:
            service.files().delete(fileId=manifest["id"]).execute()
        removed.append(item["name"])
    return removed


def _delete_quietly(service, file_id: str | None):
    if not file_id:
        return
    try:
        service.files().delete(fileId=file_id).execute()
    except Exception:
        pass


def _emit(event, **fields):
    print(json.dumps({"event": event, **fields}, ensure_ascii=False), flush=True)


def run_once(service=None, cfg=None):
    cfg = cfg or _cfg()
    if not cfg["db"].exists():
        return {"status": "DB_NOT_READY"}

    service = service or _service(cfg)
    folder_id = _ensure_folder(service, cfg)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    with tempfile.TemporaryDirectory(prefix="shisha_drive_upload_") as td:
        td = Path(td)
        backup = td / f"{cfg['prefix']}__shisha_{stamp}.sqlite"
        result = create_backup(cfg["db"], backup)
        verified = verify_backup(backup)
        if not verified["ok"]:
            raise RuntimeError("Local backup verification failed")

        manifest_path = Path(result["manifest"])
        backup_meta = _upload(
            service, backup, folder_id, backup.name, cfg, "sqlite", result["sha256"]
        )
        manifest_meta = None
        try:
            manifest_meta = _upload(
                service,
                manifest_path,
                folder_id,
                backup.name + ".manifest.json",
                cfg,
                "manifest",
                result["sha256"],
            )
            remote = _remote_verify(
                service, backup_meta["id"], manifest_meta["id"], result["sha256"]
            )
        except Exception:
            _delete_quietly(service, backup_meta.get("id"))
            _delete_quietly(service, manifest_meta.get("id") if manifest_meta else None)
            raise

    removed = _prune(service, folder_id, cfg)
    return {
        "status": "UPLOADED_VERIFIED",
        "provider": "google-drive",
        "folder_id": folder_id,
        "file_id": backup_meta["id"],
        "name": backup.name,
        "sha256": result["sha256"],
        "size_bytes": result["size_bytes"],
        "remote_integrity": remote["integrity"]["ok"],
        "retention_count": cfg["retention"],
        "pruned": removed,
    }


def main():
    cfg = _cfg()
    _emit(
        "backup_worker_started",
        provider="google-drive",
        prefix=cfg["prefix"],
        retention_count=cfg["retention"],
        interval_seconds=cfg["interval"],
    )
    while True:
        try:
            result = run_once(cfg=cfg)
            _emit("backup_cycle", **result)
        except Exception as exc:
            _emit(
                "backup_cycle_failed",
                provider="google-drive",
                error_type=type(exc).__name__,
                message=str(exc)[:300],
            )
        time.sleep(cfg["interval"])


if __name__ == "__main__":
    main()
