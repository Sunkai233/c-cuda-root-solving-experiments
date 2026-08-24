#ifndef BEM_REAL_SOLVER_H
#define BEM_REAL_SOLVER_H

#include <math.h>
#include "bem_real_tables.h"
#include "bem_polar_lut.h"

#ifndef BEM_HD
#define BEM_HD static inline
#endif

#define BEM_PI 3.141592653589793238462643383279502884
#define BEM_EPS2 1.4901161193847656e-7
#ifndef BEM_FAST_SCAN_CELLS
#define BEM_FAST_SCAN_CELLS 16
#endif

BEM_HD double bem_wrap_pi(double x) {
  x = fmod(x + BEM_PI, 2.0*BEM_PI);
  if (x < 0.0) x += 2.0*BEM_PI;
  return x - BEM_PI;
}

BEM_HD void bem_polar(unsigned af, double alpha_rad, double *cl, double *cd) {
  const unsigned off = bem_af_offset[af], n = bem_af_count[af];
  const double x = bem_wrap_pi(alpha_rad) * (180.0/BEM_PI);
  unsigned lo = 0, hi = n-1;
  if (x <= bem_alpha_deg[off]) { *cl=bem_cl[off]; *cd=bem_cd[off]; return; }
  if (x >= bem_alpha_deg[off+n-1]) { *cl=bem_cl[off+n-1]; *cd=bem_cd[off+n-1]; return; }
#ifdef BEM_DISABLE_O1_LUT
  while (hi-lo > 1) {
    const unsigned m = (lo+hi)>>1;
    if (bem_alpha_deg[off+m] <= x) lo=m; else hi=m;
  }
#else
  unsigned bin=(unsigned)fmin(720.0,fmax(0.0,floor((x+180.0)*2.0)));
  lo=(unsigned)bem_polar_lut[af*721u+bin]-off;hi=lo+1;
  while(lo>0&&bem_alpha_deg[off+lo]>x){--lo;--hi;}
  while(hi<n-1&&bem_alpha_deg[off+hi]<=x){++lo;++hi;}
#endif
  const double x0=bem_alpha_deg[off+lo], x1=bem_alpha_deg[off+hi];
  const double w=(x-x0)/(x1-x0);
  *cl = bem_cl[off+lo] + w*(bem_cl[off+hi]-bem_cl[off+lo]);
  *cd = bem_cd[off+lo] + w*(bem_cd[off+hi]-bem_cd[off+lo]);
}

BEM_HD double bem_residual(double phi, double vx, double vy, double theta,
                           unsigned node, int *valid) {
  if (fabs(vx)<1e-3 || fabs(vy)<1e-3 || fabs(phi)<1e-15) {
    *valid=1; return 0.0;
  }
  double cl, cd;
  bem_polar(bem_node_afid[node], phi-theta, &cl, &cd);
  (void)cd; /* AIDrag=False, TIDrag=False in the frozen case. */
  const double s=sin(phi), c=cos(phi), as=fabs(s);
  double ft=1.0, fh=1.0;
  if (as>0.0) {
    ft=(2.0/BEM_PI)*acos(fmin(1.0,exp(-bem_node_tip_const[node]/as)));
    fh=(2.0/BEM_PI)*acos(fmin(1.0,exp(-bem_node_hub_const[node]/as)));
  }
  const double F=fmax(ft*fh,1e-4);
  const double sigma=3.0*bem_node_chord[node]/(2.0*BEM_PI*bem_node_r[node]);
  const double cn=cl*c, ct=cl*s;
  const double k=sigma*cn/(4.0*F*s*s);
  double kp;
  if (fabs(c)<1e-15) kp=copysign(1e6,ct*s)*copysign(1.0,vx);
  else {
    kp=sigma*ct/(4.0*F*s*c);
    if (vx<0.0) kp=-kp;
  }
  const int momentum=((phi>0.0 && vx>=0.0)||(phi<0.0 && vx<0.0));
  double a;
  *valid=1;
  if (momentum) {
    if (k<=2.0/3.0) {
      a=k/(1.0+k);
      if (k < -1.0) *valid=0;
    } else {
      const double t=2.0*F*k;
      const double g1=t-(10.0/9.0-F), g2=t-(4.0/3.0-F)*F;
      const double g3=t-(25.0/9.0-2.0*F);
      a=(fabs(g3)<1e-6) ? 1.0-0.5/sqrt(g2) : (g1-sqrt(fabs(g2)))/g3;
    }
    return s/(1.0-a) - c/(vy/vx)*(1.0-kp);
  }
  a=k/(k-1.0);
  if (k<=1.0) *valid=0;
  return s*(1.0-k) - c/(vy/vx)*(1.0-kp);
}

