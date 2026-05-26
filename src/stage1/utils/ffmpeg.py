"""FFmpeg / FFprobe 命令封装"""

from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Sequence


def _run_command(cmd: Sequence[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            list(cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Command not found: {cmd[0]}. Please install ffmpeg/ffprobe.") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else ""
        stdout = exc.stdout.strip() if exc.stdout else ""
        detail = stderr or stdout or str(exc)
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{detail}") from exc


def run_ffprobe(video_path: str) -> dict:
    """
    调用 ffprobe，返回视频完整信息 JSON。
    包含 streams（视频轨、音频轨、字幕轨）和 format（容器信息）。
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        video_path,
    ]
    result = _run_command(cmd)
    return json.loads(result.stdout)


def run_ffmpeg(args: list[str]) -> str:
    """
    调用 ffmpeg 命令，返回 stdout。
    自动加 -y 覆盖输出文件。
    失败时抛出 RuntimeError。
    """
    cmd = ["ffmpeg", "-y", *args]
    result = _run_command(cmd)
    return result.stdout


def extract_audio(video_path: str, output_path: str) -> str:
    """
    从视频中提取音频。
    输出格式：wav, 16kHz, mono（Whisper 友好）。
    返回输出文件路径。
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    run_ffmpeg([
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        output_path,
    ])
    return output_path


def detect_scenes(video_path: str, threshold: float = 0.3) -> list[float]:
    """
    检测镜头切换时间点。
    返回切换点的时间戳列表（秒）。
    使用 ffmpeg scene filter，从 stderr 中解析 pts_time。
    """
    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-filter:v", f"select='gt(scene,{threshold})',showinfo",
        "-f", "null",
        "-",
    ]
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg not found. Please install ffmpeg.") from exc

    combined = (result.stdout or "") + "\n" + (result.stderr or "")
    times = []
    for match in re.finditer(r"pts_time:([0-9]+(?:\.[0-9]+)?)", combined):
        times.append(float(match.group(1)))

    # 去重与排序，避免 showinfo 重复输出
    unique = sorted({round(t, 3) for t in times if t > 0})
    return unique


def extract_frame(video_path: str, timestamp: float, output_path: str) -> str:
    """
    在指定时间点截取一帧图片。
    返回图片路径。
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    run_ffmpeg([
        "-ss", f"{timestamp:.3f}",
        "-i", video_path,
        "-frames:v", "1",
        "-q:v", "2",
        output_path,
    ])
    return output_path