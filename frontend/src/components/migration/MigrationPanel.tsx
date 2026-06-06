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
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/35 backdrop-blur-sm" onClick={onClose}>
      <div className="h-full w-[420px] overflow-y-auto border-l border-slate-200 bg-white p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-5 flex items-center justify-between">
          <h3 className="text-lg font-semibold tracking-tight text-slate-950">生成新视频</h3>
          <button onClick={onClose} className="flex h-8 w-8 items-center justify-center rounded-full text-slate-400 transition hover:bg-slate-100 hover:text-slate-700">✕</button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-500">主题</label>
            <input value={topic} onChange={(e) => setTopic(e.target.value)}
              placeholder="例：便携咖啡机产品推广"
              className="vc-field h-10" />
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-500">迁移目标类型</label>
            <select value={targetType} onChange={(e) => setTargetType(e.target.value)}
              className="vc-field h-10 bg-white">
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
              className="vc-field h-10" />
          </div>

          {/* Asset summary */}
          <div className="rounded-2xl border border-slate-200/70 bg-slate-50/80 p-3">
            <div className="mb-1 text-xs font-medium text-slate-600">已上传素材（已视觉分析）</div>
            {assets.length === 0 ? (
              <div className="text-xs text-slate-400">
                还没上传素材。可以直接迁移，系统会给出缺口和拍摄指引。
              </div>
            ) : (
              <div className="text-xs text-slate-600">
                {videoCount} 个视频 · {imageCount} 张图片
                <div className="mt-1 space-y-0.5">
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
            className="vc-button-primary h-11 w-full text-sm">
            {loading ? '迁移中...' : '开始迁移'}
          </button>
        </div>
      </div>
    </div>
  );
}
