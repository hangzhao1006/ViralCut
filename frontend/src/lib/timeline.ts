import type { Segment, SegmentRhythm, EnergyPoint } from '../types';

export function getCurrentSegment<T extends { start_time?: number; end_time?: number; time_range?: [number, number] }>(
  currentTime: number,
  items: T[],
): T | undefined {
  return items.find((item) => {
    const start = item.start_time ?? item.time_range?.[0] ?? 0;
    const end = item.end_time ?? item.time_range?.[1] ?? 0;
    return currentTime >= start && currentTime < end;
  });
}

export function getSegmentStart(s: Segment | SegmentRhythm | EnergyPoint): number {
  if ('start_time' in s) return s.start_time;
  if ('time_range' in s) return s.time_range[0];
  return 0;
}

export function getSegmentEnd(s: Segment | SegmentRhythm | EnergyPoint): number {
  if ('end_time' in s) return s.end_time;
  if ('time_range' in s) return s.time_range[1];
  return 0;
}

export function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}
