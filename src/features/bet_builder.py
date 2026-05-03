"""
src/features/bet_builder.py
AI Bet Builder v2 — Poisson-based per-match analysis.
Generates diverse, high-probability bet combinations unique to each match profile.
"""

import logging
import itertools
import math
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================
# Poisson helpers
# ============================================================

def _poisson_pmf(k: int, lam: float) -> float:
    """P(X = k) for Poisson(lam)."""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def _poisson_cdf(k: int, lam: float) -> float:
    """P(X <= k) for Poisson(lam)."""
    return sum(_poisson_pmf(i, lam) for i in range(k + 1))


def _build_score_matrix(home_xg: float, away_xg: float, max_goals: int = 7) -> list[list[float]]:
    """Build a joint probability matrix P(home=i, away=j) assuming independence."""
    matrix = []
    for i in range(max_goals + 1):
        row = []
        for j in range(max_goals + 1):
            row.append(_poisson_pmf(i, home_xg) * _poisson_pmf(j, away_xg))
        matrix.append(row)
    return matrix


def _matrix_prob(matrix: list[list[float]], condition) -> float:
    """Sum probabilities in the matrix where condition(home_goals, away_goals) is True."""
    total = 0.0
    for i, row in enumerate(matrix):
        for j, p in enumerate(row):
            if condition(i, j):
                total += p
    return total


# ============================================================
# Bookmaker odds helpers
# ============================================================

def _best_bookmaker_odds(broker_data: dict, *keys: str) -> tuple[float, str]:
    best_odds = 0.0
    best_bm = ""
    for bm_name, data in broker_data.items():
        val = data
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k, 0)
            else:
                val = 0
                break
        if isinstance(val, (int, float)) and val > best_odds:
            best_odds = val
            best_bm = bm_name
    return round(best_odds, 2), best_bm


def _totals_odds(broker_totals: dict, point: float) -> tuple[float, str]:
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
    result = []
    for bm_name, lines in broker_totals.items():
        for line in lines:
            if abs(line.get("point", 0) - point) < 0.01:
                result.append({"bookmaker": bm_name, "odds": round(line.get("over", 0), 2)})
    return result


def _fair_odds(prob: float) -> float:
    """Convert probability (0-1) to fair decimal odds."""
    if prob <= 0:
        return 20.0
    return round(1.0 / prob, 2)


# ============================================================
# Match profiling
# ============================================================

def _profile_match(home_xg: float, away_xg: float, p1: float, pn: float, p2: float) -> str:
    """Categorize the match to guide bet selection diversity."""
    total_xg = home_xg + away_xg
    xg_diff = home_xg - away_xg

    if total_xg >= 3.2:
        if xg_diff > 0.6:
            return "home_dominant_open"
        elif xg_diff < -0.6:
            return "away_dominant_open"
        return "high_scoring_open"
    elif total_xg <= 2.0:
        if xg_diff > 0.4:
            return "home_grind"
        elif xg_diff < -0.4:
            return "away_grind"
        return "low_scoring_tight"
    else:
        if p1 > 50:
            return "home_favourite"
        elif p2 > 50:
            return "away_favourite"
        elif pn > 30:
            return "balanced_draw_risk"
        return "balanced"


# ============================================================
# Core: generate_bet_builder
# ============================================================

