import type { Metadata } from "next";
import Link from "next/link";
import { AdminLink, Nav } from "./nav";
import "./globals.css";

export const metadata: Metadata = { title: "智演" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-Hans">
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
          <div role="status" aria-live="polite" className="sr-only" />
          {children}
        </div>
      </body>
    </html>
  );
}