BEM_HD int bem_bisect_region(double vx,double vy,double theta,unsigned node,
                             double a,double b,double *root) {
  int va=0,vb=0,vm=0;
  double fa=bem_residual(a,vx,vy,theta,node,&va);
  double fb=bem_residual(b,vx,vy,theta,node,&vb);
  if (!isfinite(fa)||!isfinite(fb)||copysign(1.0,fa)==copysign(1.0,fb)) return 0;
  for (int it=0;it<80;++it) {
    const double m=0.5*(a+b);
    const double fm=bem_residual(m,vx,vy,theta,node,&vm);
    if (!isfinite(fm)) return 0;
    if (fabs(fm)<5e-10 || fabs(b-a)<2e-13) { *root=m; return vm; }
    if (copysign(1.0,fa)!=copysign(1.0,fm)) { b=m; fb=fm; }
    else { a=m; fa=fm; }
  }
  *root=0.5*(a+b);
  (void)bem_residual(*root,vx,vy,theta,node,&vm);
  return vm;
}

BEM_HD int bem_bisect_region_fixed44(double vx,double vy,double theta,unsigned node,
                                      double a,double b,double *root) {
  int va=0,vb=0,vm=0;
  double fa=bem_residual(a,vx,vy,theta,node,&va);
  double fb=bem_residual(b,vx,vy,theta,node,&vb);
  if(!isfinite(fa)||!isfinite(fb)||copysign(1.0,fa)==copysign(1.0,fb))return 0;
  /* 44 steps reduce a pi/2 bracket below 9e-14 rad.  There is no
     convergence-dependent exit, so active lanes execute the same count. */
  for(int it=0;it<44;++it){
    const double m=0.5*(a+b),fm=bem_residual(m,vx,vy,theta,node,&vm);
    if(!isfinite(fm))return 0;
    if(copysign(1.0,fa)!=copysign(1.0,fm))b=m;else{a=m;fa=fm;}
  }
  *root=0.5*(a+b);(void)bem_residual(*root,vx,vy,theta,node,&vm);return vm;
}

BEM_HD int bem_brent_region(double vx,double vy,double theta,unsigned node,
                            double aa,double bb,double *root) {
  int va=0,vb=0,vn=0;
  double a=aa,b=bb,c=aa,fa=bem_residual(a,vx,vy,theta,node,&va);
  double fb=bem_residual(b,vx,vy,theta,node,&vb),fc=fa,d=b-a,e=d;
  if(!isfinite(fa)||!isfinite(fb)||copysign(1.0,fa)==copysign(1.0,fb))return 0;
  for(int it=0;it<80;++it){
    if((fb>0.0&&fc>0.0)||(fb<=0.0&&fc<=0.0)){c=a;fc=fa;e=d=b-a;}
    /* Deliberately sequential: c/fc must receive the new a/fa (old b/fb),
       matching the classic zeroin/Brent rotation. */
    if(fabs(fc)<fabs(fb)){a=b;fa=fb;b=c;fb=fc;c=a;fc=fa;}
    const double tol=2.0*2.2204460492503131e-16*fabs(b)+1e-13;
    const double m=0.5*(c-b);
    if(fabs(m)<=tol||fabs(fb)<5e-10){*root=b;(void)bem_residual(b,vx,vy,theta,node,&vn);return vn;}
    if(fabs(e)>=tol&&fabs(fa)>fabs(fb)){
      double p,q,s=fb/fa;
      if(a!=c){q=fa/fc;double r=fb/fc;p=s*(2.0*m*q*(q-r)-(b-a)*(r-1.0));q=(q-1.0)*(r-1.0)*(s-1.0);}
      else{p=2.0*m*s;q=1.0-s;}
      if(p<=0.0)p=-p;else q=-q;
      s=e;e=d;
      if(2.0*p>=3.0*m*q-fabs(tol*q)||p>=fabs(0.5*s*q))e=d=m;else d=p/q;
    }else e=d=m;
    a=b;fa=fb;b+=(fabs(d)<=tol?copysign(tol,m):d);
    fb=bem_residual(b,vx,vy,theta,node,&vn);if(!isfinite(fb))return 0;
  }
  *root=b;(void)bem_residual(b,vx,vy,theta,node,&vn);return vn;
}

