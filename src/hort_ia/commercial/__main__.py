"""`python -m hort_ia.commercial`: the measured parameters and the coverage of the ladder."""

from ..core.geo import CODE_BY_UF
from ..market import get_market_dataset
from .pricing import NATIONAL_BAND_PCT, PriceComparator
from .reference import ReferenceLevel, UnknownIdError


def main() -> None:
    c = PriceComparator(get_market_dataset())
    print(f"Dataset goes to {c.latest_month} | source: {c.source}")

    print("\nTolerance band per product (median |month-on-month change|, section 5.2)")
    for product_id, band in sorted(c.bands.items(), key=lambda kv: kv[1]):
        print(f"  {product_id:9s} +-{band:.0%}")
    print(f"  national level (fixed, section 5.2)  +-{NATIONAL_BAND_PCT:.0%}")

    print("\nStaleness drift (median |change| after k months, section 5.3)")
    for lag, drift in sorted(c.drift.items()):
        applied = "band widened by it" if lag >= 2 else "normal, band unchanged"
        print(f"  {lag} month(s)  {drift:5.1%}  {applied}")

    print("\nReference level reached per product and UF (section 5.1)")
    header = "  " + "".join(f"{uf:>4s}" for uf in sorted(CODE_BY_UF))
    initial = {ReferenceLevel.LOCAL: "L", ReferenceLevel.REGIONAL: "R", ReferenceLevel.NATIONAL: "N"}
    print(f"  {'':9s}{header}")
    for product_id in sorted(c.dataset.products):
        cells = []
        for uf in sorted(CODE_BY_UF):
            try:
                cells.append(initial[c.compare(product_id, uf=uf).reference_level])
            except UnknownIdError:
                cells.append("-")
        print(f"  {product_id:9s}  " + "".join(f"{cell:>4s}" for cell in cells))
    print("  L = entrepost in the UF, R = median of the macro-region, N = weighted national mean")


main()
