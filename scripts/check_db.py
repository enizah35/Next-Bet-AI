from src.database.database import get_session
from sqlalchemy import text

s = get_session()
r = s.execute(text("SELECT COUNT(*) FROM matches_raw")).scalar()
print(f"Total matches: {r}")
r2 = s.execute(text("SELECT COUNT(*) FROM matches_raw WHERE avg_h IS NOT NULL")).scalar()
print(f"With odds: {r2}")
r3 = s.execute(text("SELECT COUNT(*) FROM match_features")).scalar()
print(f"Features computed: {r3}")
s.close()
