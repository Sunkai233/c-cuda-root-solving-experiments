#!/usr/bin/env python3
import argparse,csv,json,math,struct
from pathlib import Path
def q(v,p):v=sorted(v);return v[int(p*(len(v)-1))]
def main():
 p=argparse.ArgumentParser();p.add_argument('--references',type=Path,required=True);p.add_argument('--roots',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();rows=list(csv.DictReader(a.references.open(encoding='utf-8')));data=a.roots.read_bytes();roots=struct.unpack(f'<{len(data)//8}d',data);groups={'all':[],'near_polar_knot':[],'away_from_knot':[],'multi_root_region':[],'single_root_region':[]};fail=[]
 for r in rows:
  e=abs(math.remainder(roots[int(r['source_index'])]-float(r['target_root']),2*math.pi));groups['all'].append(e);groups['near_polar_knot' if float(r['polar_knot_distance_deg'])<=1e-3 else 'away_from_knot'].append(e);groups['multi_root_region' if int(r['root_count_region'])>1 else 'single_root_region'].append(e)
  if not math.isfinite(e) or e>1e-7:fail.append({**r,'computed_root':repr(roots[int(r['source_index'])]),'root_absolute_error':repr(e)})
 summary={'n':len(rows),'failures':len(fail),'observed_pass_fraction':(len(rows)-len(fail))/len(rows),'zero_failure_wilson_95_upper_failure_rate':(1.96**2/(len(rows)+1.96**2)) if not fail else None,'groups':{}}
 for name,v in groups.items():
  summary['groups'][name]={'n':len(v),**({str(x):q(v,x) for x in (.5,.9,.95,.99,.999,1.0)} if v else {})}
 a.out.mkdir(parents=True,exist_ok=True);(a.out/'bem_real_holdout_analysis.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
 with (a.out/'bem_real_holdout_failures.csv').open('w',newline='',encoding='utf-8') as f:
  fields=list(fail[0]) if fail else ['sample_id','computed_root','root_absolute_error'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(fail)
 print(json.dumps(summary,indent=2));raise SystemExit(0 if not fail else 8)
if __name__=='__main__':main()
