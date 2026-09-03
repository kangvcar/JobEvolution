type PipeRow = { source: string; n: number };
type HeatRow = { name: string; v: number };
type EventRow = { at: string; text: string; review?: string; kind?: string; n?: number; skills?: string[] };

export function kindLabel(kind: string) {
  if (kind === "requires_add") return "岗位要求新增";
  if (kind === "job_status") return "岗位状态流转";
  if (kind === "skill_merge_proposal") return "技能合并提案";
  if (kind === "extract_failed") return "抽取失败";
  return kind;
}

export function Pipe({ rows }: { rows: PipeRow[] }) {
  const max = Math.max(1, ...rows.map((row) => row.n));
  return (
    <div className="pipe">
      {rows.map((row) => (
        <div className="pipe-row" key={row.source}>
          <span>{row.source}</span>
          <span className="heat-track">
            <i style={{ width: `${(100 * row.n) / max}%` }} />
          </span>
          <span>{row.n}</span>
        </div>
      ))}
    </div>
  );
}

export function Heat({ rows }: { rows: HeatRow[] }) {
  return (
    <table className="table">
      <tbody>
        {rows.map((row) => (
          <tr key={row.name}>
            <td>{row.name}</td>
            <td>
              <span className="heat-track">
                <i style={{ width: `${Math.min(100, row.v)}%` }} />
              </span>
            </td>
            <td className="num">{row.v}%</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function reviewTone(review: string) {
  if (review === "待审") return "mid";
  if (review === "驳回" || review === "已撤回") return "warn";
  return "ok";
}

export function EventList({ rows }: { rows: EventRow[] }) {
  if (!rows.length) return <p className="hint">暂无变化记录。</p>;
  return (
    <div className="ev-list">
      {rows.map((row, i) => (
        <div className="ev" key={`${row.at}-${i}`}>
          <span className="mono">{(row.at || "").slice(5, 10)}</span>
          <span className="ev-text" title={row.skills?.join("、")}>
            {row.text}
            {row.n ? (
              <>
                {" "}新增 {row.n} 条要求
                <span className="ev-names">：{(row.skills ?? []).join("、")}{row.n > (row.skills?.length ?? 0) ? " 等" : ""}</span>
              </>
            ) : null}
          </span>
          {row.review ? <span className={`pill ${reviewTone(row.review)}`}>{row.review}</span> : <span />}
        </div>
      ))}
    </div>
  );
}
