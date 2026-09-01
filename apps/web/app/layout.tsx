import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import Link from "next/link";
import { AdminLink, Nav } from "./nav";
import "./globals.css";

const plexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-sans",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-plex-mono",
});

export const metadata: Metadata = {
  title: "智演",
  description: "多源数据驱动的岗位能力图谱：岗位定位、差距分析与学习路径。",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-Hans" className={`${plexSans.variable} ${plexMono.variable}`}>
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
              <AdminLink />
            </div>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
