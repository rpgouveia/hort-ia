"""Print the market dataset coverage report: `python -m hort_ia.market`."""

from .loader import coverage_report, load_market_dataset

print(coverage_report(load_market_dataset()))
