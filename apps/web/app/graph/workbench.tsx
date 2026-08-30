"use client";

import { Graph } from "@antv/g6";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const CATEGORIES = ["语言", "框架", "平台", "工程", "领域知识"] as const;
const LEVELS = [
  { value: "", label: "不限" },
  { value: "junior", label: "初" },
  { value: "mid", label: "中" },
  { value: "senior", label: "高" },
] as const;

type Domain = { id: string; name: string };
type Job = { id: string; name: string; status?: "emerging" | "formed" };
type Requirement = {
  skill_id: string;
  name: string;
  category?: string | null;
  kind?: string;
  proficiency?: string;
  levels?: string[];
};
type JobDetail = Job & { sources?: string[] };
type Slice = {
  categories?: { id: string; name: string }[];
  requires?: Requirement[];
  period_delta?: { added?: Requirement[]; promoted?: Requirement[]; expired?: Requirement[] };
};

export function Workbench() {
  const canvas = useRef<HTMLDivElement>(null);
  const params = useSearchParams();
  const wanted = params.get("job") || params.get("job_id") || "";
  const [domains, setDomains] = useState<Domain[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [domain, setDomain] = useState("");
  const [category, setCategory] = useState("");
  const [level, setLevel] = useState("");
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState(wanted);
  const [detail, setDetail] = useState<JobDetail | null>(null);
  const [slice, setSlice] = useState<Slice | null>(null);

  useEffect(() => {
    fetch(`${API}/meta`)
      .then((r) => r.json())
      .then((body: { domains?: Domain[] }) =>
        setDomains(Array.isArray(body.domains) ? body.domains : []),
      )
      .catch(() => setDomains([]));
  }, []);

  useEffect(() => {
    const params = new URLSearchParams();
    if (domain) params.set("domain", domain);
    if (q) params.set("q", q);
    if (category) params.set("category", category);
    if (level) params.set("level", level);
    const suffix = params.toString();
    fetch(`${API}/jobs${suffix ? `?${suffix}` : ""}`)
      .then((r) => r.json())
      .then((rows: Job[]) => setJobs(Array.isArray(rows) ? rows : []))
      .catch(() => setJobs([]));
  }, [domain, q, category, level]);

  useEffect(() => {
    if (wanted) setSelected(wanted);
  }, [wanted]);

  useEffect(() => {
    if (jobs[0] && !jobs.some((job) => job.id === selected)) setSelected(jobs[0].id);
  }, [jobs, selected]);

  const current = jobs.find((job) => job.id === selected);
  const visibleRequires = (slice?.requires || []).filter(
    (skill) => (!category || skill.category === category) && (!level || skill.levels?.includes(level)),
  );

  useEffect(() => {
    if (!selected) {
      setDetail(null);
      setSlice(null);
      return;
    }
    setDetail(null);
    setSlice(null);
    Promise.all([
      fetch(`${API}/jobs/${encodeURIComponent(selected)}`).then((r) => (r.ok ? r.json() : null)),
      fetch(`${API}/graph/jobs/${encodeURIComponent(selected)}`).then((r) => (r.ok ? r.json() : null)),
    ]).then(([job, graph]) => {
      setDetail(job);
      setSlice(graph);
    }).catch(() => {
      setDetail(null);
      setSlice(null);
    });
  }, [selected]);

  useEffect(() => {
    const el = canvas.current;
    if (!el) return;
    const graph = new Graph({
      container: el,
      autoFit: "view",
      data: { nodes: [], edges: [] },
      behaviors: ["drag-canvas", "zoom-canvas"],
    });
    graph.render();
    el.focus();
    const onResize = () => {
      graph.resize();
      graph.fitView();
    };
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      graph.destroy();
    };
  }, []);

  return (
    <main id="main" className="graph-page">
      <aside className="graph-rail">
        <label>
          领域
          <select aria-label="领域" value={domain} onChange={(e) => setDomain(e.target.value)}>
            <option value="">全部</option>
            {domains.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          技能类目
          <select aria-label="技能类目" value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">全部</option>
            {CATEGORIES.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label>
          适用级别
          <select aria-label="适用级别" value={level} onChange={(e) => setLevel(e.target.value)}>
            {LEVELS.map((level) => (
              <option key={level.value} value={level.value}>
                {level.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          搜索岗位
          <input type="search" aria-label="搜索岗位" value={q} onChange={(e) => setQ(e.target.value)} />
        </label>
        {jobs.length === 0 ? (
          <p className="empty">当前筛选没有仍有要求边的技能点，请换个筛选</p>
        ) : (
          <ul className="job-list">
            {jobs.map((job) => (
              <li key={job.id}>
                <button
                  type="button"
                  className="job-item"
                  data-current={job.id === selected ? "1" : undefined}
                  onClick={() => setSelected(job.id)}
                >
                  {job.name}
                </button>
              </li>
            ))}
          </ul>
        )}
      </aside>
      <section className="graph-stage">
        <p className="graph-hint">
          岗位 → 类目 → 技能点。本周期新增或升值、已写失效时间会标在切片差分上。无技能点时画布为空。
        </p>
        <div
          id="g6"
          ref={canvas}
          tabIndex={0}
          role="application"
          aria-label="岗位切片画布"
        />
      </section>
      <aside className="graph-detail">
        <h1>{detail?.name || current?.name || "图谱"}</h1>
        {detail ? (
          <>
            <p>状态：{detail.status === "formed" ? "成型" : "萌芽"}</p>
            <p>独立源：{detail.sources?.join("、") || "暂无"}</p>
            <h2>技能点</h2>
            {slice?.categories?.filter((sliceCategory) => visibleRequires.some((skill) => skill.category === sliceCategory.name)).map((sliceCategory) => (
              <section key={sliceCategory.id}>
                <h3>{sliceCategory.name}</h3>
                <ul>
                  {visibleRequires.filter((skill) => skill.category === sliceCategory.name).map((skill) => (
                    <li key={skill.skill_id}>{skill.name}</li>
                  ))}
                </ul>
              </section>
            ))}
            {!(slice?.categories?.length) && (
              <ul>{visibleRequires.map((skill) => <li key={skill.skill_id}>{skill.name}</li>)}</ul>
            )}
            {slice && visibleRequires.length === 0 && <p className="empty">当前筛选没有技能点，请换个筛选</p>}
            <Link className="primary" href={`/diagnose?job_id=${encodeURIComponent(detail.id)}`}>
            对照简历
            </Link>
          </>
        ) : (
          <p>未接数据</p>
        )}
      </aside>
    </main>
  );
}
