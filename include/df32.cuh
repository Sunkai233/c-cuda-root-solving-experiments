#pragma once
#include <cuda_runtime.h>
#include <cmath>
#include <cstdint>

// Certified-style double-single building blocks.  Every elementary operation
// uses an explicit round-to-nearest CUDA intrinsic so compiler contraction
// cannot destroy the error-free transforms.
struct df32 { float hi,lo; };

__device__ __constant__ df32 D32_INV[18]={{1.f,0.f},{.5f,0.f},{.3333333432674408f,-9.9341077586245774e-9f},{.25f,0.f},{.20000000298023224f,-2.9802322831784522e-9f},{.1666666716337204f,-4.9670538793122887e-9f},{.1428571492433548f,-6.3862120036617398e-9f},{.125f,0.f},{.1111111119389534f,-8.278422947149977e-10f},{.10000000149011612f,-1.4901161415892261e-9f},{.09090909361839294f,-2.709302115988521e-9f},{.0833333358168602f,-2.4835269396561444e-9f},{.07692307978868484f,-2.8656079731348427e-9f},{.0714285746216774f,-3.19310600183087e-9f},{.06666667014360428f,-3.47693762670076e-9f},{.0625f,0.f},{.05882352963089943f,-2.191347242552766e-10f},{.0555555559694767f,-4.1392114735749885e-10f}};
__device__ __constant__ df32 D32_SIN_COEF[8]={{-.1666666716337204f,4.967053879312289e-9f},{-.05000000074505806f,7.450580707946131e-10f},{-.02380952425301075f,4.434869416147791e-10f},{-.013888888992369175f,1.0348028683937471e-10f},{-.00909090880304575f,-2.8786334427266524e-10f},{-.006410256493836641f,8.358023301235917e-11f},{-.004761904943734407f,1.8182964856006123e-10f},{-.0036764706019312143f,1.3695920265954786e-11f}};
__device__ __constant__ df32 D32_COS_COEF[9]={{-.5f,0.f},{-.0833333358168602f,2.4835269396561444e-9f},{-.03333333507180214f,1.73846881335038e-9f},{-.01785714365541935f,7.982765004577175e-10f},{-.011111111380159855f,2.690487554968257e-10f},{-.007575757801532745f,2.2577517633237676e-10f},{-.005494505632668734f,1.3816324473392427e-10f},{-.004166666883975267f,2.1730860166879751e-10f},{-.003267973894253373f,3.804422402109431e-11f}};

