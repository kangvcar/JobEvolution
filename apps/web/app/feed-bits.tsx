type PipeRow = { source: string; n: number };
type HeatRow = { name: string; v: number; hot?: boolean; dead?: boolean };
type EventRow = { at: string; text: string; review?: string };

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
              <span className={`heat-track${row.dead ? " dead" : row.hot ? " hot" : ""}`}>
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
