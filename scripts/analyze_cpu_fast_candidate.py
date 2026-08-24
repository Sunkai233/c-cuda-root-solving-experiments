#!/usr/bin/env python3
import argparse
import csv
import random
import statistics
from collections import defaultdict
from pathlib import Path


def q(values, p):
    values = sorted(values)
    return values[int(p * (len(values) - 1))]


def load(path):
    groups = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            groups[(row["domain"], int(row["n"]))].append(float(row["time_ms"]))
    return groups


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("strict_csv", type=Path)
    parser.add_argument("fast_run", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    strict, fast = load(args.strict_csv), load(args.fast_run / "fast_omp96.csv")
    rows = []
    for index, key in enumerate(sorted(set(strict) & set(fast))):
        ratios = [x / y for x, y in zip(strict[key], fast[key])]
        rng = random.Random(20260824 + index); n = len(ratios)
        boot = [statistics.median(ratios[rng.randrange(n)] for _ in range(n))
                for _ in range(10000)]
        rows.append({"domain": key[0], "n": key[1],
                     "strict_median_ms": statistics.median(strict[key]),
                     "fast_median_ms": statistics.median(fast[key]),
                     "strict_over_fast": statistics.median(ratios),
                     "ci95_low": q(boot, .025), "ci95_high": q(boot, .975)})
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "cpu_fast_performance_bootstrap.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    print(f"wrote {len(rows)} strict/fast comparisons; status={ (args.fast_run/'FAST_STATUS.txt').read_text().strip() }")


if __name__ == "__main__":
    main()
