import type { TaskStatus } from '../../lib/api';

const AGENTS = [
  { key: 'script', name: 'Script', label: '脚本结构' },
  { key: 'rhythm', name: 'Rhythm', label: '节奏分析' },
  { key: 'packaging', name: 'Packaging', label: '视觉包装' },
  { key: 'value', name: 'Value', label: '价值主张' },
  { key: 'energy', name: 'Energy', label: '能量曲线' },
  { key: 'transfer', name: 'Transfer', label: '迁移蓝图' },
];

const STAGE1_STEPS = [
  { key: 'scene', name: '分镜检测', desc: '切分镜头' },
  { key: 'keyframe', name: '关键帧', desc: '抽取代表帧' },
  { key: 'ocr', name: '画面文字', desc: 'OCR识别' },
  { key: 'asr', name: '语音转写', desc: 'ASR字幕' },
  { key: 'beats', name: '音乐节拍', desc: 'BPM/卡点' },
  { key: 'basic', name: '基础分析', desc: '镜头统计' },
];

// Leo variant runs these lenses in PARALLEL (no sequential per-agent tracking)
const LEO_LENSES = [
  { key: 'emotion', name: '情感心理' },
  { key: 'narrative', name: '叙事结构' },
  { key: 'social', name: '社会文化' },
  { key: 'cognition', name: '信息认知' },
  { key: 'form', name: '制作形式' },
  { key: 'behavior', name: '行为社交' },
];

// Match Stage 1 step activity from captured pipeline logs (broad keywords for both pipelines)
const STAGE1_KEYWORDS: Record<string, RegExp[]> = {
  scene: [/scene/i, /pyscenedetect/i, /镜头/, /shot/i, /分镜/],
  keyframe: [/keyframe/i, /关键帧/, /extract.?frame/i, /代表帧/],
  ocr: [/\bocr\b/i, /rapidocr/i, /easyocr/i, /画面文字/, /文字识别/],
  asr: [/whisper/i, /\basr\b/i, /transcri/i, /语音/, /字幕/],
  beats: [/\bbeat/i, /\bbpm\b/i, /librosa/i, /节拍/, /tempo/i, /卡点/],
  basic: [/basic_analysis/i, /基础分析/, /镜头统计/],
};

type StepProg = { state: 'waiting' | 'active' | 'done'; pct?: number | null };

function parseStage1(logs: string[] | undefined): Record<string, StepProg> {
  const out: Record<string, StepProg> = {};
  for (const s of STAGE1_STEPS) out[s.key] = { state: 'waiting' };
  if (!logs || logs.length === 0) return out;

  const order: string[] = [];
  let lastKey: string | null = null;
  let lastPct: number | undefined;

  for (const line of logs) {
    for (const key of Object.keys(STAGE1_KEYWORDS)) {
      if (STAGE1_KEYWORDS[key].some((p) => p.test(line))) {
        if (!order.includes(key)) order.push(key);
        lastKey = key;
        const m = line.match(/(\d+)\s*\/\s*(\d+)/);
        lastPct = m ? Math.round((+m[1] / Math.max(1, +m[2])) * 100) : undefined;
      }
    }
  }

  for (const k of order) out[k] = { state: 'done', pct: 100 };
  if (lastKey) out[lastKey] = { state: 'active', pct: lastPct };
  return out;
}

interface Props {
  status: TaskStatus;
  elapsed: number;
}

