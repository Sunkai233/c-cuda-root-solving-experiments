#define ROOT_BENCH_NO_MAIN
#include "benchmark.cu"
#include "../include/df32.cuh"

struct DParam {df32 a,b,c,d,e,f,lo,hi,x0;int domain,branch;};
struct DOutput {df32 root,residual,gradient,condition;uint32_t iterations;uint8_t status,pad[3];};
struct DRef {DParam p;double root,gradient;};

static df32 host_d32(double x){float h=float(x);return {h,float(x-double(h))};}
static std::vector<std::string> dsplit(const std::string&s){std::vector<std::string>v;std::string x;std::stringstream q(s);while(std::getline(q,x,','))v.push_back(x);return v;}
static std::vector<DRef> load_drefs(const std::string&path,int dom,const std::string&split){
  std::ifstream f(path);if(!f)throw std::runtime_error("cannot open "+path);std::string line;std::getline(f,line);std::vector<DRef>v;
  while(std::getline(f,line)){auto c=dsplit(line);if(c.size()<15||c[2]!=split)continue;Param p{};p.domain=dom;p.branch=(c[3].find("high")!=std::string::npos||c[3].find("vapor")!=std::string::npos)?1:0;for(int k=0;k<6;k++)((&p.a)[k])=strtod(c[4+k].c_str(),nullptr);double lo,hi,x0;bounds(p,lo,hi,x0);DRef r{};for(int k=0;k<6;k++)((&r.p.a)[k])=host_d32((&p.a)[k]);r.p.lo=host_d32(lo);r.p.hi=host_d32(hi);r.p.x0=host_d32(x0);r.p.domain=dom;r.p.branch=p.branch;r.root=strtod(c[10].c_str(),nullptr);r.gradient=strtod(c[11].c_str(),nullptr);v.push_back(r);}return v;
}

__device__ __forceinline__ bool d_le0(df32 x){return x.hi<0.0f||(x.hi==0.0f&&x.lo<=0.0f);}
__device__ __forceinline__ bool d_sign_change(df32 a,df32 b){return d_le0(a)!=d_le0(b)||a.hi==0.0f||b.hi==0.0f;}
__device__ __forceinline__ df32 d_clamp(df32 x,float lo,float hi){float v=d32_float(x);return v<lo?d32(lo):(v>hi?d32(hi):x);}
__device__ __forceinline__ void d_residual(const DParam&p,df32 x,df32&y,df32&dy){
  if(p.domain==BEM){df32 s,c;d32_sincos(x,s,c);df32 cl=d32_mul(p.d,d32_sub(x,p.c)),cn=d32_add(d32_mul(cl,c),d32_mul(p.e,s)),ct=d32_sub(d32_mul(cl,s),d32_mul(p.e,c));df32 cnp=d32_add(d32_sub(d32_mul(p.d,c),d32_mul(cl,s)),d32_mul(p.e,c)),ctp=d32_add(d32_add(d32_mul(p.d,s),d32_mul(cl,c)),d32_mul(p.e,s));df32 q=d32_add(cn,d32_div(ct,p.a)),qp=d32_add(cnp,d32_div(ctp,p.a)),sig4=d32_mul_f(p.b,.25f);y=d32_add(d32_sub(s,d32_div(c,p.a)),d32_mul(sig4,d32_div(q,s)));dy=d32_add(d32_add(c,d32_div(s,p.a)),d32_mul(sig4,d32_div(d32_sub(d32_mul(qp,s),d32_mul(q,c)),d32_mul(s,s))));}
  else if(p.domain==KEPLER){df32 s,c;d32_sincos(x,s,c);y=d32_sub(d32_sub(x,d32_mul(p.a,s)),p.b);dy=d32_sub(d32(1),d32_mul(p.a,c));}
  else if(p.domain==PV){df32 z=d32_div(d32_add(p.b,d32_mul(x,p.e)),p.d),ez=d32_exp(d_clamp(z,-80,80));y=d32_add(d32_add(d32_sub(x,p.a),d32_mul(p.c,d32_sub(ez,d32(1)))),d32_div(d32_add(p.b,d32_mul(x,p.e)),p.f));dy=d32_add(d32_add(d32(1),d32_div(d32_mul(d32_mul(p.c,ez),p.e),p.d)),d32_div(p.e,p.f));}
  else if(p.domain==CSTR){df32 den=d32_add(p.b,d32_mul(p.c,x)),expo=d32_div(d32_mul(d32_mul(p.b,p.c),x),den),lr=d32_add(d32_log(p.a),expo),sig;if(d32_float(lr)>=0){df32 t=d32_exp(d32_neg(lr));sig=d32_div(d32(1),d32_add(d32(1),t));}else{df32 t=d32_exp(lr);sig=d32_div(t,d32_add(d32(1),t));}df32 ep=d32_div(d32_mul(d32_mul(p.b,p.b),p.c),d32_mul(den,den));y=d32_sub(x,sig);dy=d32_sub(d32(1),d32_mul(d32_mul(sig,d32_sub(d32(1),sig)),ep));}
  else{df32 A=p.a,B=p.b,x2=d32_mul(x,x);y=d32_sub(d32_add(d32_sub(d32_mul(x2,x),d32_mul(d32_sub(d32(1),B),x2)),d32_mul(d32_sub(d32_sub(A,d32_mul_f(d32_mul(B,B),3)),d32_mul_f(B,2)),x)),d32_sub(d32_sub(d32_mul(A,B),d32_mul(B,B)),d32_mul(d32_mul(B,B),B)));dy=d32_add(d32_sub(d32_mul_f(x2,3),d32_mul_f(d32_mul(d32_sub(d32(1),B),x),2)),d32_sub(d32_sub(A,d32_mul_f(d32_mul(B,B),3)),d32_mul_f(B,2)));}
}

