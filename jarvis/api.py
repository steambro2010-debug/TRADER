from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from main import JarvisRuntime


app = FastAPI(title="JARVIS Local Control Plane", version="1.0.0")
runtime = JarvisRuntime("config.yaml")


class CommandPayload(BaseModel):
    text: str
    confirmed: bool = False


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/command")
def command(payload: CommandPayload) -> dict:
    return runtime.process_text_command(payload.text, confirmed=payload.confirmed)
