"""
src/features/bet_builder.py
AI Bet Builder v2 — Poisson-based per-match analysis.
Generates diverse, high-probability bet combinations unique to each match profile.
"""

import logging
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
    total_xg = home_xg + away_xg

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
        ("home_win", "Victoire domicile", "Résultat", "home_win", 0.45),
        ("away_win", "Victoire extérieur", "Résultat", "away_win", 0.45),
        ("draw", "Match nul", "Résultat", "draw", 0.34),
        ("dc_home", "1 ou N (Double chance)", "Double Chance", "dc_home", 0.74),
        ("dc_away", "N ou 2 (Double chance)", "Double Chance", "dc_away", 0.74),
        ("over_15", "Plus de 1.5 buts", "Buts", "over_15", 0.72),
        ("over_25", "Plus de 2.5 buts", "Buts", "over_25", 0.55),
        ("over_35", "Plus de 3.5 buts", "Buts", "over_35", 0.40),
        ("under_25", "Moins de 2.5 buts", "Buts", "under_25", 0.50),
        ("under_35", "Moins de 3.5 buts", "Buts", "under_35", 0.70),
        ("under_15", "Moins de 1.5 buts", "Buts", "under_15", 0.30),
        ("home_over_05", "Domicile marque au moins 1", "Buts Équipe", "home_over_05", 0.65),
        ("home_over_15", "Domicile marque 2+", "Buts Équipe", "home_over_15", 0.35),
        ("away_over_05", "Extérieur marque au moins 1", "Buts Équipe", "away_over_05", 0.55),
        ("away_over_15", "Extérieur marque 2+", "Buts Équipe", "away_over_15", 0.30),
        ("btts_yes", "Les deux marquent", "BTTS", "btts_yes", 0.50),
        ("btts_no", "Au moins une équipe ne marque pas", "BTTS", "btts_no", 0.45),
        ("home_cs", "Clean sheet domicile", "Défense", "home_cs", 0.30),
        ("away_cs", "Clean sheet extérieur", "Défense", "away_cs", 0.25),
        ("home_win_to_nil", "Victoire dom. sans encaisser", "Combo", "home_win_to_nil", 0.20),
        ("away_win_to_nil", "Victoire ext. sans encaisser", "Combo", "away_win_to_nil", 0.15),
        ("btts_over_25", "BTTS + Plus de 2.5", "Combo", "btts_over_25", 0.35),
        ("home_win_over_15", "Victoire dom. + Plus de 1.5", "Combo", "home_win_over_15", 0.35),
        ("away_win_over_15", "Victoire ext. + Plus de 1.5", "Combo", "away_win_over_15", 0.25),
        ("goals_0_1", "0 ou 1 but dans le match", "Fourchette", "goals_0_1", 0.20),
        ("goals_2_3", "2 ou 3 buts dans le match", "Fourchette", "goals_2_3", 0.48),
        ("goals_4_plus", "4 buts ou plus", "Fourchette", "goals_4_plus", 0.25),
    ]

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
        elif key in ("over_15", "over_25", "over_35"):
            point = {"over_15": 1.5, "over_25": 2.5, "over_35": 3.5}[key]
            bm_odds, bm_name = _totals_odds(totals_bk, point)
            all_odds = _all_totals_odds(totals_bk, point)
        elif key in ("btts_yes",):
            bm_odds, bm_name = _best_bookmaker_odds(btts_bk, "yes")
            all_odds = _all_bookmaker_odds_for_market(btts_bk, "yes")
        elif key in ("btts_no",):
            bm_odds, bm_name = _best_bookmaker_odds(btts_bk, "no")
            all_odds = _all_bookmaker_odds_for_market(btts_bk, "no")

        odds_val = bm_odds if bm_odds > 0 else _fair_odds(p)
        odds_val = max(1.01, min(30.0, odds_val))

        candidates.append({
            "key": key,
            "label": key.replace("_", " ").title(),
            "label_fr": label_fr,
            "category": category,
            "confidence": round(p * 100),
            "odds": odds_val,
            "bookmaker": bm_name,
            "all_odds": all_odds,
            "_prob": p,         # internal, for sorting
            "_profile": profile,
        })

    # Sort by probability descending (highest chance of passing first)
    candidates.sort(key=lambda x: x["_prob"], reverse=True)

    # ============================================================
    # Smart selection: pick diverse, non-redundant, high-probability bets
    # ============================================================
    CONFLICTS: dict[str, set[str]] = {
        "home_win": {"away_win", "draw", "dc_away", "away_win_to_nil", "away_cs", "away_win_over_15"},
        "away_win": {"home_win", "draw", "dc_home", "home_win_to_nil", "home_cs", "home_win_over_15"},
        "draw": {"home_win", "away_win", "dc_12", "home_win_to_nil", "away_win_to_nil",
                 "home_win_over_15", "away_win_over_15"},
        "dc_home": {"dc_away", "away_win", "away_win_to_nil", "away_win_over_15"},
        "dc_away": {"dc_home", "home_win", "home_win_to_nil", "home_win_over_15"},
        "dc_12": {"draw"},
        # Over/Under conflicts
        "over_05": {"under_15", "goals_0_1"},
        "over_15": {"under_15", "goals_0_1"},
        "over_25": {"under_25", "under_15", "goals_0_1"},
        "over_35": {"under_35", "under_25", "under_15", "goals_0_1", "goals_2_3"},
        "under_25": {"over_25", "over_35", "goals_4_plus", "btts_over_25"},
        "under_35": {"over_35", "goals_4_plus"},
        "under_15": {"over_15", "over_25", "over_35", "btts_yes", "btts_over_25",
                     "goals_2_3", "goals_4_plus"},
        # BTTS conflicts
        "btts_yes": {"btts_no", "home_cs", "away_cs", "home_win_to_nil", "away_win_to_nil", "under_15"},
        "btts_no": {"btts_yes", "btts_over_25"},
        # Team goals
        "home_over_05": {"away_cs"},
        "home_over_15": {"away_cs"},
        "away_over_05": {"home_cs"},
        "away_over_15": {"home_cs"},
        # Clean sheet
        "home_cs": {"away_over_05", "away_over_15", "btts_yes", "btts_over_25"},
        "away_cs": {"home_over_05", "home_over_15", "btts_yes", "btts_over_25"},
        # Combos
        "home_win_to_nil": {"away_win", "draw", "btts_yes", "away_over_05"},
        "away_win_to_nil": {"home_win", "draw", "btts_yes", "home_over_05"},
        "btts_over_25": {"btts_no", "under_25", "under_15", "home_cs", "away_cs"},
        "home_win_over_15": {"away_win", "draw", "dc_away"},
        "away_win_over_15": {"home_win", "draw", "dc_home"},
        # Ranges
        "goals_0_1": {"over_15", "over_25", "over_35", "goals_2_3", "goals_4_plus"},
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

    # Apply sort: boosted candidates first (still sorted by prob within each group)
    boosted_cands = [c for c in candidates if c["key"] in boosted]
    other_cands = [c for c in candidates if c["key"] not in boosted]
    ordered = boosted_cands + other_cands

    selections: list[dict] = []
    selected_keys: set[str] = set()
    cat_counts: dict[str, int] = {}

    for c in ordered:
        if len(selections) >= max_selections:
            break
        key = c["key"]

        # Skip if blocked by conflict
        blocked = CONFLICTS.get(key, set())
        if blocked & selected_keys:
            continue

        # Skip if category full
        cat = c["category"]
        limit = CATEGORY_LIMITS.get(cat, 2)
        if cat_counts.get(cat, 0) >= limit:
            continue

        # Skip trivial bets (>95% prob, odds < 1.08) — boring, no value
        if c["_prob"] > 0.95 and c["odds"] < 1.08:
            continue

        selections.append(c)
        selected_keys.add(key)
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    # Clean internal keys
    for s in selections:
        s.pop("_prob", None)
        s.pop("_profile", None)

    if not selections:
        return {"selections": [], "combined_odds": 1.0, "combined_confidence": 0, "source": "none"}

    combined_odds = 1.0
    for s in selections:
        combined_odds *= s["odds"]
    combined_odds = round(combined_odds, 2)

    combined_conf = 1.0
    for s in selections:
        combined_conf *= (s["confidence"] / 100)
    combined_pct = round(combined_conf * 100)

    return {
        "selections": selections,
        "combined_odds": combined_odds,
        "combined_confidence": combined_pct,
        "source": "winamax_betclic" if has_bookmaker else "ai_model",
        "profile": profile,
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
