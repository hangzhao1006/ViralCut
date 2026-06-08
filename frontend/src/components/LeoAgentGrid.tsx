import type { SynthesisResult, ClusteredDimension } from '../types';

const AGENTS = [
  { id: 0, name: '情感 Agent', char: '🌀' },
  { id: 1, name: '叙事 Agent', char: '🎯' },
  { id: 2, name: '社会 Agent', char: '🌊' },
  { id: 3, name: '信息 Agent', char: '⚡' },
  { id: 4, name: '制作 Agent', char: '🔷' },
  { id: 5, name: '行为 Agent', char: '🫧' },
];

const MONO: React.CSSProperties = {
  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
};

// Extract the first sentence from a mechanism string
function firstSentence(text: string): string {
  const cut = text.search(/[。！？]/);
  if (cut > 4 && cut < 72) return text.slice(0, cut + 1);
  return text.length > 65 ? text.slice(0, 65) + '…' : text;
}

// ── Ring avatar ────────────────────────────────────────────────────
function AgentRing({ char, done }: { char: string; done: boolean }) {
  const S = 72, r = 29;
  const circ = 2 * Math.PI * r;
  const arcLen = circ * 0.27;

  return (
    <div style={{ position: 'relative', width: S, height: S, flexShrink: 0 }}>
      <svg style={{ position: 'absolute', inset: 0 }} width={S} height={S}>
        <circle cx={S / 2} cy={S / 2} r={r} fill="none" stroke="#eeeeee" strokeWidth={3} />
      </svg>
      <svg
        className={!done ? 'animate-spin' : ''}
        style={{ position: 'absolute', inset: 0, ...(done ? {} : { animationDuration: '1.3s' }) }}
        width={S} height={S}
      >
        <circle
          cx={S / 2} cy={S / 2} r={r} fill="none"
          stroke={done ? '#34c759' : '#1d1d1f'} strokeWidth={3}
          strokeDasharray={done ? `${circ} 0` : `${arcLen} ${circ - arcLen}`}
          strokeLinecap="round"
          transform={`rotate(-90 ${S / 2} ${S / 2})`}
          style={{ transition: 'stroke 0.5s' }}
        />
      </svg>
      <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{
          width: 52, height: 52, borderRadius: '50%',
          border: '1px solid #e8e8e8', background: '#ffffff',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 22,
          opacity: done ? 1 : 0.3,
          transition: 'opacity 0.5s',
        }}>{char}</div>
      </div>
      {done && (
        <div style={{
          position: 'absolute', top: 1, right: 1,
          width: 17, height: 17, borderRadius: '50%',
          background: '#34c759',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 8, fontWeight: 700, color: '#fff',
        }}>✓</div>
      )}
    </div>
  );
}

// ── Speech bubble ──────────────────────────────────────────────────
function SpeechBubble({ rank, dim }: { rank: number; dim: ClusteredDimension }) {
  const sentence = firstSentence(dim.viral_mechanism ?? dim.dimension_name);
  const rankStr = `#${String(rank).padStart(2, '0')}`;

  return (
    <div style={{ position: 'relative', width: '100%', paddingTop: 8, marginTop: 6 }}>
      {/* Triangle tail pointing up toward the avatar */}
      <div style={{
        position: 'absolute', top: 0, left: '50%',
        transform: 'translateX(-50%)',
        width: 0, height: 0,
        borderLeft: '7px solid transparent',
        borderRight: '7px solid transparent',
        borderBottom: '7px solid #e0e0e0',
      }} />
      <div style={{
        position: 'absolute', top: 1, left: '50%',
        transform: 'translateX(-50%)',
        width: 0, height: 0,
        borderLeft: '6px solid transparent',
        borderRight: '6px solid transparent',
        borderBottom: '6px solid #f9f9f9',
      }} />

      {/* Bubble body */}
      <div style={{
        padding: '10px 11px',
        borderRadius: 10,
        border: '1px solid #e8e8e8',
        background: '#f9f9f9',
      }}>
        {/* Rank reference — connects visually to the cluster card below */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 5 }}>
          <span style={{ ...MONO, fontSize: 9, color: '#aeaeb2' }}>投票</span>
          <span style={{ ...MONO, fontSize: 10, fontWeight: 700, color: '#1d1d1f' }}>{rankStr}</span>
        </div>

        {/* The "vote" — dimension name */}
        <div style={{ fontSize: 11, fontWeight: 700, color: '#1d1d1f', marginBottom: 4, lineHeight: 1.35 }}>
          {dim.dimension_name}
        </div>

        {/* The reasoning sentence */}
        <div style={{ fontSize: 10, color: '#6e6e73', lineHeight: 1.6 }}>
          {sentence}
        </div>
      </div>
    </div>
  );
}

