#include <cuda_runtime.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define BEM_TABLE_QUAL static __device__ __constant__
#define BEM_HD static __device__ __forceinline__
#include "bem_real_solver.h"

#define CK(x) do{cudaError_t e=(x);if(e!=cudaSuccess){fprintf(stderr,"CUDA %s:%d: %s\n",__FILE__,__LINE__,cudaGetErrorString(e));exit(2);}}while(0)
typedef struct __attribute__((packed)){char magic[8];uint32_t version;uint64_t n;uint32_t nf,node_per_step,steps;} Header;
static int cmpd(const void*a,const void*b){double x=*(const double*)a,y=*(const double*)b;return(x>y)-(x<y);}
static int cmpf(const void*a,const void*b){float x=*(const float*)a,y=*(const float*)b;return(x>y)-(x<y);}
static double q(double*x,size_t n,double p){return x[(size_t)(p*(n-1))];}
static double host_wrap(double x){x=fmod(x+BEM_PI,2.0*BEM_PI);if(x<0)x+=2.0*BEM_PI;return x-BEM_PI;}

__global__ void solve_kernel(const double*vx,const double*vy,const double*theta,
                             const double*hint,double*roots,uint8_t*ok,uint64_t n,int algorithm){
  uint64_t i=(uint64_t)blockIdx.x*blockDim.x+threadIdx.x;
  if(i<n){unsigned node=(unsigned)(i%51)%17;double r;int good=bem_solve_algorithm(vx[i],vy[i],theta[i],hint[i],node,algorithm,&r);roots[i]=r;ok[i]=(uint8_t)good;}
}

int main(int argc,char**argv){
  if(argc<2){fprintf(stderr,"usage: %s dataset.bin [repeats] [algorithm] [roots.bin]\n",argv[0]);return 2;}
  int repeats=argc>2?atoi(argv[2]):7;if(repeats<1)repeats=1;
  int algorithm=argc>3?atoi(argv[3]):0;if(algorithm<0||algorithm>3)return 2;
  FILE*f=fopen(argv[1],"rb");if(!f){perror("fopen");return 2;}Header h;
  if(fread(&h,1,sizeof h,f)!=sizeof h||memcmp(h.magic,"BEMREAL2",8)||h.nf!=5){fprintf(stderr,"bad header\n");return 2;}
  size_t db=(size_t)h.n*5*sizeof(double), rb=(size_t)h.n*sizeof(double), sb=(size_t)h.n;
  double*hbuf,*hroot;uint8_t*hflags,*hok;CK(cudaMallocHost(&hbuf,db));CK(cudaMallocHost(&hflags,sb));CK(cudaMallocHost(&hroot,rb));CK(cudaMallocHost(&hok,sb));
  if(fread(hbuf,1,db,f)!=db||fread(hflags,1,sb,f)!=sb){fprintf(stderr,"short read\n");return 2;}fclose(f);
  double*dbuf,*droot;uint8_t*dok;CK(cudaMalloc(&dbuf,db));CK(cudaMalloc(&droot,rb));CK(cudaMalloc(&dok,sb));
  double*vx=dbuf,*vy=vx+h.n,*theta=vy+h.n,*ref=hbuf+3*h.n,*hint=dbuf+4*h.n;
  CK(cudaMemcpy(dbuf,hbuf,db,cudaMemcpyHostToDevice));
  int threads=256;int blocks=(int)((h.n+threads-1)/threads);
  for(int i=0;i<2;++i)solve_kernel<<<blocks,threads>>>(vx,vy,theta,hint,droot,dok,h.n,algorithm);CK(cudaDeviceSynchronize());
  cudaEvent_t a,b;CK(cudaEventCreate(&a));CK(cudaEventCreate(&b));float total=0.0f,*times=(float*)malloc(repeats*sizeof(float));
  for(int i=0;i<repeats;++i){CK(cudaEventRecord(a));solve_kernel<<<blocks,threads>>>(vx,vy,theta,hint,droot,dok,h.n,algorithm);CK(cudaEventRecord(b));CK(cudaEventSynchronize(b));CK(cudaEventElapsedTime(&times[i],a,b));total+=times[i];}
  cudaEvent_t ea,eb;CK(cudaEventCreate(&ea));CK(cudaEventCreate(&eb));
  CK(cudaEventRecord(ea));
  CK(cudaMemcpyAsync(dbuf,hbuf,db,cudaMemcpyHostToDevice));
  solve_kernel<<<blocks,threads>>>(vx,vy,theta,hint,droot,dok,h.n,algorithm);
  CK(cudaMemcpyAsync(hroot,droot,rb,cudaMemcpyDeviceToHost));
  CK(cudaMemcpyAsync(hok,dok,sb,cudaMemcpyDeviceToHost));
  CK(cudaEventRecord(eb));CK(cudaEventSynchronize(eb));float e2e_ms;CK(cudaEventElapsedTime(&e2e_ms,ea,eb));
  if(argc>4){FILE*rf=fopen(argv[4],"wb");if(!rf||fwrite(hroot,sizeof(double),(size_t)h.n,rf)!=(size_t)h.n){fprintf(stderr,"root output failed\n");return 2;}fclose(rf);}
  double*err=(double*)malloc(rb);size_t fail=0,branch=0;for(uint64_t i=0;i<h.n;++i){if(!hok[i])fail++;double e=fabs(host_wrap(hroot[i]-ref[i]));if(e>1e-3)branch++;err[i]=e;}
  qsort(err,(size_t)h.n,sizeof(double),cmpd);qsort(times,repeats,sizeof(float),cmpf);double ms=total/repeats;
  printf("{\"algorithm\":%d,\"records\":%" PRIu64 ",\"repeats\":%d,\"kernel_ms_mean\":%.6f,\"kernel_ms_median\":%.6f,\"kernel_ms_min\":%.6f,\"kernel_ms_max\":%.6f,\"end_to_end_ms\":%.6f,\"throughput_roots_s\":%.6f,\"solver_failures\":%zu,\"branch_error_gt_1e-3\":%zu,\"root_abs_rad\":{\"median\":%.17g,\"p95\":%.17g,\"p99\":%.17g,\"max\":%.17g}}\n",algorithm,h.n,repeats,ms,times[repeats/2],times[0],times[repeats-1],e2e_ms,1e3*h.n/ms,fail,branch,q(err,h.n,.5),q(err,h.n,.95),q(err,h.n,.99),err[h.n-1]);
  free(times);free(err);CK(cudaFree(dok));CK(cudaFree(droot));CK(cudaFree(dbuf));CK(cudaFreeHost(hok));CK(cudaFreeHost(hroot));CK(cudaFreeHost(hflags));CK(cudaFreeHost(hbuf));return 0;
}
