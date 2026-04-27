"""
src/ingestion/live_data.py
Module pour l'agrégation des données live temporelles en vue des prédictions des 7 prochains jours.
Sources : Calendrier ESPN, Météo Open-Meteo, Alertes RSS BBC/RMC.
"""

import logging
import os
import random
from datetime import datetime, timedelta
import concurrent.futures

import feedparser
import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.database import get_session
from src.database.models import Team

logger: logging.Logger = logging.getLogger(__name__)
LIVE_ODDS_IN_FAST = os.getenv("LIVE_ODDS_IN_FAST", "true").lower() == "true"

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

# Codes ESPN pour chaque ligue (site.api.espn.com)
ESPN_LEAGUE_CODES: dict[str, str] = {
    "Premier League": "eng.1",
    "Championship":   "eng.2",
    "Ligue 1":        "fra.1",
    "Ligue 2":        "fra.2",
    "Bundesliga":     "ger.1",
    "2. Bundesliga":  "ger.2",
    "La Liga":        "esp.1",
    "La Liga 2":      "esp.2",
    "Serie A":        "ita.1",
    "Serie B":        "ita.2",
    "Eredivisie":     "ned.1",
    "Primeira Liga":  "por.1",
    "Süper Lig":      "tur.1",
    "Belgian Pro League": "bel.1",
    "Scottish Premiership": "sco.1",
}

RSS_FEEDS = {
    "Premier League": "http://feeds.bbci.co.uk/sport/football/rss.xml",
    "Championship":   "http://feeds.bbci.co.uk/sport/football/rss.xml",
    "Ligue 1":        "https://rmcsport.bfmtv.com/rss/football/",
    "Ligue 2":        "https://rmcsport.bfmtv.com/rss/football/",
}

NEGATIVE_KEYWORDS = ["blessé", "blessure", "absent", "forfait", "injury", "out", "doubt", "sidelined"]

FAST_FALLBACK_TEAMS: dict[str, list[str]] = {
    "Premier League": ["Arsenal", "Man City", "Liverpool", "Chelsea", "Tottenham", "Man United", "Newcastle", "Aston Villa"],
    "Championship": ["Leeds", "Leicester", "Southampton", "West Brom", "Norwich", "Middlesbrough", "Sunderland", "Watford"],
    "Ligue 1": ["Paris SG", "Marseille", "Lyon", "Monaco", "Lille", "Rennes", "Nice", "Lens"],
    "Ligue 2": ["Saint-Etienne", "Bordeaux", "Auxerre", "Caen", "Paris FC", "Guingamp", "Amiens", "Bastia"],
    "Bundesliga": ["Bayern Munich", "Dortmund", "Leverkusen", "RB Leipzig", "Frankfurt", "Stuttgart", "Wolfsburg", "Freiburg"],
    "2. Bundesliga": ["Hamburg", "Schalke 04", "Hannover", "Hertha Berlin", "Nurnberg", "Karlsruhe", "Dusseldorf", "Kaiserslautern"],
    "La Liga": ["Real Madrid", "Barcelona", "Atletico Madrid", "Sevilla", "Real Sociedad", "Villarreal", "Valencia", "Athletic Club"],
    "La Liga 2": ["Espanyol", "Valladolid", "Leganes", "Eibar", "Zaragoza", "Oviedo", "Sporting Gijon", "Tenerife"],
    "Serie A": ["Inter", "Milan", "Juventus", "Napoli", "Roma", "Lazio", "Atalanta", "Fiorentina"],
    "Serie B": ["Parma", "Palermo", "Sampdoria", "Bari", "Venezia", "Cremonese", "Pisa", "Modena"],
    "Eredivisie": ["PSV", "Ajax", "Feyenoord", "AZ Alkmaar", "Twente", "Utrecht", "Heerenveen", "Vitesse"],
    "Primeira Liga": ["Benfica", "Porto", "Sporting CP", "Braga", "Guimaraes", "Boavista", "Famalicao", "Rio Ave"],
    "SÃ¼per Lig": ["Galatasaray", "Fenerbahce", "Besiktas", "Trabzonspor", "Basaksehir", "Sivasspor", "Antalyaspor", "Alanyaspor"],
    "Belgian Pro League": ["Club Brugge", "Anderlecht", "Genk", "Gent", "Antwerp", "Standard Liege", "Union SG", "Mechelen"],
    "Scottish Premiership": ["Celtic", "Rangers", "Hearts", "Hibernian", "Aberdeen", "Motherwell", "Dundee", "St Mirren"],
}


def get_news_alerts(team_name: str, entries: list) -> list[str]:
    """Scanne les entrées RSS pour le nom de l'équipe et repère les mots-clés de blessures ou alertes."""
    alerts = []
    try:
        for entry in entries:
            title: str = entry.title
            if team_name.lower() in title.lower():
                if any(kw in title.lower() for kw in NEGATIVE_KEYWORDS):
                    alerts.append(title)
        
        return alerts[:2]
    except Exception as e:
        logger.warning(f"Erreur parsage RSS pour {team_name} : {e}")
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


