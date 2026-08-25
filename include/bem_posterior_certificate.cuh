#pragma once

/*
 * Scalar a-posteriori certificate used by E12--E16.
 *
 * The Kantorovich radius is a theorem only if L bounds |F''| on the complete
 * candidate ball.  Here L is a conservative sampled majorant (five points,
 * inflated by 8); therefore the implementation is deliberately called a
 * sampled certificate.  E12 measures false acceptance against independent
 * 80-digit roots.  A separate same-cell bracket check supplies an existence
 * witness and the polar/physical distances supply the branch witness.
 */

#include <float.h>
#include <math.h>

typedef struct {
  double residual;
  double derivative;
  double beta;
  double lipschitz;
  double h;
  double rho;
  double branch_distance;
  double gradient_error_bound;
  unsigned char finite;
  unsigned char residual_pass;
  unsigned char condition_pass;
  unsigned char posterior_pass;
  unsigned char branch_pass;
  unsigned char gradient_pass;
  unsigned char bracket_pass;
} BemCertificate;

BEM_HD double bem_cert_polar_knot_distance(double phi,double theta,unsigned node){
  const double alpha=bem_wrap_pi(phi-theta)*(180.0/BEM_PI);
  const unsigned af=bem_node_afid[node],off=bem_af_offset[af],n=bem_af_count[af];
  unsigned lo=0,hi=n-1;
  if(alpha<=bem_alpha_deg[off])return fabs(alpha-bem_alpha_deg[off])*(BEM_PI/180.0);
  if(alpha>=bem_alpha_deg[off+n-1])return fabs(alpha-bem_alpha_deg[off+n-1])*(BEM_PI/180.0);
  while(hi-lo>1){unsigned m=(lo+hi)>>1;if(bem_alpha_deg[off+m]<=alpha)lo=m;else hi=m;}
  return fmin(fabs(alpha-bem_alpha_deg[off+lo]),fabs(alpha-bem_alpha_deg[off+hi]))*(BEM_PI/180.0);
}

BEM_HD double bem_cert_physical_distance(double x){
  const double cuts[5]={-BEM_PI,-0.5*BEM_PI,0.0,0.5*BEM_PI,BEM_PI};
  double d=INFINITY;for(int k=0;k<5;++k)d=fmin(d,fabs(x-cuts[k]));return d;
}

BEM_HD double bem_cert_eval(double x,double vx,double vy,double theta,unsigned node,int *valid){
  return bem_residual(x,vx,vy,theta,node,valid);
}

BEM_HD double bem_cert_gradient_vx(double x,double vx,double vy,double theta,unsigned node,int *ok){
  const double hx=fmax(2e-7,32.0*DBL_EPSILON*fmax(1.0,fabs(x)));
  const double hv=fmax(2e-6,32.0*DBL_EPSILON*fmax(1.0,fabs(vx)));
  int a=0,b=0,c=0,d=0;
  const double fxp=bem_cert_eval(x+hx,vx,vy,theta,node,&a);
  const double fxm=bem_cert_eval(x-hx,vx,vy,theta,node,&b);
  const double fvp=bem_cert_eval(x,vx+hv,vy,theta,node,&c);
  const double fvm=bem_cert_eval(x,vx-hv,vy,theta,node,&d);
  const double dx=(fxp-fxm)/(2.0*hx),dv=(fvp-fvm)/(2.0*hv);
  *ok=a&&b&&c&&d&&isfinite(dx)&&isfinite(dv)&&fabs(dx)>1e-14;
  return *ok?-dv/dx:NAN;
}

BEM_HD BemCertificate bem_build_certificate(double x,double vx,double vy,double theta,unsigned node,
                                              double tau_x,double tau_g){
  BemCertificate c={0};
  const double dk=bem_cert_polar_knot_distance(x,theta,node);
  c.branch_distance=fmin(dk,bem_cert_physical_distance(x));
  double step=fmin(2e-5,fmax(2e-7,0.125*c.branch_distance));
  if(!(step>0.0)||!isfinite(step))step=2e-7;
  int v0=0,vm1=0,vp1=0,vm2=0,vp2=0;
  const double f0=bem_cert_eval(x,vx,vy,theta,node,&v0);
  const double fm1=bem_cert_eval(x-step,vx,vy,theta,node,&vm1);
  const double fp1=bem_cert_eval(x+step,vx,vy,theta,node,&vp1);
  const double fm2=bem_cert_eval(x-2.0*step,vx,vy,theta,node,&vm2);
  const double fp2=bem_cert_eval(x+2.0*step,vx,vy,theta,node,&vp2);
  c.finite=(unsigned char)(v0&&vm1&&vp1&&vm2&&vp2&&isfinite(f0)&&isfinite(fm1)&&isfinite(fp1)&&isfinite(fm2)&&isfinite(fp2));
  if(!c.finite){c.rho=INFINITY;c.gradient_error_bound=INFINITY;return c;}
  const double eta_f=128.0*DBL_EPSILON*(1.0+fabs(f0)+fabs(fm2)+fabs(fp2));
  const double d1=(fp1-fm1)/(2.0*step);
  const double eta_d=4.0*eta_f/step;
  const double dlow=fabs(d1)-eta_d;
  const double s1=fabs(fp1-2.0*f0+fm1)/(step*step);
  const double s2=fabs(fp2-2.0*f0+fm2)/(4.0*step*step);
  c.residual=fabs(f0)+eta_f;c.derivative=d1;
  c.residual_pass=(unsigned char)(c.residual<=5e-8);
  if(!(dlow>0.0)){c.rho=INFINITY;c.gradient_error_bound=INFINITY;return c;}
  c.beta=c.residual/dlow;
  c.lipschitz=8.0*fmax(s1,s2)+64.0*DBL_EPSILON/(step*step);
  c.h=c.beta*c.lipschitz/dlow;
  c.condition_pass=(unsigned char)(c.beta<=tau_x);
  if(c.h<=0.5){c.rho=2.0*c.beta/(1.0+sqrt(fmax(0.0,1.0-2.0*c.h)));}
  else c.rho=INFINITY;
  c.posterior_pass=(unsigned char)(isfinite(c.rho)&&c.rho<=tau_x);
  c.branch_pass=(unsigned char)(c.posterior_pass&&c.rho<c.branch_distance);
  if(c.branch_pass){
    int vl=0,vr=0;const double fl=bem_cert_eval(x-c.rho,vx,vy,theta,node,&vl),fr=bem_cert_eval(x+c.rho,vx,vy,theta,node,&vr);
    c.bracket_pass=(unsigned char)(vl&&vr&&isfinite(fl)&&isfinite(fr)&&copysign(1.0,fl)!=copysign(1.0,fr));
  }
  c.gradient_error_bound=0.0;c.gradient_pass=1;
  if(tau_g>0.0&&c.branch_pass){
    int g0ok=0,glok=0,grok=0;const double g0=bem_cert_gradient_vx(x,vx,vy,theta,node,&g0ok);
    const double gl=bem_cert_gradient_vx(x-c.rho,vx,vy,theta,node,&glok);
    const double gr=bem_cert_gradient_vx(x+c.rho,vx,vy,theta,node,&grok);
    c.gradient_error_bound=(g0ok&&glok&&grok)?fmax(fabs(gl-g0),fabs(gr-g0))/fmax(fabs(g0),1e-30):INFINITY;
    c.gradient_pass=(unsigned char)(isfinite(c.gradient_error_bound)&&c.gradient_error_bound<=tau_g);
  }
  return c;
}
