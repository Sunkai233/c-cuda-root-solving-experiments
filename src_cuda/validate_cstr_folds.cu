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

enum : unsigned char { ROOT_OK=0, ROOT_NONFINITE=1, ROOT_BRANCH_AMBIGUOUS=2 };
struct Case { double da,g,b,root,grad,cond,reg; int branch,root_count; };
struct Out { double root,grad,cond,reg,residual; int branch,root_count; unsigned char status; };
struct Hist { double da,g,b,root; int expected_branch,expected_count,history,step,crossed; };
struct HistOut { double root; int branch,root_count,crossed; unsigned char status; };
struct Unknown { double da,g,b; int expected_count; };
struct UnknownOut { int root_count; unsigned char status; };

static std::vector<std::string> fields(const std::string&s){std::vector<std::string>v;std::stringstream q(s);std::string x;while(std::getline(q,x,','))v.push_back(x);return v;}
static int branch_id(std::string s){if(s.find("low")==0)return 1;if(s.find("middle")==0)return 2;if(s.find("high")==0)return 3;return 0;}
static double rel(double a,double b){return std::abs(a-b)/std::max(std::abs(b),1e-300);}
static double quant(std::vector<double>v,double p){std::sort(v.begin(),v.end());return v[(size_t)(p*(v.size()-1))];}

__device__ __forceinline__ void eval(double x,double da,double g,double b,double&f,double&fx,double&fda){
  double lr=log(da)+g*b*x/(g+b*x),s;
  if(lr>=0){double t=exp(-lr);s=1/(1+t);}else{double t=exp(lr);s=t/(1+t);}
  f=x-s; fx=1-s*(1-s)*g*g*b/((g+b*x)*(g+b*x)); fda=-s*(1-s)/da;
}
__device__ __forceinline__ double fold_eq(double x,double g,double b){return 1/x+1/(1-x)-g*g*b/((g+b*x)*(g+b*x));}
__device__ double bisect_fold(double a,double z,double g,double b){double fa=fold_eq(a,g,b);for(int k=0;k<80;k++){double m=.5*(a+z),fm=fold_eq(m,g,b);if(signbit(fa)!=signbit(fm))z=m;else{a=m;fa=fm;}}return .5*(a+z);}
__device__ int find_folds(double g,double b,double*q){int n=0;double a=1e-10,fa=fold_eq(a,g,b);for(int k=1;k<=4096&&n<2;k++){double z=1e-10+(1-2e-10)*double(k)/4096.0,fz=fold_eq(z,g,b);if(signbit(fa)!=signbit(fz))q[n++]=bisect_fold(a,z,g,b);a=z;fa=fz;}return n;}
__device__ double bisect_root(double a,double z,double da,double g,double b){double fa,fx,fd,fm;eval(a,da,g,b,fa,fx,fd);for(int k=0;k<90;k++){double m=.5*(a+z);eval(m,da,g,b,fm,fx,fd);if(signbit(fa)!=signbit(fm))z=m;else{a=m;fa=fm;}}return .5*(a+z);}
__device__ int all_roots(double da,double g,double b,double*r){double q[2],bounds[4]={0,0,0,1};int nf=find_folds(g,b,q);if(nf==2){bounds[1]=q[0];bounds[2]=q[1];}else{bounds[1]=bounds[2]=.5;}int n=0,segs=nf==2?3:1;for(int j=0;j<segs;j++){double a=bounds[j],z=bounds[j+1],fa,fx,fd,fz;eval(a,da,g,b,fa,fx,fd);eval(z,da,g,b,fz,fx,fd);if(fa==0)r[n++]=a;if(signbit(fa)!=signbit(fz))r[n++]=bisect_root(a,z,da,g,b);if(j==segs-1&&fz==0)r[n++]=z;}return n;}
__device__ int selected_branch(int n,int idx){return n==1?0:idx+1;}

