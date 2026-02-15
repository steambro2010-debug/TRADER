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
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
cp config.example.yaml config.yaml
python main.py --config config.yaml --input path/to/data.csv --output engine_output.json
```

### Debug mode

```bash
python main.py --config config.yaml --input path/to/data.csv --output engine_output.json --debug
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
