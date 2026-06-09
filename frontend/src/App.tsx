import { useState, useEffect, useRef } from 'react';
import type { AnalysisResult, MigrationResult, MigratedSlot, TransferBlueprint } from './types';
import * as api from './lib/api';
import type { TaskStatus } from './lib/api';
import VideoPlayer from './components/analysis/VideoPlayer';
import AgentPanel from './components/analysis/AgentPanel';
import MultiTrackTimeline from './components/analysis/MultiTrackTimeline';
import AgentProgress from './components/analysis/AgentProgress';
import Stage2LoadingView from './components/analysis/Stage2LoadingView';
import AssetLibrary from './components/AssetLibrary';
import type { AnalyzedAsset } from './components/AssetLibrary';
import MigrationForm from './components/migration/MigrationForm';
import MigrationPreview from './components/migration/MigrationPreview';
import MigrationProgress from './components/migration/MigrationProgress';
import DataInspector from './components/DataInspector';
import LeoAgentGrid from './components/LeoAgentGrid';
import { extractPartialSlots } from './lib/streamParse';

export default function App() {
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [seekTo, setSeekTo] = useState<number | null>(null);
  const [assets, setAssets] = useState<AnalyzedAsset[]>([]);
  const [migration, setMigration] = useState<MigrationResult | null>(null);
  const [migrating, setMigrating] = useState(false);
  const [streamText, setStreamText] = useState('');
  const [lastContent, setLastContent] = useState<Record<string, unknown>>({});
  const [bottomView, setBottomView] = useState<'analysis' | 'migration' | 'data'>('analysis');
  const [samples, setSamples] = useState<string[]>([]);
  const [linkUrl, setLinkUrl] = useState('');
  const [taskStatus, setTaskStatus] = useState<TaskStatus | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [loadingVideoUrl, setLoadingVideoUrl] = useState('');
  const startRef = useRef<number>(0);

  useEffect(() => {
    api.listSamples().then((r) => setSamples(r.samples ?? [])).catch(() => {});
  }, []);

  const analyzing = taskStatus?.status === 'processing';

  useEffect(() => {
    if (!analyzing) return;
    const t = setInterval(() => setElapsed(Math.floor((Date.now() - startRef.current) / 1000)), 1000);
    return () => clearInterval(t);
  }, [analyzing]);

  async function loadSample(videoId: string) {
    const result = await api.getSample(videoId);
    setAnalysis(result);
    setMigration(null);
    setBottomView('analysis');
    setTaskStatus(null);
  }

  async function handleUpload(file: File) {
    startRef.current = Date.now();
    setElapsed(0);
    setAnalysis(null);
    setTaskStatus({ task_id: '', status: 'processing', stage: 'stage1', message: '上传中...' });
    const { task_id } = await api.uploadAndAnalyze(file, 'both', true);
    pollTask(task_id);
  }

  async function handleAnalyzeLink(url: string) {
    if (!url.trim()) return;
    startRef.current = Date.now();
    setElapsed(0);
    setAnalysis(null);
    setTaskStatus({ task_id: '', status: 'processing', stage: 'stage1', message: '下载链接视频中...' });
    const { task_id } = await api.analyzeLink(url.trim(), 'both', true);
    pollTask(task_id);
  }

  function pollTask(task_id: string) {
    const poll = setInterval(async () => {
      const status = await api.getStatus(task_id);
      setTaskStatus(status);

      if (status.status === 'done') {
        clearInterval(poll);
        setAnalysis(await api.getResult(task_id));
      } else if (status.status === 'stage1_done') {
        clearInterval(poll);
        const preview = await api.getResult(task_id);
        if (preview && !preview.error) setAnalysis(preview);
      } else if (status.status === 'processing' && status.has_leo_result) {
        // Leo done, main still running — fetch partial result and keep polling
        try {
          const partial = await api.getResult(task_id);
          if (partial && partial.synthesis_result) setAnalysis(partial);
        } catch { /* keep polling */ }
      } else if (status.status === 'failed') {
        clearInterval(poll);
        if (status.stage1_available && status.video_id) {
          try {
            const partial = await api.getResult(task_id);
            if (partial && !partial.error) setAnalysis(partial);
          } catch { /* show failure banner */ }
        }
      }
    }, 2000);
  }

  function handleContinueStage2() {
    const vid = analysis?.video_id;
    if (!vid) return;
    setLoadingVideoUrl(analysis?.video_url ?? '');
    startRef.current = Date.now();
    setElapsed(0);
    setMigration(null);
    setAnalysis(null);
    setTaskStatus({ task_id: '', status: 'processing', stage: 'stage2', message: '开始完整分析...' });
    api.restage2(vid, 'both').then(({ task_id }) => pollTask(task_id));
  }

  async function handleMigrate(newContent: Record<string, unknown>) {
    if (!analysis) return;
    setMigrating(true);
    setStreamText('');
    setMigration(null);
    setBottomView('migration');
    const userAssets = {
      videos: assets.filter((a) => a.type === 'video'),
      images: assets.filter((a) => a.type === 'image'),
      texts: [],
      has_bgm: false,
    };
    setLastContent({ newContent, userAssets });
    try {
      await api.migrateStream(
        analysis.video_id,
        newContent,
        userAssets,
        (chunk) => setStreamText((prev) => prev + chunk),
        (result) => {
          if (result && result.migrated_slots?.length) {
            setMigration(result);
          } else {
            alert('迁移解析失败，请看后端日志');
          }
        },
      );
    } catch (e) {
      alert('迁移出错: ' + String(e));
    } finally {
      setMigrating(false);
    }
  }

  function doSeek(t: number) {
    setSeekTo(t);
    setTimeout(() => setSeekTo(null), 100);
  }

  function handleSlotUpdate(idx: number, updated: MigratedSlot) {
    if (!migration) return;
    const slots = [...migration.migrated_slots];
    slots[idx] = updated;
    setMigration({ ...migration, migrated_slots: slots });
  }

  async function handleSlotRegenerate(idx: number, instruction: string, forceStrategy: string) {
    if (!migration || !analysis) return;
    const current = migration.migrated_slots[idx];
    const ctx = lastContent as { newContent?: Record<string, unknown>; userAssets?: Record<string, unknown> };
    const result = await api.migrateSlot(
      analysis.video_id, idx, current as unknown as Record<string, unknown>,
      ctx.newContent ?? {}, ctx.userAssets ?? {}, instruction, forceStrategy,
    );
    if ((result as { error?: string }).error) {
      alert('重新生成失败: ' + (result as { error?: string }).error);
      return;
    }
    handleSlotUpdate(idx, result as unknown as MigratedSlot);
  }

  function downloadJson(data: unknown, filename: string) {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
  }

  function handleExport() {
    if (!analysis) return;
    if (analysis.video_structure) downloadJson(analysis.video_structure, `${analysis.video_id}_video_structure.json`);
    if (analysis.synthesis_result) downloadJson(analysis.synthesis_result, `${analysis.video_id}_synthesis.json`);
    if (migration) downloadJson(migration, `${analysis.video_id}_migration_result.json`);
  }

  function handleReuseUpload(file: File) {
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const data = JSON.parse(reader.result as string);
        if (data.video_structure || data.synthesis_result) {
          setAnalysis(data as AnalysisResult);
        } else if (data.transfer_blueprint || data.script_structure) {
          setAnalysis({ video_id: data.video_id ?? 'uploaded', video_url: '', video_structure: data, evidence_package: null });
        }
        setMigration(null);
        setBottomView('analysis');
        setTaskStatus(null);
      } catch {
        alert('JSON 解析失败，请上传分析结果文件');
      }
    };
    reader.readAsText(file);
  }

  const structure = analysis?.video_structure;
  const tb = structure?.transfer_blueprint as
    | { transfer_blueprint?: TransferBlueprint; structure_template?: unknown } | undefined;
  const blueprint: TransferBlueprint | undefined =
    tb?.transfer_blueprint?.structure_template ? tb.transfer_blueprint
    : (tb as TransferBlueprint | undefined)?.structure_template ? (tb as TransferBlueprint)
    : undefined;

  // Leo is available whenever synthesis_result exists (whether main is done or still loading)
  const leoReady = !!analysis?.synthesis_result;
  const mainReady = !!analysis?.video_structure;
  // Main is still loading when leo is done but main isn't
  const mainStillLoading = !!analysis?.main_loading || (analyzing && !!taskStatus?.has_leo_result);

  return (
    <div className="min-h-screen text-slate-900">
      <div className="mx-auto max-w-[1440px] px-4 py-4 sm:px-6 lg:px-8">

        {/* Top bar */}
        <div className="mb-4 flex flex-col gap-4 rounded-3xl border border-white/70 bg-white/75 px-5 py-4 shadow-[0_18px_48px_rgba(15,23,42,0.08)] backdrop-blur">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-slate-950 text-sm font-semibold text-white shadow-lg shadow-slate-900/20">VC</div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[15px] font-semibold tracking-tight text-slate-950">{analysis ? analysis.video_id : 'ViralCut'}</span>
                {structure?.evaluation && (
                  <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700">
                    已分析 · {structure.evaluation.score}分
                  </span>
                )}
              </div>
              <div className="mt-0.5 text-[11px] text-slate-500">爆款视频结构迁移引擎 · Evidence-based multi-agent workflow</div>
            </div>
          </div>
          <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3 border-t border-slate-200/70 pt-3">
            <div className="flex flex-col gap-1">
              <span className="vc-kicker">① 分析新视频</span>
              <div className="flex items-center gap-3">
                <label className="vc-button cursor-pointer">
                  上传视频
                  <input type="file" accept="video/*" className="hidden"
                    onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0])} />
                </label>
                <span className="text-[11px] text-slate-400">或</span>
                <div className="flex items-center gap-1">
                  <input
                    value={linkUrl}
                    onChange={(e) => setLinkUrl(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleAnalyzeLink(linkUrl)}
                    placeholder="粘贴视频链接"
                    className="h-[34px] w-40 rounded-xl border border-slate-200 bg-white px-3 text-xs text-slate-700 outline-none transition focus:border-indigo-300 focus:ring-4 focus:ring-indigo-100"
                  />
                  <button onClick={() => handleAnalyzeLink(linkUrl)} className="vc-button">分析链接</button>
                </div>
              </div>
            </div>
            <div className="h-9 w-px self-end bg-slate-200" />
            <div className="flex flex-col gap-1">
              <span className="vc-kicker">② 加载已有</span>
              <div className="flex items-center gap-2">
                {samples.length > 0 && (
                  <select onChange={(e) => e.target.value && loadSample(e.target.value)}
                    className="vc-button h-[34px] cursor-pointer appearance-none pr-8" defaultValue="">
                    <option value="">样例</option>
                    {samples.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                )}
                <label className="vc-button cursor-pointer">
                  复用结果
                  <input type="file" accept="application/json,.json" className="hidden"
                    onChange={(e) => e.target.files?.[0] && handleReuseUpload(e.target.files[0])} />
                </label>
              </div>
            </div>
            <div className="h-9 w-px self-end bg-slate-200" />
            <div className="flex flex-col gap-1">
              <span className="vc-kicker">③ 导出</span>
              <button disabled={!analysis} onClick={handleExport} className="vc-button">导出结果</button>
            </div>
          </div>
        </div>

        {/* Progress banner */}
        {taskStatus && (analyzing || taskStatus.status === 'failed') && (
          taskStatus.status === 'failed' ? (
            <div className="mb-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700 shadow-sm">
              分析失败: {taskStatus.message}
            </div>
          ) : taskStatus.stage === 'stage2' ? (
            <Stage2LoadingView
              status={taskStatus}
              elapsed={elapsed}
              videoUrl={loadingVideoUrl || analysis?.video_url || ''}
              synthesis={analysis?.synthesis_result ?? null}
            />
          ) : (
            <AgentProgress status={taskStatus} elapsed={elapsed} />
          )
        )}

        {/* Empty state */}
        {!analysis && !analyzing && (
          <div className="vc-card flex min-h-[520px] flex-col items-center justify-center rounded-[2rem] px-6 py-24 text-center">
            <div className="mb-5 flex h-16 w-16 items-center justify-center rounded-3xl bg-slate-950 text-2xl text-white shadow-xl shadow-slate-900/20">▶</div>
            <div className="text-lg font-semibold tracking-tight text-slate-900">开始一次结构拆解</div>
            <div className="mt-2 max-w-md text-sm leading-6 text-slate-500">上传爆款视频或选择样例，同时跑结构分析（6 Agent）和爆款归因（6 视角）。</div>
          </div>
        )}

        {/* Stage 1 done — awaiting confirmation */}
        {analysis && !mainReady && !leoReady && analysis.evidence_package && analysis.stage1_only && (() => {
          const ev = analysis.evidence_package as Record<string, any>;
          const meta = ev.metadata ?? {};
          const basic = ev.basic_analysis ?? {};
          const beats = ev.beats ?? {};
          const facts: [string, string][] = [
            ['时长', meta.duration ? `${Number(meta.duration).toFixed(1)}s` : '—'],
            ['镜头数', String(basic.shot_count ?? (ev.scenes?.length ?? '—'))],
            ['字幕段', String(ev.transcript?.length ?? 0)],
            ['BPM', beats.bpm ? Number(beats.bpm).toFixed(1) : '—'],
            ['节奏', String(basic.estimated_pace ?? '—')],
            ['字幕密度', String(basic.subtitle_density ?? '—')],
          ];
          return (
            <div className="vc-card overflow-hidden rounded-[2rem] p-5">
              {analysis.stage2_failed && (
                <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2.5 text-[12px] text-red-700">
                  Stage 2 分析失败，但 Stage 1 证据已成功提取。<br />
                  <span className="text-red-500">{analysis.error}</span>
                </div>
              )}
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#e0e0e0] bg-[#f5f5f7] px-4 py-3">
                <div className="text-[12px] text-[#6e6e73]">
                  Stage 1 完成 · 确认后同时运行爆款归因（并行）和结构分析（串行）
                </div>
                <button onClick={handleContinueStage2} className="vc-button vc-button-primary">
                  进入 Stage 2 →
                </button>
              </div>
              <div className="grid grid-cols-[minmax(0,1fr)_360px] gap-5">
                <div className="flex items-center justify-center rounded-2xl bg-slate-50 p-5">
                  <video src={analysis.video_url} controls className="w-full max-w-[560px] rounded-xl" />
                </div>
                <div className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm">
                  <div className="mb-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">Stage 1 提取结果</div>
                  <div className="grid grid-cols-2 gap-3">
                    {facts.map(([k, v]) => (
                      <div key={k} className="rounded-xl bg-slate-50 px-3 py-2.5">
                        <div className="text-[11px] text-slate-400">{k}</div>
                        <div className="text-sm font-semibold text-slate-900">{v}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          );
        })()}

        {/* Leo done, main still loading — show synthesis + main progress (only when not in active stage2 loading view) */}
        {leoReady && !mainReady && mainStillLoading && taskStatus?.stage !== 'stage2' && (
          <div className="vc-card overflow-hidden rounded-[2rem]">
            <div className="p-5">
              <video src={analysis?.video_url} controls className="w-full max-w-[560px] rounded-xl" />
            </div>
            <LeoAgentGrid synthesis={analysis!.synthesis_result!} isLoading={false} />
          </div>
        )}

        {/* Unified workspace — main result ready (+ optional leo at bottom) */}
        {mainReady && structure && (
          <div className="vc-card overflow-hidden rounded-[2rem]">
            {/* 3-column workspace */}
            <div className="grid min-h-[520px] grid-cols-[300px_minmax(0,1fr)_320px] bg-white">
              {/* Left: asset library + migration form */}
              <div className="flex flex-col border-r border-slate-200/80 bg-slate-50/60">
                <div className="border-b border-slate-200/80">
                  <AssetLibrary assets={assets}
                    onAssetsAdded={(a) => setAssets((prev) => [...prev, ...a])}
                    onRemove={(id) => setAssets((prev) => prev.filter((x) => x.id !== id))} />
                </div>
                {blueprint ? (
                  <MigrationForm blueprint={blueprint} assets={assets} loading={migrating} onMigrate={handleMigrate} />
                ) : (
                  <div className="p-4 text-[11px] leading-relaxed text-slate-400">
                    未检测到迁移蓝图，Transfer agent 可能未完成。
                  </div>
                )}
              </div>

              {/* Center: video */}
              <div className="flex items-center justify-center bg-[radial-gradient(circle_at_50%_20%,rgba(79,70,229,0.08),transparent_34%),#f8fafc] p-5">
                <div className="w-full max-w-[560px]">
                  <VideoPlayer videoUrl={analysis!.video_url} structure={structure}
                    currentTime={currentTime} onTimeUpdate={setCurrentTime} seekTo={seekTo} />
                </div>
              </div>

              {/* Right: agent panel */}
              <div className="border-l border-slate-200/80 bg-white p-4">
                <div className="mb-3 flex items-center justify-between">
                  <div>
                    <div className="vc-kicker">Inspector</div>
                    <div className="mt-1 text-sm font-semibold text-slate-900">当前片段分析</div>
                  </div>
                  <div className="rounded-full bg-slate-100 px-2 py-1 text-[11px] font-medium text-slate-500">
                    {currentTime.toFixed(1)}s
                  </div>
                </div>
                <AgentPanel structure={structure} currentTime={currentTime} />
              </div>
            </div>

            {/* Bottom tabs */}
            <div className="border-t border-slate-200/80 bg-white p-4">
              <div className="mb-3 flex items-center gap-2 rounded-2xl bg-slate-100/70 p-1">
                <button onClick={() => setBottomView('analysis')}
                  className={`rounded-xl px-3 py-1.5 text-xs font-medium transition ${bottomView === 'analysis' ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-500 hover:text-slate-800'}`}>
                  分析时间线
                </button>
                <button onClick={() => setBottomView('data')}
                  className={`rounded-xl px-3 py-1.5 text-xs font-medium transition ${bottomView === 'data' ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-500 hover:text-slate-800'}`}>
                  数据详情
                </button>
                {(migration || migrating || streamText) && (
                  <button onClick={() => setBottomView('migration')}
                    className={`rounded-xl px-3 py-1.5 text-xs font-medium transition ${bottomView === 'migration' ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-500 hover:text-slate-800'}`}>
                    迁移预览
                  </button>
                )}
              </div>
              {bottomView === 'analysis' && (
                <MultiTrackTimeline structure={structure} evidence={analysis!.evidence_package}
                  currentTime={currentTime} onSeek={doSeek} />
              )}
              {bottomView === 'data' && (
                <DataInspector structure={structure} evidence={analysis!.evidence_package} />
              )}
              {bottomView === 'migration' && (
                migration && blueprint ? (
                  <MigrationPreview blueprint={blueprint} migration={migration}
                    onSlotUpdate={handleSlotUpdate} onSlotRegenerate={handleSlotRegenerate} />
                ) : (migrating || streamText) && blueprint ? (
                  <MigrationProgress blueprint={blueprint} parsedSlots={extractPartialSlots(streamText)} done={!migrating} />
                ) : (
                  <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 py-12 text-center text-sm text-slate-400">
                    在左栏填写主题后点击"生成新视频"
                  </div>
                )
              )}
            </div>

            {/* Leo agent grid — always at the very bottom */}
            <LeoAgentGrid
              synthesis={analysis?.synthesis_result ?? null}
              isLoading={!leoReady}
            />
          </div>
        )}
      </div>
    </div>
  );
}
