import httpx
import logging
from datetime import datetime, timedelta
from functools import lru_cache

logging.basicConfig(level=logging.INFO)

def american_to_prob(american_odds):
    """Convertit les cotes américaines en probabilité (0-1)."""
    if american_odds > 0:
        return 100 / (american_odds + 100)
    else:
        return abs(american_odds) / (abs(american_odds) + 100)

@lru_cache(maxsize=128)
def get_recent_form(espn_code):
    """Calcule le coefficient de Forme d'une équipe en fonction de ses perfs annuelles (Win%)."""
    URL = f"https://site.api.espn.com/apis/v2/sports/soccer/{espn_code}/standings"
    form_dict = {}
    try:
        r = httpx.get(URL)
        r.raise_for_status()
        data = r.json()
        teams = data['children'][0]['standings']['entries']
        
        for t in teams:
            team_name = t['team']['name']
            stats = t['stats']
            
            wins, games = 0, 1
            for s in stats:
                if s['name'] == 'wins':
                    wins = float(s.get('value', 0))
                if s['name'] == 'gamesPlayed':
                    games = float(s.get('value', 1))
                    
            win_pct = wins / games if games > 0 else 0.5
            form_dict[team_name] = round(win_pct, 2)
            
    except Exception as e:
        logging.error(f"Error extracting form from {URL}: {e}")
    return form_dict

def get_upcoming_matches_7_days():
    """Scrape simultanément la L1 et la Premier League via API Rest pour les 7 prochains jours exclusifs."""
    leagues = [
        {"name": "Ligue 1", "espn_code": "fra.1"},
        {"name": "Premier League", "espn_code": "eng.1"}
    ]
    
    today = datetime.now()
    seven_days = today + timedelta(days=7)
    date_str = f"{today.strftime('%Y%m%d')}-{seven_days.strftime('%Y%m%d')}"
    
    all_matches = []
    
    for league in leagues:
        form_data = get_recent_form(league['espn_code'])
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league['espn_code']}/scoreboard?dates={date_str}"
        logging.info(f"Processing {league['name']} API: {url}")
        
        try:
            r = httpx.get(url)
            r.raise_for_status()
            data = r.json()
            
            if 'events' in data:
                for e in data['events']:
                    # ex: "2026-04-03T18:45Z"
                    raw_str = e['date'].replace('Z', '+0000')
                    match_date = datetime.strptime(raw_str, "%Y-%m-%dT%H:%M%z")
                    
                    competitors = e['competitions'][0]['competitors']
                    if competitors[0]['homeAway'] == 'home':
                        home_team = competitors[0]['team']['name']
                        away_team = competitors[1]['team']['name']
                    else:
                        home_team = competitors[1]['team']['name']
                        away_team = competitors[0]['team']['name']
                        
                    # Extraction des cotes si disponibles
                    odds_data = {"1": None, "N": None, "2": None}
                    try:
                        if 'odds' in e['competitions'][0] and len(e['competitions'][0]['odds']) > 0:
                            # Souvent moneyline
                            o = e['competitions'][0]['odds'][0]
                            if 'home' in o and 'odds' in o['home']:
                                odds_data["1"] = american_to_prob(float(o['home']['odds']))
                            if 'away' in o and 'odds' in o['away']:
                                odds_data["2"] = american_to_prob(float(o['away']['odds']))
                            if 'draw' in o and 'odds' in o['draw']:
                                odds_data["N"] = american_to_prob(float(o['draw']['odds']))
                    except Exception as odds_err:
                        logging.warning(f"Could not parse odds for {home_team} vs {away_team}: {odds_err}")

                    all_matches.append({
                        "homeTeam": home_team,
                        "awayTeam": away_team,
                        "date": f"{match_date.strftime('%d/%m/%y')} à {match_date.strftime('%H:%M')}",
                        "competition": league['name'],
                        "form_home": form_data.get(home_team, 0.50),
                        "form_away": form_data.get(away_team, 0.50),
                        "bookmaker_probs": odds_data,
                        "raw_date": match_date.timestamp() # tri interne sécurisé
                    })
        except Exception as e:
            logging.error(f"Error parsing API {league['name']}: {e}")
            
    all_matches.sort(key=lambda x: x['raw_date'])
    for m in all_matches:
        del m['raw_date'] # Nettoyage API JSON
    return all_matches

if __name__ == "__main__":
    ms = get_upcoming_matches_7_days()
    for m in ms:
        print(f"[{m['competition']}] {m['date']} : {m['homeTeam']} ({m['form_home']}) vs {m['awayTeam']} ({m['form_away']})")
