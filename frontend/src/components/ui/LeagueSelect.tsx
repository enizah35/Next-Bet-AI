"use client";
import React from "react";

interface LeagueSelectProps {
  value: string;
  onChange: (v: string) => void;
  leagues: string[];
}

export function LeagueSelect({ value, onChange, leagues }: LeagueSelectProps) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      style={{
        padding: "8px 32px 8px 14px",
        fontSize: 13,
        fontWeight: 500,
        borderRadius: 10,
        border: "1px solid var(--border)",
        background: "var(--bg-inset)",
        color: "var(--text)",
        cursor: "pointer",
        appearance: "none",
        backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23888' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E")`,
        backgroundRepeat: "no-repeat",
        backgroundPosition: "right 10px center",
        outline: "none",
        minWidth: 160,
      }}
    >
      <option value="all">Toutes les ligues</option>
      {leagues.map((l) => (
        <option key={l} value={l}>{l}</option>
      ))}
    </select>
  );
}
