"""Core YouTube → MP3 download and probe logic."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from yt_dlp import YoutubeDL

QUALITIES = ("128", "192", "256", "320")

_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
}

_MAX_URL_LENGTH = 2048


def require_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "ffmpeg is required to convert audio to MP3. "
            "Install it (macOS: brew install ffmpeg; Ubuntu: sudo apt install ffmpeg)."
        )


def is_youtube_url(url: str) -> bool:
    if not url or len(url) > _MAX_URL_LENGTH:
        return False
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    return host in _YOUTUBE_HOSTS


def normalize_youtube_url(url: str) -> str:
    return url.strip()


def is_playlist_url(url: str) -> bool:
    lower = url.lower()
    if "/playlist" in lower:
        return True
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    return "list" in qs and not re.search(r"[?&]v=", url)


def build_opts(
    output_dir: Path,
    audio_quality: str,
    *,
    noplaylist: bool = False,
    quiet: bool = False,
    progress_hooks: list[Callable[[dict[str, Any]], None]] | None = None,
) -> dict[str, Any]:
    if audio_quality not in QUALITIES:
        raise ValueError(f"quality must be one of {QUALITIES}")

    output_dir.mkdir(parents=True, exist_ok=True)
    outtmpl = (
        str(output_dir / "%(title)s.%(ext)s")
        if noplaylist
        else str(output_dir / "%(playlist_title)s" / "%(title)s.%(ext)s")
    )
    opts: dict[str, Any] = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": audio_quality,
            }
        ],
        "extractor_args": {
            "youtube": {
                "player_client": ["android_vr", "default"],
            }
        },
        "ignoreerrors": True,
        "noplaylist": noplaylist,
        "quiet": quiet,
        "no_warnings": quiet,
        "writethumbnail": False,
        "embedthumbnail": False,
        "postprocessor_args": {
            "ffmpeg": ["-id3v2_version", "3"],
        },
    }
    if progress_hooks:
        opts["progress_hooks"] = progress_hooks
    return opts


def probe(url: str, *, max_playlist_entries: int = 50) -> dict[str, Any]:
    if not is_youtube_url(url):
        raise ValueError("Only YouTube URLs are supported.")

    url = normalize_youtube_url(url)
    playlist = is_playlist_url(url) or ("list=" in url and "/watch" not in urlparse(url).path)

    # For watch URLs with list=, treat as single video unless path is playlist
    if "list=" in url and "/playlist" not in url.lower() and "v=" in url:
        playlist = False

    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": "in_playlist" if playlist else False,
        "noplaylist": not playlist,
        "extractor_args": {
            "youtube": {
                "player_client": ["android_vr", "default"],
            }
        },
    }

    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if not info:
        raise RuntimeError("Could not fetch video information.")

    entries = info.get("entries")
    if entries is not None:
        entry_list = [e for e in entries if e]
        count = len(entry_list)
        if count > max_playlist_entries:
            raise ValueError(
                f"Playlist has {count} items; maximum allowed is {max_playlist_entries}."
            )
        first = entry_list[0] if entry_list else {}
        thumbnails = first.get("thumbnails") or []
        thumb = (
            first.get("thumbnail")
            or (thumbnails[-1]["url"] if thumbnails else None)
            or info.get("thumbnail")
        )
        return {
            "title": info.get("title") or "Playlist",
            "duration": None,
            "thumbnail": thumb,
            "is_playlist": True,
            "entry_count": count,
            "webpage_url": info.get("webpage_url") or url,
        }

    thumbnails = info.get("thumbnails") or []
    thumb = info.get("thumbnail") or (thumbnails[-1]["url"] if thumbnails else None)
    return {
        "title": info.get("title") or "Untitled",
        "duration": info.get("duration"),
        "thumbnail": thumb,
        "is_playlist": False,
        "entry_count": 1,
        "webpage_url": info.get("webpage_url") or url,
    }


def download(
    url: str,
    output_dir: Path,
    audio_quality: str,
    *,
    progress_hook: Callable[[dict[str, Any]], None] | None = None,
    max_playlist_entries: int = 50,
) -> int:
    require_ffmpeg()
    if not is_youtube_url(url):
        raise ValueError("Only YouTube URLs are supported.")
    url = normalize_youtube_url(url)

    # Soft-check playlist size before download
    meta = probe(url, max_playlist_entries=max_playlist_entries)
    single = not meta["is_playlist"]

    hooks = [progress_hook] if progress_hook else None
    opts = build_opts(
        output_dir,
        audio_quality,
        noplaylist=single,
        quiet=True,
        progress_hooks=hooks,
    )

    with YoutubeDL(opts) as ydl:
        result = ydl.download([url])
    return 0 if result == 0 else 1
