#define _GNU_SOURCE
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../include/bem_real_solver.h"

typedef struct { double vx, vy, theta, hint, root; int node; char id[64]; } Ref;

static int load(const char *path, Ref **refs) {
  FILE *fp = fopen(path, "r"); if (!fp) { perror(path); return -1; }
  char *line = NULL; size_t cap = 0; int n = 0, allocated = 0; (void)getline(&line, &cap, fp);
  while (getline(&line, &cap, fp) > 0) {
    char *fields[22] = {0}, *save = NULL, *token = strtok_r(line, ",\r\n", &save); int nf = 0;
    while (token && nf < 22) { fields[nf++] = token; token = strtok_r(NULL, ",\r\n", &save); }
    if (nf < 22) continue;
    if (n == allocated) {
      allocated = allocated ? allocated * 2 : 1024;
      Ref *grown = realloc(*refs, (size_t)allocated * sizeof(**refs));
      if (!grown) return -1; *refs = grown;
    }
    Ref *r = *refs + n++; memset(r, 0, sizeof(*r));
    snprintf(r->id, sizeof(r->id), "%s", fields[0]); r->node = atoi(fields[3]);
    r->vx = strtod(fields[4], NULL); r->vy = strtod(fields[5], NULL);
    r->theta = strtod(fields[6], NULL); r->hint = strtod(fields[7], NULL);
    r->root = strtod(fields[11], NULL);
  }
  free(line); fclose(fp); return n;
}

static double wrapped_error(double x) { return fabs(bem_wrap_pi(x)); }

int main(int argc, char **argv) {
  if (argc != 3) { fprintf(stderr, "usage: reference.csv output_dir\n"); return 2; }
  char command[4096]; snprintf(command, sizeof(command), "mkdir -p -- '%s'", argv[2]);
  if (system(command) != 0) return 3;
  Ref *refs = NULL; int n = load(argv[1], &refs); if (n <= 0) return 3;
  char summary_path[4096], failures_path[4096];
  snprintf(summary_path, sizeof(summary_path), "%s/bem_cpu_validation_summary.csv", argv[2]);
  snprintf(failures_path, sizeof(failures_path), "%s/bem_cpu_validation_failures.csv", argv[2]);
  FILE *summary = fopen(summary_path, "w"), *failures = fopen(failures_path, "w");
  if (!summary || !failures) return 3;
  fprintf(summary, "method,n,root_max,residual_max,wrong_gt_1e-7,wrong_branch_gt_1e-3,nonfinite\n");
  fprintf(failures, "method,sample_id,computed_root,reference_root,root_error,residual,valid\n");
  const int algorithms[] = {0, 1, 2, 4};
  const char *names[] = {"bisection", "brent", "illinois", "unused", "adaptive"};
  size_t total_bad = 0;
  for (size_t ai = 0; ai < sizeof(algorithms) / sizeof(algorithms[0]); ++ai) {
    int algorithm = algorithms[ai]; double root_max = 0, residual_max = 0;
    size_t wrong = 0, branch = 0, nonfinite = 0;
    for (int i = 0; i < n; ++i) {
      double root = NAN; int ok = bem_solve_algorithm(refs[i].vx, refs[i].vy, refs[i].theta,
                                                       refs[i].hint, (unsigned)refs[i].node,
                                                       algorithm, &root), valid = 0;
      double residual = bem_residual(root, refs[i].vx, refs[i].vy, refs[i].theta,
                                     (unsigned)refs[i].node, &valid);
      double error = wrapped_error(root - refs[i].root);
      int nf = !ok || !valid || !isfinite(root) || !isfinite(residual) || !isfinite(error);
      if (nf) { ++nonfinite; error = INFINITY; }
      if (error > root_max) root_max = error; if (fabs(residual) > residual_max) residual_max = fabs(residual);
      wrong += error > 1e-7; branch += error > 1e-3;
      if (nf || error > 1e-7)
        fprintf(failures, "%s,%s,%.17g,%.17g,%.17g,%.17g,%d\n", names[algorithm], refs[i].id,
                root, refs[i].root, error, residual, valid);
    }
    fprintf(summary, "%s,%d,%.17g,%.17g,%zu,%zu,%zu\n", names[algorithm], n, root_max,
            residual_max, wrong, branch, nonfinite);
    printf("%-10s n=%d root_max=%.3e wrong=%zu branch=%zu nonfinite=%zu\n",
           names[algorithm], n, root_max, wrong, branch, nonfinite);
    total_bad += wrong + branch + nonfinite;
  }
  fclose(failures); fclose(summary); free(refs); return total_bad ? 5 : 0;
}
