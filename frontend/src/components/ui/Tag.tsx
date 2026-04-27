import React from "react";

interface TagProps {
  children: React.ReactNode;
  color?: string;
  tint?: string;
  icon?: React.ReactNode;
  size?: "sm" | "md";
}

export function Tag({ children, color = "var(--text-soft)", tint = "var(--bg-inset)", icon, size = "md" }: TagProps) {
  const pad = size === "sm" ? "3px 8px" : "5px 10px";
  const fs = size === "sm" ? 11 : 12;
  return (
    <span
      style={{
        display: "inline-flex", alignItems: "center", gap: 5,
        padding: pad, fontSize: fs, fontWeight: 500,
        background: tint, color,
        borderRadius: 6, letterSpacing: "0.01em",
      }}
    >
      {icon}
      {children}
    </span>
  );
}
