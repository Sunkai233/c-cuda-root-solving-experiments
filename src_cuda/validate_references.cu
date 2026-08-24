#define ROOT_BENCH_NO_MAIN
#include "benchmark.cu"

#include <array>

struct RefCase { Param p; double root, gradient; std::string id,branch; };

static std::vector<std::string> split_csv(const std::string&s){
  std::vector<std::string>v;std::string x;std::stringstream ss(s);while(std::getline(ss,x,','))v.push_back(x);return v;
}
static std::vector<RefCase> load_reference(const std::string&path,int dom,const std::string&split){
  std::ifstream f(path);if(!f)throw std::runtime_error("cannot open "+path);std::string line;std::getline(f,line);std::vector<RefCase>v;
  while(std::getline(f,line)){auto c=split_csv(line);if(c.size()<15||c[2]!=split)continue;RefCase r{};r.id=c[1];r.p.domain=dom;r.branch=c[3];r.p.branch=(c[3].find("high")!=std::string::npos||c[3].find("vapor")!=std::string::npos)?1:0;for(int k=0;k<6;k++)((&r.p.a)[k])=std::strtod(c[4+k].c_str(),nullptr);r.root=std::strtod(c[10].c_str(),nullptr);r.gradient=std::strtod(c[11].c_str(),nullptr);v.push_back(r);}
  return v;
}
static double relerr(double x,double y){return fabs(x-y)/fmax(fabs(y),1e-300);}

