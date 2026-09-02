import type { Metadata } from "next";
import { JetBrains_Mono, Noto_Sans_SC, Space_Grotesk } from "next/font/google";
import Link from "next/link";
import { AdminLink, Nav } from "./nav";
import "./globals.css";

const space = Space_Grotesk({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-space",
});

const noto = Noto_Sans_SC({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-noto",
});

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-jetbrains",
});

export const metadata: Metadata = {
  title: "智演",
  description: "多源数据驱动的岗位能力图谱：岗位定位、差距分析与学习路径。",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-Hans" className={`${space.variable} ${noto.variable} ${jetbrains.variable}`}>
      <body>
        <a className="skip-link" href="#main">
          跳到主内容
        </a>
        <div className="shell">
          <header className="top">
            <Link className="brand" href="/">
              智演
            </Link>
            <Nav />
            <div className="top-end">
              <Link className="top-diagnose" href="/diagnose">
                开始诊断
              </Link>
              <AdminLink />
            </div>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
