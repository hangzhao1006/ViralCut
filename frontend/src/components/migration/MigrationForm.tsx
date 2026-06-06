import { useState } from 'react';
import type { TransferBlueprint } from '../../types';
import type { AnalyzedAsset } from '../AssetLibrary';

interface Props {
  blueprint: TransferBlueprint;
  assets: AnalyzedAsset[];
  loading: boolean;
  onMigrate: (newContent: Record<string, unknown>) => void;
}

export default function MigrationForm({ blueprint, assets, loading, onMigrate }: Props) {
  const [topic, setTopic] = useState('');
  const [targetType, setTargetType] = useState('');
  const [points, setPoints] = useState('');

  const adaptationKeys = Object.keys(blueprint.adaptation_guidance ?? {});

  function submit() {
    onMigrate({
      topic,
      target_type: targetType || adaptationKeys[0]?.replace('for_', '') || 'general',
      selling_points: points.split(/[,，]/).map((p) => p.trim()).filter(Boolean),
      description: '',
    });
  }

  return (
    <div className="p-4">
      <div className="mb-3 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-indigo-400">
        <span className="h-1.5 w-1.5 rounded-full bg-indigo-400" /> Generate
      </div>
      <div className="mb-3 text-sm font-semibold text-slate-900">生成新视频</div>

      <div className="space-y-3">
        <div>
          <label className="mb-1 block text-[11px] font-medium text-slate-500">主题</label>
          <input value={topic} onChange={(e) => setTopic(e.target.value)}
            placeholder="例：便携咖啡机推广"
            className="h-9 w-full rounded-xl border border-slate-200 bg-white px-3 text-xs text-slate-800 outline-none transition focus:border-indigo-300 focus:ring-4 focus:ring-indigo-100" />
        </div>

        <div>
          <label className="mb-1 block text-[11px] font-medium text-slate-500">迁移目标类型</label>
          <select value={targetType} onChange={(e) => setTargetType(e.target.value)}
            className="h-9 w-full appearance-none rounded-xl border border-slate-200 bg-white px-3 text-xs text-slate-800 outline-none transition focus:border-indigo-300 focus:ring-4 focus:ring-indigo-100">
            <option value="">自动选择</option>
            {adaptationKeys.map((k) => (
              <option key={k} value={k.replace('for_', '')}>{k.replace('for_', '')}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="mb-1 block text-[11px] font-medium text-slate-500">卖点（逗号分隔）</label>
          <input value={points} onChange={(e) => setPoints(e.target.value)}
            placeholder="一键萃取, 静音, 小巧"
            className="h-9 w-full rounded-xl border border-slate-200 bg-white px-3 text-xs text-slate-800 outline-none transition focus:border-indigo-300 focus:ring-4 focus:ring-indigo-100" />
        </div>

        {assets.length === 0 && (
          <div className="rounded-xl bg-slate-50 px-3 py-2 text-[11px] leading-relaxed text-slate-500">
            还没上传素材，可直接迁移，系统会给出缺口和拍摄指引。
          </div>
        )}

        <button onClick={submit} disabled={!topic || loading}
          className="h-10 w-full rounded-xl bg-indigo-600 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-40">
          {loading ? '迁移中...' : '生成新视频'}
        </button>
      </div>
    </div>
  );
}
