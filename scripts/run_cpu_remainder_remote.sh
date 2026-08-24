#!/usr/bin/env bash
set -euo pipefail
root=/home/abc/supplementary_experiments
main_pid="${1:-1527143}"
log="$root/results_raw/cpu_remainder_20260824.log"
exec >>"$log" 2>&1
printf 'remainder supervisor start %s; waiting for pid %s\n' "$(date -u +%FT%TZ)" "$main_pid"
while kill -0 "$main_pid" 2>/dev/null; do sleep 20; done
printf 'main CPU run exited %s\n' "$(date -u +%FT%TZ)"
restore_governor() {
  printf 'restoring governors %s\n' "$(date -u +%FT%TZ)"
  bash "$root/scripts/set_cpu_governor_remote.sh" restore
}
trap restore_governor EXIT
cpu_run="$(cat "$root/results_raw/LATEST_CPU_C17")"
test -f "$root/results_raw/$cpu_run/COMPLETE.txt"
printf 'launching real BEM CPU baseline %s\n' "$(date -u +%FT%TZ)"
bash "$root/scripts/run_bem_real_cpu_frozen.sh"
printf 'launching gated CPU fast-math candidate %s\n' "$(date -u +%FT%TZ)"
bash "$root/scripts/run_cpu_fast_candidate.sh"
printf 'all CPU remainder jobs complete %s\n' "$(date -u +%FT%TZ)"
