#!/bin/bash
# Amendment 2's quiet-machine regrade for every run of the dev study and of the diagnostics (amendment 10 takes its lists
# again after it), one after another (regrade_unresolved.sh RUN ARM: each unresolved row once more, into
# eval-ARM-regrade.jsonl). Refuses to start while a session, an orchestrator, an evaluation or the own-repo study runs.
# Log: regrade-all.log beside this file.
#   bash regrade_all.sh
T=/c/Users/ozcin/.claude/jobs/df423e2d/tmp
cd /c/Users/ozcin/swebench-data || exit 1
# the evaluation shells too: between two of their jobs no evaluator runs for a moment
busy=$(powershell -NoProfile -Command "(Get-CimInstance Win32_Process | Where-Object { (\$_.Name -eq 'python.exe' -and \$_.CommandLine -match 'swebench_run|chain4|swebench_localeval|swebench_select|own_run|own_tasks') -or (\$_.Name -eq 'bash.exe' -and \$_.CommandLine -match 'eval_run|eval_gold|regrade_unresolved') } | Measure-Object).Count")
if [ "$busy" != "0" ]; then echo "$(date +%H:%M:%S) not quiet: $busy study processes alive; nothing regraded"; exit 1; fi
for run in c0-s1 c0-s1-r1 c1-s1 c1-s1-r1 c1-s1-r2 c4-opus c4-opus-r1 c4-opus-r2 c4-fable c4-fable-r1 c4-fable-r2 \
           c3-opus-2 c3-opus-2-r1 c3-opus-2-r2 c3-opus-3 c3-opus-3-r1 c3-opus-3-r2 \
           diag-hints diag-hints-r1 diag-hints-r2 diag-tests diag-tests-r1 diag-tests-r2; do
  for arm in none verinoda_guided; do
    [ -f "runs/$run/eval-$arm.jsonl" ] || continue
    echo "$(date +%H:%M:%S) $run $arm"
    bash "$T/regrade_unresolved.sh" "$run" "$arm" 2>&1 | grep -v -E "_recursion_count|resource_tracker|^Traceback|^Exception ignored"
  done
done
echo "$(date +%H:%M:%S) regrade done"
