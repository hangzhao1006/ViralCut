"""
link_input.py — Step 1: download video + metadata via yt-dlp.
"""
import logging
import os
import re

import yt_dlp

logger = logging.getLogger(__name__)

_PLATFORM_PATTERNS: dict[str, list[str]] = {
    "douyin": [r"douyin\.com", r"iesdouyin\.com"],
    "tiktok": [r"tiktok\.com"],
    "bilibili": [r"bilibili\.com", r"b23\.tv"],
    "youtube": [r"youtube\.com", r"youtu\.be"],
    "xiaohongshu": [r"xiaohongshu\.com", r"xhslink\.com"],
}


def _detect_platform(url: str) -> str:
    for platform, patterns in _PLATFORM_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return platform
    return "unknown"


def download_from_url(
    url: str,
    output_dir: str,
    cookie_file: str | None = None,
) -> dict:
    """
    Downloads video and extracts metadata via yt-dlp.

    Returns:
        {
          "video_path": str,   # absolute path to downloaded mp4
          "metadata": {
            "title": str,
            "platform": str,   # "douyin"|"tiktok"|"bilibili"|"youtube"|"xiaohongshu"|"unknown"
            "duration": float,
            "like_count": int | None,
            "view_count": int | None,
            "comment_count": int | None,
            "upload_date": str | None,
            "original_url": str,
            "thumbnail_url": str | None
          }
        }
    """
    os.makedirs(output_dir, exist_ok=True)

    ydl_opts: dict = {
        # Prefer mp4 video + m4a audio; fall back to best single-file mp4
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": os.path.join(output_dir, "%(id)s.%(ext)s"),
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": False,
        # Embed subtitles / thumbnails only if available; never fatal
        "writethumbnail": False,
    }

    if cookie_file:
        ydl_opts["cookiefile"] = cookie_file

    logger.info("Downloading %s → %s", url, output_dir)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info: dict = ydl.extract_info(url, download=True)

        # Prefer the actual filepath recorded by yt-dlp over prepare_filename
        requested = info.get("requested_downloads")
        if requested and isinstance(requested, list) and requested[0].get("filepath"):
            video_path: str = requested[0]["filepath"]
        else:
            video_path = ydl.prepare_filename(info)

    # yt-dlp may not update the extension after remux; normalise to .mp4
    if not video_path.lower().endswith(".mp4"):
        candidate = os.path.splitext(video_path)[0] + ".mp4"
        if os.path.exists(candidate):
            video_path = candidate

    video_path = os.path.abspath(video_path)
    logger.info("Video saved: %s", video_path)

    return {
        "video_path": video_path,
        "metadata": {
            "title": info.get("title"),
            "platform": _detect_platform(url),
            "duration": float(info.get("duration") or 0),
            "like_count": info.get("like_count"),
            "view_count": info.get("view_count"),
            "comment_count": info.get("comment_count"),
            "upload_date": info.get("upload_date"),
            "original_url": url,
            "thumbnail_url": info.get("thumbnail"),
        },
    }
