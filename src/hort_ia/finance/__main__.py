"""`python -m hort_ia.finance`: validation report of the price forecasting methods."""

from ..market import get_market_dataset
from .backtest import HORIZONS, overall
from .forecast import Forecaster
from .models import METHODS


def main() -> None:
    f = Forecaster(get_market_dataset())
    print(f"Series used: {len(f.series)} | latest month in dataset: {f.latest}")
    for h in HORIZONS:
        print(f"\nHorizon {h} month(s)  [MAPE / MAE R$/kg / n]")
        for name in METHODS:
            s = overall(f.backtest, h, name)
            print(f"  {name:15s} {s.mape:6.1%}  {s.mae:5.2f}  {s.n}")
        print("  best per product: " + ", ".join(
            f"{p}={f.best_method(p, h)}" for p in sorted({p for p, _ in f.series})
        ))


main()
