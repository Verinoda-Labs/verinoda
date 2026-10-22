#!/bin/bash
# usage: lintcmp.sh BASE file... : the ruff finding set (rule + message) of each file against BASE
base=$1; shift
rc=0
for f in "$@"; do
  a=$(git show "$base:$f" 2>/dev/null | .venv/Scripts/ruff.exe check --stdin-filename "$f" --output-format concise --no-cache - 2>/dev/null | grep -v "^Found\|^All\|fixable\|^No fixes" | sed -E 's/^[^:]+:[0-9]+:[0-9]+: //' | sort)
  b=$(.venv/Scripts/ruff.exe check "$f" --output-format concise --no-cache 2>/dev/null | grep -v "^Found\|^All\|fixable\|^No fixes" | sed -E 's/^[^:]+:[0-9]+:[0-9]+: //' | sort)
  if [ "$a" == "$b" ]; then echo "same: $f"; else echo "DIFF: $f"; diff <(echo "$a") <(echo "$b"); rc=1; fi
done
exit $rc
