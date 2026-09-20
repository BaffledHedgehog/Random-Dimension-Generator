#!/usr/bin/env python3
"""Read-only JSON range audit, not a replacement for the Minecraft codecs.

FloatProvider uniform uses min_inclusive < max_exclusive; IntProvider and
loot NumberProvider bounds are inclusive and may coincide. Dynamic providers
and mixed relative height anchors cannot be ordered without runtime context.
The walk always visits children, including children of recognized providers.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).parent / "data"


def num(value):
    """Resolve only literal numbers and explicit constant providers (not bool)."""
    if isinstance(value, dict):
        if value.get("type") in ("constant", "minecraft:constant"):
            return num(value.get("value"))
        return None
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _ordered(p, lower, upper, path, errs, strict=False, label="range"):
    mn, mx = num(p.get(lower)), num(p.get(upper))
    if mn is not None and mx is not None and (mx < mn or (strict and mx == mn)):
        comparison = "min>=max" if strict else "min>max"
        errs.append(f"{path}: {label} {comparison} {mn}..{mx}")


def check_prov(p, path, errs, float_only=False):
    if not isinstance(p, dict):
        return
    t = p.get("type", "")
    t = t.removeprefix("minecraft:") if isinstance(t, str) else ""
    # Legacy wrapped IntProvider payloads also occur in older packs. This
    # checks their numeric ordering, not whether that encoding is current.
    bounds = p
    value = p.get("value")
    if isinstance(value, dict) and "type" not in value and not any(
            key in p for key in ("min", "max", "min_inclusive")):
        bounds = value
    if t == "uniform":
        if "max_exclusive" in bounds:
            _ordered(bounds, "min_inclusive", "max_exclusive", path, errs,
                     strict=True, label="float uniform")
        elif not float_only:
            if "max_inclusive" in bounds:
                _ordered(bounds, "min_inclusive", "max_inclusive", path, errs,
                         label="inclusive uniform")
            else:
                _ordered(bounds, "min", "max", path, errs,
                         label="loot uniform")
    elif t in ("biased_to_bottom", "very_biased_to_bottom", "clamped",
               "clamped_normal", "trapezoid"):
        if not float_only:
            _ordered(bounds, "min_inclusive", "max_inclusive", path, errs,
                     label=t)
        # min/max is used by FloatProviders, trapezoid IntProviders, and
        # level-based clamped values. Ordering is shared; equality is legal.
        _ordered(bounds, "min", "max", path, errs, label=t)
        if t == "trapezoid":
            mn, mx, plateau = (num(bounds.get("min")), num(bounds.get("max")),
                               num(bounds.get("plateau", 0)))
            if None not in (mn, mx, plateau) and mn <= mx and plateau > mx - mn:
                errs.append(f"{path}: trapezoid plateau {plateau} > span {mx-mn}")
    elif t == "surface_relative_threshold_filter":
        _ordered(bounds, "min_inclusive", "max_inclusive", path, errs,
                 label="surface threshold")
    # Plain predicate ranges are inclusive too: do not flag equality or
    # rewrite numbers into conditions. One-sided thresholds are valid.
    if not float_only and p and set(p) <= {"min", "max"}:
        _ordered(p, "min", "max", path, errs, label="inclusive bounds")
    _ordered(p, "min_threshold", "max_threshold", path, errs,
             label="threshold")


def walk(o, path, errs, float_only=False):
    if isinstance(o, dict):
        check_prov(o, path, errs, float_only=float_only)
        for k, v in o.items():
            walk(v, f"{path}.{k}", errs, float_only=float_only)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk(v, f"{path}[{i}]", errs, float_only=float_only)


def scan(root=ROOT, float_only=False):
    """Return (successfully parsed file count, errors); never write files."""
    root = Path(root)
    errs = []
    files = 0
    for f in sorted(root.rglob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errs.append(f"{f}: JSON PARSE ERROR: {exc}")
            continue
        files += 1
        walk(data, str(f.relative_to(root)), errs, float_only=float_only)
    return files, errs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=ROOT,
                        help="JSON tree to audit (default: adjacent data directory)")
    args = parser.parse_args(argv)
    files, errs = scan(args.root)
    print(f"scanned {files} files")
    for err in errs:
        print("ERROR:", err)
    print(f"total errors: {len(errs)}")
    # Preserve the historical reporting CLI's successful exit status.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
