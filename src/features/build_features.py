"""
src/features/build_features.py
Feature Engineering Avancé pour le Deep Learning.

Features calculées :
  1. Forme générale (rolling 5 matchs) — points, buts marqués, buts encaissés
  2. Elo Rating System (K=32, initial=1500)
  3. Forme spécifique domicile / extérieur
  4. Indice de fatigue (jours de repos depuis le dernier match)
  5. Proxy xG (tirs cadrés rolling 5 matchs)

Règle absolue : .shift(1) partout pour éviter le Data Leakage.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.database import get_session
from src.database.models import MatchRaw, MatchFeature

logger: logging.Logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

ROLLING_WINDOW: int = 5

# ============================================================
# Constantes Elo
# ============================================================
ELO_K: int = 32           # Sensibilité (standard FIFA)
ELO_INITIAL: float = 1500.0  # Rating de départ


# ============================================================
# 1. Chargement des données
# ============================================================
def load_matches_as_dataframe(session: Session) -> pd.DataFrame:
    """Charge tous les matchs depuis matches_raw avec les stats nécessaires."""
    stmt = (
        select(
            MatchRaw.id,
            MatchRaw.date,
            MatchRaw.home_team_id,
            MatchRaw.away_team_id,
            MatchRaw.fthg,
            MatchRaw.ftag,
            MatchRaw.ftr,
            MatchRaw.home_xg,
            MatchRaw.away_xg,
            MatchRaw.home_xpts,
            MatchRaw.away_xpts,
            MatchRaw.hs,
            MatchRaw.as_shots,
            MatchRaw.hst,
            MatchRaw.ast,
        )
        .order_by(MatchRaw.date)
    )

    result = session.execute(stmt)
    rows = result.fetchall()

    df: pd.DataFrame = pd.DataFrame(
        rows,
        columns=[
            "match_id", "date", "home_team_id", "away_team_id",
            "fthg", "ftag", "ftr", "home_xg", "away_xg", "home_xpts", "away_xpts",
            "hs", "as_shots", "hst", "ast",
        ],
    )

    # Conversion date en datetime pour les calculs de jours de repos
    df["date"] = pd.to_datetime(df["date"])

    logger.info(f"Chargement de {len(df)} matchs depuis matches_raw")
    return df


def compute_points(fthg: int, ftag: int, is_home: bool) -> int:
    """Calcule les points obtenus par une équipe dans un match (3/1/0)."""
    if is_home:
        return 3 if fthg > ftag else (1 if fthg == ftag else 0)
    else:
        return 3 if ftag > fthg else (1 if fthg == ftag else 0)


# ============================================================
# 2. Système Elo
# ============================================================
def compute_elo_ratings(df: pd.DataFrame) -> dict[int, dict[int, float]]:
    """
    Calcule les ratings Elo de chaque équipe match par match.
    Retourne un dict {match_id: {home_team_id: elo_before, away_team_id: elo_before}}.

    Le rating est calculé AVANT le match (pas de leakage).
    """
    elo_ratings: dict[int, float] = {}  # team_id -> current elo
    match_elos: dict[int, dict[int, float]] = {}  # match_id -> {team_id: elo_before}

    for _, row in df.iterrows():
        match_id: int = row["match_id"]
        home_id: int = row["home_team_id"]
        away_id: int = row["away_team_id"]

        # Initialisation si première apparition
        if home_id not in elo_ratings:
            elo_ratings[home_id] = ELO_INITIAL
        if away_id not in elo_ratings:
            elo_ratings[away_id] = ELO_INITIAL

        # Sauvegarder l'Elo AVANT le match (no leakage)
        home_elo: float = elo_ratings[home_id]
        away_elo: float = elo_ratings[away_id]
        match_elos[match_id] = {home_id: home_elo, away_id: away_elo}

        # Calcul du résultat attendu (formule Elo)
        expected_home: float = 1.0 / (1.0 + 10.0 ** ((away_elo - home_elo) / 400.0))
        expected_away: float = 1.0 - expected_home

        # Résultat réel
        ftr: str = row["ftr"]
        if ftr == "H":
            actual_home, actual_away = 1.0, 0.0
        elif ftr == "D":
            actual_home, actual_away = 0.5, 0.5
        else:  # A
            actual_home, actual_away = 0.0, 1.0

        # Mise à jour des Elo APRÈS le match
        elo_ratings[home_id] = home_elo + ELO_K * (actual_home - expected_home)
        elo_ratings[away_id] = away_elo + ELO_K * (actual_away - expected_away)

    logger.info(f"Elo calculé pour {len(match_elos)} matchs, {len(elo_ratings)} équipes")
    return match_elos


# ============================================================
# 3. Forme générale (rolling 5 matchs)
# ============================================================
def compute_team_general_form(df: pd.DataFrame, team_id: int) -> pd.DataFrame:
    """Rolling stats généraux sur les 5 derniers matchs (tous terrains)."""
    home_mask = df["home_team_id"] == team_id
    away_mask = df["away_team_id"] == team_id
    team_df: pd.DataFrame = df[home_mask | away_mask].copy().sort_values("date").reset_index(drop=True)

    if team_df.empty:
        return pd.DataFrame()

    points: list[int] = []
    goals_scored: list[int] = []
    goals_conceded: list[int] = []
    xg: list[float] = []
    xpts: list[float] = []
    shots_on_target: list[float] = []
    shots_conceded_on_target: list[float] = []

    for _, row in team_df.iterrows():
        is_home: bool = row["home_team_id"] == team_id
        points.append(compute_points(row["fthg"], row["ftag"], is_home))

        if is_home:
            goals_scored.append(row["fthg"])
            goals_conceded.append(row["ftag"])
            xg.append(row["home_xg"] if pd.notna(row["home_xg"]) else np.nan)
            xpts.append(row["home_xpts"] if pd.notna(row["home_xpts"]) else np.nan)
            shots_on_target.append(row["hst"] if pd.notna(row["hst"]) else np.nan)
            shots_conceded_on_target.append(row["ast"] if pd.notna(row["ast"]) else np.nan)
        else:
            goals_scored.append(row["ftag"])
            goals_conceded.append(row["fthg"])
            xg.append(row["away_xg"] if pd.notna(row["away_xg"]) else np.nan)
            xpts.append(row["away_xpts"] if pd.notna(row["away_xpts"]) else np.nan)
            shots_on_target.append(row["ast"] if pd.notna(row["ast"]) else np.nan)
            shots_conceded_on_target.append(row["hst"] if pd.notna(row["hst"]) else np.nan)

    team_df["points"] = points
    team_df["goals_scored"] = goals_scored
    team_df["goals_conceded"] = goals_conceded
    team_df["xg"] = xg
    team_df["xpts"] = xpts
    team_df["sot"] = shots_on_target
    team_df["sot_conceded"] = shots_conceded_on_target
    
    # Imputation pour les NaN pré-2014 : Remplir avec la moyenne historique de l'équipe
    if team_df["xg"].isnull().any():
        mean_xg = team_df["xg"].mean()
        # Fallback supplémentaire (1.1 est environ la moyenne globale d'un match de foot)
        if pd.isna(mean_xg): mean_xg = 1.1 
        team_df["xg"].fillna(mean_xg, inplace=True)
        
    if team_df["xpts"].isnull().any():
        mean_xpts = team_df["xpts"].mean()
        if pd.isna(mean_xpts): mean_xpts = 1.1
        team_df["xpts"].fillna(mean_xpts, inplace=True)

    # Rolling avec .shift(1)
    for col, out_col in [
        ("points", "pts_last_5"),
        ("goals_scored", "goals_scored_last_5"),
        ("goals_conceded", "goals_conceded_last_5"),
        ("xg", "xg_last_5"),
        ("xpts", "xpts_last_5"),
        ("sot", "sot_last_5"),
        ("sot_conceded", "sot_conceded_last_5"),
    ]:
        team_df[out_col] = (
            team_df[col]
            .shift(1)
            .rolling(window=ROLLING_WINDOW, min_periods=1)
            .mean()
        )

    return team_df[["match_id", "pts_last_5", "goals_scored_last_5",
                     "goals_conceded_last_5", "xg_last_5", "xpts_last_5",
                     "sot_last_5", "sot_conceded_last_5"]]


# ============================================================
# 4. Forme spécifique domicile / extérieur
# ============================================================
def compute_team_home_form(df: pd.DataFrame, team_id: int) -> pd.DataFrame:
    """Rolling points sur les 5 derniers matchs joués À DOMICILE uniquement."""
    home_df: pd.DataFrame = df[df["home_team_id"] == team_id].copy().sort_values("date").reset_index(drop=True)

    if home_df.empty:
        return pd.DataFrame()

    home_df["points"] = home_df.apply(
        lambda r: compute_points(r["fthg"], r["ftag"], True), axis=1
    )

    home_df["pts_last_5_at_home"] = (
        home_df["points"]
        .shift(1)
        .rolling(window=ROLLING_WINDOW, min_periods=1)
        .mean()
    )

    return home_df[["match_id", "pts_last_5_at_home"]]


def compute_team_away_form(df: pd.DataFrame, team_id: int) -> pd.DataFrame:
    """Rolling points sur les 5 derniers matchs joués À L'EXTÉRIEUR uniquement."""
    away_df: pd.DataFrame = df[df["away_team_id"] == team_id].copy().sort_values("date").reset_index(drop=True)

    if away_df.empty:
        return pd.DataFrame()

    away_df["points"] = away_df.apply(
        lambda r: compute_points(r["fthg"], r["ftag"], False), axis=1
    )

    away_df["pts_last_5_away"] = (
        away_df["points"]
        .shift(1)
        .rolling(window=ROLLING_WINDOW, min_periods=1)
        .mean()
    )

    return away_df[["match_id", "pts_last_5_away"]]


