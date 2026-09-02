"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "首页" },
  { href: "/graph", label: "岗位" },
  { href: "/discover", label: "市场变化" },
] as const;

export function Nav() {
  const path = usePathname();
  return (
    <nav className="nav" aria-label="主导航">
      {LINKS.map(({ href, label }) => (
        <Link key={href} href={href} aria-current={path === href ? "page" : undefined}>
          {label}
        </Link>
      ))}
    </nav>
  );
}

export function AdminLink() {
  const path = usePathname();
  return (
    <Link className="admin" href="/admin" aria-current={path === "/admin" ? "page" : undefined}>
      管理
    </Link>
  );
}
