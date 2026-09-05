"use client";

export type ReleaseAudit = {
  release: { id?: string | null; period?: string; published_at?: string | null };
  jobs: ReleaseJob[];
};

type ReleaseError = { code: string; message?: string; count?: number; limit?: number };

export type ReleaseJob = {
  id: string;
  name: string;
  status?: string;
  definition_count: number;
  diagnostic_release: {
    ok: boolean;
    counts?: { required_equivalent?: number; formal_equivalent?: number };
    errors?: ReleaseError[];
  };
};

type Props = {
  audit: ReleaseAudit | null;
  busy: boolean;
  onRefresh: () => void;
  onRun: () => void;
};

function errorText(error: ReleaseError) {
  if (error.code === "required_count_exceeded") return `必备 ${error.count}/${error.limit}`;
  if (error.code === "formal_count_exceeded") return `正式 ${error.count}/${error.limit}`;
  return error.message || error.code;
}

export default function ReleaseBoard({ audit, busy, onRefresh, onRun }: Props) {
  const passed = audit?.jobs.filter((job) => job.diagnostic_release.ok).length ?? 0;
  return (
    <section className="qb-main" aria-labelledby="release-board-title">
      <header className="qb-head">
        <h2 id="release-board-title">诊断发布校验 <span className="hint">{audit ? `${passed}/${audit.jobs.length} 个岗位可诊断` : "读取中…"}</span></h2>
        <div className="qb-ops">
          <button type="button" onClick={onRefresh} disabled={busy}>刷新</button>
          <button type="button" onClick={onRun} disabled={busy}>{busy ? "校准中…" : "运行公开校准"}</button>
        </div>
      </header>
      <p className="release-note">先看失败原因，再运行公开校准。只有通过校验的岗位进入诊断页，失败时当前公开版本不变。</p>
      {!audit ? <p className="release-empty">暂无发布校验结果。</p> : audit.jobs.length === 0 ? <p className="release-empty">暂无公开岗位。</p> : (
        <table className="qb-table release-table">
          <thead><tr><th>岗位</th><th>状态</th><th className="num">定义</th><th className="num">必备等价</th><th className="num">正式等价</th><th>结果</th></tr></thead>
          <tbody>
            {audit.jobs.map((job) => {
              const check = job.diagnostic_release;
              const counts = check.counts || {};
              return (
                <tr key={job.id}>
                  <td className="qb-name">{job.name}</td>
                  <td>{job.status || "–"}</td>
                  <td className="num">{job.definition_count}</td>
                  <td className="num">{counts.required_equivalent ?? "–"}</td>
                  <td className="num">{counts.formal_equivalent ?? "–"}</td>
                  <td className={check.ok ? "release-ok" : "release-fail"}>{check.ok ? "可诊断" : (check.errors || []).slice(0, 2).map(errorText).join("；") || "未通过校验"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
      {audit?.release?.id ? <p className="release-meta">当前公开版本：<span className="mono">{audit.release.id}</span></p> : null}
    </section>
  );
}
