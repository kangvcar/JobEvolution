"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FlowWorkbenchCanvas, RECENT_DAYS, SECTOR_COLOR, SECTOR_ORDER, sectorOf, type FlowSkillData, type Neighbor } from "./flow-canvas";
import "./graph.css";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/* ---------- 词表 ---------- */
const CATEGORIES = ["语言", "框架", "平台", "工程", "领域知识"] as const;
const LEVELS = [
  { value: "junior", label: "初级" },
  { value: "mid", label: "中级" },
  { value: "senior", label: "高级" },
] as const;
const PROF: Record<string, { label: string; n: number }> = {
  aware: { label: "了解", n: 1 },
  able: { label: "熟练", n: 2 },
  expert: { label: "精通", n: 3 },
};
const LAYER: Record<string, string> = { high: "高置信", mid: "中置信", low: "低置信" };
const STATUS: Record<string, string> = { formed: "成型", emerging: "萌芽", candidate: "候选" };
const KINDS = [
  { value: "", label: "全部" },
  { value: "required", label: "必备" },
  { value: "bonus", label: "加分" },
] as const;
const WATCHING_PAGE = 40;

const profLabel = (v?: string) => (v ? PROF[v]?.label || v : "");
const profN = (v?: string) => (v ? PROF[v]?.n || 0 : 0);
const fmtDate = (s?: string | null) => (s ? s.slice(0, 10) : "");
const statusLabel = (s?: string) => (s ? STATUS[s] || s : "");

/* ---------- 类型 ---------- */
type Domain = { id: string; name: string };
type Job = { id: string; name: string; status?: string; domain?: string };
type JobStat = { id: string; n_sources?: number; n_added?: number; n_expired?: number; last_change?: string };
type JobRow = Job & JobStat;
type Requirement = {
  skill_id: string;
  name: string;
  kind?: string;
  category_id?: string | null;
  category?: string | null;
  proficiency?: string;
  levels?: string[];
  sources?: string[];
  excerpt?: string;
  confidence?: number;
  layer?: string;
  valid_from?: string | null;
  group_id?: string | null;
  min_required?: number | null;
};
type Evidence = { id: string; company?: string; observed_at?: string; source?: string; retracted?: boolean };
type JobEvent = { id: string; kind?: string; at?: string; review?: string; skill_name?: string; excerpt?: string };
type JobDetail = Job & {
  sources?: string[];
  definition?: { text?: string; type?: string }[];
  watching?: string[];
  events?: JobEvent[];
};
type Slice = {
  categories?: { id: string; name: string }[];
  requires?: Requirement[];
  evidence?: Evidence[];
  period_delta?: { added?: Requirement[]; expired?: Requirement[] };
};
type Dossier = { n_sources?: number; n_window?: number; neighbor?: Neighbor | null };
type JobBundle = { detail: JobDetail; slice: Slice; dossier: Dossier | null };

type SortKey = "name" | "category" | "proficiency" | "sources" | "confidence" | "valid_from";

const fetchJson = async <T,>(url: string, signal?: AbortSignal): Promise<T> => {
  const r = await fetch(url, { signal });
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r.json() as Promise<T>;
};

/* ---------- 小组件 ---------- */
function StatusTag({ status }: { status?: string }) {
  return <span className={`gw-tag is-${status || "unknown"}`}>{statusLabel(status) || "未知"}</span>;
}

function Meter({ value, label }: { value?: string; label?: boolean }) {
  const n = profN(value);
  return (
    <span className="gw-meter" title={`熟练级 ${profLabel(value) || "未标"}`}>
      {[1, 2, 3].map((i) => (
        <i key={i} className={i <= n ? "on" : ""} />
      ))}
      {label !== false && <em>{profLabel(value) || "未标"}</em>}
    </span>
  );
}

function CatDot({ category }: { category?: string | null }) {
  return <i className="gw-cat-dot" style={{ background: SECTOR_COLOR[sectorOf(category)] }} aria-hidden="true" />;
}

function SortIcon({ active, dir }: { active: boolean; dir: "asc" | "desc" }) {
  return (
    <span className={`gw-sort${active ? " on" : ""}`} aria-hidden="true">
      {active ? (dir === "asc" ? "↑" : "↓") : "↕"}
    </span>
  );
}

