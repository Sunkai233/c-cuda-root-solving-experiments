#!/usr/bin/env bash
set -euo pipefail
root=/home/abc/supplementary_experiments;cd "$root"
if find /sys/devices/system/cpu/cpufreq -name scaling_governor -type f -exec cat {} \; 2>/dev/null | grep -vxq performance;then echo "all governors must be performance" >&2;exit 4;fi
out="results_raw/$(date -u +%Y%m%dT%H%M%SZ)_bem_real_cpu_frozen";mkdir -p "$out" build/cpu_strict
gcc -std=c17 -O3 -march=native -mtune=native -flto -fopenmp -DNDEBUG -fno-math-errno -fno-trapping-math -Wall -Wextra -Wpedantic -Iinclude src_c/benchmark_bem_real_frozen_cpu.c -lm -o build/cpu_strict/benchmark_bem_real_frozen 2>"$out/compile.log"
gcc -std=c17 -O3 -march=native -mtune=native -flto -DNDEBUG -fno-math-errno -fno-trapping-math -Wall -Wextra -Wpedantic -Iinclude src_c/validate_bem_real_cpu.c -lm -o build/cpu_strict/validate_bem_real_cpu 2>"$out/validation_compile.log"
if taskset -c 0 build/cpu_strict/validate_bem_real_cpu references/bem_real_ref_v1_20260824/bem_real_reference.csv "$out/validation" | tee "$out/validation.log";then echo BEM_CPU_VALIDATION_PASS >"$out/VALIDATION_STATUS.txt";else echo BEM_CPU_VALIDATION_FAIL >"$out/VALIDATION_STATUS.txt";fi
data=results_raw/20260824T060500Z_bem_real_dataset_v2/bem_real_f64_soa.bin
taskset -c 0 build/cpu_strict/benchmark_bem_real_frozen "$data" "$out/serial.csv" 1 strict | tee "$out/serial.log"
OMP_PROC_BIND=close OMP_PLACES=cores numactl --physcpubind=0-95 --membind=0 build/cpu_strict/benchmark_bem_real_frozen "$data" "$out/omp96.csv" 96 strict | tee "$out/omp96.log"
{ gcc --version|head -1;lscpu;numactl --hardware; } >"$out/hardware.txt";sha256sum src_c/benchmark_bem_real_frozen_cpu.c src_c/validate_bem_real_cpu.c include/bem_real_solver.h references/bem_real_ref_v1_20260824/* "$data" >"$out/sha256.txt";echo "COMPLETE $out"|tee "$out/COMPLETE.txt"
