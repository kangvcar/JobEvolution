import type { Metadata } from "next";
import Link from "next/link";
import { Nav } from "./nav";
import { Logo } from "./logo";
import "./globals.css";

export const metadata: Metadata = {
  title: "智演 (JobEvolution) | 开源 AI 职业能力图谱",
  description: "从多源招聘数据流中发现新岗位、追踪岗位能力演化；对照带来源的证据与要求边，计算最小换档条件与技能成长路径。",
  openGraph: {
    title: "智演 (JobEvolution) | 开源 AI 职业能力图谱",
    description: "多源异构数据驱动的岗位与能力图谱构建与动态演化分析。",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-Hans" suppressHydrationWarning>
      <body suppressHydrationWarning>
        <a className="skip-link" href="#main">
          跳到主内容
        </a>
        <div className="shell">
          <header className="top" data-component="top">
            <div>
              <Link className="brand-logo" href="/" aria-label="智演首页">
                <Logo className="logo-svg" />
              </Link>
            </div>

            <Nav />
          </header>

          {children}
        </div>
      </body>
    </html>
  );
}
