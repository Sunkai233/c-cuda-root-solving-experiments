#!/usr/bin/env bash
set -euo pipefail

root=/home/abc/supplementary_experiments
case_dir="$root/domains/bem/openfast/5MW_Land_600s_rigid_noskew"
openfast="$root/_deps/openfast_3a9d3f2/build_release/glue-codes/openfast/openfast"
run_dir="$root/results_raw/20260824T055500Z_openfast_bem_rigid_noskew_geomflag"

cd "$case_dir"
test -f 5MW_600s_alpha.outb
test ! -e 5MW_600s_alpha_no_geomflag.outb
mv 5MW_600s_alpha.outb 5MW_600s_alpha_no_geomflag.outb
mv openfast_600s_rigid_noskew.log openfast_600s_rigid_noskew_no_geomflag.log
mv openfast_600s_rigid_noskew_manifest.txt openfast_600s_rigid_noskew_no_geomflag_manifest.txt
python3 - <<'PY'
from pathlib import Path
p = Path("NRELOffshrBsline5MW_Onshore_AeroDyn_noUA_debug.dat")
s = p.read_text()
needle = '"TnInd"\n'
if '"GeomPhi"\n' not in s:
    p.write_text(s.replace(needle, needle+'"GeomPhi"\n', 1))
PY

start="$(date -u +%FT%TZ)"
"$openfast" 5MW_600s_alpha.fst > openfast_600s_rigid_noskew.log 2>&1
end="$(date -u +%FT%TZ)"
grep -q 'OpenFAST terminated normally' openfast_600s_rigid_noskew.log
{
  echo "source_commit=3a9d3f2"
  echo "case=rigid_blade_noskew_geomflag"
  echo "start_utc=$start"
  echo "end_utc=$end"
  sha256sum 5MW_600s_alpha.fst NRELOffshrBsline5MW_Onshore_AeroDyn_noUA_debug.dat \
    NRELOffshrBsline5MW_Onshore_ElastoDyn.dat 5MW_600s_alpha.outb
  stat -c 'outb_bytes=%s' 5MW_600s_alpha.outb
  grep -E 'Total Real Time|Simulation CPU Time|Simulated Time|Time Ratio' openfast_600s_rigid_noskew.log
} | tee openfast_600s_rigid_noskew_manifest.txt

"/home/abc/miniconda3/envs/of/bin/python" "$root/scripts/analyze_openfast_bem.py" \
  --outb "$case_dir/5MW_600s_alpha.outb" \
  --openfast-io "$root/_deps/openfast_3a9d3f2/openfast_io" \
  --out "$run_dir"
"/home/abc/miniconda3/envs/of/bin/python" "$root/scripts/validate_openfast_legacy_residual.py" \
  --outb "$case_dir/5MW_600s_alpha.outb" \
  --blade "$root/domains/bem/openfast/5MW_Baseline/NRELOffshrBsline5MW_AeroDyn_blade.dat" \
  --openfast-io "$root/_deps/openfast_3a9d3f2/openfast_io" \
  --out "$run_dir/openfast_residual_audit.json"
cp openfast_600s_rigid_noskew.log openfast_600s_rigid_noskew_manifest.txt "$run_dir/"
