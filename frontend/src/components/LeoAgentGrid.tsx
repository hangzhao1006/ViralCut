import { useEffect, useRef, useState } from 'react';
import type { SynthesisResult } from '../types';

const AGENTS = [
  { id: 0, name: '情感心理', emoji: '🧠', ring: '#f59e0b', bg: '#fef3c7' },
  { id: 1, name: '叙事结构', emoji: '📖', ring: '#6366f1', bg: '#eef2ff' },
  { id: 2, name: '社会文化', emoji: '🌐', ring: '#10b981', bg: '#d1fae5' },
  { id: 3, name: '信息认知', emoji: '💡', ring: '#f97316', bg: '#ffedd5' },
  { id: 4, name: '制作形式', emoji: '🎬', ring: '#8b5cf6', bg: '#f5f3ff' },
  { id: 5, name: '行为社交', emoji: '🤝', ring: '#0ea5e9', bg: '#e0f2fe' },
];

const DIM_PALETTE = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#0ea5e9'];

function RingAvatar({
  emoji, name, ringColor, bg, done, claim, claimColor,
}: {
  emoji: string; name: string; ringColor: string; bg: string;
  done: boolean; claim?: string; claimColor?: string;
}) {
  const size = 76;
  const r = 31;
  const circ = 2 * Math.PI * r;

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative" style={{ width: size, height: size }}>
        {/* Static track */}
        <svg className="absolute inset-0" width={size} height={size}>
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e2e8f0" strokeWidth={5} />
        </svg>
        {/* Arc: spinning when loading, full-circle green when done */}
        <svg
          className={`absolute inset-0 ${!done ? 'animate-spin' : ''}`}
          width={size} height={size}
          style={!done ? { animationDuration: '1.6s' } : undefined}
        >
          <circle
            cx={size / 2} cy={size / 2} r={r}
            fill="none"
            stroke={done ? '#10b981' : ringColor}
            strokeWidth={5}
            strokeDasharray={done ? `${circ * 0.96} ${circ * 0.04}` : `${circ * 0.62} ${circ * 0.38}`}
            strokeLinecap="round"
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
            style={{ transition: 'stroke 0.5s' }}
          />
        </svg>
        {/* Emoji bubble */}
        <div className="absolute inset-0 flex items-center justify-center">
          <div
            className="flex h-14 w-14 items-center justify-center rounded-full text-2xl shadow-sm"
            style={{ background: bg }}
          >
            {emoji}
          </div>
        </div>
        {done && (
          <div className="absolute -right-0.5 -top-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500 text-[9px] font-bold text-white">
            ✓
          </div>
        )}
      </div>

      <div className="text-center">
        <div className="text-[11px] font-medium text-slate-700">{name}</div>
        {claim ? (
          <div
            className="mt-1 rounded-lg px-2 py-0.5 text-[9px] font-semibold leading-tight text-white"
            style={{ background: claimColor }}
          >
            {claim}
          </div>
        ) : done ? (
          <div className="mt-1 text-[9px] text-slate-400">独立视角</div>
        ) : (
          <div className="mt-1 animate-pulse text-[9px] text-slate-400">分析中...</div>
        )}
      </div>
    </div>
  );
}

interface Props {
  synthesis: SynthesisResult | null;
  isLoading: boolean;
}

