#define ROOT_BENCH_NO_MAIN
#include "benchmark.cu"

static void launch_method(int method,const Param*in,Output*out,size_t n,cudaStream_t stream){
  int blocks=int((n+255)/256);
  if(method==0)kernel_fp32<<<blocks,256,0,stream>>>(in,out,n);
  else if(method==1)kernel_fp64<<<blocks,256,0,stream>>>(in,out,n);
  else if(method==2)kernel_adaptive<<<blocks,256,0,stream>>>(in,out,n,1e-7,1e-4);
  else kernel_adaptive<<<blocks,256,0,stream>>>(in,out,n,1e-7,1e99);
}
static int inner_reps(size_t n){return n<2048?1000:(n<32768?100:(n<131072?10:1));}
static std::vector<double> event_samples_kernel(int method,const Param*dp,Output*doo,size_t n,int warmups,int reps,cudaStream_t stream){
  for(int k=0;k<warmups;k++)launch_method(method,dp,doo,n,stream);cudaStreamSynchronize(stream);
  int inner=inner_reps(n);cudaEvent_t a,b;cudaEventCreate(&a);cudaEventCreate(&b);std::vector<double>t;
  for(int r=0;r<reps;r++){cudaEventRecord(a,stream);for(int j=0;j<inner;j++)launch_method(method,dp,doo,n,stream);cudaEventRecord(b,stream);cudaEventSynchronize(b);float ms;cudaEventElapsedTime(&ms,a,b);t.push_back(ms/inner);}
  cudaEventDestroy(a);cudaEventDestroy(b);return t;
}
static std::vector<double> event_samples_e2e(int method,const Param*hp,Param*dp,Output*doo,Output*ho,size_t n,int warmups,int reps,cudaStream_t stream){
  for(int k=0;k<warmups;k++){cudaMemcpyAsync(dp,hp,n*sizeof(Param),cudaMemcpyHostToDevice,stream);launch_method(method,dp,doo,n,stream);cudaMemcpyAsync(ho,doo,n*sizeof(Output),cudaMemcpyDeviceToHost,stream);}cudaStreamSynchronize(stream);
  int inner=n<2048?100:(n<32768?10:1);cudaEvent_t a,b;cudaEventCreate(&a);cudaEventCreate(&b);std::vector<double>t;
  for(int r=0;r<reps;r++){cudaEventRecord(a,stream);for(int j=0;j<inner;j++){cudaMemcpyAsync(dp,hp,n*sizeof(Param),cudaMemcpyHostToDevice,stream);launch_method(method,dp,doo,n,stream);cudaMemcpyAsync(ho,doo,n*sizeof(Output),cudaMemcpyDeviceToHost,stream);}cudaEventRecord(b,stream);cudaEventSynchronize(b);float ms;cudaEventElapsedTime(&ms,a,b);t.push_back(ms/inner);}
  cudaEventDestroy(a);cudaEventDestroy(b);return t;
}

