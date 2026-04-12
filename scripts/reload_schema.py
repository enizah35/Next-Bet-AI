from sqlalchemy import text
from src.database.database import engine

def reload_supabase_schema():
    print("Rechargement du cache Supabase (PostgREST)...")
    try:
        with engine.connect() as conn:
            # Demande à l'API Supabase de rafraîchir ses colonnes connues
            conn.execute(text("NOTIFY pgrst, 'reload schema';"))
            conn.commit()
            print("Succès : Le cache a été rechargé.")
    except Exception as e:
        print(f"Erreur : {e}")

if __name__ == "__main__":
    reload_supabase_schema()
