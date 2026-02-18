# JARVIS (Windows, Local GPU Assistant)

Production-oriented modular assistant stack with strict tool-call execution and safety gates.

## 1) Capability Stages

- **Stage 1: Voice + Open Apps**
  - Continuous listening with wake word (`jarvis`)
  - STT via Faster-Whisper (CUDA)
  - App launch via desktop module
- **Stage 2: File System Control**
  - Create/move/rename/delete with risk-tier confirmation
- **Stage 3: Vision**
  - Fresh screenshot capture each request
  - OCR + UI summary / next-step suggestion
- **Stage 4: Browser Automation**
  - Playwright search + extraction
- **Stage 5: Messaging**
  - Messaging adapters with confirmation for sends
- **Stage 6: Android Bridge (planned extension)**
  - Add ADB / mobile automation module with same planner contract

## 2) Architecture

```
Voice input -> Wake gate -> STT -> Brain(JSON action) -> Planner
          -> Risk Engine -> Tool Module Execution -> Verification/result
          -> SQLite log -> concise TTS response
```

All actions conform to mandatory format:

```json
{
  "intent": "open_app",
  "risk_level": "low",
  "parameters": {
    "app_name": "FL Studio"
  }
}
```

## 3) Windows Setup

1. Install Python 3.11 (64-bit), Git, and Visual C++ Build Tools.
2. Install CUDA 12.1+ and latest NVIDIA driver.
3. Install Tesseract OCR (default path expected in `config.yaml`).
4. In PowerShell:
   ```powershell
   cd jarvis
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install --upgrade pip
   pip install -r requirements.txt
   playwright install chromium
   ```

## 4) Model Download Steps

Create `jarvis/models/` and place quantized models:

- `Qwen2.5-7B-Instruct-GPTQ-Int4`
- `Qwen2.5-VL-7B-Instruct-GPTQ-Int4`

Use Hugging Face CLI (accept model licenses first):

```powershell
huggingface-cli login
huggingface-cli download <org>/Qwen2.5-7B-Instruct-GPTQ-Int4 --local-dir models/Qwen2.5-7B-Instruct-GPTQ-Int4
huggingface-cli download <org>/Qwen2.5-VL-7B-Instruct-GPTQ-Int4 --local-dir models/Qwen2.5-VL-7B-Instruct-GPTQ-Int4
```

Adjust IDs to your preferred quantized repos.

## 5) Running

One-shot command test:

```powershell
python main.py --once "open chrome"
```

Continuous mode:

```powershell
python main.py
```

## 6) CUDA Configuration and RTX 4070 Optimization

- Use `float16` compute for Whisper and model inference.
- Keep 4-bit quantized Qwen models to fit 8GB VRAM.
- Reserve VRAM budget target:
  - LLM: ~4.5-5.5GB
  - Whisper active window: ~1-1.5GB
  - Headroom for compositor/UI/browser tasks
- Disable unused browser tabs during heavy inference.
- Prefer short context windows and compact prompts.
- Keep `max_new_tokens` bounded (`220` planner / `280` vision summary).
- Use `device_map="auto"` and monitor with `nvidia-smi -l 1`.

## 7) VRAM Management Strategy

- Lazy-load optional modules (vision/browser/messaging) only when first used.
- Use single active generation at a time (serialize heavy GPU tasks).
- Maintain low-latency mode by limiting beam sizes and sampling overhead.
- Apply backoff queue if GPU memory pressure spikes.
- Future: split VLM to on-demand subprocess to reclaim memory between calls.

## 8) Error Handling Strategy

- Every action returns structured status (`ok`, `awaiting_confirmation`, `error`).
- Planner catches module exceptions and logs stack traces.
- SQLite action logs provide audit trail and postmortem source.
- Emergency stop phrase short-circuits pipeline immediately.
- Confirmation flow for MEDIUM/HIGH risk blocks execution until affirmative response.

## 9) Safety

- **LOW**: auto execute
- **MEDIUM**: short confirmation
- **HIGH**: explicit confirmation

High-risk examples include deletes, overwrites, bulk changes, and external sends.

## 10) Extension Hooks

- Add `modules/android.py` and route in planner for Stage 6.
- Add FastAPI control plane (optional) for remote local network command injection with auth.
- Replace placeholder messaging adapter with Gmail OAuth2 + WhatsApp web state manager.
