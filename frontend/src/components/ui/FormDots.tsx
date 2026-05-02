import React from "react";

interface FormDotsProps {
  form?: string[];
  size?: number;
  emptyCount?: number;
}

const colorOf = (r: string) =>
  r === "W" ? "var(--good)" : r === "D" ? "var(--warn)" : "var(--bad)";
const tintOf = (r: string) =>
  r === "W" ? "var(--good-tint)" : r === "D" ? "var(--warn-tint)" : "var(--bad-tint)";

export function FormDots({ form = [], size = 18, emptyCount = 5 }: FormDotsProps) {
  const safeForm = form.filter((r) => ["W", "D", "L"].includes(r));

  return (
    <div style={{ display: "flex", gap: 3 }}>
      {safeForm.length === 0 && Array.from({ length: emptyCount }).map((_, i) => (
        <div
          key={`empty-${i}`}
          title="Forme indisponible"
          style={{
            width: size, height: size, borderRadius: 5,
            background: "var(--bg-elev)", color: "var(--text-muted)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontFamily: "var(--font-mono)", fontSize: size * 0.55, fontWeight: 600,
            border: "1px solid var(--border)",
          }}
        >
          -
        </div>
      ))}
      {safeForm.map((r, i) => (
        <div
          key={i}
          style={{
            width: size, height: size, borderRadius: 5,
            background: tintOf(r), color: colorOf(r),
            display: "flex", alignItems: "center", justifyContent: "center",
            fontFamily: "var(--font-mono)", fontSize: size * 0.55, fontWeight: 600,
            border: `1px solid ${colorOf(r)}55`,
          }}
        >
          {r}
        </div>
      ))}
    </div>
  );
}
