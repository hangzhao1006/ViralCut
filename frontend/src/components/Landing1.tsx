import { useEffect, useRef } from 'react';

interface LandingProps {
  /** Called when the user clicks "进入工作台" — parent hides Landing and shows the workbench. */
  onEnter: () => void;
}

/**
 * ViralCut 首页 / Landing。
 * 所有样式 scope 在 .vc-landing 下，不会污染工作台的全局样式。
 * 替换 Logo：见下方 brand 区域的注释。
 */
export default function Landing({ onEnter }: LandingProps) {
  const rootRef = useRef<HTMLDivElement>(null);

  // ── signature evidence tracks (rendered as data, not DOM-built) ──
  const segs = [
    { grow: 18, bg: 'var(--indigo-900)', pct: '0–3s', lab: '开头 Hook' },
    { grow: 42, bg: 'var(--indigo)', pct: '3–18s', lab: '展开 / 演示' },
    { grow: 24, bg: 'var(--indigo-400)', pct: '18–28s', lab: '对比' },
    { grow: 16, bg: 'var(--indigo-600)', pct: '28–34s', lab: '结尾 CTA' },
  ];
  const ticks = [4, 11, 17, 24, 30, 37, 43, 50, 56, 63, 70, 78, 85, 92];
  const blocks = [22, 30, 14, 38, 18, 26, 34, 12, 28, 20, 16, 24];
  const dots: number[] = [];
  for (let p = 4; p < 98; p += 6.5) dots.push(p);
  const energyPath = (() => {
    const pts = [2, 3, 2.5, 5, 7, 6, 8, 9, 11, 9, 7, 8, 12, 14, 11, 9, 13, 16, 12, 8, 6, 10, 15, 17, 14, 10, 7, 5, 9, 13, 11, 7, 4, 3];
    const W = 600, H = 18, max = 18;
    let d = `M0,${H}`;
    pts.forEach((v, i) => {
      const x = (i / (pts.length - 1)) * W;
      const y = H - (v / max) * (H - 2) - 1;
      d += ` L${x.toFixed(1)},${y.toFixed(1)}`;
    });
    return `${d} L${W},${H} Z`;
  })();

  const cards: [string, string, string][] = [
    ['01', '迁移方法，不复制内容', '产出的是结构模板 + 编辑规则，直接套到你的素材上。换了题材照样能用，不是一次性翻拍。'],
    ['02', '证据驱动，句句可追溯', '每个判断都钉在 Stage 1 的客观证据上（OCR/ASR/节拍），能追回原片是哪一帧——不是黑盒拍脑袋。'],
    ['03', '双重视角，交叉验证', '“怎么迁移”和“为什么爆”两套 Agent 独立跑、互相印证，单视角看不到的盲区在这里被补上。'],
    ['04', '缺口识别 + 自动补全', '素材撑不起目标结构时主动报缺口，并给出五种补全路径，而不是直接报错或硬塞。'],
    ['05', '一句话改片', '“开头更抓人”“把卖点提前”——自然语言就能调，或只重生成某一个槽位，不用全部推倒重来。'],
    ['06', '真实素材直接适配', '上传你自己的素材，自动做镜头分类、高光筛选、开头/中段/结尾推荐，直接进迁移流程。'],
  ];

  const archRows: [string, [string, boolean][]][] = [
    ['Agent 范式', [['ReAct', true], ['Chain-of-Thought', true], ['Tool Use / Function Calling', true], ['Blackboard 黑板', false], ['依赖 DAG 编排', false], ['并行集成', false]]],
    ['推理', [['Doubao Seed 2.0 Lite', false], ['火山方舟 · OpenAI 兼容', false]]],
    ['感知层', [['faster-whisper', false], ['RapidOCR', false], ['EasyOCR', false], ['librosa', false], ['yt-dlp', false]]],
    ['服务', [['FastAPI', false], ['Docker', false]]],
    ['前端', [['React', false], ['TypeScript', false], ['Vite', false], ['Tailwind', false]]],
    ['可视化', [['多轨时间线', false], ['结构槽位映射', false], ['迁移前后对比', false]]],
  ];

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const reveals = Array.from(root.querySelectorAll('.reveal'));
    const bar = root.querySelector('#vc-bar');
    const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (prefersReduced) {
      reveals.forEach((el) => el.classList.add('in'));
      bar?.classList.add('split');
      return;
    }

    const io = new IntersectionObserver(
      (entries) => entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } }),
      { threshold: 0.12 },
    );
    reveals.forEach((el) => io.observe(el));

    let sigIo: IntersectionObserver | null = null;
    const sig = root.querySelector('#vc-sig');
    if (sig && bar) {
      sigIo = new IntersectionObserver(
        (entries) => entries.forEach((e) => {
          if (e.isIntersecting) { window.setTimeout(() => bar.classList.add('split'), 250); sigIo?.unobserve(e.target); }
        }),
        { threshold: 0.35 },
      );
      sigIo.observe(sig);
    }

    return () => { io.disconnect(); sigIo?.disconnect(); };
  }, []);

  const goLogic = (e: React.MouseEvent) => {
    e.preventDefault();
    rootRef.current?.querySelector('#logic')?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <div className="vc-landing" ref={rootRef}>
      <style>{STYLES}</style>

      <nav>
        <div className="wrap nav-in">
          <div className="brand">
            {/* 换 Logo：把下面这行 <div className="logo">VC</div> 替换成
                <img src="/logo.svg" className="logo-img" alt="ViralCut" /> */}
            <img src="/logo.svg" className="logo-img" alt="ViralCut" /> 
            <b>ViralCut</b>
          </div>
          <button className="btn btn-primary" onClick={onEnter}>进入工作台 →</button>
        </div>
      </nav>

      {/* HERO */}
      <header className="hero wrap">
        <div className="kicker">爆款视频结构迁移引擎</div>
        <h1>学的是<span className="muted">结构</span>，<br />不是内容。</h1>
        <p className="lead">别人“一键生成”的是内容；我们迁移的是让爆款之所以爆的结构能力——开头钩子、镜头节奏、卖点推进、卡点收尾。素材撑不起目标结构？系统自动识别缺口并补全，而不是让你照着原片翻拍。</p>
        <div className="hero-cta">
          <button className="btn btn-primary" onClick={onEnter}>进入工作台 →</button>
          <a className="btn btn-ghost" href="#logic" onClick={goLogic}>看它怎么工作</a>
          <span className="hero-note">多 Agent 协作 · 证据可追溯 · 全程可解释</span>
        </div>

        {/* signature: deconstruction */}
        <div className="signature" id="vc-sig">
          <div className="sig-head">
            <span className="t">一条爆款 → 拆成可迁移的功能结构</span>
            <span className="s">EVIDENCE-BASED DECONSTRUCTION</span>
          </div>
          <div className="bar" id="vc-bar">
            {segs.map((s, i) => (
              <div key={i} className="seg" style={{ flexGrow: s.grow, background: s.bg }}>
                <span className="pct">{s.pct}</span>
                <span className="lab">{s.lab}</span>
              </div>
            ))}
          </div>
          <div className="tracks">
            <div className="track"><div className="tl">镜头切换</div><div className="tv"><div className="ticks">{ticks.map((p, i) => <i key={i} style={{ left: `${p}%` }} />)}</div></div></div>
            <div className="track"><div className="tl">字幕密度</div><div className="tv"><div className="blocks">{blocks.map((w, i) => <i key={i} style={{ width: `${w}px` }} />)}</div></div></div>
            <div className="track"><div className="tl">节拍 BPM</div><div className="tv"><div className="dots">{dots.map((p, i) => <i key={i} style={{ left: `${p}%` }} />)}</div></div></div>
            <div className="track"><div className="tl">能量曲线</div><div className="tv"><div className="energy"><svg viewBox="0 0 600 18" preserveAspectRatio="none"><path d={energyPath} fill="rgba(99,102,241,.16)" stroke="var(--indigo)" strokeWidth="1.4" /></svg></div></div></div>
          </div>
        </div>
      </header>

      {/* PAIN */}
      <section className="wrap">
        <div className="pain reveal">
          <div className="kicker">问题</div>
          <blockquote>创作者能“感觉”哪条视频出效果，却很难把这种经验抽出来、复用、迁移到新任务。</blockquote>
          <div className="pain-grid">
            <div><div className="n">01</div><div className="h">抽不出来</div><div className="d">“节奏好”“开头抓人”是直觉，落不成可操作的结构。</div></div>
            <div><div className="n">02</div><div className="h">复用不了</div><div className="d">下一条视频题材一换，上次的经验又得从零再来。</div></div>
            <div><div className="n">03</div><div className="h">迁移不到</div><div className="d">想借鉴爆款，结果只能照着翻拍，换了内容就不灵。</div></div>
          </div>
        </div>
      </section>

      {/* LOGIC / PIPELINE */}
      <section className="wrap" id="logic">
        <div className="sec-head reveal">
          <div className="kicker">核心逻辑</div>
          <h2>从证据到结构，再到迁移</h2>
          <p>不靠 LLM 凭感觉打分。先用感知模型抽客观证据，再用多 Agent 在证据上做结构分析与归因，最后把结构迁移到新内容并补全缺口。</p>
        </div>

        <div className="stage reveal">
          <div className="stage-num"><div className="s">STAGE</div><div className="big">01</div></div>
          <div>
            <h3>证据提取</h3>
            <p>对样例做多模态感知，产出客观的 <span className="vc-mono">evidence_package</span>：镜头切分、逐帧 OCR、语音转写、节拍点。后续所有判断都回溯到这里。</p>
            <div className="pills"><span className="pill">镜头切分</span><span className="pill">OCR · RapidOCR/EasyOCR</span><span className="pill">ASR · faster-whisper</span><span className="pill">节拍 · librosa</span></div>
          </div>
        </div>

        <div className="stage reveal">
          <div className="stage-num"><div className="s">STAGE</div><div className="big">02</div></div>
          <div>
            <h3>双视角多 Agent 分析</h3>
            <p>两套独立的 Agent 团队，从不同角度同时解读同一份证据，结论互相印证。</p>
            <div className="dual">
              <div className="lane">
                <div className="lh"><span className="dot" style={{ background: 'var(--indigo)' }} />结构分析 · 6 Agent 串行</div>
                <div className="ld">逐层拆出脚本/节奏/包装/价值/能量，产出可迁移的结构蓝图。</div>
                <div className="agents"><span>脚本</span><span className="arrow">→</span><span>节奏</span><span className="arrow">→</span><span>包装</span><span className="arrow">→</span><span>价值</span><span className="arrow">→</span><span>能量</span><span className="arrow">→</span><span>迁移</span></div>
              </div>
              <div className="lane">
                <div className="lh"><span className="dot" style={{ background: 'var(--indigo-400)' }} />爆款归因 · 6 视角并行</div>
                <div className="ld">六个视角并行投票，归纳“为什么爆”的核心维度并排名。</div>
                <div className="agents"><span>情感</span><span>叙事</span><span>社会</span><span>信息</span><span>制作</span><span>行为</span></div>
              </div>
            </div>
          </div>
        </div>

        <div className="stage reveal">
          <div className="stage-num"><div className="s">STAGE</div><div className="big">03</div></div>
          <div>
            <h3>结构迁移与缺口补全</h3>
            <p>把结构蓝图套到新主题/商品/素材上，逐个槽位检查素材是否撑得起目标结构；撑不起的，给出补全方案。</p>
            <div className="pills"><span className="pill">结构重排</span><span className="pill">文案补全</span><span className="pill">包装补全</span><span className="pill">AIGC 生成</span><span className="pill">素材重组复用</span></div>
          </div>
        </div>
      </section>

      {/* MULTI-AGENT ARCHITECTURE */}
      <section className="wrap">
        <div className="sec-head reveal">
          <div className="kicker">多 Agent 架构</div>
          <h2>两套 Agent 团队，一块共享黑板</h2>
          <p>不是把一个大模型当万能助手。证据进来后由编排器分发给两套独立的 Agent 团队，各用不同的协作模式工作，结论互相印证。</p>
        </div>

        <div className="reveal">
          <div className="orch-in">输入 · evidence_package（Stage 1 客观证据）</div>
          <div className="teams">
            <div className="team">
              <div className="team-h"><span className="dot" style={{ background: 'var(--indigo)' }} />结构分析 · 黑板 + 依赖 DAG</div>
              <div className="team-s">6 个 Agent 按依赖图调度，结果写入共享黑板，下游 Agent 读取上游结论后再推理。</div>
              <div className="lane-flow">
                <div className="flow-row"><span className="node dark">脚本</span></div>
                <div className="vbar" />
                <div className="flow-row"><span className="node">节奏</span><span className="node">包装</span><span className="node">价值</span><span className="pllabel">∥ 同层</span></div>
                <div className="vbar" />
                <div className="flow-row"><span className="node">能量</span><span className="arrow">→</span><span className="node dark">迁移</span><span className="arrow">⇒</span><span className="outlab">迁移蓝图</span></div>
              </div>
              <div className="bb">黑板 Blackboard · 所有 Agent 读写共享分析结论</div>
              <div className="meta-note">每个 Agent = ReAct 循环 · CoT 分步推理 · 调用 10 个证据工具</div>
            </div>

            <div className="team">
              <div className="team-h"><span className="dot" style={{ background: 'var(--indigo-400)' }} />爆款归因 · 并行集成</div>
              <div className="team-s">6 个分析视角并行运行（asyncio），各自独立给出发现，再交给合成 Agent 汇总。</div>
              <div className="lane-flow">
                <div className="flow-row"><span className="node">情感</span><span className="node">叙事</span><span className="node">社会</span></div>
                <div className="flow-row" style={{ marginTop: 8 }}><span className="node">信息</span><span className="node">制作</span><span className="node">行为</span><span className="pllabel">∥ 并行</span></div>
                <div className="vbar" />
                <div className="flow-row"><span className="node dark">Synthesis</span><span className="arrow">⇒</span><span className="outlab">归因维度排名</span></div>
              </div>
              <div className="bb alt">合成 · 语义聚类相似维度 + 按「认同数 × 强度」投票排名</div>
              <div className="meta-note">输出 ranked_dimensions：每个维度带认同 Agent 数、平均强度、爆款机制</div>
            </div>
          </div>

          <div className="evalbar">
            <div className="eh"><span className="dot" style={{ background: 'var(--green)' }} />质量评估 Evaluator<span className="hbadge">规则化 · 非训练奖励模型</span></div>
            <div className="ed">对最终结构做确定性检查：schema 是否完整、判断是否有证据支撑、时间线有无断层、迁移蓝图是否够强 —— 给出可解释的质量分，而不是黑盒评判。</div>
          </div>

          <div className="tools-strip">
            <span className="toolc">证据工具集</span>
            {['get_overview', 'query_timeline', 'compute_metrics', 'search_text', 'get_segment_evidence', 'get_cut_beat_alignment', 'read_blackboard', 'look_at_keyframe · 预算限额'].map((t) => (
              <span key={t} className="tool">{t}</span>
            ))}
          </div>
        </div>
      </section>

      {/* SELLING POINTS */}
      <section className="wrap">
        <div className="sec-head reveal">
          <div className="kicker">为什么不一样</div>
          <h2>不是又一个“一键生成”</h2>
          <p>评审最在意的是自主设计与可解释性。这六点是我们和“直接调现成产品”的根本区别。</p>
        </div>
        <div className="cards">
          {cards.map(([n, h, d]) => (
            <div key={n} className="card reveal"><div className="ci">{n}</div><h4>{h}</h4><p>{d}</p></div>
          ))}
        </div>
      </section>

      {/* ARCH */}
      <section className="wrap">
        <div className="sec-head reveal">
          <div className="kicker">技术架构</div>
          <h2>多 Agent 编排，前后端闭环</h2>
        </div>
        <div className="arch reveal">
          {archRows.map(([label, chips]) => (
            <div key={label} className="arch-row">
              <div className="al">{label}</div>
              <div className="av">
                {chips.map(([c, hot]) => <span key={c} className={hot ? 'chip hot' : 'chip'}>{c}</span>)}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* FINAL CTA */}
      <section className="wrap final reveal">
        <h2>把别人的爆款，拆成你自己能复用的结构。</h2>
        <p>上传样例或粘贴链接，同时跑结构分析与爆款归因，几分钟看到完整迁移方案。</p>
        <button className="btn btn-primary" onClick={onEnter}>进入工作台 →</button>
      </section>

      <footer className="wrap">
        <span>VIRALCUT · 爆款视频结构迁移引擎</span>
        <span>EVIDENCE-BASED MULTI-AGENT WORKFLOW</span>
      </footer>
    </div>
  );
}

const STYLES = `
.vc-landing{
  --bg:#f5f5f7; --card:#ffffff; --ink:#1d1d1f; --ink2:#6e6e73; --ink3:#aeaeb2;
  --border:#e2e2e4; --border-soft:#eeeeee;
  --indigo:#6366f1; --indigo-600:#4f46e5; --indigo-700:#4338ca; --indigo-900:#312e81;
  --indigo-400:#818cf8; --indigo-300:#a5b4fc; --indigo-200:#c7d2fe; --indigo-50:#eef2ff;
  --green:#34c759;
  --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  --sans: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
          "SF Pro Display","PingFang SC","Hiragino Sans GB","Microsoft YaHei", sans-serif;
  min-height:100vh; background:var(--bg); color:var(--ink);
  font-family:var(--sans); -webkit-font-smoothing:antialiased; line-height:1.5;
}
.vc-landing *{box-sizing:border-box;}
.vc-landing a{color:inherit; text-decoration:none;}
.vc-landing .wrap{max-width:1080px; margin:0 auto; padding:0 24px;}
.vc-landing .kicker{font-family:var(--mono); font-size:11px; font-weight:600; letter-spacing:.16em; text-transform:uppercase; color:var(--ink3);}

.vc-landing nav{position:sticky; top:0; z-index:50; backdrop-filter:saturate(180%) blur(20px); background:rgba(245,245,247,.72); border-bottom:1px solid var(--border-soft);}
.vc-landing .nav-in{display:flex; align-items:center; justify-content:space-between; height:60px;border:1px solid #767676;}
.vc-landing .brand{display:flex; align-items:center; gap:10px;}
.vc-landing .logo{width:30px; height:30px; border-radius:9px; background:var(--ink); color:#fff; display:flex; align-items:center; justify-content:center; font-size:12px; font-weight:600; letter-spacing:.02em;}
.vc-landing .logo-img{width:30px; height:30px; border-radius:9px; display:block; object-fit:contain;}
.vc-landing .brand b{font-size:15px; font-weight:600; letter-spacing:-.01em;}
.vc-landing .btn{display:inline-flex; align-items:center; gap:6px; border-radius:11px; cursor:pointer; font-size:13px; font-weight:600; padding:9px 16px; border:1px solid transparent; background:none; font-family:inherit; transition:.18s;}
.vc-landing .btn-primary{background:var(--indigo); color:#fff; box-shadow:0 2px 10px rgba(99,102,241,.28);}
.vc-landing .btn-primary:hover{background:var(--indigo-600); transform:translateY(-1px);}
.vc-landing .btn-ghost{border-color:var(--border); background:#fff; color:var(--ink);}
.vc-landing .btn-ghost:hover{border-color:#c8c8cc;}

.vc-landing .hero{padding:84px 0 64px;}
.vc-landing .hero .kicker{margin-bottom:20px;}
.vc-landing h1{font-size:clamp(34px,5.4vw,58px); line-height:1.04; letter-spacing:-.025em; font-weight:680; margin:0 0 22px; max-width:14ch;}
.vc-landing h1 .muted{color:var(--ink3);}
.vc-landing .lead{font-size:clamp(15px,1.7vw,18px); color:var(--ink2); max-width:54ch; margin:0 0 32px;}
.vc-landing .hero-cta{display:flex; gap:12px; align-items:center; flex-wrap:wrap;}
.vc-landing .hero-note{font-family:var(--mono); font-size:11px; color:var(--ink3);}

.vc-landing .signature{margin-top:64px; border:1px solid var(--border); background:#fff; border-radius:22px; padding:28px 28px 24px; box-shadow:0 1px 3px rgba(0,0,0,.04), 0 18px 48px rgba(15,23,42,.06);}
.vc-landing .sig-head{display:flex; justify-content:space-between; align-items:baseline; margin-bottom:18px;}
.vc-landing .sig-head .t{font-size:13px; font-weight:600;}
.vc-landing .sig-head .s{font-family:var(--mono); font-size:11px; color:var(--ink3);}
.vc-landing .bar{display:flex; gap:0; height:62px; border-radius:12px; overflow:hidden;}
.vc-landing .seg{position:relative; display:flex; align-items:flex-end; padding:9px 11px; color:#fff; overflow:hidden; transition:flex-grow .8s cubic-bezier(.22,1,.36,1), margin .8s cubic-bezier(.22,1,.36,1);}
.vc-landing .seg .lab{font-size:11px; font-weight:600; letter-spacing:.01em; opacity:0; transform:translateY(6px); transition:opacity .5s .5s, transform .5s .5s; position:relative; z-index:2;}
.vc-landing .seg .pct{position:absolute; top:8px; left:11px; font-family:var(--mono); font-size:10px; opacity:.65;}
.vc-landing .split .seg{border-radius:9px;}
.vc-landing .split .seg + .seg{margin-left:6px;}
.vc-landing .split .seg .lab{opacity:1; transform:none;}
.vc-landing .tracks{margin-top:16px; display:grid; gap:9px;}
.vc-landing .track{display:grid; grid-template-columns:74px 1fr; align-items:center; gap:14px;}
.vc-landing .track .tl{font-family:var(--mono); font-size:10px; color:var(--ink3); text-align:right; letter-spacing:.04em;}
.vc-landing .track .tv{height:18px; border-radius:6px; background:var(--bg); position:relative; overflow:hidden;}
.vc-landing .ticks{position:absolute; inset:0; display:flex; align-items:center;}
.vc-landing .ticks i{position:absolute; top:3px; bottom:3px; width:1.5px; background:var(--indigo-300); border-radius:2px;}
.vc-landing .blocks{position:absolute; inset:0; display:flex; align-items:center; gap:3px; padding:0 4px;}
.vc-landing .blocks i{height:8px; border-radius:2px; background:var(--indigo-200);}
.vc-landing .dots{position:absolute; inset:0; display:flex; align-items:center; gap:0;}
.vc-landing .dots i{position:absolute; width:4px; height:4px; border-radius:50%; background:var(--indigo-400); top:50%; transform:translateY(-50%);}
.vc-landing .energy{position:absolute; inset:0;}
.vc-landing .energy svg{width:100%; height:100%; display:block;}

.vc-landing section{padding:100px 0;}
.vc-landing .sec-head{max-width:60ch; margin-bottom:48px;}
.vc-landing .sec-head .kicker{margin-bottom:14px;}
.vc-landing h2{font-size:clamp(24px,3vw,34px); line-height:1.12; letter-spacing:-.02em; font-weight:660; margin:0 0 14px;}
.vc-landing .sec-head p{color:var(--ink2); font-size:16px; margin:0; max-width:52ch;}

.vc-landing .pain{background:var(--ink); color:#fff; border-radius:28px; padding:56px clamp(28px,5vw,64px);}
.vc-landing .pain .kicker{color:rgba(255,255,255,.45);}
.vc-landing .pain blockquote{margin:14px 0 36px; font-size:clamp(20px,2.6vw,30px); line-height:1.28; letter-spacing:-.015em; font-weight:560; max-width:24ch;}
.vc-landing .pain-grid{display:grid; grid-template-columns:repeat(3,1fr); gap:1px; background:rgba(255,255,255,.12); border-radius:16px; overflow:hidden;}
.vc-landing .pain-grid > div{background:var(--ink); padding:22px 22px 24px;}
.vc-landing .pain-grid .n{font-family:var(--mono); font-size:11px; color:var(--indigo-300); margin-bottom:10px;}
.vc-landing .pain-grid .h{font-size:16px; font-weight:600; margin-bottom:6px;}
.vc-landing .pain-grid .d{font-size:13px; color:rgba(255,255,255,.6); line-height:1.5;}

.vc-landing .stage{display:grid; grid-template-columns:118px 1fr; gap:28px; padding:30px 0; border-top:1px solid var(--border);}
.vc-landing .stage:first-of-type{border-top:none;}
.vc-landing .stage-num{font-family:var(--mono);}
.vc-landing .stage-num .s{font-size:11px; color:var(--ink3); letter-spacing:.12em;}
.vc-landing .stage-num .big{font-size:40px; font-weight:600; line-height:1; letter-spacing:-.02em; color:var(--ink); margin-top:6px;}
.vc-landing .stage h3{font-size:19px; font-weight:640; margin:0 0 6px; letter-spacing:-.01em;}
.vc-landing .stage > div > p{color:var(--ink2); font-size:14px; margin:0 0 16px; max-width:60ch;}
.vc-landing .pills{display:flex; flex-wrap:wrap; gap:7px;}
.vc-landing .pill{font-family:var(--mono); font-size:11px; padding:5px 10px; border-radius:8px; background:var(--card); border:1px solid var(--border); color:var(--ink2);}
.vc-landing .dual{display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:4px;}
.vc-landing .dual .lane{border:1px solid var(--border); border-radius:14px; padding:16px 16px 18px; background:#fff;}
.vc-landing .dual .lane .lh{display:flex; align-items:center; gap:8px; font-size:13px; font-weight:640; margin-bottom:4px;}
.vc-landing .dual .lane .ld{font-size:12px; color:var(--ink2); margin-bottom:12px; line-height:1.5;}
.vc-landing .dot{width:7px; height:7px; border-radius:50%;}
.vc-landing .agents{display:flex; flex-wrap:wrap; gap:5px;}
.vc-landing .agents span{font-family:var(--mono); font-size:10px; padding:3px 7px; border-radius:6px; background:var(--indigo-50); color:var(--indigo-700);}
.vc-landing .arrow{font-family:var(--mono); color:var(--ink3); padding:0 2px;}

.vc-landing .orch-in{font-family:var(--mono); font-size:11px; color:var(--ink3); text-align:center; margin-bottom:16px; letter-spacing:.04em;}
.vc-landing .teams{display:grid; grid-template-columns:1fr 1fr; gap:14px;}
.vc-landing .team{border:1px solid var(--border); border-radius:18px; background:#fff; padding:24px;}
.vc-landing .team-h{display:flex; align-items:center; gap:8px; font-weight:640; font-size:15px; letter-spacing:-.01em;}
.vc-landing .team-s{font-size:12.5px; color:var(--ink2); margin:6px 0 18px; line-height:1.55;}
.vc-landing .lane-flow{display:flex; flex-direction:column; align-items:flex-start;}
.vc-landing .flow-row{display:flex; gap:7px; align-items:center; flex-wrap:wrap;}
.vc-landing .node{display:inline-flex; align-items:center; gap:6px; padding:7px 13px; border-radius:10px; background:var(--indigo-50); border:1px solid var(--indigo-200); color:var(--indigo-700); font-size:13px; font-weight:600;}
.vc-landing .node.dark{background:var(--ink); color:#fff; border-color:var(--ink);}
.vc-landing .vbar{width:1.5px; height:15px; background:var(--border); margin:5px 0 5px 22px;}
.vc-landing .pllabel{font-family:var(--mono); font-size:10.5px; color:var(--ink3);}
.vc-landing .outlab{font-family:var(--mono); font-size:10.5px; color:var(--indigo-700); font-weight:600;}
.vc-landing .bb{margin-top:16px; border:1px dashed var(--indigo-300); border-radius:10px; padding:10px 13px; background:var(--indigo-50); font-size:12px; color:var(--indigo-700); font-weight:500;}
.vc-landing .bb.alt{border-style:solid; border-color:var(--border); background:var(--bg); color:var(--ink2);}
.vc-landing .meta-note{margin-top:12px; font-family:var(--mono); font-size:10.5px; color:var(--ink3); line-height:1.55;}
.vc-landing .evalbar{margin-top:14px; border:1px solid var(--border); border-radius:16px; background:#fff; padding:18px 22px;}
.vc-landing .evalbar .eh{font-weight:640; font-size:14px; display:flex; gap:8px; align-items:center; flex-wrap:wrap;}
.vc-landing .evalbar .ed{font-size:12.5px; color:var(--ink2); margin-top:6px; line-height:1.55; max-width:74ch;}
.vc-landing .hbadge{font-family:var(--mono); font-size:10px; color:var(--ink3); border:1px solid var(--border); border-radius:6px; padding:2px 7px; font-weight:500;}
.vc-landing .tools-strip{margin-top:14px; display:flex; flex-wrap:wrap; gap:6px; align-items:center;}
.vc-landing .toolc{font-family:var(--mono); font-size:10px; color:var(--ink3); letter-spacing:.1em; text-transform:uppercase; margin-right:4px;}
.vc-landing .tool{font-family:var(--mono); font-size:10.5px; padding:4px 9px; border-radius:7px; background:#fff; border:1px solid var(--border); color:var(--ink2);}

.vc-landing .cards{display:grid; grid-template-columns:repeat(3,1fr); gap:14px;}
.vc-landing .card{border:1px solid var(--border); border-radius:18px; background:#fff; padding:24px 22px 26px; transition:.2s; position:relative;}
.vc-landing .card:hover{transform:translateY(-3px); box-shadow:0 12px 32px rgba(15,23,42,.07); border-color:#d4d4d8;}
.vc-landing .card .ci{font-family:var(--mono); font-size:11px; color:var(--indigo); margin-bottom:16px;}
.vc-landing .card h4{font-size:16px; font-weight:640; margin:0 0 8px; letter-spacing:-.01em;}
.vc-landing .card p{font-size:13px; color:var(--ink2); margin:0; line-height:1.55;}

.vc-landing .arch{background:#fff; border:1px solid var(--border); border-radius:24px; padding:clamp(28px,4vw,48px);}
.vc-landing .arch-row{display:grid; grid-template-columns:120px 1fr; gap:24px; padding:20px 0; border-top:1px solid var(--border-soft);}
.vc-landing .arch-row:first-child{border-top:none; padding-top:0;}
.vc-landing .arch-row .al{font-family:var(--mono); font-size:11px; color:var(--ink3); letter-spacing:.06em; padding-top:3px; text-transform:uppercase;}
.vc-landing .arch-row .av{display:flex; flex-wrap:wrap; gap:8px;}
.vc-landing .chip{font-size:12.5px; padding:6px 12px; border-radius:9px; background:var(--bg); border:1px solid var(--border); color:var(--ink);}
.vc-landing .chip.hot{background:var(--ink); color:#fff; border-color:var(--ink);}

.vc-landing .final{text-align:center; padding:96px 0 30px;}
.vc-landing .final h2{margin-bottom:18px;}
.vc-landing .final p{color:var(--ink2); max-width:46ch; margin:0 auto 30px; font-size:16px;}
.vc-landing footer{border-top:1px solid var(--border-soft); padding:26px 0 48px; color:var(--ink3); font-family:var(--mono); font-size:11px; display:flex; justify-content:space-between; flex-wrap:wrap; gap:8px;}

.vc-landing .vc-mono{font-family:var(--mono);}
.vc-landing .reveal{opacity:0; transform:translateY(18px); transition:opacity .7s cubic-bezier(.22,1,.36,1), transform .7s cubic-bezier(.22,1,.36,1);}
.vc-landing .reveal.in{opacity:1; transform:none;}

@media (max-width:820px){
  .vc-landing .pain-grid,.vc-landing .cards,.vc-landing .teams{grid-template-columns:1fr;}
  .vc-landing .dual{grid-template-columns:1fr;}
  .vc-landing .stage{grid-template-columns:1fr; gap:14px;}
  .vc-landing .arch-row{grid-template-columns:1fr; gap:10px;}
}
@media (prefers-reduced-motion:reduce){
  .vc-landing *{transition:none !important; animation:none !important;}
  .vc-landing .reveal{opacity:1; transform:none;}
}
`;