int main(int argc,char**argv){
  std::string outdir="results_raw/performance";size_t maxn=2097152;int reps=30,warm=10,heat=5;
  for(int i=1;i<argc;i++){if(!strcmp(argv[i],"--out"))outdir=argv[++i];else if(!strcmp(argv[i],"--max-n"))maxn=strtoull(argv[++i],nullptr,10);else if(!strcmp(argv[i],"--repetitions"))reps=atoi(argv[++i]);else if(!strcmp(argv[i],"--warmups"))warm=atoi(argv[++i]);else if(!strcmp(argv[i],"--heat-seconds"))heat=atoi(argv[++i]);}
  std::filesystem::create_directories(outdir);std::ofstream csv(outdir+"/performance.csv"),raw(outdir+"/performance_repetitions.csv");csv<<"domain,n,method,kernel_median_ms,e2e_median_ms,cpu128_median_ms,kernel_mroots_s,e2e_mroots_s,correction_fraction,checksum\n";raw<<"domain,n,method,timing_kind,repetition,value_ms\n";
  int dev=0;cudaError_t ce=cudaGetDevice(&dev);if(ce!=cudaSuccess){std::fprintf(stderr,"cudaGetDevice: %s\n",cudaGetErrorString(ce));return 2;}cudaDeviceProp prop{};cudaGetDeviceProperties(&prop,dev);cudaStream_t stream;cudaStreamCreate(&stream);
  // Thermal preconditioning outside all reported timings.
  size_t hn=1<<20;std::vector<Param>hp0(hn);for(size_t i=0;i<hn;i++)hp0[i]=make_param(KEPLER,i);Param*hdp;Output*hdo;cudaMalloc(&hdp,hn*sizeof(Param));cudaMalloc(&hdo,hn*sizeof(Output));cudaMemcpy(hdp,hp0.data(),hn*sizeof(Param),cudaMemcpyHostToDevice);double hs=omp_get_wtime();while(omp_get_wtime()-hs<heat)kernel_adaptive<<<int((hn+255)/256),256>>>(hdp,hdo,hn,1e-7,1e-4);cudaDeviceSynchronize();cudaFree(hdp);cudaFree(hdo);
  const char*domains[]={"bem","kepler","pv","cstr","peng_robinson"};const char*methods[]={"fp32","fp64","adaptive_frozen_v1","adaptive_no_gradient_gate"};std::vector<size_t>ns={1,8,32,128,512,2048,8192,32768,131072,524288,2097152,8388608,16777216};
  for(int dom=0;dom<5;dom++)for(size_t n:ns){if(n>maxn)continue;std::vector<Param>p(n);std::vector<Output>ho(n),co(n);for(size_t i=0;i<n;i++)p[i]=make_param(dom,i);cudaHostRegister(p.data(),n*sizeof(Param),cudaHostRegisterDefault);cudaHostRegister(ho.data(),n*sizeof(Output),cudaHostRegisterDefault);Param*dp;Output*doo;cudaMalloc(&dp,n*sizeof(Param));cudaMalloc(&doo,n*sizeof(Output));cudaMemcpy(dp,p.data(),n*sizeof(Param),cudaMemcpyHostToDevice);
    for(int k=0;k<warm;k++)cpu_run(p,co,128);std::vector<double>ct;for(int r=0;r<reps;r++){ct.push_back(cpu_run(p,co,128));raw<<domains[dom]<<','<<n<<",cpu_fp64_omp128,solve,"<<r<<','<<std::setprecision(12)<<ct.back()<<'\n';}double cm=median(ct);
    int order[4]={int(n/8+dom)%4,int(n/8+dom+1)%4,int(n/8+dom+2)%4,int(n/8+dom+3)%4};
    for(int oi=0;oi<4;oi++){int m=order[oi];auto kt=event_samples_kernel(m,dp,doo,n,warm,reps,stream);auto et=event_samples_e2e(m,p.data(),dp,doo,ho.data(),n,warm,reps,stream);double km=median(kt),em=median(et);for(int r=0;r<reps;r++){raw<<domains[dom]<<','<<n<<','<<methods[m]<<",kernel,"<<r<<','<<std::setprecision(12)<<kt[r]<<'\n';raw<<domains[dom]<<','<<n<<','<<methods[m]<<",e2e,"<<r<<','<<et[r]<<'\n';}raw.flush();launch_method(m,dp,doo,n,stream);cudaMemcpyAsync(ho.data(),doo,n*sizeof(Output),cudaMemcpyDeviceToHost,stream);cudaStreamSynchronize(stream);double checksum=0;size_t corr=0,check=std::min(n,size_t(100000));for(size_t i=0;i<check;i++){checksum+=ho[i].root*(1+(i%17));corr+=ho[i].path==3;}csv<<domains[dom]<<','<<n<<','<<methods[m]<<','<<std::setprecision(12)<<km<<','<<em<<','<<cm<<','<<n/km/1000.0<<','<<n/em/1000.0<<','<<double(corr)/check<<','<<checksum<<'\n';csv.flush();std::printf("%-14s N=%9zu %-25s kernel=%9.4f e2e=%9.4f cpu=%9.4f corr=%.3f\n",domains[dom],n,methods[m],km,em,cm,double(corr)/check);}
    cudaFree(dp);cudaFree(doo);cudaHostUnregister(p.data());cudaHostUnregister(ho.data());
  }cudaStreamDestroy(stream);ce=cudaGetLastError();if(ce!=cudaSuccess){std::fprintf(stderr,"CUDA: %s\n",cudaGetErrorString(ce));return 3;}std::ofstream js(outdir+"/performance.json");js<<"{\n \"gpu\":\""<<prop.name<<"\",\n \"warmups\":"<<warm<<",\n \"repetitions\":"<<reps<<",\n \"heat_seconds\":"<<heat<<",\n \"table\":\"performance.csv\"\n}\n";
}
