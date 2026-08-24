#define main validation_algorithms_main_disabled
#include "validate_algorithms.cu"
#undef main

static void launch_alg(int method,const Param*in,Output*out,size_t n,cudaStream_t stream){kernel_algorithm<<<int((n+255)/256),256,0,stream>>>(in,out,n,method);}
static Param make_param_alg(int dom,size_t i){
  if(dom!=BEM)return make_param(dom,i);
  // Keep the analytic BEM comparison in its predeclared smooth, single-root
  // operating envelope.  Other parameters still vary independently; no sample
  // is replicated to inflate N.  Correctness sentinels verify this assumption.
  Param p=make_param(dom,i);p.c=-0.034906585+0.02*u01(i*11+99);double fl,fh,df;residual(p,1e-4,fl,df);residual(p,1.5707,fh,df);if(fl*fh>0)p.c=-0.034906585;return p;
}
static int inner_kernel_alg(size_t n){return n<2048?1000:(n<32768?100:(n<131072?10:1));}
static std::vector<double> sample_kernel_alg(int method,const Param*dp,Output*doo,size_t n,int warm,int reps,cudaStream_t stream){
  for(int i=0;i<warm;i++)launch_alg(method,dp,doo,n,stream);cudaStreamSynchronize(stream);int inner=inner_kernel_alg(n);cudaEvent_t a,b;cudaEventCreate(&a);cudaEventCreate(&b);std::vector<double>v;
  for(int r=0;r<reps;r++){cudaEventRecord(a,stream);for(int k=0;k<inner;k++)launch_alg(method,dp,doo,n,stream);cudaEventRecord(b,stream);cudaEventSynchronize(b);float ms;cudaEventElapsedTime(&ms,a,b);v.push_back(ms/inner);}cudaEventDestroy(a);cudaEventDestroy(b);return v;
}
static std::vector<double> sample_e2e_alg(int method,const Param*hp,Param*dp,Output*doo,Output*ho,size_t n,int warm,int reps,cudaStream_t stream){
  for(int i=0;i<warm;i++){cudaMemcpyAsync(dp,hp,n*sizeof(Param),cudaMemcpyHostToDevice,stream);launch_alg(method,dp,doo,n,stream);cudaMemcpyAsync(ho,doo,n*sizeof(Output),cudaMemcpyDeviceToHost,stream);}cudaStreamSynchronize(stream);int inner=n<2048?100:(n<32768?10:1);cudaEvent_t a,b;cudaEventCreate(&a);cudaEventCreate(&b);std::vector<double>v;
  for(int r=0;r<reps;r++){cudaEventRecord(a,stream);for(int k=0;k<inner;k++){cudaMemcpyAsync(dp,hp,n*sizeof(Param),cudaMemcpyHostToDevice,stream);launch_alg(method,dp,doo,n,stream);cudaMemcpyAsync(ho,doo,n*sizeof(Output),cudaMemcpyDeviceToHost,stream);}cudaEventRecord(b,stream);cudaEventSynchronize(b);float ms;cudaEventElapsedTime(&ms,a,b);v.push_back(ms/inner);}cudaEventDestroy(a);cudaEventDestroy(b);return v;
}

