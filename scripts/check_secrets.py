"""Scan the repository for anything that looks like a credential. Exit code 1 if found.

    python scripts/check_secrets.py
"""
import re
import sys
from pathlib import Path

PATTERNS = [
    re.compile(r"\b(PK|AK)[A-Z0-9]{16,}\b"),                 # Alpaca key ids (paper / live)
    re.compile(r"sk-or-v1-[a-f0-9]{20,}"),                    # OpenRouter
    re.compile(r"\bsk-[A-Za-z0-9]{32,}\b"),                   # OpenAI-style
    re.compile(r"['\"][A-Za-z0-9/+]{36,}['\"]"),                 # long quoted secret-like literal
    re.compile(r"(?i)(secret|api[_-]?key|token)['\"]?\s*[:=]\s*['\"][A-Za-z0-9/+_-]{24,}['\"]"),
]
SKIP_DIRS = {".git", "__pycache__", ".venv", "data", ".pytest_cache"}
SKIP_SUFFIX = {".pdf", ".png", ".parquet", ".pyc"}


def scan(root):
    hits = []
    for f in Path(root).rglob("*"):
        if not f.is_file() or any(p in SKIP_DIRS for p in f.parts) or f.suffix in SKIP_SUFFIX:
            continue
        if f.name == "check_secrets.py":
            continue
        try:
            text = f.read_text(errors="ignore")
        except OSError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if any(p.search(line) for p in PATTERNS):
                hits.append((str(f.relative_to(root)), n))
    return hits


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    found = scan(root)
    for f, n in found:
        print(f"possible credential: {f}:{n}")
    print("clean" if not found else f"{len(found)} hit(s)")
    sys.exit(1 if found else 0)