/* ---------- 主组件 ---------- */
export function Workbench() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  // URL 是视图状态的唯一来源：岗位、技能、视图、过滤条件都能分享和后退。
  const urlJob = params.get("job") || params.get("job_id") || "";
  const urlSkill = params.get("skill") || params.get("skill_id") || "";
  const view = params.get("view") === "table" ? "table" : "graph";
  const cat = params.get("cat") || "";
  const level = params.get("level") || "";
  const kind = params.get("kind") || "";
  const recent = params.get("recent") === "1";

  const setParams = useCallback(
    (patch: Record<string, string | null>) => {
      const next = new URLSearchParams(params.toString());
      next.delete("job_id");
      next.delete("skill_id");
      for (const [k, v] of Object.entries(patch)) {
        if (v) next.set(k, v);
        else next.delete(k);
      }
      const qs = next.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [params, pathname, router],
  );

  const [domains, setDomains] = useState<Domain[]>([]);
  const [period, setPeriod] = useState("");
  const [jobs, setJobs] = useState<JobRow[] | null>(null);
  const [jobsError, setJobsError] = useState("");
  const [domain, setDomain] = useState("");
  const [q, setQ] = useState("");
  const [skillQuery, setSkillQuery] = useState("");
  const [bundle, setBundle] = useState<JobBundle | null>(null);
  const [bundleFor, setBundleFor] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [tab, setTab] = useState<"requires" | "evidence" | "watching">("requires");
  const [watchingLimit, setWatchingLimit] = useState(WATCHING_PAGE);
  const [sort, setSort] = useState<{ key: SortKey; dir: "asc" | "desc" }>({ key: "sources", dir: "desc" });
  const [narrow, setNarrow] = useState(false);
  const [railOpen, setRailOpen] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(true);

  const railSearch = useRef<HTMLInputElement | null>(null);
  const skillOpener = useRef<HTMLElement | null>(null);

  /* 窄屏：岗位列表与检查面板改为抽屉 */
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 960px)");
    const apply = () => {
      setNarrow(mq.matches);
      if (mq.matches) setInspectorOpen(false);
    };
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);

  /* 元信息 + 岗位列表（带卷宗统计） */
  useEffect(() => {
    const ac = new AbortController();
    fetchJson<{ domains?: Domain[]; graph_release?: { period?: string } }>(`${API}/meta`, ac.signal)
      .then((body) => {
        setDomains(body.domains || []);
        setPeriod(body.graph_release?.period || "");
      })
      .catch(() => {});
    Promise.all([
      fetchJson<Job[]>(`${API}/jobs`, ac.signal),
      fetchJson<{ formed?: JobStat[]; emerging?: JobStat[] }>(`${API}/discover`, ac.signal).catch(() => ({}) as { formed?: JobStat[]; emerging?: JobStat[] }),
    ])
      .then(([rows, disc]) => {
        const stats = new Map<string, JobStat>();
        for (const s of [...(disc.formed || []), ...(disc.emerging || [])]) stats.set(s.id, s);
        setJobs(rows.map((j) => ({ ...j, ...stats.get(j.id) })));
        setJobsError("");
      })
      .catch((e: Error) => {
        if (e.name === "AbortError") return;
        setJobs([]);
        setJobsError("岗位列表加载失败，请确认 API 服务已启动。");
      });
    return () => ac.abort();
  }, []);

  const filteredJobs = useMemo(() => {
    const list = jobs || [];
    const needle = q.trim().toLowerCase();
    return list.filter((j) => (!domain || j.domain === domain) && (!needle || j.name.toLowerCase().includes(needle)));
  }, [jobs, domain, q]);

  const selected = useMemo(() => {
    if (!jobs) return urlJob;
    if (urlJob && jobs.some((j) => j.id === urlJob)) return urlJob;
    return filteredJobs[0]?.id || jobs[0]?.id || "";
  }, [jobs, urlJob, filteredJobs]);
  const currentRow = jobs?.find((j) => j.id === selected);

  /* 岗位卷宗 */
  useEffect(() => {
    if (!selected) return;
    const ac = new AbortController();
    setLoading(true);
    setLoadError("");
    Promise.all([
      fetchJson<JobDetail>(`${API}/jobs/${encodeURIComponent(selected)}`, ac.signal),
      fetchJson<Slice>(`${API}/graph/jobs/${encodeURIComponent(selected)}`, ac.signal),
      fetchJson<Dossier>(`${API}/discover/${encodeURIComponent(selected)}`, ac.signal).catch(() => null),
    ])
      .then(([detail, slice, dossier]) => {
        setBundle({ detail, slice, dossier });
        setBundleFor(selected);
        setWatchingLimit(WATCHING_PAGE);
        setLoading(false);
      })
      .catch((e: Error) => {
        if (e.name === "AbortError") return;
        setLoadError("岗位数据加载失败。");
        setLoading(false);
      });
    return () => ac.abort();
  }, [selected]);

  const stale = bundleFor !== selected;
  const detail = bundle?.detail;
  const slice = bundle?.slice;
  const dossier = bundle?.dossier;

  const requires = useMemo(() => slice?.requires || [], [slice]);
  const addedIds = useMemo(() => new Set((slice?.period_delta?.added || []).map((r) => r.skill_id)), [slice]);
  const expiredIds = useMemo(() => new Set((slice?.period_delta?.expired || []).map((r) => r.skill_id)), [slice]);
  const evidenceById = useMemo(() => new Map((slice?.evidence || []).map((e) => [e.id, e])), [slice]);
  const recentSince = useMemo(
    () => new Date(new Date(period || Date.now()).getTime() - RECENT_DAYS * 86400000).toISOString().slice(0, 10),
    [period],
  );

  const visible = useMemo(() => {
    const needle = skillQuery.trim().toLowerCase();
    return requires.filter(
      (r) =>
        (!cat || sectorOf(r.category) === cat) &&
        (!level || r.levels?.includes(level)) &&
        (!kind || (kind === "bonus" ? r.kind === "bonus" : r.kind !== "bonus")) &&
        (!recent || fmtDate(r.valid_from) >= recentSince) &&
        (!needle || r.name.toLowerCase().includes(needle)),
    );
  }, [requires, cat, level, kind, recent, recentSince, skillQuery]);
  const filtersActive = Boolean(cat || level || kind || recent || skillQuery);
  const visibleIds = useMemo(() => (filtersActive ? new Set(visible.map((r) => r.skill_id)) : null), [visible, filtersActive]);

  const requiredCount = requires.filter((r) => r.kind !== "bonus").length;
  const bonusCount = requires.length - requiredCount;
  const selectedReq = useMemo(() => requires.find((r) => r.skill_id === urlSkill) || null, [requires, urlSkill]);

  const groups = useMemo(() => {
    const m = new Map<string, Requirement[]>();
    for (const r of requires) if (r.group_id) m.set(r.group_id, [...(m.get(r.group_id) || []), r]);
    return m;
  }, [requires]);

  const sorted = useMemo(() => {
    const dir = sort.dir === "asc" ? 1 : -1;
    const val = (r: Requirement): string | number => {
      switch (sort.key) {
        case "name":
          return r.name;
        case "category":
          return SECTOR_ORDER.indexOf(sectorOf(r.category) as (typeof SECTOR_ORDER)[number]);
        case "proficiency":
          return profN(r.proficiency);
        case "sources":
          return r.sources?.length ?? 0;
        case "confidence":
          return r.confidence ?? 0;
        case "valid_from":
          return fmtDate(r.valid_from);
      }
    };
    return [...visible].sort((a, b) => {
      const va = val(a);
      const vb = val(b);
      const c = typeof va === "number" && typeof vb === "number" ? va - vb : String(va).localeCompare(String(vb), "zh-Hans-CN");
      return c !== 0 ? c * dir : a.name.localeCompare(b.name, "zh-Hans-CN");
    });
  }, [visible, sort]);

  const watchingRanked = useMemo(() => {
    const counts = new Map<string, number>();
    for (const e of detail?.events || []) if (e.skill_name) counts.set(e.skill_name, (counts.get(e.skill_name) || 0) + 1);
    return (detail?.watching || [])
      .map((name) => ({ name, n: counts.get(name) || 0 }))
      .sort((a, b) => b.n - a.n || a.name.localeCompare(b.name, "zh-Hans-CN"));
  }, [detail]);

  const eventStats = useMemo(() => {
    const ev = detail?.events || [];
    return { total: ev.length, approved: ev.filter((e) => e.review === "approved").length, rejected: ev.filter((e) => e.review === "rejected").length };
  }, [detail]);

  const flowSkills = useMemo<FlowSkillData[]>(
    () => requires.map((r) => ({ ...r, id: r.skill_id, added: addedIds.has(r.skill_id) })),
    [requires, addedIds],
  );

  /* 交互 */
  const pickJob = (id: string) => {
    setParams({ job: id, skill: null });
    setRailOpen(false);
  };
  const pickSkill = (id: string, opener?: HTMLElement | null) => {
    skillOpener.current = opener || null;
    setParams({ skill: id });
    setInspectorOpen(true);
  };
  const closeSkill = useCallback(() => {
    setParams({ skill: null });
    const el = skillOpener.current;
    skillOpener.current = null;
    requestAnimationFrame(() => el?.focus());
  }, [setParams]);
  const clearFilters = () => {
    setSkillQuery("");
    setParams({ cat: null, level: null, kind: null, recent: null });
  };
  const toggleSort = (key: SortKey) =>
    setSort((s) => (s.key === key ? { key, dir: s.dir === "asc" ? "desc" : "asc" } : { key, dir: key === "name" || key === "category" ? "asc" : "desc" }));

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const typing = target && (target.tagName === "INPUT" || target.tagName === "SELECT" || target.tagName === "TEXTAREA");
      if (e.key === "Escape") {
        if (railOpen) setRailOpen(false);
        else if (urlSkill) closeSkill();
        else if (narrow && inspectorOpen) setInspectorOpen(false);
      } else if (e.key === "/" && !typing) {
        e.preventDefault();
        if (narrow) setRailOpen(true);
        requestAnimationFrame(() => railSearch.current?.focus());
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [railOpen, urlSkill, narrow, inspectorOpen, closeSkill]);

  const onRailKey = (e: React.KeyboardEvent<HTMLUListElement>) => {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    const idx = filteredJobs.findIndex((j) => j.id === selected);
    const next = filteredJobs[Math.min(filteredJobs.length - 1, Math.max(0, idx + (e.key === "ArrowDown" ? 1 : -1)))];
    if (next && next.id !== selected) {
      pickJob(next.id);
      requestAnimationFrame(() => (e.currentTarget.querySelector(`[data-id="${next.id}"]`) as HTMLElement | null)?.focus());
    }
  };

  const domainName = (id?: string) => domains.find((d) => d.id === id)?.name || id || "";
  const jobName = detail?.name || currentRow?.name || "";
  const jobStatus = detail?.status || currentRow?.status;
  const jobsCount = jobs?.length ?? 0;

  /* ---------- 渲染 ---------- */
  const rail = (
    <aside className="gw-rail" aria-label="岗位列表">
      <div className="gw-rail-head">
        <label className="gw-search">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <circle cx="11" cy="11" r="7" />
            <path d="m20 20-3.5-3.5" />
          </svg>
          <input
            ref={railSearch}
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="搜索岗位"
            aria-label="搜索岗位"
          />
          <kbd aria-hidden="true">/</kbd>
        </label>
        <select className="gw-select" aria-label="技术领域" value={domain} onChange={(e) => setDomain(e.target.value)}>
          <option value="">全部领域</option>
          {domains.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
      </div>
      <div className="gw-rail-count">
        {jobs === null ? "载入中" : `${filteredJobs.length} / ${jobsCount} 个岗位`}
      </div>
      {jobsError && <p className="gw-error">{jobsError}</p>}
      <ul className="gw-joblist" role="listbox" aria-label="岗位" onKeyDown={onRailKey}>
        {jobs === null &&
          Array.from({ length: 6 }, (_, i) => (
            <li key={i} className="gw-skel-row" aria-hidden="true">
              <span />
              <span />
            </li>
          ))}
        {filteredJobs.map((j) => {
          const on = j.id === selected;
          return (
            <li key={j.id} role="presentation">
              <button
                type="button"
                role="option"
                aria-selected={on}
                data-id={j.id}
                tabIndex={on ? 0 : -1}
                className={`gw-jobrow${on ? " on" : ""}`}
                onClick={() => pickJob(j.id)}
              >
                <span className="gw-jobrow-top">
                  <span className="gw-jobrow-name">{j.name}</span>
                  <StatusTag status={j.status} />
                </span>
                <span className="gw-jobrow-meta mono">
                  <span>{j.n_sources ?? "–"} 源</span>
                  <span>本期 {j.n_added != null ? `+${j.n_added}` : "–"}</span>
                  <span>{domainName(j.domain)}</span>
                </span>
              </button>
            </li>
          );
        })}
        {jobs && filteredJobs.length === 0 && <li className="gw-empty">没有匹配的岗位</li>}
      </ul>
    </aside>
  );

  const evidenceRows = (ids?: string[]) => {
    const all = slice?.evidence || [];
    const rows = ids?.length ? all.filter((e) => ids.includes(e.id)) : all;
    return [...rows].sort((a, b) => (b.observed_at || "").localeCompare(a.observed_at || ""));
  };

  const renderEvidence = (ids?: string[], compact?: boolean) => {
    const rows = evidenceRows(ids);
    if (!rows.length) return <p className="gw-empty">暂无 JD 快照。</p>;
    return (
      <ol className={`gw-evlist${compact ? " compact" : ""}`}>
        {rows.map((e) => (
          <li key={e.id} className={e.retracted ? "is-retracted" : ""}>
            <span className="gw-ev-company">{e.company || "未知企业"}</span>
            <span className="gw-ev-date mono">{fmtDate(e.observed_at) || "—"}</span>
            <span className="gw-ev-id mono" title={e.id}>
              {e.source || "ats"} · {e.id.replace(/^jd-/, "").slice(0, 8)}
              {e.retracted ? " · 已撤回" : ""}
            </span>
          </li>
        ))}
      </ol>
    );
  };

  const skillPane = selectedReq && (
    <div className="gw-skill" key={selectedReq.skill_id}>
      <div className="gw-pane-head">
        <button type="button" className="gw-back" onClick={closeSkill}>
          ← {jobName}
        </button>
      </div>
      <div className="gw-pane-body">
        <p className="gw-eyebrow">
          <CatDot category={selectedReq.category} />
          {sectorOf(selectedReq.category)}
          <span className="gw-dot" />
          {selectedReq.kind === "bonus" ? "加分要求" : "必备要求"}
          {addedIds.has(selectedReq.skill_id) && (
            <>
              <span className="gw-dot" />
              <span className="gw-new">本期新增</span>
            </>
          )}
          {expiredIds.has(selectedReq.skill_id) && (
            <>
              <span className="gw-dot" />
              <span className="gw-exp">本期失效</span>
            </>
          )}
        </p>
        <h2 className="gw-skill-title">{selectedReq.name}</h2>

        <dl className="gw-kv">
          <div>
            <dt>熟练级</dt>
            <dd>
              <Meter value={selectedReq.proficiency} />
            </dd>
          </div>
          <div>
            <dt>置信</dt>
            <dd className="mono">
              {selectedReq.layer ? LAYER[selectedReq.layer] || selectedReq.layer : "—"}
              {selectedReq.confidence != null ? ` · ${selectedReq.confidence.toFixed(2)}` : ""}
            </dd>
          </div>
          <div>
            <dt>独立源</dt>
            <dd className="mono">{selectedReq.sources?.length ?? 0} 家</dd>
          </div>
          <div>
            <dt>生效自</dt>
            <dd className="mono">{fmtDate(selectedReq.valid_from) || "—"}</dd>
          </div>
          <div>
            <dt>适用级别</dt>
            <dd>
              {selectedReq.levels?.length
                ? selectedReq.levels.map((l) => LEVELS.find((x) => x.value === l)?.label || l).join(" / ")
                : "—"}
            </dd>
          </div>
        </dl>

        {selectedReq.excerpt && (
          <blockquote className="gw-quote">
            <span className="gw-eyebrow">JD 原文摘录</span>
            <p>{selectedReq.excerpt}</p>
          </blockquote>
        )}

        {selectedReq.group_id && (groups.get(selectedReq.group_id)?.length || 0) > 1 && (
          <section className="gw-section">
            <h3>
              同组任选 {selectedReq.min_required || 1} 项
            </h3>
            <ul className="gw-alt">
              {groups.get(selectedReq.group_id)!.map((r) => (
                <li key={r.skill_id}>
                  {r.skill_id === selectedReq.skill_id ? (
                    <strong>{r.name}</strong>
                  ) : (
                    <button type="button" className="gw-link" onClick={(e) => pickSkill(r.skill_id, e.currentTarget)}>
                      {r.name}
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </section>
        )}

        <section className="gw-section">
          <h3>
            支持此要求的 JD 快照 <span className="mono mute">{selectedReq.sources?.length ?? 0}</span>
          </h3>
          {renderEvidence(selectedReq.sources)}
        </section>
      </div>
      <div className="gw-pane-foot">
        <Link className="gw-btn solid block" href={`/diagnose?job_id=${encodeURIComponent(selected)}`}>
          对照我的简历 →
        </Link>
      </div>
    </div>
  );

  const jobPane = (
    <div className="gw-job">
      <div className="gw-pane-head gw-job-head">
        <div className="gw-job-title-row">
          <h2>{jobName || "岗位"}</h2>
          <StatusTag status={jobStatus} />
        </div>
        <p className="gw-job-meta mono">
          {domainName(detail?.domain || currentRow?.domain)}
          <span className="gw-dot" />
          {dossier?.n_sources ?? currentRow?.n_sources ?? "–"} 独立源
          <span className="gw-dot" />
          90 天 {dossier?.n_window ?? "–"} 家
          {currentRow?.last_change ? (
            <>
              <span className="gw-dot" />
              最近变化 {currentRow.last_change}
            </>
          ) : null}
        </p>
        {narrow && (
          <button type="button" className="gw-icon-btn gw-pane-close" aria-label="收起面板" onClick={() => setInspectorOpen(false)}>
            ✕
          </button>
        )}
      </div>

      <dl className="gw-stats">
        <div>
          <dt>必备</dt>
          <dd className="mono">{requiredCount}</dd>
        </div>
        <div>
          <dt>加分</dt>
          <dd className="mono">{bonusCount}</dd>
        </div>
        <div>
          <dt>本期</dt>
          <dd className="mono">
            +{slice?.period_delta?.added?.length ?? 0}
            {slice?.period_delta?.expired?.length ? ` / −${slice.period_delta.expired.length}` : ""}
          </dd>
        </div>
        <div>
          <dt>观测中</dt>
          <dd className="mono">{detail?.watching?.length ?? 0}</dd>
        </div>
      </dl>

      <div className="gw-tabs" role="tablist" aria-label="岗位信息">
        {(
          [
            ["requires", `要求 ${visible.length}${filtersActive ? ` / ${requires.length}` : ""}`],
            ["evidence", `证据 ${slice?.evidence?.length ?? 0}`],
            ["watching", `观测中 ${detail?.watching?.length ?? 0}`],
          ] as const
        ).map(([key, label]) => (
          <button key={key} type="button" role="tab" aria-selected={tab === key} className={tab === key ? "on" : ""} onClick={() => setTab(key)}>
            {label}
          </button>
        ))}
      </div>

      <div className="gw-pane-body" role="tabpanel">
        {tab === "requires" && (
          <>
            {requires.length === 0 && !loading && (
              <p className="gw-empty">
                该岗位还没有通过审核的要求边。候选要求会在达到簇内覆盖率门槛并经双源验证后进入图谱。
              </p>
            )}
            {SECTOR_ORDER.map((sector) => {
              const rows = visible.filter((r) => sectorOf(r.category) === sector);
              if (!rows.length) return null;
              return (
                <section key={sector} className="gw-group">
                  <h3>
                    <CatDot category={sector} />
                    {sector}
                    <span className="mono mute">{rows.length}</span>
                  </h3>
                  <ul className="gw-reqlist">
                    {rows.map((r) => (
                      <li key={r.skill_id}>
                        <button
                          type="button"
                          className={`gw-req${r.skill_id === urlSkill ? " on" : ""}${r.kind === "bonus" ? " is-bonus" : ""}`}
                          onClick={(e) => pickSkill(r.skill_id, e.currentTarget)}
                        >
                          <span className="gw-req-name">
                            {r.name}
                            {r.kind === "bonus" && <span className="gw-mini">加分</span>}
                            {addedIds.has(r.skill_id) && <span className="gw-mini new">新</span>}
                            {expiredIds.has(r.skill_id) && <span className="gw-mini exp">失效</span>}
                          </span>
                          <Meter value={r.proficiency} label={false} />
                          <span className="gw-req-src mono">{r.sources?.length ?? 0} 源</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </section>
              );
            })}
            {requires.length > 0 && visible.length === 0 && (
              <p className="gw-empty">
                当前过滤条件下没有要求。
                <button type="button" className="gw-link" onClick={clearFilters}>
                  清除过滤
                </button>
              </p>
            )}
          </>
        )}

        {tab === "evidence" && (
          <>
            {detail?.definition && detail.definition.length > 0 && (
              <section className="gw-section">
                <h3>岗位定义</h3>
                <ol className="gw-def">
                  {detail.definition.map((d, i) => (
                    <li key={i}>{d.text}</li>
                  ))}
                </ol>
              </section>
            )}
            <section className="gw-section">
              <h3>
                来源企业 <span className="mono mute">{detail?.sources?.length ?? 0}</span>
              </h3>
              {detail?.sources?.length ? <p className="gw-companies">{detail.sources.join("、")}</p> : <p className="gw-empty">暂无来源企业。</p>}
            </section>
            <section className="gw-section">
              <h3>
                JD 快照 <span className="mono mute">{slice?.evidence?.length ?? 0}</span>
              </h3>
              {renderEvidence()}
            </section>
            {eventStats.total > 0 && (
              <section className="gw-section">
                <h3>要求事件审核</h3>
                <p className="gw-note mono">
                  共 {eventStats.total} 条 · 通过 {eventStats.approved} · 驳回 {eventStats.rejected}
                </p>
              </section>
            )}
          </>
        )}

        {tab === "watching" && (
          <>
            <p className="gw-note">市场开始提及但尚未达到要求门槛的技能，不计入缺口。按招聘流中的提及次数排序。</p>
            {watchingRanked.length === 0 ? (
              <p className="gw-empty">暂无观测中的技能。</p>
            ) : (
              <ol className="gw-watch">
                {watchingRanked.slice(0, watchingLimit).map((w) => (
                  <li key={w.name}>
                    <span className="gw-watch-name">{w.name}</span>
                    <span className="gw-watch-n mono">{w.n ? `${w.n} 次` : ""}</span>
                  </li>
                ))}
              </ol>
            )}
            {watchingRanked.length > watchingLimit && (
              <button type="button" className="gw-btn sm" onClick={() => setWatchingLimit((n) => n + WATCHING_PAGE * 2)}>
                展开更多（剩余 {watchingRanked.length - watchingLimit}）
              </button>
            )}
          </>
        )}
      </div>

      <div className="gw-pane-foot">
        <Link className="gw-btn solid block" href={`/diagnose?job_id=${encodeURIComponent(selected)}`}>
          对照我的简历，计算换档条件 →
        </Link>
      </div>
    </div>
  );

  const inspector = (
    <aside className={`gw-inspector${loading || stale ? " is-loading" : ""}`} aria-label="岗位详情" aria-busy={loading || stale}>
      {loadError ? (
        <div className="gw-pane-body">
          <p className="gw-error">{loadError}</p>
          <button type="button" className="gw-btn sm" onClick={() => setParams({ job: selected })}>
            重试
          </button>
        </div>
      ) : !bundle ? (
        <div className="gw-pane-body gw-skel" aria-hidden="true">
          <span className="w60" />
          <span className="w40" />
          <span className="w90" />
          <span className="w70" />
          <span className="w80" />
        </div>
      ) : selectedReq ? (
        skillPane
      ) : (
        jobPane
      )}
    </aside>
  );

  const legend = (
    <ul className="gw-legend" aria-label="类目图例">
      {CATEGORIES.map((c) => (
        <li key={c}>
          <CatDot category={c} />
          {c}
        </li>
      ))}
    </ul>
  );

  return (
    <main id="main" className="gw">
      <div className="gw-bar">
        <div className="gw-bar-left">
          {narrow ? (
            <button type="button" className="gw-btn sm" aria-expanded={railOpen} onClick={() => setRailOpen(true)}>
              岗位 ▾
            </button>
          ) : (
            <span className="gw-crumb">岗位图谱</span>
          )}
          <span className="gw-dot" />
          <span className="gw-crumb-job">{jobName || "—"}</span>
          {jobStatus && <StatusTag status={jobStatus} />}
        </div>
        <div className="gw-bar-right">
          <span className="gw-version mono" title="当前图谱发布版本">
            {period ? `图谱 ${fmtDate(period)}` : "未发布版本"}
          </span>
          <div className="gw-seg" role="group" aria-label="视图">
            <button type="button" className={view === "graph" ? "on" : ""} aria-pressed={view === "graph"} onClick={() => setParams({ view: null })}>
              拓扑
            </button>
            <button type="button" className={view === "table" ? "on" : ""} aria-pressed={view === "table"} onClick={() => setParams({ view: "table" })}>
              表格
            </button>
          </div>
          <button
            type="button"
            className={`gw-btn sm${inspectorOpen ? " on" : ""}`}
            aria-pressed={inspectorOpen}
            onClick={() => setInspectorOpen((v) => !v)}
          >
            详情面板
          </button>
        </div>
      </div>

      <div className={`gw-body${inspectorOpen ? "" : " no-inspector"}`}>
        {!narrow && rail}
        {narrow && railOpen && (
          <div className="gw-drawer-mask" onClick={() => setRailOpen(false)}>
            <div className="gw-drawer left" onClick={(e) => e.stopPropagation()}>
              {rail}
            </div>
          </div>
        )}

        <section className="gw-stage" aria-label="岗位要求">
          <div className="gw-tools">
            <label className="gw-search sm">
              <input
                type="search"
                value={skillQuery}
                onChange={(e) => setSkillQuery(e.target.value)}
                placeholder="按技能名称筛选"
                aria-label="筛选要求名称"
              />
            </label>
            <select className="gw-select" aria-label="类目" value={cat} onChange={(e) => setParams({ cat: e.target.value || null })}>
              <option value="">全部类目</option>
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
              <option value="其他">其他</option>
            </select>
            <select className="gw-select" aria-label="适用级别" value={level} onChange={(e) => setParams({ level: e.target.value || null })}>
              <option value="">全部级别</option>
              {LEVELS.map((l) => (
                <option key={l.value} value={l.value}>
                  {l.label}
                </option>
              ))}
            </select>
            <div className="gw-seg" role="group" aria-label="要求类型">
              {KINDS.map((k) => (
                <button key={k.value} type="button" className={kind === k.value ? "on" : ""} aria-pressed={kind === k.value} onClick={() => setParams({ kind: k.value || null })}>
                  {k.label}
                </button>
              ))}
            </div>
            <button type="button" className={`gw-chip${recent ? " on" : ""}`} aria-pressed={recent} onClick={() => setParams({ recent: recent ? null : "1" })}>
              近 {RECENT_DAYS} 天生效
            </button>
            <span className="gw-tools-count mono">
              {filtersActive ? `${visible.length} / ${requires.length}` : requires.length} 项
            </span>
            {filtersActive && (
              <button type="button" className="gw-link" onClick={clearFilters}>
                清除
              </button>
            )}
          </div>
          <p className="gw-note">先选一个要求查看右侧详情。拓扑适合看要求分组，表格适合逐项核对。必备、加分和观测中的技能口径不同，观测中的技能不会计入缺口。</p>

          <div className="gw-stage-body">
            {view === "graph" ? (
              <div className="gw-canvas" role="application" aria-label="岗位能力拓扑画布" tabIndex={0}>
                {bundle && (
                  <FlowWorkbenchCanvas
                    job={{ id: selected, name: jobName, status: jobStatus }}
                    stats={dossier}
                    neighbor={dossier?.neighbor}
                    watching={detail?.watching}
                    evidence={slice?.evidence}
                    period={period}
                    skills={flowSkills}
                    visibleIds={visibleIds}
                    selectedSkill={urlSkill}
                    onSkillClick={(s) => pickSkill(s.id)}
                    onWatchingClick={() => {
                      setParams({ skill: null });
                      setTab("watching");
                      setInspectorOpen(true);
                    }}
                    onNeighborClick={(id) => pickJob(id)}
                  />
                )}
                {bundle && requires.length === 0 && !loading && (
                  <div className="gw-canvas-empty">
                    <strong>尚无要求边</strong>
                    <span>
                      已收录 {slice?.evidence?.length ?? 0} 份 JD 快照，{detail?.watching?.length ?? 0} 项观测中技能。要求边需双独立源验证后才会出现。
                    </span>
                  </div>
                )}
                {(loading || stale || loadError) && (
                  <div className="gw-canvas-veil" aria-live="polite">
                    {loadError ? loadError : "载入岗位数据"}
                  </div>
                )}
              </div>
            ) : (
              <div className="gw-table-wrap">
                <table className="gw-table">
                  <colgroup>
                    <col />
                    <col className="w-cat" />
                    <col className="w-kind" />
                    <col className="w-prof" />
                    <col className="w-src" />
                    <col className="w-conf" />
                    <col className="w-date" />
                  </colgroup>
                  <thead>
                    <tr>
                      {(
                        [
                          ["name", "能力", ""],
                          ["category", "类目", ""],
                          [null, "类型", ""],
                          ["proficiency", "熟练级", ""],
                          ["sources", "独立源", "num"],
                          ["confidence", "置信", "num"],
                          ["valid_from", "生效日", "num"],
                        ] as const
                      ).map(([key, label, cls]) => (
                        <th key={label} className={cls || undefined} aria-sort={key && sort.key === key ? (sort.dir === "asc" ? "ascending" : "descending") : undefined}>
                          {key ? (
                            <button type="button" className="gw-th" onClick={() => toggleSort(key)}>
                              {label}
                              <SortIcon active={sort.key === key} dir={sort.dir} />
                            </button>
                          ) : (
                            label
                          )}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {sorted.map((r) => (
                      <tr
                        key={r.skill_id}
                        className={r.skill_id === urlSkill ? "on" : ""}
                        tabIndex={0}
                        onClick={(e) => pickSkill(r.skill_id, e.currentTarget)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            pickSkill(r.skill_id, e.currentTarget);
                          }
                        }}
                      >
                        <td className="gw-td-name">
                          <span>{r.name}</span>
                          {addedIds.has(r.skill_id) && <span className="gw-mini new">新</span>}
                          {expiredIds.has(r.skill_id) && <span className="gw-mini exp">失效</span>}
                          {r.group_id && (groups.get(r.group_id)?.length || 0) > 1 && (
                            <span className="gw-mini" title="同组任选">组</span>
                          )}
                        </td>
                        <td>
                          <CatDot category={r.category} />
                          {sectorOf(r.category)}
                        </td>
                        <td className="mute">{r.kind === "bonus" ? "加分" : "必备"}</td>
                        <td>
                          <Meter value={r.proficiency} />
                        </td>
                        <td className="num">
                          <span className="gw-bar-cell">
                            <i style={{ width: `${Math.min(100, ((r.sources?.length ?? 0) / Math.max(1, ...requires.map((x) => x.sources?.length ?? 0))) * 100)}%` }} />
                            <b>{r.sources?.length ?? 0}</b>
                          </span>
                        </td>
                        <td className="num mute">{r.confidence != null ? r.confidence.toFixed(2) : "—"}</td>
                        <td className="num mute">{fmtDate(r.valid_from) || "—"}</td>
                      </tr>
                    ))}
                    {sorted.length === 0 && (
                      <tr>
                        <td colSpan={7} className="gw-empty">
                          {requires.length === 0 ? "该岗位尚无通过审核的要求边。" : "当前过滤条件下没有要求。"}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <footer className="gw-status" aria-label="图例与读数">
            <div className="gw-status-left">
              {legend}
              <span className="gw-status-tip">线越粗独立源越多 · 虚线为加分 · 悬停卡片看原文</span>
            </div>
            <span className="gw-status-right mono">
              必备 {requiredCount} · 加分 {bonusCount} · 独立源 {dossier?.n_sources ?? currentRow?.n_sources ?? "–"}
            </span>
          </footer>
        </section>

        {inspectorOpen && !narrow && inspector}
        {inspectorOpen && narrow && (
          <div className="gw-drawer-mask" onClick={() => setInspectorOpen(false)}>
            <div className="gw-drawer right" onClick={(e) => e.stopPropagation()}>
              {inspector}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
