# Candlestick Vision Predictor (Standalone Python App)

This project is an **analysis-only** desktop application that captures a user-selected chart region, extracts approximate OHLC candles with computer vision, computes indicators, and predicts next-candle direction with an ensemble model.

## Safety

- No broker automation
- No clicks/order placement
- No software injection/control
- Analysis-only workflow

## Features Implemented

1. **Screen Capture Module**
   - High-speed capture using `mss` (fallback `pyautogui`)
   - Manual ROI selection
   - Configured for 5–10 FPS (`capture_fps=8` default)

2. **Candle Detection (OpenCV)**
   - Color segmentation for green/red bodies
   - Wick/body approximation from contour geometry
   - Bullish/bearish classification
   - Pixel-to-relative-price normalization
   - Tracks last 50+ candles (up to configurable max)

3. **Feature Engineering**
   - RSI
   - EMA (9, 21, 50)
   - MACD + signal
   - Bollinger Bands
   - ATR
   - Basic candle pattern flags (doji/hammer)

4. **Model Architecture (Ensemble)**
   - Random Forest
   - XGBoost (optional if installed)
   - LSTM (optional TensorFlow)
   - Weighted averaging outputs:
     - Bullish probability
     - Bearish probability
     - Confidence score

5. **UI (Tkinter)**
   - Live chart reconstruction (last 50 candles)
   - Prediction and probability display
   - Confidence bar
   - Training mode toggle

6. **Performance**
   - Multithreaded design:
     - Thread 1: screen capture
     - Thread 2: CV processing + features
     - Thread 3: inference
   - Optional GPU support via TensorFlow/XGBoost if available in environment

7. **Training Mode**
   - Record extracted OHLC/feature rows to CSV
   - Train offline models from extracted data

## Run

```bash
python -m trader_cv_app.main
```

## Notes

- CV candle extraction is heuristic and may need color threshold tuning based on chart theme.
- For best results, use a clean chart area without overlays.
