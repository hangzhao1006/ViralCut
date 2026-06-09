import { useState, useEffect } from 'react';
import type { TaskStatus } from '../../lib/api';
import type { SynthesisResult } from '../../types';
import LeoAgentGrid from '../LeoAgentGrid';

const AGENTS = [
  { key: 'script',    label: 'Script',    desc: '脚本结构', color: '#4F46E5' },
  { key: 'rhythm',    label: 'Rhythm',    desc: '节奏分析', color: '#818CF8' },
  { key: 'packaging', label: 'Packaging', desc: '视觉包装', color: '#6366F1' },
  { key: 'value',     label: 'Value',     desc: '价值主张', color: '#312E81' },
  { key: 'energy',    label: 'Energy',    desc: '能量曲线', color: '#4338CA' },
  { key: 'transfer',  label: 'Transfer',  desc: '迁移蓝图', color: '#3730A3' },
];

const THINKING_PHRASES: Record<string, string[]> = {
  script: [
    '分析视频脚本结构…',
    '检测开场钩子类型…',
    '识别核心叙事段落…',
    '标注内容转折节点…',
    '评估 CTA 行动号召…',
    '整合脚本分析结果…',
  ],
  rhythm: [
    '检测音乐卡点节拍…',
    '测量镜头切换频率…',
    '计算平均镜头时长…',
    '映射节奏驱动因子…',
    '生成节奏分布报告…',
    '标注高节奏密度区间…',
  ],
  packaging: [
    '分析视觉包装风格…',
    '识别字幕设计规律…',
    '检测转场动效模式…',
    '评估画面构图逻辑…',
    '提取视觉吸引元素…',
    '汇总包装策略特征…',
  ],
  value: [
    '识别核心价值主张…',
    '分析受众定位策略…',
    '评估情感共鸣强度…',
    '检测社会证明元素…',
    '提炼内容价值密度…',
    '整合价值层次分析…',
  ],
  energy: [
    '绘制注意力能量曲线…',
    '标记能量峰值节点…',
    '分析高潮前置铺垫…',
    '评估开篇吸引力强度…',
    '计算能量分布特征…',
    '输出能量曲线报告…',
  ],
  transfer: [
    '提炼可迁移结构模板…',
    '识别爆款关键变量…',
    '生成内容迁移蓝图…',
    '评估模板适用范围…',
    '编写迁移指导方案…',
    '完成迁移蓝图输出…',
  ],
};

const PAUSE_TICKS = 18;

function getDisplayedText(tick: number, agentKey: string, agentIdx: number): string {
  const phrases = THINKING_PHRASES[agentKey];
  const offset = agentIdx * 28;
  const t = Math.max(0, tick - offset);

  let remaining = t;
  let phraseIdx = 0;

  for (;;) {
    const phrase = phrases[phraseIdx % phrases.length];
    const duration = phrase.length + PAUSE_TICKS;
    if (remaining < duration) {
      return phrase.slice(0, Math.min(remaining, phrase.length));
    }
    remaining -= duration;
    phraseIdx++;
  }
}

const PLACEHOLDER_CARDS = [
  { name: '这段在做什么', badge: 'Script', color: '#4F46E5' },
  { name: '节奏',        badge: 'Rhythm',  color: '#818CF8' },
  { name: '价值类型',    badge: 'Value',   color: '#6366F1' },
  { name: '注意力强度',  badge: 'Energy',  color: '#312E81' },
];

const MONO: React.CSSProperties = {
  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
};

interface Props {
  status: TaskStatus;
  elapsed: number;
  videoUrl: string;
  synthesis: SynthesisResult | null;
}