BEM_HD int bem_secant_region(double vx,double vy,double theta,unsigned node,
                             double a,double b,double *root) {
  int va=0,vb=0,vn=0,side=0;double fa=bem_residual(a,vx,vy,theta,node,&va),fb=bem_residual(b,vx,vy,theta,node,&vb);
  if(!isfinite(fa)||!isfinite(fb)||copysign(1.0,fa)==copysign(1.0,fb))return 0;
  for(int it=0;it<80;++it){
    double den=fb-fa;
    double x=(fabs(den)>1e-300)?(fa*b-fb*a)/den:0.5*(a+b);
    const double l=fmin(a,b),u=fmax(a,b);
    if(!isfinite(x)||x<=l+1e-14||x>=u-1e-14)x=0.5*(a+b);
    double fx=bem_residual(x,vx,vy,theta,node,&vn);if(!isfinite(fx))return 0;
    if(fabs(fx)<5e-10||fabs(b-a)<2e-13){*root=x;return vn;}
    if(copysign(1.0,fb)==copysign(1.0,fx)){
      b=x;fb=fx;if(side==-1)fa*=0.5;side=-1;
    }else{
      a=x;fa=fx;if(side==1)fb*=0.5;side=1;
    }
  }
  *root=(fabs(fa)<fabs(fb)?a:b);(void)bem_residual(*root,vx,vy,theta,node,&vn);return vn;
}

BEM_HD int bem_solve(double vx,double vy,double theta,double hint,unsigned node,double *root) {
  if (fabs(vx)<1e-3) { *root=0.0; return 1; }
  if (fabs(vy)<1e-3) { *root=(vx>0.0?0.5*BEM_PI:-0.5*BEM_PI); return 1; }
  double lo[3],hi[3];
  if (vx>0.0) {
    lo[0]=BEM_EPS2; hi[0]=0.5*BEM_PI-BEM_EPS2;
    if (hint<0.25*BEM_PI && hint>-0.25*BEM_PI) {
      lo[1]=-0.25*BEM_PI; hi[1]=-BEM_EPS2; lo[2]=0.5*BEM_PI+BEM_EPS2; hi[2]=BEM_PI-BEM_EPS2;
    } else {
      lo[2]=-0.25*BEM_PI; hi[2]=-BEM_EPS2; lo[1]=0.5*BEM_PI+BEM_EPS2; hi[1]=BEM_PI-BEM_EPS2;
    }
  } else {
    lo[0]=-BEM_EPS2; hi[0]=-0.5*BEM_PI+BEM_EPS2;
    if (hint>-0.25*BEM_PI && hint<0.25*BEM_PI) {
      lo[1]=0.25*BEM_PI; hi[1]=BEM_EPS2; lo[2]=-0.5*BEM_PI-BEM_EPS2; hi[2]=-BEM_PI+BEM_EPS2;
    } else {
      lo[2]=0.25*BEM_PI; hi[2]=BEM_EPS2; lo[1]=-0.5*BEM_PI-BEM_EPS2; hi[1]=-BEM_PI+BEM_EPS2;
    }
  }
  for (int q=0;q<3;++q) if (bem_bisect_region(vx,vy,theta,node,lo[q],hi[q],root)) return 1;
  *root=atan2(vx,vy);
  return 0;
}