def generate_bet_builder(
    match_stats: dict,
    match_probs: dict,
    bookmaker_odds: Optional[dict] = None,
    max_selections: int = 4,
    home_team: str = "Domicile",
    away_team: str = "Exterieur",
    availability: Optional[dict] = None,
) -> dict:
    """
    Generate a diverse, per-match bet combination using Poisson-modelled probabilities.
    Each match gets selections tailored to its unique statistical profile.
    """
    bk = bookmaker_odds or {}
    h2h_bk = bk.get("h2h", {})
    double_chance_bk = bk.get("double_chance", {})
    totals_bk = bk.get("totals", {})
    btts_bk = bk.get("btts", {})
    has_bookmaker = bool(h2h_bk or double_chance_bk or totals_bk or btts_bk)

    p1 = match_probs.get("p1", 33.3)
    pn = match_probs.get("pn", 33.4)
    p2 = match_probs.get("p2", 33.3)

    home_xg = match_stats.get("predicted_home_goals", 1.3)
    away_xg = match_stats.get("predicted_away_goals", 1.1)

    availability = availability or {}
    home_availability = availability.get("home", {}) or {}
    away_availability = availability.get("away", {}) or {}

    def _missing_count(team_availability: dict) -> int:
        missing = team_availability.get("missing_players") or []
        explicit = team_availability.get("injuries_count")
        if isinstance(explicit, int) and explicit > len(missing):
            return explicit
        return len(missing)

    home_missing = _missing_count(home_availability)
    away_missing = _missing_count(away_availability)
    home_squad_score = float(home_availability.get("squad_score", 1.0) or 1.0)
    away_squad_score = float(away_availability.get("squad_score", 1.0) or 1.0)
    home_lineup_confirmed = bool(home_availability.get("lineup_confirmed"))
    away_lineup_confirmed = bool(away_availability.get("lineup_confirmed"))

    lineup_weight = 1.15 if (home_lineup_confirmed or away_lineup_confirmed) else 0.75
    home_absence_pressure = max(0.0, (1.0 - home_squad_score) * 0.7 + max(0, home_missing - away_missing) * 0.025)
    away_absence_pressure = max(0.0, (1.0 - away_squad_score) * 0.7 + max(0, away_missing - home_missing) * 0.025)
    if home_availability.get("key_player_out"):
        home_absence_pressure += 0.05
    if away_availability.get("key_player_out"):
        away_absence_pressure += 0.05
    home_absence_pressure = min(0.18, home_absence_pressure * lineup_weight)
    away_absence_pressure = min(0.18, away_absence_pressure * lineup_weight)

    home_xg = max(0.25, home_xg * (1 - home_absence_pressure) * (1 + away_absence_pressure * 0.45))
    away_xg = max(0.25, away_xg * (1 - away_absence_pressure) * (1 + home_absence_pressure * 0.45))

    p1 = max(3.0, p1 * (1 - home_absence_pressure) * (1 + away_absence_pressure * 0.55))
    p2 = max(3.0, p2 * (1 - away_absence_pressure) * (1 + home_absence_pressure * 0.55))
    pn = max(3.0, pn * (1 + abs(home_absence_pressure - away_absence_pressure) * 0.12))
    result_total = p1 + pn + p2
    if result_total > 0:
        p1, pn, p2 = (p1 / result_total) * 100, (pn / result_total) * 100, (p2 / result_total) * 100

    total_xg = home_xg + away_xg
    home_edge = home_xg - away_xg
    away_edge = away_xg - home_xg

    # Build Poisson score matrix
    M = _build_score_matrix(home_xg, away_xg)

    # Compute precise probabilities for every market
    prob = {}

    # --- Result markets ---
    prob["home_win"] = p1 / 100
    prob["draw"] = pn / 100
    prob["away_win"] = p2 / 100
    prob["dc_home"] = (p1 + pn) / 100
    prob["dc_away"] = (p2 + pn) / 100
    prob["dc_12"] = (p1 + p2) / 100

    # --- Goals totals (Poisson) ---
    prob["over_05"] = 1 - _matrix_prob(M, lambda h, a: h + a <= 0)
    prob["over_15"] = 1 - _matrix_prob(M, lambda h, a: h + a <= 1)
    prob["over_25"] = 1 - _matrix_prob(M, lambda h, a: h + a <= 2)
    prob["over_35"] = 1 - _matrix_prob(M, lambda h, a: h + a <= 3)
    prob["under_25"] = _matrix_prob(M, lambda h, a: h + a <= 2)
    prob["under_35"] = _matrix_prob(M, lambda h, a: h + a <= 3)
    prob["under_45"] = _matrix_prob(M, lambda h, a: h + a <= 4)
    prob["under_15"] = _matrix_prob(M, lambda h, a: h + a <= 1)

    # --- Team-specific goals (Poisson) ---
    prob["home_over_05"] = 1 - _poisson_cdf(0, home_xg)
    prob["home_over_15"] = 1 - _poisson_cdf(1, home_xg)
    prob["away_over_05"] = 1 - _poisson_cdf(0, away_xg)
    prob["away_over_15"] = 1 - _poisson_cdf(1, away_xg)

    # --- BTTS ---
    prob["btts_yes"] = prob["home_over_05"] * prob["away_over_05"]
    prob["btts_no"] = 1 - prob["btts_yes"]

    # --- Clean sheets ---
    prob["home_cs"] = _poisson_cdf(0, away_xg)  # away scores 0
    prob["away_cs"] = _poisson_cdf(0, home_xg)  # home scores 0

    # --- Exact total goals ranges ---
    prob["goals_0_1"] = _matrix_prob(M, lambda h, a: h + a <= 1)
    prob["goals_2_3"] = _matrix_prob(M, lambda h, a: 2 <= h + a <= 3)
    prob["goals_4_plus"] = 1 - _matrix_prob(M, lambda h, a: h + a <= 3)

    # --- Win to nil ---
    prob["home_win_to_nil"] = _matrix_prob(M, lambda h, a: h > 0 and a == 0)
    prob["away_win_to_nil"] = _matrix_prob(M, lambda h, a: a > 0 and h == 0)

    # --- Both score + Over 2.5 combo ---
    prob["btts_over_25"] = _matrix_prob(M, lambda h, a: h > 0 and a > 0 and h + a > 2)

    # --- Home/Away win + Over 1.5 ---
    prob["home_win_over_15"] = _matrix_prob(M, lambda h, a: h > a and h + a > 1)
    prob["away_win_over_15"] = _matrix_prob(M, lambda h, a: a > h and h + a > 1)

    # --- Match profile for diversity ---
    profile = _profile_match(home_xg, away_xg, p1, pn, p2)

    # ============================================================
    # Build candidate list — all possible markets
    # ============================================================
    ALL_MARKETS = [
        # key, label_fr, category, prob_key, min_prob
        ("home_win", f"Victoire {home_team}", "Résultat", "home_win", 0.45),
        ("away_win", f"Victoire {away_team}", "Résultat", "away_win", 0.45),
        ("draw", "Match nul", "Résultat", "draw", 0.34),
        ("dc_home", f"{home_team} ou nul", "Double Chance", "dc_home", 0.74),
        ("dc_away", f"{away_team} ou nul", "Double Chance", "dc_away", 0.74),
        ("over_05", "Plus de 0.5 but", "Buts", "over_05", 0.82),
        ("over_15", "Plus de 1.5 buts", "Buts", "over_15", 0.72),
        ("over_25", "Plus de 2.5 buts", "Buts", "over_25", 0.55),
        ("over_35", "Plus de 3.5 buts", "Buts", "over_35", 0.40),
        ("under_25", "Moins de 2.5 buts", "Buts", "under_25", 0.50),
        ("under_35", "Moins de 3.5 buts", "Buts", "under_35", 0.70),
        ("under_45", "Moins de 4.5 buts", "Buts", "under_45", 0.78),
        ("under_15", "Moins de 1.5 buts", "Buts", "under_15", 0.30),
        ("home_over_05", f"{home_team} marque au moins 1", "Buts Équipe", "home_over_05", 0.65),
        ("home_over_15", f"{home_team} marque 2+", "Buts Équipe", "home_over_15", 0.35),
        ("away_over_05", f"{away_team} marque au moins 1", "Buts Équipe", "away_over_05", 0.55),
        ("away_over_15", f"{away_team} marque 2+", "Buts Équipe", "away_over_15", 0.30),
        ("btts_yes", "Les deux marquent", "BTTS", "btts_yes", 0.50),
        ("btts_no", "Au moins une équipe ne marque pas", "BTTS", "btts_no", 0.45),
        ("home_cs", f"Clean sheet {home_team}", "Défense", "home_cs", 0.30),
        ("away_cs", f"Clean sheet {away_team}", "Défense", "away_cs", 0.25),
        ("home_win_to_nil", f"{home_team} gagne sans encaisser", "Combo", "home_win_to_nil", 0.20),
        ("away_win_to_nil", f"{away_team} gagne sans encaisser", "Combo", "away_win_to_nil", 0.15),
        ("btts_over_25", "BTTS + Plus de 2.5", "Combo", "btts_over_25", 0.35),
        ("home_win_over_15", f"{home_team} gagne + Plus de 1.5", "Combo", "home_win_over_15", 0.35),
        ("away_win_over_15", f"{away_team} gagne + Plus de 1.5", "Combo", "away_win_over_15", 0.25),
        ("goals_0_1", "0 ou 1 but dans le match", "Fourchette", "goals_0_1", 0.20),
        ("goals_2_3", "2 ou 3 buts dans le match", "Fourchette", "goals_2_3", 0.48),
        ("goals_4_plus", "4 buts ou plus", "Fourchette", "goals_4_plus", 0.25),
    ]
    GENERIC_MARKETS = {"over_05", "under_45", "under_35", "over_15"}
    TEAM_SPECIFIC_MARKETS = {
        "home_win", "away_win", "dc_home", "dc_away",
        "home_over_05", "home_over_15", "away_over_05", "away_over_15",
        "home_cs", "away_cs", "home_win_to_nil", "away_win_to_nil",
        "home_win_over_15", "away_win_over_15",
    }
    TACTICAL_MARKETS = {"btts_yes", "btts_no", "over_25", "over_35", "under_25", "under_15", "goals_0_1", "goals_2_3", "goals_4_plus", "btts_over_25"}

    # Filter to only markets above their minimum probability
    candidates = []
    for key, label_fr, category, prob_key, min_prob in ALL_MARKETS:
        p = prob.get(prob_key, 0)
        if p < min_prob:
            continue

        # Get bookmaker odds where available, else use fair odds
        bm_odds, bm_name, all_odds = 0.0, "", []
        if key in ("home_win",):
            bm_odds, bm_name = _best_bookmaker_odds(h2h_bk, "home")
            all_odds = _all_bookmaker_odds_for_market(h2h_bk, "home")
        elif key in ("away_win",):
            bm_odds, bm_name = _best_bookmaker_odds(h2h_bk, "away")
            all_odds = _all_bookmaker_odds_for_market(h2h_bk, "away")
        elif key in ("draw",):
            bm_odds, bm_name = _best_bookmaker_odds(h2h_bk, "draw")
            all_odds = _all_bookmaker_odds_for_market(h2h_bk, "draw")
        elif key in ("dc_home",):
            bm_odds, bm_name = _best_bookmaker_odds(double_chance_bk, "home_draw")
            all_odds = _all_bookmaker_odds_for_market(double_chance_bk, "home_draw")
        elif key in ("dc_away",):
            bm_odds, bm_name = _best_bookmaker_odds(double_chance_bk, "draw_away")
            all_odds = _all_bookmaker_odds_for_market(double_chance_bk, "draw_away")
        elif key in ("dc_12",):
            bm_odds, bm_name = _best_bookmaker_odds(double_chance_bk, "home_away")
            all_odds = _all_bookmaker_odds_for_market(double_chance_bk, "home_away")
        elif key in ("over_05", "over_15", "over_25", "over_35"):
            point = {"over_05": 0.5, "over_15": 1.5, "over_25": 2.5, "over_35": 3.5}[key]
            bm_odds, bm_name = _totals_odds(totals_bk, point)
            all_odds = _all_totals_odds(totals_bk, point)
        elif key in ("btts_yes",):
            bm_odds, bm_name = _best_bookmaker_odds(btts_bk, "yes")
            all_odds = _all_bookmaker_odds_for_market(btts_bk, "yes")
        elif key in ("btts_no",):
            bm_odds, bm_name = _best_bookmaker_odds(btts_bk, "no")
            all_odds = _all_bookmaker_odds_for_market(btts_bk, "no")

        has_real_odds = bm_odds > 0
        odds_val = bm_odds if has_real_odds else _fair_odds(p)
        odds_val = max(1.01, min(30.0, odds_val))
        edge = round(((p * odds_val) - 1) * 100, 1) if has_real_odds else 0.0
        specificity = 0.2
        if key in TEAM_SPECIFIC_MARKETS:
            specificity += 0.45
        if key in TACTICAL_MARKETS:
            specificity += 0.25
        if key in GENERIC_MARKETS:
            specificity -= 0.35
        if home_edge > 0.25 and key.startswith("home"):
            specificity += 0.15
        if away_edge > 0.25 and key.startswith("away"):
            specificity += 0.15
        if total_xg >= 3.0 and key in {"over_25", "over_35", "btts_yes", "btts_over_25", "goals_4_plus"}:
            specificity += 0.15
        if total_xg <= 2.2 and key in {"under_25", "under_35", "btts_no", "goals_0_1", "home_cs", "away_cs"}:
            specificity += 0.15
        if home_absence_pressure > away_absence_pressure + 0.03 and key.startswith("away"):
            specificity += 0.12
        if away_absence_pressure > home_absence_pressure + 0.03 and key.startswith("home"):
            specificity += 0.12

        candidates.append({
            "key": key,
            "label": key.replace("_", " ").title(),
            "label_fr": label_fr,
            "category": category,
            "confidence": round(p * 100),
            "odds": odds_val,
            "bookmaker": bm_name,
            "all_odds": all_odds,
            "odds_source": "bookmaker" if has_real_odds else "model_fair",
            "edge": edge,
            "specificity": round(max(0.0, min(1.0, specificity)), 3),
            "generic": key in GENERIC_MARKETS,
            "_prob": p,         # internal, for sorting
            "_profile": profile,
        })

    # Sort by probability descending (highest chance of passing first)
    candidates.sort(key=lambda x: x["_prob"], reverse=True)

    # ============================================================
    # Smart selection: pick diverse, non-redundant, high-probability bets
    # ============================================================
    CONFLICTS: dict[str, set[str]] = {
        "home_win": {"home_over_05", "away_win", "draw", "dc_home", "dc_away", "away_win_to_nil", "away_cs", "away_win_over_15"},
        "away_win": {"away_over_05", "home_win", "draw", "dc_home", "dc_away", "home_win_to_nil", "home_cs", "home_win_over_15"},
        "draw": {"home_win", "away_win", "dc_12", "home_win_to_nil", "away_win_to_nil",
                 "home_win_over_15", "away_win_over_15"},
        "dc_home": {"dc_away", "home_win", "away_win", "home_win_to_nil", "away_win_to_nil", "home_win_over_15", "away_win_over_15"},
        "dc_away": {"dc_home", "home_win", "away_win", "home_win_to_nil", "away_win_to_nil", "home_win_over_15", "away_win_over_15"},
        "dc_12": {"draw"},
        # Over/Under conflicts
        "over_05": {"under_15", "goals_0_1", "home_over_05", "away_over_05"},
        "over_15": {"under_15", "goals_0_1", "home_win_over_15", "away_win_over_15"},
        "over_25": {"under_25", "under_15", "goals_0_1", "btts_over_25"},
        "over_35": {"under_45", "under_35", "under_25", "under_15", "goals_0_1", "goals_2_3", "goals_4_plus"},
        "under_25": {"over_25", "over_35", "goals_4_plus", "btts_over_25", "under_45", "under_35", "under_15"},
        "under_35": {"over_35", "goals_4_plus", "under_45", "under_25", "under_15"},
        "under_45": {"over_35", "goals_4_plus", "under_35", "under_25", "under_15"},
        "under_15": {"over_15", "over_25", "over_35", "btts_yes", "btts_over_25", "under_45", "under_35", "under_25",
                     "goals_2_3", "goals_4_plus"},
        # BTTS conflicts
        "btts_yes": {"btts_no", "home_cs", "away_cs", "home_win_to_nil", "away_win_to_nil", "btts_over_25", "under_15"},
        "btts_no": {"btts_yes", "btts_over_25"},
        # Team goals
        "home_over_05": {"away_cs", "home_win_to_nil"},
        "home_over_15": {"away_cs"},
        "away_over_05": {"home_cs", "away_win_to_nil"},
        "away_over_15": {"home_cs"},
        # Clean sheet
        "home_cs": {"away_over_05", "away_over_15", "btts_yes", "btts_over_25"},
        "away_cs": {"home_over_05", "home_over_15", "btts_yes", "btts_over_25"},
        # Combos
        "home_win_to_nil": {"home_win", "dc_home", "home_over_05", "away_win", "draw", "btts_yes", "btts_no", "home_cs", "away_over_05"},
        "away_win_to_nil": {"away_win", "dc_away", "away_over_05", "home_win", "draw", "btts_yes", "btts_no", "away_cs", "home_over_05"},
        "btts_over_25": {"btts_no", "under_25", "under_15", "home_cs", "away_cs"},
        "home_win_over_15": {"home_win", "dc_home", "home_over_05", "home_over_15", "over_15", "away_win", "draw", "dc_away"},
        "away_win_over_15": {"away_win", "dc_away", "away_over_05", "away_over_15", "over_15", "home_win", "draw", "dc_home"},
        # Ranges
        "goals_0_1": {"over_15", "over_25", "over_35", "under_15", "goals_2_3", "goals_4_plus"},
        "goals_2_3": {"over_35", "goals_0_1", "goals_4_plus", "under_15"},
        "goals_4_plus": {"under_25", "under_35", "under_15", "goals_0_1", "goals_2_3"},
    }

    # Category limits so we don't stack 3 "Buts" bets
    CATEGORY_LIMITS = {"Résultat": 1, "Double Chance": 1, "Buts": 1,
                       "Buts Équipe": 1, "BTTS": 1, "Défense": 1,
                       "Combo": 1, "Fourchette": 1}

    # Profile-based priority boost: push match-specific interesting bets
    PROFILE_BOOSTS: dict[str, set[str]] = {
        "home_dominant_open": {"home_win", "home_over_15", "over_25", "home_win_over_15"},
        "away_dominant_open": {"away_win", "away_over_15", "over_25", "away_win_over_15"},
        "high_scoring_open": {"over_35", "btts_over_25", "goals_4_plus", "btts_yes"},
        "low_scoring_tight": {"under_25", "under_15", "btts_no", "goals_0_1"},
        "home_grind": {"home_win_to_nil", "under_25", "home_cs", "home_win"},
        "away_grind": {"away_win_to_nil", "under_25", "away_cs", "away_win"},
        "home_favourite": {"home_win", "home_over_05", "dc_home", "home_win_over_15"},
        "away_favourite": {"away_win", "away_over_05", "dc_away", "away_win_over_15"},
        "balanced_draw_risk": {"draw", "under_25", "btts_no", "goals_2_3"},
        "balanced": {"over_25", "btts_yes", "dc_12", "goals_2_3"},
    }
    boosted = PROFILE_BOOSTS.get(profile, set())
    availability_notes: list[str] = []
    if home_missing or away_missing:
        availability_notes.append(f"Absents: {home_team} {home_missing}, {away_team} {away_missing}.")
    if home_lineup_confirmed or away_lineup_confirmed:
        confirmed = []
        if home_lineup_confirmed:
            confirmed.append(home_team)
        if away_lineup_confirmed:
            confirmed.append(away_team)
        availability_notes.append(f"Compo confirmee: {', '.join(confirmed)}.")
    if home_availability.get("key_player_out"):
        availability_notes.append(f"Joueur important absent cote {home_team}.")
    if away_availability.get("key_player_out"):
        availability_notes.append(f"Joueur important absent cote {away_team}.")
    availability_note = " ".join(availability_notes)

    def _conflicts_with_selected(candidate: dict, selected: list[dict]) -> bool:
        key = candidate["key"]
        for selected_item in selected:
            selected_key = selected_item["key"]
            if selected_key in CONFLICTS.get(key, set()) or key in CONFLICTS.get(selected_key, set()):
                return True
        return False

    def _clean_selection(selection: dict) -> dict:
        return {k: v for k, v in selection.items() if not k.startswith("_")}

    def _candidate_score(candidate: dict, recipe: dict, used_keys: set[str]) -> float:
        edge = max(float(candidate.get("edge") or 0.0), 0.0)
        profile_bonus = recipe["profile_weight"] if candidate["key"] in boosted else 0.0
        real_odds_bonus = recipe["real_odds_bonus"] if candidate.get("odds_source") == "bookmaker" else 0.0
        reuse_penalty = recipe["reuse_penalty"] if candidate["key"] in used_keys else 0.0
        generic_penalty = recipe.get("generic_penalty", 0.0) if candidate.get("generic") else 0.0
        return (
            candidate["_prob"] * recipe["prob_weight"]
            + edge * recipe["edge_weight"]
            + min(candidate["odds"], 8.0) * recipe["odds_weight"]
            + candidate.get("specificity", 0.0) * recipe.get("specificity_weight", 0.0)
            + profile_bonus
            + real_odds_bonus
            - reuse_penalty
            - generic_penalty
        )

    def _combined_pct(legs: list[dict]) -> float:
        combined_prob = 1.0
        for leg in legs:
            combined_prob *= leg["confidence"] / 100
        return round(combined_prob * 100, 1)

    def _valid_leg_set(legs: tuple[dict, ...], recipe: dict, used_keys: set[str]) -> bool:
        cat_counts: dict[str, int] = {}
        selected: list[dict] = []
        specific_count = 0
        generic_count = 0
        reused_count = 0

        for c in legs:
            if c["_prob"] < recipe["min_prob"]:
                return False
            if c["odds"] < 1.05:
                return False
            if c["_prob"] > 0.97 and c["odds"] < 1.05:
                return False
            if _conflicts_with_selected(c, selected):
                return False

            cat = c["category"]
            cat_limit = recipe.get("category_limits", CATEGORY_LIMITS).get(cat, 2)
            if cat_counts.get(cat, 0) >= cat_limit:
                return False

            selected.append(c)
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
            if c.get("specificity", 0.0) >= 0.5:
                specific_count += 1
            if c.get("generic"):
                generic_count += 1
            if c["key"] in used_keys:
                reused_count += 1

        if specific_count < recipe.get("min_specific_legs", 1):
            return False
        if generic_count > recipe.get("max_generic_legs", 0):
            return False
        if reused_count > recipe.get("max_reused_legs", 0):
            return False

        return True

    def _set_score(legs: tuple[dict, ...], recipe: dict, used_keys: set[str]) -> float:
        combined_pct = _combined_pct(list(legs))
        range_min = recipe["range_min"]
        range_max = recipe["range_max"]
        target = recipe["target_confidence"]
        if combined_pct < range_min:
            range_penalty = range_min - combined_pct
        elif combined_pct > range_max:
            range_penalty = combined_pct - range_max
        else:
            range_penalty = 0.0

        categories = {leg["category"] for leg in legs}
        average_leg_score = sum(_candidate_score(leg, recipe, used_keys) for leg in legs) / len(legs)
        return (
            average_leg_score
            + len(categories) * 2.5
            - abs(combined_pct - target) * recipe.get("target_penalty", 1.2)
            - range_penalty * recipe.get("range_penalty", 8.0)
        )

    def _pick_combo_legs(recipe: dict, used_keys: set[str]) -> list[dict]:
        def find_best(min_prob: float) -> list[dict]:
            recipe["min_prob"] = min_prob
            pool = [
                c for c in candidates
                if c["_prob"] >= min_prob and c["odds"] >= 1.05
            ]
            best: tuple[float, tuple[dict, ...]] | None = None

            for size in range(recipe["min_legs"], recipe["max_legs"] + 1):
                for legs in itertools.combinations(pool, size):
                    if not _valid_leg_set(legs, recipe, used_keys):
                        continue
                    score = _set_score(legs, recipe, used_keys)
                    if best is None or score > best[0]:
                        best = (score, legs)

            return list(best[1]) if best else []

        original_min_prob = recipe["min_prob"]
        original_max_reused = recipe.get("max_reused_legs", 0)
        try:
            legs = find_best(original_min_prob)
            if legs:
                return legs
            legs = find_best(max(0.18, original_min_prob - 0.18))
            if legs:
                return legs
            if used_keys:
                recipe["max_reused_legs"] = 1
                return find_best(max(0.18, original_min_prob - 0.18))
            return []
        finally:
            recipe["min_prob"] = original_min_prob
            recipe["max_reused_legs"] = original_max_reused

    def _build_combo(recipe: dict, used_keys: set[str]) -> dict | None:
        legs = _pick_combo_legs(recipe, used_keys)
        if len(legs) < recipe["min_legs"]:
            return None

        combined_odds = 1.0
        combined_prob = 1.0
        for leg in legs:
            combined_odds *= leg["odds"]
            combined_prob *= leg["confidence"] / 100

        combined_odds = round(combined_odds, 2)
        combined_pct = round(combined_prob * 100, 1)
        edge = round(((combined_prob * combined_odds) - 1) * 100, 1)

        return {
            "id": recipe["id"],
            "profile": recipe["id"],
            "label": recipe["label"],
            "rationale": f"{recipe['rationale']} {availability_note}".strip(),
            "selections": [_clean_selection(leg) for leg in legs],
            "combined_odds": combined_odds,
            "combined_confidence": round(combined_pct),
            "combined_probability": combined_pct,
            "confidence_range": {
                "min": recipe["range_min"],
                "max": recipe["range_max"],
                "label": recipe["range_label"],
            },
            "edge": edge,
            "method": "poisson_xg_market_scoring",
            "source": "winamax_betclic" if has_bookmaker else "ai_model",
            "availability_impact": {
                "home_missing": home_missing,
                "away_missing": away_missing,
                "home_lineup_confirmed": home_lineup_confirmed,
                "away_lineup_confirmed": away_lineup_confirmed,
                "home_pressure": round(home_absence_pressure, 3),
                "away_pressure": round(away_absence_pressure, 3),
            },
        }

    combo_recipes = [
        {
            "id": "safe",
            "label": "66-100%",
            "range_label": "100% - 66%",
            "range_min": 66,
            "range_max": 100,
            "target_confidence": 78,
            "min_prob": 0.58,
            "min_legs": 2,
            "max_legs": min(2, max_selections),
            "prob_weight": 105.0,
            "edge_weight": 0.35,
            "odds_weight": -1.0,
            "profile_weight": 10.0,
            "real_odds_bonus": 3.0,
            "reuse_penalty": 14.0,
            "specificity_weight": 24.0,
            "generic_penalty": 18.0,
            "min_specific_legs": 1,
            "max_generic_legs": 1,
            "max_reused_legs": 0,
            "target_penalty": 1.5,
            "range_penalty": 12.0,
            "rationale": "Ticket haute confiance: la probabilite combinee vise la tranche 66-100%, sans conflit entre marches.",
            "category_limits": {**CATEGORY_LIMITS, "Buts": 2},
        },
        {
            "id": "balanced",
            "label": "33-66%",
            "range_label": "66% - 33%",
            "range_min": 33,
            "range_max": 66,
            "target_confidence": 50,
            "min_prob": 0.38,
            "min_legs": 2,
            "max_legs": min(2, max_selections),
            "prob_weight": 78.0,
            "edge_weight": 1.0,
            "odds_weight": 1.1,
            "profile_weight": 8.0,
            "real_odds_bonus": 4.0,
            "reuse_penalty": 10.0,
            "specificity_weight": 28.0,
            "generic_penalty": 16.0,
            "min_specific_legs": 1,
            "max_generic_legs": 1,
            "max_reused_legs": 0,
            "target_penalty": 1.3,
            "range_penalty": 10.0,
            "rationale": "Ticket intermediaire: il vise la tranche 33-66% en equilibrant confiance IA et rendement.",
            "category_limits": CATEGORY_LIMITS,
        },
        {
            "id": "bold",
            "label": "0-33%",
            "range_label": "33% - 0%",
            "range_min": 0,
            "range_max": 33,
            "target_confidence": 22,
            "min_prob": 0.24,
            "min_legs": 2,
            "max_legs": max(2, min(3, max_selections)),
            "prob_weight": 62.0,
            "edge_weight": 1.25,
            "odds_weight": 2.4,
            "profile_weight": 7.0,
            "real_odds_bonus": 5.0,
            "reuse_penalty": 7.0,
            "specificity_weight": 32.0,
            "generic_penalty": 14.0,
            "min_specific_legs": 2,
            "max_generic_legs": 1,
            "max_reused_legs": 0,
            "target_penalty": 1.0,
            "range_penalty": 8.0,
            "rationale": "Ticket rendement: il reste coherent avec le modele, mais sa probabilite combinee vise 0-33%.",
            "category_limits": CATEGORY_LIMITS,
        },
    ]

    combos: list[dict] = []
    used_keys: set[str] = set()
    seen_signatures: set[str] = set()
    for recipe in combo_recipes:
        combo = _build_combo(recipe, used_keys)
        if not combo:
            continue
        signature = "|".join(selection["key"] for selection in combo["selections"])
        if signature in seen_signatures:
            continue
        combos.append(combo)
        seen_signatures.add(signature)
        used_keys.update(selection["key"] for selection in combo["selections"])

    if not combos:
        return {
            "selections": [],
            "combined_odds": 1.0,
            "combined_confidence": 0,
            "source": "none",
            "profile": profile,
            "combos": [],
        }

    primary_combo = combos[1] if len(combos) > 1 else combos[0]

    return {
        "selections": primary_combo["selections"],
        "combined_odds": primary_combo["combined_odds"],
        "combined_confidence": primary_combo["combined_confidence"],
        "source": "winamax_betclic" if has_bookmaker else "ai_model",
        "profile": profile,
        "method": "poisson_xg_market_scoring",
        "combos": combos,
    }