# ============================================================
# 4b. Série d'invincibilité (unbeaten streak)
# ============================================================
def compute_unbeaten_streak(df: pd.DataFrame, team_id: int) -> pd.DataFrame:
    """Calcule la série de matchs sans défaite avant chaque match."""
    home_mask = df["home_team_id"] == team_id
    away_mask = df["away_team_id"] == team_id
    team_df: pd.DataFrame = df[home_mask | away_mask].copy().sort_values("date").reset_index(drop=True)

    if team_df.empty:
        return pd.DataFrame()

    streaks: list[int] = []
    current_streak: int = 0

    for _, row in team_df.iterrows():
        # Stocker le streak AVANT le match (no leakage)
        streaks.append(current_streak)

        is_home: bool = row["home_team_id"] == team_id
        if is_home:
            lost = row["fthg"] < row["ftag"]
        else:
            lost = row["ftag"] < row["fthg"]

        if lost:
            current_streak = 0
        else:
            current_streak += 1

    team_df["unbeaten_streak"] = streaks
    return team_df[["match_id", "unbeaten_streak"]]


# ============================================================
# 4c. Momentum (forme récente vs forme moyenne)
# ============================================================
def compute_momentum(df: pd.DataFrame, team_id: int) -> pd.DataFrame:
    """Ratio pts_last_3 / pts_last_5 pour détecter les tendances."""
    home_mask = df["home_team_id"] == team_id
    away_mask = df["away_team_id"] == team_id
    team_df: pd.DataFrame = df[home_mask | away_mask].copy().sort_values("date").reset_index(drop=True)

    if team_df.empty:
        return pd.DataFrame()

    points: list[int] = []
    for _, row in team_df.iterrows():
        is_home: bool = row["home_team_id"] == team_id
        points.append(compute_points(row["fthg"], row["ftag"], is_home))

    team_df["points"] = points

    pts_3 = team_df["points"].shift(1).rolling(window=3, min_periods=1).mean()
    pts_5 = team_df["points"].shift(1).rolling(window=5, min_periods=1).mean()

    # Momentum = ratio forme courte / forme longue (>1 = en hausse, <1 = en baisse)
    team_df["momentum"] = (pts_3 / pts_5.replace(0, 1.0)).fillna(1.0)

    return team_df[["match_id", "momentum"]]


