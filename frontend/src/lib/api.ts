import type { AnalysisResult, MigrationResult } from '../types';

const API_BASE = '/api';

export async function uploadAndAnalyze(file: File, stage2Variant: string = 'main', pauseAfterStage1: boolean = false): Promise<{ task_id: string }> {
  const formData = new FormData();
  formData.append('video', file);
  formData.append('stage2_variant', stage2Variant);
  formData.append('pause_after_stage1', String(pauseAfterStage1));
  const res = await fetch(`${API_BASE}/analyze`, { method: 'POST', body: formData });
  return res.json();
}

export async function analyzeLink(url: string, stage2Variant: string = 'main', pauseAfterStage1: boolean = false): Promise<{ task_id: string }> {
  const res = await fetch(`${API_BASE}/analyze/link`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, stage2_variant: stage2Variant, pause_after_stage1: pauseAfterStage1 }),
  });
  return res.json();
}

export async function restage2(videoId: string, stage2Variant: string): Promise<{ task_id: string }> {
  const res = await fetch(`${API_BASE}/analyze/restage2`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ video_id: videoId, stage2_variant: stage2Variant }),
  });
  return res.json();
}

export interface TaskStatus {
  task_id: string;
  status: 'processing' | 'done' | 'failed' | 'not_found' | 'stage1_done';
  stage?: string;
  current_step?: string;
  message?: string;
  video_id?: string;
  log_tail?: string[];
  stage2_variant?: 'main' | 'leo';
  stage1_available?: boolean;
  stage1_steps?: Record<string, { state: 'waiting' | 'active' | 'done'; pct: number | null }>;
}

export async function getStatus(taskId: string): Promise<TaskStatus> {
  const res = await fetch(`${API_BASE}/analyze/${taskId}/status`);
  return res.json();
}

export async function getResult(taskId: string): Promise<AnalysisResult> {
  const res = await fetch(`${API_BASE}/analyze/${taskId}/result`);
  return res.json();
}

export async function listSamples(): Promise<{ samples: string[] }> {
  const res = await fetch(`${API_BASE}/samples`);
  return res.json();
}

export async function getSample(videoId: string): Promise<AnalysisResult> {
  const res = await fetch(`${API_BASE}/samples/${videoId}`);
  return res.json();
}

export async function uploadAssets(files: File[]): Promise<{ assets: { id: string; type: string; url: string }[] }> {
  const formData = new FormData();
  files.forEach((f) => formData.append('files', f));
  const res = await fetch(`${API_BASE}/assets/upload`, { method: 'POST', body: formData });
  return res.json();
}

export async function migrate(
  videoId: string,
  newContent: Record<string, unknown>,
  userAssets: Record<string, unknown>,
): Promise<MigrationResult> {
  const res = await fetch(`${API_BASE}/migrate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ video_id: videoId, new_content: newContent, user_assets: userAssets }),
  });
  return res.json();
}

export async function migrateStream(
  videoId: string,
  newContent: Record<string, unknown>,
  userAssets: Record<string, unknown>,
  onChunk: (text: string) => void,
  onDone: (result: MigrationResult) => void,
): Promise<void> {
  const res = await fetch(`${API_BASE}/migrate/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ video_id: videoId, new_content: newContent, user_assets: userAssets }),
  });
  if (!res.body) throw new Error('no stream body');
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n\n');
    buffer = lines.pop() ?? '';
    for (const line of lines) {
      const t = line.trim();
      if (!t.startsWith('data:')) continue;
      try {
        const obj = JSON.parse(t.slice(5).trim());
        if (obj.type === 'chunk') onChunk(obj.text);
        else if (obj.type === 'done') onDone(obj.result);
      } catch { /* ignore partial */ }
    }
  }
}

export async function migrateSlot(
  videoId: string,
  slotIndex: number,
  currentSlot: Record<string, unknown>,
  newContent: Record<string, unknown>,
  userAssets: Record<string, unknown>,
  instruction: string,
  forceStrategy: string,
): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE}/migrate/slot`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      video_id: videoId,
      slot_index: slotIndex,
      current_slot: currentSlot,
      new_content: newContent,
      user_assets: userAssets,
      instruction,
      force_strategy: forceStrategy,
    }),
  });
  return res.json();
}

export function staticUrl(path: string): string {
  return path.startsWith('http') ? path : path;
}