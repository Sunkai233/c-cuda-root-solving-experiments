#!/usr/bin/env bash
set -euo pipefail
root=/home/abc/supplementary_experiments
multicond_pid="${1:?multi-condition supervisor PID required}"
log="$root/results_raw/algorithm_v2_supervisor_20260824.log"
exec >>"$log" 2>&1
printf 'algorithm v2 supervisor start %s; waiting for pid %s\n' "$(date -u +%FT%TZ)" "$multicond_pid"
while kill -0 "$multicond_pid" 2>/dev/null; do sleep 20; done
test -n "$(find "$root/results_raw" -maxdepth 2 -path '*_openfast_multicondition_v1/COMPLETE.txt' -print -quit)"
printf 'launching complete specialized algorithm matrix %s\n' "$(date -u +%FT%TZ)"
bash "$root/scripts/run_algorithm_matrix_v2_rtx5090.sh"
printf 'complete specialized algorithm matrix finished %s\n' "$(date -u +%FT%TZ)"
