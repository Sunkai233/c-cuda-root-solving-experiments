#include <cuda_runtime.h>
#include <omp.h>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <numeric>
#include <random>
#include <limits>
#include <sstream>
#include <string>
#include <vector>

#define HD __host__ __device__

enum Domain : int { BEM=0, KEPLER=1, PV=2, CSTR=3, PR=4 };
enum Status : uint8_t { ROOT_OK=0, ROOT_MAX_ITER=3, ROOT_NONFINITE=4, ROOT_GRADIENT_RISK=5 };

struct Param { double a,b,c,d,e,f; int domain; int branch; };
struct Output { double root,residual,gradient,condition; uint32_t iterations; uint8_t path,status,pad[2]; };

template<class T> HD inline T clampv(T x,T lo,T hi){ return x<lo?lo:(x>hi?hi:x); }

template<class T> HD inline void residual(const Param&p,T x,T&y,T&dy){
  if(p.domain==BEM){
    T lam=T(p.a), sig=T(p.b), theta=T(p.c), cla=T(p.d), cd=T(p.e);
    T s=sin(x), co=cos(x), cl=cla*(x-theta);
    T cn=cl*co+cd*s, ct=cl*s-cd*co;
    T cnp=cla*co-cl*s+cd*co, ctp=cla*s+cl*co+cd*s;
    T q=cn+ct/lam, qp=cnp+ctp/lam;
    y=s-co/lam+(sig/T(4))*q/s;
    dy=co+s/lam+(sig/T(4))*(qp*s-q*co)/(s*s);
  }else if(p.domain==KEPLER){
    y=x-T(p.a)*sin(x)-T(p.b); dy=T(1)-T(p.a)*cos(x);
  }else if(p.domain==PV){
    T z=(T(p.b)+x*T(p.e))/T(p.d), ez=exp(clampv(z,T(-80),T(80)));
    y=x-T(p.a)+T(p.c)*(ez-T(1))+(T(p.b)+x*T(p.e))/T(p.f);
    dy=T(1)+T(p.c)*ez*T(p.e)/T(p.d)+T(p.e)/T(p.f);
  }else if(p.domain==CSTR){
    T den=T(p.b)+T(p.c)*x, expo=T(p.b)*T(p.c)*x/den;
    T r=T(p.a)*exp(expo), rp=r*(T(p.b)*T(p.b)*T(p.c))/(den*den);
    y=x-r/(T(1)+r); dy=T(1)-rp/((T(1)+r)*(T(1)+r));
  }else{
    T A=T(p.a),B=T(p.b);
    y=x*x*x-(T(1)-B)*x*x+(A-T(3)*B*B-T(2)*B)*x-(A*B-B*B-B*B*B);
    dy=T(3)*x*x-T(2)*(T(1)-B)*x+A-T(3)*B*B-T(2)*B;
  }
}

HD inline void bounds(const Param&p,double&lo,double&hi,double&x0){
  if(p.domain==BEM){lo=1e-4;hi=1.5707;x0=atan(1.0/p.a);}
  else if(p.domain==KEPLER){lo=0;hi=3.141592653589793;x0=p.b+0.85*p.a;}
  else if(p.domain==PV){lo=0;hi=p.a;x0=p.a*(1.0-p.b/(p.d*log(p.a/p.c+1.0)+1e-30));}
  else if(p.domain==CSTR){lo=0;hi=1;x0=p.branch?0.9:0.1;}
  else {lo=p.b+1e-8;hi=2.0;x0=p.branch?1.0:p.b+0.02;}
  x0=clampv(x0,lo,hi);
}

template<class T> HD inline T solve_newton(const Param&p,int steps,uint32_t&used){
  double lod,hid,x0d; bounds(p,lod,hid,x0d); T lo=T(lod),hi=T(hid),x=T(x0d);
  T flo,dflo; residual(p,lo,flo,dflo);
  used=0;
  #pragma unroll 12
  for(int k=0;k<steps;k++){
    T y,dy; residual(p,x,y,dy);
    if((flo<=T(0)&&y>=T(0))||(flo>=T(0)&&y<=T(0))) hi=x;
    else {lo=x;flo=y;}
    T candidate=x-y/dy;
    if(!isfinite(candidate)||candidate<=lo||candidate>=hi) candidate=(lo+hi)/T(2);
    x=candidate; used++;
  }
  return x;
}

