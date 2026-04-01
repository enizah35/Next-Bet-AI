import httpx
from bs4 import BeautifulSoup
import logging
import unicodedata
from functools import lru_cache

logging.basicConfig(level=logging.INFO)

def remove_accents(input_str):
    # Enlève les accents pour la comparaison de chaînes
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return u"".join([c for c in nfkd_form if not unicodedata.combining(c)])

def fetch_all_football_news():
    """
    Récupère massivement les derniers articles une seule fois pour toute l'API.
    """
    feeds = [
        "https://rmcsport.bfmtv.com/rss/football/",
        "http://feeds.bbci.co.uk/sport/football/rss.xml"
    ]
    all_news = []
    for url in feeds:
        try:
            response = httpx.get(url, timeout=10.0)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, features="xml")
                items = soup.findAll("item")
                for item in items[:30]:
                    title = remove_accents(item.find("title").text.lower() if item.find("title") else "")
                    desc = remove_accents(item.find("description").text.lower() if item.find("description") else "")
                    all_news.append(title + " " + desc)
        except Exception as e:
            logging.error(f"Error fetching RSS {url}: {e}")
    return all_news

def get_team_injuries_from_pool(team_name: str, news_pool: list):
    """
    Recherche les blessures dans un pool de news déjà téléchargé (Ultra Rapide).
    """
    injury_keywords = ['blessé', 'blesse', 'absent', 'forfait', 'injury', 'injured', 'misses', 'sidelined', 'out']
    team_normalized = remove_accents(team_name.lower())
    search_term = team_normalized.split()[0] if len(team_normalized) > 4 else team_normalized
    
    injuries_count = 0
    for text in news_pool:
        if search_term in text:
            if any(kw in text for kw in injury_keywords):
                injuries_count += 1
    return min(injuries_count, 4)

# Garder l'ancienne signature pour compatibilité si besoin, mais déconseillé
@lru_cache(maxsize=128)
def get_team_injuries(team_name: str):
    pool = fetch_all_football_news()
    return get_team_injuries_from_pool(team_name, pool)

if __name__ == "__main__":
    p = fetch_all_football_news()
    print(f"Fetched {len(p)} news items.")
    print(f"Arsenal injuries: {get_team_injuries_from_pool('Arsenal', p)}")
