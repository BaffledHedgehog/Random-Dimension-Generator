# -*- coding: utf-8 -*-
"""Аудит находимости структур: генерируем измерения в памяти и считаем
эмпирические метрики находимости (биом-площади, /locate-дистанции)."""
import json
import math
import random
import sys

sys.path.insert(0, ".")
import generate_dimension as gd

N_DIMS = 60
NS = "rndim"

# ---------------------------------------------------------------- helpers

def channel_marginal(ch, rng):
    """Приближение маргинального распределения climate-канала по его DF."""
    if isinstance(ch, (int, float)):
        return ("c", float(ch))
    if isinstance(ch, str):  # ссылка на DF-файл — читаем из noises? нет, DF.
        return ("n", 0.5)
    t = ch.get("type")
    if t == "minecraft:noise":
        spec = ch.get("noise")
        amp = 0.3
        if isinstance(spec, str):
            amp = 0.35
        else:
            amps = spec.get("amplitudes") or [1.0]
            amp = 0.30 * math.sqrt(sum(a * a for a in amps))
        return ("n", min(1.2, max(0.05, amp)))
    if t == "minecraft:y_clamped_gradient":
        fv = ch.get("from_value", 0.0)
        tv = ch.get("to_value", 0.0)
        return ("c", (fv + tv) / 2.0)
    if t == "minecraft:flat_cache":
        return channel_marginal(ch.get("argument"), rng)
    if t == "minecraft:constant":
        return ("c", float(ch.get("argument", 0)))
    # add/mul/min/max/abs/... — шумоподобные
    return ("n", 0.5)


def biome_area_fractions(dim, rng, samples=6000):
    """Monte-Carlo площадей биомов multi_noise (i.i.d. по каналам)."""
    gen = dim["dimension"]["generator"]
    bs = gen.get("biome_source") or {}
    if bs.get("type") != "minecraft:multi_noise" or "biomes" not in bs:
        return None
    entries = bs["biomes"]
    router = dim["noise_settings"]["noise_router"]
    chans = {}
    for name in ("temperature", "humidity", "continentalness", "erosion",
                 "weirdness", "depth"):
        # biome_source использует "vegetation" вместо "humidity"? проверим ключи
        chans[name] = channel_marginal(router.get(name, 0.0), rng)
    # ключи параметров биома: temperature/humidity/continentalness/erosion/
    # weirdness/depth/offset (в 26.2 vegetation == humidity в исходнике? нет:
    # в multi_noise json это "humidity")
    param_keys = list(entries[0]["parameters"].keys())
    params = []
    offs = []
    for e in entries:
        p = e["parameters"]
        params.append([float(p.get(k, 0.0)) for k in param_keys])
        offs.append(float(p.get("offset", 0.0)))
    # маргинали по ключам параметров: маппим имена
    marg = []
    for k in param_keys:
        if k == "offset":
            marg.append(None)
            continue
        # параметр биома -> канал router (в 26.2 humidity->vegetation,
        # weirdness->ridges)
        rname = {"humidity": "vegetation", "weirdness": "ridges"}.get(k, k)
        marg.append(channel_marginal(router.get(rname, 0.0), rng))
    counts = [0] * len(entries)
    keys_idx = list(range(len(param_keys)))
    for _ in range(samples):
        vals = []
        for i in keys_idx:
            m = marg[i]
            if m is None:
                vals.append(0.0)
            elif m[0] == "c":
                vals.append(m[1])
            else:
                vals.append(max(-1.5, min(1.5, rng.gauss(0.0, m[1]))))
        best, bd = 0, 1e9
        for bi in range(len(params)):
            d = offs[bi] * offs[bi]
            pp = params[bi]
            for i in keys_idx:
                if marg[i] is None:
                    continue
                dv = pp[i] - vals[i]
                d += dv * dv
            if d < bd:
                bd, best = d, bi
        counts[best] += 1
    return {entries[i]["biome"]: counts[i] / samples
            for i in range(len(entries))}


def resolve_biomes(ref, biome_tags):
    if isinstance(ref, str) and ref.startswith("#"):
        tag = ref[1:].split(":", 1)[1]
        return biome_tags.get(tag, [])
    return list(ref or [])


