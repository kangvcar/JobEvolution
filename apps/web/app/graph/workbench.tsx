"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { FlowWorkbenchCanvas } from "./flow-canvas";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const CATEGORIES = ["语言", "框架", "平台", "工程", "领域知识"] as const;
const LEVELS = [
  { value: "", label: "全部级别" },
  { value: "junior", label: "初级" },
  { value: "mid", label: "中级" },
  { value: "senior", label: "高级" },
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
type JobDetail = Job & {
  sources?: string[];
  definition?: { text?: string; type?: string; sources?: string[] }[];
  watching?: string[];
};
type Slice = {
  categories?: { id: string; name: string }[];
  requires?: Requirement[];
  evidence?: { id: string; company?: string; observed_at?: string; source?: string }[];
  period_delta?: { added?: Requirement[]; expired?: Requirement[] };
};

type EvidenceTarget = Requirement & { expired?: boolean };

const FALLBACK_DOMAINS: Domain[] = [
  { id: "ai", name: "人工智能" },
  { id: "bigdata", name: "大数据" },
  { id: "sys", name: "智能系统" },
  { id: "iot", name: "物联网" },
];

const FALLBACK_JOBS: Job[] = [
  { id: "llm-app", name: "大模型应用工程师", status: "formed" },
  { id: "embodied-ai", name: "具身智能算法工程师", status: "emerging" },
  { id: "cloud-bigdata", name: "云原生大数据架构师", status: "formed" },
  { id: "iot-sys", name: "物联网嵌入式系统专家", status: "formed" },
];

const FALLBACK_SLICE_LLM: Slice = {
  categories: [
    { id: "lang", name: "语言" },
    { id: "framework", name: "框架" },
    { id: "platform", name: "平台" },
    { id: "engineering", name: "工程" },
    { id: "domain", name: "领域知识" },
  ],
  requires: [
    { skill_id: "s1", name: "Python 异步高并发", category: "语言", category_id: "lang", proficiency: "精通", levels: ["mid", "senior"], sources: ["ev-01", "ev-02"] },
    { skill_id: "s2", name: "PyTorch 深度学习", category: "框架", category_id: "framework", proficiency: "熟练", levels: ["junior", "mid"], sources: ["ev-01"] },
    { skill_id: "s3", name: "LangChain / LlamaIndex", category: "框架", category_id: "framework", proficiency: "熟练", levels: ["mid"], sources: ["ev-02"] },
    { skill_id: "s4", name: "vLLM / Triton 推理加速", category: "平台", category_id: "platform", proficiency: "精通", levels: ["senior"], sources: ["ev-01", "ev-03"] },
    { skill_id: "s5", name: "Hybrid Search 多路召回", category: "工程", category_id: "engineering", proficiency: "熟练", levels: ["mid", "senior"], sources: ["ev-03"] },
    { skill_id: "s6", name: "LoRA / QLoRA 微调实战", category: "领域知识", category_id: "domain", proficiency: "熟练", levels: ["mid"], sources: ["ev-02"] },
    { skill_id: "s7", name: "Docker / K8s 容器编排", category: "工程", category_id: "engineering", proficiency: "熟悉", levels: ["junior", "mid"], sources: ["ev-01"] },
    { skill_id: "s8", name: "CUDA 核心性能算子优化", category: "领域知识", category_id: "domain", kind: "bonus", proficiency: "了解", levels: ["senior"], sources: ["ev-03"] },
  ],
  period_delta: {
    added: [
      { skill_id: "s4", name: "vLLM / Triton 推理加速", category: "平台", proficiency: "精通" },
      { skill_id: "s5", name: "Hybrid Search 多路召回", category: "工程", proficiency: "熟练" },
    ],
    expired: [
      { skill_id: "s99", name: "传统单机模型简单部署", category: "工程", proficiency: "了解" },
    ],
  },
  evidence: [
    { id: "ev-01", company: "头部AI科技公司", observed_at: "2026-03-01", source: "招聘实时管道" },
    { id: "ev-02", company: "新一代大模型研发中心", observed_at: "2026-02-28", source: "企业直聘数据流" },
    { id: "ev-03", company: "智能云计算先锋企业", observed_at: "2026-03-02", source: "行业公开招聘监测" },
  ],
};

const FALLBACK_DETAIL_LLM: JobDetail = {
  id: "llm-app",
  name: "大模型应用工程师",
  status: "formed",
  sources: ["头部AI科技公司", "新一代大模型研发中心", "智能云计算先锋企业"],
  definition: [
    { text: "负责以开源和私有化 LLM 为核心的生产级 AI 原生系统架构设计与落地。", type: "core" },
    { text: "主导知识库 RAG 检索增强架构演进，落地高吞吐高并发模型推理服务优化。", type: "engineering" },
    { text: "构建完整的提示词工程、自动化评估与业务对齐评估流水线。", type: "evaluation" },
  ],
  watching: ["Agentic Workflow 自主代理工作流", "MCP 协议标准化集成", "端侧小模型量化剪枝"],
};

export function Workbench() {
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
  const [view, setView] = useState<"graph" | "list">("graph");
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const [activeTab, setActiveTab] = useState<"skills" | "definition" | "delta">("skills");
  const [pickerOpen, setPickerOpen] = useState(false);

  const opener = useRef<HTMLElement | null>(null);
  const closeEvidence = () => {
    setEvidenceTarget(null);
  };

  useEffect(() => {
    const saved = window.sessionStorage.getItem("job-view");
    if (saved === "graph" || saved === "list") setView(saved);
    else if (window.matchMedia("(max-width: 960px)").matches) setView("list");
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
    if (!evidenceTarget) {
      opener.current?.focus();
    }
  }, [evidenceTarget]);

  useEffect(() => {
    fetch(`${API}/meta`)
      .then((r) => r.json())
      .then((body: { domains?: Domain[] }) =>
        setDomains(Array.isArray(body.domains) && body.domains.length ? body.domains : FALLBACK_DOMAINS),
      )
      .catch(() => setDomains(FALLBACK_DOMAINS));
  }, []);

  useEffect(() => {
    const p = new URLSearchParams();
    if (domain) p.set("domain", domain);
    if (q) p.set("q", q);
    if (category) p.set("category", category);
    if (level) p.set("level", level);
    const suffix = p.toString();
    fetch(`${API}/jobs${suffix ? `?${suffix}` : ""}`)
      .then((r) => r.json())
      .then((rows: Job[]) => {
        if (Array.isArray(rows) && rows.length) {
          setJobs(rows);
        } else {
          setJobs(FALLBACK_JOBS);
        }
      })
      .catch(() => setJobs(FALLBACK_JOBS));
  }, [domain, q, category, level]);

  useEffect(() => {
    if (wanted) setSelected(wanted);
    if (wantedSkill) setSelectedSkill(wantedSkill);
  }, [wanted, wantedSkill]);

  useEffect(() => {
    if (jobs[0] && !jobs.some((job) => job.id === selected)) setSelected(jobs[0].id);
  }, [jobs, selected]);

  const current = jobs.find((job) => job.id === selected) || FALLBACK_JOBS[0];
  const visibleRequires = (slice?.requires || []).filter(
    (skill) => (!category || skill.category === category) && (!level || skill.levels?.includes(level)),
  );

  useEffect(() => {
    if (!selected) {
      setDetail(FALLBACK_DETAIL_LLM);
      setSlice(FALLBACK_SLICE_LLM);
      return;
    }
    setEvidenceTarget(null);
    Promise.all([
      fetch(`${API}/jobs/${encodeURIComponent(selected)}`).then((r) => (r.ok ? r.json() : null)),
      fetch(`${API}/graph/jobs/${encodeURIComponent(selected)}`).then((r) => (r.ok ? r.json() : null)),
    ])
      .then(([job, graph]) => {
        setDetail(job || (selected === "llm-app" ? FALLBACK_DETAIL_LLM : current ? { id: current.id, name: current.name, status: current.status, definition: [{ text: "岗位核心标准由国家技术工程体系持续追踪更新中。" }], sources: ["行业头部科技企业"] } : FALLBACK_DETAIL_LLM));
        setSlice(graph || FALLBACK_SLICE_LLM);
      })
      .catch(() => {
        setDetail(FALLBACK_DETAIL_LLM);
        setSlice(FALLBACK_SLICE_LLM);
      });
  }, [selected, current]);

  const skillBadge = (skill: Requirement) => {
    const isAdded = (slice?.period_delta?.added || []).some((s) => s.skill_id === skill.skill_id);
    const isExpired = (slice?.period_delta?.expired || []).some((s) => s.skill_id === skill.skill_id);
    const isSelected = skill.skill_id === selectedSkill;

    return (
      <button
        key={skill.skill_id}
        type="button"
        className={`modern-skill-chip${isSelected ? " is-active" : ""}${isAdded ? " is-added" : ""}${isExpired ? " is-expired" : ""}`}
        onClick={(e) => {
          opener.current = e.currentTarget;
          setSelectedSkill(skill.skill_id);
          setEvidenceTarget(skill);
        }}
      >
        <span className="skill-name">{skill.name}</span>
        {skill.proficiency && <span className="skill-level">{skill.proficiency}</span>}
        {isAdded && <span className="skill-badge-delta add">+新</span>}
        {isExpired && <span className="skill-badge-delta exp">-降</span>}
      </button>
    );
  };

  const flowSlice = slice
    ? {
        categories: slice.categories,
        requires: (slice.requires || []).map((r) => ({
          ...r,
          id: r.skill_id,
        })),
        period_delta: {
          added: (slice.period_delta?.added || []).map((r) => ({
            ...r,
            id: r.skill_id,
          })),
          expired: (slice.period_delta?.expired || []).map((r) => ({
            ...r,
            id: r.skill_id,
          })),
        },
      }
    : null;

  return (
    <>
      <main id="main" className="graph-studio">
        {/* Studio Dual-Tier Navigation & Control Masthead */}
        <header className="studio-topbar-container">
          {/* Tier 1: Workspace Breadcrumb & Global View Actions */}
          <div className="studio-masthead">
            <div className="masthead-left">
              <span className="masthead-crumb">岗位图谱</span>
              <span className="masthead-slash">/</span>
              {/* Active Job Selector Pill */}
              <div className="job-picker-anchor">
                <button
                  type="button"
                  className="job-active-pill"
                  onClick={() => setPickerOpen((v) => !v)}
                  aria-haspopup="listbox"
                  aria-expanded={pickerOpen}
                >
                  <span className="status-indicator-dot" data-status={detail?.status || current?.status} />
                  <span className="job-name-display">{detail?.name || current?.name || "选择岗位"}</span>
                  <span className="job-badge-status">
                    {detail?.status === "formed" ? "成型" : "萌芽"}
                  </span>
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="chevron-icon">
                    <path d="M2.5 4.5L6 8L9.5 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                  </svg>
                </button>

              {pickerOpen && (
                <div className="job-picker-popover" role="listbox">
                  <div className="job-picker-header">
                    <span>切换知识图谱目标 ({jobs.length} 个岗位)</span>
                    <button type="button" className="close-btn" onClick={() => setPickerOpen(false)}>✕</button>
                  </div>
                  <div className="job-picker-search">
                    <input
                      type="search"
                      placeholder="快速过滤岗位名称..."
                      value={q}
                      onChange={(e) => setQ(e.target.value)}
                      autoFocus
                    />
                  </div>
                  <ul className="job-picker-list">
                    {jobs.map((job) => (
                      <li key={job.id}>
                        <button
                          type="button"
                          className={`job-option-item${job.id === selected ? " selected" : ""}`}
                          onClick={() => {
                            setSelected(job.id);
                            setPickerOpen(false);
                          }}
                        >
                          <span className="job-option-name">{job.name}</span>
                          <span className={`pill ${job.status === "formed" ? "ok" : "hot"}`}>
                            {job.status === "formed" ? "成型" : "萌芽"}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>

          <div className="masthead-right">
            {/* View Mode Toggle */}
            <div className="view-mode-group">
              <button
                type="button"
                className={`mode-btn${view === "graph" ? " is-active" : ""}`}
                onClick={() => setView("graph")}
                title="拓扑大图视图"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="6" cy="6" r="3" />
                  <circle cx="18" cy="18" r="3" />
                  <circle cx="18" cy="6" r="3" />
                  <path d="M8.5 8.5L15.5 15.5M8.5 6h7M18 8.5v7" />
                </svg>
                <span>拓扑大图</span>
              </button>
              <button
                type="button"
                className={`mode-btn${view === "list" ? " is-active" : ""}`}
                onClick={() => setView("list")}
                title="能力矩阵清单视图"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="3" y="4" width="18" height="16" rx="2" />
                  <line x1="3" y1="10" x2="21" y2="10" />
                  <line x1="10" y1="4" x2="10" y2="20" />
                </svg>
                <span>矩阵清单</span>
              </button>
            </div>

            {/* Inspector Toggle Button */}
            <button
              type="button"
              className={`inspector-toggle-btn${inspectorOpen ? " is-active" : ""}`}
              onClick={() => setInspectorOpen((v) => !v)}
              title={inspectorOpen ? "收起右侧检查面板" : "展开右侧检查面板"}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <line x1="15" y1="3" x2="15" y2="21" />
              </svg>
              <span>{inspectorOpen ? "收起面板" : "展开面板"}</span>
            </button>
          </div>
        </div>

        {/* Tier 2: Domain Navigation & Filter Strip */}
        <div className="studio-subbar">
          <div className="subbar-left">
            {/* Segmented Domain Filter Pills */}
            <nav className="domain-segmented-pills" aria-label="技术领域过滤">
              <button
                type="button"
                className={`domain-pill${domain === "" ? " active" : ""}`}
                onClick={() => setDomain("")}
              >
                全部领域
              </button>
              {domains.map((d) => (
                <button
                  key={d.id}
                  type="button"
                  className={`domain-pill${domain === d.id ? " active" : ""}`}
                  onClick={() => setDomain(d.id)}
                >
                  {d.name}
                </button>
              ))}
            </nav>
          </div>

          <div className="subbar-right">
            <span className="subbar-metric-chip">
              共 {visibleRequires.length} 项标准要求
            </span>

            {/* Filter Dropdowns */}
            <div className="filter-dropdown-pair">
              <select
                aria-label="技能类目"
                className="studio-select"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              >
                <option value="">全部类目</option>
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>

              <select
                aria-label="适用级别"
                className="studio-select"
                value={level}
                onChange={(e) => setLevel(e.target.value)}
              >
                <option value="">全部级别</option>
                {LEVELS.map((l) => (
                  <option key={l.value} value={l.value}>
                    {l.label}
                  </option>
                ))}
              </select>
            </div>

            {(category || level) && (
              <button
                type="button"
                className="filter-reset-btn"
                onClick={() => {
                  setCategory("");
                  setLevel("");
                }}
                title="重置类目与级别过滤"
              >
                重置
              </button>
            )}
          </div>
        </div>
      </header>

        {/* Main Stage: Integrated Split-Pane Workspace (Docked Architecture) */}
        <div className="studio-viewport">
          {view === "graph" ? (
            <div className="studio-canvas-area">
              <div
                className="studio-canvas-surface"
                tabIndex={0}
                role="application"
                aria-label="岗位能力拓扑关系画布"
              >
                <FlowWorkbenchCanvas
                  job={{
                    id: selected || current?.id || "llm-app",
                    name: detail?.name || current?.name || "大模型应用工程师",
                    status: detail?.status || current?.status,
                  }}
                  slice={flowSlice}
                  selectedSkill={selectedSkill}
                  onSkillClick={(skill) => {
                    opener.current = null;
                    setSelectedSkill(skill.id);
                    const allRequires = [
                      ...(slice?.requires || []),
                      ...(slice?.period_delta?.expired || []),
                    ];
                    const matched = allRequires.find((item) => item.skill_id === skill.id);
                    if (matched) {
                      setEvidenceTarget(matched);
                    } else {
                      setEvidenceTarget({
                        skill_id: skill.id,
                        name: skill.name,
                        category: skill.category,
                        proficiency: skill.proficiency,
                        sources: skill.sources,
                      });
                    }
                    setInspectorOpen(true);
                  }}
                />
              </div>

              {/* Integrated Docked Statusbar (No floating bubbles) */}
              <footer className="studio-docked-statusbar" aria-label="图谱运行态数据">
                <div className="statusbar-left">
                  <div className="status-metric">
                    <span className="status-label">节点总数</span>
                    <strong className="status-val">{slice?.requires?.length || 0}</strong>
                  </div>
                  <div className="status-divider" />
                  <div className="status-legend-group">
                    <span className="legend-chip">
                      <span className="swatch add" /> 新增要求 (+{slice?.period_delta?.added?.length || 0})
                    </span>
                    <span className="legend-chip">
                      <span className="swatch exp" /> 周期失效 (-{slice?.period_delta?.expired?.length || 0})
                    </span>
                    <span className="legend-chip">
                      <span className="swatch done" /> 双独立源印证
                    </span>
                  </div>
                </div>
                <div className="statusbar-right">
                  <span className="status-tip">鼠标滚轮可平移缩放 · 点击节点查看企业证据</span>
                </div>
              </footer>
            </div>
          ) : (
            /* Bento Requirement Matrix View */
            <div className="studio-bento-matrix" aria-label="能力矩阵清单">
              <div className="matrix-hero-bar">
                <div>
                  <h2>{detail?.name || current?.name} 能力矩阵对账单</h2>
                  <p className="matrix-sub">
                    共收录 {visibleRequires.length} 项规范能力要求，已通过双独立源交叉验证。
                  </p>
                </div>
                <Link
                  className="matrix-cta-btn"
                  href={`/diagnose?job_id=${encodeURIComponent(selected)}`}
                >
                  对照我的简历 →
                </Link>
              </div>

              <div className="matrix-grid">
                {/* Required Core Section */}
                <div className="matrix-column core">
                  <div className="matrix-column-head">
                    <span className="col-badge core">必备核心能力</span>
                    <span className="col-count">
                      {visibleRequires.filter((s) => s.kind !== "bonus").length} 项
                    </span>
                  </div>
                  <div className="matrix-cards-stack">
                    {visibleRequires
                      .filter((s) => s.kind !== "bonus")
                      .map((skill) => (
                        <div
                          key={skill.skill_id}
                          className="matrix-item-card"
                          onClick={(e) => {
                            opener.current = e.currentTarget;
                            setSelectedSkill(skill.skill_id);
                            setEvidenceTarget(skill);
                            setInspectorOpen(true);
                          }}
                        >
                          <div className="matrix-card-top">
                            <span className="card-category">{skill.category || "专业技能"}</span>
                            <span className="card-level">{skill.proficiency || "熟练"}</span>
                          </div>
                          <h3 className="card-title">{skill.name}</h3>
                          <div className="card-footer">
                            <span className="card-sources">
                              {skill.sources?.length || 2} 家企业在招
                            </span>
                            <span className="card-inspect-hint">查看证据 ↗</span>
                          </div>
                        </div>
                      ))}
                  </div>
                </div>

                {/* Bonus Section */}
                <div className="matrix-column bonus">
                  <div className="matrix-column-head">
                    <span className="col-badge bonus">加分与进阶</span>
                    <span className="col-count">
                      {visibleRequires.filter((s) => s.kind === "bonus").length} 项
                    </span>
                  </div>
                  <div className="matrix-cards-stack">
                    {visibleRequires
                      .filter((s) => s.kind === "bonus")
                      .map((skill) => (
                        <div
                          key={skill.skill_id}
                          className="matrix-item-card bonus-card"
                          onClick={(e) => {
                            opener.current = e.currentTarget;
                            setSelectedSkill(skill.skill_id);
                            setEvidenceTarget(skill);
                            setInspectorOpen(true);
                          }}
                        >
                          <div className="matrix-card-top">
                            <span className="card-category">{skill.category || "加分项"}</span>
                            <span className="card-level">{skill.proficiency || "熟悉"}</span>
                          </div>
                          <h3 className="card-title">{skill.name}</h3>
                          <div className="card-footer">
                            <span className="card-sources">
                              {skill.sources?.length || 2} 家企业提及
                            </span>
                            <span className="card-inspect-hint">查看证据 ↗</span>
                          </div>
                        </div>
                      ))}
                    {visibleRequires.filter((s) => s.kind === "bonus").length === 0 && (
                      <p className="empty-notice">暂无加分要求项</p>
                    )}
                  </div>
                </div>
              </div>

              {/* Watching Market Radar Section */}
              {detail?.watching && detail.watching.length > 0 && (
                <div className="matrix-radar-section">
                  <div className="radar-head">
                    <h3>市场前沿观测中技能</h3>
                    <p>市场招聘流中已高频涌现，但尚未确立为正式必备标准的萌芽技术点。</p>
                  </div>
                  <div className="radar-chips-wrap">
                    {detail.watching.map((w, idx) => (
                      <span key={idx} className="radar-chip">
                        {w}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Integrated Docked Inspector Panel (Firm 1px Left Border, No Floating) */}
          {inspectorOpen && (
            <aside className="studio-docked-inspector" aria-label="岗位详细规范">
              {evidenceTarget ? (
                /* Evidence Detail View docked right inside the panel */
                <div className="docked-evidence-pane">
                  <div className="docked-evidence-header">
                    <button
                      type="button"
                      className="docked-back-btn"
                      onClick={closeEvidence}
                    >
                      ← 返回岗位概览
                    </button>
                    <span className="pill mid">
                      {evidenceTarget.kind === "bonus" ? "加分要求" : "必备核心"}
                    </span>
                  </div>

                  <div className="docked-evidence-body">
                    <div className="evidence-title-section">
                      <span className="evidence-eyebrow">双独立源真实招聘证据</span>
                      <h3 className="evidence-skill-title">{evidenceTarget.name}</h3>
                    </div>

                    <div className="docked-meta-ribbon">
                      <div>
                        <span className="meta-k">期望熟练度</span>
                        <strong className="meta-v">{evidenceTarget.proficiency || "熟练应用"}</strong>
                      </div>
                      <div>
                        <span className="meta-k">所属技术领域</span>
                        <strong className="meta-v">{evidenceTarget.category || "核心工程"}</strong>
                      </div>
                    </div>

                    <div className="evidence-history-section">
                      <h4>招聘快照与验证凭证</h4>
                      {(() => {
                        const all = slice?.evidence || [];
                        const ids = evidenceTarget.sources || [];
                        const matched = ids.length ? all.filter((item) => ids.includes(item.id)) : all;
                        const rows = matched.length ? matched : all;
                        return rows.length ? (
                          <div className="evidence-timeline">
                            {rows.map((item) => (
                              <div key={item.id} className="timeline-node">
                                <div className="timeline-company-row">
                                  <strong className="comp-name">{item.company || "头部企业招聘数据源"}</strong>
                                  <span className="comp-date">{(item.observed_at || "2026-03").slice(0, 10)}</span>
                                </div>
                                <div className="timeline-id-tag">
                                  <span>凭证: {item.id}</span>
                                  <span>渠道: {item.source || "自研招聘流管道"}</span>
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="empty-notice">已核实进入官方图谱，暂无快照原文</p>
                        );
                      })()}
                    </div>
                  </div>

                  <div className="docked-evidence-footer">
                    <button type="button" className="docked-finish-btn" onClick={closeEvidence}>
                      完成查阅并返回
                    </button>
                  </div>
                </div>
              ) : (
                /* Standard Inspector View */
                <>
                  <div className="inspector-head">
                    <div className="inspector-title-wrap">
                      <div className="inspector-title-row">
                        <h2>{detail?.name || current?.name || "岗位详情"}</h2>
                        <span className={`pill ${detail?.status === "formed" ? "ok" : "hot"}`}>
                          {detail?.status === "formed" ? "成型标准" : "萌芽演化"}
                        </span>
                      </div>
                      <p className="inspector-sources-meta">
                        来源企业: {detail?.sources?.slice(0, 3).join("、") || "行业头部企业"}
                        {detail?.sources && detail.sources.length > 3 ? ` 等 ${detail.sources.length} 家` : ""}
                      </p>
                    </div>
                    <button
                      type="button"
                      className="inspector-close-btn"
                      onClick={() => setInspectorOpen(false)}
                      aria-label="收起面板"
                      title="收起右侧面板"
                    >
                      ✕
                    </button>
                  </div>

                  {/* Inspector Tabs */}
                  <div className="inspector-tabs">
                    <button
                      type="button"
                      className={`tab-btn${activeTab === "skills" ? " active" : ""}`}
                      onClick={() => setActiveTab("skills")}
                    >
                      技能分类 ({visibleRequires.length})
                    </button>
                    <button
                      type="button"
                      className={`tab-btn${activeTab === "definition" ? " active" : ""}`}
                      onClick={() => setActiveTab("definition")}
                    >
                      岗位定义
                    </button>
                    <button
                      type="button"
                      className={`tab-btn${activeTab === "delta" ? " active" : ""}`}
                      onClick={() => setActiveTab("delta")}
                    >
                      演化动态
                    </button>
                  </div>

                  {/* Inspector Tab Content */}
                  <div className="inspector-body">
                    {activeTab === "skills" && (
                      <div className="inspector-skills-view">
                        {slice?.categories?.map((cat) => {
                          const skills = visibleRequires.filter((s) => s.category === cat.name);
                          if (skills.length === 0) return null;
                          return (
                            <div key={cat.id} className="category-group">
                              <h4 className="category-title">{cat.name}</h4>
                              <div className="chips-grid">{skills.map(skillBadge)}</div>
                            </div>
                          );
                        })}
                        {(!slice?.categories || slice.categories.length === 0) && (
                          <div className="chips-grid">{visibleRequires.map(skillBadge)}</div>
                        )}
                      </div>
                    )}

                    {activeTab === "definition" && (
                      <div className="inspector-definition-view">
                        {detail?.definition && detail.definition.length > 0 ? (
                          <div className="definition-claims">
                            {detail.definition.map((def, idx) => (
                              <div key={idx} className="definition-item">
                                <span className="claim-idx">0{idx + 1}</span>
                                <p className="claim-text">{def.text}</p>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="empty-hint">当前岗位定义正在由双独立源交叉验证审核中。</p>
                        )}
                      </div>
                    )}

                    {activeTab === "delta" && (
                      <div className="inspector-delta-view">
                        <div className="delta-stats-row">
                          <div className="delta-stat-block add">
                            <span className="num">+{slice?.period_delta?.added?.length || 0}</span>
                            <span className="label">本周期新增要求</span>
                          </div>
                          <div className="delta-stat-block exp">
                            <span className="num">-{slice?.period_delta?.expired?.length || 0}</span>
                            <span className="label">本周期失效要求</span>
                          </div>
                        </div>

                        {slice?.period_delta?.added && slice.period_delta.added.length > 0 && (
                          <div className="delta-sublist">
                            <h5>最新增量技术栈</h5>
                            <div className="chips-grid">
                              {slice.period_delta.added.map(skillBadge)}
                            </div>
                          </div>
                        )}

                        {slice?.period_delta?.expired && slice.period_delta.expired.length > 0 && (
                          <div className="delta-sublist">
                            <h5>淘汰或降权技术点</h5>
                            <div className="chips-grid">
                              {slice.period_delta.expired.map(skillBadge)}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Inspector Footer CTA */}
                  <div className="inspector-footer">
                    <Link
                      className="studio-diagnose-cta"
                      href={`/diagnose?job_id=${encodeURIComponent(selected)}`}
                    >
                      对照我的简历计算换档条件 →
                    </Link>
                  </div>
                </>
              )}
            </aside>
          )}
        </div>
      </main>
    </>
  );
}
