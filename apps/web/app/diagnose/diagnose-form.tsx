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
    };
  };
};

export function DiagnoseForm() {
  const params = useSearchParams();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobId, setJobId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [phase, setPhase] = useState<"idle" | "run" | "done">("idle");
  const [tick, setTick] = useState(0);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [report, setReport] = useState<Report | null>(null);
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
      const uploaded = await fetch(`${API}/sessions`, { method: "POST", body: data });
      const body = await uploaded.json();
      if (!uploaded.ok) {
        setError(body.error || "无法读取简历");
        return;
      }
      sid = body.session_id;
      setSessionId(sid);
      setPreview(body.preview_text || "");
    }
    if (!sid) {
      setError("请先上传 PDF 或 docx");
      return;
    }
    await runDiagnose(sid, jobId);
  }

  function switchJob(id: string) {
    if (id === jobId) return;
    setJobId(id);
    if (sessionId && phase === "done") void runDiagnose(sessionId, id, true);
  }

  function names(rows: Named[] | undefined) {
    return (rows || []).map((row) => row.name).filter(Boolean).join("、") || "无";
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
      <div className="mini-graph" aria-label="岗位切片对照小图谱">
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
    <main id="main" className="page diagnose" data-phase={phase}>
      {phase !== "done" && (
        <form className="diagnose-form" onSubmit={onSubmit}>
          <h1>诊断</h1>
          <label>
            目标岗位
            <select value={jobId} onChange={(e) => setJobId(e.target.value)}>
              {jobs.map((job) => (
                <option key={job.id} value={job.id}>
                  {job.name}
                </option>
              ))}
            </select>
          </label>
          <label className="drop">
            简历（PDF / docx）
            <input
              className="sr-only"
              type="file"
              accept=".pdf,.docx"
              onChange={(e) => {
                abort.current?.abort();
                setFile(e.target.files?.[0] ?? null);
                setSessionId("");
                setReport(null);
                setPreview("");
                setPhase("idle");
              }}
            />
            <span>{file ? file.name : "选择文件"}</span>
          </label>
          <div className="diagnose-actions">
            <button type="submit" disabled={phase === "run"}>
              开始分析
            </button>
            {phase === "run" && (
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
              onClick={() => navigator.clipboard.writeText(link)}
            >
              复制对照链接
            </button>
            <button
              type="button"
              onClick={() => {
                setPhase("idle");
                setReport(null);
              }}
            >
              再分析一次
            </button>
          </header>
          <div className="diagnose-split">
            <aside>
              <h2>简历</h2>
              <pre>{report.preview_text || preview || "（无预览）"}</pre>
            </aside>
            <section>
              <h2>判断</h2>
              <p>{report.groups.judge.summary}</p>
              <p>档位 {report.groups.judge.band}</p>
              <ul className="cells">
                <li>必备覆盖 {report.groups.judge.cells.required}</li>
                <li>半档 {report.groups.judge.cells.half}</li>
                <li>经验 {report.groups.judge.cells.experience}</li>
                <li>学历 {report.groups.judge.cells.education}</li>
              </ul>
              <p>目标岗 {report.groups.judge.job_status}</p>
              <p>换档条件 {names(report.groups.judge.shift_set)}</p>

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
          </div>
        </div>
      )}
    </main>
  );
}
