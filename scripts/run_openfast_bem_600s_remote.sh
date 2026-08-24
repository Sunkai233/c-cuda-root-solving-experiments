#!/usr/bin/env bash
set -euo pipefail

# Exact two-stage data-generation command used on abc66.  It refuses to
# overwrite the canonical binary outputs.
root=/home/abc/supplementary_experiments
wind_dir="$root/domains/bem/openfast/5MW_Baseline/Wind"
case_dir="$root/domains/bem/openfast/5MW_Land_600s"
turbsim="$root/_deps/openfast_3a9d3f2/build_release/modules/turbsim/turbsim"
openfast="$root/_deps/openfast_3a9d3f2/build_release/glue-codes/openfast/openfast"

cd "$wind_dir"
test ! -e 90m_12mps_twr.bts
wind_start="$(date -u +%FT%TZ)"
"$turbsim" 90m_12mps_twr.inp > turbsim_600s.log 2>&1
wind_end="$(date -u +%FT%TZ)"
{
  echo "source_commit=3a9d3f2"
  echo "start_utc=$wind_start"
  echo "end_utc=$wind_end"
  sha256sum 90m_12mps_twr.inp 90m_12mps_twr.bts
  stat -c 'bts_bytes=%s' 90m_12mps_twr.bts
  grep -E 'Time step|Analysis time|Usable output time|Number of time steps output|Processing complete' 90m_12mps_twr.sum
} | tee turbsim_600s_manifest.txt

cd "$case_dir"
test ! -e 5MW_600s_alpha.outb
run_start="$(date -u +%FT%TZ)"
"$openfast" 5MW_600s_alpha.fst > openfast_600s_alpha.log 2>&1
run_end="$(date -u +%FT%TZ)"
grep -q 'OpenFAST terminated normally' openfast_600s_alpha.log
{
  echo "source_commit=3a9d3f2"
  echo "start_utc=$run_start"
  echo "end_utc=$run_end"
  echo "dt_seconds=0.0125"
  echo "tmax_seconds=600"
  echo "blade_nodes=19"
  echo "blades=3"
  echo "time_steps_excluding_initial=48000"
  echo "root_instances_excluding_initial=2736000"
  sha256sum 5MW_600s_alpha.fst \
    NRELOffshrBsline5MW_Onshore_AeroDyn_noUA_debug.dat \
    NRELOffshrBsline5MW_Onshore_ElastoDyn.dat \
    "$wind_dir/90m_12mps_twr.bts" 5MW_600s_alpha.outb
  stat -c 'outb_bytes=%s' 5MW_600s_alpha.outb
  grep -E 'Total Real Time|Simulation CPU Time|Simulated Time|Time Ratio' openfast_600s_alpha.log
} | tee openfast_600s_alpha_manifest.txt

"/home/abc/miniconda3/envs/of/bin/python" "$root/scripts/analyze_openfast_bem.py" \
  --outb "$case_dir/5MW_600s_alpha.outb" \
  --openfast-io "$root/_deps/openfast_3a9d3f2/openfast_io" \
  --out "$root/results_raw/20260824T050842Z_openfast_bem_600s"
