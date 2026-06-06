# Link Pipeline

End-to-end Stage 1 pipeline for **online video URLs** (Douyin / TikTok / Bilibili /
YouTube / Xiaohongshu). Downloads the video, then runs shot detection, keyframe
extraction, ASR, OCR, audio/BPM analysis, and (optionally) VLM keyframe
descriptions, producing a structured `evidence_package.json` for Stage 2.

> For local video **files**, use the sibling `file_pipeline/` instead.

## Files

| File | Role |
|------|------|
| `link_input.py`   | `yt-dlp` download + platform detection |
| `processors.py`   | PySceneDetect shots, FFmpeg keyframes, Whisper ASR, EasyOCR, librosa BPM |
| `vlm_enricher.py` | Optional VLM keyframe descriptions (OpenRouter) |
| `pipeline_link.py`| CLI entrypoint; merges results into structured JSON |

## Usage

```bash
# Default
python src/stage1/link_pipeline/pipeline_link.py "https://www.youtube.com/shorts/..."

# With options
python src/stage1/link_pipeline/pipeline_link.py \
  --output-dir ./out --whisper-model small "https://..."

# Interactive (prompts for URL)
python src/stage1/link_pipeline/pipeline_link.py
```

The script inserts its own directory onto `sys.path`, so the flat
`from link_input import ...` imports work from any working directory.

## Config

See the **Link pipeline** section of the repo-root `.env.example`:

- `OUTPUT_DIR`        — where outputs are written
- `COOKIE_FILE`       — Netscape cookie file for login/age-gated content
- `OPENROUTER_API_KEY`— required for `--vlm-model` keyframe descriptions

## Output

```
output/{video_id}/
├── metadata.json          technical params (ffprobe)
├── scenes.json
├── keyframes.json
├── frames/frame_NNN.jpg
├── audio.wav / audio.json
├── transcript.json / asr_info.json
├── ocr.json
├── beats.json
├── basic_analysis.json
└── evidence_package.json  ← Stage 2 entry point
```
