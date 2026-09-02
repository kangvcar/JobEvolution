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
        <p className="mono">智演 / 职业方向诊断</p>
        <h1>用招聘市场证据，判断你现在更适合哪个 AI 岗位</h1>
        <p className="hero-copy">上传简历，确认解析结果，再看真实招聘要求与你的经历如何对应。报告会把能力缺口和表达缺口分开，并给出下一步。</p>
        <div className="hero-actions">
          <Link className="primary" href="/diagnose">上传简历开始对照</Link>
          <Link className="ghost" href="/diagnose?job=job-e1662d9b8cfd059f">先看看大模型应用工程师</Link>
        </div>
        <div className="sample-verdict" aria-label="示例方向结论">
          <p className="mono">示例结论</p>
          <h2>你具备大模型应用开发基础，下一步应补充可验证的 RAG 项目结果。</h2>
          <div className="sample-reasons"><span>有 Python、FastAPI 实践证据</span><span>缺少规模、延迟或评测结果</span></div>
        </div>
      </section>
      <section className="home-evidence" aria-labelledby="evidence-title">
        <div>
          <p className="mono">数据依据</p>
          <h2 id="evidence-title">岗位变化先看证据，再做决定</h2>
          <p className="hint">岗位定义、招聘公司和本周期变化都来自同一份公开招聘数据。图谱和发现故事放在这里，诊断结论不会脱离来源。</p>
        </div>
        <div className="evidence-links">
          <Link className="evidence-card" href="/graph"><b>岗位</b><span>查看岗位要求与证据</span></Link>
          <Link className="evidence-card" href="/discover"><b>市场变化</b><span>了解哪些岗位正在形成</span></Link>
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
              <dt>谱内</dt>
              <dd>{feed.in_graph}</dd>
            </div>
          </dl>
        ) : (
          <p className="hint">载入中…</p>
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
              <h2>发现管线</h2>
              <p className="hint">证据按渠道计。和发现页同一份口径。</p>
              <Pipe rows={feed?.pipeline || []} />
            </section>
            <section>
              <h2>技能热度</h2>
              <p className="hint">谱内岗位占比，不是搜索指数。簇内覆盖率过 30% 才入池。</p>
              <Heat rows={feed?.heat || []} />
            </section>
            <section>
              <h2>演化流水</h2>
              <p className="hint">边级事件，不是时间轴控件。</p>
              <EventList rows={feed?.events || []} />
            </section>
          </div>
        </details>
      </aside>
    </main>
  );
}