__device__ __forceinline__ df32 d32(float x){return {x,0.0f};}
__device__ __forceinline__ df32 d32_neg(df32 a){return {-a.hi,-a.lo};}
__device__ __forceinline__ df32 d32_two_sum(float a,float b){
  float s=__fadd_rn(a,b),bb=__fsub_rn(s,a);
  float e=__fadd_rn(__fsub_rn(a,__fsub_rn(s,bb)),__fsub_rn(b,bb));return {s,e};
}
__device__ __forceinline__ df32 d32_fast_two_sum(float a,float b){
  float s=__fadd_rn(a,b),e=__fsub_rn(b,__fsub_rn(s,a));return {s,e};
}
__device__ __forceinline__ df32 d32_renorm(float a,float b){
  return fabsf(a)>=fabsf(b)?d32_fast_two_sum(a,b):d32_fast_two_sum(b,a);
}
__device__ __forceinline__ df32 d32_add(df32 a,df32 b){
  df32 s=d32_two_sum(a.hi,b.hi),t=d32_two_sum(a.lo,b.lo);
  s.lo=__fadd_rn(s.lo,t.hi);s=d32_renorm(s.hi,s.lo);
  s.lo=__fadd_rn(s.lo,t.lo);return d32_renorm(s.hi,s.lo);
}
__device__ __forceinline__ df32 d32_sub(df32 a,df32 b){return d32_add(a,d32_neg(b));}
__device__ __forceinline__ df32 d32_mul(df32 a,df32 b){
  float p=__fmul_rn(a.hi,b.hi),e=__fmaf_rn(a.hi,b.hi,-p);
  e=__fmaf_rn(a.hi,b.lo,e);e=__fmaf_rn(a.lo,b.hi,e);e=__fmaf_rn(a.lo,b.lo,e);
  return d32_renorm(p,e);
}
__device__ __forceinline__ df32 d32_mul_f(df32 a,float b){
  float p=__fmul_rn(a.hi,b),e=__fmaf_rn(a.hi,b,-p);e=__fmaf_rn(a.lo,b,e);return d32_renorm(p,e);
}
__device__ __forceinline__ df32 d32_div(df32 a,df32 b){
  float q0=__fdiv_rn(a.hi,b.hi);df32 q=d32(q0),r=d32_sub(a,d32_mul(b,q));
  float q1=__fdiv_rn(r.hi,b.hi);q=d32_add(q,d32(q1));r=d32_sub(a,d32_mul(b,q));
  float q2=__fdiv_rn(r.hi,b.hi);return d32_add(q,d32(q2));
}
__device__ __forceinline__ df32 d32_abs(df32 a){return signbit(a.hi)?d32_neg(a):a;}
__device__ __forceinline__ float d32_float(df32 a){return __fadd_rn(a.hi,a.lo);}
__device__ __forceinline__ bool d32_finite(df32 a){return isfinite(a.hi)&&isfinite(a.lo);}
__device__ __forceinline__ df32 d32_scalbn(df32 a,int k){return {scalbnf(a.hi,k),scalbnf(a.lo,k)};}

__device__ __forceinline__ df32 d32_exp(df32 x){
  const df32 ln2={0.6931471824645996094f,-1.9046542121259336e-9f};
  int k=__float2int_rn(__fmul_rn(d32_float(x),1.4426950408889634f));
  df32 r=d32_sub(x,d32_mul_f(ln2,float(k))),term=d32(1.0f),sum=d32(1.0f);
  #pragma unroll
  for(int n=1;n<=18;n++){term=d32_mul(d32_mul(term,r),D32_INV[n-1]);sum=d32_add(sum,term);}
  return d32_scalbn(sum,k);
}
__device__ __forceinline__ df32 d32_log(df32 x){
  df32 y=d32(logf(x.hi));
  #pragma unroll
  for(int i=0;i<2;i++)y=d32_add(y,d32_sub(d32_mul(x,d32_exp(d32_neg(y))),d32(1.0f)));
  return y;
}
__device__ __forceinline__ df32 d32_sqrt(df32 x){
  df32 y=d32(sqrtf(x.hi));
  #pragma unroll
  for(int i=0;i<2;i++)y=d32_add(y,d32_mul_f(d32_sub(d32_div(x,y),y),0.5f));
  return y;
}
__device__ __forceinline__ void d32_sincos(df32 x,df32&s,df32&c){
  const df32 halfpi={1.5707963705062866211f,-4.371139000186241e-8f};
  int k=__float2int_rn(__fmul_rn(d32_float(x),0.63661977236758134f));df32 r=d32_sub(x,d32_mul_f(halfpi,float(k))),r2=d32_mul(r,r);
  df32 st=r,term=r;
  #pragma unroll
  for(int n=1;n<=8;n++){term=d32_mul(d32_mul(term,r2),D32_SIN_COEF[n-1]);st=d32_add(st,term);}
  df32 ct=d32(1.0f);term=d32(1.0f);
  #pragma unroll
  for(int n=1;n<=9;n++){term=d32_mul(d32_mul(term,r2),D32_COS_COEF[n-1]);ct=d32_add(ct,term);}
  switch(k&3){case 0:s=st;c=ct;break;case 1:s=ct;c=d32_neg(st);break;case 2:s=d32_neg(st);c=d32_neg(ct);break;default:s=d32_neg(ct);c=st;}
}
