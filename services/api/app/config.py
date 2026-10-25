from __future__ import annotations

import os
from pathlib import Path


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


DOWNLOAD_API_KEY = _env("DOWNLOAD_API_KEY")
JOBS_DIR = Path(_env("JOBS_DIR", "/tmp/yt-mp3-jobs"))
JOB_TTL_SECONDS = int(_env("JOB_TTL_SECONDS", "3600"))
MAX_CONCURRENT_JOBS = int(_env("MAX_CONCURRENT_JOBS", "3"))
MAX_PLAYLIST_ENTRIES = int(_env("MAX_PLAYLIST_ENTRIES", "50"))
RATE_LIMIT_PER_MINUTE = int(_env("RATE_LIMIT_PER_MINUTE", "10"))
ALLOWED_ORIGINS = [
    o.strip()
    for o in _env(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if o.strip()
]