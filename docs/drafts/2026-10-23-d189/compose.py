"""What fills a long session's context: characters per category (tool results by tool, tool-call inputs, the
assistant's text, the person's text, attachments by type), images counted apart, compactions, and the context size
the API reported (input + cache writes + cache reads) per model call.

    python compose.py <out.json> <transcript.jsonl> [...]
"""
import json
import sys
from collections import Counter, defaultdict


def text_len(c) -> tuple[int, int]:
    """(characters of text, images) in a tool_result content or a message content."""
    if isinstance(c, str):
        return len(c), 0
    n = imgs = 0
    for x in c or []:
        if not isinstance(x, dict):
            continue
        if x.get("type") == "text":
            n += len(x.get("text") or "")
        elif x.get("type") == "image":
            imgs += 1
        elif x.get("type") == "tool_reference":
            n += len(json.dumps(x))
    return n, imgs


def analyse(path: str) -> dict:
    cat = Counter()
    imgs = Counter()
    pending: dict[str, str] = {}
    seen: set = set()
    ctx: list[int] = []
    compactions = 0
    att_types = Counter()
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                m = json.loads(line)
            except Exception:  # noqa: BLE001 - a cut line
                continue
            t = m.get("type")
            if t == "system" and m.get("subtype") in ("compact_boundary", "microcompact_boundary"):
                compactions += 1
                cat["(compaction summaries)"] += 0
                continue
            if m.get("isCompactSummary"):
                n, _ = text_len((m.get("message") or {}).get("content"))
                cat["compaction summary"] += n
                continue
            if t == "attachment":
                a = m.get("attachment") or {}
                kind = a.get("type") or "?"
                att_types[kind] += 1
                cat[f"attachment:{kind}"] += len(json.dumps(a, ensure_ascii=False))
                continue
            msg = m.get("message") or {}
            content = msg.get("content")
            if t == "assistant":
                if msg.get("id") not in seen and msg.get("usage"):
                    seen.add(msg.get("id"))
                    u = msg["usage"]
                    ctx.append(sum(u.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens",
                                                           "cache_read_input_tokens")))
                for x in content or []:
                    if x.get("type") == "text":
                        cat["assistant text"] += len(x.get("text") or "")
                    elif x.get("type") == "thinking":
                        cat["assistant thinking"] += len(x.get("thinking") or "")
                    elif x.get("type") == "tool_use":
                        name = x.get("name") or "?"
                        pending[x.get("id")] = name
                        cat[f"call input:{name}"] += len(json.dumps(x.get("input"), ensure_ascii=False))
            elif t == "user":
                if isinstance(content, str):
                    cat["user text"] += len(content)
                    continue
                for x in content or []:
                    if x.get("type") == "tool_result":
                        name = pending.get(x.get("tool_use_id"), "?")
                        if name.startswith("mcp__"):
                            name = "mcp:" + name.split("__")[1]
                        n, i = text_len(x.get("content"))
                        cat[f"result:{name}"] += n
                        imgs[f"result:{name}"] += i
                    elif x.get("type") == "text":
                        cat["user text"] += len(x.get("text") or "")
                    elif x.get("type") == "image":
                        imgs["user image"] += 1
    return {"file": path, "calls": len(ctx), "peak_context": max(ctx, default=0),
            "last_context": ctx[-1] if ctx else 0, "compactions": compactions,
            "over_500k": sum(1 for c in ctx if c > 500_000), "chars": dict(cat), "images": dict(imgs),
            "attachment_counts": dict(att_types)}


if __name__ == "__main__":
    out = [analyse(p) for p in sys.argv[2:]]
    json.dump(out, open(sys.argv[1], "w", encoding="utf-8"), indent=1)
    for r in out:
        tot = sum(r["chars"].values())
        print(f"== {r['file'][-60:]}  calls {r['calls']}  peak {r['peak_context']:,}  compactions {r['compactions']}"
              f"  calls>500k {r['over_500k']}  chars {tot:,}  images {sum(r['images'].values())}")
        for k, v in sorted(r["chars"].items(), key=lambda kv: -kv[1])[:14]:
            print(f"   {v / tot:6.1%} {v:12,}  {k}")
