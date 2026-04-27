import React from "react";

export function BrandMark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
      <circle cx="20" cy="20" r="16" fill="none" stroke="currentColor" strokeWidth="3" strokeDasharray="34 66" strokeDashoffset="0" transform="rotate(-90 20 20)" opacity="0.9"/>
      <circle cx="20" cy="20" r="16" fill="none" stroke="currentColor" strokeWidth="3" strokeDasharray="18 82" strokeDashoffset="-34" transform="rotate(-90 20 20)" opacity="0.5"/>
      <circle cx="20" cy="20" r="16" fill="none" stroke="currentColor" strokeWidth="3" strokeDasharray="48 52" strokeDashoffset="-52" transform="rotate(-90 20 20)" opacity="0.25"/>
      <circle cx="20" cy="20" r="2.5" fill="currentColor"/>
    </svg>
  );
}

export function BrandLockup({ size = 20, color }: { size?: number; color?: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, color: color || "inherit" }}>
      <BrandMark size={size + 8} />
      <span style={{ fontSize: size * 0.8, fontWeight: 700, letterSpacing: "-0.02em" }}>
        Next Bet<span style={{ opacity: 0.45 }}>.ai</span>
      </span>
    </div>
  );
}
