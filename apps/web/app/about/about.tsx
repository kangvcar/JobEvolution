"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Logo } from "../logo";
import "./about.css";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/* ------------------------------------------------------------------ 内容 */

const CHAPTERS = [
  { id: "why", n: "01", label: "初衷" },
  { id: "principles", n: "02", label: "理念" },
  { id: "design", n: "03", label: "设计" },
  { id: "effect", n: "04", label: "效果" },
  { id: "value", n: "05", label: "价值" },
  { id: "bounds", n: "06", label: "边界" },
  { id: "terms", n: "07", label: "术语" },
] as const;

// 常见做法 vs 智演。左列是求职者今天拿到的东西，右列是本产品的替代物。
const LEDGER = [
  ["岗位描述是一段静态的话", "岗位是一组带有效期的要求边。本季度新增、升值、失效画在切片差分上。"],
  ["简历打一个 0–100 的分", "四档档位、缺口集与最小换档条件。分数只在内部算，不做成海报。"],
  ["AI 总结告诉你「你缺什么」", "每条判断都能展开简历原文与 JD 原文摘录。模型改写不能充当证据。"],
  ["新岗位靠人工录入", "从 JD 聚类里长出来，按独立源计票，候选、萌芽、成型三态流转。"],
  ["关键词命中率", "已有证据、只有提及、简历未找到证据。三态对账，不建议堆词。"],
] as const;

const PRINCIPLES = [
  {
    title: "每条要求边都能点到原文",
    rule: "没有摘录的边视为无证据链，层级记低，永不自动入谱。",
    body: "要求边写入时带着证据 ID、公司、观察时间与最短原文。工作台里点一个技能点，抽屉打开的就是那几句话。",
  },
  {
    title: "不合成分数",
    rule: "匹配分只在内部算：必备覆盖 + 0.3 × 加分覆盖，半档记 0.5。",
    body: "求职者看到档位文案、缺口集和换档条件。简历不打综合分，不给 ATS 命中率，两个岗位分不出高下时写「证据不足以区分」。",
  },
  {
    title: "人是最后一道闸",
    rule: "新岗位首发、核心必备新增、低置信抽取进同一待审队列。自动审核默认关。",
    body: "开启自动审核也只让高置信事实过确定性校验与独立审核模型。抽取模型不能审自己的输出。低置信事实永不自动入谱，管理员仍可批准。",
  },
  {
    title: "双时间，失效不删",
    rule: "观察时间与有效期分开记录。旧要求边写失效时间，不删除。",
    body: "撤回与变化是两回事。证据失真、授权到期只作撤回，不进切片差分与演化趋势。真实的市场变化才关闭旧事实的有效期。",
  },
  {
    title: "观测中不算缺口",
    rule: "簇内覆盖率不到 30% 的技能点只作发现信号，不写要求边。",
    body: "市场开始提、还没进要求的技能，求职者页面固定写「不算你的缺口」。系统只写「简历未找到证据」，不推断求职者真的不会。",
  },
  {
    title: "简历只留在会话里",
    rule: "只发送提取后的文本，匿名会话最长保留 60 分钟，不注册。",
    body: "数据库不保存简历原文与身份信息。对照链接跟会话走，过期就回到初始状态。上传前把处理范围写在上传区，不做强制勾选。",
  },
] as const;

