"use client";

import Link from "next/link";
import { useState } from "react";

const INSTALL_COMMANDS: Record<string, string> = {
  curl: "curl -fsSL https://jobevolution.ai/diagnose | bash",
  npm: "npx jobevolution-cli diagnose ./resume.pdf",
  bun: "bunx jobevolution-cli diagnose ./resume.pdf",
  brew: "brew install jobevolution/tap/jobevolution",
  paru: "paru -S jobevolution-bin",
};

const FAQ_ITEMS = [
  {
    q: "智演 (JobEvolution) 是如何帮助技术人进行职业选择的？",
    a: "传统求职依赖模糊的职位标签和主观猜测。智演从多源海量招聘数据流中自动化抽取原子技能点、要求边（必备/加分/熟练级）与要求组，对照您的简历文本证据，计算当前覆盖率与换档缺口，为您推荐最具性价比的职业跃迁目标与最小学习行动路径。",
  },
  {
    q: "什么是「最小换档条件」？",
    a: "换档条件指从当前岗位跨越到目标岗位时，必须补齐的关键核心技能项。智演不会盲目罗列所有未掌握的技能，而是根据图谱中多源招聘证据支持的必备权重、熟练级（了解/熟练/精通）及可替代技能组，挑选出耗时最短、通过率最高的 1~3 项核心工程闭环行动。",
  },
  {
    q: "岗位定义与技能要求是如何提取与校验的？",
    a: "智演覆盖新一代信息技术四大固定领域（人工智能、大数据、智能系统、物联网）。每条写入正式图谱的要求边，都必须由至少两个独立招聘源印证，且明确必备/加分票占比不低于 60%，并经过严格的诊断发布完整性校验，杜绝虚假与异常要求。",
  },
  {
    q: "简历数据会被上传或用于公共大模型训练吗？",
    a: "绝不会。智演恪守「隐私优先」架构，所有文本分段与技能证据匹配均在您本地会话中运行，产品数据库不保存简历原文或个人身份标识，会话最长仅保留一小时用于报告核对，随后自动销毁。",
  },
  {
    q: "什么是「萌芽岗位」与「成型岗位」？",
    a: "萌芽岗位指在市场招聘流中高频涌现、正在演变但尚未形成稳定技术标准的职位（如早期的具身智能算法工程师）；成型岗位则是具备获批岗位定义、多组核心必备要求及完整招聘证据链的标准岗位。",
  },
  {
    q: "智演支持私有化部署或接入企业内网吗？",
    a: "支持。智演的前端工作台、核心图谱解析引擎与数据清洗管道完全开源，提供标准 Docker 镜像与 Helm Chart，支持纯离线运行及对接私有知识库和本地开源 LLM（如 DeepSeek、Qwen、Ollama）。",
  },
];