__device__ __forceinline__ bool d_bracket(const DParam&p,df32&a,df32&b){
  a=p.lo;b=p.hi;if(p.domain!=CSTR&&p.domain!=PR)return true;
  if(p.domain==PR){df32 one=d32(1),cc=d32_sub(d32_sub(p.a,d32_mul_f(d32_mul(p.b,p.b),3)),d32_mul_f(p.b,2)),u=d32_sub(one,p.b),disc=d32_sub(d32_mul_f(d32_mul(u,u),4),d32_mul_f(cc,12)),pts[4];int np=0;pts[np++]=a;if(d32_float(disc)>0){df32 sd=d32_sqrt(disc),x1=d32_mul_f(d32_sub(d32_mul_f(u,2),sd),1.0f/6),x2=d32_mul_f(d32_add(d32_mul_f(u,2),sd),1.0f/6);if(d32_float(x1)>d32_float(a)&&d32_float(x1)<d32_float(b))pts[np++]=x1;if(d32_float(x2)>d32_float(a)&&d32_float(x2)<d32_float(b))pts[np++]=x2;}pts[np++]=b;df32 fp,df,firsta=a,firstb=b,lasta=a,lastb=b;d_residual(p,pts[0],fp,df);int found=0;for(int k=1;k<np;k++){df32 fz;d_residual(p,pts[k],fz,df);if(d_sign_change(fp,fz)){if(!found){firsta=pts[k-1];firstb=pts[k];}lasta=pts[k-1];lastb=pts[k];found++;}fp=fz;}if(!found)return false;a=p.branch?lasta:firsta;b=p.branch?lastb:firstb;return true;}
  df32 prev=a,fp,df,firsta=a,firstb=b,lasta=a,lastb=b;d_residual(p,prev,fp,df);int found=0;for(int s=1;s<=256;s++){df32 z=d32_add(a,d32_mul_f(d32_sub(b,a),float(s)/256)),fz;d_residual(p,z,fz,df);if(d_sign_change(fp,fz)){if(!found){firsta=prev;firstb=z;}lasta=prev;lastb=z;found++;}prev=z;fp=fz;}if(!found)return false;a=p.branch?lasta:firsta;b=p.branch?lastb:firstb;return true;
}
__device__ __forceinline__ df32 d_solve(const DParam&p,uint32_t&used){
  df32 a,b;if(!d_bracket(p,a,b)){used=0;return {NAN,NAN};}df32 fa,fb,df;d_residual(p,a,fa,df);d_residual(p,b,fb,df);df32 x=p.x0;if(d32_float(x)<=d32_float(a)||d32_float(x)>=d32_float(b))x=d32_mul_f(d32_add(a,b),.5f);used=0;
  for(int k=0;k<52;k++){df32 f,fx;d_residual(p,x,f,fx);if(d_sign_change(fa,f)){b=x;fb=f;}else{a=x;fa=f;}df32 step=d32_div(f,fx);if(fabsf(d32_float(step))<1e-13f){used++;break;}df32 cand=d32_sub(x,step);if(!d32_finite(cand)||d32_float(cand)<=d32_float(a)||d32_float(cand)>=d32_float(b))cand=d32_mul_f(d32_add(a,b),.5f);x=cand;used++;}return x;
}
__device__ __forceinline__ DOutput d_finish(const DParam&p,df32 x,uint32_t it){
  df32 y,dy,fp;d_residual(p,x,y,dy);
  if(p.domain==BEM){df32 s,c;d32_sincos(x,s,c);df32 cl=d32_mul(p.d,d32_sub(x,p.c)),ct=d32_sub(d32_mul(cl,s),d32_mul(p.e,c));fp=d32_sub(d32_div(c,d32_mul(p.a,p.a)),d32_div(d32_mul_f(d32_mul(p.b,ct),.25f),d32_mul(d32_mul(s,p.a),p.a)));}
  else if(p.domain==KEPLER)fp=d32(-1);
  else if(p.domain==PV){df32 ez=d32_exp(d_clamp(d32_div(d32_add(p.b,d32_mul(x,p.e)),p.d),-80,80));fp=d32_add(d32_div(d32_mul(p.c,ez),p.d),d32_div(d32(1),p.f));}
  else if(p.domain==CSTR){df32 den=d32_add(p.b,d32_mul(p.c,x)),lr=d32_add(d32_log(p.a),d32_div(d32_mul(d32_mul(p.b,p.c),x),den)),sig;if(d32_float(lr)>=0){df32 t=d32_exp(d32_neg(lr));sig=d32_div(d32(1),d32_add(d32(1),t));}else{df32 t=d32_exp(lr);sig=d32_div(t,d32_add(d32(1),t));}fp=d32_neg(d32_div(d32_mul(sig,d32_sub(d32(1),sig)),p.a));}
  else fp=d32_sub(x,p.b);DOutput o{};o.root=x;o.residual=d32_abs(y);o.gradient=d32_neg(d32_div(fp,dy));o.condition=d32_div(d32(1),d32_abs(dy));o.iterations=it;o.status=(!d32_finite(x)||!d32_finite(o.gradient))?ROOT_NONFINITE:ROOT_OK;return o;
}
__global__ void kernel_df32(const DParam*p,DOutput*o,size_t n){size_t i=(size_t)blockIdx.x*blockDim.x+threadIdx.x;if(i>=n)return;uint32_t it;df32 x=d_solve(p[i],it);o[i]=d_finish(p[i],x,it);}

