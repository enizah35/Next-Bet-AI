"""
src/utils/mappings.py
Dictionnaires pour la standardisation des noms d'équipes entre différentes sources.
Le projet base ses noms officiels sur 'football-data.co.uk' (table `teams`).
"""

# Mapping : "Nom Understat" -> "Nom DB (Football-Data)"
UNDERSTAT_TO_FD = {
    # == Ligue 1 ==
    "Paris Saint Germain": "Paris SG",
    "Olympique Marseille": "Marseille",
    "Olympique Lyonnais": "Lyon",
    "Lille": "Lille",
    "Monaco": "Monaco",
    "Rennes": "Rennes",
    "Brest": "Brest",
    "Lens": "Lens",
    "Nantes": "Nantes",
    "Montpellier": "Montpellier",
    "Toulouse": "Toulouse",
    "Lorient": "Lorient",
    "Metz": "Metz",
    "Le Havre": "Le Havre",
    "Reims": "Reims",
    "Nice": "Nice",
    "Strasbourg": "Strasbourg",
    "Clermont Foot": "Clermont",
    "Saint-Etienne": "St Etienne",
    "Auxerre": "Auxerre",
    "Angers": "Angers",
    "Troyes": "Troyes",
    "Bordeaux": "Bordeaux",

    # == Premier League ==
    "Manchester United": "Man United",
    "Manchester City": "Man City",
    "Tottenham": "Tottenham",
    "Arsenal": "Arsenal",
    "Chelsea": "Chelsea",
    "Liverpool": "Liverpool",
    "Newcastle United": "Newcastle",
    "Wolverhampton Wanderers": "Wolves",
    "Nottingham Forest": "Nott'm Forest",
    "Aston Villa": "Aston Villa",
    "West Ham": "West Ham",
    "Crystal Palace": "Crystal Palace",
    "Brighton": "Brighton",
    "Bournemouth": "Bournemouth",
    "Fulham": "Fulham",
    "Everton": "Everton",
    "Brentford": "Brentford",
    "Sheffield United": "Sheffield United",
    "Luton": "Luton",
    "Burnley": "Burnley",
    "Leicester": "Leicester",
    "Southampton": "Southampton",
    "Leeds": "Leeds",
    "Ipswich": "Ipswich",
}

def get_fd_name(understat_name: str) -> str:
    """Retourne le nom officiel (DB) ou le nom original si non mappé."""
    return UNDERSTAT_TO_FD.get(understat_name, understat_name)
