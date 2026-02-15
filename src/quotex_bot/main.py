from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from quotex_bot.broker import PaperBrokerAdapter
from quotex_bot.engine import TradingEngine
from quotex_bot.models import Candle


def load_candles(csv_path: Path) -> list[Candle]:
    candles: list[Candle] = []
    with csv_path.open("r", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            candles.append(
                Candle(
                    timestamp=float(row["timestamp"]),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row.get("volume", 0.0)),
                )
            )
    return candles


def main() -> None:
    parser = argparse.ArgumentParser(description="QuoTex signal generator (paper mode)")
    parser.add_argument("--candles-csv", required=True, type=Path, help="Path to OHLC candles CSV")
    parser.add_argument("--execute", action="store_true", help="Place paper trades")
    args = parser.parse_args()

    candles = load_candles(args.candles_csv)
    broker = PaperBrokerAdapter()
    broker.connect()
    engine = TradingEngine.default(broker)

    decision, order = engine.on_candles(candles, execute=args.execute)
    print(
        json.dumps(
            {
                "signal": decision.signal.value,
                "confidence": round(decision.confidence, 4),
                "reason": decision.reason,
                "order": None
                if order is None
                else {
                    "order_id": order.order_id,
                    "won": order.won,
                    "pnl": order.pnl,
                },
            }
        )
    )


if __name__ == "__main__":
    main()
