"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

const NAV_LINKS = [
  { href: "https://github.com", label: "GitHub", external: true },
  { href: "/graph", label: "图谱工作台", external: false },
  { href: "/discover", label: "市场演化", external: false },
  { href: "/admin", label: "管理后台", external: false },
] as const;

export function Nav() {
  const path = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <>
      {/* OpenCode Desktop Nav: links and CTA button inside the same <ul> */}
      <nav data-component="nav-desktop">
        <ul>
          {NAV_LINKS.map(({ href, label, external }) => {
            if (external) {
              return (
                <li key={label}>
                  <a
                    href={href}
                    target="_blank"
                    rel="noreferrer"
                    style={{ whiteSpace: "nowrap" }}
                  >
                    {label}
                  </a>
                </li>
              );
            }
            return (
              <li key={label}>
                <Link
                  href={href}
                  className={path === href ? "active" : ""}
                  aria-current={path === href ? "page" : undefined}
                >
                  {label}
                </Link>
              </li>
            );
          })}

          {/* OpenCode CTA Download/Diagnose button as the last item inside desktop nav */}
          <li>
            <Link data-slot="cta-button" href="/diagnose">
              <svg
                width="18"
                height="18"
                viewBox="0 0 18 18"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
                style={{ flexShrink: 0 }}
                aria-hidden="true"
              >
                <path
                  d="M12.1875 9.75L9.00001 12.9375L5.8125 9.75M9.00001 2.0625L9 12.375M14.4375 15.9375H3.5625"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="square"
                />
              </svg>
              <span>开始诊断</span>
            </Link>
          </li>
        </ul>
      </nav>

      {/* OpenCode Mobile Nav Toggle */}
      <nav data-component="nav-mobile">
        <button
          type="button"
          data-component="nav-mobile-toggle"
          aria-expanded={open}
          aria-controls="nav-mobile-menu"
          className="nav-toggle"
          onClick={() => setOpen((c) => !c)}
        >
          <span className="sr-only">{open ? "关闭菜单" : "打开菜单"}</span>
          <svg
            className="icon icon-hamburger"
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            aria-hidden="true"
            xmlns="http://www.w3.org/2000/svg"
          >
            {open ? (
              <path
                d="M18 6L6 18M6 6L18 18"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="square"
              />
            ) : (
              <>
                <path d="M19 17H5V16H19V17Z" fill="currentColor" />
                <path d="M19 8H5V7H19V8Z" fill="currentColor" />
              </>
            )}
          </svg>
        </button>

        {open && (
          <div id="nav-mobile-menu" className="nav-mobile-dropdown">
            <ul>
              {NAV_LINKS.map(({ href, label, external }) => (
                <li key={label}>
                  {external ? (
                    <a
                      href={href}
                      target="_blank"
                      rel="noreferrer"
                      onClick={() => setOpen(false)}
                    >
                      {label}
                    </a>
                  ) : (
                    <Link
                      href={href}
                      className={path === href ? "active" : ""}
                      onClick={() => setOpen(false)}
                    >
                      {label}
                    </Link>
                  )}
                </li>
              ))}
              <li>
                <Link
                  data-slot="cta-button"
                  href="/diagnose"
                  onClick={() => setOpen(false)}
                >
                  <svg
                    width="18"
                    height="18"
                    viewBox="0 0 18 18"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                    style={{ flexShrink: 0 }}
                  >
                    <path
                      d="M12.1875 9.75L9.00001 12.9375L5.8125 9.75M9.00001 2.0625L9 12.375M14.4375 15.9375H3.5625"
                      stroke="currentColor"
                      strokeWidth="1.5"
                      strokeLinecap="square"
                    />
                  </svg>
                  <span>开始诊断</span>
                </Link>
              </li>
            </ul>
          </div>
        )}
      </nav>
    </>
  );
}
