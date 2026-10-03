"""Minimal OpenRouter client that enforces the assessment limits."""
import os
import time

import requests

URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_REQUESTS = 10
MAX_COMPLETION_TOKENS = 30000
TIME_LIMIT_S = 600


class BudgetExceeded(RuntimeError):
    pass


class LLM:
    def __init__(self, model: str, trace, t0: float, reasoning: str = "low"):
        self.model = model
        self.trace = trace
        self.t0 = t0
        self.key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        self.reasoning = reasoning  # "low" | "minimal" | "none" | "off" (off = do not send the parameter)
        self.requests = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.deadline = t0 + TIME_LIMIT_S - 45  # leave room for checks and writing

    def remaining_time(self) -> float:
        return self.deadline - time.time()

    def remaining_completion(self) -> int:
        return MAX_COMPLETION_TOKENS - self.completion_tokens

    def chat(self, system: str, user: str, max_tokens: int, stage: str) -> str:
        if not self.key:
            raise RuntimeError("OPENROUTER_API_KEY is not set")
        attempts = 0
        while True:
            if self.requests >= MAX_REQUESTS:
                raise BudgetExceeded("request limit reached")
            budget = min(max_tokens, self.remaining_completion() - 200)
            if budget < 800:
                raise BudgetExceeded("completion-token budget exhausted")
            timeout = self.remaining_time()
            if timeout < 20:
                raise BudgetExceeded("time budget exhausted")
            body = {
                "model": self.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "max_tokens": budget,
                "temperature": 0.2,
                "usage": {"include": True},
            }
            if self.reasoning in ("low", "minimal", "medium", "high"):
                body["reasoning"] = {"effort": self.reasoning, "exclude": True}
            elif self.reasoning == "none":
                body["reasoning"] = {"enabled": False}
            self.requests += 1
            attempts += 1
            t = time.time()
            status, data, err = None, None, None
            try:
                resp = requests.post(URL, json=body, timeout=timeout,
                                     headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json",
                                              "X-Title": "paper-to-playground"})
                status = resp.status_code
                data = resp.json() if resp.content else {}
            except Exception as e:
                err = f"{type(e).__name__}: {e}"
            dt = round(time.time() - t, 2)
            usage = (data or {}).get("usage") or {}
            pt, ct = int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)
            self.prompt_tokens += pt
            self.completion_tokens += ct
            choice = ((data or {}).get("choices") or [{}])[0]
            content = ((choice.get("message") or {}).get("content")) or ""
            if isinstance(content, list):
                content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
            api_err = (data or {}).get("error")
            ok = status == 200 and not api_err and bool(content.strip())
            self.trace.event(stage, "llm_call", "ok" if ok else "error", call=self.requests, attempt=attempts,
                             model=self.model, http_status=status, prompt_tokens=pt, completion_tokens=ct,
                             reasoning_tokens=((usage.get("completion_tokens_details") or {}).get("reasoning_tokens")),
                             cached_tokens=((usage.get("prompt_tokens_details") or {}).get("cached_tokens")),
                             elapsed_s=dt, finish_reason=choice.get("finish_reason"), max_tokens=budget,
                             error=(err or (api_err.get("message") if isinstance(api_err, dict) else api_err)),
                             total_prompt_tokens=self.prompt_tokens, total_completion_tokens=self.completion_tokens)
            if ok:
                return content
            # Retry policy: one retry without the reasoning parameter on a 400, short backoff on 429/5xx/network.
            if attempts >= 3:
                raise RuntimeError(f"LLM call failed: status={status} err={err or api_err}")
            if status == 400 and "reasoning" in body:
                self.reasoning = "off"
                continue
            if status in (429, 500, 502, 503, 504, None) or (status == 200 and not content.strip()):
                time.sleep(min(2.0 * attempts, max(0.0, self.remaining_time() - 30)))
                continue
            raise RuntimeError(f"LLM call failed: status={status} err={err or api_err}")