export default function AgentProgress({ status, elapsed }: Props) {
  const stage = status.stage ?? 'stage1';
  const current = status.current_step ?? '';
  const completed: string[] = (status as { completed_agents?: string[] }).completed_agents ?? [];

  const stage1Done = stage === 'stage2' || status.status === 'done';
  const stage2Active = stage === 'stage2' && status.status === 'processing';

  function agentState(key: string): 'done' | 'running' | 'waiting' {
    if (status.status === 'done' || completed.includes(key)) return 'done';
    if (current === key) return 'running';
    return 'waiting';
  }

  const mins = Math.floor(elapsed / 60);
  const secs = elapsed % 60;

  // Prefer backend-accumulated step progress (monotonic, no flicker); fall back to log parsing.
  const s1: Record<string, StepProg> =
    status.stage1_steps && Object.keys(status.stage1_steps).length > 0
      ? (status.stage1_steps as Record<string, StepProg>)
      : parseStage1(status.log_tail);

  const failed = status.status === 'failed';

  if (failed) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-2xl p-5 mb-4">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-red-500 text-base">✕</span>
          <span className="text-sm font-semibold text-red-800">分析失败</span>
          <span className="text-xs text-red-400">已用 {mins}分{secs.toString().padStart(2, '0')}秒</span>
        </div>
        <div className="text-[13px] text-red-700 mb-3">{status.message ?? '未知错误'}</div>
        {status.log_tail && status.log_tail.length > 0 && (
          <div className="rounded-xl bg-slate-900 px-3 py-2.5 font-mono text-[10px] leading-relaxed text-red-300 max-h-32 overflow-y-auto">
            {status.log_tail.map((line, i) => (
              <div key={i}><span className="text-slate-500">›</span> {line}</div>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="bg-gray-50 rounded-2xl p-5 mb-4">
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm font-medium">分析进度</span>
        <span className="text-xs text-gray-500">
          已用 {mins}分{secs.toString().padStart(2, '0')}秒
        </span>
      </div>

      {/* Stage progress bar */}
      <div className="flex gap-2 mb-4">
        <div className={`flex-1 h-1 rounded-full ${stage1Done ? 'bg-emerald-600' : 'bg-emerald-400 animate-pulse'}`} />
        <div className={`flex-[5] h-1 rounded-full ${status.status === 'done' ? 'bg-emerald-600' : stage2Active ? 'bg-emerald-400' : 'bg-gray-200'}`} />
      </div>

      {/* Stage labels */}
      <div className="flex items-center gap-2 mb-4 text-xs">
        <span className={`flex items-center gap-1.5 ${stage1Done ? 'text-emerald-700' : 'text-blue-600'}`}>
          {stage1Done ? '✓' : '◐'} Stage 1 视频预处理
        </span>
        <span className="text-gray-300">·</span>
        <span className={`flex items-center gap-1.5 ${stage2Active ? 'text-blue-600' : status.status === 'done' ? 'text-emerald-700' : 'text-gray-400'}`}>
          {status.status === 'done' ? '✓' : stage2Active ? '◐' : '○'} Stage 2 多Agent分析
        </span>
      </div>

      {/* Stage 1 sub-steps OR Stage 2 agent cards */}
      {!stage1Done ? (
        <div>
          <div className="grid grid-cols-3 gap-2">
            {STAGE1_STEPS.map((s) => {
              const p = s1[s.key];
              const isDone = p.state === 'done';
              const isActive = p.state === 'active';
              // fill width: real % if available, else 40% indeterminate pulse while active, 100% done, 0 waiting
              const fillPct = isDone ? 100 : isActive ? (p.pct ?? 40) : 0;
              return (
                <div key={s.key}
                  className={`relative overflow-hidden rounded-xl p-3 border transition-all ${
                    isDone ? 'border-emerald-200 bg-white' : isActive ? 'border-blue-300 bg-white' : 'border-gray-200 bg-white opacity-50'
                  }`}>
                  {/* charging fill */}
                  <div
                    className={`absolute inset-y-0 left-0 transition-all duration-700 ${
                      isDone ? 'bg-emerald-100/70' : 'bg-blue-100/70'
                    } ${isActive && p.pct == null ? 'animate-pulse' : ''}`}
                    style={{ width: `${fillPct}%` }}
                  />
                  <div className="relative">
                    <div className="flex items-center justify-between mb-1.5">
                      <span className={`text-[13px] font-medium ${isDone ? 'text-emerald-900' : isActive ? 'text-blue-900' : 'text-gray-500'}`}>{s.name}</span>
                      {isDone ? <span className="text-emerald-600 text-base">✓</span>
                        : isActive ? <span className="text-blue-600 text-base animate-spin inline-block">◐</span>
                        : <span className="text-gray-300 text-base">○</span>}
                    </div>
                    <div className={`text-[11px] ${isActive ? 'text-blue-600' : 'text-gray-500'}`}>
                      {isDone ? '已完成' : isActive ? (p.pct != null ? `${p.pct}%` : s.desc) : s.desc}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
          <div className="mt-3 rounded-xl bg-slate-900 px-3 py-2.5 font-mono text-[10px] leading-relaxed text-emerald-300 max-h-28 overflow-y-auto">
            {(status.log_tail && status.log_tail.length > 0)
              ? status.log_tail.map((line, i) => (
                  <div key={i} className={i === (status.log_tail!.length - 1) ? 'text-emerald-200' : 'text-emerald-400/70'}>
                    <span className="text-slate-500">›</span> {line}
                  </div>
                ))
              : <div className="text-emerald-400/70">› {status.message ?? '正在启动...'}</div>}
          </div>
        </div>
      ) : status.stage2_variant === 'leo' ? (
        <div>
          <div className="grid grid-cols-3 gap-2">
            {LEO_LENSES.map((l) => {
              const isDone = status.status === 'done';
              return (
                <div key={l.key} className={`rounded-xl p-3 border transition-all ${isDone ? 'bg-white border-gray-200' : 'bg-blue-50/60 border-blue-200'}`}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[13px] font-medium">{l.name}</span>
                    {isDone ? <span className="text-emerald-600 text-base">✓</span> : <span className="text-blue-500 text-base animate-pulse">◐</span>}
                  </div>
                  <div className="text-[11px] text-blue-600">{isDone ? '已完成' : '并行分析中'}</div>
                </div>
              );
            })}
          </div>
          <div className="mt-2 text-[11px] text-gray-500">爆款归因：多个视角Agent并行分析后聚类排名</div>
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          {AGENTS.map((a) => {
            const st = agentState(a.key);
            return (
              <div
                key={a.key}
                className={`rounded-xl p-3 border transition-all ${
                  st === 'done'
                    ? 'bg-white border-gray-200'
                    : st === 'running'
                    ? 'bg-blue-50 border-blue-300'
                    : 'bg-white border-gray-200 opacity-50'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[13px] font-medium">{a.name}</span>
                  {st === 'done' && <span className="text-emerald-600 text-base">✓</span>}
                  {st === 'running' && <span className="text-blue-600 text-base animate-spin inline-block">◐</span>}
                  {st === 'waiting' && <span className="text-gray-300 text-base">○</span>}
                </div>
                <div className={`text-[11px] ${st === 'running' ? 'text-blue-600' : 'text-gray-500'}`}>
                  {st === 'done' ? '已完成' : st === 'running' ? (status.message ?? '分析中...') : '等待中'}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}