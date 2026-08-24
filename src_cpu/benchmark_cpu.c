#define _GNU_SOURCE
#include <errno.h>
#include <inttypes.h>
#include <math.h>
#include <omp.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

enum { BEM=0, KEPLER=1, PV=2, CSTR=3, PR=4 };
enum { ROOT_OK=0, ROOT_NONFINITE=4, ROOT_GRADIENT_RISK=5 };
typedef struct { double a,b,c,d,e,f; int domain,branch; } Param;
typedef struct { double root,residual,gradient,condition; uint32_t iterations; uint8_t path,status,pad[2]; } Output;

static inline double clampd(double x,double lo,double hi){return x<lo?lo:(x>hi?hi:x);}
static inline void residual(const Param *restrict p,double x,double *restrict y,double *restrict dy){
  if(p->domain==BEM){double s=sin(x),co=cos(x),cl=p->d*(x-p->c),cn=cl*co+p->e*s,ct=cl*s-p->e*co;
    double cnp=p->d*co-cl*s+p->e*co,ctp=p->d*s+cl*co+p->e*s,q=cn+ct/p->a,qp=cnp+ctp/p->a;
    *y=s-co/p->a+(p->b*.25)*q/s;*dy=co+s/p->a+(p->b*.25)*(qp*s-q*co)/(s*s);
  }else if(p->domain==KEPLER){*y=x-p->a*sin(x)-p->b;*dy=1.0-p->a*cos(x);
  }else if(p->domain==PV){double z=(p->b+x*p->e)/p->d,ez=exp(clampd(z,-80,80));
    *y=x-p->a+p->c*(ez-1.0)+(p->b+x*p->e)/p->f;*dy=1.0+p->c*ez*p->e/p->d+p->e/p->f;
  }else if(p->domain==CSTR){double den=p->b+p->c*x,ex=p->b*p->c*x/den,r=p->a*exp(ex),rp=r*(p->b*p->b*p->c)/(den*den);
    *y=x-r/(1.0+r);*dy=1.0-rp/((1.0+r)*(1.0+r));
  }else{double A=p->a,B=p->b;*y=x*x*x-(1.0-B)*x*x+(A-3*B*B-2*B)*x-(A*B-B*B-B*B*B);*dy=3*x*x-2*(1-B)*x+A-3*B*B-2*B;}
}
static inline void bounds(const Param*p,double*lo,double*hi,double*x){
  if(p->domain==BEM){*lo=1e-4;*hi=1.5707;*x=atan(1.0/p->a);}else if(p->domain==KEPLER){*lo=0;*hi=3.141592653589793;*x=p->b+.85*p->a;}
  else if(p->domain==PV){*lo=0;*hi=p->a;*x=p->a*(1.0-p->b/(p->d*log(p->a/p->c+1.0)+1e-30));}
  else if(p->domain==CSTR){*lo=0;*hi=1;*x=p->branch?.9:.1;}else{*lo=p->b+1e-8;*hi=2;*x=p->branch?1.0:p->b+.02;}
  *x=clampd(*x,*lo,*hi);
}
static inline double solve_newton(const Param*p,int steps,uint32_t*used){double lo,hi,x,fl,dl;bounds(p,&lo,&hi,&x);residual(p,lo,&fl,&dl);*used=0;
  for(int k=0;k<steps;k++){double y,dy,c;residual(p,x,&y,&dy);if((fl<=0&&y>=0)||(fl>=0&&y<=0))hi=x;else{lo=x;fl=y;}c=x-y/dy;if(!isfinite(c)||c<=lo||c>=hi)c=.5*(lo+hi);x=c;(*used)++;}return x;}
static inline double solve_branch(const Param*p,int steps,uint32_t*used){double lo=p->domain==CSTR?0:p->b+1e-12,hi=p->domain==CSTR?1:2,prev=lo,fp,df;residual(p,prev,&fp,&df);
  double firsta=lo,firstb=hi,lasta=lo,lastb=hi;int found=0;for(int s=1;s<=256;s++){double z=lo+(hi-lo)*s/256.0,fz;residual(p,z,&fz,&df);
    if((fp<=0&&fz>=0)||(fp>=0&&fz<=0)){if(!found){firsta=prev;firstb=z;}lasta=prev;lastb=z;found++;}prev=z;fp=fz;}
  if(!found)return solve_newton(p,steps,used);
  double a=p->branch?lasta:firsta,b=p->branch?lastb:firstb,fa;residual(p,a,&fa,&df);*used=0;
  for(int k=0;k<steps;k++){double m=.5*(a+b),fm;residual(p,m,&fm,&df);if((fa<=0&&fm>=0)||(fa>=0&&fm<=0))b=m;else{a=m;fa=fm;}(*used)++;}return .5*(a+b);}
