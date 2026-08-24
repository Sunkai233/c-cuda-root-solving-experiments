#include <cuda_runtime.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <string>
#include <vector>
#define BEM_TABLE_QUAL static __device__ __constant__
#define BEM_HD static __device__ __forceinline__
#include "bem_real_solver.h"
#include "bem_real_precision.cuh"
struct Case{double vx,vy,th,hint,root;int node,near,multi;};struct Out{double root,residual;unsigned char ok,path;};
static std::vector<std::string>fld(const std::string&s){std::vector<std::string>v;std::stringstream q(s);std::string x;while(std::getline(q,x,','))v.push_back(x);return v;}
static std::vector<Case>load(const std::string&p,const std::string&split){std::ifstream f(p);std::string l;std::getline(f,l);std::vector<Case>v;while(std::getline(f,l)){auto x=fld(l);if(x.size()<22||x[2]!=split)continue;v.push_back({stod(x[4]),stod(x[5]),stod(x[6]),stod(x[7]),stod(x[11]),stoi(x[3]),stod(x[18])<=1e-3,stoi(x[9])>1});}return v;}
__device__ Out one(const Case&p,int method){float xf;double x;int ok=1,path=method;if(method==2){ok=bem_solve_algorithm(p.vx,p.vy,p.th,p.hint,p.node,4,&x);}else{ok=bf_solve((float)p.vx,(float)p.vy,(float)p.th,(float)p.hint,p.node,512,xf);x=xf;if(method==1||method==4){x=bd_refine(xf,p.vx,p.vy,p.th,p.node);int v;double f=bem_residual(x,p.vx,p.vy,p.th,p.node,&v);ok=v&&isfinite(f)&&fabs(f)<5e-8;if(method==4){if(!ok){ok=bem_solve_algorithm(p.vx,p.vy,p.th,p.hint,p.node,4,&x);path=2;}else path=1;}}if(method==3){int v;double f=bem_residual(x,p.vx,p.vy,p.th,p.node,&v),h=1e-6,fm=bem_residual(x-h,p.vx,p.vy,p.th,p.node,&v),fp=bem_residual(x+h,p.vx,p.vy,p.th,p.node,&v),est=fabs(f)/fmax(fabs((fp-fm)/(2*h)),1e-300);if(!ok||!v||!isfinite(est)||est>3e-8||fabs(f)>5e-8){ok=bem_solve_algorithm(p.vx,p.vy,p.th,p.hint,p.node,4,&x);path=2;}else path=0;}}int v;double r=bem_residual(x,p.vx,p.vy,p.th,p.node,&v);return{x,fabs(r),(unsigned char)(ok&&v&&isfinite(x)&&isfinite(r)),(unsigned char)path};}
__global__ void kernel(const Case*in,Out*out,size_t n,int method){size_t i=(size_t)blockIdx.x*blockDim.x+threadIdx.x;if(i<n)out[i]=one(in[i],method);}
static double wrap(double x){x=fmod(x+BEM_PI,2*BEM_PI);if(x<0)x+=2*BEM_PI;return x-BEM_PI;}static double qt(std::vector<double>v,double p){std::sort(v.begin(),v.end());return v[(size_t)(p*(v.size()-1))];}
int main(int argc,char**argv){std::string refs,split="cal",out="results_raw/bem_precision";for(int i=1;i<argc;i++){if(!strcmp(argv[i],"--references"))refs=argv[++i];else if(!strcmp(argv[i],"--split"))split=argv[++i];else if(!strcmp(argv[i],"--out"))out=argv[++i];}auto c=load(refs,split);if(c.empty())return 2;std::filesystem::create_directories(out);Case*d;Out*o;cudaMalloc(&d,c.size()*sizeof(Case));cudaMalloc(&o,c.size()*sizeof(Out));cudaMemcpy(d,c.data(),c.size()*sizeof(Case),cudaMemcpyHostToDevice);const char*names[]={"fp32","fp32_df32_refine","fp64","adaptive","df32_adaptive"};std::ofstream s(out+"/bem_precision_"+split+"_summary.csv"),raw(out+"/bem_precision_"+split+"_samples.csv");s<<"method,n,root_median,root_p95,root_p99,root_max,residual_max,wrong_gt_1e-5,wrong_gt_1e-7,wrong_branch_gt_1e-3,nonfinite,fp64_correction_fraction\n";raw<<"method,index,near_knot,multi_root,root_abs,residual,status,path\n";for(int m=0;m<5;m++){kernel<<<int((c.size()+255)/256),256>>>(d,o,c.size(),m);std::vector<Out>h(c.size());cudaMemcpy(h.data(),o,h.size()*sizeof(Out),cudaMemcpyDeviceToHost);std::vector<double>e,res;size_t w5=0,w7=0,wb=0,nf=0,corr=0;for(size_t i=0;i<c.size();i++){double z=fabs(wrap(h[i].root-c[i].root));e.push_back(z);res.push_back(h[i].residual);w5+=z>1e-5;w7+=z>1e-7;wb+=z>1e-3;nf+=!h[i].ok;corr+=(m==3||m==4)&&h[i].path==2;raw<<names[m]<<','<<i<<','<<c[i].near<<','<<c[i].multi<<','<<std::setprecision(17)<<z<<','<<h[i].residual<<','<<int(h[i].ok)<<','<<int(h[i].path)<<'\n';}s<<names[m]<<','<<c.size()<<','<<std::setprecision(17)<<qt(e,.5)<<','<<qt(e,.95)<<','<<qt(e,.99)<<','<<qt(e,1)<<','<<qt(res,1)<<','<<w5<<','<<w7<<','<<wb<<','<<nf<<','<<double(corr)/c.size()<<'\n';printf("%s %s n=%zu rootmax=%.3e wrong1e-7=%zu branch=%zu nf=%zu corr=%.3f\n",split.c_str(),names[m],c.size(),qt(e,1),w7,wb,nf,double(corr)/c.size());}cudaFree(o);cudaFree(d);}