// 管线十步。rule 是可以被检查的门槛，不是形容词。
const PIPELINE = [
  { key: "collect", label: "采集", rule: "官方招聘门户为主源，ATS 公开接口与高校就业站增量。", detail: "每条原始记录携带渠道、公司、岗位名、正文、发布日。指纹 sha256(渠道 + 站点 ID) 幂等，命中即跳过。缺正文的行直接丢弃。" },
  { key: "dedupe", label: "去重", rule: "正文 64 位 simhash，海明距离 ≤ 3 视为近重。", detail: "近重只保留观察时间最早的一条作证据，其余不计票。独立源按规范化公司名计，渠道不是独立源，同一公司多个门户仍算一个。" },
  { key: "extract", label: "抽取", rule: "只从职责与要求段出技能点，福利与公司介绍不算。", detail: "模型输出结构化 JSON，经 Pydantic 校验。每个技能点带明确必备 / 明确加分 / 未标、熟练级、置信与原文摘录。斜杠连接的复合表述拆开；沟通、团队协作等通用素质丢弃。" },
  { key: "align", label: "对齐", rule: "表面归一 → 获批同义词表 → 嵌入余弦 0.85。", detail: "大小写、全半角、空格差异直接归一。跨语言、缩写与全称只生成技能合并提案，人工比较定义与原文后才写入同义词表。LangChain 与 LangGraph、RAG 与向量数据库这类相关技术禁止合并。" },
  { key: "pool", label: "入池", rule: "簇内覆盖率 ≥ 30% 才写要求边，否则记观测中。", detail: "覆盖率是技能点在该岗位去重 JD 簇中出现的比例，随周期变，不是搜索指数。本期刚过 30% 记升值；不再出现写失效时间。" },
  { key: "vote", label: "计票", rule: "明确必备或加分票占已分类票 ≥ 60%，且来自 ≥ 2 独立源。", detail: "一份去重 JD 对一个技能点只投一票。未标票计入覆盖率与展示，不进性质判定的分母。达不到门槛只生成审核提案，三类票数与原文并列给管理员看。" },
  { key: "layer", label: "置信层", rule: "≥ 3 独立源且抽取置信 ≥ 0.8 记高；≥ 0.5 记中；其余记低。", detail: "无证据链一律低。高可由人工或自动审核批准；中进入预览层等待人审；低永不自动入谱。置信层是产品行为，置信度是边上的数。" },
  { key: "review", label: "待审", rule: "管线提交不可变原稿，人工批准、改写后批准或驳回。", detail: "人工改写不覆盖原稿，决定记录时间、理由与差异。管理页按岗位与待发布版本分组，一键全部批准仍过证据存在、证据未撤回、无重复要求、定义非空的确定性校验。" },
  { key: "release", label: "发布", rule: "诊断发布校验通过的岗位才可诊断。必备上限 12，正式要求上限 24。", detail: "校验拦截空岗位定义、无证据要求边、重复有效要求、引用已撤回证据与岗位要求异常。命中异常只暂停该岗位，其他岗位照常发布。发布版本不可变，公开指针可切回历史版本。" },
  { key: "diagnose", label: "诊断", rule: "简历技能对齐同一套词表与阈值，得出档位、缺口集与换档条件。", detail: "求职者先校对解析结果，再从推荐序里选两个可诊断岗位。方向结论由模型解释必备覆盖、简历证据级、可迁移工程能力与经验学历风险，不生成新的综合分。" },
] as const;

const LIFECYCLE = [
  { key: "candidate", label: "候选", tone: "mid", desc: "未入谱。发现页可看卷宗，不可诊断，不能当正式岗。" },
  { key: "emerging", label: "萌芽", tone: "hot", desc: "≥ 3 独立源、90 天窗，模型判为新岗位而非别名。入谱，标「新兴」。" },
  { key: "formed", label: "成型", tone: "ok", desc: "≥ 10 独立源或持续 ≥ 6 个月，且岗位定义曾获批准或自动通过。" },
] as const;

const NODES = [
  ["领域", "四个固定顶层分区：人工智能、大数据、智能系统、物联网。"],
  ["岗位", "劳动力市场中一类职位的规范化表示。初级与高级不分裂节点，级别写在要求边上。"],
  ["技能类目", "技能点的聚合层，只做导航收纳：语言、框架、平台、工程、领域知识。"],
  ["技能点", "可由原文证明的原子技术技能或领域知识。差距分析的对账单位。"],
  ["证据", "JD 快照或数据源记录。每条要求边和演化事件都能溯源到这里。"],
  ["演化事件", "图谱变更的原子记录，带发生时间、证据引用、置信与审核状态。"],
] as const;

