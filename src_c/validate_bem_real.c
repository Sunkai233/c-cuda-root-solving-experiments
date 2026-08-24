#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "bem_real_solver.h"

typedef struct __attribute__((packed)) { char magic[8]; uint32_t version; uint64_t n; uint32_t nf,node_per_step,steps; } Header;
static int cmpd(const void*a,const void*b){double x=*(const double*)a,y=*(const double*)b;return(x>y)-(x<y);}
static double q(double*x,size_t n,double p){size_t i=(size_t)(p*(n-1));return x[i];}

int main(int argc,char**argv){
  if(argc<2){fprintf(stderr,"usage: %s dataset.bin [stride] [algorithm:0=bisection,1=brent,2=illinois,3=fixed44] [roots.bin] [repetitions] [warmups]\n",argv[0]);return 2;}
  size_t stride=argc>2?strtoull(argv[2],0,10):101; if(!stride)stride=1;
  int algorithm=argc>3?atoi(argv[3]):0;if(algorithm<0||algorithm>4)return 2;
  int repetitions=argc>5?atoi(argv[5]):30,warmups=argc>6?atoi(argv[6]):10;if(repetitions<1||warmups<0)return 2;
  FILE*f=fopen(argv[1],"rb");if(!f){perror("fopen");return 2;}
  Header h; if(fread(&h,1,sizeof h,f)!=sizeof h||memcmp(h.magic,"BEMREAL2",8)||h.nf!=5){fprintf(stderr,"bad header size=%zu\n",sizeof h);return 2;}
  double*buf=(double*)malloc((size_t)h.n*5*sizeof(double));uint8_t*flags=(uint8_t*)malloc((size_t)h.n);
  if(!buf||!flags){fprintf(stderr,"allocation failed\n");return 2;}
  if(fread(buf,sizeof(double),(size_t)h.n*5,f)!=(size_t)h.n*5||fread(flags,1,(size_t)h.n,f)!=(size_t)h.n){fprintf(stderr,"short read\n");return 2;}fclose(f);
  double*vx=buf,*vy=vx+h.n,*theta=vy+h.n,*ref=theta+h.n,*hint=ref+h.n;
  size_t cap=(size_t)((h.n+stride-1)/stride),m=0,fail=0,branch=0;
  double*err=malloc(cap*sizeof(double)),*roots=malloc(cap*sizeof(double)),*delta=malloc(cap*sizeof(double));
  if(!err||!roots||!delta){fprintf(stderr,"allocation failed\n");return 2;}
  double*times=malloc((size_t)repetitions*sizeof(double)),*sorted=malloc((size_t)repetitions*sizeof(double));if(!times||!sorted){fprintf(stderr,"allocation failed\n");return 2;}
  for(int rep=-warmups;rep<repetitions;rep++){struct timespec t0,t1;clock_gettime(CLOCK_MONOTONIC_RAW,&t0);m=0;
    for(uint64_t i=0;i<h.n;i+=stride){unsigned node=(unsigned)(i%51)%17;double root;int ok=bem_solve_algorithm(vx[i],vy[i],theta[i],hint[i],node,algorithm,&root);
      if(rep>=0&&rep==repetitions-1){if(!ok)fail++;double e=fabs(bem_wrap_pi(root-ref[i]));if(e>1e-3)branch++;roots[m]=root;err[m]=e;}m++;
    }
    clock_gettime(CLOCK_MONOTONIC_RAW,&t1);if(rep>=0)times[rep]=1e3*(t1.tv_sec-t0.tv_sec)+1e-6*(t1.tv_nsec-t0.tv_nsec);
  }
  memcpy(sorted,times,(size_t)repetitions*sizeof(double));qsort(sorted,(size_t)repetitions,sizeof(double),cmpd);double solve_ms=sorted[repetitions/2];
  if(argc>4){FILE*rf=fopen(argv[4],"wb");if(!rf||fwrite(roots,sizeof(double),m,rf)!=m){fprintf(stderr,"root output failed\n");return 2;}fclose(rf);}
  size_t k=0,diff1e8=0,diff1e6=0;
  for(uint64_t i=0;i<h.n;i+=stride){double reference=roots[k];unsigned node=(unsigned)(i%51)%17;
    if(algorithm!=0)(void)bem_solve(vx[i],vy[i],theta[i],hint[i],node,&reference);
    double d=fabs(bem_wrap_pi(roots[k]-reference));delta[k++]=d;if(d>1e-8)diff1e8++;if(d>1e-6)diff1e6++;
  }
  qsort(err,m,sizeof(double),cmpd);
  qsort(delta,m,sizeof(double),cmpd);
  printf("{\"algorithm\":%d,\"records_total\":%"PRIu64",\"stride\":%zu,\"evaluated\":%zu,\"warmups\":%d,\"repetitions\":%d,\"solve_ms_median\":%.6f,\"throughput_roots_s\":%.6f,\"solver_failures\":%zu,\"branch_error_gt_1e-3\":%zu,\"root_abs_rad\":{\"median\":%.17g,\"p95\":%.17g,\"p99\":%.17g,\"max\":%.17g},\"vs_bisection\":{\"gt_1e-8\":%zu,\"gt_1e-6\":%zu,\"p99\":%.17g,\"max\":%.17g},\"solve_times_ms\":[",algorithm,h.n,stride,m,warmups,repetitions,solve_ms,1e3*m/solve_ms,fail,branch,q(err,m,.5),q(err,m,.95),q(err,m,.99),err[m-1],diff1e8,diff1e6,q(delta,m,.99),delta[m-1]);for(int i=0;i<repetitions;i++)printf("%s%.9g",i?",":"",times[i]);printf("]}\n");
  free(sorted);free(times);free(delta);free(roots);free(err);free(flags);free(buf);return 0;
}
