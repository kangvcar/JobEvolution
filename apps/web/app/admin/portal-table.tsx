"use client";

import { FormEvent, useState } from "react";

export type Portal = { key: string; type: string; name: string; host?: string; enabled: boolean; builtin?: boolean };
type FeedLine = { at: string; type: string; text: string };

const EVENT: Record<string, string> = {
  collect_started: "开始",
  jd_ingested: "入库",
  collect_portal_failed: "失败",
  collect_finished: "完成",
};

type Props = {
  portals: Portal[];
  collectBusy: boolean;
  feed: FeedLine[];
  onRunCollect: () => void;
  onToggle: (key: string, enabled: boolean) => void;
  onRemove: (key: string) => void;
  onAdd: (name: string, host: string) => Promise<boolean>;
};

export function PortalTable({ portals, collectBusy, feed, onRunCollect, onToggle, onRemove, onAdd }: Props) {
  const [name, setName] = useState("");
  const [host, setHost] = useState("");
  const [adding, setAdding] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAdding(true);
    if (await onAdd(name.trim(), host.trim())) {
      setName("");
      setHost("");
    }
    setAdding(false);
  }

  return (
    <div className="pt">
      <section className="pt-main" aria-label="招聘门户">
        <header className="qb-head">
          <h2>官网采集 <span className="hint">只打公司官网公开 JSON，与每日任务共用一把锁</span></h2>
          <button className="primary small" type="button" disabled={collectBusy} onClick={onRunCollect}>{collectBusy ? "采集中…" : "立即采集"}</button>
        </header>
        <p className="hint">启用的门户会进入采集任务。添加门户时会先探测域名，探测成功才保存；删除只适用于自定义门户，内置门户不能删除。</p>
        <form onSubmit={submit}>
          <table className="qb-table pt-table">
            <colgroup><col className="w-l" /><col className="w-m" /><col /><col className="w-s" /><col className="w-ops" /></colgroup>
            <thead>
              <tr><th>门户</th><th>类型</th><th>域名</th><th>启用</th><th className="qb-ops" aria-label="操作" /></tr>
            </thead>
            <tbody>
              {portals.map((portal) => (
                <tr key={portal.key} data-disabled={!portal.enabled || undefined}>
                  <td className="qb-name">{portal.name}</td>
                  <td className="mono">{portal.type}</td>
                  <td className="mono">{portal.host || "–"}</td>
                  <td><input type="checkbox" checked={portal.enabled} onChange={(e) => onToggle(portal.key, e.target.checked)} aria-label={`启用 ${portal.name}`} /></td>
                  <td className="qb-ops">{portal.builtin ? <span className="hint">内置</span> : <button type="button" title="删除" onClick={() => onRemove(portal.key)}>✕</button>}</td>
                </tr>
              ))}
              <tr className="pt-add">
                <td><input value={name} onChange={(e) => setName(e.target.value)} placeholder="门户名，如 智谱" required aria-label="门户名" /></td>
                <td className="mono">feishu</td>
                <td><input value={host} onChange={(e) => setHost(e.target.value)} placeholder="xxx.jobs.feishu.cn" required aria-label="飞书域名" /></td>
                <td colSpan={2}><button className="ghost small" type="submit" disabled={adding}>{adding ? "探测中…" : "探测并添加"}</button></td>
              </tr>
            </tbody>
          </table>
        </form>
      </section>
      <aside className="pt-log" aria-label="采集日志" aria-live="polite">
        <h3>日志 <span className="hint">最近 {feed.length} 条</span></h3>
        {feed.length ? (
          <ol>
            {feed.map((line, i) => (
              <li key={`${line.at}-${i}`} data-type={line.type}>
                <time>{line.at}</time> <b>{EVENT[line.type] ?? line.type}</b> <span>{line.text}</span>
              </li>
            ))}
          </ol>
        ) : <p className="hint">还没有采集事件。点「立即采集」后这里按事件时间滚动。</p>}
      </aside>
    </div>
  );
}
