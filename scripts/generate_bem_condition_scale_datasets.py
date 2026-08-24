#!/usr/bin/env python3
"""Build heterogeneous real-state BEM performance inputs; reference column is not a correctness oracle."""
import argparse,hashlib,json,math,struct
from pathlib import Path
import numpy as np
K=(1,2,4,8,16,32,64,256,1024,4096,16384,65536)
def write(path,arrays,nodes=51):
 n=len(arrays[0]);h=struct.pack('<8sIQIII',b'BEMREAL2',2,n,5,nodes,(n+nodes-1)//nodes)
 with path.open('wb') as f:f.write(h);[np.asarray(x,dtype='<f8').tofile(f) for x in arrays];np.zeros(n,dtype='u1').tofile(f)
 return hashlib.sha256(path.read_bytes()).hexdigest()
def transformed(src,n,kind):
 j=np.arange(n,dtype=np.int64);node=j%51;step=j//51;source_steps=src.shape[1]//51;source_step=step%source_steps;idx=source_step*51+node;vx=src[0,idx].copy();vy=src[1,idx].copy();theta=src[2,idx].copy();hint=src[4,idx].copy();phase=2*np.pi*source_step/source_steps
 if kind==1:vx*=.75
 elif kind==2:vx*=1.25
 elif kind==3:vx*=1+.18*np.sin(7*phase)+.08*np.sin(31*phase);vy*=1+.08*np.cos(11*phase)
 return [vx,vy,theta,np.zeros(n),hint]
def mixed(src,n):
 j=np.arange(n,dtype=np.int64);node=j%51;step=j//51;kind=step%4;base_step=step//4;source_steps=src.shape[1]//51;idx=(((base_step*104729)+(kind+1)*7919)%source_steps)*51+node;vx=src[0,idx].copy();vy=src[1,idx].copy();theta=src[2,idx].copy();hint=src[4,idx].copy();phase=2*np.pi*(idx//51)/source_steps
 vx[kind==1]*=.75;vx[kind==2]*=1.25;m=kind==3;vx[m]*=1+.18*np.sin(7*phase[m])+.08*np.sin(31*phase[m]);vy[m]*=1+.08*np.cos(11*phase[m]);return [vx,vy,theta,np.zeros(n),hint]
def main():
 p=argparse.ArgumentParser();p.add_argument('--dataset',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 with a.dataset.open('rb') as f:magic,ver,n,nf,nodes,steps=struct.unpack('<8sIQIII',f.read(32))
 src=np.memmap(a.dataset,dtype='<f8',mode='r',offset=32,shape=(5,n));hashes={};sizes=[]
 for k in K:
  count=51*k;name=f'mixed_51x{k}.bin';hashes[name]=write(a.out/name,mixed(src,count));base=f'baseline_51x{k}.bin';hashes[base]=write(a.out/base,transformed(src,count,0));sizes.append(count)
 condition_n=524280
 for kind,name in enumerate(('baseline','low_wind_075','high_wind_125','turbulent_gust')):hashes[f'{name}_{condition_n}.bin']=write(a.out/f'{name}_{condition_n}.bin',transformed(src,condition_n,kind))
 manifest={'source':str(a.dataset),'source_sha256':hashlib.sha256(a.dataset.read_bytes()).hexdigest(),'actual_nodes_per_step':51,'specification_57_node_mismatch':'NREL 5MW AeroDyn input has 17 nodes/blade x 3 blades = 51','scale_counts':sizes,'conditions':{'baseline':'unmodified consecutive real states','low_wind_075':'Vx x 0.75','high_wind_125':'Vx x 1.25','turbulent_gust':'Vx harmonic +/-26%; Vy harmonic +/-8%'},'hint_protocol':'files contain original-condition hints; transformed condition files are cold/mismatched-hint ablations until prepare_bem_warm_hints.py is applied','purpose':'performance/fallback only; zero reference column is not correctness evidence','files_sha256':hashes}
 (a.out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8');print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
