import httpx
import logging
from functools import lru_cache

logging.basicConfig(level=logging.INFO)

STADIUM_COORDS = {
    "Paris Saint-Germain": (48.8414, 2.2530),
    "Marseille": (43.2698, 5.3959),
    "Lyon": (45.7656, 4.9818),
    "Lille": (50.6119, 3.1305),
    "Lens": (50.4328, 2.8149),
    "Arsenal": (51.5549, -0.1084),
    "Manchester City": (53.4831, -2.2004),
    "Liverpool": (53.4308, -2.9608),
    "Chelsea": (51.4816, -0.1910),
    "Manchester United": (53.4631, -2.2913),
    "Tottenham": (51.6043, -0.0662)
}

def get_stadium_weather_bulk(teams: list):
    """
    Récupère la météo pour plusieurs équipes d'un coup (Optimisation Phase 3).
    """
    weather_map = {}
    for team in teams:
        coords = STADIUM_COORDS.get(team)
        if not coords:
            # Fallback Londres/Paris
            coords = (51.5074, -0.1278) if any(x in team.lower() for x in ['pool', 'city', 'utd', 'ham']) else (48.8566, 2.3522)
            
        url = "https://api.open-meteo.com/v1/forecast"
        params = {"latitude": coords[0], "longitude": coords[1], "current_weather": True}
        
        try:
            r = httpx.get(url, params=params, timeout=5.0)
            if r.status_code == 200:
                code = r.json().get("current_weather", {}).get("weathercode", 0)
                weather_map[team] = 1 if code <= 3 else (3 if code >= 50 else 2)
        except:
            weather_map[team] = 1
            
    return weather_map

@lru_cache(maxsize=128)
def get_stadium_weather(team_name: str):
    # Fallback pour compatibilité
    res = get_stadium_weather_bulk([team_name])
    return res.get(team_name, 1)