def get_upcoming_matches(league: str, use_db_fallback: bool = True) -> list[dict]:
    """
    Tente de récupérer le calendrier des 7 jours à venir depuis l'API ESPN.
    Si ESPN retourne 0 match (intersaison / dates erronées), génère une simulation intelligente.
    """
    espn_league_code = ESPN_LEAGUE_CODES.get(league, "eng.1")
    
    today = datetime.now()
    next_week = today + timedelta(days=7)
    date_str_start = today.strftime('%Y%m%d')
    date_str_end = next_week.strftime('%Y%m%d')
    
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{espn_league_code}/scoreboard?dates={date_str_start}-{date_str_end}"
    
    matches_list = []
    
    try:
        r = requests.get(url, timeout=3)
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
                    from src.utils.mappings import get_fd_name_espn
                    matches_list.append({
                        "homeTeam": get_fd_name_espn(home),
                        "awayTeam": get_fd_name_espn(away),
                        "dateStr": date_iso, # Format 2026-04-01T20:00Z
                    })
    except Exception as ex:
        logger.warning(f"ESPN API call failed: {ex}")

    # ============================================================
    # FALLBACK DE SIMULATION (Si pas de vrais matchs trouvés)
    # Très robuste pour le DEV hors saison !
    # ============================================================
    if not matches_list:
        if not use_db_fallback:
            teams = FAST_FALLBACK_TEAMS.get(league, FAST_FALLBACK_TEAMS["Premier League"]).copy()
            random.shuffle(teams)
            for i in range(0, len(teams) - 1, 2):
                match_dt = today + timedelta(days=random.randint(1, 7), hours=random.randint(14, 21))
                matches_list.append({
                    "homeTeam": teams[i],
                    "awayTeam": teams[i + 1],
                    "dateStr": match_dt.strftime("%Y-%m-%dT%H:%M:00Z"),
                })
            logger.info(f"Fallback rapide local: {len(matches_list)} matchs simulés pour {league}.")
            return matches_list

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


def enrich_pipeline(league: str, fast: bool = False) -> list[dict]:
    """Exécute le pipeline live data. En mode fast, évite les appels externes secondaires."""
    logger.info(f"--- Démarrage Pipeline Live Data pour {league} (fast={fast}) ---")
    matches = get_upcoming_matches(league, use_db_fallback=not fast)
    
    enriched = []
    
    # Pre-fetch RSS ONCE for the whole league (injuries)
    feed_url = RSS_FEEDS.get(league)
    feed_entries = []
    if feed_url and not fast:
        try:
            response = requests.get(feed_url, timeout=3)
            response.raise_for_status()
            feed = feedparser.parse(response.content)
            feed_entries = feed.entries[:20]
        except Exception as e:
            logger.warning(f"Erreur requête globale RSS: {e}")

    # Pre-fetch RSS pour le sentiment (sources multiples)
    from src.ingestion.news_sentiment import fetch_rss_entries, get_match_sentiment
    sentiment_entries = [] if fast else fetch_rss_entries(league)

    # Pre-fetch cotes live (1 seul appel API pour toute la ligue)
    from src.ingestion.live_odds import fetch_live_odds, get_match_odds
    odds_cache = {} if fast and not LIVE_ODDS_IN_FAST else fetch_live_odds(league)

    # Process matches sequentially for news, but pre-fetch weather in parallel
    home_teams = [m["homeTeam"] for m in matches]
    
    # Fetch weather concurrently, sauf en mode fast où une valeur neutre suffit.
    if fast:
        weather_results = {ht: 1 for ht in home_teams}
    else:
        weather_results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_ht = {executor.submit(get_weather, ht): ht for ht in home_teams}
            for future in concurrent.futures.as_completed(future_to_ht):
                ht = future_to_ht[future]
                try:
                    weather_results[ht] = future.result()
                except Exception:
                    weather_results[ht] = 1

    for m in matches:
        ht = m["homeTeam"]
        at = m["awayTeam"]
        
        # Use parallelized weather
        weather_code = weather_results.get(ht, 1)
        
        # Actualités blessures using pre-fetched entries
        home_news = get_news_alerts(ht, feed_entries)
        away_news = get_news_alerts(at, feed_entries)

        # Analyse de sentiment (utilise les entries déjà récupérées)
        sentiment = get_match_sentiment(ht, at, league, entries=sentiment_entries)

        # Cotes live bookmakers
        match_odds = get_match_odds(ht, at, odds_cache)
        
        enriched.append({
            "homeTeam": ht,
            "awayTeam": at,
            "date": m["dateStr"],
            "weatherCode": weather_code,
            "injuriesHome": home_news,
            "injuriesAway": away_news,
            "injuriesCountHome": len(home_news),
            "injuriesCountAway": len(away_news),
            "homeSentiment": sentiment["home_sentiment"],
            "awaySentiment": sentiment["away_sentiment"],
            "sentimentDiff": sentiment["sentiment_diff"],
            "homeHeadlines": sentiment["home_headlines"],
            "awayHeadlines": sentiment["away_headlines"],
            "odds": match_odds,  # None si pas de cotes dispo
        })
        
    return enriched
