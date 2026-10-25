from __future__ import annotations

import shutil
import threading
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from youtube_mp3 import download as yt_download

from . import config

JobStatus = Literal["queued", "running", "completed", "failed", "expired"]


@dataclass
class Job:
    id: str
    url: str
    quality: str
    status: JobStatus = "queued"
    progress: float = 0.0
    title: str | None = None
    is_playlist: bool = False
    entry_count: int = 1
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    work_dir: Path | None = None
    result_path: Path | None = None
    result_filename: str | None = None
    result_media_type: str = "audio/mpeg"


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._active = 0
        config.JOBS_DIR.mkdir(parents=True, exist_ok=True)

    def count_active(self) -> int:
        with self._lock:
            return self._active

    def create(
        self,
        url: str,
        quality: str,
        *,
        title: str | None,
        is_playlist: bool,
        entry_count: int,
    ) -> Job:
        job_id = uuid.uuid4().hex
        work_dir = config.JOBS_DIR / job_id
        work_dir.mkdir(parents=True, exist_ok=True)
        job = Job(
            id=job_id,
            url=url,
            quality=quality,
            title=title,
            is_playlist=is_playlist,
            entry_count=entry_count,
            work_dir=work_dir,
        )
        with self._lock:
            self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **kwargs: Any) -> Job | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            for key, value in kwargs.items():
                setattr(job, key, value)
            job.updated_at = time.time()
            return job

    def begin(self, job_id: str) -> bool:
        with self._lock:
            if self._active >= config.MAX_CONCURRENT_JOBS:
                return False
            job = self._jobs.get(job_id)
            if not job or job.status != "queued":
                return False
            self._active += 1
            job.status = "running"
            job.updated_at = time.time()
            return True

    def end(self) -> None:
        with self._lock:
            self._active = max(0, self._active - 1)

    def cleanup_expired(self) -> None:
        now = time.time()
        expired: list[str] = []
        with self._lock:
            for job_id, job in self._jobs.items():
                if now - job.created_at > config.JOB_TTL_SECONDS:
                    expired.append(job_id)
            for job_id in expired:
                job = self._jobs.pop(job_id, None)
                if job and job.work_dir and job.work_dir.exists():
                    shutil.rmtree(job.work_dir, ignore_errors=True)


store = JobStore()


def _safe_filename(name: str, suffix: str) -> str:
    cleaned = "".join(c if c.isalnum() or c in (" ", "-", "_") else "_" for c in name)
    cleaned = cleaned.strip().replace(" ", "_")[:80] or "audio"
    return f"{cleaned}{suffix}"


def _collect_mp3s(work_dir: Path) -> list[Path]:
    return sorted(p for p in work_dir.rglob("*.mp3") if p.is_file())


def _finalize_result(job: Job) -> None:
    assert job.work_dir is not None
    mp3s = _collect_mp3s(job.work_dir)
    if not mp3s:
        raise RuntimeError("Download finished but no MP3 file was produced.")

    if len(mp3s) == 1:
        path = mp3s[0]
        store.update(
            job.id,
            result_path=path,
            result_filename=_safe_filename(job.title or path.stem, ".mp3"),
            result_media_type="audio/mpeg",
            progress=100.0,
            status="completed",
        )
        return

    zip_path = job.work_dir / "playlist.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for mp3 in mp3s:
            zf.write(mp3, arcname=mp3.name)

    store.update(
        job.id,
        result_path=zip_path,
        result_filename=_safe_filename(job.title or "playlist", ".zip"),
        result_media_type="application/zip",
        progress=100.0,
        status="completed",
    )


def run_job(job_id: str) -> None:
    job = store.get(job_id)
    if not job:
        return

    if not store.begin(job_id):
        # Wait briefly for a slot then retry once from worker thread
        for _ in range(30):
            time.sleep(1)
            if store.begin(job_id):
                break
        else:
            store.update(
                job_id,
                status="failed",
                error="Too many downloads in progress. Try again shortly.",
            )
            return

    def progress_hook(d: dict[str, Any]) -> None:
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes") or 0
            if total:
                # Reserve last 15% for conversion
                pct = min(85.0, (downloaded / total) * 85.0)
                store.update(job_id, progress=round(pct, 1))
        elif d.get("status") == "finished":
            store.update(job_id, progress=90.0)

    try:
        assert job.work_dir is not None
        code = yt_download(
            job.url,
            job.work_dir,
            job.quality,
            progress_hook=progress_hook,
            max_playlist_entries=config.MAX_PLAYLIST_ENTRIES,
        )
        if code != 0:
            raise RuntimeError("Download failed. The video may be unavailable or restricted.")
        _finalize_result(job)
    except Exception as exc:  # noqa: BLE001 — surface to client
        store.update(job_id, status="failed", error=str(exc), progress=0.0)
    finally:
        store.end()


def start_job_thread(job_id: str) -> None:
    thread = threading.Thread(target=run_job, args=(job_id,), daemon=True)
    thread.start()