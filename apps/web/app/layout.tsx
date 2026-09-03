import type { Metadata } from "next";
import { IBM_Plex_Mono } from "next/font/google";
import Link from "next/link";
import { Nav } from "./nav";
import "./globals.css";

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-plex-mono",
});

export const metadata: Metadata = {
  title: "智演 (JobEvolution) | 开源 AI 职业能力图谱与迁移诊断",
  description: "从多源招聘数据流中发现新岗位、追踪既有岗位能力演化；对照带来源的岗位证据与要求边，计算最小换档条件与技能成长路径。",
  openGraph: {
    title: "智演 (JobEvolution) | 开源 AI 职业能力图谱与迁移诊断",
    description: "多源异构数据驱动的岗位与能力图谱构建与动态演化分析研究。",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-Hans" className={plexMono.variable} suppressHydrationWarning>
      <body suppressHydrationWarning>
        <a className="skip-link" href="#main">
          跳到主内容
        </a>
        <div className="shell">
          <header className="top" data-component="top">
            <div>
              <Link className="brand-logo" href="/" aria-label="智演首页">
                {/* Pixel-blocky wordmark matching opencode SVG identity */}
                <svg
                  className="logo-svg"
                  width="189"
                  height="34"
                  viewBox="0 0 189 34"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                  aria-hidden="true"
                >
                  {/* Blocky 'jobevolution' logo */}
                  <rect x="0" y="8" width="5" height="18" fill="#1D1D1F" />
                  <rect x="5" y="22" width="10" height="4" fill="#1D1D1F" />
                  <rect x="0" y="2" width="5" height="4" fill="#656363" />

                  <rect x="20" y="8" width="14" height="4" fill="#1D1D1F" />
                  <rect x="20" y="22" width="14" height="4" fill="#1D1D1F" />
                  <rect x="18" y="10" width="4" height="14" fill="#1D1D1F" />
                  <rect x="32" y="10" width="4" height="14" fill="#1D1D1F" />

                  <rect x="40" y="2" width="4" height="24" fill="#1D1D1F" />
                  <rect x="44" y="10" width="10" height="4" fill="#1D1D1F" />
                  <rect x="44" y="22" width="10" height="4" fill="#1D1D1F" />
                  <rect x="52" y="12" width="4" height="12" fill="#1D1D1F" />

                  <text
                    x="62"
                    y="24"
                    fill="#1D1D1F"
                    fontFamily="var(--font-mono), monospace"
                    fontSize="17"
                    fontWeight="700"
                    letterSpacing="-0.5px"
                  >
                    jobevolution
                  </text>
                </svg>
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
