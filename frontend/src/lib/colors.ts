// Color mappings for visualization

// Unified color system — indigo primary + violet / teal / amber accents.
// All four hues share similar saturation and lightness, so they feel designed together.
// Keys cannot change (backend contract); only values are updated.

// One hue only: indigo. Darkness = importance/intensity.
// Slate for purely structural/neutral segments.

export const FUNCTION_COLORS: Record<string, string> = {
  hook:         '#312E81',  // indigo-900 — deepest, most commanding
  climax:       '#3730A3',  // indigo-800 — peak dramatic moment
  cta:          '#4F46E5',  // indigo-600 — call to action
  demonstration:'#6366F1',  // indigo-500 — active content
  comparison:   '#818CF8',  // indigo-400 — analytical
  introduction: '#A5B4FC',  // indigo-300 — scene-setting
  instruction:  '#C7D2FE',  // indigo-200 — informational
  transition:   '#94A3B8',  // slate-400  — neutral bridge
  resolution:   '#CBD5E1',  // slate-300  — quiet close
};

export const PACE_COLORS: Record<string, string> = {
  very_slow: '#C7D2FE',  // indigo-200 — slowest
  slow:      '#A5B4FC',  // indigo-300
  medium:    '#6366F1',  // indigo-500
  fast:      '#4338CA',  // indigo-700
  very_fast: '#312E81',  // indigo-900 — fastest
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
  low:          '#EEF2FF',  // indigo-50
  'low-medium': '#C7D2FE',  // indigo-200
  medium:       '#818CF8',  // indigo-400
  'medium-high':'#6366F1',  // indigo-500
  high:         '#4338CA',  // indigo-700
  peak:         '#312E81',  // indigo-900
};

export const STATUS_COLORS: Record<string, { bg: string; text: string; label: string }> = {
  filled:      { bg: '#F0FDF4', text: '#047857', label: '已填充' },   // green  — success
  gap:         { bg: '#FFFBEB', text: '#B45309', label: '缺口' },    // amber  — warning
  restructured:{ bg: '#EEF2FF', text: '#4F46E5', label: '已重排' },  // indigo — our primary
  aigc_needed: { bg: '#F5F3FF', text: '#7C3AED', label: '需AIGC' },  // violet — adjacent to indigo
};

export const STRATEGY_LABELS: Record<string, string> = {
  restructure: '结构重排',
  text_fill: '文案补全',
  packaging: '包装补全',
  aigc: 'AIGC生成',
  asset_reuse: '素材复用',
};
