"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/",          label: "Command Center",  icon: "⬡" },
  { href: "/dashboard", label: "Health Dashboard", icon: "◈" },
  { href: "/search",    label: "Semantic Search",  icon: "◎" },
  { href: "/reports",   label: "Intel Reports",    icon: "◻" },
  { href: "/agent",     label: "Agent Control",    icon: "◆" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <aside
      className="w-56 flex flex-col h-screen shrink-0"
      style={{
        background: "rgba(11,14,20,0.92)",
        backdropFilter: "blur(10px)",
        WebkitBackdropFilter: "blur(10px)",
        borderRight: "1px solid rgba(255,255,255,0.07)",
      }}
    >
      {/* Brand mark */}
      <div className="px-4 py-5" style={{ borderBottom: "1px solid rgba(255,255,255,0.07)" }}>
        <div className="flex items-center gap-2.5">
          <svg width="26" height="26" viewBox="0 0 26 26" fill="none">
            <path
              d="M13 2L3 6.5V13C3 18.25 7.4 23.2 13 24.5C18.6 23.2 23 18.25 23 13V6.5L13 2Z"
              fill="rgba(139,92,246,0.15)"
              stroke="#8B5CF6"
              strokeWidth="1.5"
              strokeLinejoin="round"
            />
            <path
              d="M9.5 13L12 15.5L17 10.5"
              stroke="#00E676"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <div>
            <p className="text-white font-bold tracking-widest uppercase" style={{ fontSize: "11px" }}>
              The Sentinel
            </p>
            <p style={{ color: "#8B9BB4", fontSize: "9px", letterSpacing: "0.14em" }}>
              OSS RISK AGENT
            </p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto scrollbar-dark">
        {NAV.map(({ href, label, icon }) => {
          const active = isActive(href);
          return (
            <Link
              key={href}
              href={href}
              className="flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors"
              style={{
                background:  active ? "rgba(139,92,246,0.14)" : "transparent",
                color:       active ? "#F0F6FC" : "#8B9BB4",
                borderLeft:  active ? "2px solid #8B5CF6" : "2px solid transparent",
                fontWeight:  active ? 500 : 400,
              }}
            >
              <span style={{ color: active ? "#8B5CF6" : "#4B5563", fontSize: "12px" }}>
                {icon}
              </span>
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-4 py-4" style={{ borderTop: "1px solid rgba(255,255,255,0.07)" }}>
        <p style={{ color: "#4B5563", fontSize: "10px", letterSpacing: "0.08em" }} className="uppercase mb-1">
          Powered by Claude Sonnet
        </p>
        <div className="flex items-center gap-1.5">
          <span
            className="inline-block w-1.5 h-1.5 rounded-full animate-agent-pulse"
            style={{ background: "#8B5CF6" }}
          />
          <span style={{ color: "#8B9BB4", fontSize: "10px" }}>LangGraph active</span>
        </div>
      </div>
    </aside>
  );
}