export default function LeoAgentGrid({ synthesis, isLoading }: Props) {
  const done = !isLoading && synthesis != null;
  const dims = synthesis?.ranked_dimensions ?? [];

  // Assign a color to each dimension by rank index
  const dimColor = (name: string) => {
    const idx = dims.findIndex((d) => d.dimension_name === name);
    return DIM_PALETTE[idx % DIM_PALETTE.length];
  };

  // For each agent, find their primary dimension (highest-ranked dim they support)
  function agentClaim(agentId: number): { name: string; color: string } | undefined {
    const dim = dims.find((d) => d.supporting_agent_ids?.includes(agentId));
    if (!dim) return undefined;
    return { name: dim.dimension_name, color: dimColor(dim.dimension_name) };
  }

  // Fake progress counter shown while loading (visual only, no functional meaning)
  const [tick, setTick] = useState(0);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => {
    if (isLoading) {
      tickRef.current = setInterval(() => setTick((t) => t + 1), 800);
    } else {
      if (tickRef.current) clearInterval(tickRef.current);
    }
    return () => { if (tickRef.current) clearInterval(tickRef.current); };
  }, [isLoading]);

  return (
    <div className="border-t border-slate-200/80 bg-white px-5 py-6">
      {/* Header */}
      <div className="mb-5 flex items-center gap-2">
        <div className="h-1.5 w-1.5 rounded-full bg-indigo-400" />
        <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
          爆款归因 · 多视角 Agent 并行分析
        </span>
        {isLoading && (
          <span className="animate-pulse rounded-full bg-blue-100 px-2 py-0.5 text-[10px] text-blue-600">
            并行分析中...
          </span>
        )}
        {done && (
          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] text-emerald-700">
            ✓ 完成
          </span>
        )}
      </div>

      {/* 6 Agent avatars */}
      <div className="mb-6 grid grid-cols-6 gap-4">
        {AGENTS.map((ag) => {
          const claim = agentClaim(ag.id);
          return (
            <RingAvatar
              key={ag.id}
              emoji={ag.emoji}
              name={ag.name}
              ringColor={ag.ring}
              bg={ag.bg}
              done={done}
              claim={claim?.name}
              claimColor={claim?.color}
            />
          );
        })}
      </div>

      {/* Dimension cards (shown after leo completes) */}
      {done && dims.length > 0 && (
        <div className="space-y-2.5">
          <div className="mb-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
            维度聚类排名（Agent 共识度 × 强度）
          </div>
          {dims.map((dim, i) => {
            const color = dimColor(dim.dimension_name);
            const supporters = (dim.supporting_agent_ids ?? [])
              .map((id) => AGENTS[id])
              .filter(Boolean);
            return (
              <div
                key={i}
                className="flex items-start gap-3 rounded-2xl border border-slate-100 bg-slate-50/60 p-3.5 transition hover:border-slate-200"
              >
                {/* Rank badge */}
                <div
                  className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full text-[11px] font-bold text-white"
                  style={{ background: color }}
                >
                  {i + 1}
                </div>

                {/* Content */}
                <div className="min-w-0 flex-1">
                  <div className="mb-1 flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold text-slate-900">{dim.dimension_name}</span>
                    <span className="text-[10px] text-slate-400">
                      强度 {dim.avg_strength_score?.toFixed(1)}/10
                    </span>
                  </div>
                  {/* Strength bar */}
                  <div className="mb-2 h-1 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{ width: `${((dim.avg_strength_score ?? 0) / 10) * 100}%`, background: color }}
                    />
                  </div>
                  <div className="mb-2 text-[11px] leading-relaxed text-slate-600">{dim.viral_mechanism}</div>

                  {/* Supporting agents as chips */}
                  {supporters.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {supporters.map((ag) => (
                        <span
                          key={ag.id}
                          className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium text-white"
                          style={{ background: color + 'cc' }}
                        >
                          {ag.emoji} {ag.name}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Agreement count */}
                <div className="flex-shrink-0 text-center">
                  <div className="text-xl font-bold leading-none" style={{ color }}>
                    {dim.agent_agreement_count}
                  </div>
                  <div className="text-[9px] text-slate-400">agents</div>
                </div>
              </div>
            );
          })}

          {/* Top reason summary */}
          {synthesis?.top_viral_reason && (
            <div className="mt-4 rounded-xl border border-indigo-100 bg-indigo-50/70 px-4 py-3">
              <div className="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-indigo-400">
                综合结论
              </div>
              <div className="text-sm leading-relaxed text-indigo-950">{synthesis.top_viral_reason}</div>
            </div>
          )}
        </div>
      )}

      {/* Loading placeholder */}
      {isLoading && (
        <div className="rounded-2xl border border-dashed border-blue-200 bg-blue-50/40 py-8 text-center">
          <div className="animate-pulse text-sm text-blue-500">
            6 个视角 Agent 并行分析中，完成后呈现维度聚类...
          </div>
        </div>
      )}
    </div>
  );
}
