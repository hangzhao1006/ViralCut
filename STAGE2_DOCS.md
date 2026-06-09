# ViralCut · Stage 2 逻辑文档

> 给队友和 AI Agent 读：本文档说明 **Stage 2（爆款归因 + 结构分析）的完整前端逻辑**，包括 UI 状态机、数据流、各组件职责，以及哪些能改、哪些不能动。
>
> 一句话原则：**界面随便改，数据字段名 / API 路径 / 状态值不能动。**

---

## 1. Stage 2 是什么

Stage 2 把 Stage 1 提取的原始证据（`evidence_package`）喂给多个 AI Agent，产出两套分析结果：

| 模式 | 变量名 | 产出 | 用处 |
|------|--------|------|------|
| **leo**（爆款归因） | `synthesis_result` | 6 个视角 Agent 并行投票 → 归因排名 | 显示爆款维度 + 机制解释 |
| **main**（结构分析） | `video_structure` | 6 个 Agent 串行 → 脚本/节奏/包装/价值/能量/迁移蓝图 | 时间线工作台 + 结构迁移 |
| **both**（同时跑） | 两者都有 | Leo 先完成（并行快），Main 后完成（串行慢） | 当前默认模式 |

前端固定使用 `stage2_variant = 'both'`，即同时跑两套。

---

## 2. 触发 Stage 2

```
用户在 Stage 1 预览页点"进入 Stage 2 →"
        ↓
App.tsx: handleContinueStage2()
  1. 保存当前 analysis.video_url → loadingVideoUrl（视频 URL 一会儿要用）
  2. setAnalysis(null)          （清空，开始 loading 状态）
  3. setTaskStatus({ stage: 'stage2', status: 'processing', ... })
  4. POST /api/analyze/restage2  → 拿到新 task_id
  5. pollTask(task_id)           （2 秒轮询开始）
```

**关键：** `analysis` 被设为 `null` 后，`loadingVideoUrl` 是唯一保存了视频地址的地方，`Stage2LoadingView` 靠它播放视频。

---

## 3. UI 状态机

轮询返回的 `taskStatus.stage` / `taskStatus.status` 驱动以下四种 UI 状态，**互斥渲染**：

```
taskStatus.stage === 'stage2'
AND analysis === null
        ↓
  【Stage2LoadingView】          ← Leo 阶段 & Main 前期
  （6 Agent + 视频循环 + 右侧占位）
        ↓
  Leo 完成：analysis.synthesis_result 有值
        ↓
  【Stage2LoadingView 内 LeoAgentGrid 展开结果】
  （Main 仍在跑；左侧 Agent 仍在流式）
        ↓
  Main 完成：analysis.video_structure 有值 → mainReady = true
        ↓
  【完整工作台】（三栏 + 底部 Tab）
```

> `App.tsx` 第 301–311 行：用三元 `taskStatus.stage === 'stage2'` 判断显示哪个组件。

---

## 4. Stage 2 加载界面：`Stage2LoadingView`

**文件：** `frontend/src/components/analysis/Stage2LoadingView.tsx`

**触发条件：** `analyzing && taskStatus?.stage === 'stage2'`

### 4.1 布局（三栏 grid）

