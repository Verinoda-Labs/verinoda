#!/bin/bash
# Amendment 7's closed-book probe: the three models in turn, one call at a time (swebench_closedbook.py skips what each
# OUT already holds, so a restart resumes). Results: swebench-run/closedbook/<model>/results.jsonl
cd /c/Users/ozcin/swebench-data
export PYTHONIOENCODING=utf-8
for m in claude-sonnet-5-5 claude-opus-5-5 claude-fable-5-1; do
  echo "$(date +%H:%M:%S) $m"
  tools-venv/Scripts/python.exe /c/Users/ozcin/Desktop/vwt-ceiling/benchmarks/agent_compare/swebench_closedbook.py \
    "$m" ceiling/tasks-dev.json "C:/Users/ozcin/swebench-run/closedbook/$m"
done
echo "$(date +%H:%M:%S) closed-book probe done"