export function Home() {
  const [activeTab, setActiveTab] = useState<string>("curl");
  const [copied, setCopied] = useState(false);
  const [openFaq, setOpenFaq] = useState<number | null>(null);
  const [email, setEmail] = useState("");
  const [subscribed, setSubscribed] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(INSTALL_COMMANDS[activeTab] || "");
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const toggleFaq = (index: number) => {
    setOpenFaq(openFaq === index ? null : index);
  };

  return (
    <main className="opencode-main">
      {/* 1. Hero Section matching Image #1 */}
      <section data-component="hero">
        {/* Banner with black badge and link */}
        <div data-component="desktop-app-banner">
          <span data-slot="badge">新</span>
          <div data-slot="content">
            <span data-slot="text">
              智演 2026 技术岗位图谱现已发布。
              <span data-slot="platforms"> 适用于 AI、大数据、智能系统和物联网</span>.
            </span>
            <Link href="/diagnose" data-slot="link">
              立即体验
            </Link>
          </div>
        </div>

        {/* Hero title and copy */}
        <div data-slot="hero-copy">
          <h1 className="hero-heading">开源  AI  岗位演化图谱</h1>
          <p className="hero-desc">
            从多源招聘数据流中发现新岗位、追踪既有岗位能力演化，
            <span data-slot="br"></span>
            对照带来源的岗位证据，计算最小换档条件与技能成长路径。
          </p>
        </div>

        {/* Installation Tabs Card */}
        <div data-slot="installation">
          <section
            className="tabs"
            data-component="tabs"
            data-active={activeTab}
            aria-label="安装选项"
          >
            <div role="tablist" data-slot="tablist">
              {Object.keys(INSTALL_COMMANDS).map((tab) => (
                <button
                  key={tab}
                  role="tab"
                  aria-selected={activeTab === tab}
                  type="button"
                  data-slot="tab"
                  className={activeTab === tab ? "active" : ""}
                  onClick={() => setActiveTab(tab)}
                >
                  {tab}
                </button>
              ))}
            </div>

            <div className="tab-body" data-slot="tabcontent">
              <code className="cmd-code">
                {activeTab === "curl" ? (
                  <>
                    curl -fsSL https://<strong className="code-highlight">jobevolution.ai/install</strong> | bash
                  </>
                ) : (
                  INSTALL_COMMANDS[activeTab]
                )}
              </code>

              <button
                type="button"
                className="copy-icon-btn"
                onClick={handleCopy}
                aria-label={copied ? "已复制" : "复制代码"}
                title={copied ? "已复制" : "复制代码"}
              >
                {copied ? (
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="#1D1D1F"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                ) : (
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="#8E8E93"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                  </svg>
                )}
              </button>
            </div>
          </section>
        </div>
      </section>

      {/* 2. Hero TUI / Video Mockup matching Image #1 split-pane interface */}
      <section data-component="video" className="hero-tui-section">
        <div className="tui-terminal-window">
          {/* Left Main Diff & Action List Pane */}
          <div className="tui-main-pane">
            <div className="tui-tasks-list">
              <p className="task-row done">
                <span className="check">[✓]</span> 提取简历教育与经历证据: 硕士 · 3年大模型工程落地经验
              </p>
              <p className="task-row done">
                <span className="check">[✓]</span> 对齐可诊断岗位规范要求: 大模型应用工程师 (12 条必备要求边)
              </p>
              <p className="task-row done">
                <span className="check">[✓]</span> 核对高置信度技能点: Python, PyTorch, LangChain, FastAPI (覆盖率 76%)
              </p>
              <p className="task-row pending">
                <span className="box-empty">[ ]</span> 补齐核心换档缺口: Triton 推理优化 / 模型量化加速 (权重 0.85 · 必备)
              </p>
              <p className="task-row pending">
                <span className="box-empty">[ ]</span> 补充工程闭环证据: 多路召回重排架构 (Hybrid Search + Reranker)
              </p>
              <p className="task-row pending">
                <span className="box-empty">[ ]</span> 运行诊断发布完整性校验并导出换档报告
              </p>
            </div>

            <div className="tui-diff-header">
              <span className="diff-arrow">←</span> 技能对账差异: Triton 推理优化
            </div>

            <div className="tui-diff-lines">
              <div className="diff-row">
                <span className="line-num">12</span>
                <span className="line-code line-del">- 仅了解常规 HuggingFace Pipeline 推理测试流程</span>
              </div>
              <div className="diff-row">
                <span className="line-num">13</span>
                <span className="line-code line-add">+ 掌握 vLLM / TensorRT-LLM 生产级吞吐优化与压测</span>
              </div>
              <div className="diff-row">
                <span className="line-num">14</span>
                <span className="line-code line-add">+ 掌握 PagedAttention 显存优化与量化加速 (AWQ/GPTQ)</span>
              </div>
              <div className="diff-row">
                <span className="line-num">15</span>
                <span className="line-code">  &lt;div className="benchmark-metrics"&gt;</span>
              </div>
            </div>
          </div>

          {/* Right Status Sidebar Pane matching Image #1 */}
          <aside className="tui-side-pane">
            <div className="side-block">
              <div className="side-title">目标换档: 大模型应用工程师</div>
              <div className="side-sub">档位推算: B档 → A档</div>
            </div>

            <div className="side-block">
              <div className="side-section-label">Context</div>
              <div className="side-stat">150,000+ 招聘样本</div>
              <div className="side-stat">76% 技能覆盖率</div>
              <div className="side-stat">双独立源交叉验证</div>
            </div>

            <div className="side-block">
              <div className="side-section-label">已覆盖技能 (6项)</div>
              <ul className="side-list">
                <li>• Python (精通)</li>
                <li>• PyTorch (熟练)</li>
                <li>• LangChain / RAG</li>
                <li>• FastAPI 异步服务</li>
              </ul>
            </div>

            <div className="side-block">
              <div className="side-section-label">▼ 换档核心缺口</div>
              <ul className="side-list gap-list">
                <li>• Triton 推理优化</li>
                <li>• 生产级并发压测</li>
                <li>• 多路召回重排</li>
              </ul>
            </div>
          </aside>
        </div>
      </section>

      {/* 3. What is JobEvolution Section */}
      <section data-component="what">
        <h3>什么是 智演？</h3>
        <p>
          智演 (JobEvolution) 是一套多源异构数据驱动的职业能力图谱与换档决策系统。
          深入追踪新一代信息技术四大领域的真实招聘需求变迁，帮助求职者与技术团队用带来源的事实证据替代主观猜测。
        </p>
        <ul className="features-list">
          <li>
            <span>[*]</span>
            <div>
              <strong>四大技术领域图谱</strong> 系统化收纳人工智能、大数据、智能系统、物联网四大领域的规范岗位节点
            </div>
          </li>
          <li>
            <span>[*]</span>
            <div>
              <strong>真实招聘证据链</strong> 每条要求边（必备/加分/熟练级）均由至少两个独立招聘源支持，可追溯真实原始快照
            </div>
          </li>
          <li>
            <span>[*]</span>
            <div>
              <strong>最小换档路径推算</strong> 计算当前简历技能与目标岗位要求的差异，按要求组与优先级输出换档行动路径
            </div>
          </li>
          <li>
            <span>[*]</span>
            <div>
              <strong>本地沙箱与隐私优先</strong> 简历解析与技能提取完全在用户本地会话中运行，绝不上报、不参与公共训练
            </div>
          </li>
          <li>
            <span>[*]</span>
            <div>
              <strong>动态生命周期与卷宗</strong> 双时间模型分离记录观察时间与有效时间，透明呈现岗位的萌芽、成型、升值与衰退
            </div>
          </li>
          <li>
            <span>[*]</span>
            <div>
              <strong>终端 CLI 与图谱工作台</strong> 提供毫秒级 CLI 诊断工具与交互式 G6 岗位能力拓扑大图
            </div>
          </li>
        </ul>
        <Link href="/graph" className="btn-what-cta">
          打开岗位工作台 →
        </Link>
      </section>

      {/* 4. Growth & Stats Section */}
      <section data-component="growth">
        <h3>开源职业能力与市场指标</h3>
        <p>
          基于多源异构技术招聘数据流构建，拥有超过 150,000 条带来源的岗位证据样本，850 个规范技能节点，
          并已稳定建立 17 个信息技术核心演化目标岗位。
        </p>
        <div className="growth-figures">
          <figure className="growth-figure">
            <div className="ascii-chart">
              <span className="chart-line">|    .---.      .---.</span>
              <span className="chart-line">|   /     \    /     \</span>
              <span className="chart-line">|--'       '--'       '--</span>
            </div>
            <figcaption>图 1. 150K+ 真实招聘证据样本</figcaption>
          </figure>
          <figure className="growth-figure">
            <div className="ascii-chart">
              <span className="chart-line">|        .---.</span>
              <span className="chart-line">|  .----'     '----.</span>
              <span className="chart-line">|-'                 '---</span>
            </div>
            <figcaption>图 2. 850+ 规范技术技能点</figcaption>
          </figure>
          <figure className="growth-figure">
            <div className="ascii-chart">
              <span className="chart-line">|      /\        /\</span>
              <span className="chart-line">|     /  \  /\  /  \</span>
              <span className="chart-line">|____/    \/  \/    \___</span>
            </div>
            <figcaption>图 3. 100% 双独立源链条校验</figcaption>
          </figure>
        </div>
      </section>

      {/* 5. Privacy Section */}
      <section data-component="privacy">
        <div data-slot="privacy-title">
          <h3>隐私优先的设计</h3>
          <p>
            智演 采用严格的本地沙箱设计。用户上传的简历在本地内存态完成文本分段、实体抽取与对账比对，
            不上传云端明文，产品数据库不保存简历原文，会话结束后自动销毁。{" "}
            <Link href="/diagnose" className="inline-link">
              了解更多关于 隐私
            </Link>
            。
          </p>
        </div>
      </section>

      {/* 6. FAQ Section */}
      <section data-component="faq">
        <h3>常见问题</h3>
        <ul className="faq-list">
          {FAQ_ITEMS.map((item, index) => {
            const isOpen = openFaq === index;
            return (
              <li key={item.q} className={isOpen ? "is-open" : ""}>
                <button
                  type="button"
                  data-slot="faq-question"
                  onClick={() => toggleFaq(index)}
                  aria-expanded={isOpen}
                >
                  <span className="toggle-icon">{isOpen ? "−" : "+"}</span>
                  <span className="question-text">{item.q}</span>
                </button>
                {isOpen && <div className="faq-answer">{item.a}</div>}
              </li>
            );
          })}
        </ul>
      </section>

      {/* 7. Zen-like CTA Section */}
      <section data-component="zen-cta">
        <div data-slot="zen-cta-copy">
          <strong>探索新一代信息技术四大领域图谱</strong>
          <p>
            直接查阅人工智能、大数据、智能系统与物联网领域的技能要求、新增增量与失效历史，
            告别黑盒与信息差，基于招聘事实做职业规划。
          </p>
          <Link href="/graph" className="btn-solid">
            进入岗位工作台
          </Link>
        </div>
      </section>

      {/* 8. Email Subscription Section */}
      <section data-component="email">
        <div data-slot="dock">
          <h3>第一时间获知岗位图谱更新</h3>
          <p>订阅每周技术岗位演化周报、新兴技术栈变动与最小换档实战卷宗。</p>
          {subscribed ? (
            <p className="success-msg">[+] 感谢订阅！最新岗位图谱变动将准时投递至您的邮箱。</p>
          ) : (
            <form
              className="email-form"
              onSubmit={(e) => {
                e.preventDefault();
                if (email.trim()) setSubscribed(true);
              }}
            >
              <input
                type="email"
                required
                placeholder="name@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
              <button type="submit" className="btn-solid">
                订阅周报
              </button>
            </form>
          )}
        </div>
      </section>

      {/* 9. Footer Section */}
      <footer data-component="footer">
        <div className="footer-links-grid">
          <div className="footer-col">
            <Link href="https://github.com" target="_blank" rel="noreferrer">
              GitHub [ 150K ]
            </Link>
          </div>
          <div className="footer-col">
            <Link href="/graph">岗位工作台</Link>
          </div>
          <div className="footer-col">
            <Link href="/discover">市场变化</Link>
          </div>
          <div className="footer-col">
            <Link href="/diagnose">简历诊断</Link>
          </div>
          <div className="footer-col">
            <Link href="/admin">管理后台</Link>
          </div>
        </div>
        <div className="footer-bottom">
          <span className="copyright">© 2026 智演 (JobEvolution) · 国家工程研发支持项目 (XH-202621)</span>
          <div className="footer-meta">
            <Link href="/discover">图谱本体</Link>
            <span>·</span>
            <Link href="/diagnose">隐私规范</Link>
            <span>·</span>
            <Link href="/graph">可诊断岗位</Link>
            <span>·</span>
            <span className="lang-picker">简体中文 ▼</span>
          </div>
        </div>
      </footer>
    </main>
  );
}