```
┌──────────────────────────────────────────────────────────────┐
│ 进度条（渐变，随 leoReady + completedCount 推进）              │
│ 标题栏：◐ Stage 2 — 结构分析 · N/6 Agent 完成   00:42        │
├─────────────────┬──────────────────────┬────────────────────┤
│  结构 Agent 列   │   视频（黑底循环播放）  │  当前片段分析（占位） │
│  [300px 固定]   │   [flex: 1]          │  [320px 固定]      │
│                 │   position: relative  │                    │
│  Script  ◐      │   黑色背景            │  这段在做什么  —    │
│  └ 分析脚本…▌   │   <video autoPlay    │  节奏          —    │
│  Rhythm  ○      │    loop muted>       │  价值类型      —    │
│  Packaging ○   │   object-fit:contain  │  注意力强度    —    │
│  Value   ○      │   （等比缩放，黑边）   │                    │
│  Energy  ○      │                      │  （分析完成后填充）  │
│  Transfer ○    │                      │                    │
├─────────────────┴──────────────────────┴────────────────────┤
│  LeoAgentGrid（Leo 未完成时显示"分析中"，完成后展示归因结果）   │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 左侧 Agent 流式文字

- 每隔 55ms 递增一个 `tick` 计数器
- `getDisplayedText(tick, agentKey, agentIdx)` 根据 tick 确定性地计算当前应显示的字符数（每个 Agent 有 28 tick 的初始偏移，避免全部同步）
- 每条"思考语句"打完后暂停 18 tick，然后切换下一条
- `▌` 光标用 CSS `blink` 动画（已在 `index.css` 定义了 `@keyframes blink`）
- 实际 Agent 状态：`completed_agents[]` 里的 key → 显示绿色 ✓；`current_step` 对应的 → 蓝色高亮；其余 → 半透明等待

### 4.3 中间视频

视频用 `position: absolute; inset: 0` 内嵌于 `position: relative` 的父格，**父格无 in-flow 内容**，因此不参与 CSS Grid 行高计算。行高由左右两列内容决定，视频在格内 `object-fit: contain` 等比缩放，多余区域黑色填充。

### 4.4 右侧占位面板

四张卡片（Script / Rhythm / Value / Energy）与完成后工作台的 `AgentPanel` **视觉结构完全一致**，但内容固定为 `—` + "分析完成后显示"。当 `video_structure` 到位后，整个 `Stage2LoadingView` 被完整工作台替换，占位消失。

---

## 5. 完整工作台（mainReady 后）

**触发条件：** `analysis.video_structure` 存在（`mainReady = true`）

### 5.1 三栏布局

```
grid-cols-[300px_minmax(0,1fr)_320px]  min-h-[520px]
```

| 栏 | 内容 | 关键组件 |
|---|---|---|
| 左 (300px) | 素材库 + 迁移表单 | `AssetLibrary` + `MigrationForm` |
| 中 (flex) | 视频播放器（带时间同步） | `VideoPlayer` |
| 右 (320px) | 当前片段实时分析 | `AgentPanel` |

### 5.2 底部 Tab

三个 Tab 互斥：

| Tab | 组件 | 数据来源 |
|---|---|---|
| 分析时间线 | `MultiTrackTimeline` | `video_structure` + `evidence_package` |
| 数据详情 | `DataInspector` | 同上 |
| 迁移预览 | `MigrationPreview` 或 `MigrationProgress` | `migration` state |

### 5.3 最底部：`LeoAgentGrid`

始终挂在工作台最下方。`synthesis_result` 有值时展示 6 个 Agent 的投票结果 + Cluster 卡片；无值时不渲染（`null`）。

---

## 6. Leo 归因：`LeoAgentGrid`

**文件：** `frontend/src/components/LeoAgentGrid.tsx`

6 个 Agent（情感 / 叙事 / 社会 / 信息 / 制作 / 行为）并行跑，结果合并为 `ranked_dimensions`。

### 数据结构

```typescript
SynthesisResult {
  ranked_dimensions: ClusteredDimension[]  // 按强度排名的爆款维度
  top_viral_reason: string                 // 总结性原因
}

ClusteredDimension {
  dimension_name:        string    // 维度名称（如"情感共鸣触发"）
  viral_mechanism:       string    // 爆款机制详细描述
  agent_agreement_count: number    // 几个 Agent 同意
  avg_strength_score:    number    // 平均强度 0-10
  supporting_agent_ids:  number[]  // 哪些 Agent 支持（0-5 对应 6 个 Agent）
}
```

### 渲染逻辑

- 每个 Agent 对应一列（共 6 列），顶部显示旋转环形图（未完成）/ 绿色完整圆（完成）
- `agentDim(agentId)` 找该 Agent 在 `ranked_dimensions` 里投票支持的第一条
- 气泡（SpeechBubble）：只显示维度名称 + 排名编号（`投票 #01`），**不显示详细说明**（已删除，避免重复）
- 下方 Cluster 卡片按排名列出维度名、爆款机制、进度条、支持 Agent 标签

---

## 7. 结构分析：6 个主线 Agent

