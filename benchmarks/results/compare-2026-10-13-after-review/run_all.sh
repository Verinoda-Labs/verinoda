#!/usr/bin/env bash
# Rerun the eight public sets on the current branch, no model, --repeat 1, one set after another.
# Mirrors benchmarks/results/compare-2026-10-02/after-fix (which used the same flags).
REPO="C:/Users/ozcin/Desktop/verinoda-symbiosis"
PY="$REPO/.venv/Scripts/python.exe"
OUT="<OUT>"
# upstream Graphify checkout, HEAD = 20a20d30, clean working tree (the baseline's corpus.source <CORPUS>)
GRAPHIFY="C:/Users/ozcin/Desktop/RepoAtlas/upstream-graphify"

cd "$REPO" || exit 1
LOG="$OUT/run_all.log"
echo "[$(date -u +%FT%TZ)] branch=$(git rev-parse --abbrev-ref HEAD) head=$(git rev-parse HEAD)" >> "$LOG"
"$PY" -c "import sys; print('python', sys.version.split()[0])" >> "$LOG"

run_set() {
  local set="$1"; shift
  local t0; t0=$(date +%s)
  echo "[$(date -u +%FT%TZ)] START $set: python -m verinoda.benchmark run $* --questions verinoda/benchmark/questions/$set.json --out $OUT/$set.json --llm none --repeat 1" >> "$LOG"
  timeout 1200 "$PY" -m verinoda.benchmark run "$@" \
      --questions "verinoda/benchmark/questions/$set.json" \
      --out "$OUT/$set.json" --llm none --repeat 1 > "$OUT/$set.log" 2>&1
  local rc=$?
  local t1; t1=$(date +%s)
  echo "[$(date -u +%FT%TZ)] END $set rc=$rc seconds=$((t1 - t0))" >> "$LOG"
}

run_set orders_app        --repo examples/orders_app
run_set orders_app_tr     --repo examples/orders_app
run_set glow_mod          --repo examples/glow_mod
run_set forge_mod         --repo examples/forge_mod
run_set graphify_core     --repo "$GRAPHIFY"
run_set graphify_core_tr  --repo "$GRAPHIFY"
run_set heldout_repoatlas --repo benchmarks/corpora/heldout_repoatlas_7371990
run_set verinoda_user_tr  --repo . --at 3bd1b94a5cfcd8689d423bcb0dafa06974f8769f
echo "[$(date -u +%FT%TZ)] ALL DONE" >> "$LOG"
