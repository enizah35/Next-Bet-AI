"use client";
import React from "react";
import { DropdownSelect } from "./DropdownSelect";

interface LeagueSelectProps {
  value: string;
  onChange: (v: string) => void;
  leagues: string[];
}

export function LeagueSelect({ value, onChange, leagues }: LeagueSelectProps) {
  const options = [
    { value: "all", label: "Toutes les ligues" },
    ...leagues.map((league) => ({ value: league, label: league })),
  ];

  return (
    <DropdownSelect
      value={value}
      onChange={onChange}
      options={options}
      minWidth={190}
      ariaLabel="Filtrer par ligue"
    />
  );
}