# ============================================================
# 5. Indice de fatigue (jours de repos)
# ============================================================
def compute_days_rest(df: pd.DataFrame, team_id: int) -> pd.DataFrame:
    """Calcule le nombre de jours depuis le dernier match pour une équipe."""
    home_mask = df["home_team_id"] == team_id
    away_mask = df["away_team_id"] == team_id
    team_df: pd.DataFrame = df[home_mask | away_mask].copy().sort_values("date").reset_index(drop=True)

    if team_df.empty:
        return pd.DataFrame()

    # Différence en jours entre le match courant et le précédent
    team_df["days_rest"] = team_df["date"].diff().dt.total_seconds() / 86400.0

    return team_df[["match_id", "days_rest"]]


# ============================================================
# 6. Construction complète des features
# ============================================================
# ============================================================
# 5b. Confrontations directes (H2H) — calcul historique
# ============================================================
def compute_h2h_features(df: pd.DataFrame) -> dict[int, dict]:
    """
    Calcule les stats H2H pour chaque match en utilisant UNIQUEMENT les matchs antérieurs.
    Retourne {match_id: {h2h_dominance, h2h_avg_goals, h2h_matches}}.

    Fonctionne en une seule passe chronologique : O(n).
    """
    # pair_history stocke les confrontations passées pour chaque paire d'équipes
    # Clé : frozenset({home_id, away_id}) — indépendant de l'ordre
    pair_history: dict[frozenset, list[dict]] = {}
    h2h_features: dict[int, dict] = {}

    for _, row in df.sort_values("date").iterrows():
        match_id = row["match_id"]
        home_id = row["home_team_id"]
        away_id = row["away_team_id"]
        pair_key = frozenset({home_id, away_id})

        # Récupérer l'historique AVANT ce match
        history = pair_history.get(pair_key, [])

        if len(history) == 0:
            h2h_features[match_id] = {
                "h2h_dominance": 0.0,
                "h2h_avg_goals": 2.5,  # Fallback moyenne globale
                "h2h_matches": 0,
            }
        else:
            home_wins = sum(1 for h in history if h["winner"] == home_id)
            away_wins = sum(1 for h in history if h["winner"] == away_id)
            total = len(history)
            total_goals = sum(h["total_goals"] for h in history)

            h2h_features[match_id] = {
                "h2h_dominance": (home_wins - away_wins) / total,
                "h2h_avg_goals": total_goals / total,
                "h2h_matches": min(total, 10),  # Cap à 10 pour limiter l'amplitude
            }

        # Ajouter ce match à l'historique de la paire
        ftr = row["ftr"]
        if ftr == "H":
            winner = home_id
        elif ftr == "A":
            winner = away_id
        else:
            winner = None

        pair_history.setdefault(pair_key, []).append({
            "winner": winner,
            "total_goals": (row["fthg"] or 0) + (row["ftag"] or 0),
        })

    logger.info(f"H2H calculé pour {len(h2h_features)} matchs, {len(pair_history)} paires d'équipes")
    return h2h_features


