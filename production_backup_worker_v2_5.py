from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from shisha_backup_v1_6 import create_backup, verify_backup


def _cfg():
    required = {
        "endpoint": os.environ.get("BACKUP_S3_ENDPOINT", ""),
        "access_key": os.environ.get("BACKUP_S3_ACCESS_KEY_ID", ""),
        "secret_key": os.environ.get("BACKUP_S3_SECRET_ACCESS_KEY", ""),
        "region": os.environ.get("BACKUP_S3_REGION", "auto"),
        "bucket": os.environ.get("BACKUP_S3_BUCKET", ""),
    }
    missing = [k for k in ("endpoint", "access_key", "secret_key", "bucket") if not required[k]]
    if missing:
        raise RuntimeError("Missing backup object-storage configuration: " + ", ".join(missing))
    required["prefix"] = os.environ.get("SHISHA_BACKUP_PREFIX", "production").strip("/") or "production"
    required["retention"] = max(1, int(os.environ.get("SHISHA_BACKUP_RETENTION_COUNT", "14")))
    required["interval"] = max(3600, int(os.environ.get("SHISHA_BACKUP_INTERVAL_SECONDS", "86400")))
    required["db"] = Path(os.environ.get("SHISHA_DB_PATH", "/data/shisha/shisha_advisor.db"))
    return required


def _client(cfg):
    return boto3.client(
        "s3",
        endpoint_url=cfg["endpoint"],
        aws_access_key_id=cfg["access_key"],
        aws_secret_access_key=cfg["secret_key"],
        region_name=cfg["region"],
    )


def _emit(event, **fields):
    print(json.dumps({"event": event, **fields}, ensure_ascii=False), flush=True)


def _emit_safe_credential_shape(cfg):
    access_id = cfg["access_key"]
    secret = cfg["secret_key"]
    _emit(
        "backup_credential_shape",
        provider=os.environ.get("SHISHA_BACKUP_PROVIDER", "s3"),
        endpoint=cfg["endpoint"],
        region=cfg["region"],
        bucket=cfg["bucket"],
        access_id_length=len(access_id),
        access_id_starts_with_GOOG=access_id.startswith("GOOG"),
        access_id_has_edge_whitespace=access_id != access_id.strip(),
        secret_length=len(secret),
        secret_has_edge_whitespace=secret != secret.strip(),
        secret_value_logged=False,
    )


def _preflight(s3, cfg):
    response = s3.list_objects_v2(Bucket=cfg["bucket"], Prefix=cfg["prefix"] + "/", MaxKeys=1)
    _emit(
        "backup_preflight",
        status="PASS",
        provider=os.environ.get("SHISHA_BACKUP_PROVIDER", "s3"),
        bucket=cfg["bucket"],
        key_count=response.get("KeyCount", 0),
    )


def _remote_verify(s3, cfg, backup_key, manifest_key, expected_sha):
    with tempfile.TemporaryDirectory(prefix="shisha_remote_verify_") as td:
        td = Path(td)
        backup = td / "download.sqlite"
        manifest = backup.with_suffix(".sqlite.manifest.json")
        s3.download_file(cfg["bucket"], backup_key, str(backup))
        s3.download_file(cfg["bucket"], manifest_key, str(manifest))
        result = verify_backup(backup)
        if not result["ok"] or result["actual_sha256"] != expected_sha:
            raise RuntimeError("Remote backup verification failed")
        return result


def _prune(s3, cfg):
    paginator = s3.get_paginator("list_objects_v2")
    backups = []
    prefix = cfg["prefix"] + "/"
    for page in paginator.paginate(Bucket=cfg["bucket"], Prefix=prefix):
        for item in page.get("Contents", []):
            key = item["Key"]
            if key.endswith(".sqlite"):
                backups.append((item.get("LastModified"), key))
    backups.sort(key=lambda x: (x[0] or datetime.min.replace(tzinfo=timezone.utc), x[1]), reverse=True)
    removed = []
    for _, key in backups[cfg["retention"]:]:
        manifest_key = key + ".manifest.json"
        s3.delete_object(Bucket=cfg["bucket"], Key=key)
        s3.delete_object(Bucket=cfg["bucket"], Key=manifest_key)
        removed.append(key)
    return removed


def run_once(s3=None, cfg=None):
    cfg = cfg or _cfg()
    if not cfg["db"].exists():
        return {"status": "DB_NOT_READY"}
    s3 = s3 or _client(cfg)
    _preflight(s3, cfg)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    with tempfile.TemporaryDirectory(prefix="shisha_backup_upload_") as td:
        td = Path(td)
        backup = td / f"shisha_{stamp}.sqlite"
        result = create_backup(cfg["db"], backup)
        verified = verify_backup(backup)
        if not verified["ok"]:
            raise RuntimeError("Local backup verification failed")
        key = f'{cfg["prefix"]}/{backup.name}'
        manifest_path = Path(result["manifest"])
        manifest_key = key + ".manifest.json"
        s3.upload_file(str(backup), cfg["bucket"], key, ExtraArgs={"Metadata": {"sha256": result["sha256"]}})
        s3.upload_file(str(manifest_path), cfg["bucket"], manifest_key)
        remote = _remote_verify(s3, cfg, key, manifest_key, result["sha256"])
    removed = _prune(s3, cfg)
    return {
        "status": "UPLOADED_VERIFIED",
        "key": key,
        "sha256": result["sha256"],
        "size_bytes": result["size_bytes"],
        "remote_integrity": remote["integrity"]["ok"],
        "retention_count": cfg["retention"],
        "pruned": removed,
    }


def main():
    cfg = _cfg()
    _emit_safe_credential_shape(cfg)
    _emit("backup_worker_started", prefix=cfg["prefix"], retention_count=cfg["retention"], interval_seconds=cfg["interval"])
    while True:
        try:
            result = run_once(cfg=cfg)
            _emit("backup_cycle", **result)
        except Exception as exc:
            fields = {
                "error_type": type(exc).__name__,
                "message": str(exc)[:300],
            }
            if isinstance(exc, ClientError):
                error = exc.response.get("Error", {})
                fields["error_code"] = error.get("Code")
            _emit("backup_cycle_failed", **fields)
        time.sleep(cfg["interval"])


if __name__ == "__main__":
    main()