# ============================================================
# Daily tips (also uses Poisson)
# ============================================================

def generate_daily_tips(
    matches_data: list[dict],
    max_tips: int = 10,
) -> list[dict]:
    """Generate diverse daily tips ranked by probability of passing."""
    tips = []

    for match in matches_data:
        probs = match.get("probs", {})
        stats = match.get("stats", {})
        home = match.get("homeTeam", "")
        away = match.get("awayTeam", "")
        competition = match.get("competition", "")
        date = match.get("date", "")

        home_xg = stats.get("predicted_home_goals", 1.3)
        away_xg = stats.get("predicted_away_goals", 1.1)
        M = _build_score_matrix(home_xg, away_xg)

        p1, pn, p2 = probs.get("p1", 33), probs.get("pn", 34), probs.get("p2", 33)

        # Compute all market probabilities
        markets = [
            ("Victoire domicile", "Résultat", p1 / 100),
            ("Victoire extérieur", "Résultat", p2 / 100),
            ("1 ou N (Double chance)", "Dbl Chance", (p1 + pn) / 100),
            ("N ou 2 (Double chance)", "Dbl Chance", (p2 + pn) / 100),
            ("Plus de 2.5 buts", "Goals", 1 - _matrix_prob(M, lambda h, a: h + a <= 2)),
            ("Moins de 2.5 buts", "Goals", _matrix_prob(M, lambda h, a: h + a <= 2)),
            ("Plus de 3.5 buts", "Goals", 1 - _matrix_prob(M, lambda h, a: h + a <= 3)),
            ("Les deux marquent", "BTTS", (1 - _poisson_cdf(0, home_xg)) * (1 - _poisson_cdf(0, away_xg))),
            ("Au moins 1 ne marque pas", "BTTS", 1 - (1 - _poisson_cdf(0, home_xg)) * (1 - _poisson_cdf(0, away_xg))),
            ("Clean sheet domicile", "Défense", _poisson_cdf(0, away_xg)),
            ("BTTS + Over 2.5", "Combo", _matrix_prob(M, lambda h, a: h > 0 and a > 0 and h + a > 2)),
            ("Victoire dom. sans encaisser", "Combo", _matrix_prob(M, lambda h, a: h > 0 and a == 0)),
            ("Domicile marque 2+", "Buts Équipe", 1 - _poisson_cdf(1, home_xg)),
            ("Extérieur marque 2+", "Buts Équipe", 1 - _poisson_cdf(1, away_xg)),
        ]

        for tip_label, category, p in markets:
            if p < 0.55:  # Only tips with >55% probability
                continue
            tips.append({
                "homeTeam": home, "awayTeam": away, "competition": competition,
                "date": date, "tip": tip_label, "tip_fr": tip_label,
                "category": category, "confidence": round(p * 100),
                "odds": max(1.01, _fair_odds(p)),
            })

    tips.sort(key=lambda x: x["confidence"], reverse=True)

    # Deduplicate: max 2 tips per category across all matches
    final = []
    cat_counts: dict[str, int] = {}
    for t in tips:
        cat = t["category"]
        if cat_counts.get(cat, 0) >= 2:
            continue
        final.append(t)
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
        if len(final) >= max_tips:
            break

    return final