template<class T> HD inline T solve_physical_branch(const Param&p,int steps,uint32_t&used){
  T lo,hi;
  if(p.domain==CSTR){lo=T(0);hi=T(1);}else{lo=T(p.b)+T(1e-12);hi=T(2);}
  constexpr int SCAN=256;T prev=lo,fp,df;residual(p,prev,fp,df);T first_a=lo,first_b=hi,last_a=lo,last_b=hi;int found=0;
  for(int s=1;s<=SCAN;s++){T z=lo+(hi-lo)*T(s)/T(SCAN),fz;residual(p,z,fz,df);if((fp<=T(0)&&fz>=T(0))||(fp>=T(0)&&fz<=T(0))){if(found==0){first_a=prev;first_b=z;}last_a=prev;last_b=z;found++;}prev=z;fp=fz;}
  if(found==0)return solve_newton<T>(p,steps,used);
  T a=p.branch?last_a:first_a,b=p.branch?last_b:first_b,fa;residual(p,a,fa,df);used=0;
  for(int k=0;k<steps;k++){T m=(a+b)/T(2),fm;residual(p,m,fm,df);if((fa<=T(0)&&fm>=T(0))||(fa>=T(0)&&fm<=T(0)))b=m;else{a=m;fa=fm;}used++;}
  return (a+b)/T(2);
}

template<class T> HD inline T solve_pr_cubic(const Param&p,uint32_t&used){
  T A=T(p.a),B=T(p.b),aa=B-T(1),bb=A-T(3)*B*B-T(2)*B,cc=-(A*B-B*B-B*B*B);
  T Q=(aa*aa-T(3)*bb)/T(9),R=(T(2)*aa*aa*aa-T(9)*aa*bb+T(27)*cc)/T(54);used=1;
  if(Q>T(0)&&R*R<Q*Q*Q){
    T theta=acos(clampv(R/sqrt(Q*Q*Q),T(-1),T(1))),sq=T(2)*sqrt(Q),pi=T(3.1415926535897932384626433832795);
    T r0=-sq*cos(theta/T(3))-aa/T(3),r1=-sq*cos((theta+T(2)*pi)/T(3))-aa/T(3),r2=-sq*cos((theta+T(4)*pi)/T(3))-aa/T(3);
    T low=T(1e30),high=T(-1e30);if(r0>B){low=r0;high=r0;}if(r1>B){low=min(low,r1);high=max(high,r1);}if(r2>B){low=min(low,r2);high=max(high,r2);}return p.branch?high:low;
  }
  T disc=max(R*R-Q*Q*Q,T(0)),s=sqrt(disc),u=cbrt(R+s),v=cbrt(R-s);return -(u+v)-aa/T(3);
}

HD inline Output finish(const Param&p,double x,uint32_t it,uint8_t path){
  double y,dy; residual(p,x,y,dy); Output o{};
  o.root=x; o.residual=fabs(y); o.condition=1.0/fmax(fabs(dy),1e-300);
  double fp=0.0;
  if(p.domain==BEM){double s=sin(x),co=cos(x),cl=p.d*(x-p.c);double ct=cl*s-p.e*co;fp=co/(p.a*p.a)-p.b*ct/(4*s*p.a*p.a);}
  else if(p.domain==KEPLER)fp=-1.0;
  else if(p.domain==PV){double ez=exp(clampv((p.b+x*p.e)/p.d,-80.0,80.0));fp=p.c*ez/p.d+1.0/p.f;}
  else if(p.domain==CSTR){double den=p.b+p.c*x,r=p.a*exp(p.b*p.c*x/den);fp=-(r/p.a)/((1+r)*(1+r));}
  else fp=x-p.b;
  o.gradient=-fp/dy; o.iterations=it; o.path=path;
  o.status=(!isfinite(x)||!isfinite(y)||!isfinite(dy))?ROOT_NONFINITE:(fabs(dy)<1e-8?ROOT_GRADIENT_RISK:ROOT_OK);
  return o;
}

