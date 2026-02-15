from __future__ import annotations

import argparse
import importlib
import json
import traceback

from logger import get_logger


REQUIRED_DEPS = ["numpy", "pandas", "yaml", "sklearn"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Institutional Market Structure Intelligence Engine")
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--input", help="Path to OHLCV CSV")
    p.add_argument("--output", default="engine_output.json")
    p.add_argument("--example-csv", action="store_true")
    p.add_argument("--debug", action="store_true")
    return p.parse_args()


def _check_dependencies() -> None:
    missing = []
    for mod in REQUIRED_DEPS:
        try:
            importlib.import_module(mod)
        except Exception:
            missing.append(mod)
    if missing:
        raise SystemExit(
            "Missing Python dependencies: "
            + ", ".join(missing)
            + "\nInstall with: pip install -r requirements.txt"
        )


def write_example_csv(path: str = "example_ohlcv.csv"):
    import numpy as np
    import pandas as pd

    ts = pd.date_range("2024-01-01", periods=180, freq="1min", tz="UTC")
    base = 100 + np.cumsum(np.random.normal(0, 0.05, len(ts)))
    df = pd.DataFrame(
        {
            "timestamp": ts,
            "open": base,
            "high": base + np.random.uniform(0.02, 0.08, len(ts)),
            "low": base - np.random.uniform(0.02, 0.08, len(ts)),
            "close": base + np.random.normal(0, 0.03, len(ts)),
            "volume": np.random.randint(50, 400, len(ts)),
        }
    )
    df.to_csv(path, index=False)


def main():
    log = get_logger("main")
    args = parse_args()

    _check_dependencies()

    if args.example_csv:
        write_example_csv()
        print("Wrote example_ohlcv.csv. Run with --input example_ohlcv.csv")
        return

    if not args.input:
        raise SystemExit("Missing --input. Use --example-csv to generate sample data.")

    try:
        from config.settings import load_settings
        from pipeline import MarketIntelligencePipeline

        settings = load_settings(args.config)
        if args.debug:
            settings.raw.setdefault("debug", {})["enabled"] = True
        pipeline = MarketIntelligencePipeline(settings)
        payload = pipeline.run(args.input, args.output)
        print(json.dumps(payload["metrics"], indent=2))
    except Exception as exc:
        log.exception(f"Pipeline failed: {exc}")
        print(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
