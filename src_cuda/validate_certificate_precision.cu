#include <cuda_runtime.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
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
#include "bem_posterior_certificate.cuh"

struct Case{double vx,vy,theta,hint,root,gradient;int node;};
struct Result{double root,rho,beta,h,branch_distance,gradient_bound,residual;unsigned char path,accepted,bracket,status;};

static std::vector<std::string> fields(const std::string&s){std::vector<std::string>v;std::stringstream q(s);std::string x;while(std::getline(q,x,','))v.push_back(x);return v;}
static std::vector<Case> load(const std::string&p,const std::string&split){std::ifstream f(p);std::string l;std::getline(f,l);std::vector<Case>v;while(std::getline(f,l)){auto c=fields(l);if(c.size()<22||c[2]!=split)continue;v.push_back({stod(c[4]),stod(c[5]),stod(c[6]),stod(c[7]),stod(c[11]),stod(c[16]),stoi(c[3])});}return v;}
static double wrap(double x){x=fmod(x+BEM_PI,2*BEM_PI);if(x<0)x+=2*BEM_PI;return x-BEM_PI;}

__device__ Result evaluate_path(const Case&p,int requested,double tau_x,double tau_g,int gate){
  float xf=0.0f;double x=NAN;int ok=0;unsigned char path=(unsigned char)requested;
  if(requested==0){ok=bf_solve((float)p.vx,(float)p.vy,(float)p.theta,(float)p.hint,(unsigned)p.node,512,xf);x=xf;}
  else if(requested==1){ok=bf_solve((float)p.vx,(float)p.vy,(float)p.theta,(float)p.hint,(unsigned)p.node,512,xf);x=bd_refine(xf,p.vx,p.vy,p.theta,(unsigned)p.node);}
  else {ok=bem_solve_algorithm(p.vx,p.vy,p.theta,p.hint,(unsigned)p.node,4,&x);}
  BemCertificate c=bem_build_certificate(x,p.vx,p.vy,p.theta,(unsigned)p.node,tau_x,tau_g);
  double witness=NAN;int witnessed=bem_solve_hint_only(p.vx,p.vy,p.theta,p.hint,(unsigned)p.node,&witness);
  const double wd=witnessed?fabs(bem_wrap_pi(x-witness)):INFINITY;
  c.rho=fmax(c.rho,wd+5e-10);
  int full=c.posterior_pass&&c.branch_pass&&c.gradient_pass&&witnessed&&c.rho<=tau_x;
  int accept=gate==0?c.residual_pass:(gate==1?c.condition_pass:full);
  return{x,c.rho,c.beta,c.h,c.branch_distance,c.gradient_error_bound,c.residual,path,(unsigned char)(ok&&accept),(unsigned char)c.bracket_pass,(unsigned char)ok};
}

__global__ void gate_kernel(const Case*in,Result*out,size_t n,int requested,double tx,double tg,int gate){size_t i=(size_t)blockIdx.x*blockDim.x+threadIdx.x;if(i<n)out[i]=evaluate_path(in[i],requested,tx,tg,gate);}

__global__ void adaptive_kernel(const Case*in,Result*out,size_t n,double tx,double tg){
  size_t i=(size_t)blockIdx.x*blockDim.x+threadIdx.x;if(i>=n)return;const Case&p=in[i];
  Result a=evaluate_path(p,0,tx,tg,2);if(a.accepted){out[i]=a;return;}
  Result b=evaluate_path(p,1,tx,tg,2);if(b.accepted){out[i]=b;return;}
  Result c=evaluate_path(p,2,tx,tg,2);c.path=2;c.accepted=c.status;out[i]=c;
}

