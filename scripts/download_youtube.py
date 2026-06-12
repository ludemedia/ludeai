"""
Download the first N YouTube videos listed in each url_source JSON file.

The JSON files are phpMyAdmin exports; the video rows live in the `yt_videos`
table element with fields: published_at, title, url.

Usage:
    python scripts/download_youtube.py [--limit 15] [--outdir data/videos]

Requires: yt-dlp (installed in the project venv).
Note: ffmpeg is not assumed — yt-dlp will fall back to single-file progressive
formats so no audio/video merge is needed.
"""
import argparse
import json
from pathlib import Path

import yt_dlp

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "data" / "url_source"
SOURCES = ["路德社主頻道.json", "閆博士說.json"]


def extract_urls(json_path: Path, limit: int) -> list[str]:
    """Pull the first `limit` video URLs from the yt_videos table in a phpMyAdmin export."""
    data = json.loads(json_path.read_text(encoding="utf-8"))
    rows: list[dict] = []
    for elem in data:
        if elem.get("type") == "table" and elem.get("name") == "yt_videos":
            rows = elem.get("data", [])
            break
    urls = [r["url"] for r in rows if r.get("url")]
    return urls[:limit]


def download(urls: list[str], dest: Path, cookies: str | None, cookies_browser: str | None) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    ydl_opts = {
        # Prefer a single progressive file so ffmpeg is not required for merging.
        "format": "best[ext=mp4]/best",
        "outtmpl": str(dest / "%(title)s [%(id)s].%(ext)s"),
        "ignoreerrors": True,
        "noplaylist": True,
        "retries": 3,
        "concurrent_fragment_downloads": 4,
    }
    # YouTube increasingly demands auth for some videos ("Sign in to confirm
    # you're not a bot"). Supply cookies to get past it.
    if cookies:
        ydl_opts["cookiefile"] = cookies
    if cookies_browser:
        ydl_opts["cookiesfrombrowser"] = (cookies_browser,)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download(urls)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=15, help="videos per source (default 15)")
    parser.add_argument("--outdir", default=str(ROOT / "data" / "video_download"))
    parser.add_argument("--cookies", help="path to a cookies.txt file (Netscape format)")
    parser.add_argument("--cookies-from-browser", dest="cookies_browser",
                        help="browser to read cookies from, e.g. chrome / safari / firefox")
    args = parser.parse_args()

    out_root = Path(args.outdir)
    for source in SOURCES:
        json_path = SOURCE_DIR / source
        if not json_path.exists():
            print(f"⚠️  skip — not found: {json_path}")
            continue
        urls = extract_urls(json_path, args.limit)
        channel = json_path.stem
        dest = out_root / channel
        print(f"\n=== {channel}: downloading {len(urls)} videos → {dest} ===")
        for i, u in enumerate(urls, 1):
            print(f"  {i:>2}. {u}")
        download(urls, dest, args.cookies, args.cookies_browser)

    print("\n✅ Done.")


if __name__ == "__main__":
    main()
