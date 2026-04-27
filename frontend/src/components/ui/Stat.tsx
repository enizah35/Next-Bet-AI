import React from "react";

interface StatProps {
  label: string;
  value: string | number;
  sub?: string;
  color?: string;
}

export function Stat({ label, value, sub, color }: StatProps) {
  return (
    <div>
      <div className="overline" style={{ marginBottom: 4 }}>{label}</div>
      <div
        className="mono tabular"
        style={{ fontSize: 22, fontWeight: 600, color: color || "var(--text)", letterSpacing: "-0.02em" }}
      >
        {value}
      </div>
      {sub && <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}