int main(int argc,char**argv){
  std::string refdir,outdir="results_raw/validation",split="cal";bool frozen_only=false;double tau_x=1e-7;for(int i=1;i<argc;i++){if(!strcmp(argv[i],"--references"))refdir=argv[++i];else if(!strcmp(argv[i],"--out"))outdir=argv[++i];else if(!strcmp(argv[i],"--split"))split=argv[++i];else if(!strcmp(argv[i],"--frozen-only"))frozen_only=true;else if(!strcmp(argv[i],"--tau-x"))tau_x=std::strtod(argv[++i],nullptr);}
  if(refdir.empty()){std::fprintf(stderr,"--references is required\n");return 2;}std::filesystem::create_directories(outdir);
  int dev=0;cudaError_t ce=cudaGetDevice(&dev);if(ce!=cudaSuccess){std::fprintf(stderr,"cudaGetDevice: %s\n",cudaGetErrorString(ce));return 3;}cudaDeviceProp prop{};cudaGetDeviceProperties(&prop,dev);
  const char*names[]={"bem","kepler","pv","cstr","peng_robinson"};std::ofstream csv(outdir+"/validation_"+split+".csv"),raw(outdir+"/validation_"+split+"_raw.csv");
  csv<<"domain,split,method,n,root_median,root_p90,root_p95,root_p99,root_p999,root_max,gradient_median,gradient_p90,gradient_p95,gradient_p99,gradient_p999,gradient_max,residual_median,residual_p90,residual_p95,residual_p99,residual_p999,residual_max,nonfinite,root_gt_1e-7,root_gt_1e-5,corrections\n";
  raw<<"domain,sample_id,split,branch,method,reference_root,computed_root,root_abs_error,reference_gradient,computed_gradient,gradient_relative_error,residual_abs,condition_proxy,iterations,precision_path,status\n";
  for(int dom=0;dom<5;dom++){
    auto refs=load_reference(refdir+"/"+names[dom]+".csv",dom,split);std::vector<Param>p(refs.size());for(size_t i=0;i<refs.size();i++)p[i]=refs[i].p;
    Param*dp=nullptr;Output*doo=nullptr;cudaMalloc(&dp,p.size()*sizeof(Param));cudaMalloc(&doo,p.size()*sizeof(Output));cudaMemcpy(dp,p.data(),p.size()*sizeof(Param),cudaMemcpyHostToDevice);int blocks=int((p.size()+255)/256);
    const double tau_gs[]={0,0,1e-6,1e-5,1e-4,1e-3,1e-2};int method_count=frozen_only?3:7;
    for(int method=0;method<method_count;method++){
      double selected_tau=(frozen_only&&method==2)?1e-4:tau_gs[method];
      if(method==0)kernel_fp32<<<blocks,256>>>(dp,doo,p.size());else if(method==1)kernel_fp64<<<blocks,256>>>(dp,doo,p.size());else kernel_adaptive<<<blocks,256>>>(dp,doo,p.size(),tau_x,selected_tau);
      ce=cudaDeviceSynchronize();if(ce!=cudaSuccess){std::fprintf(stderr,"kernel: %s\n",cudaGetErrorString(ce));return 4;}std::vector<Output>o(p.size());cudaMemcpy(o.data(),doo,p.size()*sizeof(Output),cudaMemcpyDeviceToHost);
      std::vector<double>re,ge,rv;size_t nf=0,gt7=0,gt5=0,corr=0;char method_name[64];if(method==0)std::strcpy(method_name,"fp32");else if(method==1)std::strcpy(method_name,"fp64");else if(frozen_only)std::snprintf(method_name,sizeof(method_name),"adaptive_x%.0e",tau_x);else std::snprintf(method_name,sizeof(method_name),"adaptive_x%.0e_g%.0e",tau_x,selected_tau);const char*m=method_name;
      for(size_t i=0;i<o.size();i++){double er=fabs(o[i].root-refs[i].root),eg=relerr(o[i].gradient,refs[i].gradient);if(!isfinite(o[i].root)||!isfinite(o[i].gradient)){nf++;er=INFINITY;eg=INFINITY;}re.push_back(er);ge.push_back(eg);rv.push_back(o[i].residual);gt7+=er>1e-7;gt5+=er>1e-5;corr+=o[i].path==3;
        raw<<names[dom]<<','<<refs[i].id<<','<<split<<','<<refs[i].branch<<','<<m<<','<<std::setprecision(17)<<refs[i].root<<','<<o[i].root<<','<<er<<','<<refs[i].gradient<<','<<o[i].gradient<<','<<eg<<','<<o[i].residual<<','<<o[i].condition<<','<<o[i].iterations<<','<<int(o[i].path)<<','<<int(o[i].status)<<'\n';}
      csv<<names[dom]<<','<<split<<','<<m<<','<<refs.size()<<','<<std::setprecision(12)<<quantile(re,.5)<<','<<quantile(re,.9)<<','<<quantile(re,.95)<<','<<quantile(re,.99)<<','<<quantile(re,.999)<<','<<*std::max_element(re.begin(),re.end())<<','<<quantile(ge,.5)<<','<<quantile(ge,.9)<<','<<quantile(ge,.95)<<','<<quantile(ge,.99)<<','<<quantile(ge,.999)<<','<<*std::max_element(ge.begin(),ge.end())<<','<<quantile(rv,.5)<<','<<quantile(rv,.9)<<','<<quantile(rv,.95)<<','<<quantile(rv,.99)<<','<<quantile(rv,.999)<<','<<*std::max_element(rv.begin(),rv.end())<<','<<nf<<','<<gt7<<','<<gt5<<','<<corr<<'\n';
      std::printf("%-14s %-20s N=%zu root_max=%.3e grad_p99=%.3e gt1e-7=%zu corr=%zu\n",names[dom],m,refs.size(),*std::max_element(re.begin(),re.end()),quantile(ge,.99),gt7,corr);
    }cudaFree(dp);cudaFree(doo);
  }
  std::ofstream js(outdir+"/validation_"+split+".json");js<<"{\n  \"gpu\": \""<<prop.name<<"\",\n  \"split\": \""<<split<<"\",\n  \"reference_dir\": \""<<refdir<<"\",\n  \"adaptive_tau_x\": "<<std::setprecision(17)<<tau_x<<",\n  \"table\": \"validation_"<<split<<".csv\"\n}\n";
}
