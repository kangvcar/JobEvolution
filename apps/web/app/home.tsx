"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { EventList, Heat, Pipe } from "./feed-bits";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Story = {
  kind: string;
  job_id: string;
  name: string;
  title: string;
  hint: string;
  sources: string;
  delta: { add: boolean; name: string }[];
};
type Feed = {
  emerging: number;
  in_graph: number;
  stories: Story[];
  pipeline: { source: string; n: number }[];
  heat: { name: string; v: number }[];
  events: { at: string; text: string; review?: string }[];
};

export function Home() {
  const [feed, setFeed] = useState<Feed | null>(null);

  useEffect(() => {
    fetch(`${API}/feed`)
      .then((r) => r.json())
      .then((body: Feed) => setFeed(body))
      .catch(() => setFeed(null));
  }, []);

  return (
    <main id="main" className="home-page">
      <section className="home-hero">
        <div className="hero-copy-block">
          <p className="eyebrow"><span className="eyebrow-dot" />智演 / 职业迁移导航</p>
          <h1>你的下一步 AI 岗位，不该靠猜。</h1>
          <p className="hero-copy">把简历里的经历，放进真实招聘要求里比较。智演会告诉你当前更接近哪条岗位路径，哪些证据已经成立，下一档还差什么。</p>
        <div className="hero-actions">
          <Link className="primary" href="/diagnose">上传简历开始对照</Link>
          <Link className="text-link" href="/diagnose?job=job-e1662d9b8cfd059f">先看一份示例报告 <span aria-hidden="true">↗</span></Link>
        </div>
        </div>
        <div className="hero-visual" aria-label="示例方向结论">
          <div className="signal-board">
            <div className="signal-board-head"><span>示例诊断</span><span className="mono">图谱 2026 / Q3</span></div>
            <div className="path-visual">
              <article className="path-card path-card-current">
                <span className="mono">当前更接近</span>
                <h2>大模型应用工程师</h2>
                <p>Python · FastAPI · RAG</p>
              </article>
              <div className="path-connector" aria-hidden="true"><i /><span>可迁移</span><i /></div>
              <article className="path-card path-card-next">
                <span className="mono">可比较方向</span>
                <h2>Agent 工程师</h2>
                <p>工具调用 · 工作流 · 评测</p>
              </article>
            </div>
            <div className="evidence-bridge">
              <span className="bridge-line" />
              <div><b>最大阻碍</b><span>缺少可核对的 RAG 项目结果</span></div>
              <span className="bridge-line" />
            </div>
            <div className="signal-board-foot"><span>证据充分度</span><strong>原文可追溯</strong><span className="status-mark">●</span></div>
          </div>
          <p className="visual-note"><span className="mono">01</span> 每个判断都能回到简历片段和招聘来源</p>
        </div>
      </section>
      <section className="home-proof" aria-label="产品工作方式">
        <div><span className="proof-number">01</span><b>读市场</b><p>从多源招聘数据里看岗位要求怎样变化。</p></div>
        <div><span className="proof-number">02</span><b>对证据</b><p>把岗位要求和简历原文逐项对应。</p></div>
        <div><span className="proof-number">03</span><b>定方向</b><p>比较岗位档位与最小换档条件。</p></div>
        <div><span className="proof-number">04</span><b>去行动</b><p>分开处理简历证明和能力提升。</p></div>
      </section>
      <section className="home-evidence" aria-labelledby="evidence-title">
        <div>
          <p className="eyebrow">市场证据</p>
          <h2 id="evidence-title">岗位正在怎么变，决定你该补什么。</h2>
          <p className="hint">岗位定义、招聘公司和本周期变化来自同一份公开招聘数据。先看市场，再看自己的位置。</p>
        </div>
        <div className="evidence-links">
          <Link className="evidence-card" href="/graph"><span className="card-index">A</span><b>岗位图谱</b><span>查看岗位要求与证据</span><span className="card-arrow">↗</span></Link>
          <Link className="evidence-card" href="/discover"><span className="card-index">B</span><b>市场变化</b><span>了解哪些岗位正在形成</span><span className="card-arrow">↗</span></Link>
        </div>
      </section>
      <aside className="home-feed">
        {feed ? (
          <dl className="readout">
            <div>
              <dt>萌芽</dt>
              <dd>{feed.emerging}</dd>
            </div>
            <div>
              <dt>岗位总数</dt>
              <dd>{feed.in_graph}</dd>
            </div>
          </dl>
        ) : (
            <p className="hint">正在读取本周期数据</p>
        )}
        {(feed?.stories || []).slice(0, 2).map((story) => (
          <article className="story" key={story.kind}>
            <span className={`pill ${story.kind === "discover" ? "hot" : "mid"}`}>
              {story.kind === "discover" ? "新岗位发现" : "既有岗位更新"}
            </span>
            <h2>{story.title}</h2>
            <p className="hint">{story.hint}</p>
            {story.delta.length > 0 ? (
              <div className="delta">
                {story.delta.map((row) => (
                  <b key={row.name} className={row.add ? "add" : "del"}>
                    {row.add ? `+ ${row.name}` : row.name}
                  </b>
                ))}
              </div>
            ) : null}
            {story.sources ? <p className="src">{story.sources}</p> : null}
            <div className="row">
              <Link className="primary" href={`/graph?job=${encodeURIComponent(story.job_id)}`}>
                打开工作台
              </Link>
              <Link className="ghost" href={`/diagnose?job=${encodeURIComponent(story.job_id)}`}>
                对照这份岗
              </Link>
            </div>
          </article>
        ))}
        <details className="how">
          <summary>本周期怎么算出来的</summary>
          <div className="how-body">
            <section>
              <h2>数据来源</h2>
              <p className="hint">按招聘渠道去重统计，和市场变化页使用同一份口径。</p>
              <Pipe rows={feed?.pipeline || []} />
            </section>
            <section>
              <h2>技能出现情况</h2>
              <p className="hint">这是公开岗位中的出现比例，不是搜索指数。</p>
              <Heat rows={feed?.heat || []} />
            </section>
            <section>
              <h2>岗位变化记录</h2>
              <p className="hint">记录岗位要求和状态的变化。</p>
              <EventList rows={feed?.events || []} />
            </section>
          </div>
        </details>
      </aside>
    </main>
  );
}
