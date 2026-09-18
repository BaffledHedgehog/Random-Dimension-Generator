#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_predicates.py — генератор случайных predicates для Minecraft 26.2
(data format 107; каталог data/<ns>/predicate/ — единственное число;
в имени файла ТОЛЬКО basename, без «namespace:» — id с двоеточием на
Windows молча превращается в NTFS ADS-артефакт вместо файла).

ГЛАВНЫЙ ФАКТ ФОРМАТА (сверено байткодом jar 26.2, НЕ выдумано):
  В 26.2 predicates — это НЕ «типизированные файлы {"type": ...}», как
  могли бы предположить по аналогии с другими реестрами. Predicates —
  это реестр LOOT-УСЛОВИЙ (LootDataType.PREDICATE:
  Registries.PREDICATE : Registry<LootItemCondition>, кодек =
  LootItemCondition.DIRECT_CODEC, диспетчеризация по ключу "condition"):
      ReloadableServerRegistries.class → scheduleRegistryLoad(...)
      LootDataType.class static{} → PREDICATE = new LootDataType<>(
          Registries.PREDICATE, LootItemCondition.DIRECT_CODEC, ...)
      LootItemCondition.class static{} → Codec.dispatch(ldc "condition", ...)
  Т.е. файл — ОДИН объект условия {"condition": "...", ...params} —
  ровно как условия в лут-таблицах. Дополнительно DIRECT_CODEC =
  TYPED_CODEC.withAlternative(AllOfCondition.INLINE_CODEC), а
  AllOfCondition.INLINE_CODEC = список условий → корень файла может
  быть и голым МАССИВОМ [cond, cond, ...] (= неявный all_of).

  Реестр loot_condition_type 26.2 (все 20 id из
  LootItemConditions.bootstrap, сверено javap):
    random_chance{chance}, killed_by_player{}, survives_explosion{},
    entity_properties{entity, predicate}, entity_scores{entity, scores},
    location_check{predicate, offsetX/Y/Z}, match_tool{predicate},
    damage_source_properties{predicate}, block_state_property{block,
    properties}, table_bonus{enchantment, chances},
    random_chance_with_enchanted_bonus{unenchanted_chance,
    enchanted_chance:LevelBasedValue, enchantment},
    weather_check{raining, thundering}, time_check{value, period, clock},
    value_check{value:NumberProvider, range},
    enchantment_active_check{active} — НЕ генерим: требует контекст-
      параметр enchantment_active (только enchantment-компоненты),
    environment_attribute_check{attribute, value},
    inverted{term}, any_of{terms}, all_of{terms},
    reference{name}.

  МОСТИК В ЛУТ-ТАБЛИЦЫ ПОДТВЕРЖДЁН: условие
      {"condition": "minecraft:reference", "name": "<ns>:<id>"}
  существует (ConditionReference.class: MAP_CODEC =
  ResourceKey.codec(Registries.PREDICATE).fieldOf(ldc "name")) и
  ссылается на файл predicate/. Loot-таблицы и /execute if predicate
  видят ОДИН И ТОТ ЖЕ реестр. Предикаты парсятся ЛЕНИВО — ошибки не
  видны при старте сервера; тест: /execute if predicate <ns>:<id>.

  EntityPredicate в 26.2 ПОЛНОСТЬЮ ПЕРЕДЕЛАН — это КАРТА под-предикатов
  (EntityPredicate.class: Codec.dispatchedMap(ENTITY_SUB_PREDICATE_TYPE)),
  ключи — namespaced id из реестра entity_sub_predicate_type:
    minecraft:entity_type (HolderSet: id | #тег | список),
    minecraft:flags {is_baby, is_on_fire, is_on_ground, is_sneaking,
      is_sprinting, is_swimming, is_in_water, is_fall_flying, is_flying},
    minecraft:location / minecraft:stepping_on / minecraft:movement_
      affected_by (напрямую LocationPredicate),
    minecraft:distance (напрямую DistancePredicate {x, y, z, absolute,
      horizontal} — Doubles-диапазоны),
    minecraft:movement {x, y, z, speed, vertical_speed,
      horizontal_speed, fall_distance},
    minecraft:effects (карта {эффект: {amplifier, duration, visible,
      ambient}}), minecraft:nbt (голый NBT), minecraft:equipment
    {mainhand, offhand, head, chest, legs, feet, body: ItemPredicate},
    minecraft:periodic_tick (положительное int), minecraft:vehicle /
    minecraft:passenger / minecraft:targeted_entity (рекурсивный
    EntityPredicate), minecraft:team (строка), minecraft:slots
    {slots: {слот: CollectionPredicate}}, minecraft:components
    (карта точных значений компонентов), minecraft:predicates (карта
    типизированных компонент-предикатов), minecraft:entity_tags
    {all_of, any_of, none_of}, minecraft:type_specific/player,
    .../lightning {blocks_set_on_fire, entity_struck},
    .../fishing_hook {in_open_water}, .../cube_mob {size},
    .../raider {has_raid, is_captain}, .../sheep {sheared}.

  ItemPredicate 26.2 — {items: HolderSet, count: Ints, components,
  predicates} (ItemPredicate.class: items, count, components — кодек
  DataComponentMatchers ВЫПРЯМЛЕН в поля, без вложенности):
    «components» = карта ТОЧНЫХ значений компонентов,
    «predicates» = карта {компонент: типизированный предикат}
  (ОБА поля — на верхнем уровне ItemPredicate, РЯДОМ, серверная проба
  26.2). id типизированных предикатов (реестр
  DataComponentPredicates.bootstrap): minecraft: damage{damage,
  durability — Ints}, enchantments / stored_enchantments (СПИСОК
  {enchantments: HolderSet, levels: Ints}), potion_contents (HolderSet),
  custom_data (голый NBT), container, bundle_contents,
  firework_explosion, fireworks, writable_book_content,
  written_book_content, attribute_modifiers, trim, jukebox_playable,
  villager/variant.

  ВАЖНЫЕ детали (исправлено после серверной пробы 26.2):
    - time_check: поле clock ОБЯЗАТЕЛЬНО (реестр world_clock:
      "minecraft:overworld" | "minecraft:the_end"); period опционален.
    - damage_source_properties.tags — список TagPredicate-ОБЪЕКТОВ
      {"id": "minecraft:is_fire", "expected": true} — БЕЗ решётки
      (id — ResourceLocation), НЕ голых строк.
    - location_check.structures — id реестра worldgen/structure
      (mansion/fortress/jungle_pyramid, НЕ woodland_mansion/...);
      biomes — реальные id реестра worldgen/biome (mountains НЕ
      существует, есть windswept_hills); block.state — СТРОКИ
      (точное значение или {min/max} со строками).
    - minecraft:entity_tags — строковые NBT-теги сущности
      (Entity.entityTags()), НЕ теги реестра entity_type.
    - minecraft:slots — голая карта {слот: ItemPredicate}, слоты —
      имена SlotRanges: armor.head, weapon.mainhand, ...
    - player.gamemode — СПИСОК режимов (ListCodec), не строка.

  LocationPredicate: {position{x,y,z}, dimension, biomes, structures,
    block{blocks, state, nbt}, fluid{fluids, state}, light{light},
    can_see_sky, smokey}.
  EntityTarget (поле "entity"): this | attacker | direct_attacker |
    attacking_player | target_entity (LootContext$EntityTarget).
  NumberProvider: constant (голое число) | uniform{min, max} |
    binomial{n, p} (реестр NumberProviders.bootstrap).
  LevelBasedValue (enchanted_chance): minecraft:linear{base,
    per_level_above_first} | clamped{value, min, max} | fraction
    {numerator, denominator} | levels_squared{added} | exponent{base,
    power} | lookup{values, fallback}.

ЕДИНСТВЕННАЯ публичная функция:

    rand_predicates(rng, ns, name, count=None) -> {"predicates": {id: json}}

    rng    — random.Random (весь рандом только через него);
    ns     — namespace ('rndim');
    name   — имя измерения (префикс id: <ns>:<name>_predN);
    count  — сколько предикатов создать (None → тяжёлый хвост:
             в среднем ~3, выбросы до 20).

Ссылки reference — только «назад» (на predK с меньшим номером):
рекурсия физически невозможна. Модуль НИЧЕГО не пишет на диск —
возвращает dict (формат совместим с write_dimension()).
"""

import math

# ---------------------------------------------------------------------------
# Справочники (id сверен с jar 26.2: lang-файл, теги data/minecraft/tags/,
# генератором данных и байткодом; см. docstring)
# ---------------------------------------------------------------------------

# безопасные entity-типы (подмножество SPAWN_POOLS из generate_dimension.py,
# сверено с реестром entity_type 26.2 — без ловушек вроде killer_bunny)
_ENTITIES = [
    "minecraft:zombie", "minecraft:skeleton", "minecraft:creeper",
    "minecraft:spider", "minecraft:husk", "minecraft:stray",
    "minecraft:drowned", "minecraft:slime", "minecraft:enderman",
    "minecraft:cave_spider", "minecraft:witch", "minecraft:piglin",
    "minecraft:hoglin", "minecraft:zombified_piglin", "minecraft:blaze",
    "minecraft:ghast", "minecraft:magma_cube", "minecraft:phantom",
    "minecraft:guardian", "minecraft:shulker", "minecraft:breeze",
    "minecraft:wither_skeleton", "minecraft:piglin_brute",
    "minecraft:cow", "minecraft:pig", "minecraft:sheep",
    "minecraft:chicken", "minecraft:horse", "minecraft:rabbit",
    "minecraft:fox", "minecraft:wolf", "minecraft:goat", "minecraft:cat",
    "minecraft:llama", "minecraft:bee", "minecraft:frog",
    "minecraft:villager", "minecraft:polar_bear", "minecraft:turtle",
    "minecraft:squid", "minecraft:glow_squid", "minecraft:dolphin",
    "minecraft:bat", "minecraft:parrot", "minecraft:allay",
    "minecraft:parched", "minecraft:sulfur_cube", "minecraft:nautilus",
    "minecraft:camel_husk", "minecraft:happy_ghast",
    "minecraft:copper_golem", "minecraft:sniffer", "minecraft:axolotl",
    "minecraft:armor_stand", "minecraft:iron_golem", "minecraft:snow_golem",
    "minecraft:warden", "minecraft:ravager", "minecraft:evoker",
    "minecraft:vindicator", "minecraft:pillager",
]

# теги entity_type, существующие в jar 26.2 (tags/entity_type/) —
# для entity_type (HolderSet)
_ENTITY_TAGS = ["#minecraft:skeletons", "#minecraft:zombies",
                "#minecraft:undead", "#minecraft:arthropod",
                "#minecraft:raiders", "#minecraft:aquatic",
                "#minecraft:illager", "#minecraft:impact_projectiles",
                "#minecraft:freeze_immune_entity_types",
                "#minecraft:fall_damage_immune"]
# (сверено с data/minecraft/tags/entity_type/ jar 26.2 — 48 тегов;
# #minecraft:passive_mobs в 26.2 НЕ существует — сервер:
# «Missing tag: 'minecraft:passive_mobs' in 'minecraft:entity_type'»,
# поймано на реальном логе; skeletons/zombies/undead/arthropod/raiders/
# aquatic/illager — существуют)

# строки NBT-тегов сущности для minecraft:entity_tags (EntityTagPredicate:
# Entity.entityTags() → Set<String> — это обычные командные теги Tags,
# НЕ теги реестра entity_type; сверено javap)
_ENTITY_NBT_TAGS = ["marked", "boss", "summoned", "friendly",
                    "guardian", "elite", "cursed", "blessed"]

# цели для entity_properties / entity_scores (LootContext$EntityTarget).
# target_entity ИСКЛЮЧЁН: реестр predicate валидирует файлы по контексту
# без TARGET_ENTITY → WARN «Parameters [target_entity] are not provided»
# (real-server 26.2); this/attacker/direct_attacker/attacking_player
# проходят
_ENTITY_TARGETS = ["this", "attacker", "direct_attacker",
                   "attacking_player"]

# биомы и теги биомов для location_check (все id — реестр
# worldgen/biome из jar 26.2; «mountains» НЕ существует —
# это windswept_hills!)
_BIOMES = ["minecraft:plains", "minecraft:forest", "minecraft:desert",
           "minecraft:jungle", "minecraft:savanna", "minecraft:taiga",
           "minecraft:swamp", "minecraft:snowy_plains", "minecraft:beach",
           "minecraft:ocean", "minecraft:deep_ocean", "minecraft:river",
           "minecraft:windswept_hills", "minecraft:dark_forest",
           "minecraft:flower_forest", "minecraft:birch_forest",
           "minecraft:badlands", "minecraft:mushroom_fields",
           "minecraft:ice_spikes", "minecraft:sulfur_caves"]
_BIOME_TAGS = ["#minecraft:is_forest", "#minecraft:is_ocean",
               "#minecraft:is_river", "#minecraft:is_beach",
               "#minecraft:is_taiga", "#minecraft:is_jungle",
               "#minecraft:is_savanna", "#minecraft:is_mountain",
               "#minecraft:is_overworld", "#minecraft:is_nether",
               "#minecraft:is_end", "#minecraft:has_structure/mineshaft"]

# структуры для location_check (реестр worldgen/structure в jar 26.2;
# ВНИМАНИЕ: id отличаются от structure_set: особняк = mansion,
# крепость Незера = fortress, пирамида джунглей = jungle_pyramid)
_STRUCTURES = [
    "minecraft:ancient_city", "minecraft:bastion_remnant",
    "minecraft:buried_treasure", "minecraft:desert_pyramid",
    "minecraft:end_city", "minecraft:fortress", "minecraft:igloo",
    "minecraft:jungle_pyramid", "minecraft:mansion",
    "minecraft:mineshaft", "minecraft:monument",
    "minecraft:nether_fossil", "minecraft:ocean_ruin_cold",
    "minecraft:ocean_ruin_warm", "minecraft:pillager_outpost",
    "minecraft:ruined_portal", "minecraft:shipwreck",
    "minecraft:shipwreck_beached", "minecraft:stronghold",
    "minecraft:swamp_hut", "minecraft:trail_ruins",
    "minecraft:trial_chambers", "minecraft:village_desert",
    "minecraft:village_plains", "minecraft:village_savanna",
    "minecraft:village_snowy", "minecraft:village_taiga",
]

_DIMENSIONS = ["minecraft:overworld", "minecraft:the_nether",
               "minecraft:the_end"]

# блоки для BlockPredicate.location / block_state_property
_BLOCKS = ["minecraft:stone", "minecraft:dirt", "minecraft:grass_block",
           "minecraft:sand", "minecraft:gravel", "minecraft:cobblestone",
           "minecraft:oak_log", "minecraft:oak_planks", "minecraft:water",
           "minecraft:lava", "minecraft:iron_ore", "minecraft:coal_ore",
           "minecraft:gold_ore", "minecraft:diamond_ore",
           "minecraft:redstone_ore", "minecraft:lapis_ore",
           "minecraft:obsidian", "minecraft:netherrack",
           "minecraft:end_stone", "minecraft:deepslate",
           "minecraft:snow", "minecraft:ice", "minecraft:bedrock",
           "minecraft:glass", "minecraft:bookshelf", "minecraft:bricks",
           "minecraft:cinnabar", "minecraft:sulfur"]

# эффекты (реестр mob_effect 26.2; без nonexistent)
_EFFECTS = ["speed", "slowness", "haste", "mining_fatigue", "strength",
            "instant_health", "instant_damage", "jump_boost", "nausea",
            "regeneration", "resistance", "fire_resistance",
            "water_breathing", "invisibility", "blindness", "night_vision",
            "hunger", "weakness", "poison", "wither", "glowing",
            "levitation", "slow_falling", "luck", "unluck",
            "bad_omen", "hero_of_the_village", "darkness",
            "wind_charged", "weaving", "oozing", "infested"]

# слоты entity-экипировки (EntityEquipmentPredicate)
_EQ_SLOTS = ["mainhand", "offhand", "head", "chest", "legs", "feet", "body"]
# слоты для minecraft:slots (SlotsPredicate) — имена SlotRanges 26.2
# (дизассемблик SlotRanges): armor.head/chest/legs/feet/body, weapon.
# mainhand/offhand, saddle, hotbar.*, inventory.*, container.*, enderchest.*,
# horse.*, player.cursor + wildcards armor.* / weapon.* — голых
# «head»/«legs»/«armor» НЕ существует (real-server: "Unknown element
# name:armor" на rynanox_pred0 — голый armor это EquipmentSlotGroup
# зачарований, а не SlotRange)
_INV_SLOTS = ["weapon.mainhand", "weapon.offhand", "armor.head",
              "armor.chest", "armor.legs", "armor.feet", "armor.body",
              "saddle", "hotbar.0", "inventory.0", "container.0",
              "armor.*", "weapon.*", "player.cursor"]

# безопасные предметы для ItemPredicate.items
_ITEMS = ["minecraft:diamond_sword", "minecraft:iron_sword",
          "minecraft:golden_apple", "minecraft:diamond", "minecraft:emerald",
          "minecraft:iron_ingot", "minecraft:gold_ingot", "minecraft:book",
          "minecraft:enchanted_book", "minecraft:bow", "minecraft:crossbow",
          "minecraft:potion", "minecraft:totem_of_undying",
          "minecraft:elytra", "minecraft:trident", "minecraft:mace",
          "minecraft:diamond_pickaxe", "minecraft:diamond_helmet",
          "minecraft:netherite_ingot", "minecraft:blaze_rod",
          "minecraft:ender_pearl", "minecraft:bread", "minecraft:rotten_flesh"]
_ITEM_TAGS = ["#minecraft:swords", "#minecraft:pickaxes", "#minecraft:axes",
              "#minecraft:shovels", "#minecraft:hoes", "#minecraft:planks",
              "#minecraft:logs", "#minecraft:wool", "#minecraft:flowers",
              "#minecraft:arrows", "#minecraft:fishes", "#minecraft:dyes"]

# зачарования (id без префикса → с префиксом; сверен с реестром 26.2)
_ENCHANTS = ["sharpness", "smite", "bane_of_arthropods", "knockback",
             "looting", "fire_aspect", "sweeping_edge", "lunge",
             "efficiency", "fortune", "silk_touch", "unbreaking", "mending",
             "protection", "fire_protection", "blast_protection",
             "projectile_protection", "thorns", "respiration",
             "feather_falling", "depth_strider", "frost_walker",
             "swift_sneak", "soul_speed", "power", "punch", "flame",
             "infinity", "multishot", "quick_charge", "piercing",
             "impaling", "loyalty", "riptide", "channeling",
             "luck_of_the_sea", "lure", "density", "breach", "wind_burst",
             "vanishing_curse", "binding_curse"]

# зелья (реестр potion 26.2)
_POTIONS = ["water", "mundane", "thick", "awkward", "night_vision",
            "invisibility", "leaping", "fire_resistance", "swiftness",
            "slowness", "turtle_master", "water_breathing", "healing",
            "harming", "poison", "regeneration", "strength", "weakness",
            "luck", "slow_falling", "wind_charged", "weaving", "oozing",
            "infested"]

# environment-атрибуты с простыми значениями (EnvironmentAttributes.class;
# только bool-атрибуты — у float/цветовых кодеки сложнее)
_ENV_ATTRS_BOOL = [
    ("minecraft:gameplay/fast_lava", False),
    ("minecraft:gameplay/can_start_raid", True),
    ("minecraft:gameplay/water_evaporates", False),
    ("minecraft:gameplay/respawn_anchor_works", True),
    ("minecraft:gameplay/nether_portal_spawns_piglin", False),
    ("minecraft:audio/firefly_bush_sounds", True),
    ("minecraft:gameplay/increased_fire_burnout", False),
]

# NBT для entity/nbt и item custom_data (простые, заведомо валидные)
_NBT_TEMPLATES = [
    {"Health": 20.0},
    {"OnGround": True},
    {"Invulnerable": False},
    {"Fire": -1},
    {"PortalCooldown": 0},
    {"CustomNameVisible": True},
    {"Silent": False},
    {"Tags": ["marked"]},
    {"AngerTime": 0},
    {"InLove": 0},
]

# блок-состояния для block_state_property (свойства существуют у блоков)
_BLOCK_STATES = {
    "minecraft:beehive": {"honey_level": ["1", "3", "5"]},
    "minecraft:bee_nest": {"honey_level": ["2", "5"]},
    "minecraft:redstone_lamp": {"lit": ["true"]},
    "minecraft:campfire": {"lit": ["true", "false"]},
    "minecraft:respawn_anchor": {"charges": ["1", "2", "3", "4"]},
    "minecraft:composter": {"level": ["3", "6", "8"]},
    # 26.2: пустой minecraft:cauldron БЕЗ свойств (вариант ""), уровни
    # воды — у отдельного блока water_cauldron (level 1-3; сервер:
    # «Block cauldron has no property level» — поймано на реальном логе)
    "minecraft:water_cauldron": {"level": ["1", "2", "3"]},
    "minecraft:farmland": {"moisture": ["1", "7"]},
    "minecraft:candle": {"lit": ["true"]},
    "minecraft:lantern": {"hanging": ["true", "false"]},
}

# команды для командных блоков не трогаем; scoreboard-объективы произвольны
_SCORE_OBJECTIVES = ["level", "points", "kills", "deaths", "coins",
                     "score", "kills_total", "custom_count"]

_GAMEMODES = ["survival", "creative", "adventure", "spectator"]

_TEAMS = ["red", "blue", "green", "yellow", "aqua", "white"]

# максимальная глубина вложенности условий/под-предикатов
_MAX_DEPTH = 3


# ---------------------------------------------------------------------------
# Мелкие помощники
# ---------------------------------------------------------------------------

def _weighted(rng, pairs):
    """Взвешенный выбор: pairs = [(значение, вес), ...]."""
    return rng.choices([p[0] for p in pairs],
                       weights=[p[1] for p in pairs])[0]


def _ints(rng, lo, hi):
    """IntRange: голое число | {"min"} | {"max"} | {"min","max"}."""
    r = rng.random()
    if r < 0.30:
        return rng.randint(lo, hi)
    a = rng.randint(lo, hi)
    b = rng.randint(a, hi)
    if r < 0.55:
        return {"min": a}
    if r < 0.80:
        return {"max": b}
    return {"min": a, "max": b}


def _doubles(rng, lo, hi):
    """Doubles-диапазон (для дистанций/скоростей)."""
    r = rng.random()
    a = round(rng.uniform(lo, hi), 2)
    if r < 0.25:
        return a
    b = round(rng.uniform(a, hi), 2)
    if r < 0.55:
        return {"min": a}
    if r < 0.80:
        return {"max": b}
    return {"min": a, "max": b}


def _num_provider(rng, lo, hi):
    """NumberProvider: constant | uniform | binomial."""
    r = rng.random()
    if r < 0.55:
        return {"type": "minecraft:uniform",
                "min": float(rng.randint(lo, hi)),
                "max": float(rng.randint(lo, hi + 2))}
    if r < 0.75:
        return {"type": "minecraft:binomial",
                "n": float(rng.randint(hi, hi * 3 + 1)),
                "p": round(rng.uniform(0.2, 0.8), 3)}
    return float(rng.randint(lo, hi))


def _holderset(rng, ids, tags):
    """HolderSet: одиночный id | «#тег» | список id."""
    r = rng.random()
    if r < 0.45:
        return rng.choice(ids)
    if r < 0.65 and tags:
        return rng.choice(tags)
    k = min(len(ids), rng.randint(2, 4))
    return rng.sample(ids, k)


def _lvl_value(rng):
    """LevelBasedValue для enchanted_chance (все 6 типов реестра)."""
    t = _weighted(rng, [("linear", 40), ("clamped", 15), ("fraction", 15),
                        ("levels_squared", 10), ("exponent", 10),
                        ("lookup", 10)])
    if t == "linear":
        return {"type": "minecraft:linear",
                "base": round(rng.uniform(0.0, 0.4), 3),
                "per_level_above_first": round(rng.uniform(0.0, 0.2), 3)}
    if t == "clamped":
        return {"type": "minecraft:clamped",
                "value": round(rng.uniform(0.0, 0.6), 3),
                "min": 0.0, "max": round(rng.uniform(0.5, 1.0), 3)}
    if t == "fraction":
        return {"type": "minecraft:fraction",
                "numerator": rng.randint(1, 5),
                "denominator": rng.randint(5, 10)}
    if t == "levels_squared":
        return {"type": "minecraft:levels_squared",
                "added": round(rng.uniform(0.0, 0.1), 3)}
    if t == "exponent":
        return {"type": "minecraft:exponent",
                "base": round(rng.uniform(1.0, 2.0), 2),
                "power": round(rng.uniform(0.5, 2.0), 2)}
    return {"type": "minecraft:lookup",
            "values": [round(rng.uniform(0.0, 1.0), 3)
                       for _ in range(rng.randint(2, 4))],
            "fallback": round(rng.uniform(0.0, 1.0), 3)}


def _predicate_count(rng):
    """Тяжёлый хвост: в среднем ~3, почти всегда 1-5, выбросы до 20."""
    r = rng.random()
    if r < 0.60:
        return rng.randint(1, 3)
    if r < 0.93:
        return rng.randint(1, 5)
    return int(round(math.exp(rng.uniform(math.log(6), math.log(20)))))


# ---------------------------------------------------------------------------
# Под-предикаты (значения полей условий)
# ---------------------------------------------------------------------------

def _location_predicate(rng, depth):
    """LocationPredicate 26.2: position/dimension/biomes/structures/
    block/fluid/light/can_see_sky/smokey (сверено javap)."""
    p = {}
    if rng.random() < 0.55:
        pos = {}
        for ax in ("x", "y", "z"):
            if rng.random() < 0.6:
                pos[ax] = _doubles(rng, -64.0 if ax == "y" else -1000.0,
                                   320.0 if ax == "y" else 1000.0)
        if pos:
            p["position"] = pos
    if rng.random() < 0.35:
        p["dimension"] = rng.choice(_DIMENSIONS)
    if rng.random() < 0.40:
        p["biomes"] = _holderset(rng, _BIOMES, _BIOME_TAGS)
    if rng.random() < 0.20:
        p["structures"] = [rng.choice(_STRUCTURES)
                           for _ in range(rng.randint(1, 2))]
    if rng.random() < 0.30:  # BlockPredicate: {blocks, state, nbt}
        b = {"blocks": _holderset(rng, _BLOCKS, [])}
        if rng.random() < 0.3:
            # StatePropertiesPredicate: значения — СТРОКИ (точное
            # значение либо {min/max} тоже со строками!)
            if rng.random() < 0.5:
                b["state"] = {"lit": rng.choice(["true", "false"])}
            else:
                b["state"] = {"level": rng.choice(
                    ["3", "6", "8", {"min": "1", "max": "7"}])}
        p["block"] = b
    if rng.random() < 0.20:  # FluidPredicate: {fluids, state}
        p["fluid"] = {"fluids": rng.sample(
            ["minecraft:water", "minecraft:lava"], rng.randint(1, 2))}
    if rng.random() < 0.30:  # LightPredicate: {light}
        p["light"] = {"light": _ints(rng, 0, 15)}
    if rng.random() < 0.25:
        p["can_see_sky"] = rng.random() < 0.6
    if rng.random() < 0.12:
        p["smokey"] = rng.random() < 0.7
    return p


def _item_predicate(rng, depth):
    """ItemPredicate 26.2: {items, count, components, predicates} —
    DataComponentMatchers ВЫПРЯМЛЕН в поля ItemPredicate (javap: кодек
    входит в group БЕЗ fieldOf): «components» = карта ТОЧНЫХ значений,
    «predicates» = карта {компонент: типизированный предикат} — РЯДОМ,
    не в вложенном объекте. id типизированных предикатов — реестр
    DataComponentPredicates: damage{damage,durability: Ints},
    enchantments/stored_enchantments: СПИСОК {enchantments, levels},
    potion_contents: HolderSet, custom_data: NBT, ..."""
    p = {}
    if rng.random() < 0.85:
        p["items"] = _holderset(rng, _ITEMS, _ITEM_TAGS)
    if rng.random() < 0.45:
        p["count"] = _ints(rng, 1, 16)
    # точные значения компонентов (поле «components»)
    exact = {}
    if rng.random() < 0.35:
        if rng.random() < 0.4:
            exact["minecraft:rarity"] = rng.choice(
                ["common", "uncommon", "rare", "epic"])
        if rng.random() < 0.3:
            exact["minecraft:max_stack_size"] = rng.randint(1, 16)
        if rng.random() < 0.3:
            exact["minecraft:enchantment_glint_override"] = \
                rng.random() < 0.7
        if rng.random() < 0.2:
            exact["minecraft:repair_cost"] = rng.randint(0, 8)
        if exact:
            p["components"] = exact
    # типизированные компонент-предикаты (поле «predicates»)
    preds = {}
    if rng.random() < 0.45:  # список {enchantments, levels}
        preds["minecraft:enchantments"] = [{
            "enchantments": _holderset(
                rng, ["minecraft:" + e for e in _ENCHANTS], []),
            "levels": _ints(rng, 1, 5)}]
    if rng.random() < 0.25:  # HolderSet зелий
        preds["minecraft:potion_contents"] = _holderset(
            rng, ["minecraft:" + x for x in _POTIONS], [])
    if rng.random() < 0.25:  # {damage, durability} — Ints-диапазоны!
        dp = {}
        if rng.random() < 0.7:
            dp["damage"] = _ints(rng, 0, 200)
        if not dp or rng.random() < 0.5:
            dp["durability"] = _ints(rng, 0, 1500)
        preds["minecraft:damage"] = dp
    if rng.random() < 0.20:  # голый NBT
        preds["minecraft:custom_data"] = rng.choice(_NBT_TEMPLATES)
    if preds:
        p["predicates"] = preds
    return p


def _entity_predicate(rng, depth):
    """EntityPredicate 26.2: КАРТА под-предикатов, ключи namespaced
    (dispatchedMap реестра entity_sub_predicate_type)."""
    ep = {}
    n = _weighted(rng, [(1, 45), (2, 32), (3, 15), (4, 8)])
    keys = []
    for _ in range(n):
        k = _weighted(rng, [
            ("minecraft:entity_type", 10), ("minecraft:flags", 10),
            ("minecraft:location", 6), ("minecraft:distance", 6),
            ("minecraft:movement", 3), ("minecraft:effects", 5),
            ("minecraft:nbt", 3), ("minecraft:equipment", 6),
            ("minecraft:periodic_tick", 2), ("minecraft:vehicle", 2),
            ("minecraft:passenger", 2), ("minecraft:targeted_entity", 2),
            ("minecraft:team", 2), ("minecraft:slots", 2),
            ("minecraft:components", 2), ("minecraft:entity_tags", 3),
            ("minecraft:stepping_on", 2),
            ("minecraft:movement_affected_by", 2),
            ("minecraft:type_specific/player", 4),
            ("minecraft:type_specific/lightning", 1),
            ("minecraft:type_specific/fishing_hook", 1),
            ("minecraft:type_specific/cube_mob", 1),
            ("minecraft:type_specific/raider", 1),
            ("minecraft:type_specific/sheep", 1)])
        if k not in keys:
            keys.append(k)
    for k in keys:
        if k == "minecraft:entity_type":
            ep[k] = _holderset(rng, _ENTITIES, _ENTITY_TAGS)
        elif k == "minecraft:flags":
            fl = {}
            for f in ("is_baby", "is_on_fire", "is_on_ground", "is_sneaking",
                      "is_sprinting", "is_swimming", "is_in_water",
                      "is_fall_flying"):
                if rng.random() < 0.22:
                    fl[f] = rng.random() < 0.5
            if fl:
                ep[k] = fl
        elif k in ("minecraft:location", "minecraft:stepping_on",
                   "minecraft:movement_affected_by"):
            ep[k] = _location_predicate(rng, depth + 1)
        elif k == "minecraft:distance":
            d = {}
            for f in ("x", "y", "z", "absolute", "horizontal"):
                if rng.random() < 0.55:
                    d[f] = _doubles(rng, 0.0, 256.0)
            ep[k] = d
        elif k == "minecraft:movement":
            d = {}
            for f in ("x", "y", "z", "speed", "vertical_speed",
                      "horizontal_speed", "fall_distance"):
                if rng.random() < 0.45:
                    d[f] = _doubles(rng, -10.0 if f in ("x", "y", "z")
                                    else 0.0, 20.0)
            ep[k] = d
        elif k == "minecraft:effects":
            eff = {}
            for _e in rng.sample(_EFFECTS, rng.randint(1, 3)):
                inst = {}
                if rng.random() < 0.7:
                    inst["amplifier"] = _ints(rng, 0, 4)
                if rng.random() < 0.7:
                    inst["duration"] = _ints(rng, 20, 1200)
                if rng.random() < 0.25:
                    inst["visible"] = rng.random() < 0.6
                if rng.random() < 0.25:
                    inst["ambient"] = rng.random() < 0.4
                eff["minecraft:" + _e] = inst
            ep[k] = eff
        elif k == "minecraft:nbt":
            ep[k] = rng.choice(_NBT_TEMPLATES)
        elif k == "minecraft:equipment":
            eq = {}
            for s in rng.sample(_EQ_SLOTS, rng.randint(1, 3)):
                eq[s] = _item_predicate(rng, depth + 1)
            ep[k] = eq
        elif k == "minecraft:periodic_tick":
            ep[k] = rng.randint(1, 100)
        elif k in ("minecraft:vehicle", "minecraft:passenger",
                   "minecraft:targeted_entity"):
            if depth < _MAX_DEPTH:
                ep[k] = _entity_predicate(rng, depth + 1)
        elif k == "minecraft:team":
            ep[k] = rng.choice(_TEAMS)
        elif k == "minecraft:slots":
            # EntitySlotsPredicate.CODEC = SlotsPredicate.CODEC.xmap(...)
            # — БЕЗ fieldOf: значение = голая карта {слот: ItemPredicate}
            sl = {}
            for s in rng.sample(_INV_SLOTS, rng.randint(1, 3)):
                sl[s] = _item_predicate(rng, depth + 1)
            if sl:
                ep[k] = sl
        elif k == "minecraft:components":
            # карта ТОЧНЫХ значений компонентов сущности
            # (DataComponentExactPredicate.CODEC, голая карта)
            ep[k] = {"minecraft:custom_name":
                     rng.choice(["Страж", "Гость", "Тень"])}
        elif k == "minecraft:entity_tags":
            # обычные строковые теги сущности (Entity.entityTags())
            t = {}
            if rng.random() < 0.7:
                t["all_of"] = rng.sample(_ENTITY_NBT_TAGS,
                                         rng.randint(1, 2))
            if rng.random() < 0.4:
                t["any_of"] = rng.sample(_ENTITY_NBT_TAGS, 2)
            if not t or rng.random() < 0.3:
                t["none_of"] = [rng.choice(_ENTITY_NBT_TAGS)]
            ep[k] = t
        elif k == "minecraft:type_specific/player":
            pl = {}
            if rng.random() < 0.6:
                pl["level"] = _ints(rng, 0, 100)
            if rng.random() < 0.4:
                pl["gamemode"] = [rng.choice(_GAMEMODES)]  # СПИСОК
            if rng.random() < 0.25:
                pl["food"] = {"level": _ints(rng, 0, 20),
                              "saturation": _doubles(rng, 0.0, 20.0)}
            if rng.random() < 0.25 and depth < _MAX_DEPTH:
                pl["looking_at"] = _entity_predicate(rng, depth + 1)
            if pl:
                ep[k] = pl
        elif k == "minecraft:type_specific/lightning":
            lt = {}
            if rng.random() < 0.7:
                lt["blocks_set_on_fire"] = _ints(rng, 0, 8)
            if rng.random() < 0.5 and depth < _MAX_DEPTH:
                lt["entity_struck"] = _entity_predicate(rng, depth + 1)
            if lt:
                ep[k] = lt
        elif k == "minecraft:type_specific/fishing_hook":
            ep[k] = {"in_open_water": rng.random() < 0.6}
        elif k == "minecraft:type_specific/cube_mob":
            ep[k] = {"size": _ints(rng, 1, 8)}
        elif k == "minecraft:type_specific/raider":
            ep[k] = {"has_raid": rng.random() < 0.5,
                     "is_captain": rng.random() < 0.3}
        elif k == "minecraft:type_specific/sheep":
            ep[k] = {"sheared": rng.random() < 0.5}
    return ep


def _damage_source_predicate(rng, depth):
    """DamageSourcePredicate: {tags, direct_entity, source_entity,
    is_direct} (javap). tags — СПИСОК TagPredicate-ОБЪЕКТОВ
    {"id": "#тег", "expected": bool} — НЕ голых строк!"""
    p = {}
    if rng.random() < 0.55:
        # TagPredicate {"id": <id БЕЗ решётки>, "expected": bool}
        # — id это ResourceLocation, «#» НЕ допускается!
        p["tags"] = [{"id": "minecraft:" + t,
                      "expected": rng.random() < 0.7}
                     for t in rng.sample(
                         ["is_fire", "is_projectile",
                          "is_explosion", "is_fall",
                          "is_magic", "bypasses_armor",
                          "is_drowning", "is_freezing"],
                         rng.randint(1, 2))]
    if rng.random() < 0.35 and depth < _MAX_DEPTH:
        p["direct_entity"] = _entity_predicate(rng, depth + 1)
    if rng.random() < 0.35 and depth < _MAX_DEPTH:
        p["source_entity"] = _entity_predicate(rng, depth + 1)
    if rng.random() < 0.30:
        p["is_direct"] = rng.random() < 0.5
    return p


# ---------------------------------------------------------------------------
# Условия (корни predicate-файлов)
# ---------------------------------------------------------------------------

def _leaf_condition(rng, depth):
    """Простое условие без ссылок на другие предикаты."""
    r = rng.random()
    if r < 0.24:
        return {"condition": "minecraft:random_chance",
                "chance": round(rng.uniform(0.05, 0.95), 3)}
    if r < 0.38:
        return {"condition": "minecraft:entity_properties",
                "entity": rng.choice(_ENTITY_TARGETS),
                "predicate": _entity_predicate(rng, depth + 1)}
    if r < 0.48:
        lc = {"condition": "minecraft:location_check",
              "predicate": _location_predicate(rng, depth + 1)}
        if rng.random() < 0.3:  # опциональные смещения позиции
            for ax in ("offsetX", "offsetY", "offsetZ"):
                if rng.random() < 0.5:
                    lc[ax] = rng.randint(-8, 8)
        return lc
    if r < 0.58:
        return {"condition": "minecraft:match_tool",
                "predicate": _item_predicate(rng, depth + 1)}
    if r < 0.64:
        return {"condition": "minecraft:weather_check",
                "raining": rng.random() < 0.6,
                "thundering": rng.random() < 0.4}
    if r < 0.70:
        # clock ОБЯЗАТЕЛЕН (TimeCheck.CODEC: value, clock, period);
        # реестр world_clock 26.2: overworld | the_end
        tc = {"condition": "minecraft:time_check",
              "value": _ints(rng, 0, 24000),
              "clock": rng.choice(["minecraft:overworld",
                                   "minecraft:the_end"])}
        if rng.random() < 0.5:
            tc["period"] = rng.choice([1000, 24000, 72000, 100000])
        return tc
    if r < 0.78:
        return {"condition": "minecraft:value_check",
                "value": _num_provider(rng, 0, 32),
                "range": _doubles(rng, 0.0, 64.0)}
    if r < 0.84:
        return {"condition": "minecraft:entity_scores",
                "entity": rng.choice(_ENTITY_TARGETS),
                "scores": {rng.choice(_SCORE_OBJECTIVES):
                           _ints(rng, 0, 100)
                           for _ in range(rng.randint(1, 2))}}
    if r < 0.88:
        return {"condition": "minecraft:damage_source_properties",
                "predicate": _damage_source_predicate(rng, depth + 1)}
    if r < 0.92:
        block, props = rng.choice(list(_BLOCK_STATES.items()))
        chosen = rng.sample(list(props), rng.randint(1, len(props)))
        return {"condition": "minecraft:block_state_property",
                "block": block,
                "properties": {k: rng.choice(props[k]) for k in chosen}}
    if r < 0.955:
        return {"condition": "minecraft:table_bonus",
                "enchantment": "minecraft:" + rng.choice(_ENCHANTS),
                "chances": [round(rng.uniform(0.0, 0.6), 3)
                            for _ in range(rng.randint(2, 5))]}
    if r < 0.985:
        return {"condition": "minecraft:random_chance_with_enchanted_bonus",
                "unenchanted_chance": round(rng.uniform(0.05, 0.5), 3),
                "enchanted_chance": _lvl_value(rng),
                "enchantment": "minecraft:" + rng.choice(_ENCHANTS)}
    return {"condition": "minecraft:environment_attribute_check",
            "attribute": rng.choice(_ENV_ATTRS_BOOL)[0],
            "value": rng.choice([True, False])}


def _condition(rng, depth=0, prior_ids=None):
    """Любое условие, включая композитные (inverted/any_of/all_of) и
    reference на ранее созданные предикаты. prior_ids — список id
    предикатов с МЕНЬШИМ номером (ссылки только «назад»)."""
    if depth >= _MAX_DEPTH:
        return _leaf_condition(rng, depth)
    r = rng.random()
    if r < 0.06 and prior_ids:
        return {"condition": "minecraft:reference", "name": rng.choice(prior_ids)}
    if r < 0.14:
        return {"condition": "minecraft:inverted",
                "term": _condition(rng, depth + 1)}
    if r < 0.20:
        return {"condition": "minecraft:any_of",
                "terms": [_leaf_condition(rng, depth + 1)
                          for _ in range(rng.randint(2, 3))]}
    if r < 0.25:
        return {"condition": "minecraft:all_of",
                "terms": [_leaf_condition(rng, depth + 1)
                          for _ in range(rng.randint(2, 3))]}
    if r < 0.26:  # «простые» условия без параметров контекста
        return {"condition": "minecraft:killed_by_player"}
    if r < 0.27:
        return {"condition": "minecraft:survives_explosion"}
    # NOTE: enchantment_active_check здесь НЕ генерим: ему нужен контекст-
    # параметр minecraft:enchantment_active, которого нет ни в standalone-
    # валидации реестра predicates, ни в обычных лут-контекстах — любой
    # файл с ним (даже вложенным) даёт WARN «Parameters ... are not
    # provided in this context». Только внутри enchantment-компонентов.
    return _leaf_condition(rng, depth)


# ---------------------------------------------------------------------------
# Публичная функция
# ---------------------------------------------------------------------------

def rand_predicates(rng, ns, name, count=None):
    """Случайные predicates измерения.

    rng    — random.Random (весь рандом только через него);
    ns     — namespace;
    name   — имя измерения (id: <ns>:<name>_predN);
    count  — сколько предикатов создать (None → тяжёлый хвост,
             в среднем ~3, выбросы до 20).

    Возвращает {"predicates": {"<ns>:<name>_predN": json, ...}}.
    Модуль ничего не пишет на диск."""
    if count is None:
        count = _predicate_count(rng)
    out = {}
    prior = []  # id уже созданных — для reference «назад»
    # БЕЗПАРАМЕТРИЧЕСКИЕ условия с interned-синглтоном (javap: INSTANCE-
    # поле есть только у ExplosionCondition/survives_explosion и
    # LootItemKilledByPlayerCondition/killed_by_player). Два файла пака,
    # чей КОРЕНЬ — такое условие, декодируются в один объект →
    # «Adding duplicate value ... to registry» и падает ВЕСЬ пак (тот же
    # капкан, что end_islands в density_function). Вложенные вхождения
    # безопасны — регистрируется только корень.
    _SINGLETONS = ("minecraft:survives_explosion",
                   "minecraft:killed_by_player")
    for i in range(count):
        pid = "%s:%s_pred%d" % (ns, name, i)
        if rng.random() < 0.06 and prior:
            # корень-массив: неявный all_of (AllOfCondition.INLINE_CODEC)
            root = [_leaf_condition(rng, 0)
                    for _ in range(rng.randint(2, 3))]
        else:
            root = _condition(rng, 0, prior)
            if isinstance(root, dict) and root.get("condition") in _SINGLETONS:
                # оборачиваем — any_of с одним term создаёт свежий инстанс
                root = {"condition": "minecraft:any_of", "terms": [root]}
        out[pid] = root
        prior.append(pid)
    return {"predicates": out}


# ---------------------------------------------------------------------------
# Самотест: воспроизводимость, 20+ seed, валидность id/структуры
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    import random

    seeds = list(range(1, 31))  # 30 seed
    total = 0
    per_seed = []
    for sd in seeds:
        r1 = random.Random(sd)
        r2 = random.Random(sd)
        res1 = rand_predicates(r1, "rndim", "dim%d" % sd)
        res2 = rand_predicates(r2, "rndim", "dim%d" % sd)
        # воспроизводимость
        assert json.dumps(res1, sort_keys=True) == \
            json.dumps(res2, sort_keys=True), "невоспроизводимо: seed %d" % sd
        tbl = res1["predicates"]
        total += len(tbl)
        per_seed.append(len(tbl))
        for pid, js in tbl.items():
            # id-формат: ns:name_predN, [a-z0-9_/] в имени файла
            ns_, rest = pid.split(":", 1)
            assert ns_ == "rndim" and rest.startswith("dim%d_pred" % sd)
            assert all(c in "abcdefghijklmnopqrstuvwxyz0123456789_/"
                       for c in rest.replace(":", "")), pid
            # сериализуемость и наличие ключа "condition" (или массив)
            json.dumps(js)
            if isinstance(js, dict):
                assert "condition" in js and js["condition"].startswith(
                    "minecraft:"), (pid, js)
                # reference ссылается только «назад»
                if js.get("condition") == "minecraft:reference":
                    ref = js["name"]
                    my_n = int(pid.rsplit("pred", 1)[1])
                    ref_n = int(ref.rsplit("pred", 1)[1])
                    assert ref_n < my_n, (pid, ref)
            else:
                assert isinstance(js, list) and all(
                    isinstance(c, dict) and "condition" in c
                    for c in js), pid
    print("OK: %d predicates на %d seed (в среднем %.2f, min %d, max %d)"
          % (total, len(seeds), total / float(len(seeds)),
             min(per_seed), max(per_seed)))
    # пример-выписка для наглядности
    demo = rand_predicates(random.Random(777), "rndim", "demo", 3)
    for pid, js in demo["predicates"].items():
        print(" ", pid, "=", json.dumps(js, ensure_ascii=False)[:150])
