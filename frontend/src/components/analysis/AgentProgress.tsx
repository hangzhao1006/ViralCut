import type { TaskStatus } from '../../lib/api';

const AGENTS = [
  { key: 'script',    label: 'Script',    desc: '脚本结构' },
  { key: 'rhythm',    label: 'Rhythm',    desc: '节奏分析' },
  { key: 'packaging', label: 'Packaging', desc: '视觉包装' },
  { key: 'value',     label: 'Value',     desc: '价值主张' },
  { key: 'energy',    label: 'Energy',    desc: '能量曲线' },
  { key: 'transfer',  label: 'Transfer',  desc: '迁移蓝图' },
];

const STAGE1_STEPS = [
  { key: 'scene',    label: '分镜检测', desc: 'Scene detect' },
  { key: 'keyframe', label: '关键帧',   desc: 'Keyframes' },
  { key: 'ocr',      label: '画面文字', desc: 'OCR' },
  { key: 'asr',      label: '语音转写', desc: 'ASR' },
  { key: 'beats',    label: '音乐节拍', desc: 'Beats / BPM' },
  { key: 'basic',    label: '基础分析', desc: 'Statistics' },
];

const LEO_LENSES = [
  { key: 'emotion',    label: '情感 Agent', char: '🌀' },
  { key: 'narrative',  label: '叙事 Agent', char: '🎯' },
  { key: 'social',     label: '社会 Agent', char: '🌊' },
  { key: 'cognition',  label: '信息 Agent', char: '⚡' },
  { key: 'form',       label: '制作 Agent', char: '🔷' },
  { key: 'behavior',   label: '行为 Agent', char: '🫧' },
];

const STAGE1_KW: Record<string, RegExp[]> = {
  scene:    [/scene/i, /pyscenedetect/i, /镜头/, /shot/i, /分镜/],
  keyframe: [/keyframe/i, /关键帧/, /extract.?frame/i, /代表帧/],
  ocr:      [/\bocr\b/i, /rapidocr/i, /easyocr/i, /画面文字/, /文字识别/],
  asr:      [/whisper/i, /\basr\b/i, /transcri/i, /语音/, /字幕/],
  beats:    [/\bbeat/i, /\bbpm\b/i, /librosa/i, /节拍/, /tempo/i, /卡点/],
  basic:    [/basic_analysis/i, /基础分析/, /镜头统计/],
};

type StepProg = { state: 'waiting' | 'active' | 'done'; pct?: number | null };

function parseStage1(logs: string[] | undefined): Record<string, StepProg> {
  const out: Record<string, StepProg> = {};
  for (const s of STAGE1_STEPS) out[s.key] = { state: 'waiting' };
  if (!logs?.length) return out;

  const seen: string[] = [];
  let lastKey: string | null = null;
  let lastPct: number | undefined;

  for (const line of logs) {
    for (const key of Object.keys(STAGE1_KW)) {
      if (STAGE1_KW[key].some((p) => p.test(line))) {
        if (!seen.includes(key)) seen.push(key);
        lastKey = key;
        const m = line.match(/(\d+)\s*\/\s*(\d+)/);
        lastPct = m ? Math.round((+m[1] / Math.max(1, +m[2])) * 100) : undefined;
      }
    }
  }
  for (const k of seen) out[k] = { state: 'done', pct: 100 };
  if (lastKey) out[lastKey] = { state: 'active', pct: lastPct };
  return out;
}

const MONO: React.CSSProperties = {
  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
};

interface Props { status: TaskStatus; elapsed: number; }

