import type { SynthesisResult } from '../types';

const MONO: React.CSSProperties = {
  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
};

interface Props { synthesis: SynthesisResult; }

export default function ViralDimensions({ synthesis }: Props) {
  const dims = synthesis.ranked_dimensions ?? [];

  return (
    <div style={{
      border: '1px solid #e8e8e8',
      borderRadius: 16,
      background: '#fff',
      padding: '20px',
      overflowY: 'auto',
      maxHeight: '100%',
    }}>
      {/* Top reason */}
      <div style={{
        marginBottom: 20,
        padding: '14px 16px',
        borderRadius: 12,
        background: '#f5f5f7',
        border: '1px solid #eeeeee',
      }}>
        <div style={{ ...MONO, fontSize: 10, letterSpacing: '0.14em', color: '#aeaeb2', textTransform: 'uppercase', marginBottom: 8 }}>
          Top Viral Reason
        </div>
        <div style={{ fontSize: 13, lineHeight: 1.7, color: '#1d1d1f' }}>
          {synthesis.top_viral_reason}
        </div>
      </div>

      {/* Ranked dimensions */}
      <div style={{ ...MONO, fontSize: 10, letterSpacing: '0.14em', color: '#aeaeb2', textTransform: 'uppercase', marginBottom: 12 }}>
        Dimension Rankings
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {dims.map((d, i) => {
          const score = Math.min(10, d.avg_strength_score ?? 0);
          return (
            <div key={i} style={{
              border: '1px solid #eeeeee',
              borderRadius: 12,
              padding: '12px 14px',
              background: i === 0 ? '#f9f9f9' : '#fff',
            }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 10, marginBottom: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{
                    ...MONO,
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                    width: 22, height: 22, borderRadius: 6,
                    background: i === 0 ? '#1d1d1f' : '#f0f0f0',
                    fontSize: 10, fontWeight: 700,
                    color: i === 0 ? '#fff' : '#6e6e73',
                    flexShrink: 0,
                  }}>
                    {i + 1}
                  </span>
                  <span style={{ fontSize: 13, fontWeight: 600, color: '#1d1d1f' }}>
                    {d.dimension_name}
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                  <span style={{
                    ...MONO, fontSize: 10, color: '#6e6e73',
                    padding: '2px 8px', borderRadius: 6,
                    border: '1px solid #e8e8e8',
                  }}>
                    {d.agent_agreement_count} agents
                  </span>
                  <span style={{ ...MONO, fontSize: 10, color: '#aeaeb2' }}>
                    {score.toFixed(1)}
                  </span>
                </div>
              </div>

              {/* Strength bar */}
              <div style={{ height: 2, background: '#f0f0f0', borderRadius: 1, marginBottom: 8 }}>
                <div style={{
                  height: 2, borderRadius: 1,
                  width: `${score * 10}%`,
                  background: i === 0 ? '#1d1d1f' : '#c0c0c0',
                }} />
              </div>

              <div style={{ fontSize: 12, color: '#6e6e73', lineHeight: 1.65 }}>
                {d.viral_mechanism}
              </div>

              {/* Evidence */}
              {d.representative_evidence?.length > 0 && (
                <details style={{ marginTop: 8 }}>
                  <summary style={{
                    cursor: 'pointer', fontSize: 11, color: '#aeaeb2',
                    listStyle: 'none', display: 'flex', alignItems: 'center', gap: 4,
                  }}>
                    <span>▸</span> {d.representative_evidence.length} evidence items
                  </summary>
                  <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {d.representative_evidence.map((ev, j) => (
                      <div key={j} style={{
                        padding: '8px 10px', borderRadius: 8,
                        background: '#f5f5f7', border: '1px solid #eeeeee',
                        fontSize: 11, color: '#6e6e73', lineHeight: 1.6,
                      }}>
                        <span style={{
                          ...MONO, fontSize: 9, color: '#aeaeb2',
                          background: '#fff', border: '1px solid #e8e8e8',
                          padding: '1px 6px', borderRadius: 4,
                          marginRight: 6,
                        }}>
                          {ev.source}
                        </span>
                        {ev.quote && <span style={{ color: '#1d1d1f' }}>"{ev.quote}" </span>}
                        {ev.reasoning && <span>{ev.reasoning}</span>}
                      </div>
                    ))}
                  </div>
                </details>
              )}
            </div>
          );
        })}
      </div>

      {synthesis.analysis_note && (
        <div style={{
          marginTop: 14, padding: '12px 14px',
          borderRadius: 10, background: '#f5f5f7',
          fontSize: 11, color: '#6e6e73', lineHeight: 1.65,
        }}>
          {synthesis.analysis_note}
        </div>
      )}
    </div>
  );
}
