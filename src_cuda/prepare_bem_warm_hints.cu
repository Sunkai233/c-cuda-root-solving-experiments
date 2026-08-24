#include <cuda_runtime.h>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#define BEM_TABLE_QUAL static __device__ __constant__
#define BEM_HD static __device__ __forceinline__
#include "bem_real_solver.h"
#define CK(x) do{cudaError_t e=(x);if(e!=cudaSuccess){fprintf(stderr,"CUDA: %s\n",cudaGetErrorString(e));exit(2);}}while(0)
struct __attribute__((packed)) Header{char magic[8];uint32_t version;uint64_t n;uint32_t nf,nodes,steps;};
__global__ void continuation(const double*vx,const double*vy,const double*theta,const double*initial_hint,double*roots,uint64_t n,unsigned nodes){
 unsigned node=threadIdx.x;if(node>=nodes)return;double hint=initial_hint[node];
 for(uint64_t i=node;i<n;i+=nodes){double root;int ok=bem_solve_algorithm(vx[i],vy[i],theta[i],hint,node%17,4,&root);if(!ok)root=atan2(vx[i],vy[i]);roots[i]=root;hint=root;}
}
int main(int argc,char**argv){if(argc!=3){fprintf(stderr,"usage: %s input.bin output.bin\n",argv[0]);return 2;}FILE*f=fopen(argv[1],"rb");Header h;if(!f||fread(&h,1,sizeof(h),f)!=sizeof(h)||memcmp(h.magic,"BEMREAL2",8)||h.nf!=5)return 2;size_t db=(size_t)h.n*5*sizeof(double),sb=(size_t)h.n;double*host=(double*)malloc(db),*roots=(double*)malloc((size_t)h.n*sizeof(double));uint8_t*flags=(uint8_t*)malloc(sb);if(!host||!roots||!flags)return 2;if(fread(host,1,db,f)!=db||fread(flags,1,sb,f)!=sb)return 2;fclose(f);double*dev,*dr;CK(cudaMalloc(&dev,db));CK(cudaMalloc(&dr,(size_t)h.n*sizeof(double)));CK(cudaMemcpy(dev,host,db,cudaMemcpyHostToDevice));continuation<<<1,h.nodes>>>(dev,dev+h.n,dev+2*h.n,dev+4*h.n,dr,h.n,h.nodes);CK(cudaDeviceSynchronize());CK(cudaMemcpy(roots,dr,(size_t)h.n*sizeof(double),cudaMemcpyDeviceToHost));double*hint=host+4*h.n;for(uint64_t i=h.nodes;i<h.n;i++)hint[i]=roots[i-h.nodes];FILE*out=fopen(argv[2],"wb");if(!out||fwrite(&h,1,sizeof(h),out)!=sizeof(h)||fwrite(host,1,db,out)!=db||fwrite(flags,1,sb,out)!=sb)return 2;fclose(out);printf("records=%llu nodes=%u steps=%u\n",(unsigned long long)h.n,h.nodes,h.steps);CK(cudaFree(dr));CK(cudaFree(dev));free(flags);free(roots);free(host);return 0;}
