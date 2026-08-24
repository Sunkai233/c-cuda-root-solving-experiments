#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--outb", type=Path, required=True)
ap.add_argument("--openfast-io", type=Path, required=True)
a = ap.parse_args()
sys.path.insert(0, str(a.openfast_io))
from openfast_io.FAST_output_reader import FASTOutputFile
f = FASTOutputFile(str(a.outb))
for i, (name, unit) in enumerate(zip(f.info["attribute_names"], f.info["attribute_units"])):
    if "AB1N001" in name or (name.endswith("BEM") and i < 500):
        print(f"{i}\t{name}\t{unit}")
