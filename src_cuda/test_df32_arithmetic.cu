#include "../include/df32.cuh"
#include <cuda_runtime.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <string>
#include <vector>

struct AInput {df32 x,y,pos,angle;};
struct AOutput {df32 add,mul,div,exp,log,sin,cos,sqrt;};
__global__ void arithmetic_kernel(const AInput*in,AOutput*out,size_t n){size_t i=(size_t)blockIdx.x*blockDim.x+threadIdx.x;if(i>=n)return;AInput p=in[i];AOutput q{};q.add=d32_add(p.x,p.y);q.mul=d32_mul(p.x,p.y);q.div=d32_div(p.x,p.y);q.exp=d32_exp(p.x);q.log=d32_log(p.pos);d32_sincos(p.angle,q.sin,q.cos);q.sqrt=d32_sqrt(p.pos);out[i]=q;}
static uint64_t mix(uint64_t x){x+=0x9e3779b97f4a7c15ULL;x=(x^(x>>30))*0xbf58476d1ce4e5b9ULL;x=(x^(x>>27))*0x94d049bb133111ebULL;return x^(x>>31);}static double u01a(uint64_t x){return (mix(x)>>11)*0x1.0p-53;}static df32 hd32(double x){float h=float(x);return {h,float(x-double(h))};}static long double val(df32 x){return (long double)x.hi+(long double)x.lo;}
struct Stat{long double max_abs=0,max_rel=0;size_t nonfinite=0,overlap=0;void add(df32 got,long double ref,bool absolute=false){long double g=val(got);if(!std::isfinite((double)g)){nonfinite++;return;}long double ae=fabsl(g-ref),re=ae/fmaxl(fabsl(ref),absolute?1.0L:1e-30L);max_abs=fmaxl(max_abs,ae);max_rel=fmaxl(max_rel,re);float ulp=fabsf(nextafterf(got.hi,INFINITY)-got.hi);if(got.hi!=0&&fabsf(got.lo)>.50001f*ulp)overlap++;}};
int main(int argc,char**argv){std::string outdir="results_raw/df32_arithmetic";size_t n=200000;if(argc>1)outdir=argv[1];std::filesystem::create_directories(outdir);std::vector<AInput>in(n);for(size_t i=0;i<n;i++){double ux=u01a(8*i),uy=u01a(8*i+1),x=-80+160*ux,y=.25+3.75*uy;if(i%4==0){x=.5+ux;y=-x+pow(10.0,-12+4*uy);}double pos=pow(10.0,-12+24*u01a(8*i+2)),angle=-3.141592653589793+6.283185307179586*u01a(8*i+3);in[i]={hd32(x),hd32(y),hd32(pos),hd32(angle)};}AInput*di;AOutput*doo;cudaMalloc(&di,n*sizeof(AInput));cudaMalloc(&doo,n*sizeof(AOutput));cudaMemcpy(di,in.data(),n*sizeof(AInput),cudaMemcpyHostToDevice);arithmetic_kernel<<<int((n+255)/256),256>>>(di,doo,n);cudaDeviceSynchronize();std::vector<AOutput>o(n);cudaMemcpy(o.data(),doo,n*sizeof(AOutput),cudaMemcpyDeviceToHost);cudaFree(di);cudaFree(doo);Stat st[8];for(size_t i=0;i<n;i++){long double x=val(in[i].x),y=val(in[i].y),p=val(in[i].pos),a=val(in[i].angle);st[0].add(o[i].add,x+y);st[1].add(o[i].mul,x*y);st[2].add(o[i].div,x/y);st[3].add(o[i].exp,expl(x));st[4].add(o[i].log,logl(p));st[5].add(o[i].sin,sinl(a),true);st[6].add(o[i].cos,cosl(a),true);st[7].add(o[i].sqrt,sqrtl(p));}const char*name[]={"add","mul","div","exp","log","sin","cos","sqrt"};std::ofstream csv(outdir+"/df32_arithmetic.csv");csv<<"operation,n,max_absolute_error,max_relative_error,nonfinite,nonoverlap_violations\n";for(int k=0;k<8;k++){csv<<name[k]<<','<<n<<','<<std::setprecision(12)<<(double)st[k].max_abs<<','<<(double)st[k].max_rel<<','<<st[k].nonfinite<<','<<st[k].overlap<<'\n';printf("%-5s max_abs=%.3Le max_rel=%.3Le nf=%zu overlap=%zu\n",name[k],st[k].max_abs,st[k].max_rel,st[k].nonfinite,st[k].overlap);}return 0;}
