#!/usr/bin/env python3
"""Independent multiprecision oracle for a stratified real-table BEM subset.

The implementation parses original AeroDyn blade/polar files directly and does
not include or call the C/CUDA residual. Float scanning only discovers candidate
brackets; every accepted root and derivative is refined/evaluated with mpmath.
"""
from __future__ import annotations
import argparse,bisect,csv,hashlib,json,math,struct
from pathlib import Path
import mpmath as mp
import numpy as np

AFS=["Cylinder1.dat","Cylinder2.dat","DU40_A17.dat","DU35_A17.dat","DU30_A17.dat","DU25_A17.dat","DU21_A17.dat","NACA64_A17.dat"]
PI=mp.pi; EPS=mp.mpf("1.4901161193847656e-7")
def polar(path):
    lines=path.read_text(encoding="utf-8").splitlines();pos=next(i for i,s in enumerate(lines) if "NumAlf" in s);n=int(lines[pos].split()[0]);rows=[]
    for s in lines[pos+1:]:
        try:r=tuple(float(x) for x in s.split()[:3])
        except:continue
        rows.append(r)
        if len(rows)==n:break
    if len(rows)!=n:raise RuntimeError(path)
    return rows
def blade(path):
    rows=[]
    for s in path.read_text(encoding="utf-8").splitlines():
        f=s.split()
        try:r=[float(x) for x in f[:6]]+[int(f[6])]
        except:continue
        if len(f)>=7:rows.append(r)
        if len(rows)==19:break
    return np.asarray(rows,float)
def setup(base):
    ps=[polar(base/"Airfoils"/x) for x in AFS];b=blade(base/"NRELOffshrBsline5MW_AeroDyn_blade.dat");xyz=b[:,:3];z=np.empty(19);z[0]=1.5+np.linalg.norm(xyz[0]);z[1:]=z[0]+np.cumsum(np.linalg.norm(np.diff(xyz,axis=0),axis=1));tip=3*(z[-1]-z)/(2*z);hub=3*(z-1.5)/(3.0)
    q=b[1:18];pre=math.radians(-2.5);r=np.sqrt(q[:,2]**2+(-q[:,1]*math.sin(pre)+(1.5+q[:,0])*math.cos(pre))**2)
    return ps,r,q[:,5],tip[1:18],hub[1:18],q[:,6].astype(int)-1
def regions(vx,hint):
    e=float(EPS);pi=math.pi
    if vx>0:
        x=[(e,.5*pi-e)];alt=[(-.25*pi,-e),(.5*pi+e,pi-e)];x+=alt if -.25*pi<hint<.25*pi else alt[::-1]
    else:
        x=[(-e,-.5*pi+e)];alt=[(.25*pi,e),(-.5*pi-e,-pi+e)];x+=alt if -.25*pi<hint<.25*pi else alt[::-1]
    return x
def split(i):return "dev" if i%10<6 else("cal" if i%10<8 else "test")

