# Institutional Market Structure Intelligence Engine

Production-style refactor with a **single deterministic entrypoint** and modular architecture.

## Refactored structure

- `main.py` — single entrypoint, CLI, top-level error handling
- `pipeline.py` — orchestration and strict stage order
- `logger.py` — structured JSON logging
- `config/`
  - `settings.py` — config loader
  - `default.yaml` — baseline config
- `data/loader.py` — data loading, preprocessing, MTF aggregation
- `features/structural.py` — structural feature engineering
- `training/labeling.py` — triple-barrier labels
- `training/validation.py` — walk-forward split logic
- `models/ensemble.py` — ensemble model stack (tree + temporal + calibration)
- `inference/decision.py` — regime-aware decision filtering
- `risk/engine.py` — risk multiplier + guard rails
- `risk/backtest.py` — cost-aware backtest
- `institutional_engine.py` — backward-compatible wrapper to `main.py`

## Execution order (enforced)

1. Load config
2. Load data
3. Preprocess
4. Generate features
5. Generate labels
6. Train model
7. Validate (walk-forward)
8. Backtest (cost-aware)
9. Output diagnostics

Pipeline stops with full traceback if any stage fails.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell:
#   .\.venv\Scripts\Activate.ps1
# Windows CMD:
#   .venv\Scripts\activate.bat
pip install -r requirements.txt
```

## One-click launch (no CSV required)

```bash
python main.py
```

This auto-creates `config.yaml` (from `config.example.yaml` or `config/default.yaml`) and auto-generates `example_ohlcv.csv` if missing, then runs the full pipeline end-to-end.

## Run

```bash
cp config.example.yaml config.yaml
python main.py --config config.yaml --input <path-to-your-ohlcv.csv> --output engine_output.json
```

### Debug mode

```bash
python main.py --config config.yaml --input <path-to-your-ohlcv.csv> --output engine_output.json --debug
```

Debug mode:
- samples smaller dataset
- increases stage logging verbosity
- helps shape/integrity checks

### Generate sample CSV

```bash
python main.py --example-csv
python main.py --config config.yaml --input example_ohlcv.csv --output engine_output.json
```

## Notes

- No code executes on import.
- Entrypoint guard is enforced in both `main.py` and wrapper.
- Structured logs are emitted per stage.


## Label/Ensemble class guarantees

The training pipeline enforces strict 3-class semantics:
- `0 = Short`
- `1 = Long`
- `2 = No-trade`

Safety checks now fail early if:
- label generation does not contain all 3 classes
- any walk-forward training fold drops a class
- ensemble probability output is not shape `(N, 3)`

Tune `training.labeling.neutral_move_mult` (with `pt_mult/sl_mult`) to control no-trade class density.


## Launch troubleshooting

If you just want to verify launch, use `python main.py` (no flags) for one-click bootstrap mode.

If launch fails, run in this order:

```bash
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell:
#   .\.venv\Scripts\Activate.ps1
# Windows CMD:
#   .venv\Scripts\activate.bat
pip install -r requirements.txt
python main.py --example-csv
python main.py --config config.yaml --input example_ohlcv.csv --output engine_output.json --debug
```

If you pass a placeholder input (for example `path/to/data.csv`), `main.py` now auto-generates `example_ohlcv.csv` and runs that file so you can verify the pipeline launches end-to-end.

The labeling stack now enforces 3 classes (`short`, `long`, `no-trade`) and includes fallback controls:
- `training.labeling.min_no_trade_ratio`
- `training.labeling.enforce_three_classes`
- `training.labeling.neutral_move_mult`
