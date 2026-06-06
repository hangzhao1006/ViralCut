import { useState, useRef } from 'react';
import type { VideoStructure } from '../../types';
import { FUNCTION_COLORS, PACE_COLORS } from '../../lib/colors';
import { formatTime } from '../../lib/timeline';

interface Props {
  structure: VideoStructure;
  evidence: Record<string, unknown> | null;
  currentTime: number;
  onSeek: (t: number) => void;
}

const FUNCTION_LABELS: Record<string, string> = {
  hook: 'hook', introduction: '引入', instruction: '指令',
  demonstration: '示范', comparison: '对比', transition: '过渡',
  climax: '高潮', resolution: '收尾', cta: 'CTA',
};

const FUNCTION_TEXT_COLORS: Record<string, string> = {
  hook: '#fff', introduction: '#26215C', instruction: '#26215C',
  demonstration: '#04342C', comparison: '#fff', transition: '#fff',
  climax: '#fff', resolution: '#fff', cta: '#412402',
};

export default function MultiTrackTimeline({ structure, evidence, currentTime, onSeek }: Props) {
  const duration = structure.duration || 1;
  const segments = structure.script_structure?.segments ?? [];
  const rhythms = structure.rhythm_structure?.segment_rhythm ?? [];
  const energyCurve = structure.energy_curve?.energy_curve ?? [];
  const beats: number[] =
    ((evidence?.beats as Record<string, unknown>)?.beat_timestamps as number[]) ?? [];
  const ocrResults = (evidence?.ocr_results as { timestamp: number; display_text?: string }[]) ?? [];
  const ocrMarks: number[] = ocrResults
    .filter((o) => (o.display_text ?? '').trim().length > 0)
    .map((o) => o.timestamp);

  const [hover, setHover] = useState<string | null>(null);
  const trackRef = useRef<HTMLDivElement>(null);

  function handleTrackClick(e: React.MouseEvent) {
    if (!trackRef.current) return;
    const rect = trackRef.current.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    onSeek(Math.max(0, Math.min(duration, pct * duration)));
  }

  const ENERGY_VAL: Record<string, number> = {
    low: 0.25, 'low-medium': 0.4, medium: 0.6, 'medium-high': 0.78, high: 0.9, peak: 1.0,
  };
  const energyPath = buildAreaPath(energyCurve, duration, ENERGY_VAL);

  const hoverSeg = hover ? segments.find((s) => s.segment_id === hover) : null;
  const hoverRhythm = hover ? rhythms.find((r) => r.segment_id === hover) : null;

  const rulerMarks = [0, 0.2, 0.4, 0.6, 0.8, 1.0];

  return (
    <div className="relative rounded-[1.75rem] border border-slate-200/80 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-semibold text-slate-950">分析时间线</span>
        <span className="text-xs font-medium text-slate-400">{formatTime(currentTime)} / {formatTime(duration)}</span>
      </div>

      <div className="flex mb-0.5">
        <div className="w-16" />
        <div className="flex-1 flex justify-between border-b border-slate-200 pb-1 text-[10px] text-slate-400">
          {rulerMarks.map((m) => <span key={m}>{Math.round(m * duration)}s</span>)}
        </div>
      </div>

      <div
        className="absolute w-0.5 bg-rose-500 z-10 pointer-events-none"
        style={{ top: 54, bottom: 62, left: `calc(4rem + (100% - 4rem) * ${(currentTime / duration).toFixed(4)})` }}
      >
        <div className="absolute -top-1.5 -left-[5px] w-3 h-3 rounded-full bg-rose-500 border-2 border-white" />
      </div>

      <div ref={trackRef} onClick={handleTrackClick} className="cursor-pointer">
        <Track label="脚本">
          {segments.map((s) => {
            const w = ((s.end_time - s.start_time) / duration) * 100;
            const isCurrent = currentTime >= s.start_time && currentTime < s.end_time;
            return (
              <div
                key={s.segment_id}
                onMouseEnter={() => setHover(s.segment_id)}
                onMouseLeave={() => setHover(null)}
                onClick={(e) => { e.stopPropagation(); onSeek(s.start_time); }}
                className="h-[30px] rounded-lg flex items-center justify-center text-[9px] font-semibold overflow-hidden whitespace-nowrap transition-all hover:brightness-105"
                style={{
                  width: `${w}%`,
                  background: FUNCTION_COLORS[s.function] ?? '#888',
                  color: FUNCTION_TEXT_COLORS[s.function] ?? '#fff',
                  boxShadow: isCurrent ? `0 0 0 2px ${FUNCTION_COLORS[s.function]}55` : 'none',
                }}
              >
                {FUNCTION_LABELS[s.function] ?? s.function}
              </div>
            );
          })}
        </Track>

        <Track label="节奏">
          {rhythms.map((r) => {
            const w = ((r.time_range[1] - r.time_range[0]) / duration) * 100;
            const maxSps = Math.max(...rhythms.map((x) => x.shots_per_second ?? 0), 0.5);
            const h = Math.max(20, ((r.shots_per_second ?? 0) / maxSps) * 100);
            return (
              <div
                key={r.segment_id}
                onMouseEnter={() => setHover(r.segment_id)}
                onMouseLeave={() => setHover(null)}
                className="h-[24px] flex items-end"
                style={{ width: `${w}%` }}
              >
                <div className="w-full rounded-md" style={{ height: `${h}%`, background: PACE_COLORS[r.pace] ?? '#888' }} />
              </div>
            );
          })}
        </Track>

        <div className="flex items-end mb-1.5">
          <span className="w-16 text-[10px] text-gray-500">能量</span>
          <div className="flex-1 h-11 relative">
            <svg width="100%" height="44" viewBox="0 0 100 44" preserveAspectRatio="none" className="block">
              <path d={`${energyPath} L100,44 L0,44 Z`} fill="#EF9F2733" />
              <path d={energyPath} fill="none" stroke="#EF9F27" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
            </svg>
          </div>
        </div>

        <div className="flex items-center mb-1.5">
          <span className="w-16 text-[10px] text-gray-500">文字</span>
          <div className="relative h-[18px] flex-1 rounded-lg bg-slate-50 ring-1 ring-inset ring-slate-100">
            {ocrMarks.map((t, i) => (
              <div key={i} className="absolute top-0.5 bottom-0.5 w-1 bg-indigo-400 rounded-full"
                style={{ left: `${(t / duration) * 100}%` }} title="画面文字" />
            ))}
          </div>
        </div>

        <div className="flex items-center">
          <span className="w-16 text-[10px] text-gray-500">节拍</span>
          <div className="relative h-[18px] flex-1 rounded-lg bg-slate-100">
            {beats.map((t, i) => (
              <div key={i} className="absolute top-1 bottom-1 w-px bg-slate-400/70" style={{ left: `${(t / duration) * 100}%` }} />
            ))}
          </div>
        </div>
      </div>

      <div className="mt-4 min-h-[38px] rounded-2xl border border-slate-200/70 bg-slate-50/80 px-3 py-2.5">
        {hoverSeg ? (
          <div className="text-[11px] leading-5 text-slate-600">
            <span className="font-medium" style={{ color: FUNCTION_COLORS[hoverSeg.function] }}>
              {hoverSeg.segment_id} {FUNCTION_LABELS[hoverSeg.function]}
            </span>
            {' · '}{hoverSeg.start_time.toFixed(0)}-{hoverSeg.end_time.toFixed(0)}s
            {hoverRhythm && ` · 镜头密度 ${hoverRhythm.shots_per_second?.toFixed(2)}/s · 卡点 ${hoverRhythm.cut_beat_alignment?.toFixed(2)}`}
            {' · '}{hoverSeg.core_text}
          </div>
        ) : (
          <div className="text-[11px] text-slate-400">悬停查看片段详情，点击跳转</div>
        )}
      </div>
    </div>
  );
}

function Track({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center mb-1.5">
      <span className="w-16 text-[10px] text-gray-500 shrink-0">{label}</span>
      <div className="flex flex-1 gap-1">{children}</div>
    </div>
  );
}

function buildAreaPath(
  energyCurve: { time_range: [number, number]; energy_level: string }[],
  duration: number,
  valMap: Record<string, number>,
): string {
  if (energyCurve.length === 0) return 'M0,22 L100,22';
  const pts: [number, number][] = [];
  energyCurve.forEach((e) => {
    const mid = (e.time_range[0] + e.time_range[1]) / 2;
    const x = (mid / duration) * 100;
    const v = valMap[e.energy_level] ?? 0.5;
    const y = 44 - v * 40;
    pts.push([x, y]);
  });
  if (pts[0][0] > 0) pts.unshift([0, pts[0][1]]);
  if (pts[pts.length - 1][0] < 100) pts.push([100, pts[pts.length - 1][1]]);
  return 'M' + pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' L');
}
