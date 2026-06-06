import { useState } from 'react';
import type { MigratedSlot } from '../../types';
import { STATUS_COLORS, STRATEGY_LABELS } from '../../lib/colors';

interface Props {
  slot: MigratedSlot;
  index: number;
  onUpdate: (index: number, slot: MigratedSlot) => void;
  onRegenerate: (index: number, instruction: string, forceStrategy: string) => Promise<void>;
}

const STRATEGIES = ['restructure', 'text_fill', 'packaging', 'aigc', 'asset_reuse'];

export default function EditableSlotCard({ slot, index, onUpdate, onRegenerate }: Props) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(slot.migrated_content?.text ?? '');
  const [instruction, setInstruction] = useState('');
  const [regenerating, setRegenerating] = useState(false);
  const [showActions, setShowActions] = useState(false);

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
    <div className="bg-white border border-gray-200 rounded-lg p-3">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">{slot.slot_type}</span>
          <span className="text-xs text-gray-400">{slot.duration_seconds}s</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: status.bg, color: status.text }}>
            {status.label}
          </span>
          <button onClick={() => setShowActions(!showActions)} className="text-gray-400 text-xs hover:text-gray-600">
            {showActions ? '收起' : '编辑'}
          </button>
        </div>
      </div>

      {/* Text content (editable) */}
      {editing ? (
        <div className="mb-2">
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={2}
            className="w-full text-sm border border-gray-300 rounded p-2" />
          <div className="flex gap-2 mt-1">
            <button onClick={saveText} className="text-xs bg-gray-900 text-white px-2 py-1 rounded">保存</button>
            <button onClick={() => { setText(slot.migrated_content?.text ?? ''); setEditing(false); }} className="text-xs text-gray-500">取消</button>
          </div>
        </div>
      ) : (
        slot.migrated_content?.text && (
          <div className="text-sm mb-1 cursor-text" onClick={() => showActions && setEditing(true)}>
            {slot.migrated_content.text}
            {showActions && <span className="text-[10px] text-gray-400 ml-2">点击改文案</span>}
          </div>
        )
      )}

      {/* Gap info */}
      {slot.gap && (
        <div className="text-[11px] text-amber-700 mt-1">
          缺口: {slot.gap.missing}
          {slot.fill_strategy && (
            <span className="text-gray-500"> → {STRATEGY_LABELS[slot.fill_strategy.type] ?? slot.fill_strategy.type}: {slot.fill_strategy.description}</span>
          )}
        </div>
      )}

      {/* Edit actions */}
      {showActions && (
        <div className="mt-3 pt-3 border-t border-gray-100 space-y-2">
          {/* Fill method switch for gaps */}
          {isGap && (
            <div>
              <div className="text-[11px] text-gray-500 mb-1">缺口填充方式</div>
              <div className="flex flex-wrap gap-1">
                {STRATEGIES.map((s) => (
                  <button key={s} onClick={() => switchStrategy(s)}
                    className={`text-[11px] px-2 py-1 rounded border ${slot.fill_strategy?.type === s ? 'border-indigo-400 bg-indigo-50 text-indigo-700' : 'border-gray-200 text-gray-600'}`}>
                    {STRATEGY_LABELS[s]}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Regenerate with instruction */}
          <div>
            <div className="text-[11px] text-gray-500 mb-1">用一句话调整这段</div>
            <div className="flex gap-1">
              <input value={instruction} onChange={(e) => setInstruction(e.target.value)}
                placeholder="例：文案更口语化 / 开头更抓人"
                className="flex-1 text-xs border border-gray-300 rounded px-2 h-8" />
              <button onClick={regen} disabled={regenerating}
                className="text-xs bg-indigo-600 text-white px-3 rounded disabled:opacity-40">
                {regenerating ? '...' : '重新生成'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
