import { useState } from 'react';
import type { VideoStructure } from '../types';

interface Props {
  structure: VideoStructure;
  evidence: Record<string, unknown> | null;
}

type View = 'analyzed' | 'raw';

export default function DataInspector({ structure, evidence }: Props) {
  const [view, setView] = useState<View>('analyzed');

  return (
    <div className="rounded-[1.75rem] border border-slate-200/80 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center gap-2 rounded-2xl bg-slate-100/70 p-1">
        <button onClick={() => setView('analyzed')}
          className={`rounded-xl px-3 py-1.5 text-xs font-medium transition ${view === 'analyzed' ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-500 hover:text-slate-800'}`}>
          分析结果 (Stage 2)
        </button>
        <button onClick={() => setView('raw')}
          className={`rounded-xl px-3 py-1.5 text-xs font-medium transition ${view === 'raw' ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-500 hover:text-slate-800'}`}>
          原始解析 (Stage 1)
        </button>
      </div>

      {view === 'analyzed' ? <AnalyzedView structure={structure} /> : <RawView evidence={evidence} />}
    </div>
  );
}

function AnalyzedView({ structure }: { structure: VideoStructure }) {
  const script = structure.script_structure ?? {};
  const rhythm = structure.rhythm_structure ?? {};
  const value = structure.value_strategy?.value_strategy ?? {};
  const energy = structure.energy_curve ?? {};
  const blueprint = structure.transfer_blueprint?.transfer_blueprint ?? {};

  return (
    <div className="max-h-[430px] space-y-3 overflow-y-auto text-xs">
      <Section title="脚本结构">
        <Row label="结构模式" value={(script as unknown as Record<string, unknown>).structure_pattern as string} />
        <Row label="段落数" value={String(((script as unknown as Record<string, unknown>).segments as unknown[])?.length ?? 0)} />
        <Row label="hook类型" value={(script as unknown as Record<string, unknown>).hook_type as string} />
      </Section>

      <Section title="节奏">
        <Row label="整体节奏" value={(rhythm.overall_rhythm as Record<string, unknown>)?.pace as string} />
        <Row label="节奏模式" value={rhythm.rhythm_pattern as string} />
        <Row label="高潮位置" value={JSON.stringify((rhythm.climax_analysis as Record<string, unknown>)?.confirmed_range)} />
      </Section>

      <Section title="价值主张">
        <Row label="价值类型" value={value.value_type as string} />
        <Row label="核心价值" value={value.primary_value as string} />
        <Row label="目标受众" value={value.target_audience as string} />
      </Section>

      <Section title="能量曲线">
        <Row label="能量模式" value={energy.energy_pattern as string} />
      </Section>

      <Section title="迁移蓝图">
        <Row label="源视频类型" value={(blueprint as unknown as Record<string, unknown>).source_video_type as string} />
        <Row label="slot数量" value={String(((blueprint as unknown as Record<string, unknown>).structure_template as unknown[])?.length ?? 0)} />
        <Row label="剪辑规则数" value={String(((blueprint as unknown as Record<string, unknown>).editing_rules as unknown[])?.length ?? 0)} />
      </Section>

      {structure.evaluation && (
        <Section title="质量评估">
          <Row label="评分" value={`${structure.evaluation.score} (${structure.evaluation.status})`} />
        </Section>
      )}
    </div>
  );
}

function RawView({ evidence }: { evidence: Record<string, unknown> | null }) {
  if (!evidence) {
    return <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 py-8 text-center text-xs text-slate-400">无原始数据（复用结果时可能不含evidence_package）</div>;
  }

  const meta = (evidence.metadata as Record<string, unknown>) ?? {};
  const scenes = (evidence.scenes as unknown[]) ?? [];
  const keyframes = (evidence.keyframes as unknown[]) ?? [];
  const ocr = (evidence.ocr_results as unknown[]) ?? [];
  const transcript = (evidence.transcript as unknown[]) ?? [];
  const beats = (evidence.beats as Record<string, unknown>) ?? {};
  const basic = (evidence.basic_analysis as Record<string, unknown>) ?? {};

  return (
    <div className="max-h-[430px] space-y-3 overflow-y-auto text-xs">
      <Section title="视频信息">
        <Row label="时长" value={`${(meta.duration as number)?.toFixed(1)}秒`} />
        <Row label="分辨率" value={meta.resolution as string} />
        <Row label="FPS" value={String(meta.fps)} />
      </Section>

      <Section title={`镜头 (${scenes.length})`}>
        {scenes.slice(0, 8).map((s, i) => {
          const sc = s as Record<string, number>;
          return <Row key={i} label={`镜头${i}`} value={`${sc.start_time?.toFixed(1)}-${sc.end_time?.toFixed(1)}s`} />;
        })}
      </Section>

      <Section title={`画面文字 OCR (${ocr.length})`}>
        {ocr.slice(0, 10).map((o, i) => {
          const oc = o as Record<string, unknown>;
          const text = (oc.display_text as string) ?? '';
          if (!text.trim()) return null;
          return <Row key={i} label={`${(oc.timestamp as number)?.toFixed(1)}s`} value={text.slice(0, 40)} />;
        })}
      </Section>

      <Section title={`语音 (${transcript.length})`}>
        {transcript.slice(0, 8).map((t, i) => {
          const tr = t as Record<string, unknown>;
          return <Row key={i} label={`${(tr.start as number)?.toFixed(1)}s`} value={(tr.text as string)?.slice(0, 40)} />;
        })}
      </Section>

      <Section title="节拍">
        <Row label="BPM" value={String((beats.bpm as number)?.toFixed(1))} />
        <Row label="节拍数" value={String((beats.beat_timestamps as unknown[])?.length ?? 0)} />
        <Row label="卡点同步分" value={String(beats.beat_sync_score)} />
      </Section>

      <Section title="基础分析">
        <Row label="字幕密度" value={basic.subtitle_density as string} />
        <Row label="平均镜头时长" value={`${basic.avg_shot_duration}秒`} />
        <Row label="预估节奏" value={basic.estimated_pace as string} />
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500">{title}</div>
      <div className="space-y-1 rounded-2xl border border-slate-200/70 bg-slate-50/80 p-3">{children}</div>
    </div>
  );
}

function Row({ label, value }: { label: string; value?: string }) {
  if (value === undefined || value === 'undefined' || value === null) return null;
  return (
    <div className="flex justify-between gap-3">
      <span className="shrink-0 text-slate-400">{label}</span>
      <span className="text-right text-slate-700">{value}</span>
    </div>
  );
}
