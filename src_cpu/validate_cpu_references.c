#define main benchmark_cpu_program_main
#include "benchmark_cpu.c"
#undef main

typedef struct { Param param; double root, gradient; char id[64], branch_name[64]; } Ref;

#ifdef VALIDATE_FAST_SOLVER
__attribute__((noinline, optimize("fast-math")))
#else
__attribute__((noinline))
#endif
static Output candidate_solve(const Param *param) { return solve_one(param); }

static int domain_index(const char *name) {
  static const char *names[] = {"bem", "kepler", "pv", "cstr", "peng_robinson"};
  for (int i = 0; i < 5; ++i) if (strcmp(name, names[i]) == 0) return i;
  return -1;
}

static int load_refs(const char *path, const char *split, int domain, Ref **out) {
  FILE *fp = fopen(path, "r");
  if (!fp) { perror(path); return -1; }
  char *line = NULL; size_t cap = 0; ssize_t len; int n = 0, alloc = 0;
  (void)getline(&line, &cap, fp);
  while ((len = getline(&line, &cap, fp)) > 0) {
    (void)len;
    char *fields[15] = {0}, *save = NULL, *token = strtok_r(line, ",\r\n", &save);
    int nf = 0;
    while (token && nf < 15) { fields[nf++] = token; token = strtok_r(NULL, ",\r\n", &save); }
    if (nf < 15 || strcmp(fields[2], split) != 0) continue;
    if (n == alloc) {
      alloc = alloc ? alloc * 2 : 1024;
      Ref *grown = realloc(*out, (size_t)alloc * sizeof(**out));
      if (!grown) { free(line); fclose(fp); return -1; }
      *out = grown;
    }
    Ref *r = *out + n++; memset(r, 0, sizeof(*r)); r->param.domain = domain;
    r->param.branch = strstr(fields[3], "high") || strstr(fields[3], "vapor") ? 1 : 0;
    for (int k = 0; k < 6; ++k) (&r->param.a)[k] = strtod(fields[4 + k], NULL);
    r->root = strtod(fields[10], NULL); r->gradient = strtod(fields[11], NULL);
    snprintf(r->id, sizeof(r->id), "%s", fields[1]);
    snprintf(r->branch_name, sizeof(r->branch_name), "%s", fields[3]);
  }
  free(line); fclose(fp); return n;
}

int main(int argc, char **argv) {
  if (argc != 4) { fprintf(stderr, "usage: references_dir split output_dir\n"); return 2; }
  const char *refdir = argv[1], *split = argv[2], *outdir = argv[3];
  char command[4096]; snprintf(command, sizeof(command), "mkdir -p -- '%s'", outdir);
  if (system(command) != 0) return 3;
  static const char *names[] = {"bem", "kepler", "pv", "cstr", "peng_robinson"};
  char summary_path[4096], raw_path[4096];
  snprintf(summary_path, sizeof(summary_path), "%s/validation_%s.csv", outdir, split);
  snprintf(raw_path, sizeof(raw_path), "%s/validation_%s_raw.csv", outdir, split);
  FILE *summary = fopen(summary_path, "w"), *raw = fopen(raw_path, "w");
  if (!summary || !raw) return 3;
  fprintf(summary, "domain,split,n,root_max,gradient_max,residual_max,root_gt_1e-7,gradient_over_limit,nonfinite\n");
  fprintf(raw, "domain,sample_id,split,branch,reference_root,computed_root,root_abs_error,reference_gradient,computed_gradient,gradient_relative_error,residual_abs,status\n");
  size_t total_fail = 0;
  for (int domain = 0; domain < 5; ++domain) {
    char path[4096]; snprintf(path, sizeof(path), "%s/%s.csv", refdir, names[domain]);
    Ref *refs = NULL; int n = load_refs(path, split, domain, &refs);
    if (n <= 0 || domain_index(names[domain]) != domain) return 3;
    double root_max = 0, grad_max = 0, residual_max = 0;
    size_t bad_root = 0, bad_grad = 0, nonfinite = 0;
    const double grad_limit = domain == PR ? 1e-4 : 2e-6;
    for (int i = 0; i < n; ++i) {
      Output out = candidate_solve(&refs[i].param);
      double re = fabs(out.root - refs[i].root);
      double ge = fabs(out.gradient - refs[i].gradient) / fmax(fabs(refs[i].gradient), 1e-300);
      int nf = !isfinite(out.root) || !isfinite(out.gradient) || !isfinite(out.residual);
      if (nf) { re = INFINITY; ge = INFINITY; ++nonfinite; }
      if (re > root_max) root_max = re; if (ge > grad_max) grad_max = ge;
      if (out.residual > residual_max) residual_max = out.residual;
      bad_root += re > 1e-7; bad_grad += ge > grad_limit;
      fprintf(raw, "%s,%s,%s,%s,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%u\n",
              names[domain], refs[i].id, split, refs[i].branch_name, refs[i].root,
              out.root, re, refs[i].gradient, out.gradient, ge, out.residual, out.status);
    }
    fprintf(summary, "%s,%s,%d,%.17g,%.17g,%.17g,%zu,%zu,%zu\n", names[domain],
            split, n, root_max, grad_max, residual_max, bad_root, bad_grad, nonfinite);
    total_fail += bad_root + bad_grad + nonfinite;
    printf("%-14s %s n=%d root_max=%.3e gradient_max=%.3e failures=%zu\n",
           names[domain], split, n, root_max, grad_max, bad_root + bad_grad + nonfinite);
    free(refs);
  }
  fclose(raw); fclose(summary); return total_fail ? 5 : 0;
}
