import { useState } from 'react';
import type { TransferBlueprint } from '../../types';
import type { AnalyzedAsset } from '../AssetLibrary';

interface Props {
  blueprint: TransferBlueprint;
  assets: AnalyzedAsset[];
  loading: boolean;
  onClose: () => void;
  onMigrate: (newContent: Record<string, unknown>) => void;
}

export default function MigrationPanel({ blueprint, assets, loading, onClose, onMigrate }: Props) {
  const [topic, setTopic] = useState('');
  const [targetType, setTargetType] = useState('');
  const [points, setPoints] = useState('');

  const adaptationKeys = Object.keys(blueprint.adaptation_guidance ?? {});
  const videoCount = assets.filter((a) => a.type === 'video').length;
  const imageCount = assets.filter((a) => a.type === 'image').length;

  function submit() {
    onMigrate({
      topic,
      target_type: targetType || adaptationKeys[0]?.replace('for_', '') || 'general',
      selling_points: points.split(/[,，]/).map((p) => p.trim()).filter(Boolean),
      description: '',
    });
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/40 backdrop-blur-sm" onClick={onClose}>
      <div
        className="h-full w-[400px] overflow-y-auto border-l border-slate-200/80 bg-white p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-5 flex items-center justify-between">
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-indigo-400">Generate</div>
            <h3 className="mt-0.5 text-lg font-semibold tracking-tight text-slate-900">生成新视频</h3>
          </div>
          <button onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 text-slate-400 transition hover:bg-slate-50 hover:text-slate-600">
            ✕
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-500">主题</label>
            <input value={topic} onChange={(e) => setTopic(e.target.value)}
              placeholder="例：便携咖啡机产品推广"
              className="h-10 w-full rounded-xl border border-slate-200 bg-slate-50/80 px-3 text-sm text-slate-800 outline-none transition focus:border-indigo-300 focus:bg-white focus:ring-4 focus:ring-indigo-100" />
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-500">迁移目标类型</label>
            <select value={targetType} onChange={(e) => setTargetType(e.target.value)}
              className="h-10 w-full appearance-none rounded-xl border border-slate-200 bg-slate-50/80 px-3 text-sm text-slate-800 outline-none transition focus:border-indigo-300 focus:bg-white focus:ring-4 focus:ring-indigo-100">
              <option value="">自动选择</option>
              {adaptationKeys.map((k) => (
                <option key={k} value={k.replace('for_', '')}>{k.replace('for_', '')}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-500">卖点（逗号分隔）</label>
            <input value={points} onChange={(e) => setPoints(e.target.value)}
              placeholder="一键萃取, 静音, 小巧"
              className="h-10 w-full rounded-xl border border-slate-200 bg-slate-50/80 px-3 text-sm text-slate-800 outline-none transition focus:border-indigo-300 focus:bg-white focus:ring-4 focus:ring-indigo-100" />
          </div>

          {/* Asset summary */}
          <div className="rounded-2xl border border-slate-200/80 bg-slate-50/60 p-3.5">
            <div className="mb-2 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
              <span className="h-1.5 w-1.5 rounded-full bg-slate-400" /> 已上传素材（已视觉分析）
            </div>
            {assets.length === 0 ? (
              <div className="text-xs leading-relaxed text-slate-500">
                还没上传素材。可以直接迁移，系统会给出缺口和拍摄指引。
              </div>
            ) : (
              <div className="text-xs text-slate-600">
                <div className="mb-1.5 flex gap-2">
                  <span className="rounded-full bg-white px-2 py-0.5 text-[11px] font-medium text-slate-600 ring-1 ring-slate-200">{videoCount} 视频</span>
                  <span className="rounded-full bg-white px-2 py-0.5 text-[11px] font-medium text-slate-600 ring-1 ring-slate-200">{imageCount} 图片</span>
                </div>
                <div className="space-y-1">
                  {assets.slice(0, 4).map((a) => (
                    <div key={a.id} className="truncate text-[11px] text-slate-500">
                      · {a.description || a.type} {a.scene_type ? `(${a.scene_type})` : ''}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <button onClick={submit} disabled={!topic || loading}
            className="h-11 w-full rounded-xl bg-indigo-600 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-40">
            {loading ? '迁移中...' : '开始迁移'}
          </button>
        </div>
      </div>
    </div>
  );
}