__global__ void kernel_fp32(const Param*in,Output*out,size_t n){
  size_t i=(size_t)blockIdx.x*blockDim.x+threadIdx.x; if(i>=n)return;
  uint32_t it; float x=in[i].domain==PR?solve_pr_cubic<float>(in[i],it):(in[i].domain==CSTR?solve_physical_branch<float>(in[i],32,it):solve_newton<float>(in[i],12,it)); out[i]=finish(in[i],double(x),it,1);
}
__global__ void kernel_fp64(const Param*in,Output*out,size_t n){
  size_t i=(size_t)blockIdx.x*blockDim.x+threadIdx.x; if(i>=n)return;
  uint32_t it; double x=in[i].domain==PR?solve_pr_cubic<double>(in[i],it):(in[i].domain==CSTR?solve_physical_branch<double>(in[i],60,it):solve_newton<double>(in[i],60,it)); out[i]=finish(in[i],x,it,3);
}
__global__ void kernel_adaptive(const Param*in,Output*out,size_t n,double tau,double tau_grad_rel){
  size_t i=(size_t)blockIdx.x*blockDim.x+threadIdx.x; if(i>=n)return;
  uint32_t it1; float xf=in[i].domain==PR?solve_pr_cubic<float>(in[i],it1):(in[i].domain==CSTR?solve_physical_branch<float>(in[i],32,it1):solve_newton<float>(in[i],10,it1)); double y,dy;
  residual(in[i],double(xf),y,dy); double est=fabs(y)/fmax(fabs(dy),1e-300);
  double grad_risk=0.0;if(in[i].domain==PR){double x=double(xf),fxx=6*x-2*(1-in[i].b);grad_risk=est*fabs(1.0/fmax(fabs(x-in[i].b),1e-300)-fxx/dy);}
  if(!isfinite(xf)||est>tau||fabs(dy)<1e-6||grad_risk>tau_grad_rel){uint32_t it2; double x=in[i].domain==PR?solve_pr_cubic<double>(in[i],it2):(in[i].domain==CSTR?solve_physical_branch<double>(in[i],60,it2):solve_newton<double>(in[i],60,it2)); out[i]=finish(in[i],x,it1+it2,3);}
  else out[i]=finish(in[i],double(xf),it1,1);
}

static uint64_t mix64(uint64_t x){x+=0x9e3779b97f4a7c15ULL;x=(x^(x>>30))*0xbf58476d1ce4e5b9ULL;x=(x^(x>>27))*0x94d049bb133111ebULL;return x^(x>>31);}
static double u01(uint64_t x){return (mix64(x)>>11)*0x1.0p-53;}
static Param make_param(int dom,size_t i){
  double u=u01(i*7+dom),v=u01(i*7+dom+1),w=u01(i*7+dom+2); Param p{};p.domain=dom;p.branch=int(i&1);
  if(dom==BEM){p.a=1+13*u;p.b=.02+.18*v;p.c=-.034906585+.314159265*w;p.d=6.283185307179586;p.e=.006+.014*v;double fl,fh,dd;residual(p,1e-4,fl,dd);residual(p,1.5707,fh,dd);if(fl*fh>0)p.c=-.034906585;}
  else if(dom==KEPLER){p.a=(i%5==0)?1.0-pow(10.0,-7.0-4.0*u):.99*u;p.b=(i%5==0)?pow(10.0,-8.0+6.0*v):3.141592653589793*v;}
  else if(dom==PV){p.a=1+11*u;p.c=pow(10.0,-12.0+5.0*v);p.d=1+1.4*w;p.e=.02+.78*u;p.f=100*pow(10.0,1.5*v);double voc=p.d*log(p.a/p.c+1.0);p.b=.995*v*voc;}
  else if(dom==CSTR){if(i%3==0){const double da0[]={.010420977722,.002845279817,.0003348429804};const double g0[]={88.35475208,19.26544214,27.34093610};const double b0[]={20.49129565,22.71097963,74.11707092};int k=int((i/3)%3);p.a=da0[k]*(.97+.06*u);p.b=g0[k]*(.97+.06*v);p.c=b0[k]*(.97+.06*w);}else{p.a=pow(10.0,-3.0+4.0*u);p.b=2+28*v;p.c=.05+5*w;}}
  else {if(i%3==0){const double A0[]={.3351162029,.2888302441,.1770232339};const double B0[]={.04279662762,.03130383695,.0004873637057};int k=int((i/3)%3);p.a=A0[k]*(.98+.04*u);p.b=B0[k]*(.98+.04*v);}else{p.a=.45+.8*u;p.b=.02+.18*v;}}
  return p;
}