const REPORT = [
  { title: "方向结论", desc: "首屏一句话：已有基础、当前更接近的岗位、主要阻碍。每项能打开简历证据与岗位依据。" },
  { title: "简历证据地图", desc: "左侧经历与项目，右侧正式要求，连线标明提及、使用或结果。未连接的要求只写「简历未找到证据」。" },
  { title: "换档模拟器", desc: "把缺口暂时加进简历，即时重算档位。结果固定标为「假设结果，尚未被简历证明」。" },
  { title: "邻近岗位迁移地图", desc: "两个对照岗与一个邻近岗，逐岗给当前档位、最小换档技能数、共享能力与独有要求。" },
  { title: "市场信号雷达", desc: "观测中技能的覆盖率、独立源数、周期变化与未入要求的原因。固定说明「不算你的缺口」。" },
  { title: "双轨行动清单", desc: "简历证明轨给五条改写建议，能力提升轨按换档条件列三个任务，每项带证据、资源与交付物。" },
] as const;

const AUDIENCES = [
  {
    who: "求职者",
    line: "已有一到五年后端或全栈经验，准备转向大模型应用或 Agent 岗位的人。",
    gets: ["卡在哪：缺口集与简历证据不足项，逐条回到原文。", "换邻近岗会不会更好：两个岗位并排比较，不强选胜者。", "这个月先补哪几样：按换档条件排序，不是按缺口出现顺序。"],
    href: "/diagnose",
    cta: "上传简历",
  },
  {
    who: "管理员与企业 HR",
    line: "看待审队列，批、改、驳。审核是闸，不是第二套产品。",
    gets: ["按岗位与待发布版本分组，先看变化摘要与异常原因。", "批量批准跳过逐条阅读，不跳过确定性校验。", "审计记录保存会话、时间、提案 ID 与放行理由。"],
    href: "/admin",
    cta: "管理后台",
  },
  {
    who: "研究与教学",
    line: "四领域岗位演化的事件流与要求判定票，口径公开，可复现。",
    gets: ["三项准确率均按技能点集合的 F1 计，达标线 0.90。", "金标修订先盲改、再裁决，禁止以预测为唯一依据改金标。", "岗位状态、要求边、演化事件全部由管线从证据长出，不手写。"],
    href: "/discover",
    cta: "市场演化",
  },
] as const;

const BOUNDS = [
  ["不给简历打综合分", "也不给 ATS 命中率。档位、缺口集、换档条件够用了。"],
  ["不推断求职者的真实能力", "只写「简历未找到证据」。证据不足与不会是两回事。"],
  ["不自动合并语义相近的技能", "LangChain 不是 LangGraph，GPT 不是 Gemini。合并要人批。"],
  ["不做演化时间轴回放", "也不做采集流墙。产品形态是切片差分与发现页流水。"],
  ["不保存简历原文与身份", "不注册，不建账户，不做长期进度、提醒或打卡。"],
  ["不自建课程库", "学习资源只是能打开的外部页面，标题要与技能点相符。"],
  ["不手写图谱事实", "岗位状态、要求边、演化事件、别名判定都由管线产出。"],
] as const;

const TERMS = [
  ["要求边", "岗位指向技能点的核心边，带必备或加分、熟练级、有效期、来源列表。"],
  ["独立源", "去重后的公司主体。渠道不是独立源，近重 JD 不计票。"],
  ["簇内覆盖率", "技能点在该岗位去重 JD 簇中出现的比例，≥ 30% 入池。"],
  ["观测中", "已抽出但未达覆盖率门槛的技能点，只作信号，不算缺口。"],
  ["切片差分", "当前岗位相对上一周期的要求边变化：新增、升值、已写失效时间。"],
  ["换档条件", "补齐后经确定性计算能升一档的最小技能点集合。"],
  ["缺口集", "目标岗位必备技能点中简历未覆盖的集合，对外只写「简历未找到证据」。"],
  ["简历证据级", "提及、使用、结果三档。不替代熟练级，不进匹配分。"],
  ["置信层", "高、中、低三级。层是产品行为，分数是边上的数。"],
  ["图谱发布版本", "一次管线运行通过校验后原子公开的不可变事实集合。"],
] as const;

