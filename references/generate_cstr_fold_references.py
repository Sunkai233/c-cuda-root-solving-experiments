#!/usr/bin/env python3
"""Generate high-precision CSTR fold/continuation references."""
import argparse,csv,hashlib,json,math,random
from pathlib import Path
import mpmath as mp

BASE=[(88.35475208,20.49129565),(19.26544214,22.71097963),(27.34093610,74.11707092)]
FIELDS=["domain","sample_id","split","branch","p0","p1","p2","p3","p4","p5","root","gradient","residual","root_count","status"]
def split(i):return "dev" if i%10<6 else("cal" if i%10<8 else "test")
def bisect(f,a,b,n=140):
    a,b=mp.mpf(a),mp.mpf(b);fa=f(a)
    for _ in range(n):
        m=(a+b)/2;fm=f(m)
        if mp.sign(fa)!=mp.sign(fm):b=m
        else:a=m;fa=fm
    return(a+b)/2
def roots(f,scans=4096):
    out=[];a=mp.mpf("0");fa=f(a)
    for k in range(1,scans+1):
        b=mp.mpf(k)/scans;fb=f(b)
        if mp.sign(fa)!=mp.sign(fb):
            r=bisect(f,a,b)
            if all(abs(r-q)>mp.mpf("1e-40") for q in out):out.append(r)
        a,fa=b,fb
    return out
def roots_by_folds(f,fold_points):
    """Enumerate every root on monotone branches separated by exact folds.

    A uniform scan can miss the close root pair deliberately generated near a
    saddle-node.  The two stationary points provide complete, safe brackets.
    """
    bounds=[mp.mpf("0"),*sorted(fold_points),mp.mpf("1")];out=[]
    for a,b in zip(bounds,bounds[1:]):
        fa,fb=f(a),f(b)
        if fa==0 and all(abs(a-q)>mp.mpf("1e-40") for q in out):out.append(a)
        if mp.sign(fa)!=mp.sign(fb):
            r=bisect(f,a,b)
            if all(abs(r-q)>mp.mpf("1e-40") for q in out):out.append(r)
    if f(bounds[-1])==0 and all(abs(bounds[-1]-q)>mp.mpf("1e-40") for q in out):out.append(bounds[-1])
    return out
def folds(g,b):
    # h(x)=0 is exactly quadratic after multiplying by x(1-x)(g+bx)^2:
    # (b^2+g^2 b)x^2 + (2gb-g^2b)x + g^2 = 0.
    A=b*b+g*g*b;B=2*g*b-g*g*b;C=g*g;disc=B*B-4*A*C
    if disc<=0:return []
    s=mp.sqrt(disc);q=-mp.mpf("0.5")*(B+mp.sign(B)*s)
    candidates=[q/A,C/q]
    return sorted(x for x in candidates if 0<x<1)