BEM_HD int bem_algorithm_region(double vx,double vy,double theta,unsigned node,
                                double a,double b,int algorithm,double *root){
  int ok=algorithm==0?bem_bisect_region(vx,vy,theta,node,a,b,root):
    (algorithm==1?bem_brent_region(vx,vy,theta,node,a,b,root):
    (algorithm==2?bem_secant_region(vx,vy,theta,node,a,b,root):
                  bem_bisect_region_fixed44(vx,vy,theta,node,a,b,root)));
  if(!ok)return 0;
  int valid=0;double residual=bem_residual(*root,vx,vy,theta,node,&valid);
  /* Reject sign changes caused by a piecewise-polar discontinuity. */
  return valid&&isfinite(residual)&&fabs(residual)<5e-8;
}

BEM_HD int bem_scan_region_nearest_hint(double vx,double vy,double theta,double hint,
                                        unsigned node,double lo,double hi,int algorithm,
                                        int max_cells,double *root){
  enum{BEM_SCAN_CELLS=512};
  double t=(hint-lo)/(hi-lo);int center=(int)floor(t*BEM_SCAN_CELLS);
  if(center<0)center=0;if(center>=BEM_SCAN_CELLS)center=BEM_SCAN_CELLS-1;
  int left=center,right=center+1,have=0;double best=0.0,best_distance=INFINITY;
  int scanned=0;while((left>=0||right<BEM_SCAN_CELLS)&&scanned<max_cells){
    double dl=INFINITY,dr=INFINITY;
    if(left>=0){double edge=lo+(hi-lo)*(double)(left+1)/(double)BEM_SCAN_CELLS;dl=fabs(bem_wrap_pi(edge-hint));}
    if(right<BEM_SCAN_CELLS){double edge=lo+(hi-lo)*(double)right/(double)BEM_SCAN_CELLS;dr=fabs(bem_wrap_pi(edge-hint));}
    if(have&&best_distance<=fmin(dl,dr)){*root=best;return 1;}
    int cell;
    if(dl<=dr){cell=left--;}
    else{cell=right++;}
    ++scanned;
    double a=lo+(hi-lo)*(double)cell/(double)BEM_SCAN_CELLS;
    double b=lo+(hi-lo)*(double)(cell+1)/(double)BEM_SCAN_CELLS,candidate;
    if(bem_algorithm_region(vx,vy,theta,node,a,b,algorithm,&candidate)){
      double distance=fabs(bem_wrap_pi(candidate-hint));
      if(distance<best_distance){best=candidate;best_distance=distance;have=1;}
    }
  }
  if(have&&left<0&&right>=BEM_SCAN_CELLS){*root=best;return 1;}return 0;
}

BEM_HD int bem_hint_newton_region(double vx,double vy,double theta,double hint,unsigned node,
                                  double lo,double hi,double *root){
  const double lower=fmin(lo,hi),upper=fmax(lo,hi),guard=1e-10;
  double x=fmin(upper-guard,fmax(lower+guard,hint));
  for(int it=0;it<8;++it){
    int valid=0;double fx=bem_residual(x,vx,vy,theta,node,&valid);
    if(valid&&isfinite(fx)&&fabs(fx)<5e-8){*root=x;return 1;}
    double h=1e-6,fm=bem_residual(x-h,vx,vy,theta,node,&valid),fp=bem_residual(x+h,vx,vy,theta,node,&valid);
    double derivative=(fp-fm)/(2.0*h);if(!isfinite(fx)||!isfinite(derivative)||fabs(derivative)<1e-10)break;
    double step=fx/derivative;if(fabs(step)>0.05)step=copysign(0.05,step);
    double xn=x-step;if(!(xn>lower&&xn<upper))xn=0.5*(x+(step>0.0?lower:upper));x=xn;
  }
  int valid=0;double residual=bem_residual(x,vx,vy,theta,node,&valid);
  if(valid&&isfinite(residual)&&fabs(residual)<5e-8){*root=x;return 1;}return 0;
}

