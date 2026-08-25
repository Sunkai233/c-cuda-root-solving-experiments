#include <cuda_runtime.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#define BEM_TABLE_QUAL static __device__ __constant__
#define BEM_HD static __device__ __forceinline__
#include "bem_real_solver.h"
#include "bem_real_precision.cuh"
#include "bem_posterior_certificate.cuh"

#define CK(x) do{cudaError_t e=(x);if(e!=cudaSuccess){fprintf(stderr,"CUDA %s:%d: %s\n",__FILE__,__LINE__,cudaGetErrorString(e));exit(2);}}while(0)
typedef struct __attribute__((packed)){char magic[8];uint32_t version;uint64_t n;uint32_t nf,node_per_step,steps;} Header;
static int cmpf(const void*a,const void*b){float x=*(const float*)a,y=*(const float*)b;return(x>y)-(x<y);}
static double host_wrap(double x){x=fmod(x+BEM_PI,2*BEM_PI);if(x<0)x+=2*BEM_PI;return x-BEM_PI;}

__device__ __forceinline__ void enqueue_warp(uint64_t i,int hard,uint64_t*q,uint32_t*count){
  unsigned active=__activemask(),mask=__ballot_sync(active,hard);if(!hard)return;
  int leader=__ffs(mask)-1,lane=threadIdx.x&31;uint32_t base=0;
  if(lane==leader)base=atomicAdd(count,(uint32_t)__popc(mask));base=__shfl_sync(active,base,leader);
  unsigned lower=lane?((1u<<lane)-1u):0u;q[base+(uint32_t)__popc(mask&lower)]=i;
}

__global__ void first_kernel(const double*vx,const double*vy,const double*theta,const double*hint,
                             double*root,double*rho,uint8_t*ok,uint8_t*path,uint64_t*q,uint32_t*count,
                             uint64_t n,int method,double tx,double tg){
  uint64_t i=(uint64_t)blockIdx.x*blockDim.x+threadIdx.x;int hard=0;if(i<n){unsigned node=(unsigned)(i%51)%17;double x=NAN,rr=INFINITY;int good=0;uint8_t p=0;
    if(method==0){good=bem_solve_algorithm(vx[i],vy[i],theta[i],hint[i],node,4,&x);p=2;}
    else{float xf=0;good=bf_solve((float)vx[i],(float)vy[i],(float)theta[i],(float)hint[i],node,512,xf);x=xf;
      if(method==1){x=bd_refine(xf,vx[i],vy[i],theta[i],node);p=1;}
      else if(method==2){x=bd_refine(xf,vx[i],vy[i],theta[i],node);int v=0;double f=bem_residual(x,vx[i],vy[i],theta[i],node,&v);if(good&&v&&isfinite(f)&&fabs(f)<5e-8){p=1;}else hard=1;}
      else{
        double witness=NAN;int witnessed=bem_solve_hint_only(vx[i],vy[i],theta[i],hint[i],node,&witness);
        BemCertificate a=bem_build_certificate(x,vx[i],vy[i],theta[i],node,tx,method==4?tg:0.0);rr=fmax(a.rho,witnessed?fabs(bem_wrap_pi(x-witness))+5e-10:INFINITY);int pass=good&&witnessed&&a.posterior_pass&&a.branch_pass&&a.gradient_pass&&rr<=tx;
        if(pass)p=0;else{x=bd_refine(xf,vx[i],vy[i],theta[i],node);BemCertificate b=bem_build_certificate(x,vx[i],vy[i],theta[i],node,tx,method==4?tg:0.0);rr=fmax(b.rho,witnessed?fabs(bem_wrap_pi(x-witness))+5e-10:INFINITY);pass=good&&witnessed&&b.posterior_pass&&b.branch_pass&&b.gradient_pass&&rr<=tx;if(pass)p=1;else hard=1;}
      }
    }
    root[i]=x;rho[i]=rr;path[i]=p;ok[i]=(uint8_t)(good&&!hard);if(method==0||method==1)hard=0;
  }enqueue_warp(i,i<n&&hard,q,count);
}

