from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# Resolve shared package when running from repo or Docker image layout
_HERE = Path(__file__).resolve()
_CANDIDATES = [
    _HERE.parents[3] / "packages" / "shared",  # repo: services/api/app -> root
    Path("/app/packages/shared"),
]
for path in _CANDIDATES:
    if path.exists() and str(path) not in sys.path:
        sys.path.insert(0, str(path))

from youtube_mp3 import QUALITIES, is_youtube_url, normalize_youtube_url, probe  # noqa: E402

from . import config  # noqa: E402
from .jobs import Job, start_job_thread, store  # noqa: E402
from .rate_limit import limiter  # noqa: E402

app = FastAPI(title="Tube to MP3 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProbeRequest(BaseModel):
    url: str = Field(..., min_length=8, max_length=2048)


class JobRequest(BaseModel):
    url: str = Field(..., min_length=8, max_length=2048)
    quality: Literal["128", "192", "256", "320"] = "192"


class ProbeResponse(BaseModel):
    title: str
    duration: float | int | None
    thumbnail: str | None
    is_playlist: bool
    entry_count: int
    webpage_url: str


class JobCreateResponse(BaseModel):
    jobId: str


class JobStatusResponse(BaseModel):
    jobId: str
    status: str
    progress: float
    title: str | None = None
    is_playlist: bool = False
    entry_count: int = 1
    error: str | None = None
    ready: bool = False
    filename: str | None = None


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def require_api_key(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    expected = config.DOWNLOAD_API_KEY
    if not expected:
        # Fail closed in production-like setups without a key
        raise HTTPException(status_code=503, detail="Server API key is not configured.")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")
    token = authorization.removeprefix("Bearer ").strip()
    if token != expected:
        raise HTTPException(status_code=401, detail="Invalid API key.")


def _enforce_rate_limit(request: Request) -> None:
    ip = _client_ip(request)
    if not limiter.allow(ip):
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait a minute and try again.",
        )


def _validate_url(url: str) -> str:
    url = normalize_youtube_url(url)
    if not is_youtube_url(url):
        raise HTTPException(status_code=400, detail="Only YouTube URLs are supported.")
    return url


def _job_to_response(job: Job) -> JobStatusResponse:
    return JobStatusResponse(
        jobId=job.id,
        status=job.status,
        progress=job.progress,
        title=job.title,
        is_playlist=job.is_playlist,
        entry_count=job.entry_count,
        error=job.error,
        ready=job.status == "completed" and job.result_path is not None,
        filename=job.result_filename,
    )


@app.on_event("startup")
def _startup() -> None:
    config.JOBS_DIR.mkdir(parents=True, exist_ok=True)

    def _loop() -> None:
        while True:
            store.cleanup_expired()
            time.sleep(60)

    threading.Thread(target=_loop, daemon=True).start()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/probe", response_model=ProbeResponse, dependencies=[Depends(require_api_key)])
def probe_url(body: ProbeRequest, request: Request) -> ProbeResponse:
    _enforce_rate_limit(request)
    url = _validate_url(body.url)
    try:
        data = probe(url, max_playlist_entries=config.MAX_PLAYLIST_ENTRIES)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502,
            detail=f"Could not read that YouTube URL: {exc}",
        ) from exc
    return ProbeResponse(**data)


@app.post("/v1/jobs", response_model=JobCreateResponse, dependencies=[Depends(require_api_key)])
def create_job(body: JobRequest, request: Request) -> JobCreateResponse:
    _enforce_rate_limit(request)
    url = _validate_url(body.url)
    if body.quality not in QUALITIES:
        raise HTTPException(status_code=400, detail="Invalid quality.")

    try:
        meta = probe(url, max_playlist_entries=config.MAX_PLAYLIST_ENTRIES)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    job = store.create(
        url,
        body.quality,
        title=meta.get("title"),
        is_playlist=bool(meta.get("is_playlist")),
        entry_count=int(meta.get("entry_count") or 1),
    )
    start_job_thread(job.id)
    return JobCreateResponse(jobId=job.id)


@app.get("/v1/jobs/{job_id}", response_model=JobStatusResponse, dependencies=[Depends(require_api_key)])
def get_job(job_id: str) -> JobStatusResponse:
    job = store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or expired.")
    return _job_to_response(job)


@app.get("/v1/jobs/{job_id}/file", dependencies=[Depends(require_api_key)])
def get_job_file(job_id: str) -> FileResponse:
    job = store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or expired.")
    if job.status != "completed" or not job.result_path or not job.result_path.exists():
        raise HTTPException(status_code=409, detail="File is not ready yet.")
    return FileResponse(
        path=job.result_path,
        media_type=job.result_media_type,
        filename=job.result_filename or job.result_path.name,
    )
