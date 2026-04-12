"""Quick data analysis script."""
from src.database.database import get_session
from sqlalchemy import text

s = get_session()

total = s.execute(text("SELECT count(*) FROM matches_raw")).scalar()
print(f"Total matches: {total}")

with_odds = s.execute(text("SELECT count(*) FROM matches_raw WHERE avg_h IS NOT NULL AND avg_d IS NOT NULL AND avg_a IS NOT NULL")).scalar()
print(f"With avg odds: {with_odds}")

with_b365 = s.execute(text("SELECT count(*) FROM matches_raw WHERE b365_ch IS NOT NULL AND b365_cd IS NOT NULL AND b365_ca IS NOT NULL")).scalar()
print(f"With B365 closing: {with_b365}")

# B365 but NO avg
b365_only = s.execute(text("SELECT count(*) FROM matches_raw WHERE b365_ch IS NOT NULL AND avg_h IS NULL")).scalar()
print(f"B365 only (no avg): {b365_only}")

# Avg but NO B365
avg_only = s.execute(text("SELECT count(*) FROM matches_raw WHERE avg_h IS NOT NULL AND b365_ch IS NULL")).scalar()
print(f"Avg only (no B365): {avg_only}")

with_shots = s.execute(text("SELECT count(*) FROM matches_raw WHERE hs IS NOT NULL AND as_shots IS NOT NULL")).scalar()
print(f"With shot stats: {with_shots}")

with_ht = s.execute(text("SELECT count(*) FROM matches_raw WHERE hthg IS NOT NULL AND htag IS NOT NULL")).scalar()
print(f"With HT data: {with_ht}")

leagues = s.execute(text("SELECT div, count(*) FROM matches_raw GROUP BY div ORDER BY count(*) DESC")).fetchall()
print("\nLeagues:")
for l in leagues:
    print(f"  {l[0]}: {l[1]}")

dates = s.execute(text("SELECT MIN(date), MAX(date) FROM matches_raw")).fetchone()
print(f"\nDate range: {dates[0]} to {dates[1]}")

# FTR distribution
ftr = s.execute(text("SELECT ftr, count(*) FROM matches_raw GROUP BY ftr ORDER BY ftr")).fetchall()
print("\nFTR distribution:")
for r in ftr:
    print(f"  {r[0]}: {r[1]} ({r[1]/total*100:.1f}%)")

# Odds coverage by year
print("\nOdds by year:")
rows = s.execute(text("""
    SELECT EXTRACT(YEAR FROM date)::int as yr,
           count(*) as total,
           count(avg_h) as with_avg,
           count(b365_ch) as with_b365
    FROM matches_raw 
    GROUP BY EXTRACT(YEAR FROM date)::int 
    ORDER BY yr
""")).fetchall()
for r in rows:
    print(f"  {r[0]}: total={r[1]}, avg={r[2]}, b365={r[3]}")

# Check if we can recover odds from B365 where avg is missing
recover = s.execute(text("""
    SELECT count(*) FROM matches_raw 
    WHERE avg_h IS NULL AND b365_ch IS NOT NULL
""")).scalar()
print(f"\nRecoverable matches (b365 -> avg fallback): {recover}")

s.close()
