import type { TransferBlueprint, MigratedSlot } from '../../types';
import { STRATEGY_LABELS } from '../../lib/colors';

interface Props {
  blueprint: TransferBlueprint;
  parsedSlots: MigratedSlot[];
  done: boolean;
}

const STATUS_STYLE: Record<string, { bg: string; text: string; label: string }> = {
  filled: { bg: '#EAF3DE', text: '#27500A', label: '已填充' },
  gap: { bg: '#FAEEDA', text: '#633806', label: '缺口' },
  restructured: { bg: '#E6F1FB', text: '#0C447C', label: '重排' },
  aigc_needed: { bg: '#FBEAF0', text: '#72243E', label: 'AIGC' },
};

export default function MigrationProgress({ blueprint, parsedSlots, done }: Props) {
  const sourceSlots = blueprint.structure_template ?? [];
  const total = sourceSlots.length || 1;
  const completedCount = parsedSlots.length;
  const progressPct = Math.min(100, (completedCount / total) * 100);
  const totalDur = sourceSlots.reduce((s, x) => s + (x.duration_seconds || 1), 0) || 1;

  return (
    <div className="rounded-[1.75rem] border border-slate-200/80 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-sm font-semibold text-slate-950">迁移生成中</span>
        {!done && <span className="inline-block animate-spin text-slate-950">◐</span>}
      </div>
      <div className="text-xs text-slate-500 mb-3">
        正在沿爆款结构逐段映射到新视频 · {completedCount}/{total}
      </div>

      {/* Progress bar */}
      <div className="h-1.5 bg-slate-100 rounded-full mb-4 overflow-hidden">
        <div className="h-full bg-slate-950 rounded-full transition-all duration-500" style={{ width: `${progressPct}%` }} />
      </div>

      {/* Structure timeline: source skeleton on top, new video filling below */}
      <div className="space-y-1.5">
        {/* Source skeleton */}
        <div className="flex items-center">
          <span className="w-16 text-[10px] text-slate-400 shrink-0">爆款骨架</span>
          <div className="flex-1 flex gap-0.5 h-7">
            {sourceSlots.map((s, idx) => {
              const w = ((s.duration_seconds || 1) / totalDur) * 100;
              const reached = idx < completedCount;
              const current = idx === completedCount && !done;
              return (
                <div key={s.slot_id ?? idx}
                  className={`rounded flex items-center justify-center text-[9px] overflow-hidden whitespace-nowrap transition-all ${current ? 'animate-pulse' : ''}`}
                  style={{
                    width: `${w}%`,
                    background: reached ? '#CECBF6' : current ? '#AFA9EC' : '#EEEDFE',
                    color: '#3C3489',
                    opacity: reached || current ? 1 : 0.5,
                  }}>
                  {s.slot_type?.slice(0, 6)}
                </div>
              );
            })}
          </div>
        </div>

        {/* New video filling in */}
        <div className="flex items-center">
          <span className="w-16 text-[10px] text-slate-400 shrink-0">新视频</span>
          <div className="flex-1 flex gap-0.5 h-7">
            {sourceSlots.map((s, idx) => {
              const w = ((s.duration_seconds || 1) / totalDur) * 100;
              const m = parsedSlots[idx];
              if (!m) {
                return <div key={idx} className="rounded bg-slate-50 border border-dashed border-slate-200" style={{ width: `${w}%` }} />;
              }
              const st = STATUS_STYLE[m.status] ?? STATUS_STYLE.filled;
              return (
                <div key={idx}
                  className="rounded flex items-center justify-center text-[9px] overflow-hidden whitespace-nowrap transition-all"
                  style={{ width: `${w}%`, background: st.bg, color: st.text }}>
                  {st.label}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Latest mapped slot detail (the "current" reveal) */}
      {parsedSlots.length > 0 && (
        <div className="mt-4 px-3 py-2.5 rounded-2xl border border-slate-200/70 bg-slate-50/80">
          {(() => {
            const latest = parsedSlots[parsedSlots.length - 1];
            const st = STATUS_STYLE[latest.status] ?? STATUS_STYLE.filled;
            return (
              <div className="text-xs">
                <div className="flex items-center gap-2 mb-1">
                  <span className="px-1.5 py-0.5 rounded text-[10px]" style={{ background: st.bg, color: st.text }}>{st.label}</span>
                  <span className="font-medium">{latest.slot_type}</span>
                  <span className="text-slate-400">{latest.duration_seconds}s</span>
                </div>
                {latest.migrated_content?.text && (
                  <div className="text-slate-600">{latest.migrated_content.text}</div>
                )}
                {latest.gap && (
                  <div className="text-[11px] text-amber-700 mt-1">
                    缺口: {latest.gap.missing}
                    {latest.fill_strategy && (
                      <span className="text-slate-500"> → {STRATEGY_LABELS[latest.fill_strategy.type] ?? latest.fill_strategy.type}</span>
                    )}
                  </div>
                )}
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
}