# ---------------------------------------------------------------- main

def analyze(seed):
    rng = random.Random(seed)
    name = "audit%d" % seed
    gen = gd.DimensionGenerator(rng, NS, name)
    dim = gen.generate()
    res = {"seed": seed}
    st = dim.get("structures_data") or {}
    structures = st.get("structures", {})
    sets = st.get("structure_sets", {})
    biome_tags = st.get("biome_tags", {})
    res["n_biomes"] = len(dim["biomes"])
    res["n_structs"] = len(structures)
    res["min_y"] = gen.min_y
    res["max_y"] = gen.max_y
    res["sea_level"] = dim["noise_settings"]["sea_level"]
    # биом-площади
    areas = biome_area_fractions(dim, random.Random(seed + 7))
    res["bs_kind"] = (dim["dimension"]["generator"].get("biome_source")
                      or {}).get("type")
    res["areas"] = areas
    # какие структуры в каких сетах
    in_set = {}
    for ssid, ss in sets.items():
        for e in ss["structures"]:
            in_set.setdefault(e["structure"], []).append(ssid)
    rows = []
    for sid, sj in structures.items():
        b = resolve_biomes(sj["biomes"], biome_tags)
        area = sum(areas.get(x, 0.0) for x in b) if areas else None
        stype = sj["type"].split(":")[-1]
        row = {"sid": sid, "type": stype, "k_biomes": len(b), "area": area,
               "sets": in_set.get(sid, [])}
        # Findability-гейты по типу (из байткода 26.2)
        dead = None
        if stype == "ocean_monument":
            dead = "vanilla-tag: #required_ocean_monument_surrounding"
        if stype in ("woodland_mansion", "end_city") and gen.max_y <= 60:
            dead = "lowest Y in 5x5 box < 60 (hardcoded)"
        if not row["sets"]:
            dead = dead or "NO STRUCTURE SET (combined rings bug?)"
        row["dead"] = dead
        # placement
        for ssid in row["sets"]:
            p = sets[ssid]["placement"]
            if p["type"] == "minecraft:random_spread":
                row.setdefault("rs", []).append(
                    (p["spacing"], p["separation"], p.get("frequency", 1.0)))
            else:
                row.setdefault("rings", []).append(
                    (p["distance"], p["spread"], p["count"]))
        rows.append(row)
    res["rows"] = rows
    return res


