"""文件和目录工具"""

from __future__ import annotations

import os
import uuid
from datetime import datetime
from urllib.parse import urlparse


SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".flv"}


def generate_video_id(filename: str = "") -> str:
    """生成可读的 video_id。
    
    示例：
      3246165181.mov  → 3246165181_0531
      my_video.mp4    → my_video_0531
      (空)            → video_0531_a3b2
    """
    import re
    date_str = datetime.now().strftime("%m%d")

    if filename:
        name = os.path.splitext(os.path.basename(filename))[0]
        name = re.sub(r'[^\w\u4e00-\u9fff]', '_', name).strip('_')
        if len(name) > 30:
            name = name[:30]
        return f"{name}_{date_str}"
    else:
        suffix = uuid.uuid4().hex[:4]
        return f"video_{date_str}_{suffix}"


def create_output_dir(video_id: str, base_dir: str = "output") -> str:
    """
    创建输出目录结构：
    output/{video_id}/
    output/{video_id}/frames/
    返回输出目录路径。
    """
    output_dir = os.path.join(base_dir, video_id)
    frames_dir = os.path.join(output_dir, "frames")
    os.makedirs(frames_dir, exist_ok=True)
    return output_dir


def is_video_file(path: str) -> bool:
    """检查扩展名是否为支持的视频格式。"""
    ext = os.path.splitext(path)[1].lower()
    return ext in SUPPORTED_VIDEO_EXTENSIONS


def is_url(source: str) -> bool:
    """判断输入是文件路径还是 URL。"""
    parsed = urlparse(source)
    return parsed.scheme in {"http", "https"}


def get_file_size(path: str) -> int:
    """获取文件大小（字节）。"""
    return os.path.getsize(path)


def write_json(path: str, data: object) -> None:
    import json
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)