class Oracle:
    def __init__(self,base):self.ps,self.r,self.chord,self.tip,self.hub,self.af=setup(base)
    def interp(self,node,alpha,mpmode):
        tab=self.ps[self.af[node]];deg=alpha*(180/(mp.pi if mpmode else math.pi));x=float(deg);a=[z[0] for z in tab];j=bisect.bisect_right(a,x)-1
        if j<0:j=0
        if j>=len(tab)-1:j=len(tab)-2
        x0,cl0,cd0=tab[j];x1,cl1,cd1=tab[j+1];T=mp.mpf if mpmode else float;w=(deg-T(str(x0)))/T(str(x1-x0));return T(str(cl0))+w*T(str(cl1-cl0)),T(str(cd0))+w*T(str(cd1-cd0))
    def f(self,phi,vx,vy,theta,node,mpmode=True):
        T=mp.mpf if mpmode else float;pi=mp.pi if mpmode else math.pi;sin=mp.sin if mpmode else math.sin;cos=mp.cos if mpmode else math.cos;exp=mp.exp if mpmode else math.exp;acos=mp.acos if mpmode else math.acos;sqrt=mp.sqrt if mpmode else math.sqrt
        vx=T(str(vx));vy=T(str(vy));theta=T(str(theta));cl,_=self.interp(node,phi-theta,mpmode);s=sin(phi);c=cos(phi);aa=abs(s);ft=T(1);fh=T(1)
        if aa>0:ft=(T(2)/pi)*acos(min(T(1),exp(-T(str(self.tip[node]))/aa)));fh=(T(2)/pi)*acos(min(T(1),exp(-T(str(self.hub[node]))/aa)))
        F=max(ft*fh,T("1e-4") if mpmode else 1e-4);sig=T(3)*T(str(self.chord[node]))/(T(2)*pi*T(str(self.r[node])));cn=cl*c;ct=cl*s;k=sig*cn/(T(4)*F*s*s)
        if abs(c)<T("1e-30") if mpmode else abs(c)<1e-15:kp=mp.sign(ct*s)*T("1e6")*mp.sign(vx) if mpmode else math.copysign(1e6,ct*s)*math.copysign(1,vx)
        else:
            kp=sig*ct/(T(4)*F*s*c)
            if vx<0:kp=-kp
        momentum=(phi>0 and vx>=0)or(phi<0 and vx<0)
        if momentum:
            if k<=T(2)/T(3):a=k/(T(1)+k)
            else:
                tt=T(2)*F*k;g1=tt-(T(10)/T(9)-F);g2=tt-(T(4)/T(3)-F)*F;g3=tt-(T(25)/T(9)-T(2)*F);a=T(1)-T(.5)/sqrt(g2) if abs(g3)<T("1e-6") else (g1-sqrt(abs(g2)))/g3
            return s/(T(1)-a)-c/(vy/vx)*(T(1)-kp)
        a=k/(k-T(1));return s*(T(1)-k)-c/(vy/vx)*(T(1)-kp)
    def roots(self,vx,vy,theta,hint,node):
        for rid,(lo,hi) in enumerate(regions(vx,hint)):
            xs=np.linspace(lo,hi,513);fs=[]
            for x in xs:
                try:fs.append(float(self.f(float(x),vx,vy,theta,node,False)))
                except:fs.append(float("nan"))
            rr=[]
            for j in range(512):
                if not(math.isfinite(fs[j])and math.isfinite(fs[j+1])) or math.copysign(1,fs[j])==math.copysign(1,fs[j+1]):continue
                a,b=mp.mpf(str(xs[j])),mp.mpf(str(xs[j+1]));fa=self.f(a,vx,vy,theta,node,True)
                for _ in range(220):
                    m=(a+b)/2;fm=self.f(m,vx,vy,theta,node,True)
                    if mp.sign(fa)!=mp.sign(fm):b=m
                    else:a=m;fa=fm
                root=(a+b)/2;fr=abs(self.f(root,vx,vy,theta,node,True))
                if fr<mp.mpf("1e-35") and all(abs(root-q)>mp.mpf("1e-25") for q in rr):rr.append(root)
            if rr:return rid,sorted(rr),min(rr,key=lambda x:abs(mp.atan2(mp.sin(x-hint),mp.cos(x-hint))))
        return -1,[],mp.nan