def main():
    stats = {"dead_total": 0, "struct_total": 0, "dead_reasons": {},
             "locate_blocks": [], "locate_fail": 0, "stumble": [],
             "spacing": [], "freq": [], "sep": [], "rings_dist": [],
             "rings_zero": 0, "rings_total": 0, "area_small": 0,
             "area_total": 0, "area_zero": 0, "risky60": 0,
             "dims": 0, "dims_no_findable": 0, "areas_hist": [],
             "n_biomes": [], "rings_count": [], "freq_low": 0}
    for seed in range(1, N_DIMS + 1):
        r = analyze(seed)
        stats["dims"] += 1
        stats["n_biomes"].append(r["n_biomes"])
        findable = 0
        for row in r["rows"]:
            stats["struct_total"] += 1
            stats["area_total"] += 1
            if row["area"] is not None and row["area"] < 0.02:
                stats["area_small"] += 1
            if row["area"] is not None and row["area"] <= 0.0:
                stats["area_zero"] += 1
            if row["area"] is not None:
                stats["areas_hist"].append(row["area"])
            if row["dead"]:
                stats["dead_total"] += 1
                k = row["dead"].split(" (")[0]
                stats["dead_reasons"][k] = stats["dead_reasons"].get(k, 0) + 1
                continue
            if row["area"] is None:
                continue  # не multi_noise — пропускаем метрики
            for (sp, sep, f) in row.get("rs", []):
                stats["spacing"].append(sp)
                stats["sep"].append(sep)
                stats["freq"].append(f)
                if f < 0.1:
                    stats["freq_low"] += 1
                p = f * max(row["area"], 1e-9)
                # медианная дистанция /locate (чебышёвские кольца по cells)
                if p * (201 * 201 - 1) < 1:
                    stats["locate_fail"] += 1
                else:
                    R = (math.sqrt(math.log(2.0) / p) - 1) / 2.0
                    d = R * sp * 16
                    stats["locate_blocks"].append(d)
                    if d <= 8000:
                        findable += 1
                stats["stumble"].append(sp * 16 / math.sqrt(max(p, 1e-9)))
            for (dist, spread, count) in row.get("rings", []):
                stats["rings_dist"].append((64 * dist, 20 * dist, count))
                stats["rings_total"] += 1
                stats["rings_count"].append(count)
                # P(ни одна из count позиций не прошла биом-чек)
                if (1.0 - row["area"]) ** count > 0.5:
                    stats["rings_zero"] += 1
                elif row["area"] > 0:
                    findable += 1
        if findable == 0:
            stats["dims_no_findable"] += 1
    def med(x):
        x = sorted(x)
        return (x[len(x)//2] if x else None)
    ah = sorted(stats["areas_hist"])
    print("измерений: %d, структур: %d" % (N_DIMS, stats["struct_total"]))
    print("биомов на мир: медиана %s макс %d" % (
        med(stats["n_biomes"]), max(stats["n_biomes"])))
    print("МЁРТВЫЕ структуры (не сгенерируются НИКОГДА): %d (%.0f%%)" % (
        stats["dead_total"], 100.0*stats["dead_total"]/max(1, stats["struct_total"])))
    for k, v in sorted(stats["dead_reasons"].items(), key=lambda kv: -kv[1]):
        print("   %-50s %d" % (k, v))
    print("биом-площадь структуры: медиана %.3f; < 2%%: %d/%d (%.0f%%);"
          " ~0 (биом не выигрывает Voronoi): %d (%.0f%%)" % (
              med(ah) or 0, stats["area_small"], stats["area_total"],
              100.0*stats["area_small"]/max(1, stats["area_total"]),
              stats["area_zero"],
              100.0*stats["area_zero"]/max(1, stats["area_total"])))
    lb = [x for x in stats["locate_blocks"] if x is not None]
    n_rs = len(stats["spacing"])
    print("random_spread: %d; /locate НЕ найдёт совсем: %d (%.0f%%)" % (
        n_rs, stats["locate_fail"], 100.0*stats["locate_fail"]/max(1, n_rs)))
    print("  найдёмые: медиана %s блоков, p90 %s" % (
        med(lb), lb[int(len(lb)*0.9)] if lb else None))
    print("  spacing: мин %d медиана %s макс %d; sep/spacing медиана %.2f" % (
        min(stats["spacing"]), med(stats["spacing"]), max(stats["spacing"]),
        med([s/max(sp,1) for s, sp in zip(stats["sep"], stats["spacing"])])))
    fl = [f for f in stats["freq"] if f < 1.0]
    print("  frequency<1: %d сетов (из них <0.1: %d), freq значения: %s" % (
        len(fl), stats["freq_low"], sorted(set(round(f,2) for f in fl))[:10]))
    st_m = [x for x in stats["stumble"] if x < 1e6]
    print("  stumble-дистанция (структуры с p>1e-6): медиана %s блоков" % (
        med(st_m),))
    rd = [x for x in stats["rings_dist"]]
    print("concentric_rings: %d; первый радиус: медиана %s блоков (разброс %d..%d);"
          " count: медиана %s" % (
              stats["rings_total"], med([r[0] for r in rd]),
              min(r[0] for r in rd), max(r[0] for r in rd),
              med(stats["rings_count"])))
    print("  P(ни одна позиция кольца не прошла биом)>50%%: %d из %d (%.0f%%)" % (
        stats["rings_zero"], stats["rings_total"],
        100.0*stats["rings_zero"]/max(1, stats["rings_total"])))
    print("ИЗМЕРЕНИЙ без единой находимой структуры (<8к блоков): %d из %d" % (
        stats["dims_no_findable"], stats["dims"]))


if __name__ == "__main__":
    main()
