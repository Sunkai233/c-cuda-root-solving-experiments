#!/usr/bin/env bash
set -euo pipefail
cd /home/abc/supplementary_experiments
nohup bash scripts/run_cpu_c17_full.sh > /tmp/supplementary_cpu_c17_full_launcher.log 2>&1 &
printf 'pid=%s\n' "$!"
