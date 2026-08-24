#!/usr/bin/env bash
set -euo pipefail
cd /home/abc/supplementary_experiments
mkdir -p build/cpu_strict build/cpu_pgo profiles
common=(-std=c17 -O3 -march=native -mtune=native -flto -fopenmp -DNDEBUG -fno-math-errno -fno-trapping-math -Wall -Wextra -Wpedantic -Wshadow -Wconversion)
gcc "${common[@]}" -fopt-info-vec-optimized=profiles/cpu_c17_vectorized.txt \
  -fopt-info-vec-missed=profiles/cpu_c17_vector_missed.txt src_cpu/benchmark_cpu.c -lm -o build/cpu_strict/benchmark_cpu
objdump -d -M intel build/cpu_strict/benchmark_cpu > profiles/cpu_c17_disassembly.txt
build/cpu_strict/benchmark_cpu /tmp/cpu_c17_smoke.csv 2048 2 2 8
printf '%s\n' "compile=PASS" "rows=$(($(wc -l </tmp/cpu_c17_smoke.csv)-1))" 
