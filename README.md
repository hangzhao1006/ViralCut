# ViralCut — 爆款结构迁移引擎

从爆款视频中拆解创作结构，迁移到新内容上，生成新的短视频。

## 完整目录结构

```
viralcut/
├── README.md                          # 本文件
├── requirements.txt                   # Python 依赖
├── .gitignore                         # git 忽略规则
├── .env.example                       # 环境变量模板（API key 等）
│
├── scripts/
│   └── setup.sh                       # 一键安装系统依赖（ffmpeg/yt-dlp/whisper）
│
├── output/                            # 处理结果输出（gitignored）
│
├── temp/                              # 临时文件（gitignored）
│
└── src/
    └── stage1/                        # Stage 1: 视频预处理
        ├── README.md                  # Stage 1 说明文档
        │
        ├── types/                     # 【共用】数据类型，开工前一起定好
        │   └── evidence.py            # EvidencePackage dataclass
        │
        ├── utils/                     # 【共用】工具函数，谁先写谁push
        │   ├── ffmpeg.py              # FFmpeg/FFprobe 命令封装
        │   ├── file_utils.py          # 路径、临时目录、video_id
        │   └── logger.py              # 日志
        │
        ├── file_pipeline/             # 【A同学】文件上传链路
        │   ├── input.py               # 文件校验（格式、大小）
        │   ├── processors/
        │   │   ├── metadata.py        # FFprobe 元信息
        │   │   ├── scene_detect.py    # 镜头分割
        │   │   ├── keyframe.py        # 关键帧抽取
        │   │   ├── audio.py           # 音频分离
        │   │   ├── asr.py             # Whisper 语音转文字
        │   │   ├── ocr.py             # OCR 画面文字
        │   │   └── beat.py            # 节拍检测
        │   ├── assembler.py           # 汇总 → EvidencePackage
        │   └── pipeline.py            # 端到端入口
        │
        ├── link_pipeline/             # 【B同学】链接下载链路
        │   ├── input.py               # yt-dlp 下载、平台识别
        │   ├── processors/
        │   │   ├── metadata.py
        │   │   ├── scene_detect.py
        │   │   ├── keyframe.py
        │   │   ├── audio.py
        │   │   ├── asr.py
        │   │   ├── ocr.py
        │   │   └── beat.py
        │   ├── assembler.py
        │   └── pipeline.py
        │
        └── scripts/
            ├── run_file.py            # python run_file.py test.mp4
            └── run_link.py            # python run_link.py "https://..."
```

## 环境搭建

```bash
# 系统依赖（macOS）
brew install ffmpeg
brew install yt-dlp
brew install tesseract

# Python 依赖
pip install -r requirements.txt

# 环境变量
cp .env.example .env
```

## 快速验证

```bash
# 文件链路
python -m src.stage1.scripts.run_file path/to/video.mp4

# 链接链路
python -m src.stage1.scripts.run_link "https://www.douyin.com/video/xxx"

# 查看输出
cat output/{video_id}/evidence_package.json
```

## Stage 1 详细说明

### 目标

输入一个视频（文件或链接），输出标准化的证据包 JSON，供 Stage 2 的 Agent 分析使用。

### 两条链路

| 链路 | 输入 | 负责人 |
|------|------|--------|
| file_pipeline | 本地视频文件 | A同学 |
| link_pipeline | 视频链接（抖音/B站等） | B同学 |

两条链路最终输出格式完全一致，都是 EvidencePackage。

### Processor 说明

| Processor | 输入 | 输出 | 工具 |
|-----------|------|------|------|
| metadata | 视频路径 | 时长/分辨率/帧率/编码 | FFprobe |
| scene_detect | 视频路径 | 镜头列表（起止时间） | FFmpeg |
| keyframe | 视频路径 + 镜头列表 | 每个镜头的关键帧jpg | FFmpeg |
| audio | 视频路径 | 音频wav文件 | FFmpeg |
| asr | 音频文件 | 带时间戳的文字 | Whisper |
| ocr | 关键帧图片 | 每帧的画面文字 | Tesseract / LLM |
| beat | 音频文件 | BPM + 节拍时间点 | librosa |

### Processor 依赖关系

```
metadata        （无依赖）
scene_detect    （无依赖）     → keyframe → ocr
audio           （无依赖）     → asr
                               → beat
```

### 输出结构

```
output/{video_id}/
├── metadata.json
├── scenes.json
├── frames/
│   ├── scene_000.jpg
│   ├── scene_001.jpg
│   └── ...
├── audio.wav
├── transcript.json
├── ocr.json
├── beats.json
└── evidence_package.json       # 最终证据包
```

### 开发规则

1. types/evidence.py 开工前一起定好，要改两人一起改
2. utils/ 谁先写谁 push，另一个人直接用
3. file_pipeline/ 和 link_pipeline/ 互不干涉
4. 两条链路输出的 evidence_package.json 格式必须一致

### 合并计划

两条链路都跑通后：
1. 对比两边 processors，每个选更好的
2. 合成共用 processors/
3. 两个 input 保留
4. 写统一的 pipeline.py
5. 删掉 file_pipeline/ 和 link_pipeline/
