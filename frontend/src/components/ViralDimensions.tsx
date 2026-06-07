import type { SynthesisResult } from '../types';

interface Props {
  synthesis: SynthesisResult;
}

export default function ViralDimensions({ synthesis }: Props) {
  const dims = synthesis.ranked_dimensions ?? [];
  const maxScore = 10;

  return (
    <div className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm">
      {/* Top reason */}
      <div className="mb-5 rounded-2xl border border-indigo-100 bg-indigo-50/70 px-4 py-3">
        <div className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-indigo-400">
          <span className="h-1.5 w-1.5 rounded-full bg-indigo-400" /> 核心爆款原因
        </div>
        <div className="text-sm leading-relaxed text-indigo-950">{synthesis.top_viral_reason}</div>
      </div>

      {/* Ranked dimensions */}
      <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
        爆款维度排名（多视角 Agent 聚类）
      </div>
      <div className="space-y-2.5">
        {dims.map((d, i) => (
          <div key={i} className="rounded-2xl border border-slate-200/80 bg-white p-3.5 shadow-sm transition hover:border-indigo-200 hover:shadow-md">
            <div className="mb-2 flex items-start justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="inline-flex h-6 min-w-6 items-center justify-center rounded-full bg-slate-900 px-2 text-[11px] font-semibold text-white">
                  {i + 1}
                </span>
                <span className="text-sm font-semibold text-slate-900">{d.dimension_name}</span>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700">
                  {d.agent_agreement_count} 个视角认同
                </span>
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">
                  强度 {d.avg_strength_score?.toFixed(1)}
                </span>
              </div>
            </div>

            {/* Strength bar */}
            <div className="mb-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
              <div className="h-full rounded-full bg-indigo-500" style={{ width: `${(d.avg_strength_score / maxScore) * 100}%` }} />
            </div>

            <div className="text-xs leading-relaxed text-slate-600">{d.viral_mechanism}</div>

            {/* Evidence */}
            {d.representative_evidence?.length > 0 && (
              <details className="mt-2 group">
                <summary className="flex cursor-pointer items-center gap-1.5 text-[11px] font-medium text-slate-400 transition hover:text-slate-600">
                  <span className="transition group-open:rotate-90">▸</span> {d.representative_evidence.length} 条证据
                </summary>
                <div className="mt-2 space-y-1.5">
                  {d.representative_evidence.map((ev, j) => (
                    <div key={j} className="rounded-xl bg-slate-50 px-2.5 py-2 text-[11px] text-slate-600">
                      <span className="mr-1.5 rounded bg-white px-1.5 py-0.5 text-[10px] font-medium text-slate-500 ring-1 ring-slate-200">
                        {ev.source}
                      </span>
                      {ev.quote && <span className="text-slate-700">"{ev.quote}" </span>}
                      {ev.reasoning && <span className="text-slate-500">{ev.reasoning}</span>}
                    </div>
                  ))}
                </div>
              </details>
            )}
          </div>
        ))}
      </div>

      {synthesis.analysis_note && (
        <div className="mt-4 rounded-xl bg-slate-50 px-3 py-2.5 text-[11px] leading-relaxed text-slate-500">
          {synthesis.analysis_note}
        </div>
      )}
    </div>
  );
}