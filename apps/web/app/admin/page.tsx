"use client";

import { FormEvent, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type QueueEvent = {
  id: string;
  kind: string;
  at: string;
  confidence: number;
  payload?: { job_name?: string; skill_name?: string; excerpt?: string; error?: string };
};

function kindLabel(kind: string) {
  if (kind === "requires_add") return "要求边新增";
  if (kind === "job_status") return "岗位状态流转";
  if (kind === "extract_failed") return "抽取失败";
  return kind;
}

export default function AdminPage() {
  const [password, setPassword] = useState("");
  const [queue, setQueue] = useState<QueueEvent[] | null>(null);
  const [error, setError] = useState("");

  async function enter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const response = await fetch(`${API}/admin/queue`, {
      headers: { "X-Admin-Password": password },
    });
    if (!response.ok) {
      setError("口令错误");
      return;
    }
    setQueue(await response.json());
  }

  if (queue === null) {
    return (
      <main id="main" className="page admin-page">
        <section className="admin-gate" aria-labelledby="admin-gate-title">
          <h1 id="admin-gate-title">管理</h1>
          <p className="hint">输入口令查看待审队列。</p>
          <form onSubmit={enter}>
            <label htmlFor="admin-password">口令</label>
            <input id="admin-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoFocus required />
            <div className="row">
              <button className="primary" type="submit">进入待审队列</button>
              <button className="ghost" type="button" onClick={() => window.history.back()}>取消</button>
            </div>
          </form>
          {error ? <p className="admin-error" role="alert">{error}</p> : null}
        </section>
      </main>
    );
  }

  return (
    <main id="main" className="page admin-page">
      <h1>待审队列</h1>
      <p className="hint">口令通过后显示尚未入谱的演化事件。</p>
      {queue.length === 0 ? <p className="empty">暂无待审演化事件</p> : null}
      <ul className="admin-queue" aria-label="待审演化事件">
        {queue.map((item) => {
          const payload = item.payload ?? {};
          const subject = payload.job_name || payload.skill_name || "未标注岗位或技能点";
          const summary = payload.excerpt || payload.error || "暂无摘要";
          return (
            <li key={item.id}>
              <div className="admin-event-head"><strong>{kindLabel(item.kind)}</strong><time dateTime={item.at}>{item.at.slice(0, 10)}</time></div>
              <p className="admin-event-subject">{subject}</p>
              <p className="hint">{summary}</p>
            </li>
          );
        })}
      </ul>
    </main>
  );
}
