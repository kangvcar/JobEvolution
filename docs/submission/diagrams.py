# -*- coding: utf-8 -*-
"""Generate architecture / pipeline diagrams as PNG for the design doc."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib import font_manager

for cand in ["PingFang SC", "Hiragino Sans GB", "Heiti SC", "STHeiti", "Noto Sans CJK SC"]:
    if any(f.name == cand for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = cand
        break
plt.rcParams["axes.unicode_minus"] = False

INK = "#1d1d1f"
PAPER = "#ffffff"
RULE = "#8c8c8c"
ACCENT = "#c8791b"
LIGHT = "#f4f1ea"
GREY = "#e9e9e9"
OUT = "/tmp/je_doc"


def box(ax, x, y, w, h, text, fc=PAPER, ec=INK, fs=10, lw=1.2, weight="normal", color=INK, radius=0.02):
    p = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={radius}", fc=fc, ec=ec, lw=lw)
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color=color, weight=weight, linespacing=1.4)


def arrow(ax, x1, y1, x2, y2, color=INK, lw=1.2, style="-|>", ls="-"):
    a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=12, color=color, lw=lw, linestyle=ls)
    ax.add_patch(a)


def canvas(w, h):
    fig, ax = plt.subplots(figsize=(w, h), dpi=200)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(PAPER)
    return fig, ax


def save(fig, name):
    fig.savefig(f"{OUT}/{name}.png", bbox_inches="tight", facecolor=PAPER, pad_inches=0.08)
    plt.close(fig)


# ---------------------------------------------------------------- 1 architecture
def arch():
    fig, ax = canvas(11, 7.8)
    layers = [
        ("应用层  Next.js 15 / React 19", ["首页总览", "图谱工作台", "市场演化", "五步诊断", "管理后台"], PAPER),
        ("服务层  FastAPI", ["/jobs  /graph", "/discover  /feed", "/sessions  /diagnose", "/diagnose/simulate", "/admin/*  SSE"], PAPER),
        ("存储层", ["Neo4j 5：岗位 / 技能点 / 要求边 / 证据 / 演化事件 / 发布版本", "Redis 7：简历会话(TTL 1h) / 事件流 / 指纹集合 / 资源缓存"], LIGHT),
        ("图谱构建层  pipeline", ["切段", "LLM JSON 抽取", "三层归一对齐", "入池 / 判定票", "置信层 / 审核闸", "发布校验"], PAPER),
        ("采集层  collectors", ["门户适配器\n飞书/腾讯/字节/北森", "fingerprint 幂等", "simhash 近重去重", "JD 快照落盘", "Redis Stream 事件"], PAPER),
        ("数据源层", ["53 个企业官方招聘门户 · 3,580 条去重 JD 快照 · 双时间戳(观察时间 / 有效期)"], LIGHT),
    ]
    n = len(layers)
    top, bottom = 0.96, 0.04
    lh = (top - bottom) / n
    for i, (title, cells, fc) in enumerate(layers):
        y = top - (i + 1) * lh + 0.012
        h = lh - 0.024
        box(ax, 0.02, y, 0.96, h, "", fc=fc, ec=RULE, lw=1.0, radius=0.0)
        ax.text(0.035, y + h - 0.008, title, fontsize=10, weight="bold", color=INK, va="top")
        cw = 0.94 / len(cells)
        for j, c in enumerate(cells):
            cx = 0.03 + j * cw + 0.006
            box(ax, cx, y + 0.010, cw - 0.012, h - 0.062, c, fc=PAPER if fc == LIGHT else GREY, ec=INK, fs=8.6, lw=0.9, radius=0.0)
        if i < n - 1:
            pass
    # side note: external services
    ax.text(0.5, 0.005, "外部服务：LLM 供应商 DeepSeek / B.AI / Tuzi（OpenAI 兼容，唯一出口 app/llm/client.py） · 嵌入 BAAI/bge-m3（硅基流动）",
            ha="center", va="bottom", fontsize=8.5, color=RULE)
    # arrows between layers (data flows upward from source to app)
    for i in range(n - 1):
        y_top = top - (i + 1) * lh + 0.012
        arrow(ax, 0.5, y_top - 0.024 + 0.012, 0.5, y_top, color=ACCENT, lw=1.4)
    save(fig, "fig_arch")


# ---------------------------------------------------------------- 2 pipeline gates
def gates():
    fig, ax = canvas(15, 4.8)
    steps = [
        ("JD 快照", "去重正文\n公司规范名\n观察时间"),
        ("切段", "职责 / 要求\n福利 / 介绍\n只允许前两段"),
        ("LLM 抽取", "JSON + Pydantic\n每项必带原文摘录\n拆并列 / 弃通用素质"),
        ("原文回指", "摘录必须在\n原文中命中\n否则丢弃"),
        ("三层归一", "表面归一 →\n获批同义词 →\nbge 余弦 ≥0.70"),
        ("入池门", "职责/要求段 ∧\n簇内覆盖率 ≥30%\n否则观测中"),
        ("判定票门", "明确票 ≥60% ∧\n≥2 独立源\n否则只提案"),
        ("置信层", "高 / 中 / 低\n低层永不自动入谱"),
        ("审核闸", "人工批/改/驳\n独立模型复核\n(默认关)"),
        ("发布校验", "定义非空·有证据\n无重复·数量上限\n异常暂停诊断"),
        ("发布版本", "不可变事实集\n可回滚\n旧边写 valid_to"),
    ]
    n = len(steps)
    w = 0.082
    gap = (1 - n * w) / (n + 1)
    for i, (t, d) in enumerate(steps):
        x = gap + i * (w + gap)
        gate = t.endswith("门") or t in ("审核闸", "发布校验", "原文回指")
        box(ax, x, 0.42, w, 0.3, t, fc=(LIGHT if gate else PAPER), ec=(ACCENT if gate else INK), fs=8.6, weight="bold", lw=1.4 if gate else 1.1)
        ax.text(x + w / 2, 0.36, d, ha="center", va="top", fontsize=7.4, color=INK, linespacing=1.35)
        if i < n - 1:
            arrow(ax, x + w, 0.57, x + w + gap, 0.57, color=INK)
        if gate:
            ax.text(x + w / 2, 0.80, "拦截", ha="center", va="bottom", fontsize=8, color=ACCENT)
            arrow(ax, x + w / 2, 0.72, x + w / 2, 0.79, color=ACCENT, lw=1.0, ls="--")
    ax.text(0.5, 0.95, "幻觉防控：每条要求边都必须能回到原文证据，任何一道门未过只降级为“观测中 / 审核提案 / 暂停诊断”，不进入正式图谱",
            ha="center", va="top", fontsize=9.5, color=INK)
    save(fig, "fig_gates")


# ---------------------------------------------------------------- 3 job state machine
def states():
    fig, ax = canvas(9.5, 4.6)
    box(ax, 0.04, 0.40, 0.2, 0.26, "候选 candidate\n未入谱，发现页可见\n不可诊断", fc=PAPER, fs=9.5)
    box(ax, 0.40, 0.40, 0.2, 0.26, "萌芽 emerging\n入谱，标“新兴”", fc=LIGHT, ec=ACCENT, fs=9.5, lw=1.5)
    box(ax, 0.76, 0.40, 0.2, 0.26, "成型 formed\n入谱，正式岗位", fc=INK, ec=INK, fs=9.5, color=PAPER)
    arrow(ax, 0.24, 0.53, 0.40, 0.53, color=INK, lw=1.4)
    ax.text(0.32, 0.68, "≥3 独立源 ∧ 90 天窗\n∧ LLM 簇判别=新岗位", ha="center", va="bottom", fontsize=8.5)
    arrow(ax, 0.60, 0.53, 0.76, 0.53, color=INK, lw=1.4)
    ax.text(0.68, 0.68, "(≥10 独立源 ∨ 持续 ≥6 月)\n∧ 岗位定义曾获批", ha="center", va="bottom", fontsize=8.5)
    # side branches
    box(ax, 0.04, 0.06, 0.2, 0.18, "别名 ALIAS_OF\n并入既有岗位", fc=GREY, ec=RULE, fs=9)
    box(ax, 0.40, 0.06, 0.2, 0.18, "噪声 丢弃", fc=GREY, ec=RULE, fs=9)
    arrow(ax, 0.10, 0.40, 0.10, 0.24, color=RULE, ls="--")
    arrow(ax, 0.46, 0.40, 0.46, 0.24, color=RULE, ls="--")
    ax.text(0.5, 0.985, "岗位状态由证据计票自动流转：独立源 = 规范化公司名去重，simhash 近重 JD 不计票，渠道不计票",
            ha="center", va="top", fontsize=9.5)
    ax.text(0.5, 0.905, "输入：未对齐到 17 个覆盖靶子的 JD → 「标题 + 技能点」bge 嵌入 → 层次聚类(最小簇 3) → LLM 三分类(新岗位 / 别名 / 噪声)",
            ha="center", va="top", fontsize=8.5, color=RULE)
    save(fig, "fig_states")


# ---------------------------------------------------------------- 4 diagnosis flow
def diagnose():
    fig, ax = canvas(11, 4.4)
    steps = [
        ("① 上传简历", "PDF(pdfplumber)\ndocx(python-docx)\n只取文本层，原文件即删"),
        ("② 解析与校对", "LLM 拆两子任务并行\n技能点过 align_skill\n用户按原文修正"),
        ("③ 岗位推荐序", "逐层排序：档位 →\n必备覆盖 → 专属技能\n→ 可迁移能力"),
        ("④ 选两岗对照", "只允许通过发布校验\n的可诊断岗位"),
        ("⑤ 确定性匹配", "匹配分/档位/缺口集\n半档 0.5·加分 0.3\n换档条件 shift_set"),
        ("⑥ 模型解释", "方向结论(不合成分数)\n每条判断带证据 ID\n缺失只写“未找到”"),
        ("⑦ 报告", "结论 / 行动 / 依据\n换档模拟·证据地图\n迁移地图·市场雷达"),
    ]
    n = len(steps)
    w = 0.125
    gap = (1 - n * w) / (n + 1)
    for i, (t, d) in enumerate(steps):
        x = gap + i * (w + gap)
        fc = LIGHT if i in (4,) else PAPER
        box(ax, x, 0.50, w, 0.24, t, fc=fc, ec=INK, fs=9.5, weight="bold")
        ax.text(x + w / 2, 0.45, d, ha="center", va="top", fontsize=8, linespacing=1.35)
        if i < n - 1:
            arrow(ax, x + w, 0.62, x + w + gap, 0.62)
    ax.text(0.5, 0.95, "匹配分 = 100 × (必备覆盖 + 0.3 × 加分覆盖) / (必备满分 + 0.3 × 加分满分)；档位：≥0.85 高度匹配 · ≥0.60 基本匹配 · ≥0.35 有明显差距 · 其余不匹配",
            ha="center", va="top", fontsize=9)
    ax.text(0.5, 0.86, "会话：Redis TTL 1 小时，免登录；简历不落库；对照链接 = session_id + job_id",
            ha="center", va="top", fontsize=8.5, color=RULE)
    save(fig, "fig_diagnose")


# ---------------------------------------------------------------- 5 ontology
def ontology():
    fig, ax = canvas(9.5, 5.2)
    nodes = {
        "Domain": (0.08, 0.72, "Domain 领域\nai / data / system / iot"),
        "Job": (0.42, 0.72, "Job 岗位\nstatus · 大典编码\nESCO / O*NET 映射"),
        "Skill": (0.42, 0.22, "Skill 技能点\n同义词 · 类目 · 嵌入"),
        "Cat": (0.08, 0.22, "SkillCategory 技能类目\n语言/框架/平台\n工程/领域知识"),
        "Evi": (0.76, 0.72, "Evidence 证据\nJD 快照路径 · 公司\nobserved_at · simhash"),
        "Evt": (0.76, 0.22, "EvolutionEvent 演化事件\nkind · at · confidence\nreview · payload"),
    }
    bw, bh = 0.24, 0.17
    for k, (x, y, t) in nodes.items():
        fc = INK if k == "Job" else (LIGHT if k in ("Skill",) else PAPER)
        box(ax, x, y, bw, bh, t, fc=fc, ec=INK, fs=8.8, color=PAPER if k == "Job" else INK)
    # edges
    arrow(ax, 0.42, 0.805, 0.32, 0.805)
    ax.text(0.37, 0.83, "IN_DOMAIN", ha="center", fontsize=8, color=RULE)
    arrow(ax, 0.53, 0.72, 0.53, 0.39, color=ACCENT, lw=1.8)
    ax.text(0.555, 0.56, "REQUIRES\nkind 必备/加分 · proficiency 熟练级\nvalid_from / valid_to · confidence · layer\nsources[证据ID] · levels · group_id/min_required",
            ha="left", va="center", fontsize=7.8, color=INK)
    arrow(ax, 0.42, 0.305, 0.32, 0.305)
    ax.text(0.37, 0.33, "IN_CATEGORY", ha="center", fontsize=8, color=RULE)
    arrow(ax, 0.76, 0.305, 0.66, 0.305, color=RULE, ls="--")
    ax.text(0.71, 0.33, "payload 引用", ha="center", fontsize=8, color=RULE)
    arrow(ax, 0.88, 0.39, 0.88, 0.72, color=RULE, ls="--")
    ax.text(0.895, 0.56, "AFFECTS(Job)\n引用证据 ID", ha="left", va="center", fontsize=8, color=RULE)
    arrow(ax, 0.66, 0.805, 0.76, 0.805, color=RULE, ls="--")
    ax.text(0.71, 0.83, "sources 引用", ha="center", fontsize=8, color=RULE)
    # self loop alias
    ax.annotate("ALIAS_OF（别名并入）", xy=(0.50, 0.895), xytext=(0.62, 0.96), fontsize=8, color=RULE,
                arrowprops=dict(arrowstyle="-|>", color=RULE, connectionstyle="arc3,rad=-0.6", lw=1.0))
    ax.text(0.5, 0.05, "双时间：观察时间(何时在数据源看到) 与 有效期(valid_from / valid_to) 分开记录；旧要求边写失效时间而不删除，切片差分按 valid_from/valid_to 重演",
            ha="center", va="bottom", fontsize=8.5, color=INK)
    save(fig, "fig_ontology")


# ---------------------------------------------------------------- 6 deployment
def deploy():
    fig, ax = canvas(9.5, 3.6)
    box(ax, 0.03, 0.30, 0.94, 0.55, "", fc=LIGHT, ec=RULE, radius=0.0)
    ax.text(0.05, 0.80, "单服务器 Docker Compose（HTTPS 反向代理统一入口）", fontsize=10, weight="bold", va="top")
    svcs = [("web\nNext.js :3000", PAPER), ("api\nFastAPI :8000", PAPER), ("pipeline\n每日采集+抽取", PAPER), ("neo4j\n5-community :7687", GREY), ("redis\n7-alpine AOF :6379", GREY)]
    n = len(svcs)
    w = 0.16
    gap = (0.9 - n * w) / (n - 1)
    for i, (t, fc) in enumerate(svcs):
        x = 0.05 + i * (w + gap)
        box(ax, x, 0.38, w, 0.3, t, fc=fc, ec=INK, fs=9)
    arrow(ax, 0.21, 0.53, 0.05 + (w + gap), 0.53)
    arrow(ax, 0.05 + (w + gap) + w, 0.53, 0.05 + 2 * (w + gap), 0.53)
    ax.text(0.5, 0.20, "数据卷：neo4j_official_data · redis_data · ./data(JD 快照 / 评测金标 / 图谱快照)   健康检查：/meta、redis-cli ping、Neo4j 7474",
            ha="center", va="top", fontsize=8.5, color=INK)
    ax.text(0.5, 0.08, "测试隔离：neo4j-test(:17687，独立卷) 供 pytest 与 CI 使用，永不写产品图",
            ha="center", va="top", fontsize=8.5, color=RULE)
    save(fig, "fig_deploy")


if __name__ == "__main__":
    arch(); gates(); states(); diagnose(); ontology(); deploy()
    print("ok")
