# Institutional-Grade Market Structure Intelligence Engine

This repository now contains a **research-grade structural market model pipeline** (`institutional_engine.py`) designed for regime-aware probabilistic decisions with uncertainty and capital preservation controls.

## Scope

- Input: clean OHLCV data (CSV)
- Multi-timeframe aggregation: `1x, 3x, 5x, 15x, 1h, 4h`
- Structural feature engineering (150+ features generated via multi-window/lag stacks)
- Triple-barrier labeling
- Ensemble model stack (tree branch + temporal branch + calibration)
- Regime-aware decisioning with explicit **NO_TRADE** probability
- Uncertainty-aware filtering
- Risk intelligence + cost-aware backtesting

## Architecture Highlights

### 1) Data Architecture
- Volatility-aware missing candle handling
- Structural gap/anomaly flags
- Log returns, volatility-normalized returns, detrended close
- Fractional differentiation for stationarity-with-memory
- Multi-timeframe aggregation and feature merge

### 2) Structural Features
Implemented feature families:
- Trend/structure: rolling R², Hurst approximation, persistence, CUSUM breaks
- Volatility: multi-window realized vol, vol-of-vol, entropy, ATR stack
- Momentum hierarchy: ROC tree, RSI stack + derivatives, MACD derivatives, lag autocorrelation stack
- Candle microstructure: wick asymmetry, close location, compression/expansion state
- Liquidity/smart-money proxies: sweeps, equal highs/lows, FVG/imbalance, distance-to-level, vacuum probability
- Regime layer: Gaussian-mixture regime clusters + mapped regime tags

### 3) Model Stack
- Tree branch: random-forest surrogate for production tabular branch (configurable)
- Temporal branch: sequential embedding branch (lag summary + multinomial head)
- Ensemble blending + isotonic calibration
- Outputs: `P(long), P(short), P(no-trade), uncertainty`

### 4) Labeling/Validation Foundations
- Triple-barrier labeling with volatility-adjusted barriers
- Time-ordered train/test split (ready for purged walk-forward extension)
- Cost-aware backtest with spread/slippage/latency controls

### 5) Uncertainty + Filtering
- Uncertainty penalization
- Regime-aware dynamic thresholds
- Multi-timeframe agreement gate
- High-uncertainty/high-instability -> force NO_TRADE

### 6) Risk Intelligence
- Kelly-bounded risk multiplier
- Regime-scaled leverage
- Drawdown-aware throttling
- Observation-mode trigger on edge decay conditions

## Usage

1. Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2. Create config:

```bash
cp config.example.yaml config.yaml
```

3. Run pipeline:

```bash
python institutional_engine.py --config config.yaml --input your_ohlcv.csv --output engine_output.json
```

Input CSV columns required:
- `timestamp, open, high, low, close`
- optional: `volume`

## Output Contract

For each decision:
- Regime classification
- Structural bias
- Probability long/short/no-trade
- Uncertainty score
- Risk multiplier
- Confidence percentile
- Recommended position size

## Notes

- This is a research stack template that is intentionally stringent on abstention and capital protection.
- Do not treat this as live investment advice.
