"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { cssVar, mountGraph } from "./graph-kit";
import { EventList, Heat, Pipe } from "./feed-bits";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Domain = { id: string; name: string };
type Job = { id: string; name: string; status: string; domain: string };
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
  const canvas = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const [domains, setDomains] = useState<Domain[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [feed, setFeed] = useState<Feed | null>(null);

  useEffect(() => {
    fetch(`${API}/meta`)
      .then((r) => r.json())
      .then((body: { domains?: Domain[] }) => setDomains(Array.isArray(body.domains) ? body.domains : []))
      .catch(() => setDomains([]));
    fetch(`${API}/jobs`)
      .then((r) => r.json())
      .then((rows: Job[]) => setJobs(Array.isArray(rows) ? rows : []))
      .catch(() => setJobs([]));
    fetch(`${API}/feed`)
      .then((r) => r.json())
      .then((body: Feed) => setFeed(body))
      .catch(() => setFeed(null));
  }, []);

  useEffect(() => {
    const el = canvas.current;
    if (!el) return;
    const cInk = cssVar("--color-ink");
    const cPaper = cssVar("--color-paper");
    const cPaper2 = cssVar("--color-paper-2");
    const cAccent = cssVar("--color-accent");
    const cFaint = cssVar("--color-faint");
    const nodes = domains.map((d) => ({ id: `d-${d.id}`, data: { label: d.name, k: "d" } }));
    const jobIds = new Set<string>();
    for (const job of jobs) {
      jobIds.add(job.id);
      nodes.push({
        id: job.id,
        data: { label: job.name, k: job.status === "emerging" ? "e" : "j" },
      });
    }
    const edges = jobs.map((job, i) => ({
      id: `e${i}`,
      source: `d-${job.domain}`,
      target: job.id,
    }));
    return mountGraph(
      el,
      { nodes, edges },
      {
        size: (d: { data?: { k?: string } }) => (d.data?.k === "d" ? [96, 32] : [88, 28]),
        radius: 0,
        fill: (d: { data?: { k?: string } }) => (d.data?.k === "j" ? cInk : cPaper2),
        stroke: (d: { data?: { k?: string } }) =>
          d.data?.k === "e" ? cAccent : d.data?.k === "d" ? cFaint : cInk,
        lineWidth: (d: { data?: { k?: string } }) => (d.data?.k === "e" ? 2 : 1),
        labelText: (d: { data?: { label?: string } }) => d.data?.label || "",
        labelFill: (d: { data?: { k?: string } }) => (d.data?.k === "j" ? cPaper : cInk),
        labelFontSize: 11,
        labelPlacement: "center",
        labelMaxWidth: 88,
        labelWordWrap: true,
      },
      (id) => {
        if (jobIds.has(id)) router.push(`/graph?job=${encodeURIComponent(id)}`);
      },
    );
  }, [domains, jobs, router]);

  return (
    <main id="main" className="atlas">
      <h1 className="sr-only">总览</h1>
      <div className="map-stage">
        <header className="map-orient">
          <p className="mono">四领域 · 点岗位进工作台</p>
          <div className="domains">
            {domains.map((d) => (
              <span key={d.id}>
                {d.name} <b>{jobs.filter((j) => j.domain === d.id).length}</b>
              </span>
            ))}
          </div>
        </header>
        <div id="g6home" ref={canvas} role="img" aria-label="四领域岗位图，点岗位进工作台" />
        <p className="map-legend">
          <span>
            <i className="swatch d" />
            领域
          </span>
          <span>
            <i className="swatch j" />
            成型
          </span>
          <span>
            <i className="swatch e" />
            萌芽
          </span>
        </p>
      </div>
      <aside className="inspector">
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
        {(feed?.stories || []).map((story) => (
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
