type PipeRow = { source: string; n: number };
type HeatRow = { name: string; v: number };
type EventRow = { at: string; text: string; review?: string };

export function kindLabel(kind: string) {
  if (kind === "requires_add") return "岗位要求新增";
  if (kind === "job_status") return "岗位状态流转";
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

export function EventList({ rows }: { rows: EventRow[] }) {
  return (
    <div>
      {rows.map((row, i) => (
        <div className="ev" key={`${row.at}-${i}`}>
          <span className="mono">{(row.at || "").slice(5, 10)}</span>
          <span>{row.text}</span>
          {row.review ? <span className="pill">{row.review}</span> : <span />}
        </div>
      ))}
    </div>
  );
}