BEM_HD int bem_solve_hint_only(double vx,double vy,double theta,double hint,unsigned node,double *root){
  if(fabs(vx)<1e-3){*root=0.0;return 2;}if(fabs(vy)<1e-3){*root=(vx>0?0.5*BEM_PI:-0.5*BEM_PI);return 2;}
  double lo[3],hi[3];
  if(vx>0){lo[0]=BEM_EPS2;hi[0]=0.5*BEM_PI-BEM_EPS2;if(hint<0.25*BEM_PI&&hint>-0.25*BEM_PI){lo[1]=-0.25*BEM_PI;hi[1]=-BEM_EPS2;lo[2]=0.5*BEM_PI+BEM_EPS2;hi[2]=BEM_PI-BEM_EPS2;}else{lo[2]=-0.25*BEM_PI;hi[2]=-BEM_EPS2;lo[1]=0.5*BEM_PI+BEM_EPS2;hi[1]=BEM_PI-BEM_EPS2;}}
  else{lo[0]=-BEM_EPS2;hi[0]=-0.5*BEM_PI+BEM_EPS2;if(hint>-0.25*BEM_PI&&hint<0.25*BEM_PI){lo[1]=0.25*BEM_PI;hi[1]=BEM_EPS2;lo[2]=-0.5*BEM_PI-BEM_EPS2;hi[2]=-BEM_PI+BEM_EPS2;}else{lo[2]=0.25*BEM_PI;hi[2]=BEM_EPS2;lo[1]=-0.5*BEM_PI-BEM_EPS2;hi[1]=-BEM_PI+BEM_EPS2;}}
  /* A limited outward scan can certify the nearest root without guessing from
     residual alone.  If it cannot certify, the sample enters the compacted
     robust queue; later regions cannot be tried before region zero is exhausted. */
  if(bem_scan_region_nearest_hint(vx,vy,theta,hint,node,lo[0],hi[0],1,BEM_FAST_SCAN_CELLS,root))return 2;
  return 0;
}

BEM_HD int bem_solve_robust_nearest(double vx,double vy,double theta,double hint,unsigned node,int algorithm,double *root){
  if(fabs(vx)<1e-3){*root=0.0;return 1;}if(fabs(vy)<1e-3){*root=(vx>0?0.5*BEM_PI:-0.5*BEM_PI);return 1;}
  double lo[3],hi[3];
  if(vx>0){lo[0]=BEM_EPS2;hi[0]=0.5*BEM_PI-BEM_EPS2;if(hint<0.25*BEM_PI&&hint>-0.25*BEM_PI){lo[1]=-0.25*BEM_PI;hi[1]=-BEM_EPS2;lo[2]=0.5*BEM_PI+BEM_EPS2;hi[2]=BEM_PI-BEM_EPS2;}else{lo[2]=-0.25*BEM_PI;hi[2]=-BEM_EPS2;lo[1]=0.5*BEM_PI+BEM_EPS2;hi[1]=BEM_PI-BEM_EPS2;}}
  else{lo[0]=-BEM_EPS2;hi[0]=-0.5*BEM_PI+BEM_EPS2;if(hint>-0.25*BEM_PI&&hint<0.25*BEM_PI){lo[1]=0.25*BEM_PI;hi[1]=BEM_EPS2;lo[2]=-0.5*BEM_PI-BEM_EPS2;hi[2]=-BEM_PI+BEM_EPS2;}else{lo[2]=0.25*BEM_PI;hi[2]=BEM_EPS2;lo[1]=-0.5*BEM_PI-BEM_EPS2;hi[1]=-BEM_PI+BEM_EPS2;}}
  for(int q=0;q<3;++q)if(bem_scan_region_nearest_hint(vx,vy,theta,hint,node,lo[q],hi[q],algorithm,512,root))return 1;
  *root=atan2(vx,vy);return 0;
}

BEM_HD int bem_solve_algorithm(double vx,double vy,double theta,double hint,unsigned node,int algorithm,double *root){
  if(algorithm==4){int fast=bem_solve_hint_only(vx,vy,theta,hint,node,root);if(fast)return fast;return bem_solve_robust_nearest(vx,vy,theta,hint,node,1,root);}
  return bem_solve_robust_nearest(vx,vy,theta,hint,node,algorithm,root);
}
#endif
