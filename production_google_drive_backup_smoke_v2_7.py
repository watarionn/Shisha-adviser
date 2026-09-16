from __future__ import annotations

import tempfile
from pathlib import Path

import production_google_drive_backup_worker_v2_7 as worker


class Result:
    def __init__(self, payload=None, side_effect=None):
        self.payload = payload
        self.side_effect = side_effect

    def execute(self):
        if self.side_effect:
            self.side_effect()
        return self.payload


class FolderFiles:
    def __init__(self):
        self.created = []

    def list(self, **kwargs):
        return Result({"files": []})

    def create(self, **kwargs):
        self.created.append(kwargs["body"])
        return Result({"id": "folder-1"})


class FolderService:
    def __init__(self):
        self.api = FolderFiles()

    def files(self):
        return self.api


class PruneFiles:
    def __init__(self):
        self.deleted = []
        self.items = [
            {
                "id": "db-new",
                "name": "production__shisha_20260916T000000Z.sqlite",
                "createdTime": "2026-09-16T00:00:00Z",
                "appProperties": {"shisha_backup_kind": "sqlite"},
            },
            {
                "id": "mf-new",
                "name": "production__shisha_20260916T000000Z.sqlite.manifest.json",
                "createdTime": "2026-09-16T00:00:01Z",
                "appProperties": {"shisha_backup_kind": "manifest"},
            },
            {
                "id": "db-mid",
                "name": "production__shisha_20260915T000000Z.sqlite",
                "createdTime": "2026-09-15T00:00:00Z",
                "appProperties": {"shisha_backup_kind": "sqlite"},
            },
            {
                "id": "mf-mid",
                "name": "production__shisha_20260915T000000Z.sqlite.manifest.json",
                "createdTime": "2026-09-15T00:00:01Z",
                "appProperties": {"shisha_backup_kind": "manifest"},
            },
            {
                "id": "db-old",
                "name": "production__shisha_20260914T000000Z.sqlite",
                "createdTime": "2026-09-14T00:00:00Z",
                "appProperties": {"shisha_backup_kind": "sqlite"},
            },
            {
                "id": "mf-old",
                "name": "production__shisha_20260914T000000Z.sqlite.manifest.json",
                "createdTime": "2026-09-14T00:00:01Z",
                "appProperties": {"shisha_backup_kind": "manifest"},
            },
        ]

    def list(self, **kwargs):
        return Result({"files": self.items})

    def delete(self, fileId):
        return Result({}, side_effect=lambda: self.deleted.append(fileId))


class PruneService:
    def __init__(self):
        self.api = PruneFiles()

    def files(self):
        return self.api


class ChunkRequest:
    def __init__(self):
        self.calls = 0

    def next_chunk(self):
        self.calls += 1
        if self.calls == 1:
            return None, None
        return None, {"id": "uploaded-1", "name": "backup.sqlite"}


class UploadFiles:
    def __init__(self):
        self.request = ChunkRequest()
        self.body = None

    def create(self, **kwargs):
        self.body = kwargs["body"]
        return self.request


class UploadService:
    def __init__(self):
        self.api = UploadFiles()

    def files(self):
        return self.api


def main():
    assert worker.DRIVE_FILE_SCOPE == "https://www.googleapis.com/auth/drive.file"
    assert worker._escape_q("a'b\\c") == "a\\'b\\\\c"

    folder_service = FolderService()
    folder_id = worker._ensure_folder(
        folder_service,
        {
            "folder_id": "",
            "folder_name": "Shisha Advisor Production Backups",
            "prefix": "production",
        },
    )
    assert folder_id == "folder-1"
    assert folder_service.api.created[0]["appProperties"]["shisha_backup_root"] == "true"

    prune_service = PruneService()
    removed = worker._prune(
        prune_service,
        "folder-1",
        {"prefix": "production", "retention": 2},
    )
    assert removed == ["production__shisha_20260914T000000Z.sqlite"]
    assert prune_service.api.deleted == ["db-old", "mf-old"]

    with tempfile.TemporaryDirectory(prefix="drive-smoke-") as td:
        source = Path(td) / "backup.sqlite"
        source.write_bytes(b"sqlite-test")
        upload_service = UploadService()
        result = worker._upload(
            upload_service,
            source,
            "folder-1",
            "backup.sqlite",
            {"prefix": "production"},
            "sqlite",
            "deadbeef",
        )
        assert result["id"] == "uploaded-1"
        assert upload_service.api.request.calls == 2
        assert upload_service.api.body["appProperties"]["sha256"] == "deadbeef"

    print("google_drive_backup_smoke=PASS")


if __name__ == "__main__":
    main()
