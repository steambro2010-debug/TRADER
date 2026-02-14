# Qxbroker / Quotex CV Bot (Accuracy-Focused Revision)

> ⚠️ Educational / paper-trading only.

You asked for a more accurate AI model and said model size is not a concern. This revision upgrades the predictor from a simple fixed-rule score into a richer **adaptive feature model**.

## What was improved for accuracy

- Added **multi-feature engineering** from extracted candles:
  - short/medium momentum (`ret1`, `ret3`)
  - body/range ratio
  - EMA spread (fast/slow)
  - RSI-derived momentum
  - rolling volatility
  - short linear trend slope
  - support/resistance distance features
  - pattern and template-match signals
- Added an **adaptive online learner**:
  - stores pending predictions
  - compares predicted direction vs next candle outcome
  - updates model weights incrementally (online learning)
  - displays recent rolling accuracy in overlay
- Expanded logging to include:
  - raw model score
  - recent adaptive accuracy

## Security verification behavior (your qxbroker issue)

If you see:
- "Performing security verification"
- "This website uses a security service..."

The app waits for you to complete it manually in the opened browser. It does **not** bypass anti-bot checks.

## Install

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
```

## Configure

```bash
cp config.example.yaml config.yaml
```

Most important settings:
- `prediction.adaptive_learning_rate`
- `prediction.feature_weights`
- chart color thresholds (`chart.bullish_*`, `chart.bearish_*`)
- `chart.timeframe_seconds`

## Run

```bash
python quotex_cv_bot.py
```

Runtime flow:
1. App opens qxbroker in browser.
2. Complete verification/login manually.
3. Press Enter in terminal.
4. Drag-select chart area once.
5. Bot runs with adaptive model and live accuracy display.

## Hotkeys

- `S` pause/resume
- `L` toggle CSV logging
- `+/-` adjust alert threshold
- `Q` quit