**运行顺序（串行）：** Script → Rhythm → Packaging → Value → Energy → Transfer

| Agent | 输出字段 | 用途 |
|---|---|---|
| Script | `video_structure.script_structure` | 脚本段落 / 钩子 / CTA |
| Rhythm | `video_structure.rhythm_structure` | 节奏 / BPM / 每段镜头频率 |
| Packaging | `video_structure.packaging_structure` | 视觉包装策略 |
| Value | `video_structure.value_strategy` | 内容价值类型 |
| Energy | `video_structure.energy_curve` | 注意力能量曲线 |
| Transfer | `video_structure.transfer_blueprint` | 迁移蓝图（结构模板 + 编辑规则） |

`taskStatus.current_step` = 当前正在运行的 agent key（如 `'script'`）
`taskStatus.completed_agents` = 已完成的 agent key 数组

**注意嵌套：** Transfer Agent 的蓝图有双层嵌套，App.tsx 里有专门兼容逻辑：

```typescript
// App.tsx ~L210
const tb = structure?.transfer_blueprint as { transfer_blueprint?: TransferBlueprint; ... }
const blueprint =
  tb?.transfer_blueprint?.structure_template ? tb.transfer_blueprint
  : (tb as TransferBlueprint)?.structure_template ? (tb as TransferBlueprint)
  : undefined;
```

**这段逻辑不能动**，否则迁移蓝图拿不到，左栏迁移表单不出现。

---

## 8. AgentPanel：当前片段分析

**文件：** `frontend/src/components/analysis/AgentPanel.tsx`

随视频播放时间实时更新，四张卡片：

| 卡片 | 数据来源字段 |
|---|---|
| 这段在做什么 | `script_structure.segments[当前].function` + `core_text` |
| 节奏 | `rhythm_structure.segment_rhythm[当前].pace` + `rhythm_driver` |
| 价值类型 | `value_strategy.value_strategy.value_type` + `primary_value` |
| 注意力强度 | `energy_curve.energy_curve[当前].energy_level` + `role` |

用 `getCurrentSegment(currentTime, segments)` 定位当前片段（来自 `lib/timeline.ts`）。

---

## 9. 结构迁移（Stage 3）

### 9.1 触发流程

```
用户在左栏填写主题 / 卖点 / 目标类型
        ↓
MigrationForm.submit() → onMigrate(newContent)
        ↓
App.tsx: handleMigrate()
  POST /api/migrate/stream（流式 SSE）
  每个 chunk 追加到 streamText
  MigrationProgress 实时渲染部分解析结果
        ↓
流结束（type: 'done'）→ setMigration(result)
  MigrationPreview 渲染完整迁移结果
```

### 9.2 关键数据

```typescript
MigrationResult {
  migrated_slots:      MigratedSlot[]   // 每个结构槽的迁移方案
  overall_feasibility: number           // 整体可迁移度
  gap_summary:         { filled, gaps, gap_slots }
  applied_rules:       string[]
  new_script:          string
}

MigratedSlot {
  slot_id:          string
  slot_type:        string
  duration_seconds: number
  status:           'filled' | 'gap' | 'restructured' | 'aigc_needed'
  migrated_content: { text?, visual? }
  gap:              { missing, affected_requirement } | null
  fill_strategy:    { type, description, alternative? } | null
}
```

### 9.3 骨架映射（`SkeletonMap`，在 `MigrationPreview.tsx` 内）

展开「查看骨架映射关系」后显示，**高度不限**（已移除 `max-h` 限制）：

- **左列**（爆款骨架）：每个 Slot 固定 64px 高，不可交互
- **中列**（SVG 箭头）：L 形折线，从左侧 Slot 中点水平到轴线 → 竖直 → 水平到右侧 Slot 中点；拐点在轴线位置；若右侧 Slot 高度为 0，箭头消失
- **右列**（新视频）：每两个 Slot 之间有 6px 拖动手柄（`cursor: row-resize`），拖动边界时上下两个 Slot 总高度守恒，单个 Slot 最小可压到 0（可从相邻手柄恢复）

