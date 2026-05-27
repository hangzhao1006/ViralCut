# ViralCut — 爆款结构迁移引擎

从爆款视频中拆解创作结构，迁移到新内容上，生成新的短视频。

## 快速开始

```bash
# 1. 克隆项目
git clone <repo_url>
cd ViralCut

# 2. 安装系统依赖（macOS）
brew install ffmpeg
brew install tesseract

# 3. 安装 Python 依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# .env 里已预填课题提供的 Doubao API Key，直接用即可

# 5. 运行 Stage 1（文件上传链路）
python -m src.stage1.scripts.run_file path/to/video.mp4

# 6. 查看输出
ls output/vid_*/
cat output/vid_*/evidence_package.json
```

## 项目结构

```
ViralCut/
├── README.md
├── requirements.txt
├── .env.example                       # 环境变量模板（Doubao API / Whisper / OCR 配置）
├── .env                               # 实际环境变量（gitignored）
├── .gitignore
│
├── scripts/
│   └── setup.sh                       # 一键安装系统依赖
│
├── output/                            # 处理结果（gitignored）
│   └── vid_{date}_{id}/
│       ├── metadata.json
│       ├── scenes.json
│       ├── keyframes.json
│       ├── frames/                    # 关键帧图片
│       ├── audio.wav
│       ├── audio.json
│       ├── transcript.json
│       ├── asr_info.json
│       ├── ocr.json
│       ├── beats.json
│       ├── basic_analysis.json
│       └── evidence_package.json      # 最终证据包（Stage 2 的输入）
│
├── temp/                              # 临时文件（gitignored）
│
└── src/
    └── stage1/                        # Stage 1: 视频预处理
        ├── types/
        │   └── evidence.py            # 证据包 dataclass 定义（共用）
        │
        ├── utils/                     # 工具函数（共用）
        │   ├── ffmpeg.py              # FFmpeg/FFprobe 命令封装
        │   ├── doubao.py              # 火山方舟 Doubao API 封装
        │   ├── file_utils.py          # 文件路径、临时目录
        │   └── logger.py              # 统一日志
        │
        ├── file_pipeline/             # A同学：文件上传链路（已完成）
        │   ├── input.py               # 文件校验
        │   ├── processors/
        │   │   ├── metadata.py        # FFprobe 元信息
        │   │   ├── scene_detect.py    # 自适应镜头分割
        │   │   ├── keyframe.py        # 关键帧抽取
        │   │   ├── audio.py           # 音频提取
        │   │   ├── asr.py             # FasterWhisper 语音转文字（带VAD+过滤）
        │   │   ├── ocr.py             # OCR（RapidOCR + Doubao fallback）
        │   │   ├── beat.py            # BGM 节拍检测 + 卡点评分
        │   │   └── basic_analysis.py  # 基础统计指标
        │   ├── assembler.py           # 汇总 → EvidencePackage
        │   └── pipeline.py            # 端到端编排
        │
        ├── link_pipeline/             # B同学：链接下载链路（开发中）
        │   ├── input.py               # yt-dlp 下载
        │   ├── processors/            # 同 file_pipeline
        │   ├── assembler.py
        │   └── pipeline.py
        │
        └── scripts/
            ├── run_file.py            # 文件链路测试入口
            └── run_link.py            # 链接链路测试入口
```

## Stage 1 当前状态

### 已完成（file_pipeline）

| Processor | 工具 | 状态 | 说明 |
|-----------|------|------|------|
| metadata | FFprobe | ✅ | 时长/分辨率/帧率/编码/宽高比 |
| scene_detect | FFmpeg | ✅ | 自适应阈值 + 碎镜头合并 |
| keyframe | FFmpeg | ✅ | 中间帧 + 长镜头多帧 |
| audio | FFmpeg | ✅ | 16kHz mono wav |
| asr | FasterWhisper | ✅ | VAD过滤 + hallucination检测 + 质量保护 |
| ocr | RapidOCR + Doubao | ✅ | image hash去重 + 水印过滤 + 连续重复合并 |
| beat | librosa | ✅ | BPM + 节拍时间点 + 卡点评分 |
| basic_analysis | 纯计算 | ✅ | 镜头密度/字幕密度/节奏预估 |

### 待完成（link_pipeline）

B同学负责。下载视频后复用 file_pipeline 的 processors。

## Stage 1 输出示例

运行后终端会显示：

```
=== ViralCut Stage 1 Evidence Summary ===
video_id: vid_20260526_c390334d
source: /path/to/video.mp4
duration: 118.2s
resolution: 1280x720
fps: 24.0
scenes: 55
keyframes: 71
transcript segments: 2
ocr frames: 63
estimated pace: medium
subtitle density: high
output: output/vid_20260526_c390334d/evidence_package.json
```

## 环境变量说明

详见 `.env.example`，主要配置项：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| DOUBAO_API_KEY | 课题提供 | 火山方舟 API Key |
| DOUBAO_ENDPOINT | 课题提供 | 火山方舟 Endpoint |
| WHISPER_MODEL | small | ASR 模型大小：tiny/base/small/medium |
| OCR_METHOD | rapid_then_doubao | OCR 策略：rapid/doubao/rapid_then_doubao |
| OCR_MAX_FRAMES | 0 | 最大OCR帧数，0=不限 |
| ASR_LANGUAGE | auto | 语言：auto/zh/en |

## 开发规则

1. `types/evidence.py` 是共用接口，改动需两人同步
2. `utils/` 共用，谁先写谁push
3. `file_pipeline/` 和 `link_pipeline/` 互不干涉
4. 两条链路输出的 `evidence_package.json` 格式必须一致
5. 测试视频放 `src/stage1/scripts/test_videos/`（gitignored）

## 后续计划

- Stage 2: Multi-Agent 结构分析（脚本/节奏/包装/情绪/卖点）
- Stage 3: 结构迁移引擎
- Stage 4: 素材缺口识别 + 智能降级
- Stage 5: Remotion 视频生成