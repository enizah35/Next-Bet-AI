"""
src/features/bet_builder.py
AI Bet Builder : génère des compositions de paris combinés intelligentes.
Utilise les cotes réelles Winamax & Betclic quand disponibles.
Marchés limités à ceux réellement proposés par les bookmakers FR.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================
# Marchés disponibles sur Winamax / Betclic
# ============================================================

def _best_bookmaker_odds(broker_data: dict, *keys: str) -> tuple[float, str]:
    """Retourne la meilleure cote et le nom du bookmaker pour un marché donné."""
    best_odds = 0.0
    best_bm = ""
    for bm_name, data in broker_data.items():
        val = data
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k, 0)
            elif isinstance(val, list):
                # Pour totals: chercher le bon point
                val = 0
                break
            else:
                val = 0
                break
        if isinstance(val, (int, float)) and val > best_odds:
            best_odds = val
            best_bm = bm_name
    return round(best_odds, 2), best_bm


def _totals_odds(broker_totals: dict, point: float) -> tuple[float, str]:
    """Retourne la meilleure cote over pour un point donné (ex: 2.5) et le bookmaker."""
    best_odds = 0.0
    best_bm = ""
    for bm_name, lines in broker_totals.items():
        for line in lines:
            if abs(line.get("point", 0) - point) < 0.01:
                if line.get("over", 0) > best_odds:
                    best_odds = line["over"]
                    best_bm = bm_name
    return round(best_odds, 2), best_bm


def _all_bookmaker_odds_for_market(broker_data: dict, *keys: str) -> list[dict]:
    """Retourne les cotes de tous les bookmakers pour un marché."""
    result = []
    for bm_name, data in broker_data.items():
        val = data
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k, 0)
            else:
                val = 0
                break
        if isinstance(val, (int, float)) and val > 0:
            result.append({"bookmaker": bm_name, "odds": round(val, 2)})
    return result


def _all_totals_odds(broker_totals: dict, point: float) -> list[dict]:
    """Retourne les cotes over de tous les bookmakers pour un point donné."""
    result = []
    for bm_name, lines in broker_totals.items():
        for line in lines:
            if abs(line.get("point", 0) - point) < 0.01:
                result.append({"bookmaker": bm_name, "odds": round(line.get("over", 0), 2)})
    return result


def generate_bet_builder(
    match_stats: dict,
    match_probs: dict,
    bookmaker_odds: Optional[dict] = None,
    max_selections: int = 4,
) -> dict:
    """
    Génère une composition de paris IA pour un match.
    Utilise les cotes réelles Winamax/Betclic quand disponibles.

    Args:
        match_stats: dict from predict_match_stats()
        match_probs: dict with p1, pn, p2
        bookmaker_odds: dict avec h2h, totals, btts par bookmaker (ou None)
        max_selections: nombre max de sélections dans le combi

    Returns:
        dict avec selections[], combined_odds, combined_confidence
    """
    bk = bookmaker_odds or {}
    h2h_bk = bk.get("h2h", {})
    totals_bk = bk.get("totals", {})
    btts_bk = bk.get("btts", {})
    has_bookmaker = bool(h2h_bk or totals_bk or btts_bk)

    candidates = []

    # --- 1. Victoire domicile (1) ---
    if match_probs.get("p1", 0) > 50:
        odds_val, bm = _best_bookmaker_odds(h2h_bk, "home")
        if not odds_val:
            odds_val = round(100 / max(match_probs["p1"], 1), 2)
            bm = ""
        candidates.append({
            "key": "match_result_home",
            "label": "Home Win",
            "label_fr": "Victoire domicile",
            "category": "Résultat",
            "confidence": round(match_probs["p1"]),
            "odds": max(1.05, min(15.0, odds_val)),
            "bookmaker": bm,
            "all_odds": _all_bookmaker_odds_for_market(h2h_bk, "home"),
        })

    # --- 2. Victoire extérieur (2) ---
    if match_probs.get("p2", 0) > 50:
        odds_val, bm = _best_bookmaker_odds(h2h_bk, "away")
        if not odds_val:
            odds_val = round(100 / max(match_probs["p2"], 1), 2)
            bm = ""
        candidates.append({
            "key": "match_result_away",
            "label": "Away Win",
            "label_fr": "Victoire extérieur",
            "category": "Résultat",
            "confidence": round(match_probs["p2"]),
            "odds": max(1.05, min(15.0, odds_val)),
            "bookmaker": bm,
            "all_odds": _all_bookmaker_odds_for_market(h2h_bk, "away"),
        })

    # --- 3. Double chance domicile (1N) ---
    dc_home = match_probs.get("p1", 0) + match_probs.get("pn", 0)
    if dc_home > 60:
        # Double chance = dérivé de h2h (pas un marché direct sur The Odds API)
        # Cote approx = 1 / (P(H) + P(N))
        odds_val = round(100 / max(dc_home, 1), 2)
        # Si on a les h2h, on peut estimer mieux
        h_odds, _ = _best_bookmaker_odds(h2h_bk, "home")
        d_odds, _ = _best_bookmaker_odds(h2h_bk, "draw")
        if h_odds and d_odds:
            # Formule double chance = 1 / (1/home + 1/draw)
            dc_real = 1.0 / ((1.0 / h_odds) + (1.0 / d_odds))
            odds_val = round(dc_real, 2)
        bm_list = []
        for bm_name in h2h_bk:
            bm_h = h2h_bk[bm_name].get("home", 0)
            bm_d = h2h_bk[bm_name].get("draw", 0)
            if bm_h > 0 and bm_d > 0:
                dc_o = round(1.0 / ((1.0 / bm_h) + (1.0 / bm_d)), 2)
                bm_list.append({"bookmaker": bm_name, "odds": dc_o})
        candidates.append({
            "key": "double_chance_home",
            "label": "Home or Draw",
            "label_fr": "1 ou N (Double chance)",
            "category": "Double Chance",
            "confidence": round(dc_home),
            "odds": max(1.01, min(5.0, odds_val)),
            "bookmaker": bm_list[0]["bookmaker"] if bm_list else "",
            "all_odds": bm_list,
        })

    # --- 4. Double chance extérieur (N2) ---
    dc_away = match_probs.get("p2", 0) + match_probs.get("pn", 0)
    if dc_away > 60:
        odds_val = round(100 / max(dc_away, 1), 2)
        a_odds, _ = _best_bookmaker_odds(h2h_bk, "away")
        d_odds, _ = _best_bookmaker_odds(h2h_bk, "draw")
        if a_odds and d_odds:
            dc_real = 1.0 / ((1.0 / a_odds) + (1.0 / d_odds))
            odds_val = round(dc_real, 2)
        bm_list = []
        for bm_name in h2h_bk:
            bm_a = h2h_bk[bm_name].get("away", 0)
            bm_d = h2h_bk[bm_name].get("draw", 0)
            if bm_a > 0 and bm_d > 0:
                dc_o = round(1.0 / ((1.0 / bm_a) + (1.0 / bm_d)), 2)
                bm_list.append({"bookmaker": bm_name, "odds": dc_o})
        candidates.append({
            "key": "double_chance_away",
            "label": "Away or Draw",
            "label_fr": "N ou 2 (Double chance)",
            "category": "Double Chance",
            "confidence": round(dc_away),
            "odds": max(1.01, min(5.0, odds_val)),
            "bookmaker": bm_list[0]["bookmaker"] if bm_list else "",
            "all_odds": bm_list,
        })

    # --- 5. Plus de 2.5 buts ---
    over25 = match_stats.get("over25_pct", 50)
    if over25 > 50:
        odds_val, bm = _totals_odds(totals_bk, 2.5)
        if not odds_val:
            odds_val = round(100 / max(over25, 1), 2)
            bm = ""
        candidates.append({
            "key": "over_25",
            "label": "Over 2.5 Goals",
            "label_fr": "Plus de 2.5 buts",
            "category": "Buts",
            "confidence": over25,
            "odds": max(1.05, min(8.0, odds_val)),
            "bookmaker": bm,
            "all_odds": _all_totals_odds(totals_bk, 2.5),
        })

    # --- 6. Plus de 1.5 buts ---
    over15 = match_stats.get("over15_pct", 50)
    if over15 > 55:
        odds_val, bm = _totals_odds(totals_bk, 1.5)
        if not odds_val:
            odds_val = round(100 / max(over15, 1), 2)
            bm = ""
        candidates.append({
            "key": "over_15",
            "label": "Over 1.5 Goals",
            "label_fr": "Plus de 1.5 buts",
            "category": "Buts",
            "confidence": over15,
            "odds": max(1.05, min(5.0, odds_val)),
            "bookmaker": bm,
            "all_odds": _all_totals_odds(totals_bk, 1.5),
        })

    # --- 7. Les deux équipes marquent (BTTS) ---
    btts_pct = match_stats.get("btts_pct", 50)
    if btts_pct > 55:
        odds_val, bm = _best_bookmaker_odds(btts_bk, "yes")
        if not odds_val:
            odds_val = round(100 / max(btts_pct, 1), 2)
            bm = ""
        candidates.append({
            "key": "btts",
            "label": "Both Teams To Score",
            "label_fr": "Les deux marquent",
            "category": "BTTS",
            "confidence": btts_pct,
            "odds": max(1.05, min(5.0, odds_val)),
            "bookmaker": bm,
            "all_odds": _all_bookmaker_odds_for_market(btts_bk, "yes"),
        })

    # Assurer des valeurs cohérentes
    for c in candidates:
        c["confidence"] = max(30, min(95, c["confidence"]))
        c["odds"] = max(1.01, c["odds"])

    # Trier par confiance descendante
    candidates.sort(key=lambda x: x["confidence"], reverse=True)

    # --- Conflits : paris mutuellement exclusifs ou redondants ---
    CONFLICTS: dict[str, set[str]] = {
        # 1 vs 2, 1 vs N2
        "match_result_home":  {"match_result_away", "double_chance_away"},
        "match_result_away":  {"match_result_home", "double_chance_home"},
        # 1N vs N2, 1N vs 2
        "double_chance_home": {"double_chance_away", "match_result_away"},
        "double_chance_away": {"double_chance_home", "match_result_home"},
        # Over 2.5 implique Over 1.5 → redondant
        "over_25":            {"over_15"},
        "over_15":            {"over_25"},
    }

    selections: list[dict] = []
    selected_keys: set[str] = set()
    for c in candidates:
        if len(selections) >= max_selections:
            break
        key = c["key"]
        # Vérifier si ce candidat est en conflit avec une sélection déjà prise
        blocked = CONFLICTS.get(key, set())
        if blocked & selected_keys:
            continue
        selections.append(c)
        selected_keys.add(key)

    if not selections:
        return {"selections": [], "combined_odds": 1.0, "combined_confidence": 0, "source": "none"}

    # Cote combinée = produit des cotes individuelles
    combined_odds = 1.0
    for s in selections:
        combined_odds *= s["odds"]
    combined_odds = round(combined_odds, 2)

    # Confiance combinée approximée
    combined_conf = 1.0
    for s in selections:
        combined_conf *= (s["confidence"] / 100)
    combined_pct = round(combined_conf * 100)

    return {
        "selections": selections,
        "combined_odds": combined_odds,
        "combined_confidence": combined_pct,
        "source": "winamax_betclic" if has_bookmaker else "ai_model",
    }


def generate_daily_tips(
    matches_data: list[dict],
    max_tips: int = 10,
) -> list[dict]:
    """
    Sélectionne les meilleurs tips du jour à partir des données enrichies.
    Utilise les cotes bookmaker quand disponibles.
    """
    tips = []

    for match in matches_data:
        probs = match.get("probs", {})
        stats = match.get("stats", {})
        home = match.get("homeTeam", "")
        away = match.get("awayTeam", "")
        competition = match.get("competition", "")
        date = match.get("date", "")
        bk = match.get("bookmaker_odds", {})
        h2h_bk = bk.get("h2h", {})
        btts_bk = bk.get("btts", {})
        totals_bk = bk.get("totals", {})

        # Double chance home (fiable)
        dc_conf = probs.get("p1", 0) + probs.get("pn", 0)
        if dc_conf > 70:
            odds_val = round(100 / dc_conf, 2)
            h_o, _ = _best_bookmaker_odds(h2h_bk, "home")
            d_o, _ = _best_bookmaker_odds(h2h_bk, "draw")
            if h_o and d_o:
                odds_val = round(1.0 / ((1.0 / h_o) + (1.0 / d_o)), 2)
            tips.append({
                "homeTeam": home, "awayTeam": away, "competition": competition,
                "date": date, "tip": "Home or Draw", "tip_fr": "1 ou Nul",
                "category": "Dbl Chance", "confidence": round(dc_conf),
                "odds": max(1.01, odds_val),
            })

        dc_away = probs.get("p2", 0) + probs.get("pn", 0)
        if dc_away > 70:
            odds_val = round(100 / dc_away, 2)
            a_o, _ = _best_bookmaker_odds(h2h_bk, "away")
            d_o, _ = _best_bookmaker_odds(h2h_bk, "draw")
            if a_o and d_o:
                odds_val = round(1.0 / ((1.0 / a_o) + (1.0 / d_o)), 2)
            tips.append({
                "homeTeam": home, "awayTeam": away, "competition": competition,
                "date": date, "tip": "Away or Draw", "tip_fr": "2 ou Nul",
                "category": "Dbl Chance", "confidence": round(dc_away),
                "odds": max(1.01, odds_val),
            })

        # BTTS
        btts = stats.get("btts_pct", 50)
        if btts > 60:
            odds_val, _ = _best_bookmaker_odds(btts_bk, "yes")
            if not odds_val:
                odds_val = round(100 / btts, 2)
            tips.append({
                "homeTeam": home, "awayTeam": away, "competition": competition,
                "date": date, "tip": "Both Teams To Score", "tip_fr": "Les deux marquent",
                "category": "BTTS", "confidence": btts,
                "odds": max(1.05, odds_val),
            })

        # Over 2.5
        o25 = stats.get("over25_pct", 50)
        if o25 > 58:
            odds_val, _ = _totals_odds(totals_bk, 2.5)
            if not odds_val:
                odds_val = round(100 / o25, 2)
            tips.append({
                "homeTeam": home, "awayTeam": away, "competition": competition,
                "date": date, "tip": "Over 2.5 Goals", "tip_fr": "Plus de 2.5 buts",
                "category": "Goals", "confidence": o25,
                "odds": max(1.05, odds_val),
            })

    tips.sort(key=lambda x: x["confidence"], reverse=True)
    return tips[:max_tips]