拖动逻辑（`handleMouseDown` 闭包）：
```
mousedown → 捕获 h0（上方高度）、h1（下方高度）、startY
mousemove → delta = currentY - startY
            newH0 = clamp(0, h0+h1, h0+delta)
            newH1 = (h0+h1) - newH0
```

---

## 10. ❌ 绝对不能改的

改了这些 = 前后端对不上 / 渲染拿到 undefined / 功能断掉。

### 10.1 API 路径和参数名（`lib/api.ts`）

| 不能动的 | 原因 |
|---|---|
| `/api/analyze/restage2` 路径 | 后端路由 |
| 请求体字段：`video_id` / `stage2_variant` / `pause_after_stage1` | 后端按名解析 |
| 轮询路径：`/api/analyze/{task_id}/status` / `/result` | 后端路由 |
| `API_BASE = '/api'` | 必须是相对路径走代理，改成绝对 URL 会跨域 |

### 10.2 `types.ts` 字段名

这些字段名逐字对应后端 JSON，**改名 = undefined**：

- `AnalysisResult`：`video_id` / `video_url` / `video_structure` / `synthesis_result` / `stage2_variant` / `stage1_only` / `main_loading` / `evidence_package`
- `VideoStructure`：`script_structure` / `rhythm_structure` / `packaging_structure` / `value_strategy` / `energy_curve` / `transfer_blueprint` / `evaluation` / `duration`
- `TransferBlueprint`：`structure_template` / `editing_rules` / `adaptation_guidance`
- `SynthesisResult`：`ranked_dimensions` / `top_viral_reason` / `ClusteredDimension` 各字段
- `MigratedSlot`：`slot_id` / `status` / `migrated_content` / `gap` / `fill_strategy`

### 10.3 状态值字面量

轮询认这些字符串，**不能改名/拼错**：

```typescript
status: 'processing' | 'stage1_done' | 'done' | 'failed'
stage:  'stage1' | 'stage2'
stage2_variant: 'main' | 'leo' | 'both'
MigratedSlot.status: 'filled' | 'gap' | 'restructured' | 'aigc_needed'
```

### 10.4 双层嵌套蓝图取值（App.tsx ~L210-L216）

`transfer_blueprint.transfer_blueprint.structure_template` 的兼容取值逻辑，**一个字不能动**，否则左栏迁移表单不出现。

### 10.5 `lib/colors.ts` 的 key

`FUNCTION_COLORS` / `PACE_COLORS` / `STRATEGY_LABELS` 的 key 对应后端枚举值。**key 不能改**，value（颜色 / 中文标签）随意。

### 10.6 `lib/timeline.ts` / `lib/streamParse.ts`

- `timeline.ts`：时间换算 + `getCurrentSegment` 定位；播放头位置 CSS `calc` 别改成百分比乘法
- `streamParse.ts`：流式 JSON 增量解析，迁移流式预览依赖它

### 10.7 `loadingVideoUrl` 状态（App.tsx）

`handleContinueStage2` 必须在 `setAnalysis(null)` **之前**保存 `analysis.video_url`，否则 Stage2LoadingView 没有视频可播。顺序不能换。

---

## 11. ✅ 可以自由改的

| 可改内容 | 说明 |
|---|---|
| 配色 / 渐变 / 暗色模式 | Tailwind 类、内联 style 颜色值 |
| 间距 / 圆角 / 阴影 | padding / margin / border-radius |
| 字体 / 字号 / 字重 | 不影响数据 |
| Stage2LoadingView 流式文字内容 | `THINKING_PHRASES` 里的短语可任意替换 |
| Stage2LoadingView 动画速度 | `tick` 间隔 55ms、偏移 28 tick、暂停 18 tick 均可调 |
| LeoAgentGrid 布局 / 卡片样式 | 只要数据字段名不改 |
| AgentPanel 卡片排版 | 只要读取字段路径不改 |
| MigrationPreview 视觉 | 骨架映射 SLOT_H / HANDLE_H / ARROW_W 可调 |
| SkeletonMap 拖动体验 | 初始高度、最小高度阈值（目前 32px 以上才显文字）可调 |
| 新增组件 / 可视化 | 只要数据从现有 types 取，随意加 |
| 文案 / 中文标签 | 所有显示文字 |

