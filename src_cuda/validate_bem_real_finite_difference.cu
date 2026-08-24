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
struct Case{double vx,vy,th,hint,root,gl,gr,knot;int node;};struct Out{double fd,rp,rm;unsigned char ok;};
static std::vector<std::string>fs(const std::string&s){std::vector<std::string>v;std::stringstream q(s);std::string x;while(getline(q,x,','))v.push_back(x);return v;}static std::vector<Case>load(const std::string&p,const std::string&split){std::ifstream f(p);std::string l;getline(f,l);std::vector<Case>v;while(getline(f,l)){auto x=fs(l);if(x.size()<22||x[2]!=split)continue;v.push_back({stod(x[4]),stod(x[5]),stod(x[6]),stod(x[7]),stod(x[11]),stod(x[16]),stod(x[17]),stod(x[18]),stoi(x[3])});}return v;}
__device__ double wrapd(double x){x=fmod(x+BEM_PI,2*BEM_PI);if(x<0)x+=2*BEM_PI;return x-BEM_PI;}__global__ void k(const Case*in,Out*out,size_t n,double relh){size_t i=(size_t)blockIdx.x*blockDim.x+threadIdx.x;if(i>=n)return;Case p=in[i];double h=relh*fmax(1.0,fabs(p.vx)),rp,rm;int a=bem_solve_algorithm(p.vx+h,p.vy,p.th,p.hint,p.node,4,&rp),b=bem_solve_algorithm(p.vx-h,p.vy,p.th,p.hint,p.node,4,&rm);out[i]={wrapd(rp-rm)/(2*h),rp,rm,(unsigned char)(a&&b)};}
static double rel(double a,double b){return fabs(a-b)/fmax(fabs(b),1e-30);}static double q(std::vector<double>v,double p){std::sort(v.begin(),v.end());return v[(size_t)(p*(v.size()-1))];}static double wh(double x){x=fmod(x+BEM_PI,2*BEM_PI);if(x<0)x+=2*BEM_PI;return x-BEM_PI;}
int main(int argc,char**argv){std::string ref,split="cal",out="results_raw/bem_fd";for(int i=1;i<argc;i++){if(!strcmp(argv[i],"--references"))ref=argv[++i];else if(!strcmp(argv[i],"--split"))split=argv[++i];else if(!strcmp(argv[i],"--out"))out=argv[++i];}auto c=load(ref,split);std::filesystem::create_directories(out);Case*d;Out*o;cudaMalloc(&d,c.size()*sizeof(Case));cudaMalloc(&o,c.size()*sizeof(Out));cudaMemcpy(d,c.data(),c.size()*sizeof(Case),cudaMemcpyHostToDevice);double hs[]={1e-3,3e-4,1e-4,3e-5,1e-5,3e-6,1e-6,3e-7,1e-7};std::vector<double>best(c.size(),INFINITY);std::vector<int>valid(c.size());std::ofstream raw(out+"/bem_finite_difference_"+split+".csv");raw<<"index,h_relative,near_knot,fd,min_side_relative_error,branch_change,status\n";size_t branch=0,nf=0;for(double h:hs){k<<<int((c.size()+255)/256),256>>>(d,o,c.size(),h);std::vector<Out>x(c.size());cudaMemcpy(x.data(),o,x.size()*sizeof(Out),cudaMemcpyDeviceToHost);for(size_t i=0;i<c.size();i++){double e=fmin(rel(x[i].fd,c[i].gl),rel(x[i].fd,c[i].gr));int bc=fabs(wh(x[i].rp-c[i].root))>.01||fabs(wh(x[i].rm-c[i].root))>.01;branch+=bc;nf+=!x[i].ok||!isfinite(x[i].fd);if(!bc&&x[i].ok&&isfinite(e)){best[i]=fmin(best[i],e);valid[i]++;}raw<<i<<','<<h<<','<<(c[i].knot<=1e-3)<<','<<std::setprecision(17)<<x[i].fd<<','<<e<<','<<bc<<','<<int(x[i].ok)<<'\n';}}std::vector<double>all,near,away;size_t no=0;for(size_t i=0;i<c.size();i++)if(valid[i]){all.push_back(best[i]);(c[i].knot<=1e-3?near:away).push_back(best[i]);}else no++;std::ofstream s(out+"/bem_finite_difference_"+split+"_summary.csv");s<<"group,n,best_step_relative_error_median,p99,max,no_valid_step,branch_change_step_count,nonfinite_step_count\n";auto emit=[&](const char*n,std::vector<double>v){s<<n<<','<<v.size()<<','<<q(v,.5)<<','<<q(v,.99)<<','<<q(v,1)<<','<<no<<','<<branch<<','<<nf<<'\n';};emit("all",all);if(!near.empty())emit("near_knot",near);emit("away",away);printf("n=%zu best_rel_max=%.3e p99=%.3e no_valid=%zu branch_steps=%zu nonfinite_steps=%zu\n",c.size(),q(all,1),q(all,.99),no,branch,nf);}
