"use client";
import React from "react";

interface Option {
  value: string;
  label?: string;
  icon?: React.ReactNode;
}

interface SegmentedProps {
  options: Option[];
  value: string;
  onChange: (v: string) => void;
  size?: "sm" | "md";
  className?: string;
}

export function Segmented({ options, value, onChange, size = "md", className }: SegmentedProps) {
  const pad = size === "sm" ? "6px 12px" : "8px 14px";
  const fs = size === "sm" ? 12 : 13;
  return (
    <div
      className={className}
      style={{
        display: "inline-flex", padding: 3, gap: 2,
        background: "var(--bg-inset)", borderRadius: 10,
        border: "1px solid var(--border)",
      }}
    >
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            onClick={() => onChange(o.value)}
            style={{
              padding: pad, fontSize: fs, fontWeight: 500, borderRadius: 8,
              background: active ? "var(--bg-elev)" : "transparent",
              color: active ? "var(--text)" : "var(--text-soft)",
              boxShadow: active ? "0 1px 3px rgba(0,0,0,0.08)" : "none",
              transition: "all 0.15s ease",
              display: "inline-flex", alignItems: "center", gap: 6,
              border: "none", cursor: "pointer",
            }}
          >
            {o.icon}
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
