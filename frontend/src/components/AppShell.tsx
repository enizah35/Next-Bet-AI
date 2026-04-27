"use client";
import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BrandLockup } from "./BrandLockup";
import { I } from "./Icons";
import { useTheme } from "@/context/ThemeContext";

const navItems = [
  { href: "/dashboard", label: "Analyses", icon: <I.Spark size={18} /> },
  { href: "/tips",      label: "Tips du Jour", icon: <I.Flame size={18} /> },
  { href: "/stats",     label: "Stats & AI", icon: <I.Chart size={18} /> },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { mode, toggleMode } = useTheme();

  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      {/* Sidebar */}
      <aside
        style={{
          width: 220, flexShrink: 0,
          background: "var(--bg-sidebar)",
          borderRight: "1px solid var(--border)",
          display: "flex", flexDirection: "column",
          position: "sticky", top: 0, height: "100vh",
          padding: "22px 16px",
        }}
      >
        <div style={{ padding: "0 8px 28px" }}>
          <BrandLockup size={18} />
        </div>

        <nav style={{ display: "flex", flexDirection: "column", gap: 2, flex: 1 }}>
          {navItems.map((it) => {
            const active = pathname === it.href || (it.href !== "/" && pathname.startsWith(it.href));
            return (
              <Link
                key={it.href}
                href={it.href}
                style={{
                  display: "flex", alignItems: "center", gap: 12,
                  padding: "10px 12px", borderRadius: 10,
                  fontSize: 14, fontWeight: 500,
                  background: active ? "var(--bg-inset)" : "transparent",
                  color: active ? "var(--text)" : "var(--text-soft)",
                  transition: "all 0.15s ease",
                  textDecoration: "none",
                }}
                onMouseEnter={(e) => { if (!active) (e.currentTarget as HTMLElement).style.background = "var(--bg-inset)"; }}
                onMouseLeave={(e) => { if (!active) (e.currentTarget as HTMLElement).style.background = "transparent"; }}
              >
                {it.icon}
                {it.label}
              </Link>
            );
          })}
        </nav>

        {/* Theme toggle */}
        <button
          onClick={toggleMode}
          style={{
            display: "flex", alignItems: "center", gap: 10,
            padding: "10px 12px", borderRadius: 10, border: "none",
            background: "var(--bg-inset)", color: "var(--text-soft)",
            fontSize: 13, fontWeight: 500, cursor: "pointer", width: "100%",
          }}
        >
          {mode === "light" ? <I.Moon size={16} /> : <I.Sun size={16} />}
          {mode === "light" ? "Mode sombre" : "Mode clair"}
        </button>
      </aside>

      {/* Main content */}
      <main style={{ flex: 1, minWidth: 0, position: "relative" }}>
        {children}
      </main>
    </div>
  );
}

export function PageHeader({
  title,
  subtitle,
  actions,
  overline,
}: {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
  overline?: string;
}) {
  return (
    <div
      style={{
        padding: "36px 40px 20px",
        display: "flex", alignItems: "flex-end", justifyContent: "space-between",
        gap: 24, flexWrap: "wrap",
      }}
    >
      <div style={{ maxWidth: 720 }}>
        {overline && <div className="overline" style={{ marginBottom: 8 }}>{overline}</div>}
        <h1 style={{ fontSize: 34, fontWeight: 600, letterSpacing: "-0.025em", marginBottom: subtitle ? 6 : 0, lineHeight: 1.1 }}>
          {title}
        </h1>
        {subtitle && <p style={{ color: "var(--text-soft)", fontSize: 15, lineHeight: 1.5 }}>{subtitle}</p>}
      </div>
      {actions && <div style={{ display: "flex", gap: 10, alignItems: "center" }}>{actions}</div>}
    </div>
  );
}
