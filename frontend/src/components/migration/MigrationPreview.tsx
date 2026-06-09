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

// ── Constants ──────────────────────────────────────────────────────
const SLOT_H  = 64;  // fixed height for each left-side slot (px)
const HANDLE_H = 6;  // drag handle / gap between slots (px)
const ARROW_W  = 64; // middle column width (px)

type SourceSlot = { slot_type: string; duration_seconds: number; purpose: string };

// ── SkeletonMap ────────────────────────────────────────────────────
function SkeletonMap({
  sourceSlots,
  migratedSlots,
}: {
  sourceSlots: SourceSlot[];
  migratedSlots: MigratedSlot[];
}) {
  const n = migratedSlots.length;
  const [heights, setHeights] = useState<number[]>(() => Array(n).fill(SLOT_H));

  // Drag a handle between slot[idx] and slot[idx+1].
  // Captures heights at mousedown so delta is always relative to drag start.
  function handleMouseDown(idx: number, e: React.MouseEvent) {
    e.preventDefault();
    const startY = e.clientY;
    const h0    = heights[idx];
    const h1    = heights[idx + 1];
    const total = h0 + h1;

    const onMove = (ev: MouseEvent) => {
      const delta = ev.clientY - startY;
      const newH0 = Math.max(0, Math.min(total, h0 + delta));
      setHeights((prev) => {
        const next = [...prev];
        next[idx]     = newH0;
        next[idx + 1] = total - newH0;
        return next;
      });
    };

    const onUp = () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup',   onUp);
    };

    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup',   onUp);
  }

  // Left column: all slots at fixed SLOT_H with HANDLE_H gaps
  const leftCumY = sourceSlots.map((_, i) => i * (SLOT_H + HANDLE_H));
  const totalLeftH =
    sourceSlots.length * SLOT_H +
    Math.max(0, sourceSlots.length - 1) * HANDLE_H;

  // Right column: cumulative Y positions (include handle gaps)
  const rightCumY: number[] = [];
  let cum = 0;
  for (let i = 0; i < n; i++) {
    rightCumY.push(cum);
    cum += heights[i] + (i < n - 1 ? HANDLE_H : 0);
  }
  const totalRightH = cum;
  const svgH = Math.max(totalLeftH, totalRightH, 1);

  return (
    <div style={{ display: 'flex', alignItems: 'flex-start' }}>

      {/* ── Left: source slots (fixed, non-interactive) ── */}
      <div style={{ flex: 1 }}>
        {sourceSlots.map((src, i) => (
          <div key={i}>
            <div
              style={{
                height: SLOT_H,
                borderRadius: 12,
                background: '#EEF2FF',
                padding: '8px 10px',
                boxSizing: 'border-box',
                overflow: 'hidden',
              }}
            >
              <div style={{ fontSize: 11, fontWeight: 600, color: '#3730A3', lineHeight: 1.4 }}>
                {src.slot_type ?? '—'} · {src.duration_seconds ?? 0}s
              </div>
              <div
                style={{
                  fontSize: 10,
                  color: '#6366F1',
                  marginTop: 2,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {src.purpose ?? ''}
              </div>
            </div>
            {i < sourceSlots.length - 1 && <div style={{ height: HANDLE_H }} />}
          </div>
        ))}
      </div>

      {/* ── Middle: bent SVG arrows ── */}
      <div style={{ width: ARROW_W, flexShrink: 0, height: svgH, position: 'relative' }}>
        <svg width={ARROW_W} height={svgH} style={{ display: 'block', overflow: 'visible' }}>
          {migratedSlots.map((m, i) => {
            if (heights[i] === 0) return null;                        // slot collapsed → no arrow
            const isFilled = m.status === 'filled';
            const color    = isFilled ? '#1D9E75' : '#EF9F27';

            // Source midpoint on the left (use clamped index if counts differ)
            const srcIdx = Math.min(i, sourceSlots.length - 1);
            const lY = leftCumY[srcIdx] + SLOT_H / 2;

            // New-slot midpoint on the right
            const rY = rightCumY[i] + heights[i] / 2;

            // Elbow in the centre of the arrow column
            const midX = ARROW_W / 2;
            const ah   = 4; // arrowhead half-height
            const arrowPts = `${ARROW_W - 6},${rY - ah} ${ARROW_W},${rY} ${ARROW_W - 6},${rY + ah}`;

            return (
              <g key={m.slot_id}>
                <polyline
                  points={`0,${lY} ${midX},${lY} ${midX},${rY} ${ARROW_W - 2},${rY}`}
                  fill="none"
                  stroke={color}
                  strokeWidth="1.5"
                  strokeDasharray={isFilled ? undefined : '3 2'}
                  strokeLinejoin="round"
                />
                <polygon points={arrowPts} fill={color} />
              </g>
            );
          })}
        </svg>
      </div>

      {/* ── Right: new-video slots with draggable boundaries ── */}
      <div style={{ flex: 1 }}>
        {migratedSlots.map((m, i) => {
          const isFilled = m.status === 'filled';
          const h        = heights[i];
          return (
            <div key={m.slot_id}>
              {/* Slot box */}
              <div
                style={{
                  height:      h,
                  overflow:    'hidden',
                  borderRadius: h > 0 ? 12 : 0,
                  background:  isFilled ? '#EAF3DE' : '#FAEEDA',
                  padding:     h >= 32 ? '8px 10px' : 0,
                  boxSizing:   'border-box',
                  transition:  'border-radius 0.1s',
                }}
              >
                {h >= 32 && (
                  <>
                    <div
                      style={{
                        fontSize:   11,
                        fontWeight: 600,
                        color:      isFilled ? '#27500A' : '#633806',
                        lineHeight: 1.4,
                      }}
                    >
                      {m.slot_type}{isFilled ? ' ✓' : ''}
                    </div>
                    <div
                      style={{
                        fontSize:     10,
                        color:        isFilled ? '#3B6D11' : '#854F0B',
                        marginTop:    2,
                        overflow:     'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace:   'nowrap',
                      }}
                    >
                      {m.migrated_content?.text ?? ''}
                    </div>
                    {m.gap && (
                      <div style={{ fontSize: 10, color: '#854F0B', marginTop: 2 }}>
                        {m.gap.missing}
                        {m.fill_strategy && (
                          <span style={{ display: 'block', color: '#94a3b8' }}>
                            → {STRATEGY_LABELS[m.fill_strategy.type] ?? m.fill_strategy.type}
                          </span>
                        )}
                      </div>
                    )}
                  </>
                )}
              </div>

              {/* Drag handle (between this slot and the next) */}
              {i < n - 1 && (
                <div
                  onMouseDown={(e) => handleMouseDown(i, e)}
                  title="拖动调整框架高度"
                  style={{
                    height:     HANDLE_H,
                    cursor:     'row-resize',
                    display:    'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    userSelect: 'none',
                    flexShrink: 0,
                  }}
                >
                  <div
                    style={{
                      width:        '36%',
                      height:       3,
                      borderRadius: 2,
                      background:   '#cbd5e1',
                    }}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────
export default function MigrationPreview({
  blueprint,
  migration,
  onSlotUpdate,
  onSlotRegenerate,
}: Props) {
  const sourceSlots   = blueprint.structure_template ?? [];
  const migratedSlots = migration.migrated_slots ?? [];
  const gs            = migration.gap_summary;
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
          <span className="rounded-full bg-slate-100 px-2.5 py-1 font-medium text-slate-600">
            可迁移度 {migration.overall_feasibility}
          </span>
          <span className="rounded-full bg-emerald-50 px-2.5 py-1 font-medium text-emerald-700">
            {gs?.filled} 填充
          </span>
          <span className="rounded-full bg-amber-50 px-2.5 py-1 font-medium text-amber-700">
            {gs?.gaps} 缺口
          </span>
        </div>
      </div>

      <div className="mb-4 text-xs leading-relaxed text-slate-500">{migration.migration_summary}</div>

      {/* New video timeline bar */}
      <div className="mb-2 flex items-center justify-between">
        <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
          New video timeline
        </div>
        {editable && <div className="text-[11px] text-slate-400">点击片段编辑</div>}
      </div>
      <div className="flex gap-1">
        {migratedSlots.map((m, i) => {
          const w        = ((m.duration_seconds || 1) / totalDur) * 100;
          const isFilled = m.status === 'filled';
          const isSel    = selected === i;
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
                width:      `${w}%`,
                background: isFilled ? '#EAF3DE' : '#FAEEDA',
                color:      isFilled ? '#27500A' : '#854F0B',
                cursor:     editable ? 'pointer' : 'default',
              }}
            >
              <span className="max-w-full truncate px-1 font-semibold">{m.slot_type?.slice(0, 8)}</span>
              <span className="opacity-70">{m.duration_seconds}s</span>
            </button>
          );
        })}
      </div>

      {/* Selected slot editor */}
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

      {/* Collapsible skeleton mapping — full height, no scroll cap */}
      <details className="mt-4 group">
        <summary className="flex cursor-pointer items-center gap-1.5 text-xs font-medium text-slate-500 transition hover:text-slate-700">
          <span className="transition group-open:rotate-90">▸</span>
          查看骨架映射关系
          <span className="ml-1 text-[10px] text-slate-400">（右侧边界可拖动调整）</span>
        </summary>

        <div className="mt-3">
          {/* Column headers */}
          <div
            style={{
              display:             'grid',
              gridTemplateColumns: `1fr ${ARROW_W}px 1fr`,
              marginBottom:        8,
              textAlign:           'center',
              fontSize:            10,
              fontWeight:          500,
              color:               '#94a3b8',
            }}
          >
            <span>爆款骨架</span>
            <span />
            <span>新视频</span>
          </div>

          <SkeletonMap sourceSlots={sourceSlots} migratedSlots={migratedSlots} />
        </div>
      </details>

      {/* Applied rules */}
      {migration.applied_rules?.length > 0 && (
        <div className="mt-3 rounded-xl bg-slate-50 px-3 py-2.5">
          <div className="text-[11px] leading-relaxed text-slate-600">
            <span className="font-semibold text-slate-700">套用的骨架规则：</span>
            {migration.applied_rules.join(' · ')}
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
