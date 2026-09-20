#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Миграция названий зачарований: переписывает description.text в существующих
data/<ns>/enchantment/*.json по РЕАЛЬНЫМ эффектам (логика gen_enchantments
26.2+). Меняет ТОЛЬКО текст названия - цвет, эффекты, id, эксклюзив-сеты,
mcfunction-связи и лут не трогаются.

Запуск:  python migrate_ench_names.py [--dry]
"""
import json
import random
import re
import sys
import zlib
from pathlib import Path

import gen_enchantments as ge

DRY = "--dry" in sys.argv
ROOT = Path(__file__).parent / "data"
FILES = sorted((ROOT / "rndim" / "enchantment").glob("*.json"))


def main():

    # группируем по измерению: <dim>_enchN -> dim (имена уникальны в пределах dim)
    by_dim = {}
    for p in FILES:
        m = re.match(r"(.+)_ench\d+$", p.stem)
        by_dim.setdefault(m.group(1) if m else p.stem, []).append(p)

    changed = kept = 0
    samples = []
    for dim, paths in sorted(by_dim.items()):
        rng = random.Random(zlib.crc32(dim.encode("utf-8")))  # стабильный seed
        used = set()
        for p in paths:
            d = json.loads(p.read_text(encoding="utf-8"))
            old = d.get("description", {}).get("text", "")
            effects = d.get("effects", {})
            nm = None
            for _ in range(10):
                cand = ge._effect_name(rng, effects)
                if cand and cand not in used:
                    nm = cand
                    break
                # коллизия/пусто - усложняем шаблон
                seeds = ge._name_seeds(effects, rng)
                if seeds:
                    lead = seeds[0][1]
                    g = ge._word_gender(lead)
                    if g is not None:
                        cand2 = "%s %s" % (ge._inflect_adj(rng.choice(ge._ADJ), g),
                                           lead)
                        if cand2 not in used:
                            nm = cand2
                            break
                    cand3 = "%s %s" % (lead, rng.choice(ge._GEN))
                    if cand3 not in used:
                        nm = cand3
                        break
            if not nm:
                nm = old  # совсем крайний случай - оставляем старое
            if nm != old:
                changed += 1
            else:
                kept += 1
            used.add(nm)
            if len(samples) < 14:
                samples.append((dim, p.stem, old, nm))
            if not DRY and nm != old:
                d["description"]["text"] = nm
                p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")

    print("файлов: %d, изменено: %d, оставлено: %d%s"
          % (len(FILES), changed, kept, " (DRY)" if DRY else ""))
    for dim, stem, old, new in samples:
        print("  %s/%s: «%s» -> «%s»" % (dim, stem, old, new))



if __name__ == "__main__":
    main()
