#define ROOT_BENCH_NO_MAIN
#include "benchmark.cu"

struct RefCase { Param p; double root, gradient; };

static std::vector<std::string> split_csv_alg(const std::string&s){
  std::vector<std::string>v;std::string x;std::stringstream ss(s);
  while(std::getline(ss,x,','))v.push_back(x);return v;
}
static std::vector<RefCase> load_reference_alg(const std::string&path,int dom,const std::string&split){
  std::ifstream f(path);if(!f)throw std::runtime_error("cannot open "+path);
  std::string line;std::getline(f,line);std::vector<RefCase>v;
  while(std::getline(f,line)){
    auto c=split_csv_alg(line);if(c.size()<15||c[2]!=split)continue;RefCase r{};
    r.p.domain=dom;r.p.branch=(c[3].find("high")!=std::string::npos||c[3].find("vapor")!=std::string::npos)?1:0;
    for(int k=0;k<6;k++)((&r.p.a)[k])=std::strtod(c[4+k].c_str(),nullptr);
    r.root=std::strtod(c[10].c_str(),nullptr);r.gradient=std::strtod(c[11].c_str(),nullptr);v.push_back(r);
  }return v;
}

HD inline bool bracket_for(const Param&p,double&a,double&b){
  double lo,hi,x0;bounds(p,lo,hi,x0);
  if(p.domain!=CSTR&&p.domain!=PR){a=lo;b=hi;return true;}
  if(p.domain==PR){
    // Isolate cubic roots with derivative stationary points.  This is only a
    // bracket preprocessor; unlike solve_pr_cubic it does not evaluate a root.
    double cc=p.a-3*p.b*p.b-2*p.b,disc=4*(1-p.b)*(1-p.b)-12*cc,pts[4];int np=0;pts[np++]=lo;
    if(disc>0){double sd=sqrt(disc),x1=(2*(1-p.b)-sd)/6,x2=(2*(1-p.b)+sd)/6;if(x1>lo&&x1<hi)pts[np++]=x1;if(x2>lo&&x2<hi)pts[np++]=x2;}
    pts[np++]=hi;double first_a=lo,first_b=hi,last_a=lo,last_b=hi,df,fp;int found=0;residual(p,pts[0],fp,df);
    for(int k=1;k<np;k++){double fz;residual(p,pts[k],fz,df);if((fp<=0&&fz>=0)||(fp>=0&&fz<=0)){if(found==0){first_a=pts[k-1];first_b=pts[k];}last_a=pts[k-1];last_b=pts[k];found++;}fp=fz;}
    if(found==0)return false;a=p.branch?last_a:first_a;b=p.branch?last_b:first_b;return true;
  }
  double prev=lo,fp,df,a_first=lo,b_first=hi,a_last=lo,b_last=hi;residual(p,prev,fp,df);int found=0;
  for(int s=1;s<=256;s++){
    double z=lo+(hi-lo)*double(s)/256.0,fz;residual(p,z,fz,df);
    if((fp<=0&&fz>=0)||(fp>=0&&fz<=0)){if(found==0){a_first=prev;b_first=z;}a_last=prev;b_last=z;found++;}
    prev=z;fp=fz;
  }
  if(found==0)return false;a=p.branch?a_last:a_first;b=p.branch?b_last:b_first;return true;
}

HD inline double second_derivative(const Param&p,double x){
  if(p.domain==BEM){
    double lam=p.a,sig=p.b,theta=p.c,cla=p.d,cd=p.e,s=sin(x),c=cos(x),cl=cla*(x-theta);
    double cn=cl*c+cd*s,ct=cl*s-cd*c;
    double cnp=cla*c-cl*s+cd*c,ctp=cla*s+cl*c+cd*s;
    double cnpp=-2*cla*s-cl*c-cd*s,ctpp=2*cla*c-cl*s+cd*c;
    double q=cn+ct/lam,qp=cnp+ctp/lam,qpp=cnpp+ctpp/lam,n=qp*s-q*c;
    return -s+c/lam+(sig/4.0)*((qpp*s+q*s)/(s*s)-2.0*n*c/(s*s*s));
  }
  if(p.domain==KEPLER)return p.a*sin(x);
  if(p.domain==PV){double ez=exp(clampv((p.b+x*p.e)/p.d,-80.0,80.0)),q=p.e/p.d;return p.c*ez*q*q;}
  if(p.domain==PR)return 6*x-2*(1-p.b);
  double h=1e-5*fmax(1.0,fabs(x)),xp=fmin(1.0,x+h),xm=fmax(0.0,x-h),yp,dyp,ym,dym;
  residual(p,xp,yp,dyp);residual(p,xm,ym,dym);return (dyp-dym)/(xp-xm);
}

