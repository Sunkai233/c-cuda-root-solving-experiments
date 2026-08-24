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
__global__ void solve_hint_kernel(const double*vx,const double*vy,const double*theta,const double*hint,
                                  double*roots,uint8_t*ok,uint64_t*queue,uint32_t*queue_count,uint64_t n){
  uint64_t i=(uint64_t)blockIdx.x*blockDim.x+threadIdx.x;if(i>=n)return;unsigned node=(unsigned)(i%51)%17;double r;
  int good=bem_solve_hint_only(vx[i],vy[i],theta[i],hint[i],node,&r);roots[i]=r;ok[i]=(uint8_t)good;
  if(!good){uint32_t slot=atomicAdd(queue_count,1u);queue[slot]=i;}
}
__global__ void solve_fallback_kernel(const double*vx,const double*vy,const double*theta,const double*hint,
                                      double*roots,uint8_t*ok,const uint64_t*queue,const uint32_t*queue_count,uint64_t n){
  uint64_t slot=(uint64_t)blockIdx.x*blockDim.x+threadIdx.x;uint32_t count=*queue_count;if(slot>=count||slot>=n)return;
  uint64_t i=queue[slot];unsigned node=(unsigned)(i%51)%17;double r;int good=bem_solve_robust_nearest(vx[i],vy[i],theta[i],hint[i],node,1,&r);roots[i]=r;ok[i]=(uint8_t)good;
}
static void launch_solver(const double*vx,const double*vy,const double*theta,const double*hint,double*roots,uint8_t*ok,
                          uint64_t*queue,uint32_t*queue_count,uint64_t n,int algorithm){
  int blocks=(int)((n+255)/256);if(algorithm!=4){solve_kernel<<<blocks,256>>>(vx,vy,theta,hint,roots,ok,n,algorithm);return;}
  CK(cudaMemsetAsync(queue_count,0,sizeof(uint32_t)));solve_hint_kernel<<<blocks,256>>>(vx,vy,theta,hint,roots,ok,queue,queue_count,n);
  solve_fallback_kernel<<<blocks,256>>>(vx,vy,theta,hint,roots,ok,queue,queue_count,n);
}