__global__ void fallback_kernel(const double*vx,const double*vy,const double*theta,const double*hint,double*root,double*rho,uint8_t*ok,uint8_t*path,const uint64_t*q,const uint32_t*count,uint64_t n){uint64_t s=(uint64_t)blockIdx.x*blockDim.x+threadIdx.x;uint32_t m=*count;if(s>=m||s>=n)return;uint64_t i=q[s];unsigned node=(unsigned)(i%51)%17;double x;int good=bem_solve_algorithm(vx[i],vy[i],theta[i],hint[i],node,4,&x);root[i]=x;rho[i]=0.0;path[i]=2;ok[i]=(uint8_t)good;}

static void launch(const double*vx,const double*vy,const double*th,const double*hint,double*root,double*rho,uint8_t*ok,uint8_t*path,uint64_t*q,uint32_t*count,uint64_t n,int method,double tx,double tg){int b=(int)((n+255)/256);CK(cudaMemsetAsync(count,0,sizeof(uint32_t)));first_kernel<<<b,256>>>(vx,vy,th,hint,root,rho,ok,path,q,count,n,method,tx,tg);if(method>=2)fallback_kernel<<<b,256>>>(vx,vy,th,hint,root,rho,ok,path,q,count,n);}

int main(int argc,char**argv){if(argc<3){fprintf(stderr,"usage: %s dataset.bin method [repeats] [warmups] [tau_x] [tau_g]\n",argv[0]);return 2;}int method=atoi(argv[2]),reps=argc>3?atoi(argv[3]):30,warm=argc>4?atoi(argv[4]):10;double tx=argc>5?strtod(argv[5],0):1e-7,tg=argc>6?strtod(argv[6],0):2e-6;if(method<0||method>4)return 2;FILE*f=fopen(argv[1],"rb");Header h;if(!f||fread(&h,1,sizeof h,f)!=sizeof h||memcmp(h.magic,"BEMREAL2",8)||h.nf!=5)return 2;size_t db=(size_t)h.n*5*sizeof(double),rb=(size_t)h.n*sizeof(double),sb=(size_t)h.n;double*hbuf,*hroot,*hrho;uint8_t*hflags,*hok,*hpath;CK(cudaMallocHost(&hbuf,db));CK(cudaMallocHost(&hroot,rb));CK(cudaMallocHost(&hrho,rb));CK(cudaMallocHost(&hflags,sb));CK(cudaMallocHost(&hok,sb));CK(cudaMallocHost(&hpath,sb));if(fread(hbuf,1,db,f)!=db||fread(hflags,1,sb,f)!=sb)return 2;fclose(f);
  double*dbuf,*droot,*drho;uint8_t*dok,*dpath;uint64_t*dq;uint32_t*dc;CK(cudaMalloc(&dbuf,db));CK(cudaMalloc(&droot,rb));CK(cudaMalloc(&drho,rb));CK(cudaMalloc(&dok,sb));CK(cudaMalloc(&dpath,sb));CK(cudaMalloc(&dq,(size_t)h.n*sizeof(uint64_t)));CK(cudaMalloc(&dc,sizeof(uint32_t)));double*vx=dbuf,*vy=vx+h.n,*th=vy+h.n,*ref=hbuf+3*h.n,*hint=dbuf+4*h.n;CK(cudaMemcpy(dbuf,hbuf,db,cudaMemcpyHostToDevice));
  for(int k=0;k<warm;k++)launch(vx,vy,th,hint,droot,drho,dok,dpath,dq,dc,h.n,method,tx,tg);CK(cudaDeviceSynchronize());float*kt=(float*)malloc(reps*sizeof(float)),*et=(float*)malloc(reps*sizeof(float)),*ks=(float*)malloc(reps*sizeof(float)),*es=(float*)malloc(reps*sizeof(float));cudaEvent_t a,b;CK(cudaEventCreate(&a));CK(cudaEventCreate(&b));for(int r=0;r<reps;r++){CK(cudaEventRecord(a));launch(vx,vy,th,hint,droot,drho,dok,dpath,dq,dc,h.n,method,tx,tg);CK(cudaEventRecord(b));CK(cudaEventSynchronize(b));CK(cudaEventElapsedTime(&kt[r],a,b));}
  for(int k=0;k<warm;k++){CK(cudaMemcpyAsync(dbuf,hbuf,db,cudaMemcpyHostToDevice));launch(vx,vy,th,hint,droot,drho,dok,dpath,dq,dc,h.n,method,tx,tg);CK(cudaMemcpyAsync(hroot,droot,rb,cudaMemcpyDeviceToHost));CK(cudaMemcpyAsync(hok,dok,sb,cudaMemcpyDeviceToHost));}CK(cudaDeviceSynchronize());for(int r=0;r<reps;r++){CK(cudaEventRecord(a));CK(cudaMemcpyAsync(dbuf,hbuf,db,cudaMemcpyHostToDevice));launch(vx,vy,th,hint,droot,drho,dok,dpath,dq,dc,h.n,method,tx,tg);CK(cudaMemcpyAsync(hroot,droot,rb,cudaMemcpyDeviceToHost));CK(cudaMemcpyAsync(hrho,drho,rb,cudaMemcpyDeviceToHost));CK(cudaMemcpyAsync(hok,dok,sb,cudaMemcpyDeviceToHost));CK(cudaMemcpyAsync(hpath,dpath,sb,cudaMemcpyDeviceToHost));CK(cudaEventRecord(b));CK(cudaEventSynchronize(b));CK(cudaEventElapsedTime(&et[r],a,b));}
  size_t pc[3]={0},fail=0,wrong=0;double maxe=0,maxrho=0;for(uint64_t i=0;i<h.n;i++){pc[hpath[i]<=2?hpath[i]:2]++;fail+=!hok[i];double e=fabs(host_wrap(hroot[i]-ref[i]));wrong+=e>1e-3;maxe=fmax(maxe,e);if(isfinite(hrho[i]))maxrho=fmax(maxrho,hrho[i]);}memcpy(ks,kt,reps*sizeof(float));memcpy(es,et,reps*sizeof(float));qsort(ks,reps,sizeof(float),cmpf);qsort(es,reps,sizeof(float),cmpf);const char*name[]={"fp64_compacted","fixed_df32","threshold_adaptive","certificate_root_branch","certificate_root_branch_gradient"};printf("{\"method\":\"%s\",\"records\":%" PRIu64 ",\"repetitions\":%d,\"kernel_median_ms\":%.9g,\"e2e_median_ms\":%.9g,\"paths\":{\"fp32\":%zu,\"df32\":%zu,\"fp64\":%zu},\"solver_failures\":%zu,\"wrong_branch_gt_1e-3\":%zu,\"max_reference_difference\":%.17g,\"max_finite_rho\":%.17g,\"kernel_times_ms\":[",name[method],h.n,reps,ks[reps/2],es[reps/2],pc[0],pc[1],pc[2],fail,wrong,maxe,maxrho);for(int r=0;r<reps;r++)printf("%s%.9g",r?",":"",kt[r]);printf("],\"e2e_times_ms\":[");for(int r=0;r<reps;r++)printf("%s%.9g",r?",":"",et[r]);printf("]}\n");
  free(es);free(ks);free(et);free(kt);cudaFree(dc);cudaFree(dq);cudaFree(dpath);cudaFree(dok);cudaFree(drho);cudaFree(droot);cudaFree(dbuf);cudaFreeHost(hpath);cudaFreeHost(hok);cudaFreeHost(hflags);cudaFreeHost(hrho);cudaFreeHost(hroot);cudaFreeHost(hbuf);return 0;}
