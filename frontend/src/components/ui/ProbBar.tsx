import React from "react";

interface ProbBarProps {
  p1: number;
  pn: number;
  p2: number;
  height?: number;
  gap?: number;
  rounded?: boolean;
}

export function ProbBar({ p1, pn, p2, height = 8, gap = 3, rounded = true }: ProbBarProps) {
  const r = rounded ? height / 2 : 3;
  return (
    <div style={{ display: "flex", gap, width: "100%" }}>
      <div style={{ width: `${p1}%`, height, background: "var(--acc-home)", borderRadius: r, transition: "width 0.6s cubic-bezier(0.22,1,0.36,1)" }} />
      <div style={{ width: `${pn}%`, height, background: "var(--acc-draw)", borderRadius: r, transition: "width 0.6s cubic-bezier(0.22,1,0.36,1)" }} />
      <div style={{ width: `${p2}%`, height, background: "var(--acc-away)", borderRadius: r, transition: "width 0.6s cubic-bezier(0.22,1,0.36,1)" }} />
    </div>
  );
}
