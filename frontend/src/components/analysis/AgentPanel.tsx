import type { VideoStructure } from '../../types';
import { getCurrentSegment } from '../../lib/timeline';

interface Props {
  structure: VideoStructure;
  currentTime: number;
}

const FUNCTION_CN: Record<string, string> = {
  hook: '开场钩子', introduction: '背景引入', instruction: '讲解说明',
  demonstration: '效果示范', comparison: '对比展示', transition: '过渡',
  climax: '高潮亮点', resolution: '收尾', cta: '行动号召',
};

const PACE_CN: Record<string, string> = {
  very_slow: '很慢', slow: '慢', medium: '中等', fast: '快', very_fast: '很快',
};

const DRIVER_CN: Record<string, string> = {
  scene_cut: '镜头切换', beat_sync: '音乐卡点', visual_version_change: '画面变化',
  information_reveal: '信息揭示', speech: '语音讲解', uncertain: '不明确',
};

const VALUE_CN: Record<string, string> = {
  skill_learning: '技能教学', product: '产品推广', product_ad: '产品广告',
  knowledge: '知识科普', entertainment: '娱乐', emotional: '情感共鸣',
  identity: '身份认同', social_proof: '社会证明', brand: '品牌宣传',
  event_announcement: '活动预告', exhibition_promotion: '展览宣传',
  design_showcase: '设计展示', portfolio_showcase: '作品集展示',
};

const ENERGY_CN: Record<string, string> = {
  low: '低', 'low-medium': '中低', medium: '中等', 'medium-high': '中高', high: '高', peak: '峰值',
};

const ENERGY_BAR: Record<string, string> = {
  low: '▓░░░░', 'low-medium': '▓▓░░░', medium: '▓▓▓░░', 'medium-high': '▓▓▓▓░', high: '▓▓▓▓▓', peak: '█████',
};

export default function AgentPanel({ structure, currentTime }: Props) {
  const segments = structure.script_structure?.segments ?? [];
  const rhythms = structure.rhythm_structure?.segment_rhythm ?? [];
  const energyCurve = structure.energy_curve?.energy_curve ?? [];
  const valueStrategy = structure.value_strategy?.value_strategy ?? {};

  const seg = getCurrentSegment(currentTime, segments);
  const rhythm = getCurrentSegment(currentTime, rhythms);
  const energy = getCurrentSegment(currentTime, energyCurve);

  const valueType = String(valueStrategy.value_type ?? '');
  const energyLevel = energy?.energy_level ?? '';

  const cards = [
    {
      name: '这段在做什么',
      color: '#4F46E5',  // indigo-600
      badge: 'Script',
      value: seg ? (FUNCTION_CN[seg.function] ?? seg.function) : '—',
      sub: seg?.core_text ?? '播放视频查看分析',
    },
    {
      name: '节奏',
      color: '#818CF8',  // indigo-400
      badge: 'Rhythm',
      value: rhythm ? (PACE_CN[rhythm.pace] ?? rhythm.pace) : '—',
      sub: rhythm ? `由${DRIVER_CN[rhythm.rhythm_driver ?? ''] ?? '画面'}驱动` : '',
    },
    {
      name: '价值类型',
      color: '#6366F1',  // indigo-500
      badge: 'Value',
      value: VALUE_CN[valueType] ?? valueType ?? '—',
      sub: String(valueStrategy.primary_value ?? '').slice(0, 54),
    },
    {
      name: '注意力强度',
      color: '#312E81',  // indigo-900 — deepest for intensity
      badge: 'Energy',
      value: energyLevel ? `${ENERGY_BAR[energyLevel] ?? ''} ${ENERGY_CN[energyLevel] ?? energyLevel}` : '—',
      sub: energy?.role ?? '',
    },
  ];

  return (
    <div className="flex flex-col gap-3">
      {cards.map((c) => (
        <div key={c.name} className="group relative overflow-hidden rounded-2xl border border-slate-200/80 bg-white p-3.5 shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md">
          <div className="absolute inset-y-0 left-0 w-1" style={{ background: c.color }} />
          <div className="mb-2 flex items-center justify-between gap-2 pl-1">
            <div className="text-[11px] font-medium text-slate-400">{c.name}</div>
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[9px] font-semibold text-slate-500">{c.badge}</span>
          </div>
          <div className="pl-1 text-[15px] font-semibold leading-snug text-slate-950">{c.value}</div>
          {c.sub && <div className="mt-1.5 line-clamp-2 pl-1 text-[11px] leading-5 text-slate-500">{c.sub}</div>}
        </div>
      ))}
    </div>
  );
}