def main():
    p=argparse.ArgumentParser();p.add_argument("--dataset",type=Path,required=True);p.add_argument("--baseline",type=Path,required=True);p.add_argument("--bisection-roots",type=Path,required=True);p.add_argument("--brent-roots",type=Path,required=True);p.add_argument("--out",type=Path,required=True);p.add_argument("--n",type=int,default=3000);a=p.parse_args();mp.mp.dps=80
    with a.dataset.open("rb") as f:magic,ver,n,nf,nodes,steps=struct.unpack("<8sIQIII",f.read(32))
    data=np.memmap(a.dataset,dtype="<f8",mode="r",offset=32,shape=(5,n));bisr=np.memmap(a.bisection_roots,dtype="<f8",mode="r");br=np.memmap(a.brent_roots,dtype="<f8",mode="r")
    delta=np.abs((br-bisr+np.pi)%(2*np.pi)-np.pi);dis=np.flatnonzero(delta>1e-6);theta=data[2];alpha=(br-theta)*180/np.pi;oracle=Oracle(a.baseline);knot=np.empty(n)
    for node in range(17):
        ii=np.arange(node,n,17);kn=np.array([x[0] for x in oracle.ps[oracle.af[node]]]);av=alpha[ii];pos=np.searchsorted(kn,av);left=kn[np.clip(pos-1,0,len(kn)-1)];right=kn[np.clip(pos,0,len(kn)-1)];knot[ii]=np.minimum(abs(av-left),abs(av-right))
    near=np.argsort(knot)[:700];rng=np.random.default_rng(20260824);pool=np.setdiff1d(np.arange(n),np.union1d(dis,near),assume_unique=False);extra=rng.choice(pool,max(0,a.n-len(np.union1d(dis,near))),replace=False);idx=np.sort(np.union1d(np.union1d(dis,near),extra))[:a.n]
    a.out.mkdir(parents=True,exist_ok=False);fields=["sample_id","source_index","split","node","vx","vy","theta","hint","region","root_count_region","roots","target_root","residual_abs","fphi_left","fphi_right","fvx","gradient_vx_left","gradient_vx_right","polar_knot_distance_deg","bisection_error","brent_error","status"]
    with (a.out/"bem_real_reference.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for j,i in enumerate(idx):
            vx,vy,th,hint=(float(data[k,i]) for k in (0,1,2,4));node=int(i%51%17);rid,roots,r=oracle.roots(vx,vy,th,hint,node);row={"sample_id":f"bemreal_{j:06d}","source_index":int(i),"split":split(j),"node":node,"vx":repr(vx),"vy":repr(vy),"theta":repr(th),"hint":repr(hint),"region":rid,"root_count_region":len(roots),"roots":";".join(mp.nstr(x,60) for x in roots),"target_root":mp.nstr(r,60),"polar_knot_distance_deg":repr(float(knot[i]))}
            if mp.isfinite(r):
                h=mp.mpf("1e-20");f0=oracle.f(r,vx,vy,th,node,True);fl=(f0-oracle.f(r-h,vx,vy,th,node,True))/h;fr=(oracle.f(r+h,vx,vy,th,node,True)-f0)/h;hv=mp.mpf("1e-20")*max(1,abs(mp.mpf(str(vx))));fv=(oracle.f(r,mp.mpf(str(vx))+hv,vy,th,node,True)-oracle.f(r,mp.mpf(str(vx))-hv,vy,th,node,True))/(2*hv)
                row.update(residual_abs=mp.nstr(abs(f0),20),fphi_left=mp.nstr(fl,30),fphi_right=mp.nstr(fr,30),fvx=mp.nstr(fv,30),gradient_vx_left=mp.nstr(-fv/fl,30),gradient_vx_right=mp.nstr(-fv/fr,30),bisection_error=repr(abs(math.remainder(float(bisr[i]-r),2*math.pi))),brent_error=repr(abs(math.remainder(float(br[i]-r),2*math.pi))),status="ROOT_OK")
            else:row.update(status="NO_CERTIFIED_ROOT")
            w.writerow(row)
    manifest={"created_utc":"2026-08-24","mpmath_dps":80,"selection":{"all_bisection_brent_disagreements":int(len(dis)),"nearest_polar_knots":700,"total":int(len(idx)),"random_seed":20260824},"target_rule":"first valid solver region, then certified crossing closest to previous-step hint","dataset_sha256":hashlib.sha256(a.dataset.read_bytes()).hexdigest(),"csv_sha256":hashlib.sha256((a.out/"bem_real_reference.csv").read_bytes()).hexdigest()};(a.out/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8");print(json.dumps(manifest,indent=2))
if __name__=="__main__":main()
