#!/usr/bin/env python3
"""One tiny OpenRouter call to confirm the API key and model work.

Usage:  python tools/smoke_test.py [MODEL_ID]
Reads OPENROUTER_API_KEY from the environment or .env. Never prints the key.
"""
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
model = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-v4.1-flash")
key = os.environ.get("OPENROUTER_API_KEY", "").strip()
if not key.startswith("sk-or-"):
    sys.exit("OPENROUTER_API_KEY is not set: put your key in .env")
r = requests.post("https://openrouter.ai/api/v1/chat/completions", timeout=60,
                  headers={"Authorization": "Bearer " + key},
                  json={"model": model, "max_tokens": 20, "reasoning": {"enabled": False},
                        "messages": [{"role": "user", "content": "Reply with exactly: pong"}]})
d = r.json()
print("status", r.status_code, "model", d.get("model"), "reply", ((d.get("choices") or [{}])[0].get("message") or {}).get("content"),
      "usage", d.get("usage"), "error", d.get("error"))
