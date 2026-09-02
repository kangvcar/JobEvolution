"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { cssVar, mountGraph } from "../graph-kit";

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
  kind?: string;
  category_id?: string | null;
  category?: string | null;
  proficiency?: string;
  levels?: string[];
  sources?: string[];
};
type JobDetail = Job & { sources?: string[]; definition?: { text?: string; type?: string; sources?: string[] }[]; watching?: string[] };
type Slice = {
  categories?: { id: string; name: string }[];
  requires?: Requirement[];
  evidence?: { id: string; company?: string; observed_at?: string; source?: string }[];
  period_delta?: { added?: Requirement[]; expired?: Requirement[] };
};

type EvidenceTarget = Requirement & { expired?: boolean };

export function Workbench() {
  const canvas = useRef<HTMLDivElement>(null);
  const params = useSearchParams();
  const wanted = params.get("job") || params.get("job_id") || "";
  const wantedSkill = params.get("skill_id") || "";
  const [domains, setDomains] = useState<Domain[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [domain, setDomain] = useState("");
  const [category, setCategory] = useState("");
  const [level, setLevel] = useState("");
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState(wanted);
  const [selectedSkill, setSelectedSkill] = useState(wantedSkill);
  const [detail, setDetail] = useState<JobDetail | null>(null);
  const [slice, setSlice] = useState<Slice | null>(null);
  const [evidenceTarget, setEvidenceTarget] = useState<EvidenceTarget | null>(null);
  const [loading, setLoading] = useState(false);
  const [view, setView] = useState<"graph" | "list">("graph");
  const opener = useRef<HTMLElement | null>(null);
  const background = useRef<HTMLElement>(null);

  const closeEvidence = () => {
    setEvidenceTarget(null);
  };

  useEffect(() => {
    const saved = window.sessionStorage.getItem("job-view");
    if (saved === "graph" || saved === "list") setView(saved);
    else if (window.matchMedia("(max-width: 1100px)").matches) setView("list");
  }, []);

  useEffect(() => {
    window.sessionStorage.setItem("job-view", view);
  }, [view]);

  useEffect(() => {
    if (!evidenceTarget) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeEvidence();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [evidenceTarget]);

  useEffect(() => {
    if (background.current) background.current.inert = Boolean(evidenceTarget);
  }, [evidenceTarget]);

  useEffect(() => {
    if (!evidenceTarget) {
      opener.current?.focus();
    }
  }, [evidenceTarget]);

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
    if (wantedSkill) setSelectedSkill(wantedSkill);
  }, [wanted, wantedSkill]);

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
    setEvidenceTarget(null);
    setLoading(true);
    Promise.all([
      fetch(`${API}/jobs/${encodeURIComponent(selected)}`).then((r) => (r.ok ? r.json() : null)),
      fetch(`${API}/graph/jobs/${encodeURIComponent(selected)}`).then((r) => (r.ok ? r.json() : null)),
    ]).then(([job, graph]) => {
      setDetail(job);
      setSlice(graph);
      setLoading(false);
    }).catch(() => {
      setDetail(null);
      setSlice(null);
      setLoading(false);
    });
  }, [selected]);

  useEffect(() => {
    const el = canvas.current;
    if (!el) return;
    const cInk = cssVar("--color-ink");
    const cPaper = cssVar("--color-paper");
    const cPaper2 = cssVar("--color-paper-2");
    const cFall = cssVar("--color-fall");
    const cRise = cssVar("--color-rise");
    const delta = slice?.period_delta || {};
    const added = new Set((delta.added || []).map((skill) => skill.skill_id));
    const expired = new Map((delta.expired || []).map((skill) => [skill.skill_id, skill]));
    const requires = [...(slice?.requires || [])];
    for (const skill of expired.values()) {
      if (!requires.some((item) => item.skill_id === skill.skill_id)) requires.push(skill);
    }
    const categories = [...(slice?.categories || [])];
    for (const skill of requires) {
      const id = skill.category_id || skill.category;
      if (id && !categories.some((category) => category.id === id)) {
        categories.push({ id, name: skill.category || id });
      }
    }
    if (expired.size) categories.push({ id: "expired", name: "本周期失效" });
    const categoryFor = (skill: Requirement) =>
      expired.has(skill.skill_id) ? "expired" : skill.category_id || skill.category || "uncategorized";
    if (requires.some((skill) => categoryFor(skill) === "uncategorized")) {
      categories.push({ id: "uncategorized", name: "未分类" });
    }
    const nodes = [
      { id: "job", data: { label: current?.name || detail?.name || "岗位", k: "job" } },
      ...categories.map((category) => ({ id: `category-${category.id}`, data: { label: category.name, k: "category" } })),
      ...requires.map((skill) => {
        const isDelta = added.has(skill.skill_id);
        const isExpired = expired.has(skill.skill_id);
        return {
          id: `skill-${skill.skill_id}`,
          data: { label: `${isDelta ? "+" : ""}${skill.name}`, k: "skill", selected: skill.skill_id === selectedSkill, delta: isDelta ? "added" : isExpired ? "expired" : "" },
        };
      }),
    ];
    const edges = [
      ...categories.map((category) => ({ id: `job-${category.id}`, source: "job", target: `category-${category.id}` })),
      ...requires.map((skill) => ({ id: `category-${skill.skill_id}`, source: `category-${categoryFor(skill)}`, target: `skill-${skill.skill_id}` })),
    ];
    el.focus();
    return mountGraph(
      el,
      { nodes, edges },
      {
        size: (d: { data?: { k?: string } }) => (d.data?.k === "job" ? [104, 34] : d.data?.k === "category" ? [108, 30] : [120, 28]),
        radius: 0,
        fill: (d: { data?: { k?: string } }) => (d.data?.k === "job" ? cInk : d.data?.k === "category" ? cPaper2 : cPaper),
        stroke: (d: { data?: { k?: string; delta?: string; selected?: boolean } }) => d.data?.selected ? cInk : d.data?.delta === "added" ? cFall : d.data?.delta === "expired" ? cRise : d.data?.k === "job" ? cInk : cssVar("--color-rule"),
        lineWidth: (d: { data?: { k?: string; delta?: string } }) => d.data?.delta ? 2 : 1,
        labelText: (d: { data?: { label?: string } }) => d.data?.label || "",
        labelFill: (d: { data?: { k?: string } }) => d.data?.k === "job" ? cPaper : cInk,
        labelFontSize: 11,
        labelPlacement: "center",
        labelMaxWidth: 116,
        labelWordWrap: true,
      },
      (id) => {
        if (!id.startsWith("skill-")) return;
        const skillId = id.slice("skill-".length);
        const expired = (slice?.period_delta?.expired || []).find((skill) => skill.skill_id === skillId);
        const skill = (slice?.requires || []).find((item) => item.skill_id === skillId) || expired;
        if (skill) {
          opener.current = el;
          setSelectedSkill(skillId);
          setEvidenceTarget({ ...skill, expired: Boolean(expired) });
        }
      },
    );
  }, [current?.name, detail?.name, slice, selectedSkill, view]);

  const skillButton = (skill: Requirement) => (
    <li key={skill.skill_id} data-selected={skill.skill_id === selectedSkill ? "1" : undefined}>
      <button type="button" className="skill-link" onClick={(event) => { opener.current = event.currentTarget; setSelectedSkill(skill.skill_id); setEvidenceTarget(skill); }}>{skill.name}</button>
    </li>
  );

  return (
    <>
    <main id="main" ref={background} className="graph-page">
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
          <p className="empty">当前筛选没有有效岗位要求，请换个筛选</p>
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
          <span className="view-tabs"><button type="button" aria-pressed={view === "graph"} onClick={() => setView("graph")}>图谱</button><button type="button" aria-pressed={view === "list"} onClick={() => setView("list")}>要求清单</button></span>
          <span className="g-legend">
            <span>
              <i className="swatch add" />
              本周期新增
            </span>
            <span>
              <i className="swatch exp" />
              本周期失效
            </span>
          </span>
        </p>
        {view === "graph" ? <div
          id="g6"
          ref={canvas}
          tabIndex={0}
          role="application"
          aria-label="岗位要求关系图"
        /> : <div className="requirement-list" aria-label="岗位要求清单">
          {(["required", "bonus"] as const).map((kind) => <section key={kind}><h2>{kind === "required" ? "必备" : "加分"}</h2><ul>{visibleRequires.filter((skill) => (kind === "required" ? skill.kind !== "bonus" : skill.kind === "bonus")).map((skill) => <li key={skill.skill_id}><button type="button" onClick={() => { opener.current = document.activeElement as HTMLElement; setSelectedSkill(skill.skill_id); setEvidenceTarget(skill); }}>{skill.name}</button><span>{skill.proficiency || "未标熟练级"}</span></li>)}</ul></section>)}{detail?.watching?.length ? <section><h2>观测中</h2><p className="hint">市场开始提，但还没进要求，不算你的缺口。</p><p className="watching-ids">{detail.watching.join("、")}</p></section> : null}</div>}
      </section>
      <aside className="graph-detail">
        <h1>{detail?.name || current?.name || "图谱"}</h1>
        {detail ? (
          <>
            <p>状态：{detail.status === "formed" ? "成型" : "萌芽"}</p>
            <p>去重招聘公司：{detail.sources?.join("、") || "暂无"}</p>
            {detail.definition?.length ? <section className="job-definition"><h2>岗位定义</h2>{detail.definition.slice(0, 5).map((claim, index) => <p key={`${claim.text}-${index}`}>{claim.text}</p>)}</section> : <p className="hint">岗位定义审核中</p>}
            <p>本周期新增 {slice?.period_delta?.added?.length || 0} 项，失效 {slice?.period_delta?.expired?.length || 0} 项。</p>
            <h2>技能点</h2>
            {slice?.categories?.filter((sliceCategory) => visibleRequires.some((skill) => skill.category === sliceCategory.name)).map((sliceCategory) => (
              <section key={sliceCategory.id}>
                <h3>{sliceCategory.name}</h3>
                <ul>
                  {visibleRequires.filter((skill) => skill.category === sliceCategory.name).map(skillButton)}
                </ul>
              </section>
            ))}
            {!(slice?.categories?.length) && <ul>{visibleRequires.map(skillButton)}</ul>}
            {slice && visibleRequires.length === 0 && <p className="empty">当前筛选没有技能点，请换个筛选</p>}
            <Link className="primary" href={`/diagnose?job_id=${encodeURIComponent(detail.id)}`}>
            对照简历
            </Link>
          </>
        ) : loading ? (
          <p className="empty">载入中…</p>
        ) : (
          <p className="empty">未接数据</p>
        )}
      </aside>
    </main>
    {evidenceTarget && (
      <>
        <button type="button" className="evidence-backdrop" aria-label="关闭证据抽屉" onClick={closeEvidence} />
        <aside className="evidence-drawer" role="dialog" aria-modal="true" aria-labelledby="evidence-title">
          <header><div><p className="mono">岗位要求证据</p><h2 id="evidence-title">{evidenceTarget.name}</h2></div><button type="button" onClick={closeEvidence} aria-label="关闭证据抽屉">关闭</button></header>
          {evidenceTarget.expired && <p className="evidence-status">本周期失效</p>}
          {(() => {
            const all = slice?.evidence || [];
            const ids = evidenceTarget.sources || [];
            const matched = ids.length ? all.filter((item) => ids.includes(item.id)) : all;
            const rows = matched.length ? matched : all;
            return rows.length ? (
              <ul className="evidence-list">
                {rows.map((item) => <li key={item.id}><strong>{item.company || item.id}</strong><span>{item.id} · {item.source || "未知来源"} · {(item.observed_at || "").slice(0, 10)}</span></li>)}
              </ul>
            ) : <p className="empty">暂无证据记录</p>;
          })()}
        </aside>
      </>
    )}
    </>
  );
}
