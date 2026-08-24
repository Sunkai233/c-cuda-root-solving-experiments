#!/usr/bin/env python3
"""Independent high-precision PV current, power, MPP and parameter-gradient oracle."""
import argparse,csv,hashlib,json,math,random
from pathlib import Path
import mpmath as mp

FIELDS=["sample_id","split","region","IL","I0","a","Rs","Rsh","V","Voc","Vmp","I","power","dI_dV","dI_dIL","dI_dI0","dI_da","dI_dRs","dI_dRsh","residual","exp_argument","status"]
def split(i):return "dev" if i%10<6 else("cal" if i%10<8 else "test")
def bisect(f,lo,hi,n=220):
    lo,hi=mp.mpf(lo),mp.mpf(hi);flo=f(lo)
    for _ in range(n):
        mid=(lo+hi)/2;fm=f(mid)
        if mp.sign(flo)!=mp.sign(fm):hi=mid
        else:lo=mid;flo=fm
    return (lo+hi)/2
def current(v,il,i0,a,rs,rsh):
    A=1+rs/rsh;C=il+i0-v/rsh
    arg=(rs*i0/(a*A))*mp.exp((v+rs*C/A)/a)
    return C/A-(a/rs)*mp.lambertw(arg).real
def quantities(v,il,i0,a,rs,rsh):
    cur=current(v,il,i0,a,rs,rsh);z=(v+cur*rs)/a;ez=mp.exp(z)
    fi=1+i0*ez*rs/a+rs/rsh
    partial={"V":i0*ez/a+1/rsh,"IL":-1,"I0":ez-1,"a":-i0*ez*(v+cur*rs)/(a*a),"Rs":i0*ez*cur/a+cur/rsh,"Rsh":-(v+cur*rs)/(rsh*rsh)}
    grad={name:-value/fi for name,value in partial.items()}
    residual=cur-il+i0*(ez-1)+(v+cur*rs)/rsh
    return cur,z,grad,residual
def fmt(x):return mp.nstr(x,55)
def main():
    p=argparse.ArgumentParser();p.add_argument("--out",type=Path,required=True);p.add_argument("--n",type=int,default=3000);p.add_argument("--seed",type=int,default=20260827);p.add_argument("--dps",type=int,default=70);args=p.parse_args()
    args.out.mkdir(parents=True,exist_ok=False);mp.mp.dps=args.dps;rng=random.Random(args.seed);rows=[]
    for i in range(args.n):
        il=mp.mpf(1+11*rng.random());i0=mp.power(10,-12+5*rng.random());a=mp.mpf(1+1.4*rng.random());rs=mp.mpf(.02+.78*rng.random());rsh=mp.power(10,2+1.5*rng.random())
        voc=bisect(lambda v:current(v,il,i0,a,rs,rsh),0,a*mp.log(il/i0+1)*mp.mpf("1.3"))
        g=lambda v:(lambda q:q[0]+v*q[2]["V"])(quantities(v,il,i0,a,rs,rsh))
        vmp=bisect(g,0,voc)
        kind=i%4
        if kind==0:region="short_circuit";v=voc*mp.power(10,-8+6*rng.random())
        elif kind==1:region="open_circuit";v=voc*(1-mp.power(10,-8+6*rng.random()))
        elif kind==2:region="mpp_near";v=min(voc,max(mp.mpf(0),vmp*(1+mp.mpf((2*rng.random()-1)*.02))))
        else:region="interior";v=voc*mp.mpf(.05+.9*rng.random())
        cur,z,grad,res=quantities(v,il,i0,a,rs,rsh)
        rows.append([f"pvext_{i:07d}",split(i),region,*map(fmt,(il,i0,a,rs,rsh,v,voc,vmp,cur,v*cur,grad["V"],grad["IL"],grad["I0"],grad["a"],grad["Rs"],grad["Rsh"],abs(res),z)),"ROOT_OK"])
    path=args.out/"pv_extended.csv"
    with path.open("w",newline="",encoding="utf-8") as f:w=csv.writer(f);w.writerow(FIELDS);w.writerows(rows)
    counts={s:sum(r[1]==s for r in rows) for s in ("dev","cal","test")};regions={s:sum(r[2]==s for r in rows) for s in ("short_circuit","open_circuit","mpp_near","interior")}
    manifest={"seed":args.seed,"mpmath_dps":args.dps,"minimum_bits":math.floor(args.dps*math.log2(10)),"n":args.n,"splits":counts,"regions":regions,"csv_sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
    (args.out/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8");print(json.dumps(manifest,indent=2))
if __name__=="__main__":main()
