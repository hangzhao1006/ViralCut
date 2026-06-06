import { useState } from 'react';
import type { TransferBlueprint, MigrationResult, MigratedSlot } from '../../types';
import { STRATEGY_LABELS } from '../../lib/colors';
import EditableSlotCard from './EditableSlotCard';

interface Props {
  blueprint: TransferBlueprint;
  migration: MigrationResult;
  onSlotUpdate?: (index: number, slot: MigratedSlot) => void;
  onSlotRegenerate?: (index: number, instruction: string, forceStrategy: string) => Promise<void>;
}

export default function MigrationPreview({ blueprint, migration, onSlotUpdate, onSlotRegenerate }: Props) {
  const sourceSlots = blueprint.structure_template ?? [];
  const migratedSlots = migration.migrated_slots ?? [];
  const gs = migration.gap_summary;
  const [selected, setSelected] = useState<number | null>(null);

  const totalDur = migratedSlots.reduce((s, x) => s + (x.duration_seconds || 1), 0) || 1;
  const editable = onSlotUpdate && onSlotRegenerate;

  return (
    <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm">
      {/* Header */}
      <div className="mb-3 flex items-center justify-between">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-indigo-400">Migration</div>
          <div className="mt-0.5 text-sm font-semibold text-slate-900">爆款骨架 → 新视频</div>
        </div>
        <div className="flex items-center gap-2 text-[11px]">
          <span className="rounded-full bg-slate-100 px-2.5 py-1 font-medium text-slate-600">可迁移度 {migration.overall_feasibility}</span>
          <span className="rounded-full bg-emerald-50 px-2.5 py-1 font-medium text-emerald-700">{gs?.filled} 填充</span>
          <span className="rounded-full bg-amber-50 px-2.5 py-1 font-medium text-amber-700">{gs?.gaps} 缺口</span>
        </div>
      </div>

      <div className="mb-4 text-xs leading-relaxed text-slate-500">{migration.migration_summary}</div>

      {/* New video timeline — click a block to edit */}
      <div className="mb-2 flex items-center justify-between">
        <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">New video timeline</div>
        {editable && <div className="text-[11px] text-slate-400">点击片段编辑</div>}
      </div>
      <div className="flex gap-1">
        {migratedSlots.map((m, i) => {
          const w = ((m.duration_seconds || 1) / totalDur) * 100;
          const isFilled = m.status === 'filled';
          const isSel = selected === i;
          return (
            <button
              key={m.slot_id}
              type="button"
              onClick={() => editable && setSelected(isSel ? null : i)}
              title={`${m.slot_type} · ${m.duration_seconds}s`}
              className={`flex h-12 flex-col items-center justify-center overflow-hidden rounded-xl text-[9px] font-medium transition-all ${
                isSel ? 'ring-2 ring-indigo-500 ring-offset-1' : 'ring-1 ring-black/5'
              }`}
              style={{
                width: `${w}%`,
                background: isFilled ? '#EAF3DE' : '#FAEEDA',
                color: isFilled ? '#27500A' : '#854F0B',
                cursor: editable ? 'pointer' : 'default',
              }}
            >
              <span className="max-w-full truncate px-1 font-semibold">{m.slot_type?.slice(0, 8)}</span>
              <span className="opacity-70">{m.duration_seconds}s</span>
            </button>
          );
        })}
      </div>

      {/* Selected slot editor — appears right under the clicked block */}
      {editable && selected !== null && migratedSlots[selected] && (
        <div className="mt-3">
          <EditableSlotCard
            slot={migratedSlots[selected]}
            index={selected}
            sourceSlot={sourceSlots[selected]}
            onUpdate={onSlotUpdate!}
            onRegenerate={onSlotRegenerate!}
            defaultOpen
          />
        </div>
      )}

      {/* Collapsible skeleton mapping */}
      <details className="mt-4 group">
        <summary className="flex cursor-pointer items-center gap-1.5 text-xs font-medium text-slate-500 transition hover:text-slate-700">
          <span className="transition group-open:rotate-90">▸</span> 查看骨架映射关系
        </summary>
        <div className="mt-3 grid max-h-[260px] grid-cols-[1fr_64px_1fr] items-stretch gap-y-1.5 overflow-y-auto pr-1">
          <div className="pb-1 text-center text-[10px] font-medium text-slate-400">爆款骨架</div>
          <div />
          <div className="pb-1 text-center text-[10px] font-medium text-slate-400">新视频</div>
          {migratedSlots.map((m, i) => (
            <FlowRow key={m.slot_id} src={sourceSlots[i]} migrated={m} />
          ))}
        </div>
      </details>

      {/* Applied rules */}
      {migration.applied_rules?.length > 0 && (
        <div className="mt-3 rounded-xl bg-slate-50 px-3 py-2.5">
          <div className="text-[11px] leading-relaxed text-slate-600">
            <span className="font-semibold text-slate-700">套用的骨架规则：</span>{migration.applied_rules.join(' · ')}
          </div>
        </div>
      )}

      {/* New script */}
      {migration.new_script && (
        <details className="mt-3 group">
          <summary className="flex cursor-pointer items-center gap-1.5 text-xs font-medium text-slate-500 transition hover:text-slate-700">
            <span className="transition group-open:rotate-90">▸</span> 查看完整新脚本
          </summary>
          <pre className="mt-2 whitespace-pre-wrap rounded-xl bg-slate-50 p-3 font-sans text-[11px] leading-relaxed text-slate-600">
            {migration.new_script}
          </pre>
        </details>
      )}
    </div>
  );
}

function FlowRow({ src, migrated }: {
  src?: { slot_type: string; duration_seconds: number; purpose: string };
  migrated: MigratedSlot;
}) {
  const isFilled = migrated.status === 'filled';
  const arrowColor = isFilled ? '#1D9E75' : '#EF9F27';
  return (
    <>
      <div className="rounded-xl px-2.5 py-2" style={{ background: '#EEF2FF' }}>
        <div className="text-[11px] font-semibold text-indigo-900">
          {src?.slot_type ?? migrated.slot_type} · {src?.duration_seconds ?? migrated.duration_seconds}s
        </div>
        <div className="truncate text-[10px] text-indigo-500">{src?.purpose ?? ''}</div>
      </div>
      <div className="flex items-center justify-center">
        <svg width="64" height="30">
          <line x1="0" y1="15" x2="64" y2="15" stroke={arrowColor} strokeWidth="1.5" strokeDasharray={isFilled ? undefined : '3 2'} />
          <polygon points="58,11 64,15 58,19" fill={arrowColor} />
        </svg>
      </div>
      <div className="rounded-xl px-2.5 py-2" style={{ background: isFilled ? '#EAF3DE' : '#FAEEDA' }}>
        <div className="text-[11px] font-semibold" style={{ color: isFilled ? '#27500A' : '#633806' }}>
          {migrated.slot_type} {isFilled ? '✓' : ''}
        </div>
        <div className="truncate text-[10px]" style={{ color: isFilled ? '#3B6D11' : '#854F0B' }}>
          {migrated.migrated_content?.text ?? ''}
        </div>
        {migrated.gap && (
          <div className="mt-0.5 text-[10px]" style={{ color: '#854F0B' }}>
            {migrated.gap.missing}
            {migrated.fill_strategy && (
              <span className="block text-slate-500">→ {STRATEGY_LABELS[migrated.fill_strategy.type] ?? migrated.fill_strategy.type}</span>
            )}
          </div>
        )}
      </div>
    </>
  );
}
