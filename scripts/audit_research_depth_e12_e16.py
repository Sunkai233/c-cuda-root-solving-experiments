#!/usr/bin/env python3
import argparse,csv,hashlib,json
from pathlib import Path

def rows(path): return list(csv.DictReader(path.open(encoding="utf-8")))
def main():
    p=argparse.ArgumentParser();p.add_argument("--root",type=Path,default=Path("."));p.add_argument("--run",type=Path,required=True);p.add_argument("--processed",type=Path,required=True);p.add_argument("--out",type=Path,required=True);a=p.parse_args();root=a.root;run=root/a.run;processed=root/a.processed;checks=[]
    def check(name,ok,detail):checks.append({"name":name,"pass":bool(ok),"detail":str(detail)})
    check("formal COMPLETE",(run/"COMPLETE.txt").is_file(),run/"COMPLETE.txt")
    marker=root/"manifests/TEST_SPLIT_EXECUTED_certificate_v1_20260825.txt";check("one-shot marker",marker.is_file(),marker)
    manifest=json.loads((root/"manifests/frozen_certificate_goal_routing_v1.json").read_text(encoding="utf-8"));ref=root/manifest["frozen_test"]["path"];sha=hashlib.sha256(ref.read_bytes()).hexdigest();check("frozen reference SHA-256",sha==manifest["frozen_test"]["csv_sha256"],sha)
    analysis=json.loads((processed/"analysis.json").read_text(encoding="utf-8"));
    for key,value in analysis["acceptance"].items():check(key,value,value)
    check("performance methods",len(list((run/"performance").glob("method_*.json")))==5,len(list((run/"performance").glob("method_*.json"))))
    check("goal configurations",len(list((run/"goal").glob("*.json")))==8,len(list((run/"goal").glob("*.json"))))
    check("routing configurations",len(list((run/"routing").glob("*.json")))==45,len(list((run/"routing").glob("*.json"))))
    check("performance 30 repetitions",all(json.loads(x.read_text(encoding="utf-8"))["repetitions"]==30 for x in (run/"performance").glob("*.json")),"5 files")
    check("routing 30 repetitions",all(json.loads(x.read_text(encoding="utf-8"))["repetitions"]==30 for x in (run/"routing").glob("*.json")),"45 files")
    check("goal 30 repetitions",all(len(json.loads(x.read_text(encoding="utf-8"))["times_ms"])==30 for x in (run/"goal").glob("*.json")),"8 files")
    test=rows(run/"certificate_test/certificate_summary.csv");check("test certificate groups",len(test)==9,len(test))
    adaptive=rows(run/"certificate_test/certificate_adaptive_samples.csv");check("new frozen test size",len(adaptive)==1000,len(adaptive))
    result={"scope":"E12-E16 research-depth extension","passed":sum(x["pass"] for x in checks),"total":len(checks),"all_pass":all(x["pass"] for x in checks),"checks":checks};a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2),encoding="utf-8");print(json.dumps({k:result[k] for k in ("scope","passed","total","all_pass")}));return 0 if result["all_pass"] else 3
if __name__=="__main__":raise SystemExit(main())
