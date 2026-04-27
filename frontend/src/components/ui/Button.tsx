"use client";
import React, { useState } from "react";

type Variant = "primary" | "secondary" | "ghost" | "value";
type Size = "sm" | "md" | "lg";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  icon?: React.ReactNode;
  trailingIcon?: React.ReactNode;
}

export function Button({ children, variant = "primary", size = "md", icon, trailingIcon, style, ...rest }: ButtonProps) {
  const [h, setH] = useState(false);

  const sizes = {
    sm: { pad: "6px 12px", fs: 13, height: 30 },
    md: { pad: "10px 16px", fs: 14, height: 40 },
    lg: { pad: "14px 22px", fs: 15, height: 48 },
  };
  const s = sizes[size];

  const base: React.CSSProperties = {
    display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 8,
    padding: s.pad, height: s.height, fontSize: s.fs, fontWeight: 600,
    borderRadius: 12, transition: "all 0.15s ease",
    whiteSpace: "nowrap", letterSpacing: "-0.005em",
    border: "none", cursor: "pointer",
  };

  const variants: Record<Variant, React.CSSProperties> = {
    primary: {
      background: "var(--text)", color: "var(--bg)",
      boxShadow: h ? "0 4px 12px rgba(0,0,0,0.15)" : "0 1px 2px rgba(0,0,0,0.06)",
      transform: h ? "translateY(-1px)" : "none",
    },
    secondary: {
      background: "var(--bg-elev)", color: "var(--text)",
      border: "1px solid var(--border-strong)",
      boxShadow: h ? "var(--shadow-card)" : "none",
    },
    ghost: {
      background: h ? "var(--bg-inset)" : "transparent",
      color: "var(--text)",
    },
    value: {
      background: "var(--value)", color: "#fff",
      boxShadow: h ? "0 6px 20px color-mix(in oklch, var(--value) 40%, transparent)" : "0 1px 2px rgba(0,0,0,0.06)",
      transform: h ? "translateY(-1px)" : "none",
    },
  };

  return (
    <button
      onMouseEnter={() => setH(true)}
      onMouseLeave={() => setH(false)}
      style={{ ...base, ...variants[variant], ...style }}
      {...rest}
    >
      {icon}
      {children}
      {trailingIcon}
    </button>
  );
}
