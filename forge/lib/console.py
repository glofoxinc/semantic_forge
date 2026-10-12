"""Windows-safe console output (cp1252 cannot print many Unicode symbols)."""
from __future__ import annotations

import sys


def safe_print(*parts: object, sep: str = " ", end: str = "\n") -> None:
    text = sep.join(str(p) for p in parts)
    try:
        print(text, end=end)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        sys.stdout.buffer.write(text.encode(enc, errors="replace") + end.encode(enc))
        sys.stdout.flush()