---

## 12. 文件地图

| 文件 | 职责 | 改动自由度 |
|---|---|---|
| `App.tsx` | 主状态机、流程编排、渲染分支 | 外观 ✅；状态逻辑 / 嵌套蓝图取值 ❌ |
| `lib/api.ts` | 后端通信（路径 / 参数） | ❌ 契约层 |
| `types.ts` | 后端 JSON 对应类型 | 字段名 ❌；可加新可选字段 |
| `lib/colors.ts` | 颜色 / 标签映射 | key ❌ / value ✅ |
| `lib/timeline.ts` | 时间换算 / 片段定位 | ❌ |
| `lib/streamParse.ts` | 流式 JSON 增量解析 | ❌ |
| `components/analysis/Stage2LoadingView.tsx` | Stage2 加载界面（3 栏 + 流式文字 + 视频 + 占位） | 外观全 ✅ |
| `components/analysis/AgentProgress.tsx` | Stage1 步骤进度面板（Stage2 期间不再显示） | 外观 ✅ |
| `components/analysis/AgentPanel.tsx` | 右栏当前片段分析（4 张卡片） | 外观 ✅ |
| `components/analysis/VideoPlayer.tsx` | 视频 + 叠层（segment 标注）| 外观 ✅；时间同步逻辑 ❌ |
| `components/analysis/MultiTrackTimeline.tsx` | 底部多轨时间线（点击跳转） | 外观 ✅；播放头 calc ❌ |
| `components/LeoAgentGrid.tsx` | 爆款归因 6 Agent + Cluster 卡片 | 外观全 ✅ |
| `components/AssetLibrary.tsx` | 素材上传 / 管理 | 外观 ✅ |
| `components/DataInspector.tsx` | 数据详情 Tab | 外观 ✅ |
| `components/migration/MigrationForm.tsx` | 迁移输入表单（主题 / 卖点） | 外观 ✅；`onMigrate` 调用签名 ❌ |
| `components/migration/MigrationPreview.tsx` | 迁移结果完整预览 + 骨架映射（可拖动） | 外观全 ✅ |
| `components/migration/MigrationProgress.tsx` | 流式迁移进度（流式时显示） | 外观 ✅ |
| `components/migration/EditableSlotCard.tsx` | 单个 Slot 编辑 / 重新生成 | 外观 ✅ |

---

## 13. 完整流程一图览

```
用户操作         前端状态                    显示
────────────────────────────────────────────────────────────────
上传/链接        analyzing=true, stage='stage1'   AgentProgress（Stage1步骤）
                stage1_done                       Stage1 预览确认页
点"进入S2"       analysis=null, stage='stage2'     Stage2LoadingView
  ↳ leo跑完     analysis.synthesis_result 有值     └ LeoAgentGrid 展开
  ↳ main跑完    analysis.video_structure 有值       完整工作台（3栏+Tab）
                                                    └ LeoAgentGrid 最底部
填主题点生成      migrating=true                    MigrationProgress（流式）
  ↳ 流结束      migration 有值                     MigrationPreview
    ↳ 展开骨架  details[open]                        SkeletonMap（可拖边界）
```

---

## 14. 自测清单

改前端后必须跑完：

1. 上传视频 → Stage1 步骤逐步变绿
2. Stage1 完 → 停在预览页（显示时长 / 镜头数等）
3. 点"进入 Stage 2" → `Stage2LoadingView` 出现，视频静音循环，左侧 6 Agent 打字
4. Leo 完成 → `LeoAgentGrid` 区域展开，显示归因排名
5. Main 完成 → 工作台出现（时间线 / AgentPanel）
6. 点时间线 → 视频跳转，右栏四张卡片实时更新
7. 左栏填主题 → 点"生成新视频" → 流式字符逐渐出现
8. 迁移完成 → "查看骨架映射关系" 展开 → 拖动右侧格子边界 → 箭头弯折 / 格子消失
9. `npx tsc --noEmit`（在 `frontend/` 目录下）无类型错误

---

> **改之前不确定的，看第 10 节；还不确定的，先问再动。**
