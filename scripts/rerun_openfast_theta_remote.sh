#!/usr/bin/env bash
set -euo pipefail

# One-time migration from the Alpha-only reference output to the final
# Alpha+Theta reference output.  Existing artifacts are preserved, not deleted.
root=/home/abc/supplementary_experiments
case_dir="$root/domains/bem/openfast/5MW_Land_600s"
wind="$root/domains/bem/openfast/5MW_Baseline/Wind/90m_12mps_twr.bts"
openfast="$root/_deps/openfast_3a9d3f2/build_release/glue-codes/openfast/openfast"
run_dir="$root/results_raw/20260824T050842Z_openfast_bem_600s"

cd "$case_dir"
test -f 5MW_600s_alpha.outb
test ! -e 5MW_600s_alpha_no_theta.outb
mv 5MW_600s_alpha.outb 5MW_600s_alpha_no_theta.outb
mv openfast_600s_alpha.log openfast_600s_alpha_no_theta.log
mv openfast_600s_alpha_manifest.txt openfast_600s_alpha_no_theta_manifest.txt
mv "$run_dir" "${run_dir}_NO_THETA"

start="$(date -u +%FT%TZ)"
"$openfast" 5MW_600s_alpha.fst > openfast_600s_alpha.log 2>&1
end="$(date -u +%FT%TZ)"
grep -q 'OpenFAST terminated normally' openfast_600s_alpha.log
{
  echo "source_commit=3a9d3f2"
  echo "start_utc=$start"
  echo "end_utc=$end"
  echo "dt_seconds=0.0125"
  echo "tmax_seconds=600"
  echo "blade_nodes=19"
  echo "blades=3"
  echo "time_steps_excluding_initial=48000"
  echo "root_instances_excluding_initial=2736000"
  echo "nodal_fields=Vx,Vy,Phi,Alpha,Theta,AxInd,TnInd,Cl,Cd,Cx,Cy,Fl,Fd"
  sha256sum 5MW_600s_alpha.fst NRELOffshrBsline5MW_Onshore_AeroDyn_noUA_debug.dat \
    NRELOffshrBsline5MW_Onshore_ElastoDyn.dat "$wind" 5MW_600s_alpha.outb
  stat -c 'outb_bytes=%s' 5MW_600s_alpha.outb
  grep -E 'Total Real Time|Simulation CPU Time|Simulated Time|Time Ratio' openfast_600s_alpha.log
} | tee openfast_600s_alpha_manifest.txt

"/home/abc/miniconda3/envs/of/bin/python" "$root/scripts/analyze_openfast_bem.py" \
  --outb "$case_dir/5MW_600s_alpha.outb" \
  --openfast-io "$root/_deps/openfast_3a9d3f2/openfast_io" \
  --out "$run_dir"
cp openfast_600s_alpha.log openfast_600s_alpha_manifest.txt "$run_dir/"
cp "$root/domains/bem/openfast/5MW_Baseline/Wind/turbsim_600s.log" \
   "$root/domains/bem/openfast/5MW_Baseline/Wind/turbsim_600s_manifest.txt" "$run_dir/"
sha256sum "$root/scripts/analyze_openfast_bem.py" > "$run_dir/analysis_sha256.txt"
