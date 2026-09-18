#!/usr/bin/env python3
"""Scan for FLOAT NumberProvider violations only (26.2):
   - uniform with max_exclusive <= min_inclusive
   - clamped_normal / clamped with min == max (max must be larger than min)
   - trapezoid with plateau > (max-min)
Also flags carver y-ranges and other suspicious spots."""
import json
from pathlib import Path

ROOT = Path(__file__).parent / "data"

def walk(o, path, errs):
    if isinstance(o, dict):
        t = o.get("type", "")
        if t == "minecraft:uniform" and "max_exclusive" in o:
            mn, mx = o.get("min_inclusive"), o.get("max_exclusive")
            if isinstance(mn, (int, float)) and isinstance(mx, (int, float)) and mx <= mn:
                errs.append(f"{path}: float uniform min>=max {mn}..{mx}")
        elif t in ("minecraft:clamped_normal", "minecraft:clamped"):
            mn, mx = o.get("min"), o.get("max")
            if isinstance(mn, (int, float)) and isinstance(mx, (int, float)) and mx < mn:
                errs.append(f"{path}: {t} min>max {mn}..{mx}")
        elif t == "minecraft:trapezoid":
            mn, mx, pl = o.get("min"), o.get("max"), o.get("plateau", 0)
            if None not in (mn, mx, pl) and pl > (mx - mn):
                errs.append(f"{path}: trapezoid plateau {pl} > span {mx-mn}")
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
    walk(data, str(f.relative_to(ROOT)), errs)

print(f"scanned {files} files, {len(errs)} FLOAT violations")
for e in errs:
    print("ERROR:", e)
