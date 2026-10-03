#!/usr/bin/env python3
"""One tiny OpenRouter call to confirm the API key and model work.

Usage:  python tools/smoke_test.py [MODEL_ID]
Reads OPENROUTER_API_KEY (and optionally OPENROUTER_MODEL) from the environment or .env.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
model = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-v4.1-flash")
key = os.environ.get("OPENROUTER_API_KEY", "").strip()
if not key or key == "PASTE_KEY_HERE":
    sys.exit("OPENROUTER_API_KEY is not set: put your key in .env")

client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)
resp = client.chat.completions.create(model=model, max_tokens=20,
                                      messages=[{"role": "user", "content": "Reply with exactly: pong"}])
print(f"model={resp.model} reply={resp.choices[0].message.content!r} usage={resp.usage}")
