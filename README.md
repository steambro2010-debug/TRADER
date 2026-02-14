# Quotex CV Bot (Login Inside App)

> ⚠️ For education / paper-trading only. Do **not** assume predictions are profitable.

This version fixes the "centering" problem by letting you log in directly from the app-controlled browser and then select the chart area once with your mouse.

## What changed

- Opens Quotex in a browser launched by the app (you log in there directly).
- No manual desktop coordinate hunting needed.
- One-time ROI selector (`cv2.selectROI`) for chart area alignment.
- Real-time prediction overlay with CALL/PUT, confidence, timer.
- Audio alerts + hotkeys + CSV logging.

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

Adjust:
- `chart.timeframe_seconds` to your candle duration.
- candle color thresholds if your theme differs.

## Run

```bash
python quotex_cv_bot.py
```

Flow:
1. App opens Quotex in Chromium.
2. Log in from that browser window.
3. Press Enter in terminal.
4. Drag-select chart region once.
5. Bot starts analysis/overlay.

## Hotkeys

- `S`: pause/resume predictions
- `L`: toggle logging
- `+/-`: alert threshold up/down
- `Q` / `Esc`: quit

## Notes

- Template matching is included as a lightweight candle-shape score.
- Support/resistance + trend + pattern are combined into confidence.
- Always test with paper trading first.