/* ------------------------------------------------------------------ 数据 */

type Meta = { graph_release?: { period: string; published_at: string | null }; stale?: boolean };
type Card = { id: string; name: string; status: string; n_sources?: number };
type Board = { candidate: Card[]; emerging: Card[]; formed: Card[] };
type Feed = {
  pipeline: { source: string; n: number }[];
  events: unknown[];
  stories?: { name: string; status: string; title: string; hint: string; sources?: string; n_sources?: number }[];
};
type Pulse = { collect: { sources?: number; read?: number; ingested?: number; finished_at?: string | null } };

async function get<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${API}${path}`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}
const day = (v?: string | null) => (v ? v.slice(0, 10) : "");
const num = (v: number | undefined | null) => (typeof v === "number" ? v.toLocaleString("zh-CN") : "—");

/* ------------------------------------------------------------------ 组件 */

function useActiveChapter() {
  const [active, setActive] = useState<string>(CHAPTERS[0].id);
  useEffect(() => {
    const els = CHAPTERS.map((c) => document.getElementById(c.id)).filter(Boolean) as HTMLElement[];
    if (!els.length) return;
    const io = new IntersectionObserver(
      (entries) => {
        const hit = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
        if (hit) setActive(hit.target.id);
      },
      { rootMargin: "-96px 0px -60% 0px", threshold: 0 },
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);
  return active;
}

function Chapter({ id, title, sub, children }: { id: (typeof CHAPTERS)[number]["id"]; title: string; sub: string; children: React.ReactNode }) {
  const c = CHAPTERS.find((x) => x.id === id)!;
  return (
    <section id={id} className="ab-chapter" aria-labelledby={`${id}-h`}>
      <header className="ab-chapter-head">
        <span className="ab-chapter-n">{c.n}</span>
        <div>
          <h2 id={`${id}-h`}>{title}</h2>
          <p>{sub}</p>
        </div>
      </header>
      {children}
    </section>
  );
}

export function About() {
  const active = useActiveChapter();
  const [stage, setStage] = useState<(typeof PIPELINE)[number]["key"]>("pool");
  const [meta, setMeta] = useState<Meta | null>(null);
  const [board, setBoard] = useState<Board | null>(null);
  const [feed, setFeed] = useState<Feed | null>(null);
  const [pulse, setPulse] = useState<Pulse | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      const [m, b, f, p] = await Promise.all([get<Meta>("/meta"), get<Board>("/discover"), get<Feed>("/feed"), get<Pulse>("/pulse")]);
      if (!alive) return;
      setMeta(m);
      setBoard(b);
      setFeed(f);
      setPulse(p);
      setLoaded(true);
    })();
    return () => {
      alive = false;
    };
  }, []);

  const inGraph = board ? board.formed.length + board.emerging.length : undefined;
  const samples = feed?.pipeline?.reduce((acc, r) => acc + r.n, 0);
  const story = feed?.stories?.[0];
  const current = useMemo(() => PIPELINE.find((s) => s.key === stage)!, [stage]);
  const currentIndex = PIPELINE.findIndex((s) => s.key === stage);

  return (
    <main className="ab" id="main">
      {/* ---- 开篇 ---- */}
      <section className="ab-hero">
        <p className="ab-eyebrow">
          <span>关于智演</span>
          <span className="ab-dot" />
          <span>XH-202621 · 多源异构数据驱动岗位和能力图谱构建与动态演化分析</span>
        </p>
        <h1>
          把招聘市场的变化，
          <br />
          做成能对账的图谱。
        </h1>
        <p className="ab-lede">
          智演从四个领域的招聘数据流里发现新岗位、记录每个岗位要求边的增减。每一条要求都能点回原文证据，每一次变化都有发生时间与审核状态。对着一份简历，它只回答三件事：卡在哪、换邻近岗会不会更好、这个月先补哪几样。
        </p>
        <ul className="ab-hero-facts" aria-label="产品事实">
          <li>
            <b>四领域</b>
            <span>人工智能 · 大数据 · 智能系统 · 物联网</span>
          </li>
          <li>
            <b>六类节点</b>
            <span>领域 · 岗位 · 技能类目 · 技能点 · 证据 · 演化事件</span>
          </li>
          <li>
            <b>三个回答</b>
            <span>卡在哪 · 换不换 · 先补什么</span>
          </li>
          <li>
            <b>零账户</b>
            <span>免登录，简历只留在会话 60 分钟</span>
          </li>
        </ul>
      </section>

      <div className="ab-layout">
        {/* ---- 章节导航 ---- */}
        <nav className="ab-toc" aria-label="章节">
          <ol>
            {CHAPTERS.map((c) => (
              <li key={c.id}>
                <a href={`#${c.id}`} className={active === c.id ? "active" : undefined} aria-current={active === c.id ? "true" : undefined}>
                  <span className="mono">{c.n}</span>
                  <span>{c.label}</span>
                </a>
              </li>
            ))}
          </ol>
          <div className="ab-toc-cta">
            <Link href="/diagnose" className="ab-btn solid">
              开始诊断
            </Link>
          </div>
        </nav>

        <div className="ab-doc">
          {/* ---- 01 初衷 ---- */}
          <Chapter id="why" title="为什么做这件事" sub="求职者拿到的是静态岗位描述，市场却在按周变。">
            <div className="ab-prose">
              <p>
                劳动力市场的岗位名在变，JD 里的技能点也在变。「大模型应用工程师」这周刚加上评测集构建，「Agent 工程师」已经从大模型应用里拆出来成了独立岗位。求职者手里那份岗位描述对不上这些变化，简历工具给出的又往往是一个来历不明的分数。
              </p>
              <p>
                我们想做的是一张会呼吸的图谱：岗位从招聘数据里长出来，要求边带着有效期与证据，变化按周期画成切片差分。求职者不需要相信系统，只需要看到原文。
              </p>
            </div>
            <div className="ab-ledger" role="table" aria-label="常见做法与智演的对照">
              <div className="ab-ledger-head" role="row">
                <span role="columnheader">常见做法</span>
                <span role="columnheader">智演</span>
              </div>
              {LEDGER.map(([a, b]) => (
                <div className="ab-ledger-row" role="row" key={a}>
                  <span role="cell" className="ab-ledger-old">
                    {a}
                  </span>
                  <span role="cell">{b}</span>
                </div>
              ))}
            </div>
          </Chapter>

          {/* ---- 02 理念 ---- */}
          <Chapter id="principles" title="六条不变的规则" sub="每一条都写成可以被检查的门槛，而不是形容词。">
            <ol className="ab-principles">
              {PRINCIPLES.map((p, i) => (
                <li key={p.title}>
                  <span className="ab-principle-n mono">§{i + 1}</span>
                  <div>
                    <h3>{p.title}</h3>
                    <p className="ab-rule">{p.rule}</p>
                    <p>{p.body}</p>
                  </div>
                </li>
              ))}
            </ol>
          </Chapter>

          {/* ---- 03 设计 ---- */}
          <Chapter id="design" title="数据怎么流进图谱" sub="十步管线，每一步有一个能被检查的门槛。点一步看它的规则。">
            <div className="ab-rail" role="tablist" aria-label="管线步骤">
              {PIPELINE.map((s, i) => (
                <button
                  type="button"
                  role="tab"
                  key={s.key}
                  aria-selected={s.key === stage}
                  className={`ab-rail-step${s.key === stage ? " active" : ""}${i < currentIndex ? " before" : ""}`}
                  onClick={() => setStage(s.key)}
                >
                  <span className="ab-rail-n mono">{String(i + 1).padStart(2, "0")}</span>
                  <span className="ab-rail-label">{s.label}</span>
                </button>
              ))}
            </div>
            <div className="ab-rail-detail" role="tabpanel">
              <div className="ab-rail-detail-head">
                <span className="mono mute">
                  第 {currentIndex + 1} 步 / {PIPELINE.length}
                </span>
                <h3>{current.label}</h3>
              </div>
              <p className="ab-rule">{current.rule}</p>
              <p>{current.detail}</p>
            </div>

            <h3 className="ab-subhead">新岗位怎么入谱</h3>
            <p className="ab-subhead-note">状态由独立源从证据计票，用观察时间算 90 天窗与持续月数。不手写，不靠现场等满。</p>
            <ol className="ab-lifecycle">
              {LIFECYCLE.map((s, i) => (
                <li key={s.key}>
                  <div className="ab-lifecycle-node">
                    <span className={`pill ${s.tone}`}>{s.label}</span>
                    {i < LIFECYCLE.length - 1 ? <span className="ab-lifecycle-arrow" aria-hidden="true" /> : null}
                  </div>
                  <p>{s.desc}</p>
                </li>
              ))}
            </ol>

            <h3 className="ab-subhead">图谱里有什么</h3>
            <dl className="ab-nodes">
              {NODES.map(([k, v]) => (
                <div key={k}>
                  <dt>{k}</dt>
                  <dd>{v}</dd>
                </div>
              ))}
            </dl>
          </Chapter>

          {/* ---- 04 效果 ---- */}
          <Chapter id="effect" title="现在能看到什么" sub="下面的读数来自当前发布版本，随管线每天变。">
            <dl className="ab-readout" aria-label="当前发布版本读数">
              <div>
                <dt>当前发布版本</dt>
                <dd className="date">{meta?.graph_release?.published_at ? day(meta.graph_release.published_at) : loaded ? "尚未发布" : "…"}</dd>
              </div>
              <div>
                <dt>入谱岗位</dt>
                <dd>{loaded ? num(inGraph) : "…"}</dd>
              </div>
              <div>
                <dt>成型 / 萌芽 / 候选</dt>
                <dd>{loaded ? `${num(board?.formed.length)} / ${num(board?.emerging.length)} / ${num(board?.candidate.length)}` : "…"}</dd>
              </div>
              <div>
                <dt>去重 JD 样本</dt>
                <dd>{loaded ? num(samples) : "…"}</dd>
              </div>
              <div>
                <dt>招聘门户</dt>
                <dd>{loaded ? num(pulse?.collect.sources) : "…"}</dd>
              </div>
              <div>
                <dt>上次采集读取</dt>
                <dd>{loaded ? num(pulse?.collect.read) : "…"}</dd>
              </div>
            </dl>

            {story ? (
              <figure className="ab-story">
                <figcaption>
                  <span className="mono mute">真实事件 · 来自当前发布版本</span>
                  <Link href="/discover">看全部 →</Link>
                </figcaption>
                <div className="ab-story-body">
                  <b>{story.title}</b>
                  <p>{story.hint}</p>
                  {story.sources ? (
                    <p className="ab-story-sources">
                      <span className="mute">独立源</span> {story.sources}
                    </p>
                  ) : null}
                </div>
              </figure>
            ) : null}

            <h3 className="ab-subhead">一份诊断报告长什么样</h3>
            <p className="ab-subhead-note">报告首屏只放一句方向结论。其余五个记忆点都围绕「证据」组织，不围绕分数。</p>
            <ol className="ab-report">
              {REPORT.map((r, i) => (
                <li key={r.title}>
                  <span className="mono ab-report-n">{String(i + 1).padStart(2, "0")}</span>
                  <b>{r.title}</b>
                  <p>{r.desc}</p>
                </li>
              ))}
            </ol>

            <h3 className="ab-subhead">怎么验收</h3>
            <div className="ab-eval">
              <table>
                <thead>
                  <tr>
                    <th>项</th>
                    <th>比什么</th>
                    <th className="num">条数</th>
                    <th className="num">达标</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>JD 解析</td>
                    <td>管线抽出的技能点 vs 金标技能点</td>
                    <td className="num">≥ 100</td>
                    <td className="num">F1 ≥ 0.90</td>
                  </tr>
                  <tr>
                    <td>简历提取</td>
                    <td>管线抽出的技能点 vs 金标简历技能点</td>
                    <td className="num">100</td>
                    <td className="num">F1 ≥ 0.90</td>
                  </tr>
                  <tr>
                    <td>匹配</td>
                    <td>金标简历 × 金标要求边上的缺口集，不喂解析输出</td>
                    <td className="num">≥ 100 对</td>
                    <td className="num">F1 ≥ 0.90</td>
                  </tr>
                  <tr>
                    <td>学习路径</td>
                    <td>换档条件上的技能点是否都有能打开的资源</td>
                    <td className="num">约 20</td>
                    <td className="num">抽检，不定 F1</td>
                  </tr>
                </tbody>
              </table>
              <p className="ab-eval-note">
                三项都按技能点集合算 F1。评测前预测集与金标集都过同一套对齐词表并冻结阈值。CI 里的 mock 数字不是成绩，成绩来自未 mock 的本地跑。
              </p>
            </div>
          </Chapter>

          {/* ---- 05 价值 ---- */}
          <Chapter id="value" title="谁从中得到什么" sub="求职者是主路径。管理员走后台，研究者看口径。">
            <div className="ab-audiences">
              {AUDIENCES.map((a) => (
                <article key={a.who}>
                  <h3>{a.who}</h3>
                  <p className="ab-audience-line">{a.line}</p>
                  <ul>
                    {a.gets.map((g) => (
                      <li key={g}>{g}</li>
                    ))}
                  </ul>
                  <Link href={a.href} className="ab-link">
                    {a.cta} →
                  </Link>
                </article>
              ))}
            </div>
          </Chapter>

          {/* ---- 06 边界 ---- */}
          <Chapter id="bounds" title="我们不做什么" sub="边界写清楚，产品才不会变成另一个打分器。">
            <ul className="ab-bounds">
              {BOUNDS.map(([k, v]) => (
                <li key={k}>
                  <span className="ab-bounds-mark mono" aria-hidden="true">
                    ×
                  </span>
                  <div>
                    <b>{k}</b>
                    <span>{v}</span>
                  </div>
                </li>
              ))}
            </ul>
          </Chapter>

          {/* ---- 07 术语 ---- */}
          <Chapter id="terms" title="术语速查" sub="产品里只用这些词。完整定义见仓库根目录的 CONTEXT.md。">
            <dl className="ab-terms">
              {TERMS.map(([k, v]) => (
                <div key={k}>
                  <dt>{k}</dt>
                  <dd>{v}</dd>
                </div>
              ))}
            </dl>
          </Chapter>

          {/* ---- 收尾 ---- */}
          <section className="ab-end">
            <Logo className="ab-end-logo" />
            <p>招聘市场在变，你的换档条件也在变。对着一份简历算一次，约三分钟。</p>
            <div className="ab-end-actions">
              <Link href="/diagnose" className="ab-btn solid">
                上传简历，做一次诊断
              </Link>
              <Link href="/graph" className="ab-btn">
                打开图谱工作台
              </Link>
            </div>
          </section>
        </div>
      </div>

      <footer className="ab-foot">
        <span>© 2026 智演 JobEvolution</span>
        <nav>
          <Link href="/">首页</Link>
          <Link href="/graph">图谱工作台</Link>
          <Link href="/discover">市场演化</Link>
          <Link href="/diagnose">简历诊断</Link>
          <Link href="/admin">管理后台</Link>
        </nav>
      </footer>
    </main>
  );
}
