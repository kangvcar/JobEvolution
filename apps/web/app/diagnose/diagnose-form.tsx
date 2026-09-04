"use client";

import { FormEvent, ReactNode, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TICKER = [
  "读取简历技能证据",
  "对照岗位规范要求",
  "标记覆盖缺口半档",
  "推算换档条件",
];
const DEFAULT_JOB = "大模型应用工程师";
const STEPS = [
  { key: "upload", label: "上传简历" },
  { key: "correct", label: "校对解析" },
  { key: "choose", label: "选择岗位" },
  { key: "run", label: "生成对照" },
  { key: "report", label: "查看报告" },
] as const;
const BAND_LEVEL: Record<string, number> = { 不匹配: 0, 有明显差距: 1, 基本匹配: 2, 高度匹配: 3 };
const WATCHING_PREVIEW = 12;

type Step = (typeof STEPS)[number]["key"];
type ReportView = "conclusion" | "locate" | "action" | "evidence";
type Job = { id: string; name: string; status?: string };
type Named = { skill_id?: string; name: string; proficiency?: string | null };
type EvidenceFragment = { id?: string; skill_id?: string; text: string; section?: string; evidence_level?: "mention" | "use" | "result" };
type Requirement = Named & { category?: string | null; category_id?: string | null; kind?: string };
type LedgerRow = { skill_id?: string; name: string; cover: number; side: string; category?: string | null; excerpt?: string };
type Report = {
  job_id: string;
  session_id?: string;
  preview_text?: string;
  band: string;
  direction?: string;
  jobs?: { job_id: string; name: string; band: string; required_coverage?: { covered: number; total: number }; shift_set?: Named[]; minimum_shift_skill_count?: number; transferable_engineering?: number; job_specific_experience?: number; job_specific_evidence?: number; experience_education_risk?: boolean }[];
  groups: {
    judge: {
      summary: string;
      band: string;
      cells: Record<string, string>;
      job_status?: string;
      shift_set: Named[];
    };
    locate: {
      neighbors: { job_id: string; name: string; band: string }[];
      hits: Named[];
      slice: {
        categories?: { id: string; name: string }[];
        requires?: Requirement[];
        period_delta?: { added?: Requirement[]; expired?: Requirement[] };
      };
    };
    act: {
      path: { skill_id: string; name: string; excerpt: string; why: string; url: string }[];
      ledger: LedgerRow[];
    };
    explain: {
      watching_copy: string;
      watching: Named[];
      half: Named[];
      extra: Named[];
      covered: Named[];
      notes: string;
      analysis?: {
        one_sentence?: string;
        core_judgments?: { fit_band?: string; advantage?: string; blocker?: string };
        strengths?: { text: string; quote?: string }[];
        risks?: { text: string; check_scope?: string }[];
        evidence_map?: { requirement_id?: string; requirement_name?: string; evidence_fragment_id?: string; evidence_level?: string; quote?: string }[];
        rewrites?: { original?: string; problem?: string; suggestion?: string; facts_to_add?: string[] }[];
        actions?: { rewrite?: unknown[]; capability?: { name?: string; why?: string }[] };
        narrative?: string;
      };
    };
  };
};
type Simulation = {
  simulations?: { job_id: string; name: string; original_band: string; simulated_band: string; shift_set: Named[] }[];
  migration_map?: { job_id: string; name: string; band: string; minimum_shift_skill_count: number; shared_capabilities: string[]; unique_requirements: string[] }[];
  market_signal_radar?: { skill_id: string; name: string; sample_occurrence_ratio: number; company_count: number; formal_requirement_reason: string }[];
};

function BandBadge({ band, size }: { band: string; size?: "lg" }) {
  return <span className="dx-band" data-level={BAND_LEVEL[band] ?? 0} data-size={size}>{band}</span>;
}

function Chips({ rows, state, empty = "无" }: { rows: Named[] | undefined; state: string; empty?: string }) {
  const list = (rows || []).filter((row) => row.name);
  if (!list.length) return <span className="dx-empty">{empty}</span>;
  return <div className="dx-chips">{list.map((row, index) => <span key={`${row.skill_id || row.name}-${index}`} className="dx-chip" data-state={state}>{row.name}</span>)}</div>;
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="dx-field"><span>{label}</span>{children}</label>;
}

export function DiagnoseForm() {
  const params = useSearchParams();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobId, setJobId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [phase, setPhase] = useState<"idle" | "run" | "done">("idle");
  const [step, setStep] = useState<Step>("upload");
  const [tick, setTick] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [report, setReport] = useState<Report | null>(null);
  const [over, setOver] = useState(false);
  const [copied, setCopied] = useState<"" | "link" | "actions">("");
  const [parsed, setParsed] = useState<{ skills?: Named[]; profile?: Record<string, string>; education_items?: { text: string }[]; experiences?: Record<string, string>[]; projects?: Record<string, string>[]; evidence_fragments?: EvidenceFragment[] } | null>(null);
  const [selectedJobIds, setSelectedJobIds] = useState<string[]>([]);
  const [recommendations, setRecommendations] = useState<{ job_id: string; name: string; band: string; reasons: { text: string }[] }[]>([]);
  const [userAdded, setUserAdded] = useState<Named[]>([]);
  const [newSkill, setNewSkill] = useState("");
  const [simulation, setSimulation] = useState<Simulation | null>(null);
  const [reportView, setReportView] = useState<ReportView>("conclusion");
  const [assumedSkills, setAssumedSkills] = useState<string[]>([]);
  const [showAllWatching, setShowAllWatching] = useState(false);
  const simulationRequest = useRef(0);
  const abort = useRef<AbortController | null>(null);
  const copyTimer = useRef<number | null>(null);

  useEffect(() => {
    fetch(`${API}/jobs?diagnosable=true`)
      .then((r) => r.json())
      .then((rows: Job[]) => {
        const list = Array.isArray(rows) ? rows : [];
        setJobs(list);
        const fromQuery = params.get("job_id") || params.get("job");
        const fallback = list.find((j) => j.name === DEFAULT_JOB)?.id || list[0]?.id || "";
        setJobId(list.some((job) => job.id === fromQuery) ? fromQuery! : fallback);
      })
      .catch(() => setJobs([]));
  }, [params]);

  useEffect(() => {
    const sid = params.get("session_id");
    const jid = params.get("job_id") || params.get("job");
    if (sid && jid) {
      setSessionId(sid);
      setJobId(jid);
      void runDiagnose(sid, jid);
    }
    return () => abort.current?.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (phase !== "run") return;
    const id = window.setInterval(() => setTick((n) => (n + 1) % 4), 700);
    return () => window.clearInterval(id);
  }, [phase]);

  useEffect(() => {
    if (phase !== "done" || !report || report.direction) return;
    const ids: ReportView[] = ["conclusion", "locate", "action", "evidence"];
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((entry) => entry.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
        if (visible) setReportView(visible.target.id.replace("report-", "") as ReportView);
      },
      { rootMargin: "-120px 0px -60% 0px" },
    );
    for (const id of ids) {
      const node = document.getElementById(`report-${id}`);
      if (node) observer.observe(node);
    }
    return () => observer.disconnect();
  }, [phase, report]);

  const link =
    sessionId && jobId && typeof window !== "undefined"
      ? `${window.location.origin}/diagnose?session_id=${sessionId}&job_id=${jobId}`
      : "";
  const jobName = (id: string) => jobs.find((j) => j.id === id)?.name || report?.jobs?.find((j) => j.job_id === id)?.name || report?.groups?.locate?.neighbors?.find((n) => n.job_id === id)?.name || "岗位";
  const stepIndex = STEPS.findIndex((item) => item.key === step);

  function flash(kind: "link" | "actions") {
    setCopied(kind);
    if (copyTimer.current) window.clearTimeout(copyTimer.current);
    copyTimer.current = window.setTimeout(() => setCopied(""), 1500);
  }

  async function runDiagnose(sid: string, jid: string, stayDone = false) {
    abort.current?.abort();
    const ctrl = new AbortController();
    abort.current = ctrl;
    if (!stayDone) {
      setPhase("run");
      setStep("run");
    }
    setError("");
    try {
      const res = await fetch(`${API}/diagnose`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sid, job_id: jid }),
        signal: ctrl.signal,
      });
      const body = await res.json();
      if (!res.ok) {
        if (res.status === 404) {
          setPhase("idle");
          setStep("upload");
          setReport(null);
          setError(body.error || "会话已过期");
          return;
        }
        throw new Error(body.error || "诊断失败");
      }
      setReport(body);
      setSimulation(null);
      setAssumedSkills([]);
      setShowAllWatching(false);
      setReportView("conclusion");
      setPhase("done");
      setStep("report");
      if (body.groups?.explain) {
        void fetch(`${API}/diagnose/simulate`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_id: sid, job_id: jid, assumed_skill_ids: [], watching_skill_ids: (body.groups.explain.watching || []).map((row: Named) => row.skill_id) }) }).then((response) => response.ok ? response.json() : null).then((value) => value && setSimulation(value));
      }
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      setError((err as Error).message);
      if (!stayDone) {
        setPhase("idle");
        setStep(sessionId ? "choose" : "upload");
      }
    }
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!jobId || busy) return;
    setError("");
    let sid = sessionId;
    if (file) {
      setBusy(true);
      try {
        const data = new FormData();
        data.append("file", file);
        data.append("consent", "true");
        const uploaded = await fetch(`${API}/sessions`, { method: "POST", body: data });
        const body = await uploaded.json();
        if (!uploaded.ok) {
          setError(body.error || "无法读取简历");
          return;
        }
        sid = body.session_id;
        setSessionId(sid);
        setPreview(body.preview_text || "");
        setParsed(body);
        setSelectedJobIds(jobId ? [jobId] : []);
        setStep("correct");
      } catch {
        setError("网络连接失败，请重试");
      } finally {
        setBusy(false);
      }
      return;
    }
    if (!sid) {
      setError("请先上传 PDF 或 docx");
      return;
    }
    await runDiagnose(sid, jobId);
  }

  async function continueCorrect() {
    if (!sessionId || !parsed || busy) return;
    setBusy(true);
    setError("");
    try {
      const saved = await fetch(`${API}/sessions/${sessionId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ skills: parsed.skills || [], profile: parsed.profile || {}, education_items: parsed.education_items || [], experiences: parsed.experiences || [], projects: parsed.projects || [], evidence_fragments: parsed.evidence_fragments || [], user_added: userAdded }),
      });
      if (!saved.ok) { const body = await saved.json().catch(() => ({})); setError(body.error || "校对结果保存失败"); return; }
      const response = await fetch(`${API}/diagnose/recommend`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_id: sessionId }) });
      const body = await response.json();
      if (!response.ok) { setError(body.error || "推荐岗位读取失败"); return; }
      setRecommendations(Array.isArray(body.jobs) ? body.jobs : []);
      setStep("choose");
    } catch {
      setError("网络连接失败，请重试");
    } finally {
      setBusy(false);
    }
  }

  async function compareSelected() {
    if (!sessionId || selectedJobIds.length === 0) return;
    if (selectedJobIds.length === 1) {
      await runDiagnose(sessionId, selectedJobIds[0]);
      return;
    }
    setPhase("run");
    setStep("run");
    setError("");
    try {
      const res = await fetch(`${API}/diagnose`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_id: sessionId, job_ids: selectedJobIds.slice(0, 2) }) });
      const body = await res.json();
      if (!res.ok) { setError(body.error || "无法生成对照"); setPhase("idle"); setStep("choose"); return; }
      setReport(body);
      setReportView("conclusion");
      setJobId(selectedJobIds[0]);
      setPhase("done");
      setStep("report");
    } catch { setError("网络连接失败，请重试"); setPhase("idle"); setStep("choose"); }
  }

  function pick(next: File | null) {
    abort.current?.abort();
    setFile(next);
    setSessionId("");
    setReport(null);
    setPreview("");
    setPhase("idle");
    setStep("upload");
    setParsed(null);
    setSelectedJobIds([]);
    setUserAdded([]);
    setNewSkill("");
    setError("");
  }

  function goToStep(target: Step) {
    if (target === "upload") pick(null);
    else if (target === "correct" && parsed) { setPhase("idle"); setReport(null); setStep("correct"); }
    else if (target === "choose" && sessionId) { setPhase("idle"); setReport(null); setStep("choose"); }
  }

  function canGoTo(index: number) {
    if (index >= stepIndex) return false;
    const target = STEPS[index].key;
    if (target === "upload") return true;
    if (target === "correct") return Boolean(parsed);
    if (target === "choose") return Boolean(sessionId) && recommendations.length > 0;
    return false;
  }

  function switchJob(id: string) {
    if (id === jobId) return;
    setJobId(id);
    if (sessionId && phase === "done") void runDiagnose(sessionId, id, true);
  }

  function names(rows: Named[] | undefined) {
    return (rows || []).map((row) => row.name).filter(Boolean).join("、") || "无";
  }

  function copyActions() {
    const analysis = report?.groups?.explain?.analysis;
    if (!analysis) return;
    const lines = ["表达轨：", ...(analysis.rewrites || []).slice(0, 5).map((item) => `- ${item.suggestion || item.original || "补充经历证据"}`), "能力轨：", ...(analysis.actions?.capability || []).map((item) => `- ${item.name || "能力缺口"}：${item.why || "补齐下一档要求"}`)];
    void navigator.clipboard.writeText(lines.join("\n"));
    flash("actions");
  }

  async function simulate(next: string[]) {
    if (!sessionId || !jobId) return;
    const requestId = ++simulationRequest.current;
    setAssumedSkills(next);
    const res = await fetch(`${API}/diagnose/simulate`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_id: sessionId, job_id: jobId, assumed_skill_ids: next, watching_skill_ids: (report?.groups.explain.watching || []).map((row) => row.skill_id) }) });
    const body = await res.json();
    if (requestId === simulationRequest.current && res.ok) setSimulation(body);
  }

  function jumpReport(view: ReportView) {
    setReportView(view);
    window.requestAnimationFrame(() => document.getElementById(`report-${view}`)?.scrollIntoView({ behavior: "smooth", block: "start" }));
  }

  function RequirementMap() {
    const slice = report?.groups.locate.slice;
    const delta = slice?.period_delta || {};
    const requires = [...(slice?.requires || [])];
    for (const skill of delta.expired || []) {
      if (!requires.some((item) => item.skill_id === skill.skill_id)) requires.push(skill);
    }
    const changed = new Set((delta.added || []).map((row) => row.skill_id));
    const expired = new Set((delta.expired || []).map((row) => row.skill_id));
    const coverById = new Map<string, number>();
    const coverByName = new Map<string, number>();
    for (const row of report?.groups.act.ledger || []) {
      if (row.skill_id) coverById.set(row.skill_id, row.cover);
      coverByName.set(row.name, row.cover);
    }
    for (const hit of report?.groups.locate.hits || []) {
      if (hit.skill_id) coverById.set(hit.skill_id, 1);
    }
    const categories = slice?.categories?.length
      ? [...slice.categories]
      : [...new Set(requires.map((row) => row.category).filter(Boolean))].map((name) => ({ id: name as string, name: name as string }));
    if (requires.some((skill) => !(skill.category_id || skill.category))) {
      categories.push({ id: "uncategorized", name: "未分类" });
    }
    const stateOf = (skill: Requirement) => {
      const cover = coverById.get(skill.skill_id || "") ?? coverByName.get(skill.name) ?? 0;
      if (expired.has(skill.skill_id)) return "expired";
      if (cover >= 1) return "covered";
      if (cover > 0) return "half";
      return "gap";
    };
    const rows = categories
      .map((category) => ({ category, skills: requires.filter((skill) => (skill.category_id || skill.category || "uncategorized") === category.id || skill.category === category.name) }))
      .filter((row) => row.skills.length);
    return (
      <div className="dx-reqmap" aria-label="岗位要求对照图">
        {rows.map(({ category, skills }) => (
          <div key={category.id} className="dx-reqrow">
            <span className="dx-reqcat">{category.name}</span>
            <div className="dx-chips">
              {skills.map((skill) => (
                <Link key={skill.skill_id} className="dx-chip" data-state={stateOf(skill)} data-kind={skill.kind} data-delta={changed.has(skill.skill_id) ? "1" : undefined} href={`/graph?job_id=${encodeURIComponent(jobId)}&skill_id=${encodeURIComponent(skill.skill_id || "")}`} title={`${skill.kind === "bonus" ? "加分" : "必备"} · 在图谱工作台查看`}>
                  {changed.has(skill.skill_id) ? "+ " : ""}{skill.name}
                </Link>
              ))}
            </div>
          </div>
        ))}
        <div className="dx-legend">
          <span data-state="covered">已覆盖</span>
          <span data-state="half">半档</span>
          <span data-state="gap">缺口</span>
          <span data-state="bonus">虚线边框为加分项</span>
          {(delta.added || []).length > 0 && <span data-state="added">+ 本期新增</span>}
        </div>
      </div>
    );
  }

  const analysis = report?.groups.explain.analysis;
  const watching = report?.groups.explain.watching || [];
  const watchingShown = showAllWatching ? watching : watching.slice(0, WATCHING_PREVIEW);
  const currentSim = simulation?.simulations?.[0];
  const capabilities = analysis?.actions?.capability || [];
  const extraCapabilities = capabilities.filter((row) => !(report?.groups.act.path || []).some((item) => item.name === row.name));

  return (
    <main id="main" className="page dx" data-phase={phase} data-step={step}>
      <ol className="dx-steps" aria-label="诊断步骤">
        {STEPS.map((item, index) => {
          const state = index < stepIndex ? "done" : index === stepIndex ? "active" : "todo";
          const clickable = canGoTo(index);
          return (
            <li key={item.key} data-state={state} aria-current={state === "active" ? "step" : undefined}>
              {clickable ? (
                <button type="button" onClick={() => goToStep(item.key)}><i>{index + 1}</i>{item.label}</button>
              ) : (
                <span><i>{index + 1}</i>{item.label}</span>
              )}
            </li>
          );
        })}
      </ol>

      {phase !== "done" && (
        <form className="dx-card" onSubmit={onSubmit} aria-busy={busy || phase === "run"}>
          <header className="dx-card-head">
            <div>
              <h1>{step === "upload" ? "上传简历" : step === "correct" ? "校对解析结果" : step === "choose" ? "选择对照岗位" : "正在生成对照"}</h1>
              <p className="dx-sub">
                {step === "upload" && "支持 PDF 与 docx。只发送提取文本，不保存原文件，会话保留一小时。"}
                {step === "correct" && "确认角色、年限、学历、技能和证据级。只保留简历原文能支持的内容。"}
                {step === "choose" && "推荐最多三个岗位，可选一或两个进行对照。未通过图谱版本与数据校验的岗位不进入报告。"}
                {step === "run" && "通常需要 10 秒左右。"}
              </p>
            </div>
            {step === "correct" && parsed && (
              <dl className="dx-stats">
                <div><dt>技能</dt><dd>{parsed.skills?.length || 0}</dd></div>
                <div><dt>证据片段</dt><dd>{parsed.evidence_fragments?.length || 0}</dd></div>
                <div><dt>补充</dt><dd>{userAdded.length}</dd></div>
              </dl>
            )}
            {step === "choose" && <span className="dx-counter" aria-live="polite">已选 {selectedJobIds.length}/2</span>}
          </header>

          {step === "upload" && (
            <div className="dx-body">
              <Field label="目标岗位">
                <select value={jobId} onChange={(e) => setJobId(e.target.value)}>
                  {jobs.map((job) => (
                    <option key={job.id} value={job.id}>{job.name}</option>
                  ))}
                </select>
              </Field>
              <label
                className="dx-drop"
                data-over={over ? "1" : undefined}
                data-filled={file ? "1" : undefined}
                onDragOver={(event) => { event.preventDefault(); setOver(true); }}
                onDragLeave={() => setOver(false)}
                onDrop={(event) => { event.preventDefault(); setOver(false); pick(event.dataTransfer.files?.[0] ?? null); }}
              >
                <input className="sr-only" type="file" accept=".pdf,.docx" onChange={(e) => pick(e.target.files?.[0] ?? null)} />
                <span className="dx-drop-icon" aria-hidden="true">{file ? "✓" : "↑"}</span>
                <span className="dx-drop-text">
                  <b>{file ? file.name : "拖入简历，或点击选择文件"}</b>
                  <small>{file ? `${(file.size / 1024).toFixed(0)} KB · 点击可更换` : "PDF / docx · 单个文件"}</small>
                </span>
              </label>
            </div>
          )}

          {step === "correct" && parsed && (
            <div className="dx-body">
              <section className="dx-section">
                <h2>基本信息</h2>
                <div className="dx-grid-3">
                  <Field label="当前角色"><input value={parsed.profile?.role || ""} onChange={(event) => setParsed((current) => current ? { ...current, profile: { ...(current.profile || {}), role: event.target.value } } : current)} placeholder="未标注" /></Field>
                  <Field label="工作年限"><input value={parsed.profile?.experience || ""} onChange={(event) => setParsed((current) => current ? { ...current, profile: { ...(current.profile || {}), experience: event.target.value } } : current)} placeholder="未标注" /></Field>
                  <Field label="学历"><input value={parsed.education_items?.[0]?.text || ""} onChange={(event) => setParsed((current) => current ? { ...current, education_items: [{ text: event.target.value }] } : current)} placeholder="未标注" /></Field>
                </div>
              </section>

              <section className="dx-section" aria-label="修改技能">
                <h2>已识别技能 <small>{parsed.skills?.length || 0} 项</small></h2>
                {(parsed.skills || []).length === 0 ? <p className="dx-empty">未从简历中识别出技能，可在下方补充。</p> : (
                  <ul className="dx-skill-list">
                    {(parsed.skills || []).map((skill, index) => (
                      <li key={`${skill.skill_id}-${index}`}>
                        <span>{skill.name}</span>
                        <select aria-label={`${skill.name} 熟练级`} value={skill.proficiency || ""} onChange={(event) => setParsed((current) => current ? { ...current, skills: (current.skills || []).map((item, i) => i === index ? { ...item, proficiency: event.target.value || null } : item) } : current)}>
                          <option value="">未标熟练级</option>
                          <option value="aware">了解</option>
                          <option value="able">熟悉</option>
                          <option value="expert">精通</option>
                        </select>
                        <button type="button" className="dx-icon-btn" aria-label={`移除 ${skill.name}`} onClick={() => setParsed((current) => current ? { ...current, skills: (current.skills || []).filter((_, i) => i !== index) } : current)}>×</button>
                      </li>
                    ))}
                  </ul>
                )}
                <div className="dx-inline">
                  <input aria-label="补充技能" value={newSkill} onChange={(event) => setNewSkill(event.target.value)} placeholder="补充你做过但简历没写的技能" onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); const name = newSkill.trim(); if (name) { setUserAdded((items) => [...items, { name, skill_id: name }]); setNewSkill(""); } } }} />
                  <button type="button" className="dx-btn" onClick={() => { const name = newSkill.trim(); if (name) { setUserAdded((items) => [...items, { name, skill_id: name }]); setNewSkill(""); } }}>加入待核对</button>
                </div>
                {userAdded.length > 0 && (
                  <div className="dx-kv-row">
                    <span className="dx-kv-key">待核对</span>
                    <div className="dx-chips">
                      {userAdded.map((item, index) => <button key={`${item.name}-${index}`} type="button" className="dx-chip dx-chip-btn" data-state="extra" onClick={() => setUserAdded((items) => items.filter((_, i) => i !== index))} aria-label={`移除 ${item.name}`}>{item.name} ×</button>)}
                    </div>
                  </div>
                )}
              </section>

              <section className="dx-section">
                <h2>证据级校对 <small>{parsed.evidence_fragments?.length || 0} 条</small></h2>
                {(parsed.evidence_fragments || []).length === 0 ? <p className="dx-empty">未提取到证据片段。带明确结果的经历会在报告中单独标出。</p> : (
                  <ul className="dx-evidence-list">
                    {(parsed.evidence_fragments || []).map((fragment, index) => (
                      <li key={`${fragment.id || fragment.skill_id}-${index}`}>
                        <span>{fragment.text}</span>
                        <select aria-label={`${fragment.text} 证据级`} value={fragment.evidence_level || "mention"} onChange={(event) => setParsed((current) => current ? { ...current, evidence_fragments: (current.evidence_fragments || []).map((item, i) => i === index ? { ...item, evidence_level: event.target.value as EvidenceFragment["evidence_level"] } : item) } : current)}>
                          <option value="mention">提及</option>
                          <option value="use">使用</option>
                          <option value="result">结果</option>
                        </select>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </div>
          )}

          {step === "choose" && (
            <div className="dx-body">
              <section className="dx-section">
                <h2>推荐岗位</h2>
                {recommendations.length === 0 ? <p className="dx-empty">暂无推荐，请在下方直接选择岗位。</p> : (
                  <div className="dx-recs">
                    {recommendations.map((item) => {
                      const checked = selectedJobIds.includes(item.job_id);
                      return (
                        <label key={item.job_id} className="dx-rec" data-checked={checked ? "1" : undefined}>
                          <input type="checkbox" checked={checked} onChange={(event) => setSelectedJobIds((current) => event.target.checked ? [...current.filter((id) => id !== item.job_id), item.job_id].slice(-2) : current.filter((id) => id !== item.job_id))} />
                          <span className="dx-rec-body">
                            <span className="dx-rec-head"><b>{item.name}</b><BandBadge band={item.band} /></span>
                            <small>{item.reasons.map((reason) => reason.text).join("；")}</small>
                          </span>
                        </label>
                      );
                    })}
                  </div>
                )}
              </section>
              <section className="dx-section">
                <h2>其他岗位</h2>
                <div className="dx-inline">
                  <select aria-label="搜索或改选岗位" value={jobId} onChange={(event) => setJobId(event.target.value)}>
                    {jobs.map((job) => <option key={job.id} value={job.id}>{job.name}</option>)}
                  </select>
                  <button type="button" className="dx-btn" disabled={selectedJobIds.includes(jobId)} onClick={() => setSelectedJobIds((ids) => [...ids.filter((id) => id !== jobId), jobId].slice(-2))}>加入对照</button>
                </div>
                {selectedJobIds.length > 0 && (
                  <div className="dx-kv-row">
                    <span className="dx-kv-key">对照</span>
                    <div className="dx-chips">
                      {selectedJobIds.map((id) => <button key={id} type="button" className="dx-chip dx-chip-btn" data-state="covered" onClick={() => setSelectedJobIds((ids) => ids.filter((item) => item !== id))} aria-label={`移除 ${jobName(id)}`}>{jobName(id)} ×</button>)}
                    </div>
                  </div>
                )}
              </section>
            </div>
          )}

          {step === "run" && (
            <ol className="dx-ticker" role="status" aria-live="polite">
              {TICKER.map((line, i) => (
                <li key={line} data-state={i < tick ? "done" : i === tick ? "active" : "todo"}>{line}</li>
              ))}
            </ol>
          )}

          {error && <p className="dx-error" role="alert">{error}</p>}

          {step !== "run" && (
            <footer className="dx-card-foot">
              <div>
                {step === "correct" && <button type="button" className="dx-btn dx-ghost" onClick={() => pick(null)}>重新上传</button>}
                {step === "choose" && <button type="button" className="dx-btn dx-ghost" onClick={() => setStep("correct")}>返回校对</button>}
              </div>
              <div>
                {step === "upload" && <button type="submit" className="dx-btn dx-primary" disabled={busy || !file}>{busy ? "解析中…" : "上传并解析"}</button>}
                {step === "correct" && <button type="button" className="dx-btn dx-primary" disabled={busy} onClick={continueCorrect}>{busy ? "保存中…" : "确认并选择岗位"}</button>}
                {step === "choose" && <button type="button" className="dx-btn dx-primary" onClick={compareSelected} disabled={selectedJobIds.length === 0}>开始对照{selectedJobIds.length === 2 ? "（两岗位）" : ""}</button>}
              </div>
            </footer>
          )}
        </form>
      )}

      {phase === "done" && report && (
        <div className="dx-report">
          <header className="dx-bar">
            <div className="dx-bar-title">
              <span className="dx-eyebrow">{report.direction ? "双岗位对照" : "对照岗位"}</span>
              <h1>{report.direction ? (report.jobs || []).map((item) => item.name).join(" · ") : jobName(jobId)}</h1>
              {!report.direction && <BandBadge band={report.groups.judge.band} size="lg" />}
            </div>
            {!report.direction && (
              <dl className="dx-bar-metrics">
                <div><dt>必备覆盖</dt><dd>{report.groups.judge.cells.required}</dd></div>
                <div><dt>半档</dt><dd>{report.groups.judge.cells.half}</dd></div>
                <div><dt>经验</dt><dd>{report.groups.judge.cells.experience}</dd></div>
                <div><dt>学历</dt><dd>{report.groups.judge.cells.education}</dd></div>
              </dl>
            )}
            <div className="dx-bar-actions">
              {!report.direction && <button type="button" className="dx-btn" onClick={() => { navigator.clipboard.writeText(link); flash("link"); }}>{copied === "link" ? "已复制" : "复制链接"}</button>}
              {analysis && <button type="button" className="dx-btn" onClick={copyActions}>{copied === "actions" ? "已复制" : "复制行动"}</button>}
              <button type="button" className="dx-btn" onClick={() => window.print()}>打印</button>
              <button type="button" className="dx-btn dx-ghost" onClick={() => { setPhase("idle"); setReport(null); setStep(recommendations.length ? "choose" : "upload"); }}>再分析一次</button>
            </div>
          </header>
          {error && <p className="dx-error" role="alert">{error}</p>}

          {report.direction ? (
            <section className="dx-direction" aria-live="polite">
              <p className="dx-verdict">{report.direction === "无法区分方向" ? "两个岗位当前没有可区分的优势，请比较各自换档条件。" : `当前更接近：${report.direction}`}</p>
              <div className="dx-table-wrap">
                <table className="dx-table dx-compare">
                  <thead>
                    <tr><th scope="col">指标</th>{(report.jobs || []).map((item) => <th key={item.job_id} scope="col" data-lead={item.name === report.direction ? "1" : undefined}>{item.name}</th>)}</tr>
                  </thead>
                  <tbody>
                    <tr><th scope="row">当前档位</th>{(report.jobs || []).map((item) => <td key={item.job_id}><BandBadge band={item.band} /></td>)}</tr>
                    <tr><th scope="row">必备覆盖</th>{(report.jobs || []).map((item) => <td key={item.job_id}>{item.required_coverage?.covered ?? 0}/{item.required_coverage?.total ?? 0}</td>)}</tr>
                    <tr><th scope="row">岗位专属证据</th>{(report.jobs || []).map((item) => <td key={item.job_id}>{item.job_specific_evidence ?? 0} 项</td>)}</tr>
                    <tr><th scope="row">可迁移工程能力</th>{(report.jobs || []).map((item) => <td key={item.job_id}>{item.transferable_engineering ?? 0} 项</td>)}</tr>
                    <tr><th scope="row">岗位独有经历</th>{(report.jobs || []).map((item) => <td key={item.job_id}>{item.job_specific_experience ?? 0} 项</td>)}</tr>
                    <tr><th scope="row">最小换档</th>{(report.jobs || []).map((item) => <td key={item.job_id}>{item.minimum_shift_skill_count ?? item.shift_set?.length ?? 0} 项</td>)}</tr>
                    <tr><th scope="row">换档条件</th>{(report.jobs || []).map((item) => <td key={item.job_id}><Chips rows={item.shift_set} state="gap" /></td>)}</tr>
                    <tr><th scope="row">经验 / 学历风险</th>{(report.jobs || []).map((item) => <td key={item.job_id}>{item.experience_education_risk ? "有" : "无"}</td>)}</tr>
                  </tbody>
                </table>
              </div>
              <div className="dx-inline">
                {(report.jobs || []).map((item) => <button key={item.job_id} type="button" className="dx-btn" onClick={() => { setSelectedJobIds([item.job_id]); setJobId(item.job_id); void runDiagnose(sessionId, item.job_id); }}>查看 {item.name} 详细报告</button>)}
              </div>
            </section>
          ) : (
            <div className="dx-split">
              <aside className="dx-rail">
                <nav className="dx-rail-nav" aria-label="报告视图">
                  {([["conclusion", "结论"], ["locate", "定位"], ["action", "行动"], ["evidence", "依据"]] as const).map(([view, label]) => (
                    <button key={view} type="button" aria-pressed={reportView === view} onClick={() => jumpReport(view)}>{label}</button>
                  ))}
                </nav>
                <details className="dx-resume">
                  <summary>简历摘录</summary>
                  <pre>{report.preview_text || preview || "（无预览）"}</pre>
                </details>
              </aside>

              <div className="dx-content">
                <section id="report-conclusion" className="dx-panel">
                  <h2>结论</h2>
                  <p className="dx-verdict">{report.groups.judge.summary}</p>
                  <div className="dx-metrics">
                    <div className="dx-metric"><span>档位</span><strong><BandBadge band={report.groups.judge.band} /></strong></div>
                    <div className="dx-metric"><span>必备覆盖</span><strong>{report.groups.judge.cells.required}</strong></div>
                    <div className="dx-metric"><span>半档</span><strong>{report.groups.judge.cells.half}</strong></div>
                    <div className="dx-metric"><span>经验</span><strong>{report.groups.judge.cells.experience}</strong></div>
                    <div className="dx-metric"><span>学历</span><strong>{report.groups.judge.cells.education}</strong></div>
                    <div className="dx-metric"><span>目标岗状态</span><strong>{report.groups.judge.job_status || "—"}</strong></div>
                  </div>
                  <div className="dx-kv">
                    <div className="dx-kv-row"><span className="dx-kv-key">换档条件</span><Chips rows={report.groups.judge.shift_set} state="gap" empty="已满足下一档必备要求" /></div>
                  </div>

                  {analysis && (
                    <div className="dx-analysis" aria-label="AI 简历分析">
                      <h3>简历分析</h3>
                      {analysis.one_sentence && <p className="dx-lead">{analysis.one_sentence}</p>}
                      <div className="dx-grid-2">
                        <div className="dx-note"><span className="dx-note-key">优势</span><p>{analysis.core_judgments?.advantage || "—"}</p></div>
                        <div className="dx-note"><span className="dx-note-key">阻碍</span><p>{analysis.core_judgments?.blocker || "—"}</p></div>
                      </div>
                      {(analysis.strengths || []).length > 0 && (
                        <div className="dx-kv-row"><span className="dx-kv-key">有依据</span><ul className="dx-list">{(analysis.strengths || []).map((item) => <li key={item.text}>{item.quote || item.text}</li>)}</ul></div>
                      )}
                      {(analysis.risks || []).length > 0 && (
                        <div className="dx-kv-row"><span className="dx-kv-key">待核对</span><ul className="dx-list">{(analysis.risks || []).map((item) => <li key={item.text}>{item.text}{item.check_scope && <small> · {item.check_scope}</small>}</li>)}</ul></div>
                      )}
                      {(analysis.rewrites || []).length > 0 && (
                        <div className="dx-rewrites">
                          {(analysis.rewrites || []).slice(0, 5).map((item, index) => (
                            <details key={`${item.original}-${index}`}>
                              <summary>表达建议 {index + 1}<small>{item.problem}</small></summary>
                              <dl className="dx-rewrite">
                                <dt>原文</dt><dd>{item.original}</dd>
                                <dt>建议</dt><dd>{item.suggestion}</dd>
                                <dt>仍需补充</dt><dd>{(item.facts_to_add || []).join("、") || "无需补充"}</dd>
                              </dl>
                            </details>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </section>

                <section id="report-locate" className="dx-panel">
                  <h2>定位</h2>
                  <div className="dx-kv-row">
                    <span className="dx-kv-key">相邻岗位</span>
                    <div className="dx-seg" role="group" aria-label="切换对照岗位">
                      {report.groups.locate.neighbors.map((n) => (
                        <button key={n.job_id} type="button" aria-pressed={n.job_id === jobId} onClick={() => switchJob(n.job_id)}>{n.name}<BandBadge band={n.band} /></button>
                      ))}
                    </div>
                  </div>
                  <RequirementMap />
                </section>

                <section id="report-action" className="dx-panel">
                  <h2>行动</h2>
                  {report.groups.act.path.length > 0 ? (
                    <>
                      <div className="dx-sim" aria-labelledby="simulator-title">
                        <div className="dx-sim-head"><h3 id="simulator-title">换档模拟</h3><small>勾选假设已具备的能力，结果尚未被简历证明</small></div>
                        <div className="dx-chips">
                          {report.groups.act.path.map((item) => (
                            <label key={item.skill_id} className="dx-chip dx-chip-check" data-state={assumedSkills.includes(item.skill_id) ? "covered" : "gap"}>
                              <input type="checkbox" checked={assumedSkills.includes(item.skill_id)} onChange={(event) => simulate(event.target.checked ? [...assumedSkills, item.skill_id] : assumedSkills.filter((id) => id !== item.skill_id))} />
                              {item.name}
                            </label>
                          ))}
                        </div>
                        <p className="dx-sim-result" aria-live="polite" data-active={assumedSkills.length ? "1" : undefined}>
                          {currentSim && assumedSkills.length ? (
                            <><BandBadge band={currentSim.original_band} /><span aria-hidden="true">→</span><BandBadge band={currentSim.simulated_band} /><span>下一换档：{names(currentSim.shift_set)}</span></>
                          ) : "勾选后显示假设档位与下一换档条件"}
                        </p>
                      </div>
                      <ol className="dx-actions">
                        {report.groups.act.path.map((item, index) => {
                          const capability = capabilities.find((row) => row.name === item.name);
                          return (
                            <li key={item.skill_id}>
                              <span className="dx-actions-index">{index + 1}</span>
                              <div>
                                <div className="dx-actions-head"><b>{item.name}</b><span className="dx-tag">{item.why}</span>{capability?.why && <span className="dx-muted">{capability.why}</span>}{item.url ? <a href={item.url} rel="noreferrer" target="_blank">学习资源 ↗</a> : null}</div>
                                {item.excerpt && <p>岗位原文：{item.excerpt}</p>}
                              </div>
                            </li>
                          );
                        })}
                      </ol>
                    </>
                  ) : <p className="dx-empty">当前档位没有待补的正式缺口。</p>}
                  {extraCapabilities.length > 0 && (
                    <div className="dx-kv-row"><span className="dx-kv-key">能力轨</span><ul className="dx-list">{extraCapabilities.map((item) => <li key={item.name}><b>{item.name}</b> · {item.why}</li>)}</ul></div>
                  )}
                  {analysis?.narrative && <details className="dx-details"><summary>面试自我介绍草稿</summary><p>{analysis.narrative}</p></details>}
                </section>

                <section id="report-evidence" className="dx-panel">
                  <h2>依据</h2>
                  <div className="dx-table-wrap">
                    <table className="dx-table dx-ledger">
                      <thead>
                        <tr><th scope="col">技能点</th><th scope="col">类别</th><th scope="col">边</th><th scope="col">覆盖</th></tr>
                      </thead>
                      <tbody>
                        {report.groups.act.ledger.map((row) => (
                          <tr key={`${row.side}-${row.name}`}>
                            <td>{row.name}</td>
                            <td className="dx-muted">{row.category || "—"}</td>
                            <td><span className="dx-tag" data-side={row.side}>{row.side === "bonus" ? "加分" : "必备"}</span></td>
                            <td><span className="dx-cover"><i style={{ width: `${Math.round(Math.min(1, Math.max(0, row.cover)) * 100)}%` }} /><b>{row.cover}</b></span></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="dx-kv">
                    <div className="dx-kv-row"><span className="dx-kv-key">已覆盖</span><Chips rows={report.groups.explain.covered} state="covered" /></div>
                    <div className="dx-kv-row"><span className="dx-kv-key">半档</span><Chips rows={report.groups.explain.half} state="half" /></div>
                    <div className="dx-kv-row"><span className="dx-kv-key">简历多出</span><Chips rows={report.groups.explain.extra} state="extra" /></div>
                    <div className="dx-kv-row">
                      <span className="dx-kv-key">观测中<small>{watching.length}</small></span>
                      <div>
                        <Chips rows={watchingShown} state="watch" />
                        {watching.length > WATCHING_PREVIEW && <button type="button" className="dx-link" onClick={() => setShowAllWatching((v) => !v)}>{showAllWatching ? "收起" : `展开全部 ${watching.length} 项`}</button>}
                        <p className="dx-fine">{report.groups.explain.watching_copy}</p>
                      </div>
                    </div>
                  </div>
                  <p className="dx-fine">{report.groups.explain.notes}</p>
                  {analysis && (analysis.evidence_map || []).length > 0 && (
                    <details className="dx-details">
                      <summary>简历证据地图<small>{(analysis.evidence_map || []).length} 项要求</small></summary>
                      <div className="dx-table-wrap">
                        <table className="dx-table">
                          <thead><tr><th scope="col">要求</th><th scope="col">证据级</th><th scope="col">引文</th></tr></thead>
                          <tbody>
                            {(analysis.evidence_map || []).map((item, index) => (
                              <tr key={`${item.requirement_id}-${item.evidence_fragment_id || index}`}>
                                <td>{item.requirement_name || item.requirement_id}</td>
                                <td><span className="dx-tag" data-level={item.evidence_level}>{item.evidence_level || "未提及"}</span></td>
                                <td className="dx-muted">{item.quote || "简历中未找到对应证据"}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </details>
                  )}
                </section>
              </div>
            </div>
          )}
        </div>
      )}
    </main>
  );
}
