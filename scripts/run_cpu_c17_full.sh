#!/usr/bin/env bash
set -euo pipefail
root=/home/abc/supplementary_experiments
cd "$root"
if find /sys/devices/system/cpu/cpufreq -name scaling_governor -type f -exec cat {} \; 2>/dev/null | grep -vxq performance;then
  echo "ERROR: every CPU frequency policy must use the performance governor" >&2
  exit 4
fi
run_id="$(date -u +%Y%m%dT%H%M%SZ)_cpu_c17_full"
out="$root/results_raw/$run_id"
mkdir -p "$out" build/cpu_strict build/cpu_pgo_train profiles
printf '%s\n' "$run_id" > results_raw/LATEST_CPU_C17
common=(-std=c17 -O3 -march=native -mtune=native -flto -fopenmp -DNDEBUG -fno-math-errno -fno-trapping-math -Wall -Wextra -Wpedantic -Wshadow -Wconversion)
gcc "${common[@]}" src_cpu/benchmark_cpu.c -lm -o build/cpu_strict/benchmark_cpu 2>"$out/strict_compile.log"
gcc -std=c17 -O3 -march=native -mtune=native -fopenmp -DNDEBUG -fno-math-errno -fno-trapping-math \
  -fopt-info-vec-all="$out/vectorization.txt" -c src_cpu/benchmark_cpu.c -o build/cpu_strict/vector_check.o
objdump -d -M intel build/cpu_strict/benchmark_cpu > "$out/disassembly.txt"

pgo_dir="$root/build/pgo_data_$run_id"
mkdir -p "$pgo_dir"
gcc "${common[@]}" -fprofile-generate="$pgo_dir" src_cpu/benchmark_cpu.c -lm -o build/cpu_pgo_train/benchmark_cpu 2>"$out/pgo_generate_compile.log"
OMP_PROC_BIND=close OMP_PLACES=cores numactl --physcpubind=0-95 --membind=0 \
  build/cpu_pgo_train/benchmark_cpu "$out/pgo_training_development.csv" 131072 1 1 96 2 >"$out/pgo_training.log"
gcc "${common[@]}" -fprofile-use="$pgo_dir" -fprofile-correction src_cpu/benchmark_cpu.c -lm -o build/cpu_pgo_train/benchmark_cpu 2>"$out/pgo_use_compile.log"

taskset -c 0 build/cpu_strict/benchmark_cpu "$out/strict_serial.csv" 16777216 30 10 1 0 >"$out/strict_serial.log"
taskset -c 0 build/cpu_strict/benchmark_cpu "$out/strict_simd.csv" 16777216 30 10 1 1 >"$out/strict_simd.log"
OMP_PROC_BIND=close OMP_PLACES=cores numactl --physcpubind=0-95 --membind=0 \
  build/cpu_strict/benchmark_cpu "$out/strict_omp96.csv" 16777216 30 10 96 2 >"$out/strict_omp96.log"
OMP_PROC_BIND=close OMP_PLACES=cores numactl --physcpubind=0-95 --membind=0 \
  build/cpu_pgo_train/benchmark_cpu "$out/pgo_omp96.csv" 16777216 30 10 96 2 >"$out/pgo_omp96.log"

{
  printf 'run_id=%s\n' "$run_id"
  printf 'git_commit=%s\n' "$(git rev-parse HEAD)"
  printf 'affinity_serial=cpu0\nparallel_physical_cpus=0-95\nnuma_node=0\nthreads=96\n'
  printf 'governor_cpu0='; cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null || printf 'unavailable\n'
  gcc --version | head -1
  lscpu
  numactl --hardware
} > "$out/hardware_manifest.txt"
sha256sum src_cpu/benchmark_cpu.c manifests/final_scope_no_e8_v1.json > "$out/sha256.txt"
printf 'COMPLETE %s\n' "$run_id" | tee "$out/COMPLETE.txt"
