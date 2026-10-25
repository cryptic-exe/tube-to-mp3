#!/usr/bin/env python3
"""Download a YouTube video or playlist as MP3 (CLI)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running without installing the shared package
_ROOT = Path(__file__).resolve().parent
_SHARED = _ROOT / "packages" / "shared"
if _SHARED.exists() and str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))

try:
    from youtube_mp3 import QUALITIES, download, require_ffmpeg
except ImportError:
    print("Missing dependency: yt-dlp. Install with: pip install -r requirements.txt")
    sys.exit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download a YouTube song or playlist as MP3.",
    )
    parser.add_argument("url", help="YouTube video or playlist URL")
    parser.add_argument(
        "-o",
        "--output",
        default="downloads",
        help="Output directory (default: downloads)",
    )
    parser.add_argument(
        "-q",
        "--quality",
        default="192",
        choices=list(QUALITIES),
        help="MP3 bitrate in kbps (default: 192)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        require_ffmpeg()
    except RuntimeError as exc:
        print(exc)
        return 1

    output_dir = Path(args.output).expanduser().resolve()
    print(f"Downloading to: {output_dir}")
    try:
        return download(args.url, output_dir, args.quality)
    except (ValueError, RuntimeError) as exc:
        print(exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())