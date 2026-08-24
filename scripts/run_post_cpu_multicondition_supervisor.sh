#!/usr/bin/env bash
set -euo pipefail
root=/home/abc/supplementary_experiments
cpu_remainder_pid="${1:?CPU remainder PID required}"
log="$root/results_raw/openfast_multicondition_supervisor_20260824.log"
exec >>"$log" 2>&1
printf 'multicondition supervisor start %s; waiting for pid %s\n' "$(date -u +%FT%TZ)" "$cpu_remainder_pid"
while kill -0 "$cpu_remainder_pid" 2>/dev/null; do sleep 20; done
cpu_run="$(cat "$root/results_raw/LATEST_CPU_C17")"
test -f "$root/results_raw/$cpu_run/COMPLETE.txt"
test -n "$(find "$root/results_raw" -maxdepth 2 -path '*_bem_real_cpu_frozen/COMPLETE.txt' -print -quit)"
test -n "$(find "$root/results_raw" -maxdepth 2 -path '*_cpu_fast_candidate/COMPLETE.txt' -print -quit)"
printf 'launching OpenFAST multi-condition experiment %s\n' "$(date -u +%FT%TZ)"
bash "$root/scripts/run_openfast_multicondition_remote.sh"
printf 'OpenFAST multi-condition experiment complete %s\n' "$(date -u +%FT%TZ)"