HD inline double solve_bisection_alg(const Param&p,uint32_t&used){
  double a,b;if(!bracket_for(p,a,b)){used=0;return NAN;}double fa,fb,df;residual(p,a,fa,df);residual(p,b,fb,df);used=0;
  for(int k=0;k<100;k++){double m=.5*(a+b),fm;residual(p,m,fm,df);used++;if(fabs(fm)<1e-14||fabs(b-a)<2e-13)return m;if((fa<=0&&fm>=0)||(fa>=0&&fm<=0)){b=m;fb=fm;}else{a=m;fa=fm;}}
  return .5*(a+b);
}
HD inline double solve_bracketed_secant_alg(const Param&p,uint32_t&used){
  double a,b;if(!bracket_for(p,a,b)){used=0;return NAN;}double fa,fb,df;residual(p,a,fa,df);residual(p,b,fb,df);used=0;
  for(int k=0;k<100;k++){double den=fb-fa,s=(fabs(den)>1e-300)?b-fb*(b-a)/den:.5*(a+b);if(!isfinite(s)||s<=a||s>=b)s=.5*(a+b);double fs;residual(p,s,fs,df);used++;if(fabs(fs)<1e-14||fabs(b-a)<2e-13)return s;if((fa<=0&&fs>=0)||(fa>=0&&fs<=0)){b=s;fb=fs;}else{a=s;fa=fs;}if(k%8==7){double m=.5*(a+b),fm;residual(p,m,fm,df);if((fa<=0&&fm>=0)||(fa>=0&&fm<=0)){b=m;fb=fm;}else{a=m;fa=fm;}}}
  return fabs(fa)<fabs(fb)?a:b;
}
HD inline double solve_newton_alg(const Param&p,uint32_t&used,bool halley){
  double a,b;if(!bracket_for(p,a,b)){used=0;return NAN;}double fa,fb,df,x=.5*(a+b);residual(p,a,fa,df);residual(p,b,fb,df);used=0;
  for(int k=0;k<100;k++){double y,dy;residual(p,x,y,dy);used++;if(fabs(y)<1e-14||fabs(b-a)<2e-13)return x;if((fa<=0&&y>=0)||(fa>=0&&y<=0)){b=x;fb=y;}else{a=x;fa=y;}double step=y/dy;if(halley){double d2=second_derivative(p,x),den=2*dy*dy-y*d2;if(isfinite(den)&&fabs(den)>1e-300)step=2*y*dy/den;}double s=x-step;if(!isfinite(s)||s<=a||s>=b)s=.5*(a+b);x=s;}
  return x;
}

HD inline double solve_brent_alg(const Param&p,uint32_t&used){
  double a,b;if(!bracket_for(p,a,b)){used=0;return NAN;}double fa,fb,df;residual(p,a,fa,df);residual(p,b,fb,df);double c=a,fc=fa;used=0;
  for(int k=0;k<100;k++){
    double best=fabs(fa)<fabs(fb)?a:b,fbest=fabs(fa)<fabs(fb)?fa:fb;if(fabs(fbest)<1e-14||fabs(b-a)<2e-13)return best;double s;
    if(fa!=fb&&fa!=fc&&fb!=fc)s=a*fb*fc/((fa-fb)*(fa-fc))+b*fa*fc/((fb-fa)*(fb-fc))+c*fa*fb/((fc-fa)*(fc-fb));
    else s=b-fb*(b-a)/(fb-fa);
    double lo=fmin(a,b),hi=fmax(a,b),guard=.05*(hi-lo);if(!isfinite(s)||s<=lo+guard||s>=hi-guard)s=.5*(a+b);
    double fs;residual(p,s,fs,df);c=best;fc=fbest;if((fa<=0&&fs>=0)||(fa>=0&&fs<=0)){b=s;fb=fs;}else{a=s;fa=fs;}used++;
  }return fabs(fa)<fabs(fb)?a:b;
}

