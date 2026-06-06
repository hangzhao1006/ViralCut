// Color mappings for visualization

export const FUNCTION_COLORS: Record<string, string> = {
  hook: '#4F46E5',
  introduction: '#8B5CF6',
  instruction: '#8B5CF6',
  demonstration: '#10B981',
  comparison: '#0EA5E9',
  transition: '#64748B',
  climax: '#F43F5E',
  resolution: '#64748B',
  cta: '#F59E0B',
};

export const PACE_COLORS: Record<string, string> = {
  very_slow: '#0F766E',
  slow: '#14B8A6',
  medium: '#22C55E',
  fast: '#F97316',
  very_fast: '#EF4444',
};

export const ENERGY_HEIGHT: Record<string, number> = {
  low: 25,
  'low-medium': 40,
  medium: 60,
  'medium-high': 78,
  high: 90,
  peak: 100,
};

export const ENERGY_COLORS: Record<string, string> = {
  low: '#A7F3D0',
  'low-medium': '#5EEAD4',
  medium: '#A3E635',
  'medium-high': '#FACC15',
  high: '#FB923C',
  peak: '#F43F5E',
};

export const STATUS_COLORS: Record<string, { bg: string; text: string; label: string }> = {
  filled: { bg: '#ECFDF5', text: '#047857', label: '已填充' },
  gap: { bg: '#FFFBEB', text: '#B45309', label: '缺口' },
  restructured: { bg: '#EFF6FF', text: '#1D4ED8', label: '已重排' },
  aigc_needed: { bg: '#FDF2F8', text: '#BE185D', label: '需AIGC生成' },
};

export const STRATEGY_LABELS: Record<string, string> = {
  restructure: '结构重排',
  text_fill: '文案补全',
  packaging: '包装补全',
  aigc: 'AIGC生成',
  asset_reuse: '素材复用',
};
