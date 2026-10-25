#!/bin/bash
# C3's selection (DESIGN_SWEBENCH_CEILING.md, amendments 2, 4 and 9): each attempt as the selector reads it after amendment
# 6's re-runs (merge_attempt.py: C4 Opus's session is the first attempt), then swebench_select.py per arm over the three.
# The selector runs reproductions in the shared environments, so nothing else may run: no session, no evaluation.
#   bash c3_select.sh
T=/c/Users/ozcin/.claude/jobs/df423e2d/tmp
AC=/c/Users/ozcin/Desktop/vwt-ceiling/benchmarks/agent_compare
cd /c/Users/ozcin/swebench-data || exit 1
export PYTHONIOENCODING=utf-8
# the evaluation shells too: between two of their jobs no evaluator runs for a moment
busy=$(powershell -NoProfile -Command "(Get-CimInstance Win32_Process | Where-Object { (\$_.Name -eq 'python.exe' -and \$_.CommandLine -match 'swebench_run|chain4|swebench_localeval|swebench_select|own_run|own_tasks') -or (\$_.Name -eq 'bash.exe' -and \$_.CommandLine -match 'eval_run|eval_gold|regrade_unresolved') } | Measure-Object).Count")
if [ "$busy" != "0" ]; then echo "$(date +%H:%M:%S) not quiet: $busy study processes alive; nothing selected"; exit 1; fi
tools-venv/Scripts/python.exe "$T/merge_attempt.py" c4-opus c3-att-1 || exit 1
tools-venv/Scripts/python.exe "$T/merge_attempt.py" c3-opus-2 c3-att-2 || exit 1
tools-venv/Scripts/python.exe "$T/merge_attempt.py" c3-opus-3 c3-att-3 || exit 1
mkdir -p runs/c3-select
for arm in none verinoda_guided; do
  echo "$(date +%H:%M:%S) selecting, $arm"
  tools-venv/Scripts/python.exe "$AC/swebench_select.py" C:/Users/ozcin/swebench-data ceiling/tasks-dev.json "$arm" \
      "runs/c3-select/select-$arm.jsonl" runs/c3-att-1 runs/c3-att-2 runs/c3-att-3 \
      --copies C:/Users/ozcin/swebench-run/ceiling/copies --workers 2 2>&1 | grep -v -E "_recursion_count|resource_tracker"
done
echo "$(date +%H:%M:%S) selection done"
