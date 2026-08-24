#define _GNU_SOURCE
#include <inttypes.h>
#include <math.h>
#include <omp.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "../include/bem_real_solver.h"
typedef struct __attribute__((packed)){char magic[8];uint32_t version;uint64_t n;uint32_t nf,nodes,steps;}Header;
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC_RAW,&t);return(double)t.tv_sec+1e-9*t.tv_nsec;}static int cmp(const void*a,const void*b){double x=*(const double*)a,y=*(const double*)b;return(x>y)-(x<y);}static double median(double*x,int n){double*v=malloc((size_t)n*sizeof(double));memcpy(v,x,(size_t)n*sizeof(double));qsort(v,n,sizeof(double),cmp);double z=v[n/2];free(v);return z;}
static void solve_all(uint64_t n,const double*restrict vx,const double*restrict vy,const double*restrict th,const double*restrict hint,double*restrict roots,uint8_t*restrict ok,int alg,int threads){
#pragma omp parallel for schedule(static) num_threads(threads)
 for(uint64_t i=0;i<n;i++){double x;int good=bem_solve_algorithm(vx[i],vy[i],th[i],hint[i],(unsigned)(i%51u)%17u,alg,&x);roots[i]=x;ok[i]=(uint8_t)good;}}
int main(int argc,char**argv){if(argc<5){fprintf(stderr,"dataset out.csv threads mode\n");return 2;}const char*dataset=argv[1],*out=argv[2];int threads=atoi(argv[3]),reps=30,warm=10;FILE*f=fopen(dataset,"rb");Header h;if(!f||fread(&h,1,sizeof h,f)!=sizeof h||memcmp(h.magic,"BEMREAL2",8))return 3;size_t db=(size_t)h.n*5*sizeof(double);double*buf=aligned_alloc(64,(db+63)&~(size_t)63),*roots=aligned_alloc(64,((size_t)h.n*sizeof(double)+63)&~(size_t)63);uint8_t*flags=malloc((size_t)h.n),*ok=malloc((size_t)h.n);if(fread(buf,1,db,f)!=db||fread(flags,1,(size_t)h.n,f)!=(size_t)h.n)return 4;fclose(f);double*vx=buf,*vy=vx+h.n,*th=vy+h.n,*hint=buf+4*h.n;FILE*o=fopen(out,"w");fprintf(o,"algorithm,threads,repetition,time_ms,failures,checksum\n");const int algs[]={0,1,2,4};const char*names[]={"bisection","brent","illinois","adaptive_compacted"};for(int z=0;z<4;z++){int a=algs[z];for(int k=0;k<warm;k++)solve_all(h.n,vx,vy,th,hint,roots,ok,a,threads);double*t=malloc((size_t)reps*sizeof(double));for(int r=0;r<reps;r++){double s=now();solve_all(h.n,vx,vy,th,hint,roots,ok,a,threads);t[r]=(now()-s)*1e3;size_t fail=0;double sum=0;for(uint64_t i=0;i<h.n;i++){fail+=!ok[i];sum+=roots[i]*(1+i%17);}fprintf(o,"%s,%d,%d,%.12g,%zu,%.17g\n",names[z],threads,r,t[r],fail,sum);fflush(o);}printf("%s threads=%d median_ms=%.3f\n",names[z],threads,median(t,reps));free(t);}fclose(o);free(ok);free(flags);free(roots);free(buf);}