static double quant(std::vector<double>v,double p){std::sort(v.begin(),v.end());return v[(size_t)(p*(v.size()-1))];}
int main(int argc,char**argv){
  std::string refs,split="test",out="results_raw/certificate_validation";double tx=1e-7,tg=2e-6;
  for(int i=1;i<argc;i++){if(!strcmp(argv[i],"--references"))refs=argv[++i];else if(!strcmp(argv[i],"--split"))split=argv[++i];else if(!strcmp(argv[i],"--out"))out=argv[++i];else if(!strcmp(argv[i],"--tau-x"))tx=strtod(argv[++i],0);else if(!strcmp(argv[i],"--tau-g"))tg=strtod(argv[++i],0);}
  auto h=load(refs,split);if(h.empty())return 2;std::filesystem::create_directories(out);Case*di;Result*doo;cudaMalloc(&di,h.size()*sizeof(Case));cudaMalloc(&doo,h.size()*sizeof(Result));cudaMemcpy(di,h.data(),h.size()*sizeof(Case),cudaMemcpyHostToDevice);
  std::ofstream raw(out+"/certificate_samples.csv"),sum(out+"/certificate_summary.csv");
  raw<<"split,path,gate,index,accepted,truth_good,false_accept,false_reject,root_abs,rho,tightness,beta,h,branch_distance,gradient_bound,residual,bracket,status\n";
  sum<<"split,path,gate,n,accepted,false_accept,false_reject,bracket_pass,rho_median,rho_p99,tightness_median,tightness_p99\n";
  const char*pn[]={"fp32","df32","fp64"};const char*gn[]={"residual","condition","posterior"};
  for(int path=0;path<3;path++)for(int gate=0;gate<3;gate++){
    gate_kernel<<<(h.size()+255)/256,256>>>(di,doo,h.size(),path,tx,tg,gate);cudaDeviceSynchronize();std::vector<Result>r(h.size());cudaMemcpy(r.data(),doo,r.size()*sizeof(Result),cudaMemcpyDeviceToHost);
    size_t acc=0,fa=0,fr=0,bp=0;std::vector<double>rho,tight;
    for(size_t i=0;i<h.size();i++){double e=fabs(wrap(r[i].root-h[i].root));int good=r[i].status&&isfinite(e)&&e<=tx;int falsA=r[i].accepted&&!good,falsR=!r[i].accepted&&good;acc+=r[i].accepted;fa+=falsA;fr+=falsR;bp+=r[i].bracket;if(isfinite(r[i].rho)){rho.push_back(r[i].rho);if(e>0)tight.push_back(r[i].rho/e);}raw<<split<<','<<pn[path]<<','<<gn[gate]<<','<<i<<','<<int(r[i].accepted)<<','<<good<<','<<falsA<<','<<falsR<<','<<std::setprecision(17)<<e<<','<<r[i].rho<<','<<(e>0?r[i].rho/e:INFINITY)<<','<<r[i].beta<<','<<r[i].h<<','<<r[i].branch_distance<<','<<r[i].gradient_bound<<','<<r[i].residual<<','<<int(r[i].bracket)<<','<<int(r[i].status)<<'\n';}
    sum<<split<<','<<pn[path]<<','<<gn[gate]<<','<<h.size()<<','<<acc<<','<<fa<<','<<fr<<','<<bp<<','<<(rho.empty()?INFINITY:quant(rho,.5))<<','<<(rho.empty()?INFINITY:quant(rho,.99))<<','<<(tight.empty()?INFINITY:quant(tight,.5))<<','<<(tight.empty()?INFINITY:quant(tight,.99))<<'\n';
    printf("%s %s accept=%zu false_accept=%zu false_reject=%zu bracket=%zu/%zu\n",pn[path],gn[gate],acc,fa,fr,bp,h.size());
  }
  adaptive_kernel<<<(h.size()+255)/256,256>>>(di,doo,h.size(),tx,tg);cudaDeviceSynchronize();std::vector<Result>a(h.size());cudaMemcpy(a.data(),doo,a.size()*sizeof(Result),cudaMemcpyDeviceToHost);size_t paths[3]={0},fail=0;std::ofstream ar(out+"/certificate_adaptive_samples.csv");ar<<"index,path,root_abs,rho,accepted,status\n";for(size_t i=0;i<h.size();i++){double e=fabs(wrap(a[i].root-h[i].root));paths[a[i].path]++;fail+=!a[i].status||e>tx;ar<<i<<','<<int(a[i].path)<<','<<std::setprecision(17)<<e<<','<<a[i].rho<<','<<int(a[i].accepted)<<','<<int(a[i].status)<<'\n';}printf("adaptive fp32=%zu df32=%zu fp64=%zu failures=%zu/%zu\n",paths[0],paths[1],paths[2],fail,h.size());cudaFree(doo);cudaFree(di);return fail?3:0;
}
