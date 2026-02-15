# Qxbroker / Quotex CV Bot (Lean Survival Architecture)

> ⚠️ Educational / paper-trading only.

This version removes the heavy model and switches to a **survival-grade architecture**:
- fewer but more robust features
- strong abstention bias
- regime-aware confidence gating
- strict capital-preservation guard

## What changed (major)

- Deleted heavy 5GB memory-bank model and live online weight mutation.
- Added extraction quality scoring (`quality`, `spacing_cv`, candle count).
- Added regime classification (`trend_up`, `trend_down`, `range`, `volatile`, `unknown`).
- Added lean 12-feature model with regime-specific weights and calibrated probabilities.
- Added abstention gate (quality + regime + confidence thresholds).
- Added performance guard to auto-pause when live shadow metrics degrade:
  - max consecutive losses
  - minimum rolling shadow win rate
- Kept dual display:
  - `CURRENT SIGNAL`
  - `NEXT SIGNAL`
  - explicit `Decision: TRADE / ABSTAIN(<reason>)`

## Why this design

The previous heavy architecture risked alpha illusion from overfitting noisy visual extraction.
This design prioritizes:
1. Data quality first
2. Selective signal issuance
3. Edge preservation over trade frequency
4. Automatic risk-off behavior when quality degrades

## qxbroker security verification

If you see:
- "Performing security verification"
- "This website uses a security service..."

Complete verification manually in the opened browser window. The app waits and continues.

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

Most important controls:
- `prediction.min_extraction_quality`
- `prediction.confidence_threshold_by_regime`
- `prediction.allow_volatile_regime`
- `risk.max_consecutive_losses`
- `risk.min_shadow_win_rate`

## Run

```bash
python quotex_cv_bot.py
```

Runtime:
1. Browser opens qxbroker.
2. Complete verification/login.
3. Press Enter in terminal.
4. Select chart ROI once.
5. Bot runs with abstention-first logic.

## Hotkeys

- `S` pause/resume
- `L` logging on/off
- `+/-` alert threshold
- `Q` quit

## Operational policy

If shadow win-rate and guardrails fail consistently, stop live usage and treat the system as research-only until revalidated.
