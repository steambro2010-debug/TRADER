# Quotex CV Trading Assistant (Python + OpenCV)

> ⚠️ Educational and paper-trading use only. This tool can be wrong and should not be used as a guarantee of profit.

A lightweight Python bot that captures a Quotex candlestick chart region, extracts visual candle data, detects common patterns, computes support/resistance, and outputs a real-time **CALL/PUT** prediction with confidence.

## Features

- Real-time screen capture of Quotex chart window.
- OpenCV-based candle extraction from chart colors.
- Visual pattern detection: **Doji**, **Hammer**, **Bullish/Bearish Engulfing**.
- Approximate OHLC extraction from visible candles.
- Support/resistance estimation from visible price action.
- Prediction output:
  - Direction: `CALL` / `PUT`
  - Confidence `%`
  - Countdown to next candle close
- On-screen overlay with arrows/levels and hotkey controls.
- Audio beep on high-confidence signals.
- Optional CSV logging for backtesting.

## Quick Start

1. Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2. Create configuration:

```bash
cp config.example.yaml config.yaml
```

3. Edit `config.yaml`:

- Set your monitor and screen region to the Quotex chart area.
- Set candle colors to match your Quotex theme.
- Set `timeframe_seconds` to your chart interval.

4. Run:

```bash
python quotex_cv_bot.py
```

## Hotkeys

- `S`: Start/Stop predictions
- `+` / `-`: Increase/decrease high-confidence audio alert threshold
- `L`: Toggle CSV logging
- `Q` or `Esc`: Quit

## Calibration Guide (important)

For best results, keep Quotex on **default candlestick chart** and stable zoom.

1. Open Quotex chart in full view.
2. Use a fixed timeframe (e.g. 60s candles) and set `timeframe_seconds` accordingly.
3. Measure chart region coordinates and put them in `config.yaml`.
4. Tune color thresholds:
   - `bullish_bgr_min/max`
   - `bearish_bgr_min/max`
5. Start bot and verify extracted candles visually on overlay.
6. Use paper trading to validate signal quality before any real-money usage.

## Performance Notes

- Reduce `screen.region` size to chart-only area.
- Increase `process_every_n_frames` to lower CPU usage.
- Keep `max_candles` moderate (80–150) for responsiveness.

## Risk Management Suggestions

- Add max trades/day and max loss/day limits before live use.
- Require minimum confidence and trend confirmation.
- Avoid trading during volatile news windows.

## Compatibility

- Tested for desktop platforms where Python/OpenCV screen capture works (Windows/Linux/macOS).
- On Windows, `winsound` is used for alert tones; on other OSes terminal bell is used.

