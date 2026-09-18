#!/usr/bin/env python3
"""Scan datapack JSONs for invalid NumberProviders (26.2 rules)."""
import json, sys, os
from pathlib import Path

ROOT = Path(__file__).parent / "data"

def num(v):
    if isinstance(v, dict):
        if "type" in v and ("min" in v or "value" in v or "min_inclusive" in v):
            return None
        if v.get("type") in ("minecraft:constant",):
            return v.get("value")
        return None
    return v if isinstance(v, (int, float)) else None

def check_prov(p, path, errs):
    if not isinstance(p, dict):
        return
    t = p.get("type", "")
    if t == "minecraft:uniform":
        # float: min_inclusive / max_exclusive (or min/max); int: min_inclusive / max_inclusive
        mn = p.get("min_inclusive", p.get("min"))
        mx = p.get("max_exclusive", p.get("max_inclusive", p.get("max")))
        if mn is not None and mx is not None and isinstance(mn, (int, float)) and isinstance(mx, (int, float)):
            if mx <= mn:
                errs.append(f"{path}: uniform min>=max {mn}..{mx}")
    elif t == "minecraft:trapezoid":
        mn = p.get("min"); mx = p.get("max"); pl = p.get("plateau", 0)
        if None not in (mn, mx, pl) and pl > (mx - mn):
            errs.append(f"{path}: trapezoid plateau {pl} > span {mx-mn} [{mn},{mx}]")
    elif t == "minecraft:clamped":
        mn = p.get("min"); mx = p.get("max")
        if mn is not None and mx is not None and mx < mn:
            errs.append(f"{path}: clamped min>max")
    elif t == "minecraft:clamped_normal":
        mn = p.get("min"); mx = p.get("max")
        if mn is not None and mx is not None and mx < mn:
            errs.append(f"{path}: clamped_normal min>max")

def walk(o, path, errs):
    if isinstance(o, dict):
        if "type" in o and o["type"] in (
            "minecraft:uniform", "minecraft:trapezoid", "minecraft:clamped",
            "minecraft:clamped_normal", "minecraft:biased_to_bottom",
            "minecraft:very_biased_to_bottom", "minecraft:constant",
        ) and any(k in o for k in ("min", "max", "min_inclusive", "max_exclusive", "max_inclusive", "plateau", "value")):
            check_prov(o, path, errs)
        else:
            for k, v in o.items():
                walk(v, f"{path}.{k}", errs)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk(v, f"{path}[{i}]", errs)

errs = []
files = 0
for f in ROOT.rglob("*.json"):
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except Exception as e:
        errs.append(f"{f}: JSON PARSE ERROR: {e}")
        continue
    files += 1
    walk(data, str(f.relative_to(ROOT.parent.parent)), errs)

print(f"scanned {files} files")
for e in errs:
    print("ERROR:", e)
print(f"total errors: {len(errs)}")
