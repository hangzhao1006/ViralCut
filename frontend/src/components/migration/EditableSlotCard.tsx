import { useState } from 'react';
import type { MigratedSlot } from '../../types';
import { STATUS_COLORS, STRATEGY_LABELS } from '../../lib/colors';

interface Props {
  slot: MigratedSlot;
  index: number;
  sourceSlot?: { slot_type: string; purpose: string; duration_seconds: number; input_requirements?: { needed_assets?: string[] } };
  defaultOpen?: boolean;
  onUpdate: (index: number, slot: MigratedSlot) => void;
  onRegenerate: (index: number, instruction: string, forceStrategy: string) => Promise<void>;
}

const STRATEGIES = ['restructure', 'text_fill', 'packaging', 'aigc', 'asset_reuse'];

export default function EditableSlotCard({ slot, index, sourceSlot, defaultOpen, onUpdate, onRegenerate }: Props) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(slot.migrated_content?.text ?? '');
  const [instruction, setInstruction] = useState('');
  const [regenerating, setRegenerating] = useState(false);
  const [showActions, setShowActions] = useState(defaultOpen ?? false);

  const status = STATUS_COLORS[slot.status] ?? STATUS_COLORS.filled;
  const isGap = slot.status === 'gap' || slot.status === 'aigc_needed';

  function saveText() {
    onUpdate(index, { ...slot, migrated_content: { ...slot.migrated_content, text } });
    setEditing(false);
  }

  function switchStrategy(strategy: string) {
    const newStatus = strategy === 'aigc' ? 'aigc_needed' : strategy === 'restructure' ? 'restructured' : 'gap';
    onUpdate(index, {
      ...slot,
      status: newStatus as MigratedSlot['status'],
      fill_strategy: { type: strategy, description: STRATEGY_LABELS[strategy] ?? strategy },
    });
  }

  async function regen() {
    setRegenerating(true);
    try {
      await onRegenerate(index, instruction, '');
      setInstruction('');
    } finally {
      setRegenerating(false);
    }
  }

  return (
    <div className="group rounded-2xl border border-slate-200/80 bg-white/95 p-3.5 shadow-sm transition-all duration-200 hover:border-indigo-200 hover:shadow-md">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="inline-flex h-6 min-w-6 items-center justify-center rounded-full bg-slate-100 px-2 text-[11px] font-semibold text-slate-500">
              {String(index + 1).padStart(2, '0')}
            </span>
            <span className="truncate text-sm font-semibold text-slate-900">{slot.slot_type}</span>
          </div>
          <div className="mt-1 text-[11px] text-slate-400">{slot.duration_seconds}s · {slot.slot_id}</div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <span
            className="rounded-full px-2.5 py-1 text-[11px] font-medium ring-1 ring-black/5"
            style={{ background: status.bg, color: status.text }}
          >
            {status.label}
          </span>
          <button
            type="button"
            onClick={() => setShowActions(!showActions)}
            className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-500 transition hover:border-indigo-200 hover:bg-indigo-50 hover:text-indigo-700"
          >
            {showActions ? '收起' : '编辑'}
          </button>
        </div>
      </div>

      {sourceSlot && (
        <div className="mb-3 rounded-2xl border border-indigo-100 bg-indigo-50/70 px-3 py-2.5">
          <div className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-indigo-400">
            <span className="h-1.5 w-1.5 rounded-full bg-indigo-400" />
            Skeleton role
          </div>
          <div className="text-xs leading-relaxed text-indigo-950">{sourceSlot.purpose}</div>
          {sourceSlot.input_requirements?.needed_assets && (
            <div className="mt-2 flex flex-wrap gap-1">
              {sourceSlot.input_requirements.needed_assets.map((asset) => (
                <span key={asset} className="rounded-full bg-white/80 px-2 py-0.5 text-[10px] font-medium text-indigo-600 ring-1 ring-indigo-100">
                  {asset}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {editing ? (
        <div className="mb-3">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={3}
            className="w-full resize-none rounded-xl border border-slate-200 bg-slate-50/80 p-3 text-sm leading-relaxed text-slate-800 outline-none transition focus:border-indigo-300 focus:bg-white focus:ring-4 focus:ring-indigo-100"
          />
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              onClick={saveText}
              className="rounded-full bg-slate-950 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-slate-800"
            >
              保存
            </button>
            <button
              type="button"
              onClick={() => { setText(slot.migrated_content?.text ?? ''); setEditing(false); }}
              className="rounded-full px-3 py-1.5 text-xs font-medium text-slate-500 transition hover:bg-slate-100 hover:text-slate-700"
            >
              取消
            </button>
          </div>
        </div>
      ) : (
        slot.migrated_content?.text && (
          <div
            className="mb-2 rounded-xl bg-slate-50 px-3 py-2.5 text-sm leading-relaxed text-slate-700 transition hover:bg-slate-100"
            onClick={() => showActions && setEditing(true)}
          >
            {slot.migrated_content.text}
            {showActions && <span className="ml-2 text-[10px] font-medium text-indigo-400">点击改文案</span>}
          </div>
        )
      )}

      {slot.gap && (
        <div className="mt-2 rounded-xl border border-amber-200 bg-amber-50/80 px-3 py-2 text-[11px] leading-relaxed text-amber-800">
          <span className="font-semibold">缺口：</span>{slot.gap.missing}
          {slot.fill_strategy && (
            <span className="mt-1 block text-amber-700/80">
              → {STRATEGY_LABELS[slot.fill_strategy.type] ?? slot.fill_strategy.type}: {slot.fill_strategy.description}
            </span>
          )}
        </div>
      )}

      {showActions && (
        <div className="mt-3 space-y-3 border-t border-slate-100 pt-3">
          {isGap && (
            <div>
              <div className="mb-1.5 text-[11px] font-medium text-slate-500">缺口填充方式</div>
              <div className="flex flex-wrap gap-1.5">
                {STRATEGIES.map((s) => (
                  <button
                    type="button"
                    key={s}
                    onClick={() => switchStrategy(s)}
                    className={`rounded-full border px-2.5 py-1 text-[11px] font-medium transition ${
                      slot.fill_strategy?.type === s
                        ? 'border-indigo-300 bg-indigo-50 text-indigo-700 shadow-sm'
                        : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50'
                    }`}
                  >
                    {STRATEGY_LABELS[s]}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div>
            <div className="mb-1.5 text-[11px] font-medium text-slate-500">用一句话调整这段</div>
            <div className="flex gap-2">
              <input
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                placeholder="例：文案更口语化 / 开头更抓人"
                className="h-9 flex-1 rounded-full border border-slate-200 bg-white px-3 text-xs text-slate-700 outline-none transition placeholder:text-slate-400 focus:border-indigo-300 focus:ring-4 focus:ring-indigo-100"
              />
              <button
                type="button"
                onClick={regen}
                disabled={regenerating}
                className="rounded-full bg-indigo-600 px-3.5 text-xs font-semibold text-white shadow-sm transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {regenerating ? '生成中' : '重新生成'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