static double reference(const Param&p){
  double lo,hi,x0;bounds(p,lo,hi,x0);double prev=lo,fp,d;residual(p,prev,fp,d);
  if(p.domain==BEM||p.domain==KEPLER||p.domain==PV){double a=lo,b=hi,fa=fp;for(int k=0;k<120;k++){double m=.5*(a+b),fm;residual(p,m,fm,d);if((fa<=0&&fm>=0)||(fa>=0&&fm<=0))b=m;else{a=m;fa=fm;}}return .5*(a+b);}
  const int scan=256;std::vector<double> roots;
  for(int s=1;s<=scan;s++){double z=lo+(hi-lo)*s/scan,fz;residual(p,z,fz,d);if((fp<=0&&fz>=0)||(fp>=0&&fz<=0)){double a=prev,b=z,fa=fp;for(int k=0;k<100;k++){double m=.5*(a+b),fm;residual(p,m,fm,d);if((fa<=0&&fm>=0)||(fa>=0&&fm<=0))b=m;else{a=m;fa=fm;}}roots.push_back(.5*(a+b));}prev=z;fp=fz;}
  if(roots.empty())return std::numeric_limits<double>::quiet_NaN();
  return *std::min_element(roots.begin(),roots.end(),[&](double a,double b){return fabs(a-x0)<fabs(b-x0);});
}
static double median(std::vector<double>v){std::sort(v.begin(),v.end());return v[v.size()/2];}
static double quantile(std::vector<double>v,double q){std::sort(v.begin(),v.end());size_t k=std::min(v.size()-1,size_t(q*(v.size()-1)));return v[k];}
static double cpu_run(const std::vector<Param>&p,std::vector<Output>&o,int threads){
  double t=omp_get_wtime();
  #pragma omp parallel for schedule(static) num_threads(threads)
  for(long long i=0;i<(long long)p.size();i++){uint32_t it;double x=p[i].domain==PR?solve_pr_cubic<double>(p[i],it):(p[i].domain==CSTR?solve_physical_branch<double>(p[i],60,it):solve_newton<double>(p[i],60,it));o[i]=finish(p[i],x,it,3);}
  return (omp_get_wtime()-t)*1000.0;
}

