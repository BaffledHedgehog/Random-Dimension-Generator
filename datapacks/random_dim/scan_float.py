#!/usr/bin/env python3
"""Read-only FloatProvider ordering audit, plus threshold/trapezoid checks.

Uniform max_exclusive must be strictly larger than min_inclusive. Inclusive
bounds may coincide; quantities are not continuous predicate conditions.
This is a static range audit, not full schema/runtime validation.
"""
import argparse
from pathlib import Path

from scan_providers import scan as _scan, walk as _walk

ROOT = Path(__file__).parent / "data"


def walk(o, path, errs):
    _walk(o, path, errs, float_only=True)


def scan(root=ROOT):
    return _scan(root, float_only=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=ROOT,
                        help="JSON tree to audit (default: adjacent data directory)")
    args = parser.parse_args(argv)
    files, errs = scan(args.root)
    print(f"scanned {files} files, {len(errs)} FLOAT violations")
    for err in errs:
        print("ERROR:", err)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