def build_all_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Construit TOUTES les features pour chaque match :
    - Forme générale (rolling 5)
    - Elo ratings
    - Forme spécifique dom/ext
    - Jours de repos
    - Proxy xG (tirs cadrés rolling 5)
    - Confrontations directes (H2H)
    """
    all_team_ids: set[int] = set(df["home_team_id"].unique()) | set(df["away_team_id"].unique())
    logger.info(f"Calcul des features avancées pour {len(all_team_ids)} équipes")

    # --- Elo (global, une seule passe chronologique) ---
    match_elos: dict[int, dict[int, float]] = compute_elo_ratings(df)

    # --- H2H (global, une seule passe chronologique) ---
    h2h_features: dict[int, dict] = compute_h2h_features(df)

    # --- Stats par équipe ---
    general_stats: dict[int, pd.DataFrame] = {}
    home_form_stats: dict[int, pd.DataFrame] = {}
    away_form_stats: dict[int, pd.DataFrame] = {}
    rest_stats: dict[int, pd.DataFrame] = {}
    streak_stats: dict[int, pd.DataFrame] = {}
    momentum_stats: dict[int, pd.DataFrame] = {}

    for team_id in all_team_ids:
        general_stats[team_id] = compute_team_general_form(df, team_id)
        home_form_stats[team_id] = compute_team_home_form(df, team_id)
        away_form_stats[team_id] = compute_team_away_form(df, team_id)
        rest_stats[team_id] = compute_days_rest(df, team_id)
        streak_stats[team_id] = compute_unbeaten_streak(df, team_id)
        momentum_stats[team_id] = compute_momentum(df, team_id)

    logger.info("Stats par équipe calculées, assemblage des features...")

    # --- Assemblage final ---
    features_rows: list[dict] = []

    for _, row in df.iterrows():
        match_id: int = row["match_id"]
        home_id: int = row["home_team_id"]
        away_id: int = row["away_team_id"]

        feature: dict = {"match_id": match_id}

        # ---- Elo ----
        elo_data: dict = match_elos.get(match_id, {})
        home_elo: Optional[float] = elo_data.get(home_id)
        away_elo: Optional[float] = elo_data.get(away_id)
        feature["home_elo"] = home_elo
        feature["away_elo"] = away_elo
        feature["elo_diff"] = (home_elo - away_elo) if home_elo and away_elo else None

        # ---- Forme générale (home team) ----
        home_gen = general_stats[home_id]
        if not home_gen.empty:
            hr = home_gen[home_gen["match_id"] == match_id]
            if not hr.empty:
                feature["home_pts_last_5"] = hr.iloc[0]["pts_last_5"]
                feature["home_goals_scored_last_5"] = hr.iloc[0]["goals_scored_last_5"]
                feature["home_goals_conceded_last_5"] = hr.iloc[0]["goals_conceded_last_5"]
                feature["home_xg_last_5"] = hr.iloc[0]["xg_last_5"]
                feature["home_xpts_last_5"] = hr.iloc[0]["xpts_last_5"]
                feature["home_sot_last_5"] = hr.iloc[0]["sot_last_5"]
                feature["home_sot_conceded_last_5"] = hr.iloc[0]["sot_conceded_last_5"]
            else:
                feature["home_pts_last_5"] = None
                feature["home_goals_scored_last_5"] = None
                feature["home_goals_conceded_last_5"] = None
                feature["home_xg_last_5"] = None
                feature["home_xpts_last_5"] = None
                feature["home_sot_last_5"] = None
                feature["home_sot_conceded_last_5"] = None
        else:
            feature["home_pts_last_5"] = None
            feature["home_goals_scored_last_5"] = None
            feature["home_goals_conceded_last_5"] = None
            feature["home_xg_last_5"] = None
            feature["home_xpts_last_5"] = None
            feature["home_sot_last_5"] = None
            feature["home_sot_conceded_last_5"] = None

        # ---- Forme générale (away team) ----
        away_gen = general_stats[away_id]
        if not away_gen.empty:
            ar = away_gen[away_gen["match_id"] == match_id]
            if not ar.empty:
                feature["away_pts_last_5"] = ar.iloc[0]["pts_last_5"]
                feature["away_goals_scored_last_5"] = ar.iloc[0]["goals_scored_last_5"]
                feature["away_goals_conceded_last_5"] = ar.iloc[0]["goals_conceded_last_5"]
                feature["away_xg_last_5"] = ar.iloc[0]["xg_last_5"]
                feature["away_xpts_last_5"] = ar.iloc[0]["xpts_last_5"]
                feature["away_sot_last_5"] = ar.iloc[0]["sot_last_5"]
                feature["away_sot_conceded_last_5"] = ar.iloc[0]["sot_conceded_last_5"]
            else:
                feature["away_pts_last_5"] = None
                feature["away_goals_scored_last_5"] = None
                feature["away_goals_conceded_last_5"] = None
                feature["away_xg_last_5"] = None
                feature["away_xpts_last_5"] = None
                feature["away_sot_last_5"] = None
                feature["away_sot_conceded_last_5"] = None
        else:
            feature["away_pts_last_5"] = None
            feature["away_goals_scored_last_5"] = None
            feature["away_goals_conceded_last_5"] = None
            feature["away_xg_last_5"] = None
            feature["away_xpts_last_5"] = None
            feature["away_sot_last_5"] = None
            feature["away_sot_conceded_last_5"] = None

        # ---- Forme spécifique domicile ----
        home_hf = home_form_stats[home_id]
        if not home_hf.empty:
            hhr = home_hf[home_hf["match_id"] == match_id]
            feature["home_pts_last_5_at_home"] = hhr.iloc[0]["pts_last_5_at_home"] if not hhr.empty else None
        else:
            feature["home_pts_last_5_at_home"] = None

        # ---- Forme spécifique extérieur ----
        away_af = away_form_stats[away_id]
        if not away_af.empty:
            aar = away_af[away_af["match_id"] == match_id]
            feature["away_pts_last_5_away"] = aar.iloc[0]["pts_last_5_away"] if not aar.empty else None
        else:
            feature["away_pts_last_5_away"] = None

        # ---- Jours de repos (home) ----
        home_rest = rest_stats[home_id]
        if not home_rest.empty:
            hrd = home_rest[home_rest["match_id"] == match_id]
            feature["home_days_rest"] = hrd.iloc[0]["days_rest"] if not hrd.empty else None
        else:
            feature["home_days_rest"] = None

        # ---- Jours de repos (away) ----
        away_rest = rest_stats[away_id]
        if not away_rest.empty:
            ard = away_rest[away_rest["match_id"] == match_id]
            feature["away_days_rest"] = ard.iloc[0]["days_rest"] if not ard.empty else None
        else:
            feature["away_days_rest"] = None

        # ---- Série d'invincibilité ----
        home_streak = streak_stats[home_id]
        if not home_streak.empty:
            hsd = home_streak[home_streak["match_id"] == match_id]
            feature["home_unbeaten_streak"] = hsd.iloc[0]["unbeaten_streak"] if not hsd.empty else None
        else:
            feature["home_unbeaten_streak"] = None

        away_streak = streak_stats[away_id]
        if not away_streak.empty:
            asd = away_streak[away_streak["match_id"] == match_id]
            feature["away_unbeaten_streak"] = asd.iloc[0]["unbeaten_streak"] if not asd.empty else None
        else:
            feature["away_unbeaten_streak"] = None

        # ---- Momentum ----
        home_mom = momentum_stats[home_id]
        if not home_mom.empty:
            hmd = home_mom[home_mom["match_id"] == match_id]
            feature["home_momentum"] = hmd.iloc[0]["momentum"] if not hmd.empty else None
        else:
            feature["home_momentum"] = None

        away_mom = momentum_stats[away_id]
        if not away_mom.empty:
            amd = away_mom[away_mom["match_id"] == match_id]
            feature["away_momentum"] = amd.iloc[0]["momentum"] if not amd.empty else None
        else:
            feature["away_momentum"] = None

        # ---- H2H ----
        h2h = h2h_features.get(match_id, {})
        feature["h2h_dominance"] = h2h.get("h2h_dominance", 0.0)
        feature["h2h_avg_goals"] = h2h.get("h2h_avg_goals", 2.5)
        feature["h2h_matches"] = h2h.get("h2h_matches", 0)

        features_rows.append(feature)

    features_df: pd.DataFrame = pd.DataFrame(features_rows)
    logger.info(f"Features avancées calculées pour {len(features_df)} matchs ({len(features_df.columns)} colonnes)")
    return features_df


# ============================================================
# 7. Sauvegarde en base
# ============================================================
def save_features_to_db(session: Session, features_df: pd.DataFrame) -> int:
    """Insère les features calculées dans la table match_features (batch upsert)."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    def safe_float(val) -> Optional[float]:
        return float(val) if pd.notna(val) else None

    rows_to_insert: list[dict] = []
    for _, row in features_df.iterrows():
        if pd.isna(row.get("home_pts_last_5")) and pd.isna(row.get("away_pts_last_5")) and pd.isna(row.get("elo_diff")):
            continue
        rows_to_insert.append({
            "match_id": int(row["match_id"]),
            "home_pts_last_5": safe_float(row.get("home_pts_last_5")),
            "home_goals_scored_last_5": safe_float(row.get("home_goals_scored_last_5")),
            "home_goals_conceded_last_5": safe_float(row.get("home_goals_conceded_last_5")),
            "away_pts_last_5": safe_float(row.get("away_pts_last_5")),
            "away_goals_scored_last_5": safe_float(row.get("away_goals_scored_last_5")),
            "away_goals_conceded_last_5": safe_float(row.get("away_goals_conceded_last_5")),
            "home_elo": safe_float(row.get("home_elo")),
            "away_elo": safe_float(row.get("away_elo")),
            "elo_diff": safe_float(row.get("elo_diff")),
            "home_pts_last_5_at_home": safe_float(row.get("home_pts_last_5_at_home")),
            "away_pts_last_5_away": safe_float(row.get("away_pts_last_5_away")),
            "home_days_rest": safe_float(row.get("home_days_rest")),
            "away_days_rest": safe_float(row.get("away_days_rest")),
            "home_xg_last_5": safe_float(row.get("home_xg_last_5")),
            "away_xg_last_5": safe_float(row.get("away_xg_last_5")),
            "home_xpts_last_5": safe_float(row.get("home_xpts_last_5")),
            "away_xpts_last_5": safe_float(row.get("away_xpts_last_5")),
            "home_unbeaten_streak": safe_float(row.get("home_unbeaten_streak")),
            "away_unbeaten_streak": safe_float(row.get("away_unbeaten_streak")),
            "home_momentum": safe_float(row.get("home_momentum")),
            "away_momentum": safe_float(row.get("away_momentum")),
            "home_sot_last_5": safe_float(row.get("home_sot_last_5")),
            "away_sot_last_5": safe_float(row.get("away_sot_last_5")),
            "home_sot_conceded_last_5": safe_float(row.get("home_sot_conceded_last_5")),
            "away_sot_conceded_last_5": safe_float(row.get("away_sot_conceded_last_5")),
            "h2h_dominance": safe_float(row.get("h2h_dominance")),
            "h2h_avg_goals": safe_float(row.get("h2h_avg_goals")),
            "h2h_matches": safe_float(row.get("h2h_matches")),
        })

    # Batch upsert par lots de 500
    BATCH_SIZE = 500
    inserted = 0
    for i in range(0, len(rows_to_insert), BATCH_SIZE):
        batch = rows_to_insert[i:i + BATCH_SIZE]
        stmt = pg_insert(MatchFeature).values(batch)
        stmt = stmt.on_conflict_do_update(
            index_elements=["match_id"],
            set_={col: stmt.excluded[col] for col in batch[0] if col != "match_id"},
        )
        session.execute(stmt)
        session.commit()
        inserted += len(batch)
        logger.info(f"  Batch {i // BATCH_SIZE + 1} : {inserted}/{len(rows_to_insert)} features insérées")

    logger.info(f"{inserted} features insérées/mises à jour dans match_features")
    return inserted


# ============================================================
# 8. Point d'entrée
# ============================================================
def run_feature_engineering() -> bool:
    """Point d'entrée principal du feature engineering avancé."""
    logger.info("=" * 60)
    logger.info("DÉMARRAGE DU FEATURE ENGINEERING AVANCÉ")
    logger.info("  → Elo + Forme Dom/Ext + Fatigue + xG Proxy")
    logger.info("=" * 60)

    session: Session = get_session()

    try:
        df: pd.DataFrame = load_matches_as_dataframe(session)

        if df.empty:
            logger.warning("Aucun match trouvé dans matches_raw. Exécutez d'abord l'ingestion.")
            return False

        features_df: pd.DataFrame = build_all_features(df)
        save_features_to_db(session, features_df)

        logger.info("=" * 60)
        logger.info("FEATURE ENGINEERING AVANCÉ TERMINÉ AVEC SUCCÈS")
        logger.info("=" * 60)
        return True

    except Exception as e:
        logger.error(f"Erreur fatale durant le feature engineering : {e}", exc_info=True)
        session.rollback()
        return False

    finally:
        session.close()


if __name__ == "__main__":
    run_feature_engineering()
