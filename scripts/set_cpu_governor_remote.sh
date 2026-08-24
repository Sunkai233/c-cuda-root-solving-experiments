#!/usr/bin/env bash
set -euo pipefail
root=/home/abc/supplementary_experiments
mode="${1:-set}"
state="${2:-$root/results_raw/cpu_governor_before_formal_20260824.csv}"
case "$mode" in
  set)
    test ! -e "$state" || { echo "state file already exists: $state" >&2; exit 2; }
    docker run --rm --privileged -v /sys:/hostsys:rw -v "$root:/work" \
      nvidia/cuda:12.8.1-base-ubuntu24.04 bash -lc '
        set -eu
        state=/work/results_raw/cpu_governor_before_formal_20260824.csv
        : > "$state"
        for p in /hostsys/devices/system/cpu/cpufreq/policy*/scaling_governor; do
          printf "%s,%s\n" "${p#/hostsys}" "$(cat "$p")" >> "$state"
          printf "%s\n" performance > "$p"
        done
      '
    ;;
  restore)
    test -f "$state" || { echo "missing state file: $state" >&2; exit 2; }
    docker run --rm --privileged -v /sys:/hostsys:rw -v "$root:/work" \
      nvidia/cuda:12.8.1-base-ubuntu24.04 bash -lc '
        set -eu
        while IFS=, read -r p governor; do printf "%s\n" "$governor" > "/hostsys$p"; done \
          < /work/results_raw/cpu_governor_before_formal_20260824.csv
      '
    ;;
  *) echo "usage: $0 set|restore [state.csv]" >&2; exit 2 ;;
esac
find /sys/devices/system/cpu/cpufreq -name scaling_governor -type f -exec cat {} \; | sort | uniq -c
