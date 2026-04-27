"use client";
import React, { useState } from "react";

// api-football / api-sports.io team IDs → https://media.api-sports.io/football/teams/{id}.png
const LOGO_IDS: Record<string, number> = {
  // Premier League
  "Arsenal": 42,
  "Man City": 50,
  "Manchester City": 50,
  "Liverpool": 40,
  "Chelsea": 49,
  "Tottenham": 47,
  "Spurs": 47,
  "Man United": 33,
  "Manchester United": 33,
  "Newcastle": 34,
  "Newcastle United": 34,
  "Brighton": 51,
  "Aston Villa": 66,
  "West Ham": 48,
  "West Ham United": 48,
  "Wolves": 39,
  "Wolverhampton": 39,
  "Everton": 45,
  "Crystal Palace": 52,
  "Brentford": 55,
  "Fulham": 36,
  "Nottm Forest": 65,
  "Nottingham Forest": 65,
  "Leicester": 46,
  "Leicester City": 46,
  "Bournemouth": 35,
  "Ipswich": 57,
  "Ipswich Town": 57,
  "Southampton": 41,
  // Ligue 1
  "PSG": 85,
  "Paris Saint-Germain": 85,
  "Paris SG": 85,
  "Lyon": 80,
  "Olympique Lyonnais": 80,
  "Marseille": 81,
  "Olympique de Marseille": 81,
  "Monaco": 91,
  "AS Monaco": 91,
  "Lille": 79,
  "LOSC Lille": 79,
  "Nice": 84,
  "OGC Nice": 84,
  "Rennes": 94,
  "Stade Rennais": 94,
  "Lens": 116,
  "RC Lens": 116,
  "Nantes": 83,
  "FC Nantes": 83,
  "Strasbourg": 95,
  "RC Strasbourg": 95,
  "Reims": 93,
  "Stade de Reims": 93,
  "Brest": 106,
  "Stade Brestois": 106,
  "Toulouse": 96,
  "Toulouse FC": 96,
  "Le Havre": 111,
  "Montpellier": 82,
  "Montpellier HSC": 82,
  "Angers": 77,
  "Angers SCO": 77,
  "Auxerre": 94,
  "AJ Auxerre": 94,
  "Lorient": 97,
  "FC Lorient": 97,
  "Saint-Etienne": 97,
  "AS Saint-Etienne": 97,
  "Metz": 112,
  "FC Metz": 112,
  "Paris FC": 114,
};

const TEAM_COLORS: Record<string, { bg: string; fg: string; mono: string }> = {
  "Man City": { bg: "#6CABDD", fg: "#ffffff", mono: "MCI" },
  "Arsenal": { bg: "#EF0107", fg: "#ffffff", mono: "ARS" },
  "Liverpool": { bg: "#C8102E", fg: "#ffffff", mono: "LIV" },
  "Chelsea": { bg: "#034694", fg: "#ffffff", mono: "CHE" },
  "Tottenham": { bg: "#132257", fg: "#ffffff", mono: "TOT" },
  "Man United": { bg: "#DA291C", fg: "#ffffff", mono: "MUN" },
  "Newcastle": { bg: "#241F20", fg: "#ffffff", mono: "NEW" },
  "Brighton": { bg: "#0057B8", fg: "#ffffff", mono: "BHA" },
  "Aston Villa": { bg: "#670E36", fg: "#95BFE5", mono: "AVL" },
  "West Ham": { bg: "#7A263A", fg: "#F3D459", mono: "WHU" },
  "PSG": { bg: "#004170", fg: "#ED1C24", mono: "PSG" },
  "Marseille": { bg: "#2FAEE0", fg: "#ffffff", mono: "OM" },
  "Lyon": { bg: "#DA001A", fg: "#ffffff", mono: "OL" },
  "Monaco": { bg: "#E2001A", fg: "#ffffff", mono: "ASM" },
  "Lille": { bg: "#E01E13", fg: "#ffffff", mono: "LIL" },
  "Nice": { bg: "#E01E1A", fg: "#000000", mono: "NCE" },
  "Rennes": { bg: "#E30613", fg: "#000000", mono: "SRF" },
  "Lens": { bg: "#FFED00", fg: "#E30613", mono: "RCL" },
  "Nantes": { bg: "#FFCD00", fg: "#006B3F", mono: "FCN" },
  "Strasbourg": { bg: "#005BAC", fg: "#E30613", mono: "RCS" },
  "Bayern": { bg: "#DC052D", fg: "#ffffff", mono: "FCB" },
  "Dortmund": { bg: "#FDE100", fg: "#000000", mono: "BVB" },
  "Leverkusen": { bg: "#E32221", fg: "#000000", mono: "B04" },
  "Real Madrid": { bg: "#FEBE10", fg: "#ffffff", mono: "RMA" },
  "Barcelona": { bg: "#A50044", fg: "#004D98", mono: "FCB" },
  "Atletico": { bg: "#CB3524", fg: "#ffffff", mono: "ATM" },
  "Inter": { bg: "#003DA5", fg: "#000000", mono: "INT" },
  "Milan": { bg: "#FB090B", fg: "#000000", mono: "MIL" },
  "Juventus": { bg: "#000000", fg: "#ffffff", mono: "JUV" },
  "Napoli":   { bg: "#12A0D7", fg: "#ffffff", mono: "NAP" },
  "Lorient":  { bg: "#F26522", fg: "#000000", mono: "LOR" },
  "Paris FC": { bg: "#E30613", fg: "#003087", mono: "PFC" },
};

export function getTeam(name: string) {
  return TEAM_COLORS[name] || { bg: "#555", fg: "#fff", mono: name.slice(0, 3).toUpperCase() };
}

export function TeamLogo({ name, size = 40 }: { name: string; size?: number }) {
  const [failed, setFailed] = useState(false);
  const t = getTeam(name);
  const logoId = LOGO_IDS[name];
  const fontSize = size <= 28 ? 9 : size <= 40 ? 11 : 14;

  const radius = Math.round(size * 0.22);

  if (logoId && !failed) {
    const pad = Math.round(size * 0.1);
    return (
      <div
        style={{
          width: size, height: size, borderRadius: radius,
          background: "var(--bg-elev)",
          border: "1px solid var(--border)",
          flexShrink: 0, overflow: "hidden",
          display: "flex", alignItems: "center", justifyContent: "center",
        }}
      >
        <img
          src={`https://media.api-sports.io/football/teams/${logoId}.png`}
          alt={name}
          width={size - pad * 2}
          height={size - pad * 2}
          onError={() => setFailed(true)}
          style={{ width: size - pad * 2, height: size - pad * 2, objectFit: "contain" }}
        />
      </div>
    );
  }

  return (
    <div
      style={{
        width: size, height: size, borderRadius: radius,
        background: t.bg, color: t.fg,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontFamily: "var(--font-mono)", fontWeight: 600, fontSize,
        letterSpacing: "0.02em", flexShrink: 0,
        border: "1px solid rgba(0,0,0,0.12)",
      }}
    >
      {t.mono}
    </div>
  );
}
