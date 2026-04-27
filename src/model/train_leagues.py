"""
src/model/train_leagues.py
Entraine des modeles specialises par ligue.

Exemples :
  python -m src.model.train_leagues --leagues F1 E0
  python -m src.model.train_leagues --all --quick
"""

import argparse
import json
import logging
from pathlib import Path

from src.database.database import get_session
from src.ingestion.load_historical import LEAGUES, LEAGUE_NAMES
from src.model import train

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

DEFAULT_PRIORITY_LEAGUES = ["F1", "E0", "D1", "SP1", "I1"]


def normalize_league(value: str) -> str:
    raw = value.strip()
    upper = raw.upper()
    if upper in LEAGUE_NAMES:
        return upper

    aliases = {name.lower(): code for code, name in LEAGUE_NAMES.items()}
    code = aliases.get(raw.lower())
    if not code:
        valid = ", ".join([f"{code}={name}" for code, name in LEAGUE_NAMES.items()])
        raise ValueError(f"Ligue inconnue '{value}'. Valeurs possibles : {valid}")
    return code


def configure_for_league_training(quick: bool) -> None:
    """
    Mode quick = utile pour lancer une premiere passe sur plusieurs ligues.
    On garde les arbres + stacking, mais un seul NN pour limiter le temps.
    """
    if not quick:
        return

    train.TRAIN_CONFIG["ensemble_seeds"] = [13]
    train.TRAIN_CONFIG["epochs"] = 180
    train.TRAIN_CONFIG["patience"] = 30
    train.TRAIN_CONFIG["batch_size"] = 128
    logger.info("Mode quick actif : 1 NN, 180 epochs max, patience 30, batch 128.")


def main() -> bool:
    parser = argparse.ArgumentParser(description="Entraine des modeles de prediction ligue par ligue.")
    parser.add_argument("--all", action="store_true", help="Entrainer toutes les ligues ingerees.")
    parser.add_argument(
        "--leagues",
        nargs="*",
        help="Codes ou noms de ligues. Par defaut: F1 E0 D1 SP1 I1.",
    )
    parser.add_argument("--quick", action="store_true", help="Premiere passe plus rapide pour toutes les ligues.")
    parser.add_argument("--dry-run", action="store_true", help="Affiche les volumes par ligue sans entrainer.")
    parser.add_argument("--list", action="store_true", help="Liste les ligues disponibles.")
    parser.add_argument("--min-matches", type=int, default=2500, help="Minimum de matchs par ligue.")
    parser.add_argument(
        "--output-root",
        default=str(train.MODEL_DIR / "leagues"),
        help="Dossier racine des checkpoints par ligue.",
    )
    args = parser.parse_args()

    if args.list:
        for code in LEAGUES:
            print(f"{code}: {LEAGUE_NAMES[code]}")
        return True

    if args.all:
        league_codes = LEAGUES
    elif args.leagues:
        league_codes = [normalize_league(value) for value in args.leagues]
    else:
        league_codes = DEFAULT_PRIORITY_LEAGUES

    configure_for_league_training(args.quick)

    session = get_session()
    try:
        df = train.load_training_data(session)
    finally:
        session.close()

    counts = df["div"].value_counts().to_dict()
    logger.info("Volumes par ligue : %s", {code: counts.get(code, 0) for code in league_codes})

    if args.dry_run:
        for code in league_codes:
            print(f"{code} ({LEAGUE_NAMES.get(code, code)}): {counts.get(code, 0)} matchs")
        return True

    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    summary = []
    for code in league_codes:
        league_output = output_root / code
        logger.info("=" * 80)
        logger.info("Entrainement specialise : %s (%s)", code, LEAGUE_NAMES.get(code, code))
        logger.info("=" * 80)

        ok = train.run_training(
            league_code=code,
            output_dir=league_output,
            min_matches=args.min_matches,
            source_df=df,
        )

        metrics_path = league_output / train.METRICS_PATH.name
        metrics = {}
        if metrics_path.exists():
            with open(metrics_path, "r") as f:
                metrics = json.load(f)

        summary.append({
            "league_code": code,
            "league_name": LEAGUE_NAMES.get(code, code),
            "ok": ok,
            "matches": int(counts.get(code, 0)),
            "test_accuracy": metrics.get("test_accuracy"),
            "market_baseline_test_accuracy": metrics.get("market_baseline_test_accuracy"),
            "best_vs_market_delta": metrics.get("best_vs_market_delta"),
            "best_approach": metrics.get("best_approach"),
        })

    summary_path = output_root / "training_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    logger.info("Resume sauvegarde : %s", summary_path)
    for item in summary:
        logger.info(
            "%s | acc=%s | market=%s | delta=%s | best=%s | ok=%s",
            item["league_code"],
            item["test_accuracy"],
            item["market_baseline_test_accuracy"],
            item["best_vs_market_delta"],
            item["best_approach"],
            item["ok"],
        )

    return all(item["ok"] for item in summary)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
