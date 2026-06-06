import type { TaskStatus } from '../../lib/api';

const AGENTS = [
  { key: 'script', name: 'Script', label: '脚本结构' },
  { key: 'rhythm', name: 'Rhythm', label: '节奏分析' },
  { key: 'packaging', name: 'Packaging', label: '视觉包装' },
  { key: 'value', name: 'Value', label: '价值主张' },
  { key: 'energy', name: 'Energy', label: '能量曲线' },
  { key: 'transfer', name: 'Transfer', label: '迁移蓝图' },
];

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

  return (
    <div className="vc-card mb-4 rounded-[2rem] p-5">
      <div className="mb-5 flex items-center justify-between gap-4">
        <div>
          <div className="vc-kicker">Processing</div>
          <div className="mt-1 text-base font-semibold text-slate-950">分析进度</div>
        </div>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
          已用 {mins}分{secs.toString().padStart(2, '0')}秒
        </span>
      </div>

      <div className="mb-4 flex gap-2">
        <div className={`h-1.5 flex-1 rounded-full ${stage1Done ? 'bg-emerald-500' : 'bg-indigo-500 animate-pulse'}`} />
        <div className={`h-1.5 flex-[5] rounded-full ${status.status === 'done' ? 'bg-emerald-500' : stage2Active ? 'bg-indigo-500 animate-pulse' : 'bg-slate-200'}`} />
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2 text-xs">
        <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 ${stage1Done ? 'bg-emerald-50 text-emerald-700' : 'bg-indigo-50 text-indigo-700'}`}>
          {stage1Done ? '✓' : '◐'} Stage 1 视频预处理
        </span>
        <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 ${stage2Active ? 'bg-indigo-50 text-indigo-700' : status.status === 'done' ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-400'}`}>
          {status.status === 'done' ? '✓' : stage2Active ? '◐' : '○'} Stage 2 多 Agent 分析
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-6">
        {AGENTS.map((a) => {
          const st = agentState(a.key);
          return (
            <div
              key={a.key}
              className={`rounded-2xl border p-3 transition-all ${
                st === 'done'
                  ? 'border-emerald-200 bg-emerald-50/70'
                  : st === 'running'
                  ? 'border-indigo-200 bg-indigo-50 shadow-sm ring-4 ring-indigo-100'
                  : 'border-slate-200 bg-white opacity-60'
              }`}
            >
              <div className="mb-1.5 flex items-center justify-between">
                <span className="text-[13px] font-semibold text-slate-900">{a.name}</span>
                {st === 'done' && <span className="text-emerald-600">✓</span>}
                {st === 'running' && <span className="inline-block animate-spin text-indigo-600">◐</span>}
                {st === 'waiting' && <span className="text-slate-300">○</span>}
              </div>
              <div className={`text-[11px] ${st === 'running' ? 'text-indigo-700' : 'text-slate-500'}`}>
                {st === 'done' ? a.label : st === 'running' ? (status.message ?? '分析中...') : '等待中'}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
