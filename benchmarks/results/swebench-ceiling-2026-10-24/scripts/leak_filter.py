"""The leak scan's hits less the kinds the review has cleared before (runs/leak-review.md): the instance's own environment
(swebench-run/envs), the session's own saved tool results and background-task output (Claude Code's folders named after
its copy), and path-like fragments of text (two characters around a colon, a URL's tail). What is left is read by hand.

    python leak_filter.py LEAKSCAN.txt
"""

import ast
import re
import sys
from pathlib import Path

CLEARED = re.compile(r"swebench-run/envs/[0-9a-f]+/|/\.claude/projects/C--Users-ozcin-swebench-run-[^/]+/[0-9a-f-]+/"
                     r"(tool-results|tasks)/|AppData/Local/Temp/claude/C--Users-ozcin-swebench-run-[^/]+/[0-9a-f-]+/tasks/|"
                     r"^[a-z]:/[a-z%]*$|^p://|/AppData/Local/Programs/Python$", re.I)
lines = Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
print(lines[0])
left = 0
for line in lines[1:]:
    try:
        iid, arm, tool, text, found = ast.literal_eval(line)
    except (ValueError, SyntaxError):
        print("unparsed:", line[:200])
        continue
    rest = [f for f in found if not CLEARED.search(f.rstrip("\\"))]
    if rest:
        left += 1
        print((iid, arm, tool, text[:300], rest))
print(f"left after the cleared kinds: {left}")
