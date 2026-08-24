#!/usr/bin/env bash
set -euo pipefail

# Create a separate rigid-blade case for a standalone residual whose local
# radius is fully determined by the public blade geometry.  The flexible case
# is preserved unchanged as an aeroelastic reference dataset.
root=/home/abc/supplementary_experiments
src="$root/domains/bem/openfast/5MW_Land_600s"
dst="$root/domains/bem/openfast/5MW_Land_600s_rigid"
openfast="$root/_deps/openfast_3a9d3f2/build_release/glue-codes/openfast/openfast"
wind="$root/domains/bem/openfast/5MW_Baseline/Wind/90m_12mps_twr.bts"
run_dir="$root/results_raw/20260824T054000Z_openfast_bem_rigid_600s"

test ! -e "$dst"
mkdir -p "$dst"
cp "$src/5MW_600s_alpha.fst" "$dst/"
cp "$src/NRELOffshrBsline5MW_Onshore_AeroDyn_noUA_debug.dat" "$dst/"
cp "$src/NRELOffshrBsline5MW_Onshore_ElastoDyn.dat" "$dst/"
cp "$src/NRELOffshrBsline5MW_Onshore_ElastoDyn_Tower.dat" "$dst/"
cp "$src/NRELOffshrBsline5MW_Onshore_ServoDyn.dat" "$dst/"

sed -i -E \
  -e 's/^True([[:space:]]+FlapDOF1)/False\1/' \
  -e 's/^True([[:space:]]+FlapDOF2)/False\1/' \
  -e 's/^True([[:space:]]+EdgeDOF)/False\1/' \
  "$dst/NRELOffshrBsline5MW_Onshore_ElastoDyn.dat"
grep -E 'FlapDOF1|FlapDOF2|EdgeDOF' "$dst/NRELOffshrBsline5MW_Onshore_ElastoDyn.dat" \
  | grep -v '^True'

cd "$dst"
start="$(date -u +%FT%TZ)"
"$openfast" 5MW_600s_alpha.fst > openfast_600s_rigid.log 2>&1
end="$(date -u +%FT%TZ)"
grep -q 'OpenFAST terminated normally' openfast_600s_rigid.log
{
  echo "source_commit=3a9d3f2"
  echo "case=rigid_blade"
  echo "start_utc=$start"
  echo "end_utc=$end"
  echo "dt_seconds=0.0125"
  echo "tmax_seconds=600"
  echo "blade_nodes=19"
  echo "blades=3"
  echo "time_steps_excluding_initial=48000"
  echo "node_states_excluding_initial=2736000"
  echo "ordinary_solved_nodes_per_step=51"
  echo "ordinary_root_instances=2448000"
  sha256sum 5MW_600s_alpha.fst NRELOffshrBsline5MW_Onshore_AeroDyn_noUA_debug.dat \
    NRELOffshrBsline5MW_Onshore_ElastoDyn.dat "$wind" 5MW_600s_alpha.outb
  stat -c 'outb_bytes=%s' 5MW_600s_alpha.outb
  grep -E 'Total Real Time|Simulation CPU Time|Simulated Time|Time Ratio' openfast_600s_rigid.log
} | tee openfast_600s_rigid_manifest.txt

"/home/abc/miniconda3/envs/of/bin/python" "$root/scripts/analyze_openfast_bem.py" \
  --outb "$dst/5MW_600s_alpha.outb" \
  --openfast-io "$root/_deps/openfast_3a9d3f2/openfast_io" \
  --out "$run_dir"
"/home/abc/miniconda3/envs/of/bin/python" "$root/scripts/validate_openfast_legacy_residual.py" \
  --outb "$dst/5MW_600s_alpha.outb" \
  --blade "$root/domains/bem/openfast/5MW_Baseline/NRELOffshrBsline5MW_AeroDyn_blade.dat" \
  --openfast-io "$root/_deps/openfast_3a9d3f2/openfast_io" \
  --out "$run_dir/openfast_residual_audit.json"
cp openfast_600s_rigid.log openfast_600s_rigid_manifest.txt "$run_dir/"
