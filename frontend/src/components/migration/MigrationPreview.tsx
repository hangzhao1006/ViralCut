import type { TransferBlueprint, MigrationResult, MigratedSlot } from '../../types';
import { STRATEGY_LABELS } from '../../lib/colors';
import EditableSlotCard from './EditableSlotCard';

interface Props {
  blueprint: TransferBlueprint;
  migration: MigrationResult;
  onSlotUpdate?: (index: number, slot: MigratedSlot) => void;
  onSlotRegenerate?: (index: number, instruction: string, forceStrategy: string) => Promise<void>;
}

const MATCH_LABEL: Record<string, string> = {
  filled: '素材匹配',
  gap: '缺口补全',
  restructured: '结构重排',
  aigc_needed: 'AIGC生成',
};

export default function MigrationPreview({ blueprint, migration, onSlotUpdate, onSlotRegenerate }: Props) {
  const sourceSlots = blueprint.structure_template ?? [];
  const migratedSlots = migration.migrated_slots ?? [];
  const gs = migration.gap_summary;

  return (
    <div className="rounded-[1.75rem] border border-slate-200/80 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-semibold text-slate-950">迁移过程：爆款骨架 → 新视频</span>
        <span className="text-xs text-slate-500">
          可迁移度 {migration.overall_feasibility} · {gs?.filled}/{gs?.total_slots} 填充 · {gs?.gaps} 缺口
        </span>
      </div>

      <div className="text-xs text-slate-500 mb-3">{migration.migration_summary}</div>

      {/* New video timeline (slots mapped temporally) */}
      <div className="mb-4">
        <div className="text-[11px] font-medium text-slate-400 mb-1">新视频时间线</div>
        <div className="flex gap-0.5 h-8">
          {migratedSlots.map((m) => {
            const total = migratedSlots.reduce((s, x) => s + (x.duration_seconds || 1), 0);
            const w = ((m.duration_seconds || 1) / total) * 100;
            const isFilled = m.status === 'filled';
            return (
              <div
                key={m.slot_id}
                title={`${m.slot_type} · ${m.duration_seconds}s · ${isFilled ? '已填充' : '缺口'}`}
                className="rounded flex items-center justify-center text-[8px] overflow-hidden whitespace-nowrap"
                style={{
                  width: `${w}%`,
                  background: isFilled ? '#EAF3DE' : '#FAEEDA',
                  color: isFilled ? '#27500A' : '#854F0B',
                }}
              >
                {m.duration_seconds}s
              </div>
            );
          })}
        </div>
      </div>

      {/* Mapping grid */}
      <div className="grid grid-cols-[1fr_80px_1fr] gap-y-2 items-stretch max-h-[320px] overflow-y-auto pr-1">
        <div className="text-[11px] font-medium text-slate-400 text-center pb-1">爆款骨架 · {blueprint.source_video_type}</div>
        <div />
        <div className="text-[11px] font-medium text-slate-400 text-center pb-1">{migration.new_video_type}</div>

        {migratedSlots.map((m, i) => {
          const src = sourceSlots[i];
          return <FlowRow key={m.slot_id} src={src} migrated={m} />;
        })}
      </div>

      {/* Applied framework rules */}
      {migration.applied_rules?.length > 0 && (
        <div className="mt-4 px-3 py-2.5 rounded-2xl border border-slate-200/70 bg-slate-50/80">
          <div className="text-[11px] text-slate-600">
            <span className="font-medium">套用的骨架规则: </span>
            {migration.applied_rules.join(' · ')}
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="mt-2 flex gap-4 text-[10px] text-slate-500 flex-wrap">
        <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm bg-emerald-100" />已填充</span>
        <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm bg-amber-100" />缺口+补全策略</span>
        <span className="flex items-center gap-1"><span className="w-3.5 h-0.5 bg-emerald-600" />素材匹配</span>
        <span className="flex items-center gap-1"><span className="w-3.5 border-t border-dashed border-amber-500" />需补全</span>
      </div>

      {/* Editable slot cards */}
      {onSlotUpdate && onSlotRegenerate && (
        <div className="mt-4 rounded-2xl border border-slate-200/70 bg-slate-50/70 p-3">
          <div className="mb-2 flex items-center justify-between">
            <div>
              <div className="vc-kicker">Slot editor</div>
              <div className="mt-1 text-xs font-semibold text-slate-800">逐段编辑与重生成</div>
            </div>
            <span className="rounded-full bg-white px-2 py-1 text-[10px] font-medium text-slate-500 shadow-sm">{migratedSlots.length} slots</span>
          </div>
          <div className="max-h-[280px] space-y-2 overflow-y-auto pr-1">
            {migratedSlots.map((m, i) => (
              <EditableSlotCard key={m.slot_id} slot={m} index={i}
                onUpdate={onSlotUpdate} onRegenerate={onSlotRegenerate} />
            ))}
          </div>
        </div>
      )}

      {/* New script */}
      {migration.new_script && (
        <details className="mt-3">
          <summary className="text-xs text-slate-500 cursor-pointer">查看完整新脚本</summary>
          <pre className="text-[11px] text-slate-600 whitespace-pre-wrap font-sans leading-relaxed mt-2 rounded-2xl border border-slate-200/70 bg-slate-50/80 p-3">
            {migration.new_script}
          </pre>
        </details>
      )}
    </div>
  );
}

function FlowRow({ src, migrated }: { src?: { slot_type: string; duration_seconds: number; purpose: string }; migrated: MigratedSlot }) {
  const isFilled = migrated.status === 'filled';
  const arrowColor = isFilled ? '#1D9E75' : '#EF9F27';
  const dashed = !isFilled;

  return (
    <>
      {/* Source skeleton slot */}
      <div className="rounded-lg px-2.5 py-2" style={{ background: '#EEEDFE' }}>
        <div className="text-[11px] font-medium" style={{ color: '#3C3489' }}>
          {src?.slot_type ?? migrated.slot_type} · {src?.duration_seconds ?? migrated.duration_seconds}s
        </div>
        <div className="text-[10px] truncate" style={{ color: '#534AB7' }}>{src?.purpose ?? ''}</div>
      </div>

      {/* Arrow with match label */}
      <div className="flex items-center justify-center relative">
        <svg width="80" height="36">
          <line x1="0" y1="18" x2="80" y2="18" stroke={arrowColor} strokeWidth="1.5" strokeDasharray={dashed ? '3 2' : undefined} />
          <polygon points="74,14 80,18 74,22" fill={arrowColor} />
        </svg>
        <span className="absolute text-[8px] bg-white px-1" style={{ color: isFilled ? '#0F6E56' : '#854F0B' }}>
          {MATCH_LABEL[migrated.status] ?? ''}
        </span>
      </div>

      {/* New video slot */}
      <div className="rounded-lg px-2.5 py-2" style={{ background: isFilled ? '#EAF3DE' : '#FAEEDA' }}>
        <div className="text-[11px] font-medium" style={{ color: isFilled ? '#27500A' : '#633806' }}>
          {migrated.slot_type} · {migrated.duration_seconds}s {isFilled ? '✓' : ''}
        </div>
        <div className="text-[10px] truncate" style={{ color: isFilled ? '#3B6D11' : '#854F0B' }}>
          {migrated.migrated_content?.text ?? ''}
        </div>
        {migrated.gap && (
          <div className="text-[10px] mt-1" style={{ color: '#854F0B' }}>
            {migrated.gap.missing}
            {migrated.fill_strategy && (
              <span className="block text-slate-500">
                → {STRATEGY_LABELS[migrated.fill_strategy.type] ?? migrated.fill_strategy.type}: {migrated.fill_strategy.description}
              </span>
            )}
          </div>
        )}
      </div>
    </>
  );
}