static inline double solve_cubic(const Param*p,uint32_t*used){double A=p->a,B=p->b,a=B-1,b=A-3*B*B-2*B,c=-(A*B-B*B-B*B*B),Q=(a*a-3*b)/9,R=(2*a*a*a-9*a*b+27*c)/54;*used=1;
  if(Q>0&&R*R<Q*Q*Q){double th=acos(clampd(R/sqrt(Q*Q*Q),-1,1)),sq=2*sqrt(Q),pi=3.14159265358979323846;
    double rr[3]={-sq*cos(th/3)-a/3,-sq*cos((th+2*pi)/3)-a/3,-sq*cos((th+4*pi)/3)-a/3},low=1e300,high=-1e300;
    for(int i=0;i<3;i++)if(rr[i]>B){if(rr[i]<low)low=rr[i];if(rr[i]>high)high=rr[i];}
    return p->branch?high:low;}
  double disc=fmax(R*R-Q*Q*Q,0),s=sqrt(disc);return -(cbrt(R+s)+cbrt(R-s))-a/3;}
static inline Output solve_one(const Param*p){uint32_t it;double x=p->domain==PR?solve_cubic(p,&it):(p->domain==CSTR?solve_branch(p,60,&it):solve_newton(p,60,&it));double y,dy,fp=0;residual(p,x,&y,&dy);
  if(p->domain==BEM){double s=sin(x),co=cos(x),cl=p->d*(x-p->c),ct=cl*s-p->e*co;fp=co/(p->a*p->a)-p->b*ct/(4*s*p->a*p->a);}
  else if(p->domain==KEPLER)fp=-1;else if(p->domain==PV){double ez=exp(clampd((p->b+x*p->e)/p->d,-80,80));fp=p->c*ez/p->d+1/p->f;}
  else if(p->domain==CSTR){double den=p->b+p->c*x,r=p->a*exp(p->b*p->c*x/den);fp=-(r/p->a)/((1+r)*(1+r));}else fp=x-p->b;
  Output o={x,fabs(y),-fp/dy,1.0/fmax(fabs(dy),1e-300),it,3,ROOT_OK,{0,0}};if(!isfinite(x)||!isfinite(y)||!isfinite(dy))o.status=ROOT_NONFINITE;else if(fabs(dy)<1e-8)o.status=ROOT_GRADIENT_RISK;return o;}

static uint64_t mix64(uint64_t x){x+=0x9e3779b97f4a7c15ULL;x=(x^(x>>30))*0xbf58476d1ce4e5b9ULL;x=(x^(x>>27))*0x94d049bb133111ebULL;return x^(x>>31);}
static double u01(uint64_t x){return (mix64(x)>>11)*0x1.0p-53;}
static Param make_param(int dom,size_t i){double u=u01(i*7+dom),v=u01(i*7+dom+1),w=u01(i*7+dom+2);Param p={0};p.domain=dom;p.branch=(int)(i&1);
  if(dom==BEM){p.a=1+13*u;p.b=.02+.18*v;p.c=-.034906585+.314159265*w;p.d=6.283185307179586;p.e=.006+.014*v;double fl,fh,dd;residual(&p,1e-4,&fl,&dd);residual(&p,1.5707,&fh,&dd);if(fl*fh>0)p.c=-.034906585;}
  else if(dom==KEPLER){p.a=(i%5==0)?1.0-pow(10.0,-7.0-4.0*u):.99*u;p.b=(i%5==0)?pow(10.0,-8.0+6.0*v):3.141592653589793*v;}
  else if(dom==PV){p.a=1+11*u;p.c=pow(10.0,-12.0+5.0*v);p.d=1+1.4*w;p.e=.02+.78*u;p.f=100*pow(10.0,1.5*v);p.b=.995*v*(p.d*log(p.a/p.c+1.0));}
  else if(dom==CSTR){if(i%3==0){const double da[]={.010420977722,.002845279817,.0003348429804},g[]={88.35475208,19.26544214,27.34093610},be[]={20.49129565,22.71097963,74.11707092};int k=(int)((i/3)%3);p.a=da[k]*(.97+.06*u);p.b=g[k]*(.97+.06*v);p.c=be[k]*(.97+.06*w);}else{p.a=pow(10.0,-3+4*u);p.b=2+28*v;p.c=.05+5*w;}}
  else{if(i%3==0){const double A[]={.3351162029,.2888302441,.1770232339},B[]={.04279662762,.03130383695,.0004873637057};int k=(int)((i/3)%3);p.a=A[k]*(.98+.04*u);p.b=B[k]*(.98+.04*v);}else{p.a=.45+.8*u;p.b=.02+.18*v;}}return p;}