int main(int argc,char**argv){
  if(argc<2){fprintf(stderr,"usage: %s dataset.bin [repeats] [algorithm] [roots.bin] [warmups]\n",argv[0]);return 2;}
  int repeats=argc>2?atoi(argv[2]):7;if(repeats<1)repeats=1;
  int algorithm=argc>3?atoi(argv[3]):0;if(algorithm<0||algorithm>4)return 2;
  int warmups=argc>5?atoi(argv[5]):10;if(warmups<0)warmups=0;
  FILE*f=fopen(argv[1],"rb");if(!f){perror("fopen");return 2;}Header h;
  if(fread(&h,1,sizeof h,f)!=sizeof h||memcmp(h.magic,"BEMREAL2",8)||h.nf!=5){fprintf(stderr,"bad header\n");return 2;}
  size_t db=(size_t)h.n*5*sizeof(double), rb=(size_t)h.n*sizeof(double), sb=(size_t)h.n;
  double*hbuf,*hroot;uint8_t*hflags,*hok;CK(cudaMallocHost(&hbuf,db));CK(cudaMallocHost(&hflags,sb));CK(cudaMallocHost(&hroot,rb));CK(cudaMallocHost(&hok,sb));
  if(fread(hbuf,1,db,f)!=db||fread(hflags,1,sb,f)!=sb){fprintf(stderr,"short read\n");return 2;}fclose(f);
  double*dbuf,*droot;uint8_t*dok;uint64_t*dqueue;uint32_t*dqueue_count;CK(cudaMalloc(&dbuf,db));CK(cudaMalloc(&droot,rb));CK(cudaMalloc(&dok,sb));CK(cudaMalloc(&dqueue,(size_t)h.n*sizeof(uint64_t)));CK(cudaMalloc(&dqueue_count,sizeof(uint32_t)));
  double*vx=dbuf,*vy=vx+h.n,*theta=vy+h.n,*ref=hbuf+3*h.n,*hint=dbuf+4*h.n;
  CK(cudaMemcpy(dbuf,hbuf,db,cudaMemcpyHostToDevice));
  for(int i=0;i<warmups;++i)launch_solver(vx,vy,theta,hint,droot,dok,dqueue,dqueue_count,h.n,algorithm);CK(cudaDeviceSynchronize());
  cudaEvent_t a,b;CK(cudaEventCreate(&a));CK(cudaEventCreate(&b));float total=0.0f,*times=(float*)malloc(repeats*sizeof(float)),*sorted=(float*)malloc(repeats*sizeof(float));
  int kernel_inner=h.n<2048?10:(h.n<32768?5:(h.n<131072?2:1));
  for(int i=0;i<repeats;++i){CK(cudaEventRecord(a));for(int j=0;j<kernel_inner;j++)launch_solver(vx,vy,theta,hint,droot,dok,dqueue,dqueue_count,h.n,algorithm);CK(cudaEventRecord(b));CK(cudaEventSynchronize(b));CK(cudaEventElapsedTime(&times[i],a,b));times[i]/=kernel_inner;total+=times[i];}
  cudaEvent_t ea,eb;CK(cudaEventCreate(&ea));CK(cudaEventCreate(&eb));
  float*e2e=(float*)malloc(repeats*sizeof(float)),*e2e_sorted=(float*)malloc(repeats*sizeof(float));
  for(int i=0;i<warmups;++i){CK(cudaMemcpyAsync(dbuf,hbuf,db,cudaMemcpyHostToDevice));launch_solver(vx,vy,theta,hint,droot,dok,dqueue,dqueue_count,h.n,algorithm);CK(cudaMemcpyAsync(hroot,droot,rb,cudaMemcpyDeviceToHost));CK(cudaMemcpyAsync(hok,dok,sb,cudaMemcpyDeviceToHost));}CK(cudaDeviceSynchronize());
  int e2e_inner=h.n<2048?5:(h.n<32768?2:1);
  for(int i=0;i<repeats;++i){CK(cudaEventRecord(ea));for(int j=0;j<e2e_inner;j++){CK(cudaMemcpyAsync(dbuf,hbuf,db,cudaMemcpyHostToDevice));launch_solver(vx,vy,theta,hint,droot,dok,dqueue,dqueue_count,h.n,algorithm);CK(cudaMemcpyAsync(hroot,droot,rb,cudaMemcpyDeviceToHost));CK(cudaMemcpyAsync(hok,dok,sb,cudaMemcpyDeviceToHost));}CK(cudaEventRecord(eb));CK(cudaEventSynchronize(eb));CK(cudaEventElapsedTime(&e2e[i],ea,eb));e2e[i]/=e2e_inner;}
  if(argc>4){FILE*rf=fopen(argv[4],"wb");if(!rf||fwrite(hroot,sizeof(double),(size_t)h.n,rf)!=(size_t)h.n){fprintf(stderr,"root output failed\n");return 2;}fclose(rf);}
  double*err=(double*)malloc(rb);size_t fail=0,branch=0,fast=0,fallback=0;for(uint64_t i=0;i<h.n;++i){if(!hok[i])fail++;fast+=hok[i]==2;fallback+=hok[i]==1;double e=fabs(host_wrap(hroot[i]-ref[i]));if(e>1e-3)branch++;err[i]=e;}
  qsort(err,(size_t)h.n,sizeof(double),cmpd);memcpy(sorted,times,repeats*sizeof(float));memcpy(e2e_sorted,e2e,repeats*sizeof(float));qsort(sorted,repeats,sizeof(float),cmpf);qsort(e2e_sorted,repeats,sizeof(float),cmpf);double ms=total/repeats;
  printf("{\"algorithm\":%d,\"records\":%" PRIu64 ",\"warmups\":%d,\"repeats\":%d,\"kernel_inner\":%d,\"e2e_inner\":%d,\"kernel_ms_mean\":%.6f,\"kernel_ms_median\":%.6f,\"kernel_ms_min\":%.6f,\"kernel_ms_max\":%.6f,\"end_to_end_ms_median\":%.6f,\"throughput_roots_s\":%.6f,\"solver_failures\":%zu,\"fast_path\":%zu,\"fallback_path\":%zu,\"branch_error_gt_1e-3\":%zu,\"root_abs_rad\":{\"median\":%.17g,\"p95\":%.17g,\"p99\":%.17g,\"max\":%.17g},\"kernel_times_ms\":[",algorithm,h.n,warmups,repeats,kernel_inner,e2e_inner,ms,sorted[repeats/2],sorted[0],sorted[repeats-1],e2e_sorted[repeats/2],1e3*h.n/ms,fail,fast,fallback,branch,q(err,h.n,.5),q(err,h.n,.95),q(err,h.n,.99),err[h.n-1]);
  for(int i=0;i<repeats;i++)printf("%s%.9g",i?",":"",times[i]);printf("],\"end_to_end_times_ms\":[");for(int i=0;i<repeats;i++)printf("%s%.9g",i?",":"",e2e[i]);printf("]}\n");
  free(e2e_sorted);free(e2e);free(sorted);free(times);free(err);CK(cudaFree(dqueue_count));CK(cudaFree(dqueue));CK(cudaFree(dok));CK(cudaFree(droot));CK(cudaFree(dbuf));CK(cudaFreeHost(hok));CK(cudaFreeHost(hroot));CK(cudaFreeHost(hflags));CK(cudaFreeHost(hbuf));return 0;
}
