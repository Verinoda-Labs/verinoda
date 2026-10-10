"""A stand-in for a product that answers on the standard library only (Symbiosis's own query.py is not in this
repository): read every Markdown file, split sentences, rank them by how many of the question's words they share
(a word matches on its first five letters, a crude stem), print the ten best with file:line.

Usage: python stdlib_answer.py KB_DIR "question" [--mem]
"""

import re
import sys
from pathlib import Path

STOP = {"hangi", "neyi", "ne", "için", "ve", "ile", "bir", "bu", "mi", "mı"}
SENT = re.compile(r"(?<=[.!?])\s+")
WORD = re.compile(r"\w+")


def stems(text: str) -> set[str]:
    return {w[:5] for w in WORD.findall(text.casefold()) if w not in STOP and len(w) > 1}


def load(kb: Path) -> list[tuple[str, int, str]]:
    out = []
    for p in sorted(kb.rglob("*.md")):
        lines = p.read_text(encoding="utf-8").splitlines()
        for n, line in enumerate(lines, 1):
            if not line.strip() or line.startswith("#"):
                continue
            for s in SENT.split(line.strip()):
                out.append((p.relative_to(kb).as_posix(), n, s))
    return out


def answer(sents: list[tuple[str, int, str]], question: str, k: int = 10) -> list[tuple[str, int, str]]:
    q = stems(question)
    scored = [(len(q & stems(s)), i, (f, n, s)) for i, (f, n, s) in enumerate(sents)]
    scored = [x for x in scored if x[0] > 0]
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [x[2] for x in scored[:k]]


def peak_mb() -> float:
    import ctypes
    from ctypes import wintypes

    class PMC(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
    k32 = ctypes.WinDLL("kernel32")
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    get = ctypes.WinDLL("psapi").GetProcessMemoryInfo
    get.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
    get.restype = wintypes.BOOL
    c = PMC()
    c.cb = ctypes.sizeof(PMC)
    if not get(k32.GetCurrentProcess(), ctypes.byref(c), c.cb):
        return -1.0
    return c.PeakWorkingSetSize / 2**20


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    kb, question = Path(sys.argv[1]), sys.argv[2]
    for f, n, s in answer(load(kb), question):
        print(f"{f}:{n}  {s}")
    if "--mem" in sys.argv:
        print(f"PEAK_MB {peak_mb():.1f}", file=sys.stderr)
