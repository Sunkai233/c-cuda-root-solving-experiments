#define ROOT_BENCH_NO_MAIN
#include "benchmark.cu"

static void checked(cudaError_t error,const char*what){
  if(error!=cudaSuccess){std::fprintf(stderr,"%s: %s\n",what,cudaGetErrorString(error));std::exit(2);}
}

int main(int argc,char**argv){
  int domain=argc>1?std::atoi(argv[1]):KEPLER;
  int method=argc>2?std::atoi(argv[2]):2;
  size_t n=argc>3?std::strtoull(argv[3],nullptr,10):131072;
  if(domain<0||domain>4||method<0||method>3||n==0)return 2;
  std::vector<Param> h(n);for(size_t i=0;i<n;i++)h[i]=make_param(domain,i);
  Param*in=nullptr;Output*out=nullptr;checked(cudaMalloc(&in,n*sizeof(Param)),"cudaMalloc input");checked(cudaMalloc(&out,n*sizeof(Output)),"cudaMalloc output");
  checked(cudaMemcpy(in,h.data(),n*sizeof(Param),cudaMemcpyHostToDevice),"H2D");
  int blocks=int((n+255)/256);
  /* Context/JIT warm-up uses a different kernel so the selected target has one launch. */
  kernel_fp64<<<blocks,256>>>(in,out,n);checked(cudaDeviceSynchronize(),"warmup");
  if(method==0)kernel_fp32<<<blocks,256>>>(in,out,n);
  else if(method==1)kernel_fp64<<<blocks,256>>>(in,out,n);
  else if(method==2)kernel_adaptive<<<blocks,256>>>(in,out,n,3e-8,1e-4);
  else kernel_adaptive<<<blocks,256>>>(in,out,n,3e-8,1e99);
  checked(cudaDeviceSynchronize(),"target kernel");
  Output first{};checked(cudaMemcpy(&first,out,sizeof(first),cudaMemcpyDeviceToHost),"D2H checksum");
  std::printf("domain=%d method=%d n=%zu checksum=%.17g path=%u\n",domain,method,n,first.root,unsigned(first.path));
  cudaFree(out);cudaFree(in);return 0;
}
