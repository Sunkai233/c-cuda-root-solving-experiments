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
struct Case{double vx,vy,th,hint,root;int node;};struct Out{double root,res;unsigned char ok;};
static std::vector<std::string>fld(const std::string&s){std::vector<std::string>v;std::stringstream q(s);std::string x;while(getline(q,x,','))v.push_back(x);return v;}static std::vector<Case>load(const std::string&p){std::ifstream f(p);std::string l;getline(f,l);std::vector<Case>v;while(getline(f,l)){auto x=fld(l);if(x.size()>=22)v.push_back({stod(x[4]),stod(x[5]),stod(x[6]),stod(x[7]),stod(x[11]),stoi(x[3])});}return v;}
__global__ void k(const Case*in,Out*out,size_t n,int a){size_t i=(size_t)blockIdx.x*blockDim.x+threadIdx.x;if(i>=n)return;double x;int ok=bem_solve_algorithm(in[i].vx,in[i].vy,in[i].th,in[i].hint,in[i].node,a,&x),v;double r=bem_residual(x,in[i].vx,in[i].vy,in[i].th,in[i].node,&v);out[i]={x,fabs(r),(unsigned char)(ok&&v&&isfinite(r))};}
static double w(double x){x=fmod(x+BEM_PI,2*BEM_PI);if(x<0)x+=2*BEM_PI;return x-BEM_PI;}static double q(std::vector<double>v,double p){std::sort(v.begin(),v.end());return v[(size_t)(p*(v.size()-1))];}
int main(int argc,char**argv){std::string ref,out="results_raw/bem_alg_v2";for(int i=1;i<argc;i++){if(!strcmp(argv[i],"--references"))ref=argv[++i];else if(!strcmp(argv[i],"--out"))out=argv[++i];}auto c=load(ref);std::filesystem::create_directories(out);Case*d;Out*o;cudaMalloc(&d,c.size()*sizeof(Case));cudaMalloc(&o,c.size()*sizeof(Out));cudaMemcpy(d,c.data(),c.size()*sizeof(Case),cudaMemcpyHostToDevice);const char*names[]={"bisection","brent","illinois","fixed44","adaptive_compacted"};std::ofstream s(out+"/bem_algorithm_v2_summary.csv");s<<"method,n,root_p99,root_max,residual_max,wrong_gt_1e-7,wrong_branch_gt_1e-3,nonfinite\n";for(int a: {0,1,2,3,4}){k<<<int((c.size()+255)/256),256>>>(d,o,c.size(),a);std::vector<Out>h(c.size());cudaMemcpy(h.data(),o,h.size()*sizeof(Out),cudaMemcpyDeviceToHost);std::vector<double>e,r;size_t w7=0,wb=0,nf=0;for(size_t i=0;i<c.size();i++){double z=fabs(w(h[i].root-c[i].root));e.push_back(z);r.push_back(h[i].res);w7+=z>1e-7;wb+=z>1e-3;nf+=!h[i].ok;}s<<names[a]<<','<<c.size()<<','<<std::setprecision(17)<<q(e,.99)<<','<<q(e,1)<<','<<q(r,1)<<','<<w7<<','<<wb<<','<<nf<<'\n';printf("%s n=%zu rootmax=%.3e wrong=%zu branch=%zu nf=%zu\n",names[a],c.size(),q(e,1),w7,wb,nf);}cudaFree(o);cudaFree(d);}