export default function Stage2LoadingView({ status, elapsed, videoUrl, synthesis }: Props) {
  const completed = ((status as Record<string, unknown>).completed_agents as string[] | undefined) ?? [];
  const current = status.current_step ?? '';
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const iv = setInterval(() => setTick((t) => t + 1), 55);
    return () => clearInterval(iv);
  }, []);

  const mins = Math.floor(elapsed / 60);
  const secs = elapsed % 60;
  const completedCount = completed.length;
  const leoReady = synthesis !== null;

  return (
    <div className="vc-card mb-4 overflow-hidden rounded-[2rem]">
      {/* Progress bar */}
      <div style={{ height: 3, background: '#eeeeee' }}>
        <div style={{
          height: 3,
          background: 'linear-gradient(90deg, #6366f1, #818cf8)',
          width: `${Math.min(95, 10 + (leoReady ? 50 : 0) + (completedCount / 6) * 45)}%`,
          transition: 'width 1.5s ease',
          borderRadius: 2,
        }} />
      </div>

      {/* Header */}
      <div style={{
        padding: '10px 20px',
        borderBottom: '1px solid #eeeeee',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: '#fff',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ ...MONO, fontSize: 11, fontWeight: 600, color: '#6366f1' }}>
            ◐ Stage 2 — {leoReady ? '结构分析' : '爆款归因'}
          </span>
          <span style={{ fontSize: 10, color: '#aeaeb2' }}>
            · {leoReady ? `${completedCount}/6 Agent 完成` : '6 个视角并行分析中'}
          </span>
          {current && leoReady && (
            <span style={{
              ...MONO, fontSize: 9, color: '#6366f1',
              background: 'rgba(99,102,241,0.08)',
              padding: '2px 7px', borderRadius: 6,
            }}>
              {current}
            </span>
          )}
        </div>
        <span style={{ ...MONO, fontSize: 10, color: '#aeaeb2' }}>
          {mins}:{secs.toString().padStart(2, '0')}
        </span>
      </div>

      {/* 3-column workspace */}
      <div className="grid min-h-[520px] grid-cols-[300px_minmax(0,1fr)_320px] bg-white">

        {/* Left: 6 agents vertically */}
        <div className="flex flex-col border-r border-slate-200/80 bg-slate-50/60 overflow-y-auto">
          <div style={{
            padding: '12px 12px 6px',
            ...MONO,
            fontSize: 9, fontWeight: 600,
            letterSpacing: '0.14em',
            color: '#aeaeb2',
            textTransform: 'uppercase' as const,
          }}>
            结构 Agent
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: '0 10px 12px' }}>
            {AGENTS.map((agent, idx) => {
              const isDone = completed.includes(agent.key);
              const isActive = !isDone && current === agent.key && leoReady;
              const isWaiting = leoReady && !isDone && !isActive && !!current;
              const text = isDone
                ? '分析完成'
                : getDisplayedText(tick, agent.key, idx);

              return (
                <div key={agent.key} style={{
                  borderRadius: 12,
                  border: `1px solid ${isActive ? '#6366f1' : isDone ? '#d1fae5' : '#e5e7eb'}`,
                  background: isActive
                    ? 'rgba(99,102,241,0.04)'
                    : isDone ? '#f0fdf4' : '#fff',
                  padding: '9px 12px',
                  opacity: isWaiting ? 0.35 : 1,
                  transition: 'opacity 0.3s, border-color 0.3s, background 0.3s',
                }}>
                  {/* Agent header row */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 5 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <div style={{
                        width: 5, height: 5, borderRadius: '50%',
                        background: isDone ? '#34c759' : isActive ? '#6366f1' : '#d1d5db',
                        flexShrink: 0,
                        transition: 'background 0.3s',
                      }} />
                      <span style={{ ...MONO, fontSize: 12, fontWeight: 600, color: '#1d1d1f' }}>
                        {agent.label}
                      </span>
                      <span style={{ fontSize: 9, color: '#aeaeb2' }}>{agent.desc}</span>
                    </div>
                    <span style={{ fontSize: 11, color: isDone ? '#34c759' : isActive ? '#6366f1' : '#d1d5db' }}>
                      {isDone ? '✓' : isActive ? '◐' : '○'}
                    </span>
                  </div>

                  {/* Streaming text */}
                  <div style={{
                    ...MONO,
                    fontSize: 10,
                    color: isDone ? '#34c759' : isActive ? '#4f46e5' : '#9ca3af',
                    lineHeight: 1.5,
                    minHeight: 15,
                    paddingLeft: 11,
                  }}>
                    {text}
                    {!isDone && (
                      <span style={{ animation: 'blink 1s step-end infinite' }}>▌</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Center: video — position:relative with no in-flow content so the
            grid row height is set by the side columns, not the video.
            The absolute inner div fills the cell; video letterboxes in black. */}
        <div style={{ position: 'relative', background: '#000' }}>
          <div style={{
            position: 'absolute', inset: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            {videoUrl ? (
              <video
                key={videoUrl}
                src={videoUrl}
                autoPlay
                loop
                muted
                playsInline
                style={{
                  maxWidth: '100%',
                  maxHeight: '100%',
                  display: 'block',
                  objectFit: 'contain',
                }}
              />
            ) : (
              <div style={{ color: '#555', fontSize: 12 }}>载入中…</div>
            )}
          </div>
        </div>

        {/* Right: 当前片段分析 placeholder */}
        <div className="border-l border-slate-200/80 bg-white p-4">
          <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div className="vc-kicker">Inspector</div>
              <div style={{ marginTop: 4, fontSize: 14, fontWeight: 600, color: '#0f172a' }}>
                当前片段分析
              </div>
            </div>
            <div style={{
              borderRadius: 999, background: '#f1f5f9',
              padding: '4px 8px', fontSize: 11, fontWeight: 500, color: '#94a3b8',
            }}>
              —
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {PLACEHOLDER_CARDS.map((c) => (
              <div key={c.name} style={{
                position: 'relative',
                overflow: 'hidden',
                borderRadius: 16,
                border: '1px solid rgba(226,232,240,0.8)',
                background: '#fff',
                padding: '12px 12px 12px 16px',
                boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
              }}>
                <div style={{
                  position: 'absolute', left: 0, top: 0, bottom: 0,
                  width: 4, background: c.color,
                }} />
                <div style={{
                  display: 'flex', alignItems: 'center',
                  justifyContent: 'space-between', marginBottom: 6,
                }}>
                  <div style={{ fontSize: 11, fontWeight: 500, color: '#94a3b8' }}>{c.name}</div>
                  <span style={{
                    borderRadius: 999, background: '#f1f5f9',
                    padding: '2px 7px', fontSize: 9, fontWeight: 600, color: '#94a3b8',
                  }}>
                    {c.badge}
                  </span>
                </div>
                <div style={{ fontSize: 15, fontWeight: 600, color: '#e2e8f0', marginBottom: 4 }}>
                  —
                </div>
                <div style={{ fontSize: 11, color: '#cbd5e1', lineHeight: 1.4 }}>
                  分析完成后显示
                </div>
              </div>
            ))}
          </div>
        </div>

      </div>

      {/* Leo agent grid — shows when Leo finishes, stays loading before */}
      <LeoAgentGrid synthesis={synthesis} isLoading={!leoReady} />
    </div>
  );
}
