import React from "react";

interface FormDotsProps {
  form?: string[];
  size?: number;
}

const colorOf = (r: string) =>
  r === "W" ? "var(--good)" : r === "D" ? "var(--warn)" : "var(--bad)";
const tintOf = (r: string) =>
  r === "W" ? "var(--good-tint)" : r === "D" ? "var(--warn-tint)" : "var(--bad-tint)";

export function FormDots({ form = [], size = 18 }: FormDotsProps) {
  return (
    <div style={{ display: "flex", gap: 3 }}>
      {form.map((r, i) => (
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
