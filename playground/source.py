"""Find the source excerpt. Prefer text supplied in case.json; the URL fetch is only a
best-effort fallback (during assessment only OpenRouter is reachable)."""
import html as htmllib
import re

import requests

EXCERPT_KEYS = ("excerpt", "source_excerpt", "paper_excerpt", "text", "source_text", "paper_text", "context", "content", "passage")
META_KEYS = {"source_url", "focus", "audience", "title", "paper_title", "section", "id", "name"}
MAX_CHARS = 7000  # ~1.8k tokens; hidden excerpts are focused sections


def find_excerpt(case: dict):
    """Return (key, text) for the excerpt field, or (None, '')."""
    for k in case:
        if k.lower() in EXCERPT_KEYS and isinstance(case[k], str) and case[k].strip():
            return k, case[k].strip()
    best = None
    for k, v in case.items():
        if k.lower() in META_KEYS or not isinstance(v, str):
            continue
        if len(v) > 300 and (best is None or len(v) > len(case[best])):
            best = k
    return (best, case[best].strip()) if best else (None, "")


def _html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|nav|header|footer|math)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<annotation[^>]*>(.*?)</annotation>", r" \1 ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    raw = htmllib.unescape(raw)
    return re.sub(r"[ \t\r\f\v]+", " ", re.sub(r"\n\s*\n+", "\n\n", raw)).strip()


_TAIL = re.compile(r"(?im)^\s*(?:\d+\.?\s*)?(references|bibliography|acknowledg(?:e)?ments?)\s*$")


def trim_excerpt(text: str, focus: str, max_chars: int = MAX_CHARS):
    """Drop reference lists/acknowledgements, collapse whitespace, and keep the window that best matches the
    focus (keywords, section and equation numbers). Returns (text, note)."""
    orig = len(text)
    m = _TAIL.search(text)
    if m and m.start() > len(text) * 0.3:
        text = text[:m.start()]
    text = re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", text)).strip()
    if len(text) > max_chars:
        words = {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z\-]{3,}", focus or "")}
        nums = re.findall(r"\b\d+(?:\.\d+)+\b|\(\d+\)", focus or "")
        low, best, best_i = text.lower(), -1, 0
        for i in range(0, len(text) - max_chars + 500, 500):
            win = low[i:i + max_chars]
            sc = sum(win.count(w) for w in words) + sum(25 * win.count(n.lower()) for n in nums)
            if sc > best:
                best, best_i = sc, i
        text = text[best_i:best_i + max_chars]
    return text, ("trimmed %d -> %d chars" % (orig, len(text)) if len(text) < orig else "")


def _window(text: str, focus: str) -> str:
    m = re.search(r"[Ss]ection\s+(\d+(?:\.\d+)*)", focus or "")
    if m:
        num = re.escape(m.group(1))
        hit = re.search(r"(?m)(^|\s)" + num + r"\s+[A-Z][^\n]{2,80}", text)
        if hit:
            start = max(0, hit.start() - 200)
            return text[start:start + MAX_CHARS]
    return text[:MAX_CHARS]


def fetch_excerpt(url: str, focus: str, timeout: float = 3.0):
    """Best effort. Returns (text, note)."""
    if not url or not url.startswith("http"):
        return "", "no URL"
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "paper-to-playground/1.0"})
        resp.raise_for_status()
    except Exception as e:  # network blocked during assessment: expected
        return "", f"fetch failed: {type(e).__name__}"
    ctype = resp.headers.get("content-type", "")
    if "pdf" in ctype or url.lower().endswith(".pdf"):
        try:
            import io
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(resp.content))
            text = "\n".join((pg.extract_text() or "") for pg in reader.pages[:40])
        except Exception as e:
            return "", f"pdf parse failed: {type(e).__name__}"
    else:
        text = _html_to_text(resp.text)
    text = _window(text, focus)
    return text, f"fetched {len(text)} chars"
