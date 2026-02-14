# Qxbroker / Quotex CV Bot (Revised)

> ⚠️ Educational / paper-trading only.

This revised version is for your `qxbroker.com` case where you see:
- "Performing security verification"
- "This website uses a security service..."

## What changed in this revision

- Default URL changed to `https://qxbroker.com/en/trade`.
- Added an explicit **manual security verification wait step** before analysis starts.
- Kept in-app login flow (browser opened by app).
- Keeps one-time ROI selection so centering is easier.

## Important note about verification pages

The bot does **not** bypass anti-bot security. You must complete any challenge manually in the opened browser window. After it clears and your chart is visible, press Enter in terminal.

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

If needed, tune:
- `browser.security_wait_timeout_seconds`
- candle color thresholds under `chart`
- `chart.timeframe_seconds`

## Run

```bash
python quotex_cv_bot.py
```

Runtime flow:
1. App opens browser at qxbroker.
2. Complete security verification/login manually.
3. Press Enter in terminal.
4. Drag-select chart area once.
5. Bot starts live analysis.

## Hotkeys

- `S` pause/resume
- `L` toggle CSV logging
- `+/-` adjust alert threshold
- `Q` quit
