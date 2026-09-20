#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_trial_spawners.py - генератор случайных конфигов trial_spawner
(Minecraft 26.2, pack_format 107). Синтаксис сверен с ванильным jar 26.2
(minecraft-26.2-client.jar): всеми 28 JSON из data/minecraft/trial_spawner/
(trial_chamber/*/normal|ominous.json, DataVersion 4903) и байткодом классов
кодеков (javap Java 25):

  TrialSpawnerConfig.DIRECT_CODEC - RecordCodecBuilder из 9 полей, ВСЕ
  optionalFieldOf (дефолты из TrialSpawnerConfig$Builder):
    spawn_range:                        Codec.intRange(1, 128),         def 4
    total_mobs:                         floatRange(0, MAX),             def 6.0
    simultaneous_mobs:                  floatRange(0, MAX),             def 2.0
    total_mobs_added_per_player:        floatRange(0, MAX),             def 2.0
    simultaneous_mobs_added_per_player: floatRange(0, MAX),             def 1.0
    ticks_between_spawn:                intRange(0, MAX_INT),           def 40
    spawn_potentials:   WeightedList<SpawnData> (LIST_CODEC),          def []
    loot_tables_to_eject: WeightedList<LootTable.KEY_CODEC>,           def
        [spawners/trial_chamber/consumables, spawners/trial_chamber/key]
        (bайткод Builder: BuiltInLootTables.SPAWNER_TRIAL_CHAMBER_*)
    items_to_drop_when_ominous: LootTable.KEY_CODEC,                   def
        spawners/trial_chamber/items_to_drop_when_ominous
  Реестр: Registries.TRIAL_SPAWNER_CONFIG - простой реестр датапака, файлы
  data/<ns>/trial_spawner/<имя>.json (БЕЗ префикса worldgen/), как в jar.

  SpawnData.CODEC - 3 поля (байткод SpawnData.class):
    entity:            CompoundTag.CODEC, fieldOf - СЫРОЙ NBT-компаунд!
                       Значит полное NBT моба валидно: id + IsBaby/Size
                       (ванильные конфиги) + CustomName/attributes/Health/
                       equipment{<слот>:ItemStack}/drop_chances/
                       DeathLootTable/PersistenceRequired/... - те же теги,
                       что и у мобов в .nbt-шаблонах (Entity.load), БЕЗ
                       NoAI/Invulnerable (мобы живут своей жизнью и уязвимы).
    custom_spawn_rules: optionalFieldOf - CustomSpawnRules.CODEC:
                       block_light_limit / sky_light_limit, оба
                       InclusiveRange.INT (JSON {"min_inclusive":
                       <0..15>, "max_inclusive": <0..15>}).
    equipment:         optionalFieldOf - EquipmentTable.CODEC: {loot_table
                       (обяз.), slot_drop_chances (опц. float либо map
                       слот->float)} - НЕ экипировка моба, а ССЫЛКА на
                       лут-таблицу equipment/* (ванильные ominous-конфиги:
                       "minecraft:equipment/trial_chamber_melee").
  WeightedList в JSON: [{"data": <SpawnData>, "weight": <int>}, ...].

Модуль импортируется главным скриптом (generate_dimension.py) и сам ничего
не пишет на диск - только ВОЗВРАЩАЕТ данные:

    rand_trial_spawners(rng, ns, name, loot_alloc=None, mob_pool=None,
                        count=None)
        -> {"trial_spawners": {id: json}, "loot_slots": <int>}

    id вида "<ns>:<name>_tsN" (normal) и "<ns>:<name>_tsN_om" (ominous) -
    файлы data/<ns>/trial_spawner/<name>_tsN.json / <name>_tsN_om.json.
    Пары согласованы: обычный конфиг и его «злая» версия (больше мобов,
    быстрее спавн, equipment-таблицы). loot_alloc - общий на измерение
    счётчик gen_structures.LootSlots: КАЖДАЯ ссылка на лут (DeathLootTable
    моба-«босса» из spawn_potentials, приз из loot_tables_to_eject,
    items_to_drop_when_ominous) занимает СВОЙ уникальный слот
    "<ns>:<name>_lootN" - без повторов в рамках измерения; None -> ванильные
    таблицы. "loot_slots" - сколько слотов занял этот вызов. mob_pool -
    список мобов (по умолчанию gen_structures.STRUCTURE_MOBS).

Ключи для волтов (trial_key) ванильные спавнеры выбрасывают через
loot_tables_to_eject (minecraft:spawners/trial_chamber/key -
BuiltInLootTables, подтверждено байткодом) - поэтому в normal-конфигах
эта таблица присутствует всегда: волт в паре со спавнером открываем.
"""

import random

# Импорт из gen_structures: пул мобов, генератор полного NBT «босса» и
# общий счётчик слотов лут-таблиц (зависимость односторонняя:
# gen_structures этот модуль НЕ импортирует).
from gen_structures import STRUCTURE_MOBS, LootSlots, _rand_mob_nbt

# ---------------------------------------------------------------------------
# Константы, подтверждённые ванильным jar 26.2
# ---------------------------------------------------------------------------

# Ванильные лут-таблицы выброса (BuiltInLootTables.class, байткод ldc):
# именно из них выпадают trial_key/ominous_trial_key.
VANILLA_SPAWNER_KEY = "minecraft:spawners/trial_chamber/key"
VANILLA_SPAWNER_KEY_OMINOUS = "minecraft:spawners/ominous/trial_chamber/key"
VANILLA_SPAWNER_CONSUMABLES = "minecraft:spawners/trial_chamber/consumables"
VANILLA_SPAWNER_CONSUMABLES_OM = \
    "minecraft:spawners/ominous/trial_chamber/consumables"
VANILLA_ITEMS_TO_DROP_WHEN_OMINOUS = \
    "minecraft:spawners/trial_chamber/items_to_drop_when_ominous"

# Ванильные equipment-таблицы для SpawnData.equipment (встречаются в
# ominous-конфигах trial_chamber)
EQUIPMENT_TABLES = [
    "minecraft:equipment/trial_chamber_melee",
    "minecraft:equipment/trial_chamber_ranged",
    "minecraft:equipment/trial_chamber",
]


def _heavy_count(rng, mean, big_min, big_max, big_p):
    """Тяжёлохвостое число (паттерн heavy_count из generate_dimension):
    почти всегда маленькое (экспоненциальное со средним ~mean, не выше
    big_min-1), с шансом big_p - большой выброс, лог-равномерный
    в [big_min, big_max]. Скопировано, чтобы не тянуть цикл импорта."""
    n = 1 + int(rng.expovariate(1.0 / max(0.5, mean - 1)))
    if rng.random() < big_p:
        import math
        return int(round(math.exp(
            rng.uniform(math.log(big_min), math.log(big_max)))))
    return max(1, min(n, big_min - 1))


def _mob_entity(rng, mob_pool, loot_alloc, boss_chance):
    """NBT entity для spawn_potentials. С шансом boss_chance - полный NBT
    «босса» из gen_structures._rand_mob_nbt (CustomName/attributes/
    equipment/DeathLootTable - CompoundTag.CODEC в SpawnData принимает
    сырой NBT, см. докстринг модуля); иначе - минимум: id (+ изредка
    IsBaby/Size, как в ванильных конфигах). Никогда NoAI/Invulnerable -
    мобы живут своей жизнью и уязвимы."""
    if rng.random() < boss_chance:
        return _rand_mob_nbt(rng, loot_alloc)
    mob = rng.choice(mob_pool)
    eid = mob if ":" in mob else "minecraft:" + mob
    entity = {"id": eid}
    if mob.split(":")[-1] == "zombie" and rng.random() < 0.2:
        entity["IsBaby"] = 1        # как в ванильном small_melee/baby_zombie
    if mob.split(":")[-1] == "slime" and rng.random() < 0.3:
        entity["Size"] = rng.randint(1, 3)   # как в ванильном small_melee/slime
    return entity


def _rand_spawn_potentials(rng, mob_pool, loot_alloc, boss_chance,
                           equip_chance):
    """spawn_potentials: 1-3 взвешенных SpawnData. equip_chance - шанс
    equipment-таблицы (SpawnData.equipment, только поле loot_table +
    slot_drop_chances float, как в ванильных ominous-конфигах)."""
    potentials = []
    for _ in range(rng.randint(1, 3)):
        data = {"entity": _mob_entity(rng, mob_pool, loot_alloc,
                                      boss_chance)}
        if rng.random() < equip_chance:
            data["equipment"] = {
                "loot_table": rng.choice(EQUIPMENT_TABLES),
                "slot_drop_chances": round(rng.uniform(0.0, 0.15), 3),
            }
        # custom_spawn_rules: ограничения света (InclusiveRange.INT 0..15)
        if rng.random() < 0.12:
            lo = rng.randint(0, 12)
            data["custom_spawn_rules"] = {
                "block_light_limit": {
                    "min_inclusive": lo, "max_inclusive": rng.randint(lo, 15)},
                "sky_light_limit": {
                    "min_inclusive": rng.randint(0, 12),
                    "max_inclusive": 15},
            }
        potentials.append({"data": data, "weight": rng.randint(1, 8)})
    return potentials


def _rand_loot_tables_to_eject(rng, loot_alloc, ominous):
    """loot_tables_to_eject: что спавнер выбрасывает при «победе».
    ВСЕГДА включаем ванильную таблицу ключей - из неё выпадают trial_key,
    которыми открываются волты (иначе пары спавнер+волт из gen_structures
    неиграбельны); остальное - призы (каждый СВОЙ уникальный слот) /
    consumables."""
    out = []
    if ominous:
        out.append({"data": VANILLA_SPAWNER_KEY_OMINOUS,
                    "weight": rng.randint(1, 4)})
        out.append({"data": VANILLA_SPAWNER_CONSUMABLES_OM,
                    "weight": rng.randint(2, 9)})
    else:
        out.append({"data": VANILLA_SPAWNER_KEY, "weight": 1})
        if rng.random() < 0.4:
            out.append({"data": VANILLA_SPAWNER_CONSUMABLES,
                        "weight": rng.randint(2, 9)})
    if loot_alloc is not None and rng.random() < 0.5:
        out.append({"data": loot_alloc.take(), "weight": rng.randint(1, 5)})
    return out


def _rand_ts_config(rng, mob_pool, loot_alloc, base=None):
    """Один конфиг trial_spawner. base - «обычная» версия, от которой
    делается злая (поля сильнее); None - генерировать с нуля.

    ПЛОТНОСТЬ СПАВНА СОЗНАТЕЛЬНО СКРОМНАЯ (жёсткие лимиты, чтобы измерение
    не заполнялось мобами, как у ванильных trial chambers): normal
    simultaneous_mobs 1..3, ominous максимум 4; per_player <= 0.5;
    ticks_between_spawn >= 40 (реже = лучше)."""
    ominous = base is not None
    if ominous:
        sim = min(4.0, round(base["simultaneous_mobs"] *
                             rng.uniform(1.25, 1.7), 1))
        total = min(12.0, round(base["total_mobs"] *
                                rng.uniform(1.5, 2.5), 1))
        ticks = max(40, int(round(base["ticks_between_spawn"] *
                                  rng.uniform(0.7, 1.0))))
    else:
        sim = round(rng.uniform(1.0, 3.0), 1)
        total = round(rng.uniform(2.0, 6.0), 1)
        ticks = rng.choice([40, 40, 60, 80, 100, 120, 160, 200])
    cfg = {
        "simultaneous_mobs": sim,
        "simultaneous_mobs_added_per_player": round(
            rng.uniform(0.1, 0.5), 2),
        "total_mobs": total,
        "total_mobs_added_per_player": round(rng.uniform(0.5, 1.0), 2),
        "ticks_between_spawn": ticks,
        # боссы с полным NBT чаще в ominous; equipment-таблицы - тоже
        "spawn_potentials": _rand_spawn_potentials(
            rng, mob_pool, loot_alloc,
            boss_chance=0.45 if ominous else 0.2,
            equip_chance=0.6 if ominous else 0.1),
        "loot_tables_to_eject": _rand_loot_tables_to_eject(
            rng, loot_alloc, ominous),
    }
    if rng.random() < 0.3:
        cfg["spawn_range"] = rng.randint(2, 8)   # intRange(1, 128)
    if ominous:
        # items_to_drop_when_ominous: свой слот или ванильная таблица
        if loot_alloc is not None and rng.random() < 0.5:
            cfg["items_to_drop_when_ominous"] = loot_alloc.take()
        elif rng.random() < 0.6:
            cfg["items_to_drop_when_ominous"] = VANILLA_ITEMS_TO_DROP_WHEN_OMINOUS
    return cfg


def rand_trial_spawners(rng, ns, name, loot_alloc=None, mob_pool=None,
                        count=None):
    """Случайные ПАРЫ конфигов trial_spawner (normal + ominous).

    Возвращает {"trial_spawners": {id: json}, "loot_slots": <int>} -
    файлы писать в data/<ns>/trial_spawner/<имя из id>.json (реестр БЕЗ
    worldgen/). id: "<ns>:<name>_tsN" (normal) и "<ns>:<name>_tsN_om"
    (ominous) - gen_structures различает пару по суффиксу "_om".

    loot_alloc - общий на измерение счётчик gen_structures.LootSlots:
    каждая ссылка на лут занимает СВОЙ уникальный слот (None -> только
    ванильные таблицы); mob_pool - список мобов (по умолчанию
    gen_structures.STRUCTURE_MOBS); count - сколько ПАР (по умолчанию
    тяжёлый хвост: в среднем ~3, выбросы до ~20). "loot_slots" - сколько
    слотов лута занял этот вызов."""
    mob_pool = list(mob_pool) if mob_pool else STRUCTURE_MOBS
    _slots0 = loot_alloc.count if loot_alloc is not None else 0
    n = count if count is not None else _heavy_count(rng, 3, 8, 20, 0.08)
    out = {}
    for i in range(n):
        base_id = "%s:%s_ts%d" % (ns, name, i + 1)
        om_id = "%s:%s_ts%d_om" % (ns, name, i + 1)
        normal = _rand_ts_config(rng, mob_pool, loot_alloc)
        out[base_id] = normal
        out[om_id] = _rand_ts_config(rng, mob_pool, loot_alloc, base=normal)
    return {"trial_spawners": out,
            "loot_slots": (loot_alloc.count if loot_alloc is not None
                           else 0) - _slots0}


def pair_config_ids(ids):
    """Разбить плоский список id конфигов на пары (normal, ominous) по
    суффиксу "_om" (для gen_structures: блоку нужны оба). Конфиг без
    пары используется как свой own ominous (валидно - это просто id)."""
    ids = [i for i in (ids or []) if i]
    normals = [i for i in ids if not i.endswith("_om")]
    return [(i, (i + "_om" if i + "_om" in ids else i)) for i in normals]


# ---------------------------------------------------------------------------
# Самопроверка
# ---------------------------------------------------------------------------

def _self_test(seeds=20):
    import json as _json
    ok = 0
    import re
    for seed in range(1, seeds + 1):
        rng = random.Random(seed)
        alloc = LootSlots("rndim", "testdim")
        ts = rand_trial_spawners(rng, "rndim", "testdim", loot_alloc=alloc)
        cfgs = ts["trial_spawners"]
        assert set(ts) == {"trial_spawners", "loot_slots"}
        assert ts["loot_slots"] == alloc.count, (ts["loot_slots"],
                                                 alloc.count)
        assert len(cfgs) >= 2 and len(cfgs) % 2 == 0
        normals = sorted(i for i in cfgs if not i.endswith("_om"))
        # парность: каждому tsN соответствует tsN_om
        for nid in normals:
            assert nid + "_om" in cfgs, nid
        for cid, cfg in cfgs.items():
            _json.dumps(cfg)                       # сериализуемость
            fname = cid.split(":", 1)[1]
            assert re.fullmatch(r"[a-z0-9_/]+", fname), fname
            # границы кодека (байткод TrialSpawnerConfig):
            assert 1 <= cfg.get("spawn_range", 4) <= 128
            assert cfg["ticks_between_spawn"] >= 0
            for k in ("simultaneous_mobs", "total_mobs",
                      "simultaneous_mobs_added_per_player",
                      "total_mobs_added_per_player"):
                assert cfg[k] >= 0, (cid, k)
            pots = cfg["spawn_potentials"]
            assert 1 <= len(pots) <= 3
            for p in pots:
                assert isinstance(p["weight"], int) and p["weight"] >= 1
                assert "id" in p["data"]["entity"], (cid, p)
                # мобы живые и уязвимые: NoAI/Invulnerable запрещены
                assert not ({"NoAI", "Invulnerable"}
                            & set(p["data"]["entity"])), (cid, p)
                if "equipment" in p["data"]:
                    assert "loot_table" in p["data"]["equipment"]
                    assert 0.0 <= p["data"]["equipment"].get(
                        "slot_drop_chances", 0.0) <= 1.0
                if "custom_spawn_rules" in p["data"]:
                    for lim in ("block_light_limit", "sky_light_limit"):
                        r = p["data"]["custom_spawn_rules"][lim]
                        assert (0 <= r["min_inclusive"] <=
                                r["max_inclusive"] <= 15), (cid, lim)
            eject = cfg["loot_tables_to_eject"]
            assert eject and all(
                {"data", "weight"} <= set(e) for e in eject)
            # в normal ВСЕГДА есть ванильная таблица ключей (иначе волты
            # в паре со спавнером неоткрываемы)
            if not cid.endswith("_om"):
                assert any(e["data"] == VANILLA_SPAWNER_KEY
                           for e in eject), cid
        # УНИКАЛЬНОСТЬ: каждая ссылка на наш лут (DeathLootTable босса,
        # приз из eject, items_to_drop_when_ominous) - свой слот, без
        # повторов во всём измерении
        refs = []
        for cfg in cfgs.values():
            for p in cfg["spawn_potentials"]:
                lt = p["data"]["entity"].get("DeathLootTable")
                if lt and lt.startswith("rndim:"):
                    refs.append(lt)
            refs += [e["data"] for e in cfg["loot_tables_to_eject"]
                     if e["data"].startswith("rndim:")]
            it = cfg.get("items_to_drop_when_ominous")
            if it and it.startswith("rndim:"):
                refs.append(it)
        assert len(refs) == len(set(refs)) and len(refs) == alloc.count, \
            (len(refs), len(set(refs)), alloc.count)
        # ominous злее normal той же пары
        for nid in normals:
            n, o = cfgs[nid], cfgs[nid + "_om"]
            assert (o["simultaneous_mobs"] >= n["simultaneous_mobs"] and
                    o["total_mobs"] >= n["total_mobs"] and
                    o["ticks_between_spawn"] <= n["ticks_between_spawn"]), nid
        # жёсткие лимиты плотности спавна (чтобы не было тысяч мобов):
        # simultaneous_mobs <= 4, per_player <= 0.5, ticks >= 40
        for cid, cfg in cfgs.items():
            assert cfg["simultaneous_mobs"] <= 4.0, cid
            assert cfg["simultaneous_mobs_added_per_player"] <= 0.5, cid
            assert cfg["ticks_between_spawn"] >= 40, cid
        # воспроизводимость
        rng2 = random.Random(seed)
        ts2 = rand_trial_spawners(rng2, "rndim", "testdim",
                                  loot_alloc=LootSlots("rndim", "testdim"))
        assert ts2 == ts, seed
        # pair_config_ids
        pairs = pair_config_ids(sorted(cfgs))
        assert len(pairs) == len(normals)
        assert all(b.endswith("_om") for _, b in pairs)
        print("seed %2d: пар=%d конфигов=%d (боссов с полным NBT: %d, "
              "лут-слотов: %d)" % (
                  seed, len(normals), len(cfgs),
                  sum(1 for c in cfgs.values() for p in c["spawn_potentials"]
                      if len(p["data"]["entity"]) > 1), alloc.count))
        ok += 1
    # распределение количества пар: тяжёлый хвост
    counts = [rand_trial_spawners(random.Random(1000 + i), "rndim", "t")
              ["trial_spawners"] for i in range(200)]
    n_pairs = [len(c) // 2 for c in counts]
    mean = sum(n_pairs) / len(n_pairs)
    assert 1 <= mean <= 6, mean
    assert max(n_pairs) <= 20
    print("OK: %d/%d seed'ов без исключений; среднее число пар %.2f, "
          "макс %d" % (ok, seeds, mean, max(n_pairs)))


if __name__ == "__main__":
    _self_test()