int main(int argc,char**argv){
  std::string outdir="results_raw/algorithm_performance";size_t maxn=16777216;int reps=30,warm=10,heat=45;for(int i=1;i<argc;i++){if(!strcmp(argv[i],"--out"))outdir=argv[++i];else if(!strcmp(argv[i],"--max-n"))maxn=strtoull(argv[++i],nullptr,10);else if(!strcmp(argv[i],"--repetitions"))reps=atoi(argv[++i]);else if(!strcmp(argv[i],"--warmups"))warm=atoi(argv[++i]);else if(!strcmp(argv[i],"--heat-seconds"))heat=atoi(argv[++i]);}
  std::filesystem::create_directories(outdir);std::ofstream csv(outdir+"/algorithm_performance.csv"),raw(outdir+"/algorithm_performance_repetitions.csv");csv<<"domain,n,method,kernel_median_ms,e2e_median_ms,kernel_mroots_s,e2e_mroots_s,root_p99,root_max,wrong_root,iterations_median,iterations_p99,checksum\n";raw<<"domain,n,method,timing_kind,repetition,value_ms\n";
  int dev=0;cudaSetDevice(dev);cudaDeviceProp prop{};cudaGetDeviceProperties(&prop,dev);cudaStream_t stream;cudaStreamCreate(&stream);
  size_t hn=1<<20;std::vector<Param>hp0(hn);for(size_t i=0;i<hn;i++)hp0[i]=make_param(KEPLER,i);Param*hdp;Output*hdo;cudaMalloc(&hdp,hn*sizeof(Param));cudaMalloc(&hdo,hn*sizeof(Output));cudaMemcpy(hdp,hp0.data(),hn*sizeof(Param),cudaMemcpyHostToDevice);double hs=omp_get_wtime();while(omp_get_wtime()-hs<heat)launch_alg(3,hdp,hdo,hn,stream);cudaStreamSynchronize(stream);cudaFree(hdp);cudaFree(hdo);
  const char*domains[]={"bem","kepler","pv","cstr","peng_robinson"};const char*methods[]={"brent_dekker","bracketed_secant","safeguarded_newton","safeguarded_halley","analytic_cubic","mikkola_kepler","lambert_w","chandrupatla","bishop_transform"};std::vector<size_t>ns={1,8,32,128,512,2048,8192,32768,131072,524288,2097152,8388608,16777216};
  for(int dom=0;dom<5;dom++)for(size_t n:ns){if(n>maxn)continue;std::vector<Param>p(n);std::vector<Output>ho(n);for(size_t i=0;i<n;i++)p[i]=make_param_alg(dom,i);cudaHostRegister(p.data(),n*sizeof(Param),cudaHostRegisterDefault);cudaHostRegister(ho.data(),n*sizeof(Output),cudaHostRegisterDefault);Param*dp;Output*doo;cudaMalloc(&dp,n*sizeof(Param));cudaMalloc(&doo,n*sizeof(Output));cudaMemcpy(dp,p.data(),n*sizeof(Param),cudaMemcpyHostToDevice);const int ids[5][7]={{0,1,2,3,-1,-1,-1},{0,1,2,3,5,-1,-1},{0,1,2,3,6,7,8},{0,1,2,3,-1,-1,-1},{0,1,2,3,4,-1,-1}};int count=dom==PV?7:(dom==KEPLER||dom==PR?5:4),start=int((n/8+dom)%count);
    for(int oi=0;oi<count;oi++){int m=ids[dom][(start+oi)%count];auto kt=sample_kernel_alg(m,dp,doo,n,warm,reps,stream),et=sample_e2e_alg(m,p.data(),dp,doo,ho.data(),n,warm,reps,stream);for(int r=0;r<reps;r++){raw<<domains[dom]<<','<<n<<','<<methods[m]<<",kernel,"<<r<<','<<std::setprecision(12)<<kt[r]<<'\n';raw<<domains[dom]<<','<<n<<','<<methods[m]<<",e2e,"<<r<<','<<et[r]<<'\n';}raw.flush();launch_alg(m,dp,doo,n,stream);cudaMemcpyAsync(ho.data(),doo,n*sizeof(Output),cudaMemcpyDeviceToHost,stream);cudaStreamSynchronize(stream);size_t check=std::min(n,size_t(100000));std::vector<double>err,it;size_t wrong=0;double checksum=0;for(size_t i=0;i<check;i++){uint32_t u;double ref=dom==PR?solve_pr_cubic<double>(p[i],u):solve_bisection_alg(p[i],u),e=fabs(ho[i].root-ref);err.push_back(e);it.push_back(ho[i].iterations);wrong+=e>1e-7;checksum+=ho[i].root*(1+(i%17));}double km=median(kt),em=median(et);csv<<domains[dom]<<','<<n<<','<<methods[m]<<','<<std::setprecision(12)<<km<<','<<em<<','<<n/km/1000.0<<','<<n/em/1000.0<<','<<quantile(err,.99)<<','<<*std::max_element(err.begin(),err.end())<<','<<wrong<<','<<quantile(it,.5)<<','<<quantile(it,.99)<<','<<checksum<<'\n';csv.flush();std::printf("%-14s N=%9zu %-20s kernel=%9.4f e2e=%9.4f wrong=%zu it99=%.0f\n",domains[dom],n,methods[m],km,em,wrong,quantile(it,.99));}
    cudaFree(dp);cudaFree(doo);cudaHostUnregister(p.data());cudaHostUnregister(ho.data());
  }
  cudaStreamDestroy(stream);std::ofstream js(outdir+"/algorithm_performance.json");js<<"{\n  \"gpu\": \""<<prop.name<<"\",\n  \"precision\": \"strict_fp64\",\n  \"warmups\": "<<warm<<",\n  \"repetitions\": "<<reps<<",\n  \"heat_seconds\": "<<heat<<"\n}\n";
}
