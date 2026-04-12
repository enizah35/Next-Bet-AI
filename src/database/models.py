"""
src/database/models.py
Modèles SQLAlchemy pour la base de données Next-Bet-AI.
Tables : teams, matches_raw, match_features
"""

import enum
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Boolean,
    ForeignKey,
    UniqueConstraint,
    Enum,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Classe de base déclarative SQLAlchemy 2.0."""
    pass


class SubscriptionTier(str, enum.Enum):
    NONE = "none"
    LIGUE1 = "ligue1"
    PL = "pl"
    ULTIMATE = "ultimate"


class Profile(Base):
    """Profil utilisateur pour la gestion des abonnements et des essais."""
    __tablename__ = "profiles"

    id: str = Column(String(36), primary_key=True)  # UUID de Supabase Auth
    subscription_tier: str = Column(String(20), default="none")
    billing_cycle: str = Column(String(20), nullable=True) # 'monthly' | 'yearly'
    stripe_customer_id: str | None = Column(String(100), nullable=True)
    stripe_subscription_id: str | None = Column(String(100), nullable=True)
    trial_started_at = Column(DateTime, nullable=True)
    is_trial_used: bool = Column(Boolean, default=False)
    is_beta_approved: bool = Column(Boolean, default=False)  # Nouveau : Accès Beta
    updated_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<Profile(id={self.id}, tier={self.subscription_tier})>"


class Team(Base):
    """Table des équipes de football (Ligue 1 & Premier League)."""
    __tablename__ = "teams"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    name: str = Column(String(100), unique=True, nullable=False, index=True)
    league: str = Column(String(50), nullable=False)

    # Relations
    home_matches = relationship("MatchRaw", foreign_keys="MatchRaw.home_team_id", back_populates="home_team")
    away_matches = relationship("MatchRaw", foreign_keys="MatchRaw.away_team_id", back_populates="away_team")

    def __repr__(self) -> str:
        return f"<Team(id={self.id}, name='{self.name}', league='{self.league}')>"


class MatchRaw(Base):
    """Table des matchs historiques filtrés depuis football-data.co.uk."""
    __tablename__ = "matches_raw"

    id: int = Column(Integer, primary_key=True, autoincrement=True)

    # Informations générales
    div: str = Column(String(10), nullable=False)
    date = Column(DateTime, nullable=False, index=True)
    time: str | None = Column(String(10), nullable=True)

    # Clés étrangères vers les équipes
    home_team_id: int = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    away_team_id: int = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)

    # Score final et mi-temps
    fthg: int = Column(Integer, nullable=False)         # Full Time Home Goals
    ftag: int = Column(Integer, nullable=False)         # Full Time Away Goals
    ftr: str = Column(String(1), nullable=False)        # Full Time Result (H/D/A)
    hthg: int = Column(Integer, nullable=True)          # Half Time Home Goals
    htag: int = Column(Integer, nullable=True)          # Half Time Away Goals
    htr: str | None = Column(String(1), nullable=True)  # Half Time Result

    # Statistiques du match
    hs: int | None = Column(Integer, nullable=True)      # Home Shots
    as_shots: int | None = Column(Integer, nullable=True) # Away Shots (as est réservé Python)
    hst: int | None = Column(Integer, nullable=True)     # Home Shots on Target
    ast: int | None = Column(Integer, nullable=True)     # Away Shots on Target
    hf: int | None = Column(Integer, nullable=True)      # Home Fouls
    af: int | None = Column(Integer, nullable=True)      # Away Fouls
    hc: int | None = Column(Integer, nullable=True)      # Home Corners
    ac: int | None = Column(Integer, nullable=True)      # Away Corners
    hy: int | None = Column(Integer, nullable=True)      # Home Yellow Cards
    ay: int | None = Column(Integer, nullable=True)      # Away Yellow Cards
    hr: int | None = Column(Integer, nullable=True)      # Home Red Cards
    ar: int | None = Column(Integer, nullable=True)      # Away Red Cards

    # Métriques Avancées (Understat)
    home_xg: float | None = Column(Float, nullable=True)
    away_xg: float | None = Column(Float, nullable=True)
    home_xpts: float | None = Column(Float, nullable=True)
    away_xpts: float | None = Column(Float, nullable=True)

    # Cotes — Moyennes du marché
    avg_h: float | None = Column(Float, nullable=True)        # Average Home Win
    avg_d: float | None = Column(Float, nullable=True)        # Average Draw
    avg_a: float | None = Column(Float, nullable=True)        # Average Away Win
    avg_over_25: float | None = Column(Float, nullable=True)  # Average Over 2.5
    avg_under_25: float | None = Column(Float, nullable=True) # Average Under 2.5

    # Cotes — Clôture Bet365
    b365_ch: float | None = Column(Float, nullable=True)  # B365 Closing Home
    b365_cd: float | None = Column(Float, nullable=True)  # B365 Closing Draw
    b365_ca: float | None = Column(Float, nullable=True)  # B365 Closing Away

    # Relations
    home_team = relationship("Team", foreign_keys=[home_team_id], back_populates="home_matches")
    away_team = relationship("Team", foreign_keys=[away_team_id], back_populates="away_matches")
    features = relationship("MatchFeature", back_populates="match", uselist=False, cascade="all, delete-orphan")

    # Contrainte d'unicité pour éviter les doublons
    __table_args__ = (
        UniqueConstraint("date", "home_team_id", "away_team_id", name="uq_match_date_teams"),
    )

    def __repr__(self) -> str:
        return f"<MatchRaw(id={self.id}, date={self.date}, home={self.home_team_id} vs away={self.away_team_id}, ftr='{self.ftr}')>"


class MatchFeature(Base):
    """Table des features calculées pour le Deep Learning."""
    __tablename__ = "match_features"

    match_id: int = Column(Integer, ForeignKey("matches_raw.id"), primary_key=True)

    # Forme générale (5 derniers matchs, tous terrains confondus)
    home_pts_last_5: float | None = Column(Float, nullable=True)
    home_goals_scored_last_5: float | None = Column(Float, nullable=True)
    home_goals_conceded_last_5: float | None = Column(Float, nullable=True)
    away_pts_last_5: float | None = Column(Float, nullable=True)
    away_goals_scored_last_5: float | None = Column(Float, nullable=True)
    away_goals_conceded_last_5: float | None = Column(Float, nullable=True)

    # Elo Rating System
    home_elo: float | None = Column(Float, nullable=True)
    away_elo: float | None = Column(Float, nullable=True)
    elo_diff: float | None = Column(Float, nullable=True)  # home_elo - away_elo

    # Forme spécifique domicile / extérieur
    home_pts_last_5_at_home: float | None = Column(Float, nullable=True)  # Forme à domicile uniquement
    away_pts_last_5_away: float | None = Column(Float, nullable=True)     # Forme à l'extérieur uniquement

    # Indice de fatigue (jours de repos)
    home_days_rest: float | None = Column(Float, nullable=True)
    away_days_rest: float | None = Column(Float, nullable=True)

    # Vraies métriques avancées (Understat - xG & xPts)
    home_xg_last_5: float | None = Column(Float, nullable=True)
    away_xg_last_5: float | None = Column(Float, nullable=True)
    home_xpts_last_5: float | None = Column(Float, nullable=True)
    away_xpts_last_5: float | None = Column(Float, nullable=True)

    # Série d'invincibilité & momentum
    home_unbeaten_streak: float | None = Column(Float, nullable=True)
    away_unbeaten_streak: float | None = Column(Float, nullable=True)
    home_momentum: float | None = Column(Float, nullable=True)
    away_momentum: float | None = Column(Float, nullable=True)

    # Tirs cadrés (rolling 5 matchs)
    home_sot_last_5: float | None = Column(Float, nullable=True)
    away_sot_last_5: float | None = Column(Float, nullable=True)
    home_sot_conceded_last_5: float | None = Column(Float, nullable=True)
    away_sot_conceded_last_5: float | None = Column(Float, nullable=True)

    # Confrontations directes (H2H)
    h2h_dominance: float | None = Column(Float, nullable=True)
    h2h_avg_goals: float | None = Column(Float, nullable=True)
    h2h_matches: float | None = Column(Float, nullable=True)

    # Relation inverse
    match = relationship("MatchRaw", back_populates="features")

    def __repr__(self) -> str:
        return f"<MatchFeature(match_id={self.match_id}, elo_diff={self.elo_diff}, home_pts_5={self.home_pts_last_5})>"


class PredictionLog(Base):
    """Historique des prédictions IA pour le suivi de performance."""
    __tablename__ = "prediction_logs"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    
    # Match info
    home_team: str = Column(String(100), nullable=False)
    away_team: str = Column(String(100), nullable=False)
    league: str = Column(String(50), nullable=False)
    match_date = Column(DateTime, nullable=False)
    
    # Prédiction
    prediction: str = Column(String(100), nullable=False)  # "H", "D", "A", "1 ou N (Double chance)", etc.
    tip_type: str = Column(String(50), nullable=False)     # "result", "btts", "over25", "double_chance"
    confidence: float = Column(Float, nullable=False)
    odds: float = Column(Float, nullable=True)
    
    # Probabilités du modèle au moment de la prédiction
    prob_home: float | None = Column(Float, nullable=True)
    prob_draw: float | None = Column(Float, nullable=True)
    prob_away: float | None = Column(Float, nullable=True)
    
    # Résultat (renseigné après le match)
    actual_result: str | None = Column(String(10), nullable=True)  # "H", "D", "A"
    actual_home_goals: int | None = Column(Integer, nullable=True)
    actual_away_goals: int | None = Column(Integer, nullable=True)
    is_won: bool | None = Column(Boolean, nullable=True)  # None = pending, True = won, False = lost
    
    # Timestamps
    created_at = Column(DateTime, nullable=False)
    verified_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("match_date", "home_team", "away_team", "tip_type", name="uq_prediction_log"),
    )

    def __repr__(self) -> str:
        status = "won" if self.is_won else ("lost" if self.is_won is False else "pending")
        return f"<PredictionLog({self.home_team} vs {self.away_team}, tip={self.prediction}, {status})>"

