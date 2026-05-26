"""
测试入口：python -m src.stage1.scripts.run_file path/to/video.mp4
"""

from __future__ import annotations

import sys

from dotenv import load_dotenv
load_dotenv()  # 加载 .env 文件中的环境变量

from src.stage1.file_pipeline.pipeline import run


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m src.stage1.scripts.run_file path/to/video.mp4")
        raise SystemExit(1)

    video_path = sys.argv[1]
    package = run(video_path)

    print("\n=== ViralCut Stage 1 Evidence Summary ===")
    print(f"video_id: {package.video_id}")
    print(f"source: {package.source.local_path}")
    print(f"duration: {package.metadata.duration}s")
    print(f"resolution: {package.metadata.width}x{package.metadata.height}")
    print(f"fps: {package.metadata.fps}")
    print(f"scenes: {len(package.scenes)}")
    print(f"keyframes: {len(package.keyframes)}")
    print(f"transcript segments: {len(package.transcript)}")
    print(f"ocr frames: {len(package.ocr_results)}")
    print(f"estimated pace: {package.basic_analysis.estimated_pace}")
    print(f"subtitle density: {package.basic_analysis.subtitle_density}")
    print(f"output: output/{package.video_id}/evidence_package.json")


if __name__ == "__main__":
    main()