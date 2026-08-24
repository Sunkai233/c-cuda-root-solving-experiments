#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#define PI 3.141592653589793238462643383279502884
static double wrap(double x){x=fmod(x+PI,2.0*PI);if(x<0)x+=2.0*PI;return x-PI;}
int main(int argc,char**argv){
  if(argc!=3){fprintf(stderr,"usage: %s cpu.bin gpu.bin\n",argv[0]);return 2;}
  FILE*a=fopen(argv[1],"rb"),*b=fopen(argv[2],"rb");if(!a||!b){perror("fopen");return 2;}
  uint64_t n=0,c8=0,c6=0,c3=0;double x,y,mx=0.0;
  while(fread(&x,sizeof x,1,a)==1){if(fread(&y,sizeof y,1,b)!=1){fprintf(stderr,"length mismatch\n");return 2;}
    double d=fabs(wrap(x-y));if(d>mx)mx=d;if(d>1e-8)c8++;if(d>1e-6)c6++;if(d>1e-3)c3++;n++;}
  if(fread(&y,sizeof y,1,b)==1){fprintf(stderr,"length mismatch\n");return 2;}
  printf("{\"records\":%llu,\"gt_1e-8\":%llu,\"gt_1e-6\":%llu,\"gt_1e-3\":%llu,\"max_abs_rad\":%.17g}\n",
    (unsigned long long)n,(unsigned long long)c8,(unsigned long long)c6,(unsigned long long)c3,mx);
  fclose(a);fclose(b);return 0;
}
