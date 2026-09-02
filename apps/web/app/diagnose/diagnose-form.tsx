"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TICKER = [
  "在对你的技能",
  "在读这个岗现在要什么",
  "在标缺口和半档",
  "在定档位",
];
const DEFAULT_JOB = "大模型应用工程师";

type Job = { id: string; name: string; status?: string };
type Named = { skill_id?: string; name: string };
type Requirement = Named & { category?: string | null; category_id?: string | null };
type Report = {
  job_id: string;
  session_id?: string;
  preview_text?: string;
  band: string;
  direction?: string;
  jobs?: { job_id: string; name: string; band: string; required_coverage?: { covered: number; total: number }; shift_set?: Named[]; transferable_engineering?: number; job_specific_experience?: number; experience_education_risk?: boolean }[];
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
      ledger: { name: string; cover: number; side: string }[];
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
        evidence_map?: { skill_id?: string; name?: string; state?: string; evidence_fragment_id?: string; quote?: string; check_scope?: string }[];
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

export function DiagnoseForm() {
  const params = useSearchParams();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobId, setJobId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [phase, setPhase] = useState<"idle" | "run" | "done">("idle");
  const [step, setStep] = useState<"upload" | "correct" | "choose" | "run" | "report">("upload");
  const [tick, setTick] = useState(0);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [report, setReport] = useState<Report | null>(null);
  const [over, setOver] = useState(false);
  const [copied, setCopied] = useState(false);
  const [parsed, setParsed] = useState<{ skills?: Named[]; profile?: Record<string, string>; education_items?: { text: string }[]; evidence_fragments?: Record<string, unknown>[] } | null>(null);
  const [selectedJobIds, setSelectedJobIds] = useState<string[]>([]);
  const [recommendations, setRecommendations] = useState<{ job_id: string; name: string; band: string; reasons: { text: string }[] }[]>([]);
  const [simulation, setSimulation] = useState<Simulation | null>(null);
  const [assumedSkills, setAssumedSkills] = useState<string[]>([]);
  const simulationRequest = useRef(0);
  const abort = useRef<AbortController | null>(null);

  useEffect(() => {
    fetch(`${API}/jobs`)
      .then((r) => r.json())
      .then((rows: Job[]) => {
        const list = Array.isArray(rows) ? rows : [];
        setJobs(list);
        const fromQuery = params.get("job_id") || params.get("job");
        const fallback = list.find((j) => j.name === DEFAULT_JOB)?.id || list[0]?.id || "";
        setJobId(fromQuery || fallback);
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

  const link =
    sessionId && jobId && typeof window !== "undefined"
      ? `${window.location.origin}/diagnose?session_id=${sessionId}&job_id=${jobId}`
      : "";

  async function runDiagnose(sid: string, jid: string, stayDone = false) {
    abort.current?.abort();
    const ctrl = new AbortController();
    abort.current = ctrl;
    if (!stayDone) setPhase("run");
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
          setReport(null);
          setError(body.error || "会话已过期");
          return;
        }
        throw new Error(body.error || "诊断失败");
      }
      setReport(body);
      setPhase("done");
      setStep("report");
      if (body.groups?.explain) {
        void fetch(`${API}/diagnose/simulate`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_id: sid, job_id: jid, assumed_skill_ids: [], watching_skill_ids: (body.groups.explain.watching || []).map((row: Named) => row.skill_id) }) }).then((response) => response.ok ? response.json() : null).then((value) => value && setSimulation(value));
      }
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      setError((err as Error).message);
      setPhase("idle");
    }
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!jobId) return;
    setError("");
    let sid = sessionId;
    if (file) {
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
      return;
    }
    if (!sid) {
      setError("请先上传 PDF 或 docx");
      return;
    }
    await runDiagnose(sid, jobId);
  }

  async function continueCorrect() {
    if (!sessionId || !parsed) return;
    await fetch(`${API}/sessions/${sessionId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ skills: parsed.skills || [], profile: parsed.profile || {}, education_items: parsed.education_items || [], evidence_fragments: parsed.evidence_fragments || [] }),
    });
    const response = await fetch(`${API}/diagnose/recommend`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_id: sessionId }) });
    const body = await response.json();
    setRecommendations(Array.isArray(body.jobs) ? body.jobs : []);
    setStep("choose");
  }

  async function compareSelected() {
    if (!sessionId || selectedJobIds.length === 0) return;
    setPhase("run");
    setStep("run");
    setError("");
    const res = await fetch(`${API}/diagnose`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_id: sessionId, job_ids: selectedJobIds.slice(0, 2) }) });
    const body = await res.json();
    if (!res.ok) { setError(body.error || "无法生成对照"); setPhase("idle"); setStep("choose"); return; }
    setReport(body);
    setJobId(selectedJobIds[0]);
    setPhase("done");
    setStep("report");
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
    const analysis = report?.groups.explain.analysis;
    if (!analysis) return;
    const lines = ["表达轨：", ...(analysis.rewrites || []).slice(0, 5).map((item) => `- ${item.suggestion || item.original || "补充经历证据"}`), "能力轨：", ...(analysis.actions?.capability || []).map((item) => `- ${item.name || "能力缺口"}：${item.why || "补齐下一档要求"}`)];
    void navigator.clipboard.writeText(lines.join("\n"));
  }

  async function simulate(next: string[]) {
    if (!sessionId || !jobId) return;
    const requestId = ++simulationRequest.current;
    setAssumedSkills(next);
    const res = await fetch(`${API}/diagnose/simulate`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_id: sessionId, job_id: jobId, assumed_skill_ids: next, watching_skill_ids: (report?.groups.explain.watching || []).map((row) => row.skill_id) }) });
    const body = await res.json();
    if (requestId === simulationRequest.current && res.ok) setSimulation(body);
  }

  function MiniGraph() {
    const slice = report?.groups.locate.slice;
    const delta = slice?.period_delta || {};
    const requires = [...(slice?.requires || [])];
    for (const skill of delta.expired || []) {
      if (!requires.some((item) => item.skill_id === skill.skill_id)) requires.push(skill);
    }
    const changed = new Set((delta.added || []).map((row) => row.skill_id));
    const categories = slice?.categories?.length
      ? [...slice.categories]
      : [...new Set(requires.map((row) => row.category).filter(Boolean))].map((name) => ({ id: name as string, name: name as string }));
    if (requires.some((skill) => !(skill.category_id || skill.category))) {
      categories.push({ id: "uncategorized", name: "未分类" });
    }
    return (
      <div className="mini-graph" aria-label="岗位要求对照图">
        <span className="mini-node mini-job">{jobs.find((j) => j.id === jobId)?.name || "岗位"}</span>
        {categories.map((category) => {
          const skills = requires.filter((skill) => (skill.category_id || skill.category || "uncategorized") === category.id || skill.category === category.name);
          return (
            <section key={category.id} className="mini-category">
              <span className="mini-node">{category.name}</span>
              <div className="mini-skills">
                {skills.map((skill) => (
                  <Link key={skill.skill_id} className="mini-skill" data-delta={changed.has(skill.skill_id) ? "1" : undefined} href={`/graph?job_id=${encodeURIComponent(jobId)}&skill_id=${encodeURIComponent(skill.skill_id || "")}`}>
                    {changed.has(skill.skill_id) ? "+" : ""}{skill.name}
                  </Link>
                ))}
              </div>
            </section>
          );
        })}
      </div>
    );
  }

  return (
    <main id="main" className="page diagnose" data-phase={phase} data-step={step}>
      <ol className="diagnose-steps" aria-label="诊断步骤">
        {["上传简历", "校对解析", "选择岗位", "生成对照", "查看报告"].map((label, index) => (
          <li key={label} data-active={(index === ["upload", "correct", "choose", "run", "report"].indexOf(step)) ? "1" : undefined}>{index + 1}. {label}</li>
        ))}
      </ol>
      {phase !== "done" && (
        <form className="diagnose-form" onSubmit={onSubmit}>
          <h1>{step === "upload" ? "上传简历" : step === "correct" ? "校对解析结果" : step === "choose" ? "选择目标岗位" : "正在生成对照"}</h1>
          {step === "choose" && <p className="diagnostic-meta">生成前会核对图谱发布版本、岗位更新时间、数据状态和去重招聘公司数量。未通过校验的岗位不会进入报告。</p>}
          {step === "upload" && <label>
            目标岗位
            <select value={jobId} onChange={(e) => setJobId(e.target.value)}>
              {jobs.map((job) => (
                <option key={job.id} value={job.id}>
                  {job.name}
                </option>
              ))}
            </select>
          </label>}
          {step === "upload" && <label
            className={`drop${over ? " over" : ""}`}
            onDragOver={(event) => {
              event.preventDefault();
              setOver(true);
            }}
            onDragLeave={() => setOver(false)}
            onDrop={(event) => {
              event.preventDefault();
              setOver(false);
              pick(event.dataTransfer.files?.[0] ?? null);
            }}
          >
            简历（PDF / docx）
            <input
              className="sr-only"
              type="file"
              accept=".pdf,.docx"
              onChange={(e) => pick(e.target.files?.[0] ?? null)}
            />
            <span>{file ? file.name : "选择文件或拖入此处"}</span>
          </label>}
          {step === "upload" && <details className="privacy-details"><summary>隐私与数据处理详情</summary><p>上传后只发送提取出的文本给当前配置的模型服务商。产品数据库不保存简历原文件，会话最长保留一小时。</p></details>}
          {step === "correct" && <section className="correction-panel" aria-label="解析校对"><p className="hint">请确认角色、年限、学历、技能和证据级。你可以返回重传，提交前不会生成岗位结论。</p><dl className="readout"><div><dt>当前角色</dt><dd>{parsed?.profile?.role || "未标注"}</dd></div><div><dt>工作年限</dt><dd>{parsed?.profile?.experience || "未标注"}</dd></div><div><dt>学历</dt><dd>{parsed?.education_items?.map((item) => item.text).join("、") || "未标注"}</dd></div></dl><p><b>已识别技能：</b>{names(parsed?.skills)}</p><p className="hint">证据片段：{parsed?.evidence_fragments?.length || 0} 条。明确结果会在报告中单独标出。</p><button type="button" onClick={continueCorrect}>确认并选择岗位</button></section>}
          {step === "choose" && <section className="choose-panel"><p className="hint">推荐岗位最多三个。可选择一个或两个岗位进行对照。</p><div className="recommendations">{recommendations.map((item) => <label key={item.job_id} className="recommendation"><input type="checkbox" checked={selectedJobIds.includes(item.job_id)} onChange={(event) => setSelectedJobIds((current) => event.target.checked ? [...current.filter((id) => id !== item.job_id), item.job_id].slice(-2) : current.filter((id) => id !== item.job_id))} /><span><b>{item.name}</b><small>{item.band} · {item.reasons.map((reason) => reason.text).join("；")}</small></span></label>)}</div><label>搜索或改选岗位<select value={jobId} onChange={(event) => setJobId(event.target.value)}>{jobs.map((job) => <option key={job.id} value={job.id}>{job.name}</option>)}</select></label><button type="button" onClick={() => setSelectedJobIds((ids) => ids.length ? ids : [jobId])}>加入当前岗位</button></section>}
          <div className="diagnose-actions">
            {step === "correct" && <button type="button" onClick={() => pick(null)}>重新上传</button>}
            {step === "choose" && <button type="button" onClick={() => setStep("correct")}>返回校对</button>}
            {step === "upload" && <button type="submit" disabled={phase === "run"}>上传并解析</button>}
            {step === "choose" && <button type="button" onClick={compareSelected} disabled={selectedJobIds.length === 0}>生成对照</button>}
            {step === "run" && (
              <p className="ticker" aria-live="polite">
                {TICKER.map((line, i) => (
                  <span key={line} data-on={i === tick ? "1" : "0"}>
                    {line}
                  </span>
                ))}
              </p>
            )}
          </div>
          {error && <p className="diagnose-error">{error}</p>}
        </form>
      )}

      {phase === "done" && report && (
        <div className="diagnose-done">
          <header className="diagnose-bar">
            <strong>{jobs.find((j) => j.id === jobId)?.name}</strong>
            <button
              type="button"
              onClick={() => {
                navigator.clipboard.writeText(link);
                setCopied(true);
                window.setTimeout(() => setCopied(false), 1500);
              }}
            >
              复制对照链接
            </button>
            <button type="button" onClick={() => window.print()}>打印结论</button>
            <button type="button" onClick={copyActions}>复制双轨行动</button>
            {copied ? (
              <span className="hint" role="status">
                已复制
              </span>
            ) : null}
            <button
              type="button"
              onClick={() => {
                setPhase("idle");
                setReport(null);
                setStep("choose");
              }}
            >
              再分析一次
            </button>
          </header>
          {report.direction ? <section className="direction-report" aria-live="polite">
            <p className="verdict">{report.direction === "无法区分方向" ? "两个岗位当前没有可区分的优势，请比较各自换档条件。" : `当前更接近：${report.direction}`}</p>
            <div className="direction-cards">{(report.jobs || []).map((item) => <article key={item.job_id}><h2>{item.name}</h2><p>当前档位：{item.band}</p><p>必备覆盖：{item.required_coverage?.covered ?? 0}/{item.required_coverage?.total ?? 0}</p><p>可迁移工程能力：{item.transferable_engineering ?? 0} 项</p><p>岗位独有经历：{item.job_specific_experience ?? 0} 项</p><p>换档条件：{names(item.shift_set)}</p></article>)}</div>
          </section> : <div className="diagnose-split">
            <aside>
              <h2>简历</h2>
              <pre>{report.preview_text || preview || "（无预览）"}</pre>
            </aside>
            <section>
              <h2>判断</h2>
              <p className="verdict">{report.groups.judge.summary}</p>
              <p>档位 {report.groups.judge.band}</p>
              <dl className="readout">
                <div>
                  <dt>必备覆盖</dt>
                  <dd>{report.groups.judge.cells.required}</dd>
                </div>
                <div>
                  <dt>半档</dt>
                  <dd>{report.groups.judge.cells.half}</dd>
                </div>
                <div>
                  <dt>经验</dt>
                  <dd>{report.groups.judge.cells.experience}</dd>
                </div>
                <div>
                  <dt>学历</dt>
                  <dd>{report.groups.judge.cells.education}</dd>
                </div>
              </dl>
              <p>目标岗 {report.groups.judge.job_status}</p>
              <p>换档条件 {names(report.groups.judge.shift_set)}</p>

              {report.groups.explain.analysis && <section className="analysis-card" aria-label="AI 简历分析">
                <h2>简历分析</h2>
                <p className="verdict">{report.groups.explain.analysis.one_sentence}</p>
                <p><b>优势：</b>{report.groups.explain.analysis.core_judgments?.advantage}</p>
                <p><b>阻碍：</b>{report.groups.explain.analysis.core_judgments?.blocker}</p>
                {(report.groups.explain.analysis.strengths || []).map((item) => <p key={item.text}>有依据：{item.quote || item.text}</p>)}
                {(report.groups.explain.analysis.risks || []).map((item) => <p key={item.text}>待核对：{item.text}（{item.check_scope}）</p>)}
                <details><summary>查看简历证据地图</summary><div className="evidence-map-list">{(report.groups.explain.analysis.evidence_map || []).map((item) => <div key={item.skill_id}><b>{item.name}</b><span>{item.state}</span><small>{item.quote || item.check_scope}</small></div>)}</div></details>
                {(report.groups.explain.analysis.rewrites || []).slice(0, 5).map((item, index) => <details key={`${item.original}-${index}`}><summary>表达建议 {index + 1}</summary><p>原文：{item.original}</p><p>问题：{item.problem}</p><p>建议：{item.suggestion}</p><p className="hint">仍需补充：{(item.facts_to_add || []).join("、") || "无需补充"}</p></details>)}
                {(report.groups.explain.analysis.actions?.capability || []).map((item) => <p key={item.name}>能力轨：{item.name}。{item.why}</p>)}
                {report.groups.explain.analysis.narrative && <details><summary>面试自我介绍草稿</summary><p>{report.groups.explain.analysis.narrative}</p></details>}
              </section>}

              <h2>定位</h2>
              <div className="neighbors">
                {report.groups.locate.neighbors.map((n) => (
                  <button
                    key={n.job_id}
                    type="button"
                    data-current={n.job_id === jobId ? "1" : "0"}
                    onClick={() => switchJob(n.job_id)}
                  >
                    {n.name} · {n.band}
                  </button>
                ))}
              </div>
              <MiniGraph />
              <p>已对齐 {names(report.groups.locate.hits)}</p>

              <h2>行动</h2>
              <section className="simulator" aria-labelledby="simulator-title">
                <div className="row"><h3 id="simulator-title">换档模拟器</h3><span className="hint">假设结果，尚未被简历证明</span></div>
                <div className="simulator-options">{report.groups.act.path.map((step) => <label key={step.skill_id}><input type="checkbox" checked={assumedSkills.includes(step.skill_id)} onChange={(event) => simulate(event.target.checked ? [...assumedSkills, step.skill_id] : assumedSkills.filter((id) => id !== step.skill_id))} />{step.name}</label>)}</div>
                <p className="simulator-result" aria-live="polite">{simulation?.simulations?.[0] ? `当前${simulation.simulations[0].original_band} → 假设${simulation.simulations[0].simulated_band}。下一换档：${names(simulation.simulations[0].shift_set)}` : "选择一项正式缺口查看假设档位"}</p>
                {(simulation?.migration_map || []).length > 0 && <div className="migration-map">{simulation?.migration_map?.map((item) => <article key={item.job_id}><b>{item.name}</b><span>{item.band} · 还需 {item.minimum_shift_skill_count} 项</span><small>共享：{item.shared_capabilities.join("、") || "无"}</small><small>独有：{item.unique_requirements.slice(0, 3).join("、") || "无"}</small></article>)}</div>}
                {(simulation?.market_signal_radar || []).length > 0 && <div className="market-radar"><b>市场观察</b>{simulation?.market_signal_radar?.map((item) => <span key={item.skill_id}>{item.name} · 招聘样本 {Math.round(item.sample_occurrence_ratio * 100)}% · {item.company_count} 家公司</span>)}</div>}
              </section>
              <ol>
                {report.groups.act.path.map((step) => (
                  <li key={step.skill_id}>
                    {step.name}（{step.why}）
                    {step.excerpt ? ` · ${step.excerpt}` : ""}
                    {step.url ? (
                      <>
                        {" "}
                        <a href={step.url} rel="noreferrer" target="_blank">
                          资源
                        </a>
                      </>
                    ) : null}
                  </li>
                ))}
              </ol>
              <table className="ledger">
                <thead>
                  <tr>
                    <th>技能点</th>
                    <th>边</th>
                    <th>覆盖</th>
                  </tr>
                </thead>
                <tbody>
                  {report.groups.act.ledger.map((row) => (
                    <tr key={`${row.side}-${row.name}`}>
                      <td>{row.name}</td>
                      <td>{row.side === "bonus" ? "加分" : "必备"}</td>
                      <td>{row.cover}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <h2>解释</h2>
              <p>{report.groups.explain.watching_copy}</p>
              <p>观测中 {names(report.groups.explain.watching)}</p>
              <p>半档 {names(report.groups.explain.half)}</p>
              <p>已覆盖 {names(report.groups.explain.covered)}</p>
              <p>简历多出来的 {names(report.groups.explain.extra)}</p>
              <p>{report.groups.explain.notes}</p>
            </section>
          </div>}
        </div>
      )}
    </main>
  );
}