#ifndef ROOT_BENCH_NO_MAIN
int main(int argc,char**argv){
  std::string outdir="results_raw/manual";size_t maxn=2097152;int reps=30,warm=10;
  for(int i=1;i<argc;i++){if(!strcmp(argv[i],"--out"))outdir=argv[++i];else if(!strcmp(argv[i],"--max-n"))maxn=strtoull(argv[++i],nullptr,10);else if(!strcmp(argv[i],"--repetitions"))reps=atoi(argv[++i]);else if(!strcmp(argv[i],"--warmups"))warm=atoi(argv[++i]);}
  std::filesystem::create_directories(outdir);std::ofstream csv(outdir+"/measurements.csv");
  csv<<"domain,n,method,median_ms,throughput_mroots_s,max_root_error,p99_root_error,max_residual,correction_fraction,checksum\n";
  int dev;cudaGetDevice(&dev);cudaDeviceProp prop{};cudaGetDeviceProperties(&prop,dev);std::fprintf(stderr,"GPU=%s cc=%d.%d\n",prop.name,prop.major,prop.minor);
  const char*names[]={"bem","kepler","pv","cstr","peng_robinson"};
  std::vector<size_t> ns={1,8,32,128,512,2048,8192,32768,131072,524288,2097152,8388608,16777216};
  for(int dom=0;dom<5;dom++)for(size_t n:ns){if(n>maxn)continue;std::vector<Param>p(n);for(size_t i=0;i<n;i++)p[i]=make_param(dom,i);std::vector<Output>h(n),cpu(n);Param*dp;Output*dout;cudaMalloc(&dp,n*sizeof(Param));cudaMalloc(&dout,n*sizeof(Output));cudaMemcpy(dp,p.data(),n*sizeof(Param),cudaMemcpyHostToDevice);int blocks=int((n+255)/256);
    for(int k=0;k<warm;k++)kernel_adaptive<<<blocks,256>>>(dp,dout,n,1e-7,1e-6);cudaDeviceSynchronize();
    std::vector<double>gt,ct;cudaEvent_t a,b;cudaEventCreate(&a);cudaEventCreate(&b);
    for(int r=0;r<reps;r++){cudaEventRecord(a);kernel_adaptive<<<blocks,256>>>(dp,dout,n,1e-7,1e-6);cudaEventRecord(b);cudaEventSynchronize(b);float ms;cudaEventElapsedTime(&ms,a,b);gt.push_back(ms);}
    cudaMemcpy(h.data(),dout,n*sizeof(Output),cudaMemcpyDeviceToHost);for(int k=0;k<warm;k++)cpu_run(p,cpu,128);for(int r=0;r<reps;r++)ct.push_back(cpu_run(p,cpu,128));
    size_t check=std::min(n,size_t(10000));std::vector<double>err;err.reserve(check);double maxres=0,checksum=0;size_t corrected=0;for(size_t i=0;i<check;i++){double ref=reference(p[i]);if(isfinite(ref))err.push_back(fabs(h[i].root-ref));maxres=std::max(maxres,h[i].residual);checksum+=h[i].root*(1+(i%17));corrected+=h[i].path==3;}if(err.empty())err.push_back(std::numeric_limits<double>::infinity());
    double gm=median(gt),cm=median(ct);double ge=quantile(err,.99),gmax=*std::max_element(err.begin(),err.end());
    csv<<names[dom]<<','<<n<<",gpu_adaptive,"<<std::setprecision(12)<<gm<<','<<n/gm/1000.0<<','<<gmax<<','<<ge<<','<<maxres<<','<<double(corrected)/check<<','<<checksum<<'\n';
    csv<<names[dom]<<','<<n<<",cpu_omp128,"<<cm<<','<<n/cm/1000.0<<","<<0<<","<<0<<","<<0<<","<<0<<","<<0<<'\n';csv.flush();
    std::printf("%-14s N=%9zu gpu=%9.4f ms cpu128=%9.4f ms speedup=%7.2f maxerr=%.3e corr=%.4f\n",names[dom],n,gm,cm,cm/gm,gmax,double(corrected)/check);
    cudaEventDestroy(a);cudaEventDestroy(b);cudaFree(dp);cudaFree(dout);
  }
  cudaError_t ce=cudaGetLastError();if(ce!=cudaSuccess){std::fprintf(stderr,"CUDA error: %s\n",cudaGetErrorString(ce));return 2;}
  std::ofstream js(outdir+"/run.json");js<<"{\n  \"gpu\": \""<<prop.name<<"\",\n  \"compute_capability\": \""<<prop.major<<'.'<<prop.minor<<"\",\n  \"warmups\": "<<warm<<",\n  \"repetitions\": "<<reps<<",\n  \"precision\": \"fp32_fp64_adaptive\",\n  \"measurements\": \"measurements.csv\"\n}\n";
  return 0;
}
#endif
