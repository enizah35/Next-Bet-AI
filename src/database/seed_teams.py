from src.database.database import get_session
from src.database.models import Team

def seed_teams():
    session = get_session()
    
    l1_teams = [
        "Paris Saint-Germain", "Marseille", "Lyon", "Monaco", "Lille", 
        "Nice", "Rennes", "Lens", "Reims", "Strasbourg", 
        "Montpellier", "Toulouse", "Nantes", "Le Havre", "Brest", 
        "Lorient", "Clermont Foot", "Metz"
    ]
    
    pl_teams = [
        "Man City", "Arsenal", "Liverpool", "Aston Villa", "Tottenham", 
        "Chelsea", "Newcastle", "Man United", "West Ham", "Crystal Palace", 
        "Brighton", "Bournemouth", "Wolves", "Fulham", "Everton", 
        "Brentford", "Nottingham Forest", "Luton", "Burnley", "Sheffield Utd"
    ]

    try:
        # Ajout Ligue 1
        for name in l1_teams:
            if not session.query(Team).filter(Team.name == name).first():
                session.add(Team(name=name, league="Ligue 1"))
        
        # Ajout Premier League
        for name in pl_teams:
            if not session.query(Team).filter(Team.name == name).first():
                session.add(Team(name=name, league="Premier League"))
        
        session.commit()
        print(f"Succès : {len(l1_teams)} équipes L1 et {len(pl_teams)} équipes PL ajoutées.")
    except Exception as e:
        session.rollback()
        print(f"Erreur lors du seeding : {e}")
    finally:
        session.close()

if __name__ == "__main__":
    seed_teams()
