import React from "react";

interface RingProps {
  value: number;
  size?: number;
  stroke?: number;
  color?: string;
  label?: string;
}

export function Ring({ value, size = 60, stroke = 5, color = "var(--acc-home)", label }: RingProps) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const off = c - (Math.min(value, 100) / 100) * c;
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
      <div style={{ position: "relative", width: size, height: size }}>
        <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--bg-inset)" strokeWidth={stroke} />
          <circle
            cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke}
            strokeDasharray={c} strokeDashoffset={off} strokeLinecap="round"
            style={{ transition: "stroke-dashoffset 0.8s cubic-bezier(0.22,1,0.36,1)" }}
          />
        </svg>
        <div
          className="mono tabular"
          style={{
            position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: size * 0.26, fontWeight: 600, letterSpacing: "-0.02em",
          }}
        >
          {value}<span style={{ fontSize: size * 0.18, color: "var(--text-muted)", marginLeft: 1 }}>%</span>
        </div>
      </div>
      {label && <div className="overline" style={{ fontSize: 10 }}>{label}</div>}
    </div>
  );
}