export default function AgentProgress({ status, elapsed }: Props) {
  const stage     = status.stage ?? 'stage1';
  const current   = status.current_step ?? '';
  const completed = (status as Record<string, unknown>).completed_agents as string[] ?? [];
  const phase     = (status as Record<string, unknown>).current_phase as string | undefined;
  const isBoth    = status.stage2_variant === 'both';

  const stage1Done  = stage === 'stage2' || status.status === 'done';
  const stage2Active = stage === 'stage2' && status.status === 'processing';

  function agentState(key: string): 'done' | 'running' | 'waiting' {
    if (status.status === 'done' || completed.includes(key)) return 'done';
    if (current === key) return 'running';
    return 'waiting';
  }

  const mins = Math.floor(elapsed / 60);
  const secs = elapsed % 60;

  const s1: Record<string, StepProg> =
    status.stage1_steps && Object.keys(status.stage1_steps).length > 0
      ? (status.stage1_steps as Record<string, StepProg>)
      : parseStage1(status.log_tail);

  // ── Failure state ──────────────────────────────────────────────────
  if (status.status === 'failed') {
    return (
      <div style={{
        border: '1px solid #ffd0cc',
        borderRadius: 16,
        padding: '16px 20px',
        background: '#fff8f7',
        marginBottom: 16,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: '#ff3b30' }}>Analysis failed</span>
          <span style={{ ...MONO, fontSize: 10, color: '#aeaeb2' }}>
            {mins}:{secs.toString().padStart(2, '0')}
          </span>
        </div>
        <div style={{ fontSize: 13, color: '#6e6e73', marginBottom: 10 }}>
          {status.message ?? 'Unknown error'}
        </div>
        {status.log_tail?.length ? (
          <div style={{
            borderRadius: 10, background: '#0a0a0a',
            padding: '10px 12px', fontFamily: 'ui-monospace, Menlo, monospace',
            fontSize: 10, lineHeight: 1.7, color: '#ff6b6b',
            maxHeight: 120, overflowY: 'auto',
          }}>
            {status.log_tail.map((l, i) => <div key={i}>› {l}</div>)}
          </div>
        ) : null}
      </div>
    );
  }

  // ── Stage labels ───────────────────────────────────────────────────
  const leoPhase  = phase === 'leo'  || (!isBoth && status.stage2_variant === 'leo');
  const mainPhase = phase === 'main' || (!isBoth && status.stage2_variant !== 'leo');
  const leoDone   = isBoth && phase === 'main';

  return (
    <div style={{
      border: '1px solid #e8e8e8', borderRadius: 16,
      padding: '18px 20px', background: '#fff',
      marginBottom: 16,
    }}>
      {/* Timer + stage breadcrumb */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {/* Stage 1 */}
          <span style={{ fontSize: 11, fontWeight: 500, color: stage1Done ? '#34c759' : '#6366f1' }}>
            {stage1Done ? '✓' : '◐'} Stage 1
          </span>
          <span style={{ color: '#e0e0e0', fontSize: 12 }}>›</span>
          {/* Stage 2 labels */}
          {isBoth ? (
            <>
              <span style={{ fontSize: 11, fontWeight: 500, color: leoDone || status.status === 'done' ? '#34c759' : stage2Active && leoPhase ? '#6366f1' : '#aeaeb2' }}>
                {leoDone || status.status === 'done' ? '✓' : leoPhase ? '◐' : '○'} 爆款归因
              </span>
              <span style={{ color: '#e0e0e0', fontSize: 12 }}>›</span>
              <span style={{ fontSize: 11, fontWeight: 500, color: status.status === 'done' ? '#34c759' : mainPhase && stage2Active ? '#6366f1' : '#aeaeb2' }}>
                {status.status === 'done' ? '✓' : mainPhase && stage2Active ? '◐' : '○'} 结构分析
              </span>
            </>
          ) : (
            <span style={{ fontSize: 11, fontWeight: 500, color: status.status === 'done' ? '#34c759' : stage2Active ? '#6366f1' : '#aeaeb2' }}>
              {status.status === 'done' ? '✓' : stage2Active ? '◐' : '○'} Stage 2
            </span>
          )}
        </div>
        <span style={{ ...MONO, fontSize: 10, color: '#aeaeb2' }}>
          {mins}:{secs.toString().padStart(2, '0')}
        </span>
      </div>

      {/* Thin progress track */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 16, height: 3 }}>
        <div style={{ flex: 1, borderRadius: 2, background: stage1Done ? '#34c759' : '#6366f1', opacity: stage1Done ? 1 : 0.6 }} />
        <div style={{ flex: isBoth ? 2 : 5, borderRadius: 2, background: status.status === 'done' ? '#34c759' : stage2Active ? '#e8e8e8' : '#eeeeee' }}>
          {stage2Active && (
            <div style={{ height: '100%', width: leoDone ? '50%' : '15%', borderRadius: 2, background: '#6366f1', transition: 'width 1s' }} />
          )}
        </div>
      </div>

      {/* ── Stage 1 sub-steps ── */}
      {!stage1Done && (
        <div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 12 }}>
            {STAGE1_STEPS.map((s) => {
              const p = s1[s.key];
              const isDone   = p.state === 'done';
              const isActive = p.state === 'active';
              return (
                <div key={s.key} style={{
                  border: `1px solid ${isDone ? '#e8e8e8' : isActive ? '#6366f1' : '#eeeeee'}`,
                  borderRadius: 10,
                  padding: '10px 12px',
                  background: '#fff',
                  opacity: p.state === 'waiting' ? 0.45 : 1,
                  transition: 'border-color 0.3s, opacity 0.3s',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontSize: 12, fontWeight: 500, color: '#1d1d1f' }}>{s.label}</span>
                    {isDone
                      ? <span style={{ fontSize: 12, color: '#34c759' }}>✓</span>
                      : isActive
                      ? <span style={{ fontSize: 12, color: '#6366f1' }}>◐</span>
                      : <span style={{ fontSize: 12, color: '#d0d0d0' }}>○</span>
                    }
                  </div>
                  <div style={{ ...MONO, fontSize: 10, color: isActive ? '#6366f1' : '#aeaeb2' }}>
                    {isDone ? 'Done' : isActive ? (p.pct != null ? `${p.pct}%` : s.desc) : s.desc}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Log tail */}
          <div style={{
            borderRadius: 10, background: '#0a0a0a',
            padding: '10px 14px',
            fontFamily: 'ui-monospace, Menlo, monospace',
            fontSize: 10, lineHeight: 1.75, color: '#34c759',
            maxHeight: 96, overflowY: 'auto',
          }}>
            {status.log_tail?.length
              ? status.log_tail.map((l, i) => (
                  <div key={i} style={{ color: i === status.log_tail!.length - 1 ? '#34c759' : 'rgba(52,199,89,0.5)' }}>
                    <span style={{ color: '#444' }}>›</span> {l}
                  </div>
                ))
              : <div style={{ color: 'rgba(52,199,89,0.5)' }}>› {status.message ?? 'Starting...'}</div>
            }
          </div>
        </div>
      )}

      {/* ── Leo lenses (parallel) ── */}
      {stage1Done && leoPhase && (
        <div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 8 }}>
            {LEO_LENSES.map((l) => {
              const isDone = status.status === 'done' || leoDone;
              return (
                <div key={l.key} style={{
                  border: `1px solid ${isDone ? '#e8e8e8' : '#6366f1'}`,
                  borderRadius: 10,
                  padding: '10px 8px',
                  background: '#fff',
                  display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6,
                  transition: 'border-color 0.3s',
                }}>
                  <div style={{
                    width: 32, height: 32, borderRadius: '50%',
                    background: '#f5f5f7', border: '1px solid #e8e8e8',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 16,
                    opacity: isDone ? 1 : 0.4,
                    transition: 'opacity 0.4s',
                  }}>{l.char}</div>
                  <span style={{ fontSize: 10, color: '#6e6e73', textAlign: 'center' }}>{l.label}</span>
                  <span style={{ fontSize: 10, color: isDone ? '#34c759' : '#6366f1' }}>
                    {isDone ? '✓' : '◐'}
                  </span>
                </div>
              );
            })}
          </div>
          <div style={{ marginTop: 10, fontFamily: 'ui-monospace, monospace', fontSize: 10, color: '#aeaeb2' }}>
            6 lenses running in parallel — synthesizing when complete
          </div>
        </div>
      )}

      {/* ── Main structure agents (sequential) ── */}
      {stage1Done && !leoPhase && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
          {AGENTS.map((a) => {
            const st = agentState(a.key);
            return (
              <div key={a.key} style={{
                border: `1px solid ${st === 'running' ? '#6366f1' : '#eeeeee'}`,
                borderRadius: 10,
                padding: '10px 12px',
                background: '#fff',
                opacity: st === 'waiting' ? 0.45 : 1,
                transition: 'border-color 0.3s, opacity 0.3s',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span style={{ fontFamily: 'ui-monospace, monospace', fontSize: 12, fontWeight: 500, color: '#1d1d1f' }}>
                    {a.label}
                  </span>
                  {st === 'done'
                    ? <span style={{ fontSize: 12, color: '#34c759' }}>✓</span>
                    : st === 'running'
                    ? <span style={{ fontSize: 12, color: '#6366f1' }}>◐</span>
                    : <span style={{ fontSize: 12, color: '#d8d8d8' }}>○</span>
                  }
                </div>
                <div style={{ fontFamily: 'ui-monospace, monospace', fontSize: 10, color: st === 'running' ? '#6366f1' : '#aeaeb2' }}>
                  {st === 'done' ? 'Done' : st === 'running' ? (status.message ?? 'Running…') : a.desc}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
