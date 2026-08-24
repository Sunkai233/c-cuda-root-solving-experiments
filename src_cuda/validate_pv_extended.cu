#define ROOT_BENCH_NO_MAIN
#include "benchmark.cu"

struct PVRef{Param p;std::string id,split,region;double root,power,g[6];};
struct PVOut{double root,power,g[6],residual,z;uint8_t status;};
static std::vector<std::string> fields(const std::string&s){std::vector<std::string>v;std::stringstream q(s);std::string x;while(std::getline(q,x,','))v.push_back(x);return v;}
static std::vector<PVRef> load(const std::string&path,const std::string&wanted){
  std::ifstream f(path);std::string line;std::getline(f,line);std::vector<PVRef>v;
  while(std::getline(f,line)){auto c=fields(line);if(c.size()<22||c[1]!=wanted)continue;PVRef r{};r.id=c[0];r.split=c[1];r.region=c[2];r.p={stod(c[3]),stod(c[8]),stod(c[4]),stod(c[5]),stod(c[6]),stod(c[7]),PV,0};r.root=stod(c[11]);r.power=stod(c[12]);for(int k=0;k<6;k++)r.g[k]=stod(c[13+k]);v.push_back(r);}return v;
}
__global__ void kernel_pv_extended(const Param*in,PVOut*out,size_t n){
  size_t i=(size_t)blockIdx.x*blockDim.x+threadIdx.x;if(i>=n)return;const Param&p=in[i];uint32_t used;double x=solve_newton<double>(p,60,used),z=(p.b+x*p.e)/p.d,ez=exp(z),fi=1+p.c*ez*p.e/p.d+p.e/p.f;PVOut o{};o.root=x;o.power=p.b*x;o.z=z;
  double part[6]={p.c*ez/p.d+1/p.f,-1,ez-1,-p.c*ez*(p.b+x*p.e)/(p.d*p.d),p.c*ez*x/p.d+x/p.f,-(p.b+x*p.e)/(p.f*p.f)};
  for(int k=0;k<6;k++)o.g[k]=-part[k]/fi;double dy;o.residual=0;residual(p,x,o.residual,dy);o.residual=fabs(o.residual);o.status=(!isfinite(x)||!isfinite(ez)||!isfinite(fi))?1:0;out[i]=o;
}
static double rel(double a,double b){return fabs(a-b)/fmax(fabs(b),1e-30);}
static double quant(std::vector<double>v,double p){std::sort(v.begin(),v.end());return v[(size_t)(p*(v.size()-1))];}
int main(int argc,char**argv){
  std::string refs,split="cal",outdir="results_raw/pv_extended_validation";for(int i=1;i<argc;i++){if(!strcmp(argv[i],"--references"))refs=argv[++i];else if(!strcmp(argv[i],"--split"))split=argv[++i];else if(!strcmp(argv[i],"--out"))outdir=argv[++i];}if(refs.empty())return 2;std::filesystem::create_directories(outdir);auto r=load(refs,split);if(r.empty())return 3;std::vector<Param>p(r.size());for(size_t i=0;i<r.size();i++)p[i]=r[i].p;Param*dp;PVOut*doo;cudaMalloc(&dp,p.size()*sizeof(Param));cudaMalloc(&doo,p.size()*sizeof(PVOut));cudaMemcpy(dp,p.data(),p.size()*sizeof(Param),cudaMemcpyHostToDevice);kernel_pv_extended<<<int((p.size()+255)/256),256>>>(dp,doo,p.size());cudaDeviceSynchronize();std::vector<PVOut>o(p.size());cudaMemcpy(o.data(),doo,o.size()*sizeof(PVOut),cudaMemcpyDeviceToHost);
  const char*gn[]={"dI_dV","dI_dIL","dI_dI0","dI_da","dI_dRs","dI_dRsh"};std::vector<double>root,power,g[6];size_t nf=0,over=0,under=0;std::ofstream raw(outdir+"/pv_extended_"+split+"_samples.csv");raw<<"sample_id,split,region,root_abs,power_abs";for(auto n:gn)raw<<','<<n<<"_rel";raw<<",residual,exp_argument,status\n";
  for(size_t i=0;i<o.size();i++){double er=fabs(o[i].root-r[i].root),ep=fabs(o[i].power-r[i].power);root.push_back(er);power.push_back(ep);raw<<r[i].id<<','<<split<<','<<r[i].region<<','<<std::setprecision(17)<<er<<','<<ep;for(int k=0;k<6;k++){double e=rel(o[i].g[k],r[i].g[k]);g[k].push_back(e);raw<<','<<e;}raw<<','<<o[i].residual<<','<<o[i].z<<','<<int(o[i].status)<<'\n';nf+=o[i].status;over+=o[i].z>709.0;under+=o[i].z<-745.0;}
  std::ofstream sum(outdir+"/pv_extended_"+split+"_summary.csv");sum<<"metric,median,p90,p95,p99,p99.9,max\n";auto emit=[&](const char*n,const std::vector<double>&v){sum<<n;for(double q:{.5,.9,.95,.99,.999,1.0})sum<<','<<std::setprecision(12)<<quant(v,q);sum<<'\n';};emit("root_absolute",root);emit("power_absolute",power);for(int k=0;k<6;k++)emit(gn[k],g[k]);sum<<"nonfinite,"<<nf<<"\nexp_overflow,"<<over<<"\nexp_underflow,"<<under<<'\n';std::printf("split=%s n=%zu root_max=%.3e power_max=%.3e grad_max=",split.c_str(),r.size(),quant(root,1),quant(power,1));for(int k=0;k<6;k++)std::printf("%s%s:%.3e",k?",":"",gn[k],quant(g[k],1));std::printf(" nonfinite=%zu overflow=%zu underflow=%zu\n",nf,over,under);cudaFree(doo);cudaFree(dp);return 0;
}