HD inline double solve_chandrupatla_alg(const Param&p,uint32_t&used){
  double x1,x2;if(!bracket_for(p,x1,x2)){used=0;return NAN;}double f1,f2,df;residual(p,x1,f1,df);residual(p,x2,f2,df);
  double x3=x2,f3=f2,t=.5;used=0;
  for(int k=0;k<100;k++){
    double x=x1+t*(x2-x1),f;residual(p,x,f,df);used++;double oldx2=x2,oldf2=f2;x3=oldx2;f3=oldf2;
    if(copysign(1.0,f)==copysign(1.0,f1)){x3=x1;f3=f1;}else{x2=x1;f2=f1;}x1=x;f1=f;
    double xmin=fabs(f1)<fabs(f2)?x1:x2,fmin=fabs(f1)<fabs(f2)?f1:f2,dx=fabs(x2-x1),tol=4*2.2204460492503131e-16*fabs(xmin)+4*2.2250738585072014e-308;
    if(fabs(fmin)<1e-14||dx<tol)return xmin;t=.5;double denx=x3-x2,denf=f3-f2;
    if(fabs(denx)>1e-300&&fabs(denf)>1e-300){double xi=(x1-x2)/denx,phi=(f1-f2)/denf;
      if(xi>0&&xi<1&&(1-sqrt(1-xi))<phi&&phi<sqrt(xi)){double alpha=(x3-x1)/(x2-x1);
        t=f1/(f1-f2)*f3/(f3-f2)-alpha*f1/(f3-f1)*f2/(f2-f3);}}
    double tl=.5*tol/fmax(dx,1e-300);t=clampv(t,tl,1-tl);
  }return fabs(f1)<fabs(f2)?x1:x2;
}

HD inline double solve_kepler_mikkola(const Param&p,uint32_t&used){
  double e=p.a,M=p.b;if(e<1e-14){used=1;return M;}double alpha=(1-e)/(4*e+.5),beta=M/(8*e+1),z=cbrt(beta+sqrt(beta*beta+alpha*alpha*alpha));
  double s=fabs(z)>1e-300?z-alpha/z:0;s-=.078*s*s*s*s*s/(1+e);double E=M+e*s*(3-4*s*s);used=1;
  for(int k=0;k<3;k++){double f=E-e*sin(E)-M,fp=1-e*cos(E),fpp=e*sin(E),den=2*fp*fp-f*fpp;E-=fabs(den)>1e-300?2*f*fp/den:f/fp;used++;}return clampv(E,0.0,3.141592653589793);
}

HD inline double lambertw_from_log(double lz,uint32_t&used){double w=lz>1?lz-log(lz):exp(lz);w=fmax(w,1e-300);used=0;
  for(int k=0;k<12;k++){double f=w+log(w)-lz,d=1+1/w,step=f/d;w-=step;if(w<=0)w=.5*(w+step);used++;if(fabs(step)<2e-14*fmax(1.0,w))break;}return w;}
HD inline double solve_pv_lambert(const Param&p,uint32_t&used){double IL=p.a,V=p.b,I0=p.c,a=p.d,Rs=p.e,Rsh=p.f,den=Rs+Rsh;
  double lz=log(Rs*I0*Rsh/(a*den))+Rsh*(Rs*(IL+I0)+V)/(a*den);double w=lambertw_from_log(lz,used);return (Rsh*(IL+I0)-V)/den-a*w/Rs;}
HD inline double solve_pv_bishop(const Param&p,uint32_t&used){double lo=p.b,hi=p.b+p.e*p.a,fa,fb;
  double Ilo=p.a-p.c*(exp(clampv(lo/p.d,-80.0,80.0))-1)-lo/p.f;fa=lo-p.e*Ilo-p.b;
  double Ihi=p.a-p.c*(exp(clampv(hi/p.d,-80.0,80.0))-1)-hi/p.f;fb=hi-p.e*Ihi-p.b;used=0;
  for(int k=0;k<100;k++){double m=.5*(lo+hi),I=p.a-p.c*(exp(clampv(m/p.d,-80.0,80.0))-1)-m/p.f,fm=m-p.e*I-p.b;used++;if(fabs(fm)<1e-14||fabs(hi-lo)<2e-13)return I;if(copysign(1.0,fa)!=copysign(1.0,fm)){hi=m;fb=fm;}else{lo=m;fa=fm;}}(void)fb;double vd=.5*(lo+hi);return p.a-p.c*(exp(clampv(vd/p.d,-80.0,80.0))-1)-vd/p.f;}

__global__ void kernel_algorithm(const Param*in,Output*out,size_t n,int method){
  size_t i=(size_t)blockIdx.x*blockDim.x+threadIdx.x;if(i>=n)return;uint32_t it=0;double x;
  if(method==0)x=solve_brent_alg(in[i],it);else if(method==1)x=solve_bracketed_secant_alg(in[i],it);else if(method==2)x=solve_newton_alg(in[i],it,false);else if(method==3)x=solve_newton_alg(in[i],it,true);else if(method==4)x=solve_pr_cubic<double>(in[i],it);else if(method==5)x=solve_kepler_mikkola(in[i],it);else if(method==6)x=solve_pv_lambert(in[i],it);else if(method==7)x=solve_chandrupatla_alg(in[i],it);else x=solve_pv_bishop(in[i],it);
  out[i]=finish(in[i],x,it,3);
}

