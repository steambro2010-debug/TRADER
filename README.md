# QuoTex Signal Bot (Python Baseline)

This repository now contains a Python starter implementation for generating `UP`, `DOWN`, and `NO-TRADE` signals from candle streams.

## What is implemented
- `TrendAnalyzer`: EMA + RSI probability model.
- `RiskEngine`: confidence gates, uncertainty filter, cooldown, and daily loss guard.
- `TradingEngine`: orchestrates prediction -> policy -> optional paper execution.
- `PaperBrokerAdapter`: local testing adapter (no real broker calls).

## Run
```bash
PYTHONPATH=src python -m quotex_bot.main --candles-csv examples/candles.csv
```

With paper execution:
```bash
PYTHONPATH=src python -m quotex_bot.main --candles-csv examples/candles.csv --execute
```

## Test
```bash
PYTHONPATH=src python -m unittest discover -s tests -p 'test_*.py'
```

## Notes
- This is a safe baseline for decision support and paper testing.
- Production chart OCR/CV capture and broker APIs should be integrated through dedicated adapters.