static double now_ms(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC_RAW,&t);return 1000.0*t.tv_sec+1e-6*t.tv_nsec;}
static int cmpd(const void*a,const void*b){double x=*(const double*)a,y=*(const double*)b;return(x>y)-(x<y);}
static double median(double*x,int n){qsort(x,(size_t)n,sizeof(double),cmpd);return x[n/2];}
static double run(const Param*restrict p,Output*restrict o,size_t n,int mode,int threads){double t=now_ms();
  if(mode==0){for(size_t i=0;i<n;i++)o[i]=solve_one(p+i);}
  else if(mode==1){
    #pragma omp simd aligned(p,o:64)
    for(size_t i=0;i<n;i++)o[i]=solve_one(p+i);
  }else{
    #pragma omp parallel for simd schedule(static) num_threads(threads) aligned(p,o:64)
    for(size_t i=0;i<n;i++)o[i]=solve_one(p+i);
  }return now_ms()-t;}
int main(int argc,char**argv){const char*out=argc>1?argv[1]:"cpu_performance.csv";size_t maxn=argc>2?strtoull(argv[2],0,10):16777216;int reps=argc>3?atoi(argv[3]):30,warm=argc>4?atoi(argv[4]):10,threads=argc>5?atoi(argv[5]):128,only=argc>6?atoi(argv[6]):-1;
  FILE*f=fopen(out,"w");if(!f){perror("fopen");return 2;}fprintf(f,"domain,n,mode,repetition,time_ms,throughput_mroots_s,checksum,nonfinite\n");
  const size_t ns[]={1,8,32,128,512,2048,8192,32768,131072,524288,2097152,8388608,16777216};const char*dn[]={"bem","kepler","pv","cstr","peng_robinson"},*mn[]={"serial","omp_simd_1t","omp_parallel_simd"};
  for(int dom=0;dom<5;dom++)for(size_t ni=0;ni<sizeof(ns)/sizeof(ns[0]);ni++){size_t n=ns[ni];if(n>maxn)continue;Param*p=0;Output*o=0;if(posix_memalign((void**)&p,64,n*sizeof(*p))||posix_memalign((void**)&o,64,n*sizeof(*o))){fprintf(stderr,"allocation failed\n");return 2;}for(size_t i=0;i<n;i++)p[i]=make_param(dom,i);
    for(int mode=0;mode<3;mode++){if(only>=0&&mode!=only)continue;for(int k=0;k<warm;k++)run(p,o,n,mode,threads);double*ts=malloc((size_t)reps*sizeof(double));
      for(int r=0;r<reps;r++){ts[r]=run(p,o,n,mode,threads);double sum=0;size_t nf=0;for(size_t i=0;i<n;i++){sum+=o[i].root*(1+(i%17));nf+=o[i].status==ROOT_NONFINITE;}fprintf(f,"%s,%zu,%s,%d,%.12g,%.12g,%.17g,%zu\n",dn[dom],n,mn[mode],r,ts[r],n/ts[r]/1000.0,sum,nf);}fflush(f);double med=median(ts,reps);printf("%-14s n=%9zu %-17s median=%10.4f ms\n",dn[dom],n,mn[mode],med);free(ts);}
    free(o);free(p);
  }fclose(f);return 0;}
