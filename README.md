# ViralCut — 爆款视频结构迁移引擎

> 从优质样例中**拆解可迁移的创作结构**，迁移到新的主题 / 商品 / 素材上，生成新的短视频方案。
> 强调"迁移方法"而非"复制内容"：当素材撑不起目标结构时，自动识别缺口并补全。

ViralCut 是一个端到端的 AI 短视频创作系统：感知样例 → 多 Agent 拆解结构 → 把结构迁移到新内容并补全素材缺口，全程**可解释、可视化、可调整**。

> 字节跳动 AI 全栈挑战赛 · 工程训练营课题作品。

---

## 目录

- [功能特性](#功能特性)
- [整体流程](#整体流程)
- [核心 AI 架构](#核心-ai-架构)
- [工具协议](#工具协议)
- [安全边界](#安全边界)
- [快速开始](#快速开始)
- [API 接口](#api-接口)
- [项目结构](#项目结构)
- [环境变量](#环境变量)
- [技术栈](#技术栈)
- [团队分工](#团队分工)
- [致谢](#致谢)

---

## 功能特性

| 能力 | 说明 |
|------|------|
| 📥 样例输入 | 支持视频文件上传与链接（yt-dlp）两条链路，输出格式一致 |
| 🔍 多模态证据提取 | 镜头切分、逐帧 OCR、语音转写（ASR）、BGM 节拍、基础统计 |
| 🧩 结构拆解 | 脚本 / 节奏 / 包装 / 价值 / 能量五类结构，逐层拆解 |
| 🎯 双视角分析 | 结构分析（怎么迁移）+ 爆款归因（为什么爆），互相印证 |
| 🔁 结构迁移 | 套用迁移蓝图到新主题 / 商品 / 素材，生成新短视频方案 |
| 🕳️ 缺口识别 + 补全 | 自动发现素材撑不起的结构槽位，给出五种补全策略 |
| ✍️ 单槽位重生成 | 不满意某一段可单独重生成，不必整体重来 |
| 🎬 真实素材适配 | 对用户上传素材做理解、匹配与槽位推荐 |
| 📊 全程可视化 | 实时进度、多轨时间线、结构槽位映射、迁移前后对比 |
| ✅ 质量评估 | 规则化确定性检查，给出可解释的质量分 |

---

## 整体流程

```
样例视频 / 链接
      │
      ▼
┌─────────────────────────────────────────────┐
│ Stage 1 · 证据提取                            │
│ 镜头切分 · OCR · ASR · 节拍 · 基础统计        │
│            → evidence_package.json（客观证据）│
└─────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────┐
│ Stage 2 · 多 Agent 分析（双视角，可并跑）     │
│ ① 结构分析  Blackboard + 依赖 DAG，6 Agent    │
│            → video_structure（含迁移蓝图）    │
│ ② 爆款归因  6 视角并行 → 聚类投票             │
│            → ranked_dimensions（爆款维度排名）│
│ ③ Evaluator 规则化质量评估                    │
└─────────────────────────────────────────────┘
      │  + 新主题 / 商品卖点 / 用户素材
      ▼
┌─────────────────────────────────────────────┐
│ Stage 3 · 结构迁移与素材补全                  │
│ 套用迁移蓝图 → 逐槽位检查 → 缺口识别          │
│ → 五种补全策略 → 新短视频方案                 │
└─────────────────────────────────────────────┘
```

---

## 核心 AI 架构

系统的核心不是"调一个大模型生成结果"，而是一套**证据驱动的多 Agent 工作流**。

### 两套 Agent 团队

证据进入 Stage 2 后，由编排器分发给两套独立、互相印证的 Agent 团队：

**① 结构分析（main）— 黑板架构 + 依赖 DAG**

6 个 Agent 按依赖图调度，结果写入共享黑板（Blackboard），下游 Agent 通过 `read_blackboard` 读取上游结论后再推理：

```
脚本 Script
   └→ 节奏 Rhythm · 包装 Packaging · 价值 Value   (同层，仅依赖 script)
        └→ 能量 Energy → 迁移 Transfer ⇒ 迁移蓝图
```

每个 Agent 都是一个 **ReAct 循环**：模型推理（CoT 分步思考）→ 调用证据工具 → 观察结果 → 继续推理，直到产出最终 JSON。

**② 爆款归因（leo）— 并行集成**

6 个分析视角（情感 / 叙事 / 社会 / 信息 / 制作 / 行为）通过 `asyncio` 并行运行，各自独立给出发现；再由合成 Agent **语义聚类**相似维度、按「认同 Agent 数 × 平均强度」**投票排名**，输出 `ranked_dimensions`。

**③ Evaluator — 规则化质量评估**

对最终结构做确定性检查（schema 完整性、判断是否有证据支撑、时间线断层、迁移蓝图强度），给出可解释的质量分。**这是规则化的确定性评估，不是训练得到的奖励模型，也不触发自我纠正循环**——刻意保持可解释、可复现。

### 用到的方法 / 范式

| 范式 | 在哪里 |
|------|--------|
| ReAct（推理-行动循环） | 每个结构分析 Agent 的工具调用循环 |
| Chain-of-Thought | 各 Agent prompt 内置"分析步骤"，先分步推理再产出 |
| Tool Use / Function Calling | 10 个证据工具，标准 OpenAI tools 协议 |
| Blackboard 黑板架构 | Agent 间共享分析结论 |
| 依赖 DAG 编排 | 按依赖图分层调度，而非死串行 |
| 并行集成 + 合成 | 爆款归因的多视角并行 → 聚类投票 |

---

## 工具协议

结构分析的每个 Agent 不直接拿到全部数据，而是按需调用以下工具从证据索引（TimelineIndex）和黑板读取信息。所有工具走标准 OpenAI Function Calling 协议（`tools` schema + `tool_calls`）：

| 工具 | 作用 |
|------|------|
| `get_overview` | 视频整体概况：时长 / 分辨率 / 镜头数 / 节奏 / 字幕密度 |
| `query_timeline` | 查询时间段内的镜头、关键帧、画面文字、语音、节拍 |
| `compute_metrics` | 计算时间段的镜头密度、平均镜头时长、节拍密度 |
| `search_text` | 搜索画面中含指定关键词的帧 |
| `get_segment_evidence` | 获取某段落内的全部证据 |
| `get_cut_beat_alignment` | 镜头切换与音乐节拍的对齐程度 |
| `get_all_display_texts` | 所有关键帧画面文字，按时间排列 |
| `read_blackboard` | 读取其他 Agent 已完成的分析结果 |
| `look_at_keyframe` | 查看关键帧实际画面（**受视觉预算限制**） |
| `get_vision_budget_status` | 查询视觉调用预算使用情况 |

---

## 安全边界

- **API Key 隔离**：所有密钥只放在 `.env`（已 gitignored），代码中不硬编码；Docker 通过 `env_file` 注入。
- **视觉调用预算**：`look_at_keyframe` 这类昂贵的多模态调用受**全局 + 单 Agent** 双重上限约束（`STAGE2_VISION_MAX_CALLS_TOTAL` / `_PER_AGENT`），防止失控消耗。
- **优雅降级**：Stage 2 `both` 模式下，爆款归因（leo）若连接失败或 Agent 运行失败，会被隔离跳过，结构分析（核心能力）照常产出，不会拖垮整个任务。
- **可解释优先**：Evaluator 为规则化确定性检查而非黑盒；所有结构判断都可回溯到 Stage 1 的客观证据。
- **失败保留**：Stage 1 完成即落盘，Stage 2 失败时仍保留并展示 Stage 1 结果。
- **强制确认**：Stage 1 跑完一定暂停等用户确认，Stage 2 只能由用户显式触发。

---

## 快速开始

### 方式一：本地开发（推荐用于调试）

```bash
# 1. 系统依赖（macOS）
brew install ffmpeg

# 2. Python 环境（必须 3.11，3.13 与 onnxruntime/easyocr 不兼容）
conda create -n viralcut python=3.11 -y
conda activate viralcut
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env          # .env 已预填课题提供的 Doubao Key

# 4. 启动后端（项目根目录，不要加 --reload）
python -m uvicorn backend.main:app --port 8000

# 5. 启动前端（另开终端）
cd frontend && npm install && npm run dev
#  → http://localhost:5173  （dev server 自动把 /api 代理到本地 8000）
```

### 方式二：Docker（一键起全栈）

```bash
cp .env.example .env
docker compose up -d --build
#  前端 → http://localhost:3030
#  后端 → http://localhost:8080
```

> 改了前端代码后，只重建前端即可：`docker compose up -d --build frontend`
> （不带服务名的 `--build` 会连后端一起重建，后端镜像很大，导出会慢好几分钟。）

### 命令行单跑 Stage 1（无需前端）

```bash
python -m src.stage1.scripts.run_file path/to/video.mp4   # 文件链路
python -m src.stage1.scripts.run_link "<视频链接>"          # 链接链路
cat output/vid_*/evidence_package.json
```

---

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/analyze` | 上传视频，跑 Stage 1 |
| POST | `/api/analyze/link` | 链接视频，跑 Stage 1 |
| POST | `/api/analyze/restage2` | 复用 Stage 1 证据，单独触发 Stage 2（`main`/`leo`/`both`） |
| GET | `/api/analyze/{task_id}/status` | 轮询任务状态与实时进度 |
| GET | `/api/analyze/{task_id}/result` | 获取结果（Stage 1-only / leo 部分结果 / 完整结果） |
| GET | `/api/samples` · `/api/samples/{id}` | 列出 / 加载已分析样例 |
| POST | `/api/assets/upload` | 上传并分析用户真实素材 |
| POST | `/api/migrate` · `/migrate/stream` · `/migrate/slot` | 结构迁移 / 流式迁移 / 单槽位重生成 |
| GET | `/api/health` | 健康检查 |

---

## 项目结构

```
ViralCut/
├── docker-compose.yml
├── requirements.txt
├── .env.example / .env (gitignored)
│
├── src/
│   ├── stage1/                     # 证据提取
│   │   ├── file_pipeline/          # 文件上传链路（faster-whisper + RapidOCR）
│   │   ├── link_pipeline/          # 链接下载链路（yt-dlp + whisper + EasyOCR）
│   │   ├── types/  utils/  scripts/
│   │
│   ├── stage2/                     # 多 Agent 分析
│   │   ├── framework/
│   │   │   ├── base_agent.py       # ReAct 工具调用循环
│   │   │   ├── blackboard.py       # 共享黑板
│   │   │   └── tools.py            # 10 个证据工具 + 视觉预算
│   │   ├── agents/                 # script/rhythm/packaging/value/energy/transfer
│   │   ├── prompts/                # 各 Agent 的 CoT prompt
│   │   ├── evaluator.py            # 规则化质量评估
│   │   ├── pipeline.py             # 结构分析编排（依赖 DAG）
│   │   └── leo_variant/            # 爆款归因（并行多视角 → 聚类投票）
│   │
│   └── stage3/                     # 结构迁移与素材补全
│       ├── migrate.py              # 结构迁移
│       ├── migrate_slot.py         # 单槽位重生成
│       ├── migrate_stream.py       # 流式迁移
│       ├── asset_analyzer.py       # 真实素材理解
│       ├── asset_matcher.py        # 素材-槽位匹配
│       └── prompts/
│
├── backend/                        # FastAPI 服务
│   ├── main.py
│   ├── api/                        # analyze / assets / migrate 路由
│   ├── tasks/analysis_task.py      # 任务编排（Stage1 → Stage2 both）
│   └── store/task_store.py         # 任务状态 + 实时进度
│
└── frontend/                       # React + TS + Vite + Tailwind
    ├── index.html
    └── src/
        ├── App.tsx                 # 主流程 + 首页门控
        ├── components/
        │   ├── Landing.tsx         # 产品首页
        │   ├── LeoAgentGrid.tsx    # 爆款归因投票可视化
        │   ├── analysis/           # Stage2LoadingView / AgentProgress / 时间线
        │   └── migration/          # 迁移表单 / 预览
        └── lib/                    # api.ts / types.ts / colors.ts
```

---

## 环境变量

详见 `.env.example`，主要配置：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DOUBAO_API_KEY` / `DOUBAO_ENDPOINT` | 课题提供 | 火山方舟 Doubao Seed 2.0 Lite |
| `WHISPER_MODEL` | small | ASR 模型大小 |
| `OCR_METHOD` | rapid_then_doubao | OCR 策略 |
| `LEO_BASE_URL` / `LEO_API_KEY` / `LEO_MODEL` | — | 爆款归因变体的模型配置（可复用 Doubao） |
| `LEO_NUM_AGENTS` | 6 | 并行视角数 |
| `STAGE2_VISION_MAX_CALLS_TOTAL` / `_PER_AGENT` | 16 / 4 | 视觉调用预算上限 |

---

## 技术栈

- **推理**：Doubao Seed 2.0 Lite（火山方舟，OpenAI 兼容）
- **感知层**：faster-whisper / openai-whisper · RapidOCR / EasyOCR · librosa · scenedetect · yt-dlp · FFmpeg
- **后端**：FastAPI · Docker
- **前端**：React · TypeScript · Vite · Tailwind CSS
- **多 Agent**：ReAct · Chain-of-Thought · Tool Use / Function Calling · Blackboard · 依赖 DAG · 并行集成

---

## 开发规则

1. `src/stage1/types/evidence.py` 是共用接口，改动需同步。
2. 两条 Stage 1 链路输出的 `evidence_package.json` 格式必须一致，Stage 2 才能 pipeline 无关。
3. 前端数据契约（`lib/api.ts` 路径与字段、`types.ts`、状态机值）锁定，视觉样式可自由改（见 `FRONTEND_GUIDE.md`）。
4. `tsc --noEmit` 必须通过——Docker build 会跑 `tsc && vite build`。
5. `.env`、`output/`、`node_modules/`、模型缓存、测试视频均 gitignored。

---

## 团队分工

> 两人团队，按模块分工（请按实际情况补充姓名）。

| 模块 | 负责人 |
|------|--------|
| Stage 1 文件链路（file_pipeline）、Stage 2 结构分析（main）、Stage 3 结构迁移与素材补全、前端集成 | 赵航 |
| Stage 1 链接链路（link_pipeline）、Stage 2 爆款归因（leo_variant）、Stage 3 结构迁移与素材补全、前端集成优化 | _（待填）_ |

**AI 工具使用说明**：编码与调试使用 Claude/ChatGPT 辅助；结构分析、文案整理使用 LLM 辅助；核心思路、任务拆解、架构设计与关键功能实现均由团队自主完成。

---

## 致谢

- 课题来源：字节跳动 AI 全栈挑战赛 · 工程训练营
- 推理能力：火山方舟 Doubao Seed 2.0 Lite
- 开源依赖：faster-whisper、RapidOCR、EasyOCR、librosa、yt-dlp、FFmpeg、FastAPI、React、Vite

---

## 许可证

本项目为比赛课题作业，仅供学习与赛事评审使用。