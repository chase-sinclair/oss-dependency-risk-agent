"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "Home" },
  { href: "/dashboard", label: "Health Dashboard" },
  { href: "/search", label: "Semantic Search" },
  { href: "/reports", label: "Reports" },
  { href: "/agent", label: "Agent Control Room" },
];

export default function Sidebar() {
  const pathname = usePathname();

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <aside className="w-56 bg-[#0f172a] flex flex-col h-screen shrink-0">
      <div className="px-4 py-5 border-b border-slate-700">
        <span className="text-white font-semibold text-sm tracking-wide">
          OSS Risk Agent
        </span>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {NAV.map(({ href, label }) => (
          <Link
            key={href}
            href={href}
            className={`block px-3 py-2 rounded text-sm ${
              isActive(href)
                ? "bg-slate-700 text-white font-medium"
                : "text-slate-400 hover:text-white hover:bg-slate-800"
            }`}
          >
            {label}
          </Link>
        ))}
      </nav>

      <div className="px-4 py-4 border-t border-slate-700">
        <p className="text-slate-500 text-xs">Powered by Claude</p>
      </div>
    </aside>
  );
}
