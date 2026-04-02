from sqlalchemy import text
from src.database.database import engine

def update_db():
    print("Mise à jour de la table profiles pour la Beta...")
    try:
        with engine.connect() as conn:
            # Ajout de la colonne if not exists
            conn.execute(text("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS is_beta_approved BOOLEAN DEFAULT FALSE;"))
            conn.commit()
            print("Succès : Colonne is_beta_approved ajoutée.")
    except Exception as e:
        print(f"Erreur lors de la mise à jour : {e}")

if __name__ == "__main__":
    update_db()