// ── Placeholder when agent found nothing ───────────────────────────
function AbstainBubble() {
  return (
    <div style={{ position: 'relative', width: '100%', paddingTop: 8, marginTop: 6 }}>
      <div style={{ padding: '10px 11px', borderRadius: 10, border: '1px dashed #eeeeee' }}>
        <div style={{ fontSize: 10, color: '#d0d0d0', textAlign: 'center' }}>—</div>
      </div>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────
interface Props {
  synthesis: SynthesisResult | null;
  isLoading: boolean;
}

export default function LeoAgentGrid({ synthesis, isLoading }: Props) {
  const done = !isLoading && synthesis != null;
  const dims = synthesis?.ranked_dimensions ?? [];

  function agentDim(agentId: number): { rank: number; dim: ClusteredDimension } | null {
    const idx = dims.findIndex((d) => d.supporting_agent_ids?.includes(agentId));
    if (idx === -1) return null;
    return { rank: idx + 1, dim: dims[idx] };
  }

  return (
    <div style={{ borderTop: '1px solid #eeeeee', background: '#fff', padding: '24px 28px 32px' }}>

      {/* Section header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 22 }}>
        <span style={{ ...MONO, fontSize: 10, fontWeight: 600, letterSpacing: '0.14em', color: '#aeaeb2', textTransform: 'uppercase' }}>
          Viral Dimensions
        </span>
        <span style={{ fontSize: 10, fontWeight: 500, color: isLoading ? '#6366f1' : '#34c759' }}>
          {isLoading ? '● Analyzing' : '● Complete'}
        </span>
      </div>

      {/* 6 agent columns — each has ring + name + speech bubble */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 10, marginBottom: 24, alignItems: 'start' }}>
        {AGENTS.map((ag) => {
          const found = agentDim(ag.id);
          return (
            <div key={ag.id} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <AgentRing char={ag.char} done={done} />
              <span style={{ fontSize: 11, color: '#6e6e73', fontWeight: 500, textAlign: 'center', marginTop: 6 }}>
                {ag.name}
              </span>
              {done ? (
                found
                  ? <SpeechBubble rank={found.rank} dim={found.dim} />
                  : <AbstainBubble />
              ) : (
                <div style={{ marginTop: 10, fontSize: 10, color: '#d8d8d8', textAlign: 'center' }}>
                  分析中…
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Cluster cards — connected via rank numbers shown in speech bubbles above */}
      {done && dims.length > 0 && (
        <div>
          <div style={{ ...MONO, fontSize: 10, letterSpacing: '0.14em', color: '#aeaeb2', textTransform: 'uppercase', marginBottom: 12 }}>
            Clusters
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {dims.map((dim, i) => {
              const score = Math.min(10, dim.avg_strength_score ?? 0);
              const supporters = (dim.supporting_agent_ids ?? [])
                .map((id) => AGENTS[id])
                .filter(Boolean);

              return (
                <div key={i} style={{
                  display: 'flex', alignItems: 'flex-start', gap: 16,
                  padding: '14px 16px',
                  border: '1px solid #eeeeee',
                  borderRadius: 12,
                  background: i === 0 ? '#f9f9f9' : '#fff',
                }}>
                  {/* Rank — matches the "投票 #0N" in speech bubbles above */}
                  <div style={{
                    ...MONO, fontSize: 22, fontWeight: 700, lineHeight: 1,
                    color: '#1d1d1f', minWidth: 30, paddingTop: 2, flexShrink: 0,
                  }}>
                    {String(i + 1).padStart(2, '0')}
                  </div>

                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 14, fontWeight: 600, color: '#1d1d1f', marginBottom: 6 }}>
                      {dim.dimension_name}
                    </div>
                    <div style={{ height: 2, background: '#f0f0f0', borderRadius: 1, marginBottom: 8 }}>
                      <div style={{
                        height: 2, borderRadius: 1,
                        width: `${score * 10}%`,
                        background: i === 0 ? '#1d1d1f' : '#b0b0b0',
                        transition: 'width 1s ease',
                      }} />
                    </div>
                    <div style={{ fontSize: 12, color: '#6e6e73', lineHeight: 1.65, marginBottom: 8 }}>
                      {dim.viral_mechanism}
                    </div>
                    {/* Supporting agents */}
                    {supporters.length > 0 && (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                        {supporters.map((ag) => (
                          <span key={ag.id} style={{
                            ...MONO,
                            fontSize: 9, color: '#6e6e73',
                            padding: '2px 7px', borderRadius: 5,
                            border: '1px solid #e8e8e8',
                            background: '#f5f5f7',
                          }}>
                            {ag.name}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  <div style={{ flexShrink: 0, textAlign: 'right' }}>
                    <div style={{ ...MONO, fontSize: 22, fontWeight: 700, color: '#1d1d1f', lineHeight: 1 }}>
                      {dim.agent_agreement_count}
                    </div>
                    <div style={{ ...MONO, fontSize: 9, color: '#aeaeb2', letterSpacing: '0.08em', marginTop: 2 }}>
                      AGENTS
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {synthesis?.top_viral_reason && (
            <div style={{
              marginTop: 14, padding: '14px 16px',
              borderRadius: 12, background: '#f5f5f7', border: '1px solid #eeeeee',
            }}>
              <div style={{ ...MONO, fontSize: 10, letterSpacing: '0.14em', color: '#aeaeb2', textTransform: 'uppercase', marginBottom: 8 }}>
                Summary
              </div>
              <div style={{ fontSize: 13, lineHeight: 1.7, color: '#1d1d1f' }}>
                {synthesis.top_viral_reason}
              </div>
            </div>
          )}
        </div>
      )}

      {isLoading && (
        <div style={{ borderTop: '1px solid #eeeeee', paddingTop: 20, textAlign: 'center' }}>
          <span style={{ fontSize: 12, color: '#c8c8c8' }}>
            Parallel analysis in progress — results will appear here when complete
          </span>
        </div>
      )}
    </div>
  );
}