def main():
    p=argparse.ArgumentParser();p.add_argument("--out",type=Path,required=True);p.add_argument("--n",type=int,default=3000);p.add_argument("--seed",type=int,default=20260824);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);mp.mp.dps=80;rng=random.Random(a.seed);rows=[];extended=[];i=0;triple_index=0
    while i<a.n:
        g0,b0=BASE[i%len(BASE)];g=mp.mpf(str(g0*(.95+.1*rng.random())));b=mp.mpf(str(b0*(.95+.1*rng.random())));ff=folds(g,b)
        if len(ff)!=2:continue
        xf=ff[(i//3)&1];daf=xf/(1-xf)*mp.exp(-g*b*xf/(g+b*xf));delta=mp.power(10,-8+6*rng.random());da=daf*(1+delta if (i&2) else 1-delta)
        fun=lambda x:x-(da*mp.exp(g*b*x/(g+b*x)))/(1+da*mp.exp(g*b*x/(g+b*x)));rr=roots_by_folds(fun,ff)
        if len(rr) not in (1,3):continue
        selector=triple_index%3 if len(rr)==3 else 0;triple_index+=len(rr)==3;x=rr[selector];den=g+b*x;r=da*mp.exp(g*b*x/den);fx=1-r*g*g*b/(den*den*(1+r)**2);fda=-(r/da)/(1+r)**2;grad=-fda/fx;cond=1/abs(fx);lam=mp.mpf("1e-4");greg=-fda*fx/(fx*fx+lam*lam);spacing=min([abs(rr[j+1]-rr[j]) for j in range(len(rr)-1)]or[mp.inf]);branch=(("low","middle","high")[selector]+"_triple") if len(rr)==3 else "single"
        row=["cstr",f"cstrfold_{i:07d}",split(i),branch,*[mp.nstr(q,55) for q in (da,g,b,0,0,0,x,grad,abs(fun(x)))],len(rr),"ROOT_OK"];rows.append(row)
        extended.append({"sample_id":row[1],"fold_side":"upper"if (i//3)&1 else"lower","relative_fold_offset":mp.nstr((da-daf)/daf,25),"fold_x":mp.nstr(xf,30),"fold_Da":mp.nstr(daf,30),"root_spacing_min":mp.nstr(spacing,30),"Fx":mp.nstr(fx,30),"condition":mp.nstr(cond,30),"raw_gradient":mp.nstr(grad,30),"regularized_gradient_lambda_1e-4":mp.nstr(greg,30),"regularization_relative_bias":mp.nstr(abs(greg-grad)/max(abs(grad),mp.mpf("1e-300")),30),"root_count":len(rr),"selected_branch":branch});i+=1
    with (a.out/"cstr.csv").open("w",newline="",encoding="utf-8") as f:w=csv.writer(f);w.writerow(FIELDS);w.writerows(rows)
    with (a.out/"cstr_fold_metrics.csv").open("w",newline="",encoding="utf-8") as f:w=csv.DictWriter(f,fieldnames=list(extended[0]));w.writeheader();w.writerows(extended)
    histories=[];ambiguous=[]
    for case,(g0,b0) in enumerate(BASE):
        g,b=mp.mpf(str(g0)),mp.mpf(str(b0));xf=folds(g,b);fold_da=sorted(x/(1-x)*mp.exp(-g*b*x/(g+b*x)) for x in xf);lo_da,hi_da=fold_da[0]*mp.mpf("0.8"),fold_da[1]*mp.mpf("1.2")
        for direction in ("cold_up","hot_down"):
            seq=[lo_da+(hi_da-lo_da)*k/80 for k in range(81)];seq=seq if direction=="cold_up" else seq[::-1];prev=None;previous_branch=None
            for step,da in enumerate(seq):
                fun=lambda x:x-(da*mp.exp(g*b*x/(g+b*x)))/(1+da*mp.exp(g*b*x/(g+b*x)));rr=roots_by_folds(fun,xf)
                x=(rr[0] if direction=="cold_up" else rr[-1]) if prev is None else min(rr,key=lambda q:abs(q-prev));idx=rr.index(x);branch=("single" if len(rr)==1 else ("low","middle","high")[idx]);crossed=previous_branch is not None and branch!=previous_branch and "single" in (branch,previous_branch)
                histories.append({"history_id":f"case{case}_{direction}","direction":direction,"step":step,"Da":mp.nstr(da,35),"gamma":mp.nstr(g,20),"beta":mp.nstr(b,20),"root_count":len(rr),"roots":";".join(mp.nstr(q,35) for q in rr),"selected_root":mp.nstr(x,35),"selected_branch":branch,"crossed_fold":int(crossed),"status":"ROOT_OK"});prev=x;previous_branch=branch
                if len(rr)==3 and not any(q["history_id"]==f"case{case}_unknown" for q in ambiguous):ambiguous.append({"history_id":f"case{case}_unknown","Da":mp.nstr(da,35),"gamma":mp.nstr(g,20),"beta":mp.nstr(b,20),"root_count":3,"roots":";".join(mp.nstr(q,35) for q in rr),"selected_root":"","status":"ROOT_BRANCH_AMBIGUOUS"})
    with (a.out/"cstr_continuation.csv").open("w",newline="",encoding="utf-8") as f:w=csv.DictWriter(f,fieldnames=list(histories[0]));w.writeheader();w.writerows(histories)
    with (a.out/"cstr_unknown_history.csv").open("w",newline="",encoding="utf-8") as f:w=csv.DictWriter(f,fieldnames=list(ambiguous[0]));w.writeheader();w.writerows(ambiguous)
    split_counts={name:sum(row[2]==name for row in rows) for name in ("dev","cal","test")}
    root_counts={str(k):sum(int(row[-2])==k for row in rows) for k in (1,3)}
    assert len(rows)==a.n and sum(split_counts.values())==a.n
    assert len(extended)==a.n and sum(root_counts.values())==a.n
    manifest={"seed":a.seed,"mpmath_dps":80,"n":a.n,"splits":split_counts,"root_counts":root_counts,"branches":{name:sum(row[3]==name for row in rows) for name in ("single","low_triple","middle_triple","high_triple")},"continuation_histories":len(set(q["history_id"] for q in histories)),"continuation_rows":len(histories),"ambiguous_unknown_history_cases":len(ambiguous),"regularization_lambda":1e-4,"files_sha256":{name:hashlib.sha256((a.out/name).read_bytes()).hexdigest() for name in ("cstr.csv","cstr_fold_metrics.csv","cstr_continuation.csv","cstr_unknown_history.csv")}};(a.out/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8");print(json.dumps(manifest,indent=2))
if __name__=="__main__":main()