static double relerr_alg(double x,double y){return fabs(x-y)/fmax(fabs(y),1e-300);}
int main(int argc,char**argv){
  std::string refdir,split="cal",outdir="results_raw/algorithm_validation",only_domain;for(int i=1;i<argc;i++){if(!strcmp(argv[i],"--references"))refdir=argv[++i];else if(!strcmp(argv[i],"--split"))split=argv[++i];else if(!strcmp(argv[i],"--out"))outdir=argv[++i];else if(!strcmp(argv[i],"--domain"))only_domain=argv[++i];}
  if(refdir.empty())return 2;std::filesystem::create_directories(outdir);const char*domains[]={"bem","kepler","pv","cstr","peng_robinson"};const char*methods[]={"brent_dekker","bracketed_secant","safeguarded_newton","safeguarded_halley","analytic_cubic","mikkola_kepler","lambert_w","chandrupatla","bishop_transform"};
  std::ofstream csv(outdir+"/algorithm_validation_"+split+".csv"),fail(outdir+"/algorithm_failures_"+split+".csv");csv<<"domain,method,n,root_p99,root_max,gradient_p99,gradient_max,residual_max,nonfinite,wrong_root,iterations_median,iterations_p99\n";fail<<"domain,method,index,p0,p1,reference_root,computed_root,absolute_error,status\n";
  for(int dom=0;dom<5;dom++){if(!only_domain.empty()&&only_domain!=domains[dom])continue;auto refs=load_reference_alg(refdir+"/"+domains[dom]+".csv",dom,split);if(refs.empty()){std::fprintf(stderr,"no %s rows for split %s\n",domains[dom],split.c_str());return 3;}std::vector<Param>p(refs.size());for(size_t i=0;i<p.size();i++)p[i]=refs[i].p;Param*dp;Output*doo;cudaMalloc(&dp,p.size()*sizeof(Param));cudaMalloc(&doo,p.size()*sizeof(Output));cudaMemcpy(dp,p.data(),p.size()*sizeof(Param),cudaMemcpyHostToDevice);const int ids[5][7]={{0,1,2,3,-1,-1,-1},{0,1,2,3,5,-1,-1},{0,1,2,3,6,7,8},{0,1,2,3,-1,-1,-1},{0,1,2,3,4,-1,-1}};int count=dom==PV?7:(dom==KEPLER||dom==PR?5:4);
    for(int mi=0;mi<count;mi++){int method=ids[dom][mi];kernel_algorithm<<<int((p.size()+255)/256),256>>>(dp,doo,p.size(),method);cudaDeviceSynchronize();std::vector<Output>o(p.size());cudaMemcpy(o.data(),doo,p.size()*sizeof(Output),cudaMemcpyDeviceToHost);std::vector<double>re,ge,it;size_t nf=0,wrong=0;double resid=0;for(size_t i=0;i<o.size();i++){double er=fabs(o[i].root-refs[i].root);if(!isfinite(o[i].root)||!isfinite(o[i].gradient)){nf++;fail<<domains[dom]<<','<<methods[method]<<','<<i<<','<<std::setprecision(17)<<p[i].a<<','<<p[i].b<<','<<refs[i].root<<','<<o[i].root<<",nan,"<<int(o[i].status)<<'\n';continue;}double eg=relerr_alg(o[i].gradient,refs[i].gradient);re.push_back(er);ge.push_back(eg);it.push_back(o[i].iterations);if(er>1e-7){wrong++;fail<<domains[dom]<<','<<methods[method]<<','<<i<<','<<std::setprecision(17)<<p[i].a<<','<<p[i].b<<','<<refs[i].root<<','<<o[i].root<<','<<er<<','<<int(o[i].status)<<'\n';}resid=fmax(resid,o[i].residual);}if(re.empty()){re.push_back(INFINITY);ge.push_back(INFINITY);it.push_back(INFINITY);}csv<<domains[dom]<<','<<methods[method]<<','<<p.size()<<','<<std::setprecision(12)<<quantile(re,.99)<<','<<*std::max_element(re.begin(),re.end())<<','<<quantile(ge,.99)<<','<<*std::max_element(ge.begin(),ge.end())<<','<<resid<<','<<nf<<','<<wrong<<','<<quantile(it,.5)<<','<<quantile(it,.99)<<'\n';std::printf("%-14s %-20s wrong=%zu root_max=%.3e grad_p99=%.3e it_p99=%.0f\n",domains[dom],methods[method],wrong,*std::max_element(re.begin(),re.end()),quantile(ge,.99),quantile(it,.99));}
    cudaFree(dp);cudaFree(doo);
  }
  return 0;
}
