"""
src/ingestion/live_data.py
Module pour l'agrégation des données live temporelles en vue des prédictions des 7 prochains jours.
Sources : Calendrier ESPN, Météo Open-Meteo, Alertes RSS BBC/RMC.
"""

import logging
import random
import re
from datetime import datetime, timedelta
from typing import Any

import feedparser
import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.database import get_session
from src.database.models import Team

logger: logging.Logger = logging.getLogger(__name__)

# Coordinates mapping for demo/weather
STADIUM_COORDS = {
    # PL
    "Arsenal": (51.5549, -0.1084),
    "Man City": (53.4831, -2.2004),
    "Liverpool": (53.4308, -2.9608),
    "Chelsea": (51.4816, -0.1910),
    "Tottenham": (51.6042, -0.0662),
    # L1
    "Paris SG": (48.8414, 2.2530),
    "Marseille": (43.2698, 5.3959),
    "Lyon": (45.7656, 4.9819),
    "Monaco": (43.7276, 7.4156),
    "Lille": (50.6120, 3.1305),
}

RSS_FEEDS = {
    "Premier League": "http://feeds.bbci.co.uk/sport/football/rss.xml",
    "Ligue 1": "https://rmcsport.bfmtv.com/rss/football/",
}

NEGATIVE_KEYWORDS = ["blessé", "blessure", "absent", "forfait", "injury", "out", "doubt", "sidelined"]


def get_news_alerts(team_name: str, league: str) -> list[str]:
    """Scannés les flux RSS pour le nom de l'équipe et repère les mots-clés de blessures ou alertes."""
    feed_url = RSS_FEEDS.get(league)
    alerts = []
    if not feed_url:
        return alerts

    try:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:20]:  # Scan les 20 dernières actualités
            title: str = entry.title
            # Si l'équipe est mentionnée
            if team_name.lower() in title.lower():
                # Vérification présence de mots clés négatifs
                if any(kw in title.lower() for kw in NEGATIVE_KEYWORDS):
                    alerts.append(title)
        
        # Max 2 alerts
        return alerts[:2]
    except Exception as e:
        logger.warning(f"Erreur RSS pour {team_name} : {e}")
        return []


def get_weather(team_name: str) -> int:
    """Interroge Open-Meteo pour les 7 prochains jours sur la localisation du stade de l'équipe."""
    coords = STADIUM_COORDS.get(team_name, (48.8566, 2.3522))  # Defaults to Paris
    url = f"https://api.open-meteo.com/v1/forecast?latitude={coords[0]}&longitude={coords[1]}&daily=weathercode&timezone=GMT"
    
    try:
        r = requests.get(url, timeout=5)
        data = r.json()
        codes = data.get("daily", {}).get("weathercode", [])
        if codes:
            # Code WMO moyen (simplified)
            code = codes[0]
            if code in [0, 1, 2, 3]: return 1 # Optimal/Clear
            if code in [45, 48, 51, 53, 55]: return 2 # Cloudy/wind
            return 3 # Rain
        return 1
    except Exception:
        return 1


def get_upcoming_matches(league: str) -> list[dict]:
    """
    Tente de récupérer le calendrier des 7 jours à venir depuis l'API ESPN.
    Si ESPN retourne 0 match (intersaison / dates erronées), génère une simulation intelligente.
    """
    espn_league_code = "eng.1" if league == "Premier League" else "fra.1"
    
    today = datetime.now()
    next_week = today + timedelta(days=7)
    date_str_start = today.strftime('%Y%m%d')
    date_str_end = next_week.strftime('%Y%m%d')
    
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{espn_league_code}/scoreboard?dates={date_str_start}-{date_str_end}"
    
    matches_list = []
    
    try:
        r = requests.get(url, timeout=5)
        data = r.json()
        events = data.get("events", [])
        
        for e in events:
            # Format ESPN: "HomeTeam vs AwayTeam" or specific components
            comps = e.get("competitions", [{}])[0].get("competitors", [])
            if len(comps) == 2:
                # Competitor indices vary, generally home is 0, away is 1
                home = comps[0].get("team", {}).get("name") if comps[0].get("homeAway") == "home" else comps[1].get("team", {}).get("name")
                away = comps[1].get("team", {}).get("name") if comps[1].get("homeAway") == "away" else comps[0].get("team", {}).get("name")
                date_iso = e.get("date")
                
                if home and away:
                    matches_list.append({
                        "homeTeam": home,
                        "awayTeam": away,
                        "dateStr": date_iso, # Format 2026-04-01T20:00Z
                    })
    except Exception as ex:
        logger.warning(f"ESPN API call failed: {ex}")

    # ============================================================
    # FALLBACK DE SIMULATION (Si pas de vrais matchs trouvés)
    # Très robuste pour le DEV hors saison !
    # ============================================================
    if not matches_list:
        logger.info(f"API ESPN sans match pour la {league}. Initialisation de la Simulation de remplacement basées sur la DB...")
        session: Session = get_session()
        
        stmt = select(Team.name).where(Team.league == league)
        teams = [r[0] for r in session.execute(stmt).fetchall()]
        session.close()
        
        if len(teams) >= 2:
            # Créer entre 5 et 8 machs au hasard
            num_matches = min(8, len(teams) // 2)
            random.shuffle(teams)
            
            for i in range(num_matches):
                home = teams[i*2]
                away = teams[i*2 + 1]
                
                # Attribuer une date random dans les 7 jours
                days_ahead = random.randint(1, 7)
                match_dt = today + timedelta(days=days_ahead, hours=random.randint(14, 21))
                
                matches_list.append({
                    "homeTeam": home,
                    "awayTeam": away,
                    "dateStr": match_dt.strftime("%Y-%m-%dT%H:%M:00Z"),
                })
        
    logger.info(f"Trouvé {len(matches_list)} matchs à venir pour la {league}.")
    return matches_list


def enrich_pipeline(league: str) -> list[dict]:
    """Exécute tout le pipeline de récupération (Météo, RSS, Matchs) et retourne la raw list."""
    logger.info(f"--- Démarrage Pipeline Live Data pour {league} ---")
    matches = get_upcoming_matches(league)
    
    enriched = []
    
    for m in matches:
        ht = m["homeTeam"]
        at = m["awayTeam"]
        
        # Météo du stade (Home)
        weather_code = get_weather(ht)
        
        # Actualités blessures
        home_news = get_news_alerts(ht, league)
        away_news = get_news_alerts(at, league)
        
        enriched.append({
            "homeTeam": ht,
            "awayTeam": at,
            "date": m["dateStr"],
            "weatherCode": weather_code,
            "injuriesHome": home_news,
            "injuriesAway": away_news,
            "injuriesCountHome": len(home_news),
            "injuriesCountAway": len(away_news),
        })
        
    return enriched
