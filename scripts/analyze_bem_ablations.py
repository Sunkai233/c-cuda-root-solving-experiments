#!/usr/bin/env python3
"""Bootstrap the frozen BEM LUT, warm-history, condition and scale runs."""
import argparse,csv,json,random,statistics
from pathlib import Path

def q(v,p):s=sorted(v);return s[min(len(s)-1,int(p*(len(s)-1)))]
def ratio(a,b,seed,B):
 r=[x/y for x,y in zip(a,b)];g=random.Random(seed);n=len(r);z=[statistics.median(r[g.randrange(n)] for _ in range(n)) for _ in range(B)];return statistics.median(r),q(z,.025),q(z,.975)
def load(p):return json.loads(p.read_text())
def main():
 p=argparse.ArgumentParser();p.add_argument('--lut',type=Path,required=True);p.add_argument('--warm',type=Path,required=True);p.add_argument('--scale',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--bootstrap',type=int,default=10000);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 rows=[];lut=load(a.lut/'lut.json');binary=load(a.lut/'binary.json')
 for kind,key in [('kernel','kernel_times_ms'),('e2e','end_to_end_times_ms')]:
  med,lo,hi=ratio(binary[key],lut[key],11+len(kind),a.bootstrap);rows.append({'experiment':'lut','condition':'all','timing_kind':kind,'baseline_over_candidate':'binary/lut','ratio_median':med,'ci95_low':lo,'ci95_high':hi,'baseline_fast_fraction':binary['fast_path']/binary['records'],'candidate_fast_fraction':lut['fast_path']/lut['records']})
 names=['baseline_524280','low_wind_075_524280','high_wind_125_524280','turbulent_gust_524280']
 for j,name in enumerate(names):
  cold=load(a.warm/(name+'_cold.json'));warm=load(a.warm/(name+'_warm.json'))
  for kind,key in [('kernel','kernel_times_ms'),('e2e','end_to_end_times_ms')]:
   med,lo,hi=ratio(cold[key],warm[key],101+j+len(kind),a.bootstrap);rows.append({'experiment':'warm_history','condition':name,'timing_kind':kind,'baseline_over_candidate':'cold/warm','ratio_median':med,'ci95_low':lo,'ci95_high':hi,'baseline_fast_fraction':cold['fast_path']/cold['records'],'candidate_fast_fraction':warm['fast_path']/warm['records']})
 with (a.out/'bem_ablation_bootstrap.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
 scale=[]
 for pth in sorted(a.scale.glob('*.json')):
  if pth.name in ('root_comparison.json',):continue
  x=load(pth);scale.append({'dataset':pth.stem,'records':x['records'],'kernel_median_ms':x['kernel_ms_median'],'e2e_median_ms':x['end_to_end_ms_median'],'throughput_roots_s':x['throughput_roots_s'],'fast_fraction':x['fast_path']/x['records'],'fallback_fraction':x['fallback_path']/x['records'],'solver_failures':x['solver_failures'],'reference_column_is_oracle':False})
 with (a.out/'bem_condition_scale_summary.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=scale[0]);w.writeheader();w.writerows(scale)
 summary={'bootstrap_resamples':a.bootstrap,'lut_root_max_difference_rad':load(a.lut/'root_comparison.json')['max_abs_rad'],'ablation_rows':len(rows),'scale_rows':len(scale),'important_caveat':'warm/cold and LUT/binary were sequential runs; intervals quantify repetition noise but not run-order systematic error'}
 (a.out/'bem_ablation_analysis.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
