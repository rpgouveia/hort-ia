"""`python -m hort_ia.recommender`: recommendations for a profile, with reasons and exclusions.

Examples:
    uv run python -m hort_ia.recommender --ibge 4106902 --month 11 --small-space --planted tomate
    uv run python -m hort_ia.recommender --region sul --month 3 --previous repolho
"""

import argparse
from datetime import date

from .engine import get_recommender
from .models import Profile, RecommenderError


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m hort_ia.recommender", description=__doc__.splitlines()[0])
    parser.add_argument("--ibge", help="IBGE code of the municipality (7 digits) or UF (2 digits)")
    parser.add_argument("--region", help="macro-region: norte, nordeste, centro_oeste, sudeste, sul")
    parser.add_argument("--month", type=int, default=date.today().month, help="1-12 (default: current month)")
    parser.add_argument("--small-space", action="store_true", help="only crops suited to pots and small spaces")
    parser.add_argument("--planted", default="", help="comma-separated crop ids already in the garden")
    parser.add_argument("--previous", help="last crop of the bed (rotation)")
    args = parser.parse_args()

    try:
        profile = Profile(
            ibge_code=args.ibge,
            region=args.region,
            month=args.month,
            small_space=args.small_space,
            planted=[c.strip() for c in args.planted.split(",") if c.strip()],
            previous_crop=args.previous,
        )
        result = get_recommender().recommend(profile)
    except (ValueError, RecommenderError) as err:
        parser.error(str(err))

    print(f"Region {result.region}, month {result.month}, small space: {result.small_space}")
    for item in result.recommendations:
        print(f"\n{item.rank:2}. {item.crop_name_pt} ({item.score:+.1f})")
        for reason in item.reasons:
            print(f"    + {reason.text}")
        for warning in item.warnings:
            print(f"    ! {warning.text}")
    print("\nExcluded: " + ", ".join(f"{e.crop_id} ({e.reason})" for e in result.excluded))
    for warning in result.warnings:
        print(f"Warning: {warning}")
    print(f"model_version {result.model_version}")


main()