__global__ void static_kernel(const Case*in,Out*out,size_t n){size_t i=(size_t)blockIdx.x*blockDim.x+threadIdx.x;if(i>=n)return;Case p=in[i];double rr[3],f,fx,fda;int nr=all_roots(p.da,p.g,p.b,rr),idx=0;if(nr==3&&p.branch>0)idx=p.branch-1;double x=nr?rr[idx]:NAN;eval(x,p.da,p.g,p.b,f,fx,fda);Out o{x,-fda/fx,1/fabs(fx),-fda*fx/(fx*fx+1e-8),fabs(f),selected_branch(nr,idx),nr,ROOT_OK};if(nr<1||!isfinite(o.root)||!isfinite(o.grad)||!isfinite(o.reg))o.status=ROOT_NONFINITE;out[i]=o;}
__global__ void history_kernel(const Hist*in,HistOut*out,int histories,int steps){int h=blockIdx.x*blockDim.x+threadIdx.x;if(h>=histories)return;double prev=NAN;int pb=-1;for(int k=0;k<steps;k++){int i=h*steps+k;Hist p=in[i];double rr[3];int nr=all_roots(p.da,p.g,p.b,rr),idx=0;if(nr>1&&isfinite(prev)){double d=fabs(rr[0]-prev);for(int j=1;j<nr;j++)if(fabs(rr[j]-prev)<d){idx=j;d=fabs(rr[j]-prev);}}else if(nr>1)idx=(p.expected_branch==3)?nr-1:0;int br=selected_branch(nr,idx),cross=(pb>=0&&br!=pb&&(br==0||pb==0));double x=nr?rr[idx]:NAN;out[i]={x,br,nr,cross,(unsigned char)((nr&&isfinite(x))?ROOT_OK:ROOT_NONFINITE)};prev=x;pb=br;}}
__global__ void unknown_kernel(const Unknown*in,UnknownOut*out,size_t n){size_t i=(size_t)blockIdx.x*blockDim.x+threadIdx.x;if(i>=n)return;double r[3];int nr=all_roots(in[i].da,in[i].g,in[i].b,r);out[i]={nr,(unsigned char)(nr>1?ROOT_BRANCH_AMBIGUOUS:ROOT_OK)};}

static std::vector<Case> load_static(const std::string&dir,const std::string&split){std::ifstream a(dir+"/cstr.csv"),m(dir+"/cstr_fold_metrics.csv");std::string la,lm;std::getline(a,la);std::getline(m,lm);std::vector<Case>v;while(std::getline(a,la)&&std::getline(m,lm)){auto x=fields(la),y=fields(lm);if(x.size()<15||y.size()<13||x[2]!=split)continue;v.push_back({stod(x[4]),stod(x[5]),stod(x[6]),stod(x[10]),stod(x[11]),stod(y[7]),stod(y[9]),branch_id(x[3]),stoi(x[13])});}return v;}
static std::vector<Hist> load_hist(const std::string&dir){std::ifstream f(dir+"/cstr_continuation.csv");std::string l,last;std::getline(f,l);std::vector<Hist>v;int h=-1;while(std::getline(f,l)){auto x=fields(l);if(x[0]!=last){last=x[0];h++;}v.push_back({stod(x[3]),stod(x[4]),stod(x[5]),stod(x[8]),branch_id(x[9]),stoi(x[6]),h,stoi(x[2]),stoi(x[10])});}return v;}
static std::vector<Unknown> load_unknown(const std::string&dir){std::ifstream f(dir+"/cstr_unknown_history.csv");std::string l;std::getline(f,l);std::vector<Unknown>v;while(std::getline(f,l)){auto x=fields(l);v.push_back({stod(x[1]),stod(x[2]),stod(x[3]),stoi(x[4])});}return v;}

