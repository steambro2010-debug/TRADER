# Quotex Vision-Driven Trading Intelligence Engine

## Overview
This build uses **region-based screen capture + computer vision** to reconstruct OHLC candles from the Quotex chart.
The vision stack is engineered for low CPU, long runtime stability, and thread-safe AI triggering.

## Data Acquisition Architecture
- `data_capture/capture.py` — MSS region capture (10–15 FPS), user region selection, background thread.
- `data_capture/vision.py` — grayscale + blur + Canny + contour filtering pipeline for candle body/wick detection.
- `data_capture/candle_tracker.py` — rightmost-candle tracking + candle-shift closure logic.
- `data_capture/data_buffer.py` — validated rolling OHLC buffer (1000 default) with smoothing.
- `core/ai_engine.py` — indicator + model inference engine (trigger on candle close or interval).
- `core/orchestrator.py` — thread-safe orchestration, UI signal emission, debug mode overlay.

## CV Pipeline
1. Capture only chart ROI (saved in `config.json`).
2. Convert frame to grayscale.
3. Gaussian blur.
4. Canny edges.
5. Contour detection + shape filtering (ratio, min height, body width constraints).
6. Wick/body extraction for pixel OHLC.
7. Track rightmost candle; finalize previous candle when chart shifts.
8. Validate/smooth OHLC and append to rolling buffer.

## Runtime Guarantees
- Capture thread is separate from processing/UI.
- AI receives only stable finalized OHLC data.
- Buffer is never reset during updates.
- Prediction runs on new candle close or periodic timer.
- Debug mode can show overlays + processing time.

## Run
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

On first run, select chart ROI once. Region is persisted to config.

## Debug Mode
Set `runtime.debug_vision=true`:
- Candle outlines
- Wick lines
- Buffer count
- Frame processing ms

## Disclaimer
Binary options are high-risk. This tool is for research/education only.
