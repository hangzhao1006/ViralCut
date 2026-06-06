import { useRef, useEffect } from 'react';
import type { VideoStructure } from '../../types';
import { getCurrentSegment } from '../../lib/timeline';
import { ENERGY_COLORS } from '../../lib/colors';

interface Props {
  videoUrl: string;
  structure: VideoStructure;
  currentTime: number;
  onTimeUpdate: (t: number) => void;
  seekTo: number | null;
}

export default function VideoPlayer({ videoUrl, structure, currentTime, onTimeUpdate, seekTo }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    if (seekTo !== null && videoRef.current) {
      videoRef.current.currentTime = seekTo;
    }
  }, [seekTo]);

  const segments = structure.script_structure?.segments ?? [];
  const energyCurve = structure.energy_curve?.energy_curve ?? [];
  const duration = structure.duration || 1;

  const currentSeg = getCurrentSegment(currentTime, segments);
  const currentEnergy = getCurrentSegment(currentTime, energyCurve);

  return (
    <div className="relative overflow-hidden rounded-[1.75rem] bg-slate-950 p-2 shadow-[0_24px_60px_rgba(15,23,42,0.22)] ring-1 ring-slate-900/10">
      <div className="absolute inset-x-10 top-0 h-24 rounded-full bg-indigo-500/20 blur-3xl" />
      <div className="relative aspect-video overflow-hidden rounded-2xl bg-black">
        <video
          ref={videoRef}
          src={videoUrl}
          controls
          className="h-full w-full object-contain"
          onTimeUpdate={(e) => onTimeUpdate(e.currentTarget.currentTime)}
        />

        {currentSeg && (
          <div className="pointer-events-none absolute left-3 top-3 rounded-full border border-white/10 bg-black/65 px-3 py-1.5 text-xs font-medium text-white shadow-lg backdrop-blur-md">
            {currentSeg.segment_id} · {currentSeg.function} · {currentSeg.start_time.toFixed(0)}-{currentSeg.end_time.toFixed(0)}s
          </div>
        )}

        {currentEnergy && (
          <div
            className="pointer-events-none absolute right-3 top-3 rounded-full px-3 py-1.5 text-xs font-semibold text-white shadow-lg"
            style={{ background: ENERGY_COLORS[currentEnergy.energy_level] ?? '#888' }}
          >
            能量: {currentEnergy.energy_level}
          </div>
        )}

        <div className="pointer-events-none absolute bottom-0 left-0 right-0 flex h-1.5 overflow-hidden">
          {energyCurve.map((e) => {
            const segDur = e.time_range[1] - e.time_range[0];
            return (
              <div
                key={e.segment_id}
                style={{
                  flex: segDur,
                  background: ENERGY_COLORS[e.energy_level] ?? '#888',
                }}
              />
            );
          })}
        </div>

        <div
          className="pointer-events-none absolute bottom-0 h-3 w-0.5 bg-white shadow-[0_0_0_1px_rgba(0,0,0,0.25)]"
          style={{ left: `${(currentTime / duration) * 100}%` }}
        />
      </div>
    </div>
  );
}
