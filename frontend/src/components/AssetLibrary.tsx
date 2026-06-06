import { useState, useRef } from 'react';
import * as api from '../lib/api';

export interface AnalyzedAsset {
  id: string;
  type: string;
  url: string;
  description?: string;
  scene_type?: string;
  suitable_for?: string[];
}

interface Props {
  assets: AnalyzedAsset[];
  onAssetsAdded: (assets: AnalyzedAsset[]) => void;
  onRemove: (id: string) => void;
}

export default function AssetLibrary({ assets, onAssetsAdded, onRemove }: Props) {
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    setUploading(true);
    try {
      const res = await api.uploadAssets(Array.from(files));
      onAssetsAdded((res.assets ?? []) as AnalyzedAsset[]);
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <div className="vc-kicker">Assets</div>
          <div className="mt-1 text-sm font-semibold text-slate-900">素材库</div>
        </div>
        {assets.length > 0 && <span className="rounded-full bg-white px-2 py-1 text-[11px] font-medium text-slate-500 ring-1 ring-slate-200">{assets.length}</span>}
      </div>

      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files); }}
        className={`mb-4 cursor-pointer rounded-2xl border border-dashed p-4 text-center transition-all ${
          dragOver ? 'border-indigo-400 bg-indigo-50 shadow-sm ring-4 ring-indigo-100' : 'border-slate-300 bg-white hover:border-slate-400 hover:bg-slate-50'
        }`}
      >
        <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-2xl bg-slate-100 text-slate-500">↑</div>
        <div className="mt-2 text-[12px] font-medium text-slate-700">
          {uploading ? '视觉分析中...' : '拖入或点击上传'}
        </div>
        <div className="mt-1 text-[10px] text-slate-400">视频 / 图片素材</div>
        <input
          ref={inputRef}
          type="file"
          accept="video/*,image/*"
          multiple
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      <div className="grid grid-cols-2 gap-2">
        {assets.map((a) => (
          <div key={a.id} className="group relative aspect-square overflow-hidden rounded-2xl bg-slate-900 shadow-sm ring-1 ring-slate-900/5">
            {a.type === 'image' ? (
              <img src={a.url} alt={a.description} className="h-full w-full object-cover transition duration-300 group-hover:scale-105" />
            ) : (
              <video src={a.url} className="h-full w-full object-cover transition duration-300 group-hover:scale-105" />
            )}
            <div className="absolute inset-0 bg-gradient-to-t from-black/75 via-black/10 to-transparent" />
            <span className="absolute bottom-1.5 left-2 right-2 truncate text-[9px] font-medium text-white">
              {a.description || a.type}
            </span>
            {a.scene_type && (
              <span className="absolute left-1.5 top-1.5 rounded-full bg-white/85 px-1.5 py-0.5 text-[8px] font-semibold text-slate-800 backdrop-blur">
                {a.scene_type}
              </span>
            )}
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onRemove(a.id); }}
              className="absolute right-1.5 top-1.5 flex h-6 w-6 items-center justify-center rounded-full bg-black/55 text-[11px] text-white opacity-0 backdrop-blur transition hover:bg-rose-500 group-hover:opacity-100"
              title="删除素材"
              aria-label="删除素材"
            >
              ✕
            </button>
          </div>
        ))}
      </div>

      {assets.length > 0 && (
        <div className="mt-3 rounded-2xl bg-white px-3 py-2 text-[10px] text-slate-500 ring-1 ring-slate-200">
          视觉分析: {assets.filter((a) => a.type === 'video').length} 视频 ·{' '}
          {assets.filter((a) => a.type === 'image').length} 图片
        </div>
      )}
    </div>
  );
}