static double hd(df32 x){return double(x.hi)+double(x.lo);}static double rerr(double x,double y){return fabs(x-y)/fmax(fabs(y),1e-300);}
int main(int argc,char**argv){std::string refdir,outdir="results_raw/df32_validation",split="cal";for(int i=1;i<argc;i++){if(!strcmp(argv[i],"--references"))refdir=argv[++i];else if(!strcmp(argv[i],"--out"))outdir=argv[++i];else if(!strcmp(argv[i],"--split"))split=argv[++i];}if(refdir.empty())return 2;std::filesystem::create_directories(outdir);const char*names[]={"bem","kepler","pv","cstr","peng_robinson"};std::ofstream csv(outdir+"/df32_validation_"+split+".csv"),fail(outdir+"/df32_failures_"+split+".csv");csv<<"domain,n,root_median,root_p95,root_p99,root_max,gradient_median,gradient_p95,gradient_p99,gradient_max,residual_max,nonfinite,wrong_root,iterations_p99\n";fail<<"domain,index,reference_root,computed_root,root_error,gradient_error,status\n";
  for(int dom=0;dom<5;dom++){auto refs=load_drefs(refdir+"/"+names[dom]+".csv",dom,split);std::vector<DParam>p(refs.size());for(size_t i=0;i<p.size();i++)p[i]=refs[i].p;DParam*dp;DOutput*doo;cudaMalloc(&dp,p.size()*sizeof(DParam));cudaMalloc(&doo,p.size()*sizeof(DOutput));cudaMemcpy(dp,p.data(),p.size()*sizeof(DParam),cudaMemcpyHostToDevice);kernel_df32<<<int((p.size()+255)/256),256>>>(dp,doo,p.size());cudaDeviceSynchronize();std::vector<DOutput>o(p.size());cudaMemcpy(o.data(),doo,p.size()*sizeof(DOutput),cudaMemcpyDeviceToHost);std::vector<double>re,ge,it;size_t nf=0,wrong=0;double rm=0;for(size_t i=0;i<o.size();i++){double x=hd(o[i].root),g=hd(o[i].gradient),er=fabs(x-refs[i].root),eg=rerr(g,refs[i].gradient);if(!isfinite(x)||!isfinite(g)){nf++;fail<<names[dom]<<','<<i<<','<<refs[i].root<<','<<x<<",nan,nan,"<<int(o[i].status)<<'\n';continue;}re.push_back(er);ge.push_back(eg);it.push_back(o[i].iterations);rm=fmax(rm,hd(o[i].residual));if(er>1e-7){wrong++;fail<<names[dom]<<','<<i<<','<<std::setprecision(17)<<refs[i].root<<','<<x<<','<<er<<','<<eg<<','<<int(o[i].status)<<'\n';}}if(re.empty()){re.push_back(INFINITY);ge.push_back(INFINITY);it.push_back(INFINITY);}csv<<names[dom]<<','<<p.size()<<','<<std::setprecision(12)<<quantile(re,.5)<<','<<quantile(re,.95)<<','<<quantile(re,.99)<<','<<*max_element(re.begin(),re.end())<<','<<quantile(ge,.5)<<','<<quantile(ge,.95)<<','<<quantile(ge,.99)<<','<<*max_element(ge.begin(),ge.end())<<','<<rm<<','<<nf<<','<<wrong<<','<<quantile(it,.99)<<'\n';printf("%-14s root_max=%.3e grad_p99=%.3e wrong=%zu nf=%zu it99=%.0f\n",names[dom],*max_element(re.begin(),re.end()),quantile(ge,.99),wrong,nf,quantile(it,.99));cudaFree(dp);cudaFree(doo);}return 0;}
