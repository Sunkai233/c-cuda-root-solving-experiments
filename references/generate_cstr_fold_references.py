#!/usr/bin/env python3
"""Generate high-precision CSTR fold/continuation references."""
import argparse,csv,hashlib,json,math,random
from pathlib import Path
import mpmath as mp

BASE=[(88.35475208,20.49129565),(19.26544214,22.71097963),(27.34093610,74.11707092)]
FIELDS=["domain","sample_id","split","branch","p0","p1","p2","p3","p4","p5","root","gradient","residual","root_count","status"]
def split(i):return "dev" if i%10<6 else("cal" if i%10<8 else "test")
def bisect(f,a,b,n=260):
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
def folds(g,b):
    h=lambda x:1/x+1/(1-x)-g*g*b/(g+b*x)**2;out=[];a=mp.mpf("1e-8");fa=h(a)
    for k in range(1,4097):
        z=mp.mpf("1e-8")+(mp.mpf("0.99999998")*k/4096);fz=h(z)
        if mp.sign(fa)!=mp.sign(fz):out.append(bisect(h,a,z))
        a,fa=z,fz
    return out
def main():
    p=argparse.ArgumentParser();p.add_argument("--out",type=Path,required=True);p.add_argument("--n",type=int,default=3000);p.add_argument("--seed",type=int,default=20260824);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);mp.mp.dps=80;rng=random.Random(a.seed);rows=[];extended=[];i=0
    while i<a.n:
        g0,b0=BASE[i%len(BASE)];g=mp.mpf(str(g0*(.95+.1*rng.random())));b=mp.mpf(str(b0*(.95+.1*rng.random())));ff=folds(g,b)
        if len(ff)!=2:continue
        xf=ff[(i//3)&1];daf=xf/(1-xf)*mp.exp(-g*b*xf/(g+b*xf));delta=mp.power(10,-8+6*rng.random());da=daf*(1+delta if (i&2) else 1-delta)
        fun=lambda x:x-(da*mp.exp(g*b*x/(g+b*x)))/(1+da*mp.exp(g*b*x/(g+b*x)));rr=roots(fun)
        if len(rr) not in (1,3):continue
        high=bool(i&1);x=rr[-1] if high else rr[0];den=g+b*x;r=da*mp.exp(g*b*x/den);fx=1-r*g*g*b/(den*den*(1+r)**2);fda=-(r/da)/(1+r)**2;grad=-fda/fx;cond=1/abs(fx);lam=mp.mpf("1e-4");greg=-fda*fx/(fx*fx+lam*lam);spacing=min([abs(rr[j+1]-rr[j]) for j in range(len(rr)-1)]or[mp.inf]);branch=("high"if high else"low")+("_triple"if len(rr)==3 else"_single")
        row=["cstr",f"cstrfold_{i:07d}",split(i),branch,*[mp.nstr(q,55) for q in (da,g,b,0,0,0,x,grad,abs(fun(x)))],len(rr),"ROOT_OK"];rows.append(row)
        extended.append({"sample_id":row[1],"fold_side":"upper"if (i//3)&1 else"lower","relative_fold_offset":mp.nstr((da-daf)/daf,25),"fold_x":mp.nstr(xf,30),"fold_Da":mp.nstr(daf,30),"root_spacing_min":mp.nstr(spacing,30),"Fx":mp.nstr(fx,30),"condition":mp.nstr(cond,30),"raw_gradient":mp.nstr(grad,30),"regularized_gradient_lambda_1e-4":mp.nstr(greg,30),"regularization_relative_bias":mp.nstr(abs(greg-grad)/max(abs(grad),mp.mpf("1e-300")),30),"root_count":len(rr),"selected_branch":branch});i+=1
    with (a.out/"cstr.csv").open("w",newline="",encoding="utf-8") as f:w=csv.writer(f);w.writerow(FIELDS);w.writerows(rows)
    with (a.out/"cstr_fold_metrics.csv").open("w",newline="",encoding="utf-8") as f:w=csv.DictWriter(f,fieldnames=list(extended[0]));w.writeheader();w.writerows(extended)
    split_counts={name:sum(row[2]==name for row in rows) for name in ("dev","cal","test")}
    root_counts={str(k):sum(int(row[-2])==k for row in rows) for k in (1,3)}
    assert len(rows)==a.n and sum(split_counts.values())==a.n
    assert len(extended)==a.n and sum(root_counts.values())==a.n
    manifest={"seed":a.seed,"mpmath_dps":80,"n":a.n,"splits":split_counts,"root_counts":root_counts,"regularization_lambda":1e-4,"csv_sha256":hashlib.sha256((a.out/"cstr.csv").read_bytes()).hexdigest(),"metrics_sha256":hashlib.sha256((a.out/"cstr_fold_metrics.csv").read_bytes()).hexdigest()};(a.out/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8");print(json.dumps(manifest,indent=2))
if __name__=="__main__":main()