int main(int argc,char**argv){std::string refs,split="cal",outdir="results_raw/cstr_fold";for(int i=1;i<argc;i++){if(!strcmp(argv[i],"--references"))refs=argv[++i];else if(!strcmp(argv[i],"--split"))split=argv[++i];else if(!strcmp(argv[i],"--out"))outdir=argv[++i];}if(refs.empty())return 2;std::filesystem::create_directories(outdir);auto c=load_static(refs,split);auto h=load_hist(refs);auto u=load_unknown(refs);if(c.empty()||h.empty()||u.empty()||h.size()%81){fprintf(stderr,"load failure static=%zu history=%zu unknown=%zu\n",c.size(),h.size(),u.size());return 3;}
  Case*dc;Out*doo;cudaMalloc(&dc,c.size()*sizeof(Case));cudaMalloc(&doo,c.size()*sizeof(Out));cudaMemcpy(dc,c.data(),c.size()*sizeof(Case),cudaMemcpyHostToDevice);static_kernel<<<int((c.size()+127)/128),128>>>(dc,doo,c.size());std::vector<Out>o(c.size());cudaMemcpy(o.data(),doo,o.size()*sizeof(Out),cudaMemcpyDeviceToHost);
  Hist*dh;HistOut*dho;cudaMalloc(&dh,h.size()*sizeof(Hist));cudaMalloc(&dho,h.size()*sizeof(HistOut));cudaMemcpy(dh,h.data(),h.size()*sizeof(Hist),cudaMemcpyHostToDevice);history_kernel<<<1,32>>>(dh,dho,int(h.size()/81),81);std::vector<HistOut>ho(h.size());cudaMemcpy(ho.data(),dho,ho.size()*sizeof(HistOut),cudaMemcpyDeviceToHost);
  Unknown*du;UnknownOut*duo;cudaMalloc(&du,u.size()*sizeof(Unknown));cudaMalloc(&duo,u.size()*sizeof(UnknownOut));cudaMemcpy(du,u.data(),u.size()*sizeof(Unknown),cudaMemcpyHostToDevice);unknown_kernel<<<1,32>>>(du,duo,u.size());std::vector<UnknownOut>uo(u.size());cudaMemcpy(uo.data(),duo,uo.size()*sizeof(UnknownOut),cudaMemcpyDeviceToHost);cudaDeviceSynchronize();
  std::vector<double>er,eg,ec,erg,eh;size_t wrong=0,nf=0;std::ofstream raw(outdir+"/cstr_fold_"+split+"_samples.csv");raw<<"index,branch,root_count,root_abs,gradient_rel,condition_rel,regularized_rel,residual,status\n";for(size_t i=0;i<c.size();i++){double a=fabs(o[i].root-c[i].root),b=rel(o[i].grad,c[i].grad),d=rel(o[i].cond,c[i].cond),e=rel(o[i].reg,c[i].reg);er.push_back(a);eg.push_back(b);ec.push_back(d);erg.push_back(e);wrong+=(o[i].branch!=c[i].branch||o[i].root_count!=c[i].root_count);nf+=o[i].status!=ROOT_OK;raw<<i<<','<<o[i].branch<<','<<o[i].root_count<<','<<std::setprecision(17)<<a<<','<<b<<','<<d<<','<<e<<','<<o[i].residual<<','<<int(o[i].status)<<'\n';}
  size_t hwrong=0,uwrong=0;std::ofstream hr(outdir+"/cstr_continuation_samples.csv");hr<<"history,step,root_abs,branch,root_count,crossed,status\n";for(size_t i=0;i<h.size();i++){double e=fabs(ho[i].root-h[i].root);eh.push_back(e);hwrong+=(ho[i].branch!=h[i].expected_branch||ho[i].root_count!=h[i].expected_count||ho[i].crossed!=h[i].crossed||ho[i].status!=ROOT_OK);hr<<h[i].history<<','<<h[i].step<<','<<std::setprecision(17)<<e<<','<<ho[i].branch<<','<<ho[i].root_count<<','<<ho[i].crossed<<','<<int(ho[i].status)<<'\n';}for(size_t i=0;i<u.size();i++)uwrong+=(uo[i].root_count!=u[i].expected_count||uo[i].status!=ROOT_BRANCH_AMBIGUOUS);
  std::ofstream s(outdir+"/cstr_fold_"+split+"_summary.csv");s<<"split,n,root_max,gradient_p99,gradient_max,condition_max,regularized_max,wrong_branch_or_count,nonfinite,continuation_n,continuation_root_max,continuation_wrong,ambiguous_n,ambiguous_wrong\n"<<split<<','<<c.size()<<','<<std::setprecision(17)<<quant(er,1)<<','<<quant(eg,.99)<<','<<quant(eg,1)<<','<<quant(ec,1)<<','<<quant(erg,1)<<','<<wrong<<','<<nf<<','<<h.size()<<','<<quant(eh,1)<<','<<hwrong<<','<<u.size()<<','<<uwrong<<'\n';
  printf("split=%s n=%zu root_max=%.3e grad_max=%.3e reg_max=%.3e wrong=%zu nonfinite=%zu continuation_max=%.3e continuation_wrong=%zu ambiguous_wrong=%zu\n",split.c_str(),c.size(),quant(er,1),quant(eg,1),quant(erg,1),wrong,nf,quant(eh,1),hwrong,uwrong);return (wrong||nf||hwrong||uwrong)?4:0;}
