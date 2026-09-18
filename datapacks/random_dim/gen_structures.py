#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_structures.py — генератор случайных КАРВЕРОВ и СТРУКТУР для Minecraft 26.2
(pack_format 107). Синтаксис каждого JSON и формат .nbt-шаблонов сверён с
ванильным jar-файлом 26.2 (minecraft-26.2-client.jar): байткодом классов
кодеков, ванильными worldgen/structure/*.json и бинарными NBT-шаблонами
из data/minecraft/structure/ (DataVersion 4903).

Модуль импортируется главным скриптом (generate_dimension.py) и сам ничего
не пишет на диск — только ВОЗВРАЩАЕТ dict'ы {id: json} / {путь: текст}:

    rand_carvers(rng, ns, name, min_y, max_y)
        -> {carver_id: json}          # писать в data/<ns>/worldgen/configured_carver/<имя>.json

    rand_structures(rng, ns, name, min_y, max_y, biome_ids,
                    count=None, loot_alloc=None)
        -> {
            "structures":       {id: json},   # data/<ns>/worldgen/structure/
            "structure_sets":   {id: json},   # data/<ns>/worldgen/structure_set/
            "template_pools":   {id: json},   # data/<ns>/worldgen/template_pool/<путь>.json
            "processor_lists":  {id: json},   # data/<ns>/worldgen/processor_list/
            "biome_tags":       {tag: json},  # data/<ns>/tags/worldgen/biome/<tag>.json
                                              # (tag вида "has_structure/<имя>")
            "nbt_files":        {ключ: bytes} # data/<ns>/structure/<ключ>.nbt —
                                              # СВОИ шаблоны (gzip-NBT) с особыми мобами
           }
    # loot_alloc — общий на измерение счётчик LootSlots (см. класс ниже):
    # каждый сундук/волт/моб шаблона занимает СВОЙ уникальный слот
    # лут-таблицы "<ns>:<name>_lootN"; сам слот занятых этим вызовом
    # возвращается в result["loot_slots"].

Формат 26.2 (проверено по jar):
  configured_carver: {"type": "minecraft:cave|canyon|nether_cave", "config": {
      probability (float), y (HeightProvider uniform по двум VerticalAnchor:
      {absolute} | {above_bottom} | {below_top}),
      yScale (число ИЛИ uniform/trapezoid FloatProvider), lava_level (VerticalAnchor),
      debug_settings (опционально: air_state/barrier_state/water_state/lava_state),
      replaceable (HolderSet: тег "#..." ИЛИ список ID блоков — подтверждено
      байткодом: RegistryCodecs.homogeneousList(Registries.BLOCK)),
      cave/nether_cave: floor_level, horizontal_radius_multiplier,
      vertical_radius_multiplier (число ИЛИ uniform FloatProvider),
      canyon: vertical_rotation (FloatProvider) + shape {distance_factor,
      horizontal_radius_factor, thickness (trapezoid), vertical_radius_default_factor,
      vertical_radius_center_factor, width_smoothness} }}
  structure: 15 из 16 типов 26.2 (реестр сверен по data/minecraft/worldgen/
  structure/*.json и классам structures/*.class). ocean_monument НЕ
  генерируем: findGenerationPoint требует биомы ванильного тега
  #minecraft:required_ocean_monument_surrounding (радиус 29), своих биомов
  там нет — monument ВСЕГДА empty (аудит находимости):
    jigsaw, mineshaft, woodland_mansion, desert_pyramid,
    jungle_temple, igloo, swamp_hut, stronghold, buried_treasure, shipwreck,
    ocean_ruin, end_city, fortress, nether_fossil, ruined_portal.
    Общий settingsCodec (Structure$StructureSettings): biomes (обяз.),
    spawn_overrides (обяз.), step (обяз.), terrain_adaptation (опц.,
    TerrainAdjustment: none|bury|beard_thin|beard_box|encapsulate).
    ПЛЮС ФОРКИ ванильных jigsaw-структур (~35% структур, VANILLA_JIGSAW_FORKS
    ниже): type jigsaw со start_pool = ВАНИЛЬНЫЙ пул — структура
    собирается ЦЕЛИКОМ из ванильного дерева кусков (5 деревень,
    pillager_outpost, bastion_remnant, ancient_city, trail_ruins,
    trial_chambers — все 10 jigsaw-структур jar 26.2), параметры
    случайные (size 4-20, max_distance_from_center, terrain_adaptation,
    step, start_height, spawn_overrides, biomes — наши), а
    use_expansion_hack / start_jigsaw_name / pool_aliases /
    dimension_padding / liquid_settings копируются из ванили.
    Доп. поля по типам (из байткода кодеков):
      mineshaft:     mineshaft_type = normal|mesa
      ocean_ruin:    biome_temp = cold|warm; large_probability, cluster_probability
                     (floatRange 0..1)
      nether_fossil: height (HeightProvider)
      shipwreck:     is_beached (bool)
      ruined_portal: setups — непустой список {air_pocket_probability,
                     can_be_cold, mossiness, overgrown, placement
                     (on_land_surface|partly_buried|underground|in_mountain|
                      in_nether|on_ocean_floor), replace_with_blackstone,
                     vines, weight}
      остальные (buried_treasure/desert_pyramid/end_city/fortress/igloo/
      jungle_temple/woodland_mansion/stronghold/swamp_hut):
      только settingsCodec.
  structure_set: structures[{structure, weight}], placement:
    random_spread {spacing, separation, salt, опц. spread_type/frequency/
      frequency_reduction_method/locate_offset} или
    concentric_rings (как strongholds; ~10% сетов ИЗ ОДНОЙ структуры;
    preferred_biomes = биомы самой структуры) {distance intRange(0,1023),
      spread intRange(0,1023), count intRange(1,4095), preferred_biomes
      (HolderSet биомов), salt}.
  template_pool: elements[{element{element_type, location, processors,
      projection}, weight}], fallback. location — путь шаблона БЕЗ расширения.
      Свои пулы (свои jigsaw-данжи) содержат ТОЛЬКО свои .nbt из
      data/<ns>/structure/ — отдельные ванильные куски НЕ подмешиваются
      (решение юзера: «один дом а не целиком деревня — это кринж»);
      ванильский контент приходит ЦЕЛИКОМ через форки (ванильный
      start_pool = целое ванильное дерево кусков, а не его кусок).
  processor_list: processors[{processor_type: rule|block_rot|protected_blocks|
      capped}]. Старых block_replace/block_swap/guarded в 26.2 НЕТ — их роль
      играет rule (input_predicate → output_state).

Шаблоны построек (со specials-мобами и сундуками) — БИНАРНЫЕ .nbt
(gzip-NBT), как у ванильных шаблонов из jar. Формат корня сверен по
StructureTemplate.class и ванильным .nbt (DataVersion 4903):
    {size:[I,I,I], entities:[{pos:[D,D,D], blockPos:[I,I,I], nbt:{...}}],
     blocks:[{pos:[I,I,I], state:<индекс палитры>, nbt:{...}}],
     palette:[{Name:"...", Properties:{...}}], DataVersion:4903}
ВАЖНО (проверено на реальном сервере 26.2 + байткод server-26.2.jar):
текстовые .snbt-шаблоны ОБЫЧНЫЙ сервер НЕ читает — StructureTemplateManager
строит ResourceManagerTemplateSource с RESOURCE_STRUCTURE_LISTER =
FileToIdConverter("structure", ".nbt") и readStructure() =
NbtIo.readCompressed (gzip). Текстовый листер ".snbt" используется ТОЛЬКО
источником gametest-каталога (DirectoryTemplateSource c флагом isText=true).
Поэтому rand_structures возвращает "nbt_files": {<путь без расширения>:
<bytes gzip-NBT>}; файл data/<ns>/structure/<путь>.nbt доступен из пулов
как "<ns>:<путь>" и по place template.

Точные NBT-имена тегов (сверены по байткоду 26.2 + ванильным шаблонам):
  сундук/бочка:  nbt блока {id:"minecraft:chest", LootTable:"ns:path"}
                 (RandomizableContainer.tryLoadLootTable читает "LootTable";
                 seed "LootTableSeed" не обязателен — StructureTemplate сам
                 подставляет случайный при установке)
  моб:           id, CustomName (NBT-компонент {text,color,italic} —
                 ComponentSerialization.CODEC), CustomNameVisible, Health
                 (float), attributes:[{id:"minecraft:max_health", base:D}]
                 (AttributeInstance$Packed), equipment:{mainhand|offhand|head|
                 chest|legs|feet:{id,count,components}} (EntityEquipment.CODEC =
                 unboundedMap(EquipmentSlot, ItemStack); старых HandItems/
                 ArmorItems в 26.2 НЕТ — их конвертирует EquipmentFormatFix),
                 drop_chances:{<слот>:F} (DropChances.CODEC), DeathLootTable
                 (Mob), PersistenceRequired, Glowing, Fire, CanPickUpLoot,
                 LeftHanded, Silent, Rotation. NoAI/Invulnerable НЕ
                 генерируются — мобы живут своей жизнью и уязвимы.
  предмет:       {id:"minecraft:diamond_sword", count:1,
                 components:{"minecraft:enchantments":{"minecraft:sharpness":5}
                 (ItemEnchantments.CODEC = прямой map, без обёртки "levels"),
                 "minecraft:custom_name":{text:...,color:...}}}

Привязка к измерению: structure_set — ГЛОБАЛЬНЫЙ реестр, поля "dimension" нет
ни в structure_set, ни в dimension/world_preset. Структура появляется в
тех измерениях, где биом-сорс содержит биомы из её поля "biomes" — поэтому
структуры ссылаются на биомы ТОЛЬКО этого измерения (список ID или свой тег
#ns:has_structure/... из biome_tags).

АУДИТ КРОСС-ЧАНКОВЫХ ЧТЕНИЙ (26.2, байткод server/client jar, сент. 2026):
структуры НЕ способны читать террейн дальше ±1 чанка от генерируемого —
и это не конвертируется в «unsafe terrain read»:
  * StructureStart.placeInChunk вызывает postProcess ТОЛЬКО для кусков,
    пересекающих бокс текущего чанка; TemplateStructurePiece.postProcess
    ставит placeSettings.setBoundingBox(бокс чанка) — StructureTemplate
    пропускает блоки/сущности вне бокса → все записи обрезаны по чанку;
  * единственный выход за пределы чанка — lambda$updateShapeAtEdge$0
    (StructureTemplate): после установки читает СОСЕДНИЙ блок у края
    бокса (getBlockState на 1 блок наружу) и при изменении формы пишет
    туда setBlock — чебышёвское расстояние 1 <= writeRadius(FEATURES)=1
    (ChunkPyramid: step FEATURES = STRUCTURE_STARTS@8 + CARVERS@1 +
    blockStateWriteRadius(1)) → легально, варнинга нет;
  * terrain_adaptation (Beardifier) — чистая математика плотности, блочных
    чтений не делает; инflate бокса на +12 учтён лимитом md+12<=128.
Проверенные ограничения, которые генератор обязан соблюдать (см. ниже):
  1) jigsaw: verifyRange — max_distance_from_center + 12 <= 128 при
     terrain_adaptation != none (иначе датапак не грузится ЦЕЛИКОМ);
  1а) jigsaw: size — Codec.intRange(0, 20) (байткод JigsawStructure.CODEC,
      сконстантён iconst_0+bipush 20): «40 шагов» генерации НЕВОЗМОЖНЫ,
      потолок гигантского форка — 20; max_distance_from_center держим
      не ниже 4*size — иначе дальние куски дерева молча отбрасываются
      (обрубанная деревня);
  2) jigsaw: use_expansion_hack=true → YSpan дочернего куска <= 16,
     иначе кусок молча отбрасывается (дыры в данже); поэтому у ФОРКОВ
     hack всегда ванильный: включение его у бастиона/древнего города/
     trial chambers (куски выше 16) продырявит структуру, выключение у
     деревень меняет ванильное поведение — копируем как есть;
  3) random_spread: separation < spacing;
  4) стартовые высоты оставляют запас до потолка мира: jigsaw
     start_height <= max_y - 34 (куски пулов до ~24 блоков + запас 10;
     ниже кровли — roof_bottom - 34), nether_fossil height <= max_y - 30;
     прочие высокие не-jigsaw типы (mansion/fortress/end_city, до ~30
     блоков) высоту в JSON НЕ принимают (только settingsCodec) — их
     вертикалью управляет код относительно рельефа, поэтому их лишь
     допускают в высокие миры (Y_GATED_TYPES: max_y >= 100).
Аудит данных (сент. 2026: 253 jigsaw-структуры / 1050 .nbt / 123 с hack):
нарушений нет; собственные куски <= 16x24x16.

Мобы с NBT (CustomName/Health/attributes/equipment/DeathLootTable) невозможны
в биом-спавнерах (SpawnerData = type/weight/minCount/maxCount), но возможны
в шаблонах .nbt — поэтому «особые» мобы генерируются только здесь.
"""

import gzip
import json
import math
import random
import struct

# ---------------------------------------------------------------------------
# Константы, подтверждённые ванильным jar 26.2
# ---------------------------------------------------------------------------

# Ванильные configured_carver из data/minecraft/worldgen/configured_carver/
CARVER_TYPES = ["minecraft:cave", "minecraft:cave", "minecraft:cave",
                "minecraft:canyon", "minecraft:canyon", "minecraft:nether_cave"]

CARVER_REPLACEABLE_TAGS = {
    "minecraft:nether_cave": "#minecraft:nether_carver_replaceables",
    # cave/canyon в ванили используют overworld-тег
    "minecraft:cave": "#minecraft:overworld_carver_replaceables",
    "minecraft:canyon": "#minecraft:overworld_carver_replaceables",
}

# Шаги генерации, которые реально используют ванильные structure 26.2
STRUCTURE_STEPS = ["underground_structures", "surface_structures",
                   "underground_decoration"]

# Значения terrain_adaptation (enum TerrainAdjustment, байткод подтверждён:
# none, bury, beard_thin, beard_box, encapsulate)
TERRAIN_ADAPTATIONS = ["none", "beard_thin", "beard_box", "bury", "encapsulate"]
# Веса terrain_adaptation (порядок = TERRAIN_ADAPTATIONS): beard_thin/
# beard_box «доращивают» землю под структурой — постройки стоят на земле,
# а не висят в воздухе, поэтому бороды суммарно 45%; bury/encapsulate
# прячут структуру целиком под землю/в капсулу — суммарно лишь 10%
# (равновероятный choice давал 40% bury+encapsulate — аудит находимости)
TERRAIN_ADAPTATION_WEIGHTS = [45, 30, 15, 5, 5]

# 15 из 16 типов структур 26.2 (data/minecraft/worldgen/structure/*.json).
# jigsaw — отдельно (ему нужен start_pool); остальные генерируют куски в
# коде. ocean_monument исключён: findGenerationPoint требует, чтобы ВСЕ
# биомы в радиусе 29 были из ванильного тега
# minecraft:required_ocean_monument_surrounding — биомы случайного
# измерения в нём отсутствуют, monument ВСЕГДА возвращает empty.
JIGSAW_TYPE = "minecraft:jigsaw"
NON_JIGSAW_TYPES = [
    "minecraft:buried_treasure", "minecraft:desert_pyramid",
    "minecraft:end_city", "minecraft:fortress", "minecraft:igloo",
    "minecraft:jungle_temple", "minecraft:woodland_mansion",
    "minecraft:stronghold", "minecraft:swamp_hut",
    # типы с собственными полями кодека (см. _rand_structure_json):
    "minecraft:mineshaft", "minecraft:ocean_ruin", "minecraft:nether_fossil",
    "minecraft:shipwreck", "minecraft:ruined_portal",
]
# Типы, которым нужна АБСОЛЮТНАЯ высота: findGenerationPoint требует
# getLowestY(бокс 5x5 чанков) >= 60 — при max_y < 100 рельеф туда не
# дотягивается, структуры ВСЕГДА empty (аудит находимости), поэтому
# выдаём их только мирам с max_y >= 100. Про высоту сверху: эти типы
# (~30 блоков кусков) принимают в JSON ТОЛЬКО settingsCodec — поля
# start_height/height у них нет, вертикаль задаёт код; единственный
# не-jigsaw тип с полем высоты — nether_fossil (height, см.
# _rand_structure_json: hi_y = max_y - 30).
Y_GATED_TYPES = ("minecraft:woodland_mansion", "minecraft:end_city")

# Вертикальные размещения ruined_portal (RuinedPortalPiece$VerticalPlacement,
# подтверждены ванильными ruined_portal*.json)
RUINED_PORTAL_PLACEMENTS = ["on_land_surface", "partly_buried", "underground",
                            "in_mountain", "in_nether", "on_ocean_floor"]

# Блок-теги для predicate_type tag_match (все есть в data/minecraft/tags/block/)
TAG_MATCH_TAGS = ["minecraft:doors", "minecraft:logs", "minecraft:planks",
                  "minecraft:wool", "minecraft:trail_ruins_replaceable"]

# Теги для protected_blocks: features_cannot_replace (как в ванильных
# процессорах ancient_city) + проверенные TAG_MATCH_TAGS
_PROTECTED_TAG_CHOICES = ["#minecraft:features_cannot_replace"] \
    + ["#%s" % t for t in TAG_MATCH_TAGS]

# Блоки, часто встречающиеся в ванильных nbt-шаблонах (входы rule-процессоров)
TEMPLATE_BLOCKS = [
    "minecraft:cobblestone", "minecraft:mossy_cobblestone",
    "minecraft:stone_bricks", "minecraft:cracked_stone_bricks",
    "minecraft:oak_planks", "minecraft:oak_log", "minecraft:oak_stairs",
    "minecraft:glass_pane", "minecraft:dirt_path", "minecraft:grass_block",
    "minecraft:dirt", "minecraft:gravel", "minecraft:blackstone",
    "minecraft:polished_blackstone_bricks", "minecraft:sandstone",
    "minecraft:cut_sandstone", "minecraft:snow_block", "minecraft:wheat",
    "minecraft:torch", "minecraft:wall_torch",
]

# DataVersion 26.2 (version.json: world_version = 4903)
DATA_VERSION = 4903

# ---------------------------------------------------------------------------
# Мобы для особых сущностей в .nbt-шаблонах. Список собран из
# assets/minecraft/lang/en_us.json (entity.minecraft.*) с фильтрацией
# не-Mob сущностей: лодки/плоты, вагонетки, снаряды и частицы-облака,
# display-сущности, рамки/картины/лееры, item/falling_block/tnt/end_crystal,
# player, armor_stand/mannequin (LivingEntity, но не Mob), боссы
# (ender_dragon/wither), killer_bunny (это вариант кролика, а НЕ отдельный
# entity_type — сервер отвечает "Unknown registry key"), а также
# суффиксные ключи с точками (villager.armorer, tropical_fish.type.*, ...).
STRUCTURE_MOBS = [
    "allay", "armadillo", "axolotl", "bat", "bee", "blaze", "bogged",
    "breeze", "camel", "camel_husk", "cat", "cave_spider", "chicken",
    "copper_golem", "cow", "creaking", "creeper", "dolphin", "donkey",
    "drowned", "elder_guardian", "enderman", "endermite", "evoker", "fox",
    "frog", "ghast", "giant", "glow_squid", "goat", "guardian", "happy_ghast",
    "hoglin", "horse", "husk", "illusioner", "iron_golem",
    "llama", "magma_cube", "mooshroom", "mule", "nautilus", "ocelot", "panda",
    "parched", "parrot", "phantom", "pig", "piglin", "piglin_brute",
    "pillager", "polar_bear", "pufferfish", "rabbit", "ravager", "salmon",
    "sheep", "shulker", "silverfish", "skeleton", "skeleton_horse", "slime",
    "sniffer", "snow_golem", "spider", "squid", "stray", "strider",
    "sulfur_cube", "tadpole", "trader_llama", "tropical_fish", "turtle",
    "vex", "villager", "vindicator", "wandering_trader", "warden", "witch",
    "wither_skeleton", "wolf", "zoglin", "zombie", "zombie_horse",
    "zombie_nautilus", "zombie_villager", "zombified_piglin",
]

# Мобы, у которых в jar есть лут-таблица entities/<имя> — fallback для
# DeathLootTable, когда счётчик слотов не передан (killer_bunny использует rabbit)
MOB_LOOT_TABLES = {
    "allay", "armadillo", "axolotl", "bat", "bee", "blaze", "bogged",
    "breeze", "camel", "camel_husk", "cat", "cave_spider", "chicken",
    "copper_golem", "cow", "creaking", "creeper", "dolphin", "donkey",
    "drowned", "elder_guardian", "enderman", "endermite", "evoker", "fox",
    "frog", "ghast", "giant", "glow_squid", "goat", "guardian", "happy_ghast",
    "hoglin", "horse", "husk", "illusioner", "iron_golem", "llama",
    "magma_cube", "mooshroom", "mule", "nautilus", "ocelot", "panda",
    "parched", "parrot", "phantom", "pig", "piglin", "piglin_brute",
    "pillager", "polar_bear", "pufferfish", "rabbit", "ravager", "salmon",
    "sheep", "shulker", "silverfish", "skeleton", "skeleton_horse", "slime",
    "sniffer", "snow_golem", "spider", "squid", "stray", "strider",
    "sulfur_cube", "tadpole", "trader_llama", "tropical_fish", "turtle",
    "vex", "villager", "vindicator", "wandering_trader", "warden", "witch",
    "wither_skeleton", "wolf", "zoglin", "zombie", "zombie_horse",
    "zombie_nautilus", "zombie_villager", "zombified_piglin",
}

# Ванильные chest-лут-таблицы (data/minecraft/loot_table/chests/) — fallback
# для сундуков, когда счётчик слотов не передан (loot_alloc=None)
VANILLA_CHEST_LOOT = [
    "minecraft:chests/simple_dungeon", "minecraft:chests/abandoned_mineshaft",
    "minecraft:chests/stronghold_corridor", "minecraft:chests/stronghold_crossing",
    "minecraft:chests/stronghold_library", "minecraft:chests/desert_pyramid",
    "minecraft:chests/jungle_temple", "minecraft:chests/igloo_chest",
    "minecraft:chests/woodland_mansion", "minecraft:chests/buried_treasure",
    "minecraft:chests/shipwreck_supply", "minecraft:chests/shipwreck_treasure",
    "minecraft:chests/shipwreck_map", "minecraft:chests/underwater_ruin_big",
    "minecraft:chests/underwater_ruin_small", "minecraft:chests/ancient_city",
    "minecraft:chests/ancient_city_ice_box", "minecraft:chests/bastion_bridge",
    "minecraft:chests/bastion_hoglin_stable", "minecraft:chests/bastion_other",
    "minecraft:chests/bastion_treasure", "minecraft:chests/nether_bridge",
    "minecraft:chests/pillager_outpost", "minecraft:chests/ruined_portal",
    "minecraft:chests/end_city_treasure",
    "minecraft:chests/village/village_plains_house",
    "minecraft:chests/village/village_desert_house",
    "minecraft:chests/village/village_taiga_house",
]

# Полный реестр entity_type 26.2 — сверен по jar (constant pool
# net/minecraft/world/entity/EntityTypeIds.class: все snake_case id;
# шумовые строки create/name/this исключены; creaking_transient и
# falling_block_type есть только в lang, в реестре отсутствуют — НЕ
# использовать). Нужен самотесту: id любой сущности спавнера обязан
# здесь присутствовать (суммон несуществующего id = "Unknown registry
# key" и молча мёртвый спавнер).
ENTITY_TYPE_IDS = frozenset(
    "minecraft:" + e for e in [
        "acacia_boat", "acacia_chest_boat", "allay", "area_effect_cloud",
        "armadillo", "armor_stand", "arrow", "axolotl", "bamboo_chest_raft",
        "bamboo_raft", "bat", "bee", "birch_boat", "birch_chest_boat",
        "blaze", "block_display", "bogged", "breeze", "breeze_wind_charge",
        "camel", "camel_husk", "cat", "cave_spider", "cherry_boat",
        "cherry_chest_boat", "chest_minecart", "chicken", "cod",
        "command_block_minecart", "copper_golem", "cow", "creaking",
        "creeper", "dark_oak_boat", "dark_oak_chest_boat", "dolphin",
        "donkey", "dragon_fireball", "drowned", "egg", "elder_guardian",
        "end_crystal", "ender_dragon", "ender_pearl", "enderman",
        "endermite", "evoker", "evoker_fangs", "experience_bottle",
        "experience_orb", "eye_of_ender", "falling_block", "fireball",
        "firework_rocket", "fishing_bobber", "fox", "frog",
        "furnace_minecart", "ghast", "giant", "glow_item_frame",
        "glow_squid", "goat", "guardian", "happy_ghast", "hoglin",
        "hopper_minecart", "horse", "husk", "illusioner", "interaction",
        "iron_golem", "item", "item_display", "item_frame", "jungle_boat",
        "jungle_chest_boat", "leash_knot", "lightning_bolt",
        "lingering_potion", "llama", "llama_spit", "magma_cube",
        "mangrove_boat", "mangrove_chest_boat", "mannequin", "marker",
        "minecart", "mooshroom", "mule", "nautilus", "oak_boat",
        "oak_chest_boat", "ocelot", "ominous_item_spawner", "painting",
        "pale_oak_boat", "pale_oak_chest_boat", "panda", "parched",
        "parrot", "phantom", "pig", "piglin", "piglin_brute", "pillager",
        "player", "polar_bear", "pufferfish", "rabbit", "ravager",
        "salmon", "sheep", "shulker", "shulker_bullet", "silverfish",
        "skeleton", "skeleton_horse", "slime", "small_fireball",
        "sniffer", "snow_golem", "snowball", "spawner_minecart",
        "spectral_arrow", "spider", "splash_potion", "spruce_boat",
        "spruce_chest_boat", "squid", "stray", "strider", "sulfur_cube",
        "tadpole", "text_display", "tnt", "tnt_minecart", "trader_llama",
        "trident", "tropical_fish", "turtle", "vex", "villager",
        "vindicator", "wandering_trader", "warden", "wind_charge",
        "witch", "wither", "wither_skeleton", "wither_skull", "wolf",
        "zoglin", "zombie", "zombie_horse", "zombie_nautilus",
        "zombie_villager", "zombified_piglin",
    ])

# Спектр сущностей спавнеров данжей (решение юзера: «спавнят ВСЕ
# сущности, не только мобов, даже предметы»). Мобы — 85% пула,
# спец-типы — 15%; внутри спец-типов веса ниже (item — самый частый,
# wind_charge — редкий). Формат NBT каждого типа сверен javap'ом
# соответствующих классов jar 26.2 (см. докстринги генераторов).
# ВНИМАНИЕ на имена реестра: отдельного boat/chest_boat НЕТ (только
# по породам дерева: oak_boat/oak_chest_boat/bamboo_raft/...),
# вагонетка с сундуком — chest_minecart (НЕ minecart_chest).
SPAWNER_MOB_SHARE = 0.85          # суммарная доля обычных мобов
SPAWNER_SPECIAL_WEIGHTS = {       # веса внутри оставшихся 15%
    "item": 3.0,                 # Item {id, count, components}
    "armor_stand": 2.0,          # equipment + ShowArms/Small/...
    "tnt": 2.0,                  # fuse (short, 20-200)
    "falling_block": 2.0,        # BlockState из палитры измерения
    "experience_orb": 2.0,       # Value (short, 1-50)
    "chest_boat": 1.5,           # Items 3-6 (по породе дерева)
    "chest_minecart": 1.5,       # Items 3-6
    "item_frame": 1.5,           # Item {...} + ItemRotation
    "glow_item_frame": 1.5,
    "firework_rocket": 1.5,      # FireworksItem с зарядами
    "area_effect_cloud": 1.5,    # Radius/Duration/potion_contents
    "boat": 1.0,                 # лёгкий NBT
    "minecart": 1.0,             # лёгкий NBT
    "wind_charge": 0.5,          # редкий
}

# породы лодок (реестр: <wood>_boat/<wood>_chest_boat, бамбук — рафт)
_BOAT_WOODS = ["acacia", "bamboo", "birch", "cherry", "dark_oak",
               "jungle", "mangrove", "oak", "pale_oak", "spruce"]

# Предметы для сущности item / рамок / контейнеров спавнеров.
# Идентификаторы сверены по реестру предметов 26.2 (assets/minecraft/
# items/*.json в jar, 1537 шт.). Зачарованное оружие/броня/именное —
# через _rand_item_stack (обший генератор снаряжения мобов).
SPAWNER_RARE_ITEMS = [          # (id, min, max) — редкие материалы/
    ("minecraft:diamond", 1, 3),            # артефакты; max учёл
    ("minecraft:emerald", 1, 3),            # max_stack_size предмета
    ("minecraft:gold_ingot", 1, 3),         # (музык. диски/тотемы/
    ("minecraft:iron_ingot", 2, 6),         # рога/книги — ровно 1)
    ("minecraft:copper_ingot", 2, 6),
    ("minecraft:lapis_lazuli", 2, 6),
    ("minecraft:amethyst_shard", 2, 6),
    ("minecraft:quartz", 2, 6),
    ("minecraft:coal", 2, 8),
    ("minecraft:netherite_scrap", 1, 2),
    ("minecraft:ancient_debris", 1, 2),
    ("minecraft:echo_shard", 1, 1),
    ("minecraft:ender_pearl", 1, 4),
    ("minecraft:ender_eye", 1, 2),
    ("minecraft:blaze_rod", 1, 2),
    ("minecraft:ghast_tear", 1, 2),
    ("minecraft:prismarine_shard", 1, 4),
    ("minecraft:nautilus_shell", 1, 2),
    ("minecraft:heart_of_the_sea", 1, 1),
    ("minecraft:nether_star", 1, 1),
    ("minecraft:totem_of_undying", 1, 1),
    ("minecraft:enchanted_book", 1, 1),
    ("minecraft:golden_apple", 1, 2),
    ("minecraft:golden_carrot", 2, 6),
    ("minecraft:experience_bottle", 1, 4),
    ("minecraft:tipped_arrow", 4, 12),
    ("minecraft:saddle", 1, 1),
    ("minecraft:name_tag", 1, 1),
    ("minecraft:bundle", 1, 1),
    ("minecraft:mace", 1, 1),
    ("minecraft:ominous_bottle", 1, 1),
    ("minecraft:trial_key", 1, 2),
    ("minecraft:recovery_compass", 1, 1),
    ("minecraft:spyglass", 1, 1),
    ("minecraft:goat_horn", 1, 1),
    ("minecraft:disc_fragment_5", 1, 1),
    ("minecraft:music_disc_pigstep", 1, 1),
    ("minecraft:wind_charge", 1, 4),
    ("minecraft:gold_nugget", 2, 8),
    ("minecraft:iron_nugget", 2, 8),
    ("minecraft:slime_ball", 2, 6),
]
SPAWNER_USEFUL_STACKS = [       # (id, min, max) — просто полезный стак
    ("minecraft:arrow", 8, 32), ("minecraft:spectral_arrow", 4, 16),
    ("minecraft:torch", 8, 16), ("minecraft:coal", 4, 16),
    ("minecraft:bread", 3, 12), ("minecraft:cooked_beef", 3, 12),
    ("minecraft:cooked_cod", 3, 12), ("minecraft:apple", 3, 12),
    ("minecraft:golden_carrot", 2, 8), ("minecraft:sweet_berries", 4, 16),
    ("minecraft:oak_log", 4, 16), ("minecraft:string", 2, 12),
    ("minecraft:leather", 2, 8), ("minecraft:paper", 2, 8),
    ("minecraft:book", 1, 4), ("minecraft:bone", 2, 8),
    ("minecraft:gunpowder", 2, 8), ("minecraft:redstone", 4, 16),
    ("minecraft:rotten_flesh", 4, 12), ("minecraft:snowball", 4, 16),
    ("minecraft:spider_eye", 2, 8),
]

# area_effect_cloud: potion_contents {potion: <базовое зелье>} — реестр
# Potions.class 26.2 (long_/strong_ префиксов в 26.2 больше нет);
# custom_effects — MobEffects.class (формат записи Details: id/amplifier/
# duration/ambient/show_particles/show_icon — RecordCodecBuilder)
AEC_POTIONS = [
    "fire_resistance", "harming", "healing", "infested", "invisibility",
    "leaping", "luck", "night_vision", "oozing", "poison", "regeneration",
    "slow_falling", "slowness", "strength", "swiftness", "turtle_master",
    "water_breathing", "weakness", "weaving", "wind_charged",
]
AEC_EFFECTS = [
    "speed", "slowness", "haste", "mining_fatigue", "strength",
    "instant_health", "instant_damage", "jump_boost", "nausea",
    "regeneration", "resistance", "fire_resistance", "water_breathing",
    "invisibility", "blindness", "night_vision", "hunger", "weakness",
    "poison", "wither", "health_boost", "absorption", "saturation",
    "glowing", "levitation", "luck", "unluck", "slow_falling",
    "darkness", "wind_charged", "weaving", "oozing", "infested",
]

# Формы залпов фейерверка (FireworkExplosion$Shape, 26.2 — строковые id)
FIREWORK_SHAPES = ["small_ball", "large_ball", "star", "creeper", "burst"]

# Атрибуты и разумные диапазоны base (id — snake_case без "generic.",
# подтверждено Attributes.class и ванильным NBT allay). Атрибуты, которых
# нет у конкретного моба, молча пропускаются при загрузке (AttributeMap.apply:
# getInstance == null → skip), поэтому можно брать любые.
ATTRIBUTE_RANGES = {
    "minecraft:max_health": (10.0, 100.0),
    "minecraft:attack_damage": (1.0, 20.0),
    "minecraft:movement_speed": (0.1, 0.6),
    "minecraft:follow_range": (16.0, 80.0),
    "minecraft:armor": (0.0, 15.0),
    "minecraft:armor_toughness": (0.0, 10.0),
    "minecraft:attack_speed": (0.5, 4.0),
    "minecraft:knockback_resistance": (0.0, 1.0),
    "minecraft:max_absorption": (0.0, 20.0),
    "minecraft:scale": (0.5, 2.0),
    "minecraft:jump_strength": (0.3, 1.5),
    "minecraft:safe_fall_distance": (3.0, 15.0),
}

# Ванильные зачарования 26.2 (data/minecraft/enchantment/*.json)
ENCHANTMENTS = [
    "aqua_affinity", "bane_of_arthropods", "blast_protection", "breach",
    "channeling", "density", "depth_strider", "efficiency",
    "feather_falling", "fire_aspect", "fire_protection", "flame", "fortune",
    "frost_walker", "impaling", "infinity", "knockback", "looting", "loyalty",
    "luck_of_the_sea", "lunge", "lure", "mending", "multishot", "piercing",
    "power", "projectile_protection", "protection", "punch", "quick_charge",
    "respiration", "riptide", "sharpness", "silk_touch", "smite",
    "soul_speed", "sweeping_edge", "swift_sneak", "thorns", "unbreaking",
    "wind_burst",  # curse-зачарования (binding/vanishing) намеренно не берём
]

# кастомные зачарования текущего измерения (id "ns:name_enchN") — их
# подмешивает generate_dimension.py перед вызовом rand_structures
CUSTOM_ENCHS = []


def set_custom_enchants(ids):
    """Задать кастомные зачарования измерения: попадают в снаряжение
    мобов-«боссов» из .nbt-шаблонов (связка мобы ↔ зачарования).
    Вызывать до rand_structures."""
    global CUSTOM_ENCHS
    CUSTOM_ENCHS = [i for i in (ids or []) if i]

# Предметы для экипировки мобов (существование подтверждено текстурами
# assets/minecraft/textures/item/ в jar 26.2)
WEAPON_ITEMS = [
    "minecraft:wooden_sword", "minecraft:stone_sword", "minecraft:iron_sword",
    "minecraft:golden_sword", "minecraft:diamond_sword",
    "minecraft:netherite_sword", "minecraft:copper_sword",
    "minecraft:iron_axe", "minecraft:golden_axe", "minecraft:diamond_axe",
    "minecraft:netherite_axe", "minecraft:copper_axe",
    "minecraft:diamond_pickaxe", "minecraft:iron_shovel",
    "minecraft:diamond_shovel", "minecraft:iron_hoe", "minecraft:diamond_hoe",
    "minecraft:bow", "minecraft:crossbow", "minecraft:trident",
    "minecraft:mace", "minecraft:shears", "minecraft:shield",
    "minecraft:totem_of_undying",
]
ARMOR_ITEMS = [
    "minecraft:leather_helmet", "minecraft:leather_chestplate",
    "minecraft:leather_leggings", "minecraft:leather_boots",
    "minecraft:chainmail_helmet", "minecraft:chainmail_chestplate",
    "minecraft:chainmail_leggings", "minecraft:chainmail_boots",
    "minecraft:iron_helmet", "minecraft:iron_chestplate",
    "minecraft:iron_leggings", "minecraft:iron_boots",
    "minecraft:golden_helmet", "minecraft:golden_chestplate",
    "minecraft:golden_leggings", "minecraft:golden_boots",
    "minecraft:diamond_helmet", "minecraft:diamond_chestplate",
    "minecraft:diamond_leggings", "minecraft:diamond_boots",
    "minecraft:netherite_helmet", "minecraft:netherite_chestplate",
    "minecraft:netherite_leggings", "minecraft:netherite_boots",
    "minecraft:turtle_helmet", "minecraft:copper_helmet",
    "minecraft:copper_chestplate", "minecraft:copper_leggings",
    "minecraft:copper_boots",
]

# Генерация «крутых» имён мобов: прилагательное + существительное
# (пулы расширены ~×2.8: больше мрачных эпитетов/титулов/реликвий)
MOB_NAME_ADJ = ["Ancient", "Crimson", "Hollow", "Gloom", "Dread", "Storm",
                "Frost", "Ember", "Shadow", "Void", "Cursed", "Iron", "Pale",
                "Rotten", "Shimmering", "Whispering", "Blood", "Moonlit",
                "Sunken", "Howling", "Ravenous", "Eternal",
                "Ashen", "Blighted", "Buried", "Cold", "Corrupted", "Cruel",
                "Dark", "Deep", "Dismal", "Doomed", "Drowned", "Faded",
                "Feral", "Forgotten", "Ghastly", "Grim", "Haunted", "Hidden",
                "Hungry", "Jagged", "Lost", "Malign", "Merciless", "Molten",
                "Mournful", "Nocturnal", "Obsidian", "Rusted", "Sacred",
                "Silent", "Skeletal", "Sorrowful", "Stagnant", "Starved",
                "Stony", "Unholy", "Unseen", "Venomous", "Warped",
                "Withered", "Wretched"]
MOB_NAME_NOUN = ["Warden", "Reaper", "Sovereign", "Stalker", "Herald",
                 "Butcher", "Priest", "Hunter", "Nightmare", "Keeper",
                 "Watcher", "Warlord", "Shade", "Fiend", "Prodigy",
                 "Marauder", "Executioner", "Zealot", "Colossus", "Tyrant",
                 "Arbiter", "Avenger", "Banshee", "Beast", "Betrayer",
                 "Chaplain", "Conqueror", "Cultist", "Deacon", "Defiler",
                 "Disciple", "Enforcer", "Ferryman", "Ghoul", "Hangman",
                 "Harbinger", "Inquisitor", "Jailer", "Lich", "Mourner",
                 "Necromancer", "Omen", "Oracle", "Pilgrim", "Reaver",
                 "Sentinel", "Seraph", "Slayer", "Specter", "Summoner",
                 "Torturer", "Undertaker", "Vanguard", "Wraith"]
ITEM_NAME_NOUN = ["Blade", "Axe", "Bow", "Hammer", "Relic", "Trophy", "Fang",
                  "Sigil", "Idol", "Charm", "Crown", "Talisman",
                  "Amulet", "Codex", "Crest", "Dagger", "Effigy", "Gauntlet",
                  "Grimoire", "Helm", "Horn", "Key", "Lantern", "Mask",
                  "Mirror", "Pendant", "Ring", "Scepter", "Scroll", "Shard",
                  "Skull", "Totem", "Vessel", "Whisper"]
# Цвета текстовых компонентов (все 16 именованных цветов Minecraft)
TEXT_COLORS = ["red", "gold", "yellow", "aqua", "light_purple", "green",
               "dark_aqua", "dark_purple", "dark_red", "gray", "white",
               "dark_blue", "blue", "black", "dark_gray", "dark_green"]

# Ванильные nbt-шаблоны из data/minecraft/structure/ (пути БЕЗ .nbt) —
# только документация содержимого jar и источник для САМОТЕСТА (проверка
# «в своих пулах нет ванильских кусков»). В ГЕНЕРАЦИИ не используется:
# отдельные ванильные куски в своих пулax давали «обрубки» ванильских
# структур — jigsaw-данж собирался из разрозненных домов (юзер: «один дом
# а не целиком деревня — это кринж»). Ванильский контент теперь приходит
# только ЦЕЛИКОМ — форки VANILLA_JIGSAW_FORKS (ванильный start_pool =
# корень целого ванильного дерева кусков).
NBT_FAMILIES = {
    "village/plains/houses": [
        "plains_accessory_1", "plains_animal_pen_1", "plains_animal_pen_2",
        "plains_animal_pen_3", "plains_armorer_house_1", "plains_big_house_1",
        "plains_butcher_shop_1", "plains_butcher_shop_2", "plains_cartographer_1",
        "plains_fisher_cottage_1", "plains_fletcher_house_1",
        "plains_large_farm_1", "plains_library_1", "plains_library_2",
        "plains_masons_house_1", "plains_medium_house_1", "plains_medium_house_2",
        "plains_meeting_point_4", "plains_meeting_point_5",
        "plains_shepherds_house_1", "plains_small_farm_1",
        "plains_small_house_1", "plains_small_house_2", "plains_small_house_3",
        "plains_small_house_4", "plains_small_house_5", "plains_small_house_6",
        "plains_small_house_7", "plains_small_house_8", "plains_stable_1",
        "plains_stable_2", "plains_tannery_1", "plains_temple_3",
        "plains_temple_4", "plains_tool_smith_1", "plains_weaponsmith_1",
    ],
    "village/desert/houses": [
        "desert_animal_pen_1", "desert_animal_pen_2", "desert_armorer_1",
        "desert_butcher_shop_1", "desert_cartographer_house_1", "desert_farm_1",
        "desert_farm_2", "desert_fisher_1", "desert_fletcher_house_1",
        "desert_large_farm_1", "desert_library_1", "desert_mason_1",
        "desert_medium_house_1", "desert_medium_house_2",
        "desert_shepherd_house_1",
        "desert_small_house_1", "desert_small_house_2", "desert_small_house_3",
        "desert_small_house_4", "desert_small_house_5", "desert_small_house_6",
        "desert_small_house_7", "desert_small_house_8", "desert_tannery_1",
        "desert_temple_1", "desert_temple_2", "desert_tool_smith_1",
        "desert_weaponsmith_1",
    ],
    "village/savanna/houses": [
        "savanna_animal_pen_1", "savanna_animal_pen_2", "savanna_animal_pen_3",
        "savanna_armorer_1", "savanna_butchers_shop_1", "savanna_butchers_shop_2",
        "savanna_cartographer_1", "savanna_fisher_cottage_1",
        "savanna_fletcher_house_1", "savanna_large_farm_1", "savanna_large_farm_2",
        "savanna_library_1", "savanna_mason_1", "savanna_medium_house_1",
        "savanna_medium_house_2", "savanna_shepherd_1", "savanna_small_farm",
        "savanna_small_house_1", "savanna_small_house_2", "savanna_small_house_3",
        "savanna_small_house_4", "savanna_small_house_5", "savanna_small_house_6",
        "savanna_small_house_7", "savanna_small_house_8", "savanna_tannery_1",
        "savanna_temple_1", "savanna_temple_2", "savanna_tool_smith_1",
        "savanna_weaponsmith_1", "savanna_weaponsmith_2",
    ],
    "village/snowy/houses": [
        "snowy_animal_pen_1", "snowy_animal_pen_2", "snowy_armorer_house_1",
        "snowy_armorer_house_2", "snowy_butchers_shop_1", "snowy_butchers_shop_2",
        "snowy_cartographer_house_1", "snowy_farm_1", "snowy_farm_2",
        "snowy_fisher_cottage", "snowy_fletcher_house_1", "snowy_library_1",
        "snowy_masons_house_1", "snowy_masons_house_2", "snowy_medium_house_1",
        "snowy_medium_house_2", "snowy_medium_house_3", "snowy_shepherds_house_1",
        "snowy_small_house_1", "snowy_small_house_2", "snowy_small_house_3",
        "snowy_small_house_4", "snowy_small_house_5", "snowy_small_house_6",
        "snowy_small_house_7", "snowy_small_house_8", "snowy_tannery_1",
        "snowy_temple_1", "snowy_tool_smith_1", "snowy_weapon_smith_1",
    ],
    "village/taiga/houses": [
        "taiga_animal_pen_1", "taiga_armorer_2", "taiga_armorer_house_1",
        "taiga_butcher_shop_1", "taiga_cartographer_house_1",
        "taiga_fisher_cottage_1", "taiga_fletcher_house_1", "taiga_large_farm_1",
        "taiga_large_farm_2", "taiga_library_1", "taiga_masons_house_1",
        "taiga_medium_house_1", "taiga_medium_house_2", "taiga_medium_house_3",
        "taiga_medium_house_4", "taiga_shepherds_house_1", "taiga_small_farm_1",
        "taiga_small_house_1", "taiga_small_house_2", "taiga_small_house_3",
        "taiga_small_house_4", "taiga_small_house_5", "taiga_tannery_1",
        "taiga_temple_1", "taiga_tool_smith_1", "taiga_weaponsmith_1",
        "taiga_weaponsmith_2",
    ],
    "village/common/animals": [
        "cat_black", "cat_british", "cat_calico", "cat_jellie", "cat_persian",
        "cat_ragdoll", "cat_red", "cat_siamese", "cat_tabby", "cat_white",
        "cows_1", "horses_1", "horses_2", "horses_3", "horses_4", "horses_5",
        "pigs_1", "sheep_1", "sheep_2",
    ],
    "pillager_outpost": [
        "base_plate", "feature_cage_with_allays", "feature_cage1",
        "feature_cage2", "feature_logs", "feature_plate", "feature_targets",
        "feature_tent1", "feature_tent2", "watchtower", "watchtower_overgrown",
    ],
    "ruined_portal": [
        "giant_portal_1", "giant_portal_2", "giant_portal_3", "portal_1",
        "portal_2", "portal_3", "portal_4", "portal_5", "portal_6", "portal_7",
        "portal_8", "portal_9", "portal_10",
    ],
    "shipwreck": [
        "rightsideup_backhalf", "rightsideup_backhalf_degraded",
        "rightsideup_fronthalf", "rightsideup_fronthalf_degraded",
        "rightsideup_full", "rightsideup_full_degraded", "sideways_backhalf",
        "sideways_backhalf_degraded", "sideways_fronthalf",
        "sideways_fronthalf_degraded", "sideways_full", "sideways_full_degraded",
        "upsidedown_backhalf", "upsidedown_backhalf_degraded",
        "upsidedown_fronthalf", "upsidedown_fronthalf_degraded",
        "upsidedown_full", "upsidedown_full_degraded", "with_mast",
        "with_mast_degraded",
    ],
    "igloo": ["bottom", "middle", "top"],
    "end_city": [
        "base_floor", "base_roof", "bridge_end", "bridge_gentle_stairs",
        "bridge_piece", "bridge_steep_stairs", "fat_tower_base",
        "fat_tower_middle", "fat_tower_top", "second_floor_1", "second_floor_2",
        "second_roof", "ship", "third_floor_1", "third_floor_2", "third_roof",
        "tower_base", "tower_floor", "tower_piece", "tower_top",
    ],
    "woodland_mansion": [
        "1x1_a1", "1x1_a2", "1x1_a3", "1x1_a4", "1x1_a5", "1x1_as1", "1x1_as2",
        "1x1_as3", "1x1_as4", "1x1_b1", "1x1_b2", "1x1_b3", "1x1_b4", "1x1_b5",
        "1x2_a1", "1x2_a2", "1x2_a3", "1x2_a4", "1x2_a5", "1x2_a6", "1x2_a7",
        "1x2_a8", "1x2_a9", "1x2_b1", "1x2_b2", "1x2_b3", "1x2_b4", "1x2_b5",
        "1x2_c_stairs", "1x2_c1", "1x2_c2", "1x2_c3", "1x2_c4", "1x2_d_stairs",
        "1x2_d1", "1x2_d2", "1x2_d3", "1x2_d4", "1x2_d5", "1x2_s1", "1x2_s2",
        "1x2_se1", "2x2_a1", "2x2_a2", "2x2_a3", "2x2_a4", "2x2_b1", "2x2_b2",
        "2x2_b3", "2x2_b4", "2x2_b5", "2x2_s1", "carpet_east", "carpet_north",
        "carpet_south_1", "carpet_south_2", "carpet_west_1", "carpet_west_2",
        "corridor_floor", "entrance", "indoors_door_1", "indoors_door_2",
        "indoors_wall_1", "indoors_wall_2", "roof", "roof_corner", "roof_front",
        "roof_inner_corner", "small_wall", "small_wall_corner", "wall_corner",
        "wall_flat", "wall_window",
    ],
    "underwater_ruin": [
        "big_brick_1", "big_brick_2", "big_brick_3", "big_brick_8",
        "big_cracked_1", "big_cracked_2", "big_cracked_3", "big_cracked_8",
        "big_mossy_1", "big_mossy_2", "big_mossy_3", "big_mossy_8",
        "big_warm_4", "big_warm_5", "big_warm_6", "big_warm_7",
        "brick_1", "brick_2", "brick_3", "brick_4", "brick_5", "brick_6",
        "brick_7", "brick_8", "cracked_1", "cracked_2", "cracked_3",
        "cracked_4", "cracked_5", "cracked_6", "cracked_7", "cracked_8",
        "mossy_1", "mossy_2", "mossy_3", "mossy_4", "mossy_5", "mossy_6",
        "mossy_7", "mossy_8", "warm_1", "warm_2", "warm_3", "warm_4", "warm_5",
        "warm_6", "warm_7", "warm_8",
    ],
    "spring": [
        "sulfur_spring_extra_large_1", "sulfur_spring_large_1",
        "sulfur_spring_large_2", "sulfur_spring_medium_1",
        "sulfur_spring_medium_2", "sulfur_spring_medium_3",
        "sulfur_spring_small_1", "sulfur_spring_small_2",
        "sulfur_spring_small_3", "sulfur_spring_small_4",
    ],
    "fossil": [
        "skull_1", "skull_2", "skull_3", "skull_4",
        "skull_1_coal", "skull_2_coal", "skull_3_coal", "skull_4_coal",
        "spine_1", "spine_2", "spine_3", "spine_4",
        "spine_1_coal", "spine_2_coal", "spine_3_coal", "spine_4_coal",
    ],
    "nether_fossils": ["fossil_%d" % i for i in range(1, 15)],
    "trail_ruins": [
        "buildings/group_full_1", "buildings/group_full_2",
        "buildings/group_full_3", "buildings/group_full_4",
        "buildings/group_full_5", "buildings/group_hall_1",
        "buildings/group_hall_2", "buildings/group_hall_3",
        "buildings/group_hall_4", "buildings/group_hall_5",
        "buildings/group_lower_1", "buildings/group_lower_2",
        "buildings/group_lower_3", "buildings/group_lower_4",
        "buildings/group_lower_5", "buildings/group_room_1",
        "buildings/group_room_2", "buildings/group_room_3",
        "buildings/group_room_4", "buildings/group_room_5",
        "buildings/group_upper_1", "buildings/group_upper_2",
        "buildings/group_upper_3", "buildings/group_upper_4",
        "buildings/group_upper_5", "buildings/large_room_1",
        "buildings/large_room_2", "buildings/large_room_3",
        "buildings/large_room_4", "buildings/large_room_5",
        "buildings/one_room_1", "buildings/one_room_2", "buildings/one_room_3",
        "buildings/one_room_4", "buildings/one_room_5",
        "decor/decor_1", "decor/decor_2", "decor/decor_3", "decor/decor_4",
        "decor/decor_5", "decor/decor_6", "decor/decor_7",
        "roads/long_road_end", "roads/road_end_1", "roads/road_section_1",
        "roads/road_section_2", "roads/road_section_3", "roads/road_section_4",
        "roads/road_spacer_1",
        "tower/hall_1", "tower/hall_2", "tower/hall_3", "tower/hall_4",
        "tower/hall_5", "tower/large_hall_1", "tower/large_hall_2",
        "tower/large_hall_3", "tower/large_hall_4", "tower/large_hall_5",
        "tower/one_room_1", "tower/one_room_2", "tower/one_room_3",
        "tower/one_room_4", "tower/one_room_5", "tower/platform_1",
        "tower/platform_2", "tower/platform_3", "tower/platform_4",
        "tower/platform_5", "tower/stable_1", "tower/stable_2",
        "tower/stable_3", "tower/stable_4", "tower/stable_5", "tower/tower_1",
        "tower/tower_2", "tower/tower_3", "tower/tower_4", "tower/tower_5",
        "tower/tower_top_1", "tower/tower_top_2", "tower/tower_top_3",
        "tower/tower_top_4", "tower/tower_top_5",
    ],
    "trial_chambers": [
        # только куски без ссылок на спавнер-пулы (те требуют pool_aliases)
        "chamber/assembly", "chamber/chamber_1", "chamber/chamber_2",
        "chamber/chamber_4", "chamber/chamber_8", "chamber/entrance_cap",
        "corridor/atrium_1", "corridor/end_1", "corridor/end_2",
        "corridor/entrance_1", "corridor/entrance_2", "corridor/entrance_3",
        "corridor/first_plate", "corridor/second_plate",
        "corridor/straight_1", "corridor/straight_2", "corridor/straight_3",
        "corridor/straight_4", "corridor/straight_5", "corridor/straight_6",
        "corridor/straight_7", "corridor/straight_8",
        "hallway/cache_1", "hallway/corner_staircase",
        "hallway/corner_staircase_down", "hallway/corridor_connector_1",
        "hallway/encounter_1", "hallway/encounter_2", "hallway/encounter_3",
        "hallway/encounter_4", "hallway/encounter_5", "hallway/left_corner",
        "hallway/long_straight_staircase", "hallway/long_straight_staircase_down",
        "hallway/lower_hallway_connector", "hallway/right_corner",
        "hallway/rubble", "hallway/rubble_chamber", "hallway/rubble_chamber_thin",
        "hallway/rubble_thin", "hallway/straight", "hallway/straight_staircase",
        "hallway/straight_staircase_down", "hallway/trapped_staircase",
        "hallway/upper_hallway_connector",
    ],
    "ancient_city/structures": [
        "barracks", "camp_1", "camp_2", "camp_3", "chamber_1", "chamber_2",
        "chamber_3", "ice_box_1", "large_pillar_1", "large_ruin_1",
        "medium_pillar_1", "medium_ruin_1", "medium_ruin_2", "sauna_1",
        "small_ruin_1", "small_ruin_2", "small_statue", "tall_ruin_1",
        "tall_ruin_2", "tall_ruin_3", "tall_ruin_4",
    ],
    "bastion": [
        "units/air_base", "hoglin_stable/air_base", "treasure/big_air_full",
        "bridge/starting_pieces/entrance_base",
        "units/stages/stage_0_0", "units/stages/stage_0_1",
        "units/stages/stage_0_2", "units/stages/stage_0_3",
        "units/stages/stage_1_0", "units/stages/stage_1_1",
        "units/stages/stage_1_2", "units/stages/stage_1_3",
        "units/stages/stage_2_0", "units/stages/stage_2_1",
        "units/stages/stage_3_0", "units/stages/stage_3_1",
        "units/stages/stage_3_2", "units/stages/stage_3_3",
        "hoglin_stable/starting_pieces/starting_stairs_0",
        "hoglin_stable/starting_pieces/starting_stairs_1",
        "hoglin_stable/starting_pieces/starting_stairs_2",
        "hoglin_stable/starting_pieces/starting_stairs_3",
        "hoglin_stable/starting_pieces/starting_stairs_4",
        "hoglin_stable/large_stables/inner_0", "hoglin_stable/large_stables/inner_1",
        "hoglin_stable/large_stables/inner_2", "hoglin_stable/large_stables/inner_3",
        "hoglin_stable/large_stables/inner_4", "hoglin_stable/large_stables/outer_0",
        "hoglin_stable/large_stables/outer_1", "hoglin_stable/large_stables/outer_2",
        "hoglin_stable/large_stables/outer_3", "hoglin_stable/large_stables/outer_4",
        "hoglin_stable/small_stables/inner_0", "hoglin_stable/small_stables/inner_1",
        "hoglin_stable/small_stables/inner_2", "hoglin_stable/small_stables/inner_3",
        "hoglin_stable/small_stables/outer_0", "hoglin_stable/small_stables/outer_1",
        "hoglin_stable/small_stables/outer_2", "hoglin_stable/small_stables/outer_3",
        "treasure/bases/lava_basin", "treasure/bases/centers/center_0",
        "treasure/bases/centers/center_1", "treasure/bases/centers/center_2",
        "treasure/bases/centers/center_3",
        "treasure/extensions/empty", "treasure/extensions/fire_room",
        "treasure/extensions/house_0", "treasure/extensions/house_1",
        "treasure/extensions/large_bridge_0", "treasure/extensions/large_bridge_1",
        "treasure/extensions/large_bridge_2", "treasure/extensions/large_bridge_3",
        "treasure/extensions/roofed_bridge",
        "treasure/extensions/small_bridge_0", "treasure/extensions/small_bridge_1",
        "treasure/extensions/small_bridge_2", "treasure/extensions/small_bridge_3",
        "bridge/bridge_pieces/bridge",
    ],
}

NBT_LOCATIONS = sorted(
    "minecraft:%s/%s" % (fam, leaf)
    for fam, leaves in NBT_FAMILIES.items() for leaf in leaves)

# Ванильные алиасы спавнер-пулов trial_chambers (скопировано из
# data/minecraft/worldgen/structure/trial_chambers.json, 26.2). Цепочка:
# кусок (chamber_2 и др.) -> реальный пул spawner/ranged -> connector NBT,
# чей jigsaw-блок дёргает АЛИАС spawner/contents/ranged — реального пула
# с таким id нет, без этих биндингов JigsawPlacement WARNs «Empty or
# non-existent pool». Содержимое варьируется между группами: ranged и
# slow_ranged выбираются согласованно (random_group), melee/small_melee —
# независимо (random). contents/breeze — реальный пул, алиас не нужен.
TRIAL_POOL_ALIASES = [
    {
        "type": "minecraft:random_group",
        "groups": [
            {"weight": 1, "data": [
                {"type": "minecraft:direct",
                 "alias": "minecraft:trial_chambers/spawner/contents/ranged",
                 "target": "minecraft:trial_chambers/spawner/ranged/skeleton"},
                {"type": "minecraft:direct",
                 "alias": "minecraft:trial_chambers/spawner/contents/slow_ranged",
                 "target": "minecraft:trial_chambers/spawner/slow_ranged/skeleton"},
            ]},
            {"weight": 1, "data": [
                {"type": "minecraft:direct",
                 "alias": "minecraft:trial_chambers/spawner/contents/ranged",
                 "target": "minecraft:trial_chambers/spawner/ranged/stray"},
                {"type": "minecraft:direct",
                 "alias": "minecraft:trial_chambers/spawner/contents/slow_ranged",
                 "target": "minecraft:trial_chambers/spawner/slow_ranged/stray"},
            ]},
            {"weight": 1, "data": [
                {"type": "minecraft:direct",
                 "alias": "minecraft:trial_chambers/spawner/contents/ranged",
                 "target": "minecraft:trial_chambers/spawner/ranged/poison_skeleton"},
                {"type": "minecraft:direct",
                 "alias": "minecraft:trial_chambers/spawner/contents/slow_ranged",
                 "target": "minecraft:trial_chambers/spawner/slow_ranged/poison_skeleton"},
            ]},
        ],
    },
    {
        "type": "minecraft:random",
        "alias": "minecraft:trial_chambers/spawner/contents/melee",
        "targets": [
            {"weight": 1, "data": "minecraft:trial_chambers/spawner/melee/zombie"},
            {"weight": 1, "data": "minecraft:trial_chambers/spawner/melee/husk"},
            {"weight": 1, "data": "minecraft:trial_chambers/spawner/melee/spider"},
        ],
    },
    {
        "type": "minecraft:random",
        "alias": "minecraft:trial_chambers/spawner/contents/small_melee",
        "targets": [
            {"weight": 1, "data": "minecraft:trial_chambers/spawner/small_melee/slime"},
            {"weight": 1, "data": "minecraft:trial_chambers/spawner/small_melee/cave_spider"},
            {"weight": 1, "data": "minecraft:trial_chambers/spawner/small_melee/silverfish"},
            {"weight": 1, "data": "minecraft:trial_chambers/spawner/small_melee/baby_zombie"},
        ],
    },
]

# ---------------------------------------------------------------------------
# ФОРКИ ванильных jigsaw-структур 26.2
# ---------------------------------------------------------------------------
# Все 10 структур с "type": "minecraft:jigsaw" из jar minecraft-26.2-client.jar
# (data/minecraft/worldgen/structure/*.json — остальные 24 типа генерятся кодом
# без jigsaw-пулов). Поля v_* — ВАНИЛЬНЫЕ значения (сверены с jar — нужны
# самотесту как регрессионный эталон); в форке случайны только size /
# max_distance_from_center / terrain_adaptation / step / start_height /
# spawn_overrides / biomes, а НЕ-случайные поля (start_pool,
# use_expansion_hack, start_jigsaw_name, pool_aliases, dimension_padding,
# liquid_settings, project_start_to_heightmap) переносятся из ванили:
#   * start_pool — ВАНИЛЬНЫЙ стартовый пул: форк собирается ЦЕЛИКОМ из
#     ванильного дерева кусков (town_centers → улицы → дома; bastion/starts
#     → стадии; ancient_city/city_center → стены/structures; ...) — именно
#     так «деревня появляется целиком», а не одним домом;
#   * use_expansion_hack — вкл/выкл привязано к геометрии ванильных пулов:
#     включение у высоких пулов отбрасывает куски YSpan>16 (дыры),
#     выключение у деревень меняет их поведение (см. ограничение 2 выше);
#   * start_jigsaw_name — именованный якорь старта: ancient_city без
#     "minecraft:city_anchor" размещается по origin куска, а ЯКОРЬ,
#     отсутствующий в стартовом куске, даёт "No starting jigsaw found"
#     → структура ВСЕГДА empty (якорь есть во всех 3 кусках city_center);
#   * pool_aliases — обязательные биндинги спавнер-пулов: trial_chambers
#     без них НЕ собирается (WARN "Empty or non-existent pool" + дыры);
#     список — те же TRIAL_POOL_ALIASES (скопированы из её jar-JSON);
#   * dimension_padding / liquid_settings — ванильные (trial_chambers:
#     10 / ignore_waterlogging), подмешивают кускам отступ от границ мира.
# Веса: деревни ×2 (юзер просил именно «огромные деревни»), прочие ×1.
VANILLA_JIGSAW_FORKS = [
    {"key": "village_plains", "weight": 2,
     "start_pool": "minecraft:village/plains/town_centers",
     "v_size": 6, "v_max_distance": 80,
     "v_terrain_adaptation": "beard_thin", "v_step": "surface_structures",
     "v_start_height": {"absolute": 0},
     "use_expansion_hack": True,
     "project_start_to_heightmap": "WORLD_SURFACE_WG",
     "start_jigsaw_name": None, "pool_aliases": None,
     "dimension_padding": None, "liquid_settings": None},
    {"key": "village_desert", "weight": 2,
     "start_pool": "minecraft:village/desert/town_centers",
     "v_size": 6, "v_max_distance": 80,
     "v_terrain_adaptation": "beard_thin", "v_step": "surface_structures",
     "v_start_height": {"absolute": 0},
     "use_expansion_hack": True,
     "project_start_to_heightmap": "WORLD_SURFACE_WG",
     "start_jigsaw_name": None, "pool_aliases": None,
     "dimension_padding": None, "liquid_settings": None},
    {"key": "village_savanna", "weight": 2,
     "start_pool": "minecraft:village/savanna/town_centers",
     "v_size": 6, "v_max_distance": 80,
     "v_terrain_adaptation": "beard_thin", "v_step": "surface_structures",
     "v_start_height": {"absolute": 0},
     "use_expansion_hack": True,
     "project_start_to_heightmap": "WORLD_SURFACE_WG",
     "start_jigsaw_name": None, "pool_aliases": None,
     "dimension_padding": None, "liquid_settings": None},
    {"key": "village_snowy", "weight": 2,
     "start_pool": "minecraft:village/snowy/town_centers",
     "v_size": 6, "v_max_distance": 80,
     "v_terrain_adaptation": "beard_thin", "v_step": "surface_structures",
     "v_start_height": {"absolute": 0},
     "use_expansion_hack": True,
     "project_start_to_heightmap": "WORLD_SURFACE_WG",
     "start_jigsaw_name": None, "pool_aliases": None,
     "dimension_padding": None, "liquid_settings": None},
    {"key": "village_taiga", "weight": 2,
     "start_pool": "minecraft:village/taiga/town_centers",
     "v_size": 6, "v_max_distance": 80,
     "v_terrain_adaptation": "beard_thin", "v_step": "surface_structures",
     "v_start_height": {"absolute": 0},
     "use_expansion_hack": True,
     "project_start_to_heightmap": "WORLD_SURFACE_WG",
     "start_jigsaw_name": None, "pool_aliases": None,
     "dimension_padding": None, "liquid_settings": None},
    {"key": "pillager_outpost", "weight": 2,
     "start_pool": "minecraft:pillager_outpost/base_plates",
     "v_size": 7, "v_max_distance": 80,
     "v_terrain_adaptation": "beard_thin", "v_step": "surface_structures",
     "v_start_height": {"absolute": 0},
     "use_expansion_hack": True,
     "project_start_to_heightmap": "WORLD_SURFACE_WG",
     "start_jigsaw_name": None, "pool_aliases": None,
     "dimension_padding": None, "liquid_settings": None},
    {"key": "bastion_remnant", "weight": 1,
     "start_pool": "minecraft:bastion/starts",
     "v_size": 6, "v_max_distance": 80,
     "v_terrain_adaptation": None, "v_step": "surface_structures",
     "v_start_height": {"absolute": 33},
     "use_expansion_hack": False,
     "project_start_to_heightmap": None,
     "start_jigsaw_name": None, "pool_aliases": None,
     "dimension_padding": None, "liquid_settings": None},
    {"key": "ancient_city", "weight": 1,
     "start_pool": "minecraft:ancient_city/city_center",
     "v_size": 7, "v_max_distance": 116,
     "v_terrain_adaptation": "beard_box", "v_step": "underground_decoration",
     "v_start_height": {"absolute": -27},
     "use_expansion_hack": False,
     "project_start_to_heightmap": None,
     "start_jigsaw_name": "minecraft:city_anchor", "pool_aliases": None,
     "dimension_padding": None, "liquid_settings": None},
    {"key": "trail_ruins", "weight": 1,
     "start_pool": "minecraft:trail_ruins/tower",
     "v_size": 7, "v_max_distance": 80,
     "v_terrain_adaptation": "bury", "v_step": "underground_structures",
     "v_start_height": {"absolute": -15},
     "use_expansion_hack": False,
     "project_start_to_heightmap": "WORLD_SURFACE_WG",
     "start_jigsaw_name": None, "pool_aliases": None,
     "dimension_padding": None, "liquid_settings": None},
    {"key": "trial_chambers", "weight": 1,
     "start_pool": "minecraft:trial_chambers/chamber/end",
     "v_size": 20, "v_max_distance": 116,
     "v_terrain_adaptation": "encapsulate", "v_step": "underground_structures",
     "v_start_height": {"type": "minecraft:uniform",
                        "min_inclusive": {"absolute": -40},
                        "max_inclusive": {"absolute": -20}},
     "use_expansion_hack": False,
     "project_start_to_heightmap": None,
     "start_jigsaw_name": None,
     "pool_aliases": TRIAL_POOL_ALIASES,
     "dimension_padding": 10, "liquid_settings": "ignore_waterlogging"},
]

# start_pool → запись форка (проверка самотестом: у структуры-форка
# start_pool обязан быть из этой таблицы)
VANILLA_FORK_BY_POOL = {f["start_pool"]: f for f in VANILLA_JIGSAW_FORKS}

# взвешенный выбор форка (веса — целые, разворачиваем в список выбора)
_FORK_CHOICES = [f for f in VANILLA_JIGSAW_FORKS for _ in range(f["weight"])]

# доля структур измерения, которые становятся форками (~30-40% по ТЗ)
FORK_SHARE = 0.35

# terrain_adaptation для форков — веса из ТЗ (none 40 / beard_thin 30 /
# beard_box 15 / bury 10 / encapsulate 5); у своих jigsaw — свои веса
# (TERRAIN_ADAPTATION_WEIGHTS выше)
FORK_ADAPTATIONS = ["none", "beard_thin", "beard_box", "bury", "encapsulate"]
FORK_ADAPTATION_WEIGHTS = [40, 30, 15, 10, 5]


# ---------------------------------------------------------------------------
# Утилиты
# ---------------------------------------------------------------------------

def _gd():
    """Константы главного генератора. Импорт отложен до вызова функции,
    чтобы generate_dimension.py мог импортировать этот модуль сверху."""
    import generate_dimension
    return generate_dimension


def _anchor(rng, y, min_y, max_y):
    """VerticalAnchor для абсолютной Y-координаты: absolute / above_bottom /
    below_top (все три формы — как в ванильных carver/structure JSON)."""
    r = rng.random()
    if r < 0.5:
        return {"absolute": y}
    if r < 0.75:
        return {"above_bottom": y - min_y}
    return {"below_top": max_y - y}


def _float_or_uniform(rng, lo, hi):
    """Число ИЛИ uniform FloatProvider ({min_inclusive, max_exclusive})."""
    if rng.random() < 0.5:
        a = round(rng.uniform(lo, hi), 3)
        b = round(rng.uniform(lo, hi), 3)
        if a >= b:
            a, b = b, a
        if a == b:
            b = round(b + (hi - lo) * 0.1, 3)
        return {"type": "minecraft:uniform", "min_inclusive": a,
                "max_exclusive": b}
    return round(rng.uniform(lo, hi), 3)


# ---------------------------------------------------------------------------
# NBT: бинарный сериализатор с типизированными обёртками тегов
# ---------------------------------------------------------------------------

class _B(int):
    """NBT-тег TAG_Byte — boolean-поля NBT (Glowing, italic, ...)."""


class _S(int):
    """NBT-тег TAG_Short — например Fire (Entity.read: getShort)."""


class _F(float):
    """NBT-тег TAG_Float — Health, drop_chances, Rotation."""


class _L(int):
    """NBT-тег TAG_Long (LootTableSeed и др.)."""


def _nbt_tag_id(v):
    """ID типа тега по python-значению (с обёртками)."""
    if isinstance(v, (bool, _B)):
        return 1
    if isinstance(v, _S):
        return 2
    if isinstance(v, _L):
        return 4
    if isinstance(v, int):
        return 3
    if isinstance(v, _F):
        return 5
    if isinstance(v, float):
        return 6
    if isinstance(v, str):
        return 8
    if isinstance(v, (list, tuple)):
        return 9
    if isinstance(v, dict):
        return 10
    raise TypeError("не умею сериализовать %r" % (type(v),))


def _nbt_payload(v, out):
    """Тело тега (без id и имени)."""
    if isinstance(v, (bool, _B)):
        out += struct.pack(">b", int(v))
    elif isinstance(v, _S):
        out += struct.pack(">h", int(v))
    elif isinstance(v, _L):
        out += struct.pack(">q", int(v))
    elif isinstance(v, int):
        out += struct.pack(">i", v)
    elif isinstance(v, _F):
        out += struct.pack(">f", float(v))
    elif isinstance(v, float):
        out += struct.pack(">d", v)
    elif isinstance(v, str):
        b = v.encode("utf-8")
        out += struct.pack(">H", len(b)) + b
    elif isinstance(v, (list, tuple)):
        if not v:
            out += struct.pack(">b", 0) + struct.pack(">i", 0)  # TAG_End
        else:
            tid = _nbt_tag_id(v[0])
            for x in v:
                if _nbt_tag_id(x) != tid:
                    raise TypeError("смешанные типы в списке NBT: %r" % (v,))
            out += struct.pack(">b", tid) + struct.pack(">i", len(v))
            for x in v:
                _nbt_payload(x, out)
    elif isinstance(v, dict):
        for k, x in v.items():
            tid = _nbt_tag_id(x)
            kb = k.encode("utf-8")
            out += struct.pack(">b", tid) + struct.pack(">H", len(kb)) + kb
            _nbt_payload(x, out)
        out += b"\x00"  # TAG_End
    else:
        raise TypeError("не умею сериализовать %r" % (type(v),))


def _nbt_bytes(root):
    """Корневой compound -> gzip-NBT (формат ванильных structure/*.nbt:
    NbtIo.readCompressed читает gzip с безымянным корневым compound)."""
    out = bytearray()
    out += struct.pack(">b", 10) + struct.pack(">H", 0)  # root TAG_Compound ""
    _nbt_payload(root, out)
    return gzip.compress(bytes(out), mtime=0)


# ---------------------------------------------------------------------------
# КАРВЕРЫ
# ---------------------------------------------------------------------------

def _rand_carver_json(rng, min_y, max_y, ctype):
    gd = _gd()
    rnd_f, solid = gd.rnd_f, gd.SOLID_BLOCKS

    # y: HeightProvider uniform по двум якорям (гарантируем bottom < top)
    ya = rng.randint(min_y, max_y - 1)
    yb = rng.randint(ya + 1, max_y)

    # replaceable: HolderSet — тег ИЛИ список ID блоков.
    # БЕДРОК ИСКЛЮЧАЕМ (в отличие от пулов рельефа): карверы режут
    # ПОСЛЕ surface-правил, и карвер с bedrock в replaceable пробивает
    # bedrock_floor/roof — дыры в дне мира (падение в пустоту) и в кровле
    if rng.random() < 0.65:
        replaceable = CARVER_REPLACEABLE_TAGS[ctype]
    else:
        carveable = [b for b in solid if b[0] != "minecraft:bedrock"]
        replaceable = [b[0] for b in rng.sample(
            carveable, rng.randint(4, min(12, len(carveable))))]

    cfg = {
        "probability": rnd_f(rng, 0.005, 0.5, 4),
        "y": {"type": "minecraft:uniform",
              "min_inclusive": _anchor(rng, ya, min_y, max_y),
              "max_inclusive": _anchor(rng, yb, min_y, max_y)},
        "yScale": _float_or_uniform(rng, 0.1, 3.0),
        "lava_level": (rng.random() < 0.6 and
                       {"above_bottom": rng.randint(0, 16)} or
                       {"absolute": rng.randint(min_y, min_y + 32)}),
        "replaceable": replaceable,
    }

    if ctype in ("minecraft:cave", "minecraft:nether_cave"):
        # CaveCarverConfiguration: floor_level и множители — FloatProvider
        cfg["floor_level"] = _float_or_uniform(rng, -1.0, 0.2)
        cfg["horizontal_radius_multiplier"] = _float_or_uniform(rng, 0.5, 1.5)
        cfg["vertical_radius_multiplier"] = _float_or_uniform(rng, 0.5, 1.5)
    else:  # canyon
        rot_a = round(rng.uniform(-0.15, 0.0), 3)
        rot_b = round(rng.uniform(0.0, 0.15), 3)
        if rot_a >= rot_b:
            rot_a, rot_b = rot_b, rot_a
        thick_min = round(rng.uniform(0.0, 3.0), 1)
        thick_max = round(rng.uniform(4.0, 9.0), 1)
        cfg["vertical_rotation"] = {
            "type": "minecraft:uniform", "min_inclusive": rot_a,
            "max_exclusive": max(rot_b, rot_a + 0.01)}
        # plateau <= max-min ОБЯЗАТЕЛЕН (TrapezoidFloat: "Plateau can at
        # most be the full span") — ловили на реальном сервере: у zelomire
        # plateau 2.8 при размахе 2.4 валил загрузку ВСЕГО пака.
        # ПЛЮС: round(uniform(0, span), 1) может дать РОВНО span, а в double
        # span бывает 5.999... — вычитаем страховочные 0.05, чтобы plateau
        # был строго меньше размаха при любом округлении
        cfg["shape"] = {
            "distance_factor": _float_or_uniform(rng, 0.5, 1.0),
            "horizontal_radius_factor": _float_or_uniform(rng, 0.5, 1.0),
            "thickness": {"type": "minecraft:trapezoid", "min": thick_min,
                          "max": thick_max,
                          "plateau": (lambda s: math.floor(
                              rng.uniform(0.0, max(0.0, s - 0.15)) * 10) / 10.0)(
                              thick_max - thick_min)},
            "vertical_radius_default_factor": rnd_f(rng, 0.5, 1.5),
            "vertical_radius_center_factor": rnd_f(rng, 0.0, 0.5),
            "width_smoothness": rng.randint(1, 5),
        }

    # debug_settings есть только у cave/canyon в ванили (не у nether_cave).
    # air_state заполняет ВСЮ прорезанную карвером область — массовая
    # заливка, поэтому только PALETTE_BLOCKS (replaceable выше — не трогаем:
    # это «что можно прокопать», семантика другая)
    if ctype != "minecraft:nether_cave" and rng.random() < 0.08:
        cfg["debug_settings"] = {
            "air_state": gd.block_state(rng.choice(gd.PALETTE_BLOCKS)),
            "barrier_state": {"Name": "minecraft:glass"},
            "lava_state": {"Name": "minecraft:orange_stained_glass"},
            "water_state": {"Name": "minecraft:candle",
                            "Properties": {"candles": "1", "lit": "false",
                                           "waterlogged": "false"}},
        }
    return {"type": ctype, "config": cfg}


def rand_carvers(rng, ns, name, min_y, max_y, count=None):
    """Случайные configured_carver. Возвращает {id: json}.

    count — сколько карверов создать (по умолчанию 0-4 — старое поведение;
    вызывается с числом из тяжело-хвостового распределения).
    Писать в data/<ns>/worldgen/configured_carver/<имя из id>.json;
    ссылаться из биома (поле "carvers" — строка или список ID).
    """
    out = {}
    n = count if count is not None else rng.randint(0, 4)
    for i in range(n):
        cid = "%s:%s_cav%d" % (ns, name, i + 1)
        out[cid] = _rand_carver_json(rng, min_y, max_y,
                                     rng.choice(CARVER_TYPES))
    return out


# ---------------------------------------------------------------------------
# СТРУКТУРЫ (JSON)
# ---------------------------------------------------------------------------

def _rand_rule_processor(rng):
    """minecraft:rule — аналог старого block_replace/block_swap:
    input_predicate (block_match / random_block_match / tag_match)
    → output_state."""
    gd = _gd()
    rules = []
    for _ in range(rng.randint(1, 5)):
        r = rng.random()
        if r < 0.30:  # «swap»: безусловная замена одного блока
            inp = {"block": rng.choice(TEMPLATE_BLOCKS),
                   "predicate_type": "minecraft:block_match"}
        elif r < 0.60:
            inp = {"block": rng.choice(TEMPLATE_BLOCKS),
                   "predicate_type": "minecraft:random_block_match",
                   "probability": round(rng.uniform(0.05, 0.9), 3)}
        else:
            inp = {"tag": rng.choice(TAG_MATCH_TAGS),
                   "predicate_type": "minecraft:tag_match"}
        out_r = rng.random()
        if out_r < 0.55:
            # правило может заменить ЛЮБОЙ блок поставленного куска —
            # массовая заливка, только безопасный пул (без block entity)
            output = gd.block_state(rng.choice(gd.PALETTE_BLOCKS))
        elif out_r < 0.8:
            output = {"Name": "minecraft:air"}
        else:
            output = {"Name": "minecraft:cobweb"}
        loc = (rng.random() < 0.85 and
               {"predicate_type": "minecraft:always_true"} or
               {"block": rng.choice(["minecraft:water", "minecraft:lava"]),
                "predicate_type": "minecraft:block_match"})
        rules.append({"input_predicate": inp, "location_predicate": loc,
                      "output_state": output})
    return {"processor_type": "minecraft:rule", "rules": rules}


def _rand_processor_list(rng):
    """0–6 процессоров. Типы — только те, что есть в ванильных
    processor_list 26.2: rule / block_rot / protected_blocks / capped.
    Вариативность расширена: protected_blocks — разные ванильные
    блок-теги (формат 26.2: value = TagKey<Block>), capped — делегат
    rule ИЛИ block_rot и лимиты 1-12."""
    gd = _gd()
    processors = []
    for _ in range(rng.randint(0, 6)):
        r = rng.random()
        if r < 0.50:
            processors.append(_rand_rule_processor(rng))
        elif r < 0.72:
            # rottable_blocks ОБЯЗАТЕЛЬНЫ: без списка block_rot выедает
            # ЛЮБЫЕ блоки куска (при integrity ~0.5 — почти половину);
            # ограничиваем типовыми блоками шаблонов (образец —
            # gen_jigsaw._rand_proc_list)
            processors.append({
                "processor_type": "minecraft:block_rot",
                "rottable_blocks": rng.sample(TEMPLATE_BLOCKS,
                                              rng.randint(1, 4)),
                "integrity": round(rng.uniform(0.6, 0.95), 3)})
        elif r < 0.86:
            processors.append({
                "processor_type": "minecraft:protected_blocks",
                "value": rng.choice(_PROTECTED_TAG_CHOICES)})
        else:
            # capped: делегат rule ИЛИ block_rot, лимит варьируем
            if rng.random() < 0.6:
                delegate = _rand_rule_processor(rng)
            else:
                delegate = {
                    "processor_type": "minecraft:block_rot",
                    "rottable_blocks": rng.sample(TEMPLATE_BLOCKS,
                                                  rng.randint(1, 4)),
                    "integrity": round(rng.uniform(0.6, 0.95), 3)}
            processors.append({"processor_type": "minecraft:capped",
                               "delegate": delegate,
                               "limit": rng.randint(1, 12)})
    return {"processors": processors}


def _rand_template_pool(rng, proc_id, own_locations, is_start=True):
    """template_pool СВОЕГО jigsaw-данжа: 2–10 элементов — ТОЛЬКО свои
    .nbt-шаблоны (отдельные ванильные куски НЕ подмешиваются: юзер —
    «один дом а не целиком деревня — это кринж»; ванильский контент
    приходит ЦЕЛИКОМ через форки — ванильный start_pool из
    VANILLA_JIGSAW_FORKS). own_locations — непустой список "ns:key".
    is_start: пул используется как СТАРТОВЫЙ (start_pool структуры) — в
    стартовом пуле недопустим empty_pool_element: старт может выпасть
    пустым, findGenerationPoint вернёт empty и структура не сгенерится."""
    assert own_locations, "стартовый пул без своих шаблонов"
    elements = []
    # projection всегда rigid — чтобы entity-мобы и сундуки не смещались
    # по heightmap; element_type — только single_pool_element (legacy
    # нужен ванильным деревням со старой сеткой bounding box)
    for loc in rng.sample(own_locations,
                          rng.randint(2, min(10, len(own_locations)))):
        elements.append({
            "element": {
                "element_type": "minecraft:single_pool_element",
                "location": loc,
                "processors": (rng.random() < 0.5 and proc_id
                               or "minecraft:empty"),
                "projection": "rigid",
            },
            "weight": rng.randint(2, 12),
        })
    # пустой элемент — только в ОБЫЧНЫХ пулах (как в ванильных): в стартовом
    # он даёт пустой старт → структура не генерится вообще (аудит)
    if not is_start and rng.random() < 0.2:
        elements.append({"element": {"element_type":
                                     "minecraft:empty_pool_element"},
                         "weight": rng.randint(1, 10)})
    return {"elements": elements, "fallback": "minecraft:empty"}


def _rand_spawn_overrides(rng):
    """~50%: 1-2 случайные категории спавнов (вторая — с шансом 35%:
    расширение вариативности; из непустых пулов главного генератора;
    SPAWN_POOLS — тир-списки (вес, [мобы]), поэтому мобы выбираются
    через _sample_mobs), 1-3 случайных моба на категорию."""
    if rng.random() >= 0.5:
        return {}
    gd = _gd()
    cats = [c for c, tiers in gd.SPAWN_POOLS.items() if tiers]
    # monster — самая частая, как в ванильных структурах
    first = "monster" if rng.random() < 0.6 else rng.choice(cats)
    chosen = [first]
    if rng.random() < 0.35 and len(cats) > 1:
        chosen.append(rng.choice([c for c in cats if c != first]))
    # фильтр по проверенному списку сущностей: в SPAWN_POOLS бывают ID,
    # которых нет в реестре entity_type 26.2 (killer_bunny — это вариант
    # кролика, а не отдельный тип; сервер: "Unknown registry key")
    valid = set(STRUCTURE_MOBS)
    out = {}
    for cat in chosen:
        tiers = gd.SPAWN_POOLS[cat]
        all_mobs = [m for _, ms in tiers for m in ms
                    if m.split(":")[-1] in valid]
        if not all_mobs:
            continue
        k = 1 if rng.random() < 0.7 else 2
        spawns = []
        for etype in gd._sample_mobs(rng, tiers, k):
            if etype.split(":")[-1] not in valid:
                continue
            lo = 1
            spawns.append({"type": etype, "weight": rng.randint(1, 15),
                           "minCount": lo, "maxCount": rng.randint(lo, 3)})
        if not spawns:
            spawns.append({"type": "minecraft:" + rng.choice(
                sorted(valid & {m.split(":")[-1]
                                for _, ms in tiers for m in ms})),
                "weight": rng.randint(1, 15), "minCount": 1, "maxCount": 2})
        out[cat] = {"bounding_box": rng.choice(["piece", "full"]),
                    "spawns": spawns}
    return out


def _rand_structure_json(rng, stype, pool_id, min_y, max_y, biomes_ref,
                         has_ceiling=False, roof_bottom=None):
    """JSON structure любого из 15 типов 26.2 (без ocean_monument — он
    всегда empty в случайных биомах, см. NON_JIGSAW_TYPES). Общие поля settingsCodec:
    biomes / step / spawn_overrides / terrain_adaptation; типоспецифичные
    поля — по байткоду кодеков соответствующих классов."""
    step = rng.choice(STRUCTURE_STEPS)
    out = {
        "type": stype,
        "biomes": biomes_ref,
        "step": step,
        "spawn_overrides": _rand_spawn_overrides(rng),
    }
    # terrain_adaptation — у ЛЮБОГО типа (TerrainAdjustment; none в ваниле
    # просто опускается). Взвешенный выбор вместо равновероятного choice:
    # раньше bury/encapsulate выпадали в 40% случаев (структуры целиком
    # под землёй или в капсуле — аудит находимости), теперь суммарно 10%;
    # бороды (beard_thin/beard_box) «доращивают» землю под структурой —
    # суммарно 45%, чтобы постройки стояли на земле, а не висели в воздухе
    if rng.random() < 0.85:
        out["terrain_adaptation"] = rng.choices(
            TERRAIN_ADAPTATIONS, weights=TERRAIN_ADAPTATION_WEIGHTS)[0]

    if stype == JIGSAW_TYPE:
        out["start_pool"] = pool_id
        out["size"] = rng.randint(1, 7)
        out["use_expansion_hack"] = rng.random() < 0.5
        out["max_distance_from_center"] = rng.randint(20, 116)
        # start_height: якорь absolute ИЛИ uniform-провайдер из якорей.
        # ОГРАНИЧЕНИЕ ВЫСОТЫ (юзер: «структура обрезалась у почти
        # максимальной высоты»): куски пулов бывают до ~24 блоков (свои
        # башни gen_jigsaw, ванильные trial chambers / особняки) + запас
        # 10 → старт не выше max_y - 34, иначе верхние блоки (и block
        # entity спавнеров) выходят за границу мира → DUMMY-теги и WARN
        # «Tried to load a DUMMY block entity» на каждой загрузке чанка
        lo_y, hi_y = min_y + 8, max_y - 34
        # в мире с кровлей — та же дисциплина относительно кровли:
        # roof_bottom - 24 - 10 (кусок 24 + тот же запас)
        if roof_bottom is not None:
            hi_y = min(hi_y, roof_bottom - 24 - 10)
        if hi_y <= lo_y:  # очень низкий мир: потолок важнее — старт с тем
            # же запасом 34, но не ниже дна мира (иначе пустой диапазон)
            lo_y = hi_y = max(min_y, max_y - 34)
        if rng.random() < 0.6:
            out["start_height"] = {"absolute": rng.randint(lo_y, hi_y)}
        else:
            ya = rng.randint(lo_y, hi_y)
            yb = rng.randint(ya, hi_y)
            out["start_height"] = {
                "type": "minecraft:uniform",
                "min_inclusive": {"absolute": ya},
                "max_inclusive": {"absolute": yb}}
        # опциональные поля, подтверждённые ванильными jigsaw-структурами.
        # heightmap-проекция — ТОЛЬКО без кровли: в cavern-мирах
        # WORLD_SURFACE_WG указывает на крышу, и вся структура целиком
        # оказывается вне мира (там же — источник DUMMY-тегов).
        # Поверхностный шаг — почти всегда (юзер: «слишком часто в
        # воздухе, хочу чтоб с земли росли»); подземные шаги
        # (underground_structures/underground_decoration) — как было,
        # absolute start_height
        if step == "surface_structures" and rng.random() < 0.9 \
                and not has_ceiling:
            out["project_start_to_heightmap"] = "WORLD_SURFACE_WG"
        if rng.random() < 0.12:
            out["dimension_padding"] = rng.choice([4, 6, 8, 10])
        if rng.random() < 0.15:
            out["liquid_settings"] = "ignore_waterlogging"
        # pool_aliases СВОИМ jigsaw не нужны: свои куски не содержат
        # jigsaw-блоков и не тянут ванильные цепочки до алиаса contents/*
        # (алиасы обязательны только ФОРКАМ trial_chambers — см.
        # _rand_fork_structure_json)
    elif stype == "minecraft:mineshaft":
        # MineshaftStructure$Type: NORMAL("normal") / MESA("mesa")
        out["mineshaft_type"] = rng.choice(["normal", "mesa"])
    elif stype == "minecraft:ocean_ruin":
        # OceanRuinStructure$Type: WARM("warm") / COLD("cold");
        # large_probability/cluster_probability — Codec.floatRange(0, 1)
        out["biome_temp"] = rng.choice(["warm", "cold"])
        # Codec.floatRange(0, 1) включительно — берём весь диапазон
        out["large_probability"] = round(rng.uniform(0.0, 1.0), 3)
        out["cluster_probability"] = round(rng.uniform(0.0, 1.0), 3)
    elif stype == "minecraft:nether_fossil":
        # NetherFossilStructure: height — HeightProvider. Запас до
        # потолка ~30 (как высоким не-jigsaw типам): окаменелость и
        # рельеф над точкой старта не должны резаться о height limit
        lo_y, hi_y = min_y + 8, max_y - 30
        if hi_y <= lo_y:  # очень низкий мир: потолок важнее
            lo_y = hi_y = max(min_y, max_y - 30)
        if rng.random() < 0.6:
            out["height"] = {"absolute": rng.randint(lo_y, hi_y)}
        else:
            ya = rng.randint(lo_y, hi_y)
            yb = rng.randint(ya, hi_y)
            out["height"] = {
                "type": "minecraft:uniform",
                "min_inclusive": _anchor(rng, ya, min_y, max_y),
                "max_inclusive": _anchor(rng, yb, min_y, max_y)}
    elif stype == "minecraft:shipwreck":
        # ShipwreckStructure: is_beached — Codec.BOOL
        out["is_beached"] = rng.random() < 0.4
    elif stype == "minecraft:ruined_portal":
        # RuinedPortalStructure: setups — nonEmptyList(Setup.CODEC)
        # вариативность расширена: 1-6 сетов (было 1-4), mossiness 0..1,
        # размещения — взвешенные (наземные чаще, «в незере»/на дне
        # океана — реже)
        setups = []
        for _ in range(rng.randint(1, 6)):
            setups.append({
                "air_pocket_probability": round(rng.uniform(0.0, 1.0), 3),
                "can_be_cold": rng.random() < 0.6,
                "mossiness": round(rng.uniform(0.0, 1.0), 3),
                "overgrown": rng.random() < 0.3,
                "placement": rng.choices(
                    RUINED_PORTAL_PLACEMENTS,
                    weights=[3, 3, 2, 2, 1, 1])[0],
                "replace_with_blackstone": rng.random() < 0.2,
                "vines": rng.random() < 0.35,
                "weight": round(rng.uniform(0.1, 1.0), 3),
            })
        out["setups"] = setups
    # остальные типы (buried_treasure/desert_pyramid/end_city/fortress/
    # igloo/jungle_temple/woodland_mansion/stronghold/
    # swamp_hut) собственных полей не имеют — только settingsCodec
    return out


def _rand_fork_structure_json(rng, fork, min_y, max_y, biomes_ref,
                              has_ceiling=False, roof_bottom=None):
    """ФОРК ванильной jigsaw-структуры (запись из VANILLA_JIGSAW_FORKS):
    type minecraft:jigsaw со start_pool = ВАНИЛЬНЫЙ пул — структура
    собирается ЦЕЛИКОМ из ванильного дерева кусков (деревня/бастион/
    древний город/trial chambers/...), параметры случайные:

      size             обычно randint(4,12), ~15% «гигантские» randint(13,20)
                       (байткод JigsawStructure.CODEC: size =
                       Codec.intRange(0, 20) — «40 шагов» НЕВОЗМОЖНЫ,
                       потолок гиганта 20);
      max_distance_from_center  randint(30, cap); cap = 116 при
                       terrain_adaptation != none (verifyRange: md+12 <=
                       128, иначе датапак не грузится ЦЕЛИКОМ), иначе 128;
                       пол не ниже 4*size — при маленьком md дальние куски
                       дерева молча отбрасываются (обрубленная деревня);
      terrain_adaptation  взвешенно none 40 / beard_thin 30 / beard_box
                       15 / bury 10 / encapsulate 5 (всегда присутствует);
      start_height     как у своих jigsaw: absolute/uniform в границах
                       мира, запас 34 до потолка, roof-ограничение
                       (при heightmap-проекции движок игнорирует);
      project_start_to_heightmap  ванильное значение с шансом 0.9 (и
                       только в мире без кровли), иначе по текущим
                       правилам (surface-шаг + 0.9 + без кровли);
      spawn_overrides / step / biomes — существующие рандомайзеры.

    Копируется из ванили (геометрия чужого дерева кусков хрупка):
      use_expansion_hack — включение true ОТБРАСЫВАЕТ куски с YSpan > 16
        (JigsawPlacement$Placer: doExpansionHack && box.getYSpan() > 16
        → skip) — бастион/древний город/trial chambers получили бы дыры;
        выключение у деревень меняет их поведение — ровно ванильное;
      start_jigsaw_name — именованный якорь старта (ancient_city:
        "minecraft:city_anchor"; якорь есть во всех кусках city_center);
      pool_aliases — обязательные биндинги спавнер-пулов trial_chambers;
      dimension_padding / liquid_settings — ванильные, иначе как у своих."""
    step = rng.choice(STRUCTURE_STEPS)
    out = {
        "type": JIGSAW_TYPE,
        "biomes": biomes_ref,
        "step": step,
        "spawn_overrides": _rand_spawn_overrides(rng),
        "start_pool": fork["start_pool"],
        "use_expansion_hack": fork["use_expansion_hack"],
    }
    # terrain_adaptation — ВСЕГДА, веса из ТЗ
    adapt = rng.choices(FORK_ADAPTATIONS, weights=FORK_ADAPTATION_WEIGHTS)[0]
    out["terrain_adaptation"] = adapt
    # size: обычно 4-12, ~15% гигантские 13-20 (потолок кодека — 20)
    out["size"] = (rng.randint(13, 20) if rng.random() < 0.15
                   else rng.randint(4, 12))
    # max_distance_from_center: verifyRange + пол 4*size
    md_cap = 116 if adapt != "none" else 128
    md_lo = min(md_cap, max(30, 4 * out["size"]))
    out["max_distance_from_center"] = rng.randint(md_lo, md_cap)
    # start_height — как у своих jigsaw (в границах мира, запас до потолка)
    lo_y, hi_y = min_y + 8, max_y - 34
    if roof_bottom is not None:
        hi_y = min(hi_y, roof_bottom - 24 - 10)
    if hi_y <= lo_y:
        lo_y = hi_y = max(min_y, max_y - 34)
    if rng.random() < 0.6:
        out["start_height"] = {"absolute": rng.randint(lo_y, hi_y)}
    else:
        ya = rng.randint(lo_y, hi_y)
        yb = rng.randint(ya, hi_y)
        out["start_height"] = {
            "type": "minecraft:uniform",
            "min_inclusive": {"absolute": ya},
            "max_inclusive": {"absolute": yb}}
    # heightmap-проекция: ванильное значение (у деревень/аванпоста/
    # trail_ruins — WORLD_SURFACE_WG) с шансом 0.9 и только без кровли
    # (в cavern-мирах WORLD_SURFACE_WG = крыша); иначе — текущие правила
    if fork["project_start_to_heightmap"] and not has_ceiling \
            and rng.random() < 0.9:
        out["project_start_to_heightmap"] = fork["project_start_to_heightmap"]
    elif step == "surface_structures" and rng.random() < 0.9 \
            and not has_ceiling:
        out["project_start_to_heightmap"] = "WORLD_SURFACE_WG"
    # именованный якорь старта (ancient_city без него размещается по
    # origin куска — копируем ванильное имя всегда)
    if fork["start_jigsaw_name"]:
        out["start_jigsaw_name"] = fork["start_jigsaw_name"]
    # обязательные алиасы пулов (trial_chambers без них не собирается)
    if fork["pool_aliases"]:
        out["pool_aliases"] = fork["pool_aliases"]
    # dimension_padding / liquid_settings: ванильные, иначе как у своих
    if fork["dimension_padding"] is not None:
        out["dimension_padding"] = fork["dimension_padding"]
    elif rng.random() < 0.12:
        out["dimension_padding"] = rng.choice([4, 6, 8, 10])
    if fork["liquid_settings"]:
        out["liquid_settings"] = fork["liquid_settings"]
    elif rng.random() < 0.15:
        out["liquid_settings"] = "ignore_waterlogging"
    return out


def _rand_structure_set_json(rng, structure_ids, ns, name, set_num,
                             biome_ids, biome_tags, biomes_ref=None):
    """structure_set: random_spread или (редко, ~10%) concentric_rings
    (как ванильный strongholds).

    biomes_ref — поле "biomes" структуры (тег "#ns:..." ИЛИ список ID):
    concentric_rings ищет позиции колец в preferred_biomes, поэтому кольца
    берут ТЕ ЖЕ биомы, что и сама структура — независимый сэмпл давал
    позиции, которые не проходят биом-чек структуры (пустые кольца)."""
    # rings только для сета из ОДНОЙ структуры: раньше ids=structure_ids[:1]
    # молча выкидывал остальные структуры сета — они оставались БЕЗ
    # structure_set и не генерились ВООБЩЕ (аудит находимости)
    if rng.random() < 0.10 and len(structure_ids) == 1:
        # ConcentricRingsStructurePlacement (байткод):
        #   distance  intRange(0, 1023), spread intRange(0, 1023),
        #   count     intRange(1, 4095), preferred_biomes — HolderSet<Biome>
        # (базовые поля placementCodec: salt и др.)
        placement = {
            "type": "minecraft:concentric_rings",
            "distance": rng.randint(6, 16),
            "spread": rng.randint(2, 6),
            "count": rng.randint(8, 48),
            "preferred_biomes": (biomes_ref if biomes_ref is not None
                                 else sorted(biome_ids)),
            "salt": rng.randrange(1 << 24),
        }
        ids = structure_ids
    else:
        # random_spread: spacing у 80% сетов «обычный» (12-34), у 20%
        # редкий (34-48); separation = 15-35% spacing — плотная сетка
        spacing = (rng.randint(12, 34) if rng.random() < 0.8
                   else rng.randint(34, 48))
        separation = round(spacing * rng.uniform(0.15, 0.35))
        if separation >= spacing:   # инвариант random_spread: sep < spacing
            separation = spacing - 1
        placement = {"type": "minecraft:random_spread",
                     "spacing": spacing,
                     "separation": separation,
                     "salt": rng.randrange(1 << 24)}
        if rng.random() < 0.25:
            placement["spread_type"] = "triangular"
        # frequency только 0.3-0.8 и максимум у 10% сетов: низкая частота
        # делает /locate почти бесполезным (аудит: freq < 0.1 — не найдёт)
        if rng.random() < 0.10:
            placement["frequency"] = round(rng.uniform(0.3, 0.8), 3)
            placement["frequency_reduction_method"] = rng.choice(
                ["legacy_type_1", "legacy_type_2", "legacy_type_3"])
        ids = structure_ids
    return {"structures": [{"structure": sid, "weight": rng.randint(1, 5)}
                           for sid in ids],
            "placement": placement}


# ---------------------------------------------------------------------------
# SNBT: предметы, мобы, постройки
# ---------------------------------------------------------------------------

def _rand_text_component(rng, text):
    """Текстовый компонент 26.2 (NBT-нативный, НЕ JSON-строка):
    {text:"...",color:"...",italic:0b}."""
    comp = {"text": text}
    if rng.random() < 0.85:
        comp["color"] = rng.choice(TEXT_COLORS)
    if rng.random() < 0.8:
        comp["italic"] = _B(0)
    return comp


def _rand_mob_name(rng):
    """«Крутое» имя: прилагательное+существительное, иногда с эпитетом
    через слоги главного генератора (Vorlath, Kragmor...)."""
    adj = rng.choice(MOB_NAME_ADJ)
    noun = rng.choice(MOB_NAME_NOUN)
    r = rng.random()
    if r < 0.55:
        return "%s %s" % (adj, noun)
    if r < 0.8:
        return "%s %s the %s" % (adj, noun, rng.choice(MOB_NAME_ADJ))
    gd = _gd()
    syll = gd.random_name(rng).capitalize()
    return "%s %s of %s" % (adj, noun, syll)


_SLOT_PART = {"head": "helmet", "chest": "chestplate",
              "legs": "leggings", "feet": "boots"}


def _rand_item_stack(rng, kind, slot=None):
    """ItemStack 26.2: {id, count, components:{...}}. Зачарования —
    прямой map {"minecraft:sharpness":5} (ItemEnchantments.CODEC).

    Слоты снаряжения (правила gen_loot): броня подбирается ПОД
    запрошенный слот (шлем — в head и т.д., как в ванильных
    equipment-таблицах — сапоги на голову не надеваем); в слоты рук
    (mainhand/offhand) броня не попадает. Атрибут-модификаторы тут не
    генерируются — ванильные базовые характеристики предмета (урон/
    скорость атаки, броня) действуют как есть; equippable/
    camera_overlay/max_stack_size тоже не трогаем."""
    if kind == "armor":
        part = _SLOT_PART.get(slot)
        pool = ([i for i in ARMOR_ITEMS if i.endswith("_" + part)] if part
                else ARMOR_ITEMS)
    elif kind == "weapon":
        pool = WEAPON_ITEMS
    else:  # «любой» — слот руки: только оружие/щит/тотем
        pool = WEAPON_ITEMS
    out = {"id": rng.choice(pool), "count": 1}
    comps = {}
    if rng.random() < 0.7:
        ench = {}
        for name in rng.sample(ENCHANTMENTS, rng.randint(1, 3)):
            ench["minecraft:" + name] = rng.randint(1, 5)
        # кастомные зачарования измерения (связка с gen_enchantments;
        # подмешивает generate_dimension.py через set_custom_enchants)
        if CUSTOM_ENCHS and rng.random() < 0.35:
            ench[rng.choice(CUSTOM_ENCHS)] = rng.randint(1, 2)
        comps["minecraft:enchantments"] = ench
    if rng.random() < 0.35:
        gd = _gd()
        noun = rng.choice(ITEM_NAME_NOUN)
        syll = gd.random_name(rng).capitalize()
        comps["minecraft:custom_name"] = _rand_text_component(
            rng, "%s of %s" % (noun, syll))
    if rng.random() < 0.2:
        comps["minecraft:unbreakable"] = {}
    if comps:
        out["components"] = comps
    return out


# ---------------------------------------------------------------------------
# Счётчик уникальных слотов лут-таблиц измерения
# ---------------------------------------------------------------------------

class LootSlots:
    """Раздача уникальных id лут-таблиц "<ns>:<name>_lootN" (N с единицы).

    Требование: у каждой особой сущности/контейнера измерения (сундук,
    бочка, волт, DeathLootTable моба-«босса», призы trial_spawner'а) —
    СВОЯ таблица, без повторов в рамках измерения. Генераторы занимают
    слоты ПО МЕРЕ создания ссылок (take()), а gen_loot.rand_loot потом
    одним вызовом создаёт таблицы для всех слотов 1..count (та же схема
    имён). Один экземпляр на измерение передаётся во ВСЕ генераторы
    (trial_spawners → структуры → jigsaw), поэтому уникальность
    гарантирует сам счётчик.

    release() возвращает занятый слот, если ссылка на него исчезла
    (например, сундук замещён волтом со своей таблицей, или блок
    не нашёлся): слот переиспользуется следующим take(), поэтому
    «дырок» в нумерации 1..count не остаётся — каждый занятый в
    итоге id гарантированно имеет ровно одну живую ссылку."""

    def __init__(self, ns, name):
        self.ns = ns
        self.name = name
        self._ids = []      # все когда-либо выданные id
        self._free = []     # освобождённые id (переиспользуются take)

    def take(self):
        """Занять следующий свободный слот; возвращает id таблицы."""
        if self._free:
            return self._free.pop()
        tid = "%s:%s_loot%d" % (self.ns, self.name, len(self._ids) + 1)
        self._ids.append(tid)
        return tid

    def owns(self, tid):
        """Выдан ли этот id данным счётчиком (для release)."""
        return tid in self._ids

    def release(self, tid):
        """Вернуть слот, если ссылка на таблицу пропала (id будет
        переиспользован). Чужие/vanilla id молча игнорируются."""
        if tid and tid in self._ids and tid not in self._free:
            self._free.append(tid)

    @property
    def ids(self):
        """Все ДЕЙСТВУЮЩИЕ id (без освобождённых, в порядке занятия)."""
        return [i for i in self._ids if i not in self._free]

    @property
    def count(self):
        """Сколько слотов реально занято (id — ровно 1..count без дырок)."""
        return len(self._ids) - len(self._free)


def _rand_chest_nbt(rng, loot_alloc):
    """NBT блочного энтити сундука/бочки: LootTable — точное имя тега
    (RandomizableContainer.tryLoadLootTable, подтверждено ванильными
    шаблонами DataVersion 4903). loot_alloc — счётчик LootSlots: каждому
    сундуку СВОЯ уникальная таблица (None → ванильная chest-таблица)."""
    if loot_alloc is not None:
        table = loot_alloc.take()
    else:
        table = rng.choice(VANILLA_CHEST_LOOT)
    return {"LootTable": table}


def _rand_spawner_stack(rng):
    """Стек для сущности item / рамок / контейнеров спавнера: 55%
    зачарованное оружие/броня с шансом имени (генератор снаряжения
    _rand_item_stack), 25% редкий материал/артефакт, 20% полезный
    стак (стрелы/еда/факелы). Формат ItemStack 26.2: {id, count,
    components}."""
    r = rng.random()
    if r < 0.55:
        return _rand_item_stack(rng, rng.choice(["weapon", "armor"]))
    if r < 0.80:
        iid, lo, hi = rng.choice(SPAWNER_RARE_ITEMS)
    else:
        iid, lo, hi = rng.choice(SPAWNER_USEFUL_STACKS)
    return {"id": iid, "count": rng.randint(lo, hi)}


def _boat_entity_id(rng, chest):
    """Id лодки по породе: oak_boat/oak_chest_boat, а бамбук —
    bamboo_raft/bamboo_chest_raft (реестр 26.2, EntityTypeIds)."""
    wood = rng.choice(_BOAT_WOODS)
    if wood == "bamboo":
        return "minecraft:%s" % ("bamboo_chest_raft" if chest
                                 else "bamboo_raft")
    return "minecraft:%s_%s" % (wood, "chest_boat" if chest else "boat")


def _weighted_choice(rng, weights):
    """Взвешенный выбор ключа dict {key: вес} (веса — float > 0)."""
    total = sum(weights.values())
    r = rng.random() * total
    acc = 0.0
    for key, w in weights.items():
        acc += w
        if r < acc:
            return key
    return next(reversed(weights))       # численный запас


def _gen_item_entity(rng):
    """minecraft:item — Item {id, count, components} (ItemEntity:
    put(Item) через ItemStack.CODEC; PickupDelay — short)."""
    ent = {"id": "minecraft:item", "Item": _rand_spawner_stack(rng)}
    if rng.random() < 0.30:
        ent["PickupDelay"] = _S(rng.randint(10, 100))
    return ent


def _gen_armor_stand_entity(rng):
    """minecraft:armor_stand — до 6 слотов equipment (EntityEquipment:
    map слот→ItemStack, тот же формат что у мобов) + флаги ArmorStand
    (ShowArms/NoBasePlate/Small/Invisible — byte; DisabledSlots int).
    ~25% — совсем без NBT (ультракастом — не всегда)."""
    ent = {"id": "minecraft:armor_stand"}
    if rng.random() < 0.25:
        return ent
    equip = {}
    if rng.random() < 0.60:
        equip["mainhand"] = _rand_item_stack(rng, "weapon")
    if rng.random() < 0.25:
        equip["offhand"] = _rand_item_stack(rng, "any")
    for slot in ("head", "chest", "legs", "feet"):
        if rng.random() < 0.45:
            equip[slot] = _rand_item_stack(rng, "armor", slot)
    if equip:
        ent["equipment"] = equip
    if rng.random() < 0.35:
        ent["ShowArms"] = _B(1)
    if rng.random() < 0.30:
        ent["NoBasePlate"] = _B(1)
    if rng.random() < 0.20:
        ent["Small"] = _B(1)
    if rng.random() < 0.10:
        ent["Invisible"] = _B(1)
    if rng.random() < 0.40:
        ent["CustomName"] = _rand_text_component(rng, _rand_mob_name(rng))
        if rng.random() < 0.6:
            ent["CustomNameVisible"] = _B(1)
    return ent


def _gen_tnt_entity(rng):
    """minecraft:tnt — fuse (SHORT, 20-200 тиков; PrimedTnt 26.2 пишет
    putShort("fuse"), тег в нижнем регистре), иногда explosion_power
    (float) и маскировка block_state (рендер другим блоком)."""
    ent = {"id": "minecraft:tnt", "fuse": _S(rng.randint(20, 200))}
    if rng.random() < 0.25:
        ent["explosion_power"] = _F(round(rng.uniform(1.0, 6.0), 1))
    if rng.random() < 0.25:
        bid, props = rng.choice(_gd().PALETTE_BLOCKS)
        bs = {"Name": bid}
        if props:
            bs["Properties"] = dict(props)
        ent["block_state"] = bs
    return ent


def _gen_falling_block_entity(rng):
    """minecraft:falling_block — BlockState {Name, Properties} из палитры
    измерения (тег CamelCase — сверен FallingBlockEntity 26.2: store
    "BlockState", putInt "Time", putBoolean DropItem/HurtEntities/
    CancelDrop, FallHurtAmount float, FallHurtMax int)."""
    bid, props = rng.choice(_gd().PALETTE_BLOCKS)
    bs = {"Name": bid}
    if props:
        bs["Properties"] = dict(props)
    ent = {"id": "minecraft:falling_block",
           "BlockState": bs,
           "Time": 1}
    if rng.random() < 0.25:
        ent["HurtEntities"] = _B(1)
        ent["FallHurtAmount"] = _F(round(rng.uniform(1.0, 3.0), 1))
        ent["FallHurtMax"] = rng.randint(5, 20)
    if rng.random() < 0.20:
        ent["DropItem"] = _B(1)
    if rng.random() < 0.10:
        ent["CancelDrop"] = _B(1)
    return ent


def _gen_experience_orb_entity(rng):
    """minecraft:experience_orb — Value (SHORT 1-50; ExperienceOrb
    26.2: putShort "Value"; Count при отсутствии = 1)."""
    return {"id": "minecraft:experience_orb",
            "Value": _S(rng.randint(1, 50))}


def _gen_container_entity(rng, eid):
    """Сундук-сущности (chest_boat по породе дерева / chest_minecart):
    Items — список 3-6 ItemStack'ов со Slot (byte, ContainerHelper →
    ItemStackWithSlot.CODEC: Slot unsigned byte + id/count/components;
    у контейнера 27 слотов 0-26)."""
    items = []
    for slot in rng.sample(range(27), rng.randint(3, 6)):
        stack = _rand_spawner_stack(rng)
        stack["Slot"] = _B(slot)
        items.append(stack)
    return {"id": eid, "Items": items}


def _gen_item_frame_entity(rng, eid):
    """minecraft:item_frame / glow_item_frame — Item {...} (ItemStack),
    ItemRotation (int 0-7), иногда Invisible/Fixed (byte) и
    ItemDropChance (float; ItemFrame 26.2, сверен javap)."""
    ent = {"id": eid, "Item": _rand_spawner_stack(rng)}
    if rng.random() < 0.50:
        ent["ItemRotation"] = rng.randint(0, 7)
    if rng.random() < 0.20:
        ent["Invisible"] = _B(1)
    if rng.random() < 0.15:
        ent["Fixed"] = _B(1)
    if rng.random() < 0.25:
        ent["ItemDropChance"] = _F(round(rng.uniform(0.0, 1.0), 2))
    return ent


def _gen_firework_entity(rng):
    """minecraft:firework_rocket — FireworksItem (ItemStack c
    компонентом minecraft:fireworks: flight_duration byte + explosions
    [{shape (строковый id), colors [int], fade_colors, has_trail/
    has_twinkle byte}]; Fireworks/FireworkExplosion 26.2) + LifeTime
    (int; FireworkRocketEntity: putInt Life/LifeTime)."""
    explosions = []
    for _ in range(rng.randint(1, 3)):
        ex = {"shape": rng.choice(FIREWORK_SHAPES),
              "colors": [rng.randint(0, 0xFFFFFF)
                         for _ in range(rng.randint(1, 3))]}
        if rng.random() < 0.50:
            ex["fade_colors"] = [rng.randint(0, 0xFFFFFF)
                                 for _ in range(rng.randint(1, 2))]
        if rng.random() < 0.30:
            ex["has_trail"] = _B(1)
        if rng.random() < 0.30:
            ex["has_twinkle"] = _B(1)
        explosions.append(ex)
    fw = {"id": "minecraft:firework_rocket", "count": 1,
          "components": {"minecraft:fireworks": {
              "flight_duration": _B(rng.randint(1, 3)),
              "explosions": explosions}}}
    ent = {"id": "minecraft:firework_rocket", "FireworksItem": fw}
    if rng.random() < 0.50:
        ent["LifeTime"] = rng.randint(20, 60)
    return ent


def _gen_aec_entity(rng):
    """minecraft:area_effect_cloud — Radius (float) + Duration/
    WaitTime/ReapplicationDelay (int) + potion_contents: готовое зелье
    (60%) или custom_effects [{id, amplifier byte, duration int}]
    (40%); формат AreaEffectCloud/PotionContents/MobEffectInstance$
    Details 26.2, сверен javap (теги CamelCase + snake_case
    potion_contents)."""
    ent = {"id": "minecraft:area_effect_cloud",
           "Radius": _F(round(rng.uniform(2.0, 6.0), 2)),
           "Duration": rng.randint(100, 800),
           "WaitTime": rng.randint(0, 20),
           "ReapplicationDelay": rng.randint(20, 100)}
    pc = {}
    if rng.random() < 0.60:
        pc["potion"] = "minecraft:" + rng.choice(AEC_POTIONS)
    else:
        pc["custom_effects"] = [
            {"id": "minecraft:" + rng.choice(AEC_EFFECTS),
             "amplifier": _B(rng.randint(0, 2)),
             "duration": rng.randint(100, 600)}
            for _ in range(rng.randint(1, 2))]
        if rng.random() < 0.40:
            pc["custom_color"] = rng.randint(0, 0xFFFFFF)
    ent["potion_contents"] = pc
    if rng.random() < 0.30:
        ent["DurationOnUse"] = _F(round(rng.uniform(-1.0, 1.0), 1))
    return ent


def _gen_boat_entity(rng):
    """minecraft:<wood>_boat — лёгкий NBT (только поворот)."""
    return {"id": _boat_entity_id(rng, chest=False),
            "Rotation": [_F(round(rng.uniform(0.0, 360.0), 1)), _F(0.0)]}


def _gen_minecart_entity(rng):
    """minecraft:minecart — лёгкий NBT (только поворот)."""
    return {"id": "minecraft:minecart",
            "Rotation": [_F(round(rng.uniform(0.0, 360.0), 1)), _F(0.0)]}


def _gen_wind_charge_entity(rng):
    """minecraft:wind_charge — без NBT (редкий тип)."""
    return {"id": "minecraft:wind_charge"}


# Диспетчер спец-типов: ключ SPAWNER_SPECIAL_WEIGHTS → генератор
_SPECIAL_ENTITY_GENS = {
    "item": _gen_item_entity,
    "armor_stand": _gen_armor_stand_entity,
    "tnt": _gen_tnt_entity,
    "falling_block": _gen_falling_block_entity,
    "experience_orb": _gen_experience_orb_entity,
    "chest_boat": lambda rng: _gen_container_entity(
        rng, _boat_entity_id(rng, chest=True)),
    "chest_minecart": lambda rng: _gen_container_entity(
        rng, "minecraft:chest_minecart"),
    "item_frame": lambda rng: _gen_item_frame_entity(
        rng, "minecraft:item_frame"),
    "glow_item_frame": lambda rng: _gen_item_frame_entity(
        rng, "minecraft:glow_item_frame"),
    "firework_rocket": _gen_firework_entity,
    "area_effect_cloud": _gen_aec_entity,
    "boat": _gen_boat_entity,
    "minecart": _gen_minecart_entity,
    "wind_charge": _gen_wind_charge_entity,
}


def _rand_special_entity(rng):
    """Сущность спец-типа для спавнера: взвешенный выбор типа из
    SPAWNER_SPECIAL_WEIGHTS + собственный NBT-генератор."""
    kind = _weighted_choice(rng, SPAWNER_SPECIAL_WEIGHTS)
    return _SPECIAL_ENTITY_GENS[kind](rng)


def _rand_spawner_mob(rng):
    """Моб для спавнера — СМЕСЬ NBT-глубины (решение юзера):
    40% вообще без NBT (просто тип), 40% лёгкий (CustomName или
    Health), 20% полный (генератор «особого» моба: атрибуты/
    снаряжение/DeathLootTable...; loot_alloc=None → ванильная
    таблица моба как fallback)."""
    mob = rng.choice(STRUCTURE_MOBS)
    r = rng.random()
    if r < 0.40:
        return {"id": "minecraft:" + mob}
    if r < 0.80:
        ent = {"id": "minecraft:" + mob}
        if rng.random() < 0.5:
            ent["CustomName"] = _rand_text_component(rng, _rand_mob_name(rng))
            if rng.random() < 0.6:
                ent["CustomNameVisible"] = _B(1)
        else:
            # выше max_health движок молча клампит — безопасно
            ent["Health"] = _F(round(rng.uniform(5.0, 30.0), 1))
        if rng.random() < 0.15:
            ent["Glowing"] = _B(1)
        return ent
    return _rand_mob_nbt_full(rng, mob, None)


def _rand_spawner_entity(rng):
    """Сущность для SpawnData спавнера: мобы (SPAWNER_MOB_SHARE=85%)
    или спец-тип (15%: item/tnt/лодки/фейерверк/...)."""
    if rng.random() < SPAWNER_MOB_SHARE:
        return _rand_spawner_mob(rng)
    return _rand_special_entity(rng)


def _rand_spawner_nbt(rng):
    """mob_spawner данжа с ОСОБОЙ сущностью — моб или спец-тип (см.
    _rand_spawner_entity). Формат сверен с ванильным bastion/treasure/
    bases/lava_basin.nbt; числовые поля — SHORT (BaseSpawner 26.2
    пишет их putShort'ом). Спавнер «быстрый» (решение юзера):
    MinSpawnDelay 40-100, MaxSpawnDelay 120-240 (диапазоны гарантируют
    max > min: min <= 100 < 120 <= max), SpawnCount 3-5,
    MaxNearbyEntities 6-9, RequiredPlayerRange 24-32 (не больше 32),
    SpawnRange 4-6."""
    spawn_data = {"entity": _rand_spawner_entity(rng)}
    return {
        "id": "minecraft:mob_spawner",
        "Delay": _S(0),
        "MinSpawnDelay": _S(rng.randint(40, 100)),
        "MaxSpawnDelay": _S(rng.randint(120, 240)),
        "SpawnCount": _S(rng.randint(3, 5)),
        "MaxNearbyEntities": _S(rng.randint(6, 9)),
        "RequiredPlayerRange": _S(rng.randint(24, 32)),
        "SpawnRange": _S(rng.randint(4, 6)),
        "SpawnData": spawn_data,
        "SpawnPotentials": [{"data": spawn_data, "weight": 1}],
    }


def _ts_pairs(trial_spawner_ids):
    """Пары (normal, ominous) id конфигов trial_spawner по суффиксу "_om"
    (конвенция gen_trial_spawners: "<ns>:<name>_tsN" + "..._tsN_om").
    Конфиг без пары используется как свой own ominous — это валидно,
    normal_config/ominous_config принимают любой id реестра."""
    ids = [i for i in (trial_spawner_ids or []) if i]
    normals = [i for i in ids if not i.endswith("_om")]
    return [(i, (i + "_om" if i + "_om" in ids else i)) for i in normals]


def _rand_trial_spawner_nbt(rng, normal_id, ominous_id):
    """NBT блочного энтити trial_spawner для .nbt-шаблона. Формат сверен
    с ванильными trial_chambers/spawner/*.nbt (14 шаблонов в jar):
    {id, normal_config, ominous_config} — ссылки на реестр
    data/<ns>/trial_spawner/. Доп. поля из TrialSpawner$FullConfig.
    MAP_CODEC (байткод): target_cooldown_length (неотр. int, деф. 36000),
    required_player_range (intRange, деф. 14)."""
    nbt = {"id": "minecraft:trial_spawner",
           "normal_config": normal_id,
           "ominous_config": ominous_id}
    if rng.random() < 0.3:
        nbt["target_cooldown_length"] = rng.choice(
            [1200, 6000, 12000, 36000, 72000])
    if rng.random() < 0.25:
        nbt["required_player_range"] = rng.randint(8, 24)
    return nbt


def _rand_vault_nbt(rng, loot_alloc):
    """NBT блочного энтити vault. Формат сверен с ванильными
    trial_chambers/reward/{vault,ominous_vault}.nbt: config инлайново
    (VaultConfig.CODEC, байткод: loot_table / key_item (ItemStack) /
    activation_range / deactivation_range — double, deact >= act).
    key_item: trial_key / ominous_trial_key (тогда рядом нужен спавнер —
    ключ выпадает из него) или случайный предмет (волт-загадка).
    loot_alloc — счётчик LootSlots: каждому волту СВОЯ уникальная
    таблица (None → ванильная trial_chambers/reward)."""
    r = rng.random()
    if r < 0.5:
        key = {"id": "minecraft:trial_key", "count": 1}
    elif r < 0.75:
        key = {"id": "minecraft:ominous_trial_key", "count": 1}
    else:
        key = {"id": rng.choice(WEAPON_ITEMS + ARMOR_ITEMS),
               "count": rng.randint(1, 3)}
    cfg = {
        "loot_table": (loot_alloc.take() if loot_alloc is not None else
                       "minecraft:chests/trial_chambers/reward"),
        "key_item": key,
    }
    if rng.random() < 0.2:
        act = round(rng.uniform(3.0, 8.0), 1)
        cfg["activation_range"] = act
        cfg["deactivation_range"] = round(
            act + rng.uniform(0.5, 3.0), 1)   # deact >= act (validate)
    return {"id": "minecraft:vault", "config": cfg}


def _place_vault(rng, blocks, pal, loot_alloc, cell, nbt=None, stand_y=1):
    """Поставить блок vault на клетку (x, z) на уровне stand_y (по умолч.
    1 — на полу), замещая при необходимости сундук. Свойства блока — как
    в ванильных trial_chambers/reward/*.nbt (facing/vault_state/ominous;
    ominous согласован с ключом). nbt — готовый _rand_vault_nbt (иначе
    новый с loot_alloc)."""
    if nbt is None:
        nbt = _rand_vault_nbt(rng, loot_alloc)
    ominous = (nbt["config"]["key_item"]["id"] ==
               "minecraft:ominous_trial_key")
    x, z = cell
    state = {"Name": "minecraft:vault",
             "Properties": {"facing": rng.choice(
                 ["north", "south", "east", "west"]),
                 "vault_state": "inactive",
                 "ominous": "true" if ominous else "false"}}
    for blk in blocks:
        if blk["pos"][0] == x and blk["pos"][1] == stand_y \
                and blk["pos"][2] == z:
            # замещаем сундук? его слот лута больше никем не используется —
            # освобождаем (волт несёт СВОЮ таблицу, взятую выше)
            if loot_alloc is not None:
                old = blk.get("nbt") or {}
                loot_alloc.release(old.get("LootTable", ""))
            blk["state"] = pal(state)
            blk["nbt"] = nbt
            return True
    # блок не нашёлся: слот, взятый для nbt, остался без ссылки — вернуть
    if loot_alloc is not None:
        loot_alloc.release(nbt["config"]["loot_table"])
    return False


def _rand_mob_nbt_full(rng, mob, loot_alloc):
    """Полный NBT «особого» моба для entities[] .nbt-шаблона и полного
    варианта моба спавнера. mob — конкретный тип из STRUCTURE_MOBS;
    набор полей случаен: не каждому мобу всё сразу. loot_alloc —
    счётчик LootSlots: DeathLootTable каждого моба СВОЯ уникальная
    таблица (None → ванильная entities/<mob>, если она есть)."""
    nbt = {"id": "minecraft:" + mob}

    # имя (NBT-нативный текстовый компонент, ComponentSerialization.CODEC)
    if rng.random() < 0.9:
        nbt["CustomName"] = _rand_text_component(rng, _rand_mob_name(rng))
        if rng.random() < 0.7:
            nbt["CustomNameVisible"] = _B(1)

    # атрибуты: attributes:[{id, base}] — формат AttributeInstance$Packed;
    # отсутствующие у моба атрибуты при загрузке молча пропускаются
    attrs = []
    max_health = None
    for aid in rng.sample(sorted(ATTRIBUTE_RANGES), rng.randint(1, 3)):
        lo, hi = ATTRIBUTE_RANGES[aid]
        base = round(rng.uniform(lo, hi), 2)
        if aid == "minecraft:max_health":
            max_health = base
        attrs.append({"id": aid, "base": base})
    if max_health is None and rng.random() < 0.6:
        max_health = round(rng.uniform(10.0, 60.0), 1)
        attrs.append({"id": "minecraft:max_health", "base": max_health})
    nbt["attributes"] = attrs
    if max_health is not None:
        # Health — float и не выше max_health (иначе движок клампит)
        nbt["Health"] = _F(max_health)

    # экипировка: equipment:{<слот>:{id,count,components}} (EntityEquipment.
    # CODEC = unboundedMap(EquipmentSlot, ItemStack)); drop_chances —
    # отдельный map слот->float (DropChances.CODEC). Броня — строго по
    # слоту (см. _rand_item_stack)
    equip = {}
    if rng.random() < 0.55:
        equip["mainhand"] = _rand_item_stack(rng, "weapon")
    if rng.random() < 0.15:
        equip["offhand"] = _rand_item_stack(rng, "any")
    for slot in ("head", "chest", "legs", "feet"):
        if rng.random() < 0.35:
            equip[slot] = _rand_item_stack(rng, "armor", slot)
    if equip:
        nbt["equipment"] = equip
        if rng.random() < 0.6:
            nbt["drop_chances"] = {
                slot: _F(round(rng.uniform(0.0, 1.0), 3))
                for slot in rng.sample(sorted(equip),
                                       rng.randint(1, len(equip)))}

    # DeathLootTable (тег моба, Mob.class): свой уникальный слот или
    # ванильная entities/<mob>, если она существует
    if rng.random() < 0.8:
        if loot_alloc is not None:
            nbt["DeathLootTable"] = loot_alloc.take()
        elif mob in MOB_LOOT_TABLES:
            nbt["DeathLootTable"] = "minecraft:entities/" + mob

    # прочие флаги (каждый — со своим шансом). NoAI/Invulnerable НЕ
    # генерируются ВООБЩЕ: мобы должны жить своей жизнью и быть уязвимыми
    if rng.random() < 0.6:
        nbt["PersistenceRequired"] = _B(1)
    if rng.random() < 0.25:
        nbt["Glowing"] = _B(1)
    if rng.random() < 0.10:
        nbt["Fire"] = _S(rng.choice([-1, 20, 60, 100]))  # short (getShort)
    if rng.random() < 0.15:
        nbt["CanPickUpLoot"] = _B(1)
    if rng.random() < 0.10:
        nbt["LeftHanded"] = _B(1)
    if rng.random() < 0.05:
        nbt["Silent"] = _B(1)
    # поворот (yaw, pitch) — float
    nbt["Rotation"] = [_F(round(rng.uniform(0.0, 360.0), 1)), _F(0.0)]
    return nbt


def _rand_mob_nbt(rng, loot_alloc):
    """Полный NBT случайного «особого» моба (для entities[] шаблонов
    и gen_jigsaw): тип выбирается из STRUCTURE_MOBS, содержимое —
    _rand_mob_nbt_full."""
    return _rand_mob_nbt_full(rng, rng.choice(STRUCTURE_MOBS), loot_alloc)


# Планировки своих .nbt-шаблонов (смешиваются с ванильными в пулы):
# hut — хижина с дверью/окнами/крышей; ruin — рваные стены без крыши,
# обломки; tower — башенка с лестницей и площадкой наверху; platform —
# помост на сваях с перилами (этаж декора — над землёй); shrine —
# открытый павильон с колоннами и крышей-плитой
_NBT_LAYOUTS = ("hut", "ruin", "tower", "platform", "shrine")


def _rand_nbt_template(rng, loot_alloc, trial_spawner_ids=None, kind=None):
    """СВОЙ шаблон постройки (gzip-NBT, как ванильные .nbt): маленькое
    здание из случайных полных блоков (5 планировок — см. _NBT_LAYOUTS),
    со случайными сундуками и (с шансом ~40-70%) 1-3 особыми мобами.
    kind — планировка (None → случайная). Возвращает bytes gzip-NBT для
    data/<ns>/structure/<ключ>.nbt.

    loot_alloc — счётчик LootSlots: каждый сундук/волт/моб шаблона
    занимает СВОЙ уникальный слот лут-таблицы (None → ванильские
    fallback-таблицы). Материалы — только gd.PALETTE_BLOCKS: стены/пол
    заливаются массово, block-entity блоки (spawner/copper_golem_statue/
    chest/...) недопустимы (жалоба: данж со стенами из медных статуй
    грузил FPS).

    trial_spawner_ids — список id конфигов trial_spawner вида "ns:name_tsN"
    (пары normal/ominous по суффиксу "_om", см. gen_trial_spawners.py).
    Если список не пуст, «особый» блок в центре постройки выбирается из
    ~20% mob_spawner / ~25% trial_spawner / ~25% vault (волт с ключом
    trial_key ставится ПАРОЙ со спавнером — ключ выпадает из спавнера
    через loot_tables_to_eject) / ~30% ничего. None/пусто — прежнее
    поведение (только ~18% mob_spawner)."""
    gd = _gd()
    solid = gd.PALETTE_BLOCKS
    if kind is None:
        kind = rng.choice(_NBT_LAYOUTS)

    # материалы: пол / стены / колонны (полные кубы из PALETTE_BLOCKS —
    # безопасные для массовой заливки, без block entity)
    floor_b = rng.choice(solid)
    wall_b = rng.choice(solid)
    col_b = rng.choice(solid)
    air_state = {"Name": "minecraft:air"}

    palette = []          # список {Name, Properties}
    pal_idx = {}          # ключ (Name, frozenset(props)) -> индекс

    def pal(state):
        key = (state.get("Name"),
               tuple(sorted((state.get("Properties") or {}).items())))
        if key not in pal_idx:
            pal_idx[key] = len(palette)
            palette.append(state)
        return pal_idx[key]

    floor_i = pal(gd.block_state(floor_b))
    wall_i = pal(gd.block_state(wall_b))
    col_i = pal(gd.block_state(col_b))
    air_i = pal(air_state)
    ladder_i = pal({"Name": "minecraft:ladder",
                    "Properties": {"facing": "east",
                                   "waterlogged": "false"}})

    blocks = []
    chest_cells = []      # (x, z) для сундуков
    interior_cells = []   # (x, z) клетки уровня декора
    occupied = set()      # клетки с обломками (мобам не место)
    stand_y = 1           # уровень, где стоят сундуки/мобы/особый блок

    if kind == "hut":
        # хижина: дверь в случайной стене, окна, иногда крыша
        sx, sz = rng.randint(5, 9), rng.randint(5, 9)
        h = rng.randint(3, 6)
        has_roof = rng.random() < 0.6
        door_side = rng.randrange(4)
        door_pos = None
        if h >= 3:
            dx, dz = rng.randint(1, sx - 2), rng.randint(1, sz - 2)
            if door_side == 0:
                door_pos = (dx, 0)
            elif door_side == 1:
                door_pos = (dx, sz - 1)
            elif door_side == 2:
                door_pos = (0, dz)
            else:
                door_pos = (sx - 1, dz)
        for y in range(h):
            for x in range(sx):
                for z in range(sz):
                    corner = x in (0, sx - 1) and z in (0, sz - 1)
                    edge = x in (0, sx - 1) or z in (0, sz - 1)
                    if y == 0:
                        state = floor_i                  # пол
                    elif has_roof and y == h - 1:
                        state = floor_i if rng.random() < 0.5 else wall_i
                    elif corner and (has_roof or y < h - 1):
                        state = col_i                    # колонны по углам
                    elif edge and y <= h - 2:
                        # стены; окна и дверь — «дыры»
                        if (door_pos and (x, z) == door_pos and y in (1, 2)):
                            state = air_i
                        elif y >= 1 and rng.random() < 0.15:
                            state = air_i                # окно/разрушение
                        else:
                            state = wall_i
                    else:
                        state = air_i                   # интерьер
                    blocks.append({"pos": [x, y, z], "state": state})
                    if y == 1 and not edge:
                        interior_cells.append((x, z))
    elif kind == "ruin":
        # руина: у каждой колонки периметра случайная высота + эрозия,
        # крыши нет, обломки на полу
        sx, sz = rng.randint(7, 11), rng.randint(7, 11)
        h = rng.randint(3, 5)
        colh = {}
        for x in range(sx):
            for z in range(sz):
                if x in (0, sx - 1) or z in (0, sz - 1):
                    colh[(x, z)] = (h - 1 if rng.random() < 0.55
                                    else rng.randint(0, h - 1))
        for y in range(h):
            for x in range(sx):
                for z in range(sz):
                    edge = x in (0, sx - 1) or z in (0, sz - 1)
                    corner = x in (0, sx - 1) and z in (0, sz - 1)
                    if y == 0:
                        state = floor_i
                    elif edge and y <= colh[(x, z)]:
                        state = ((col_i if corner else wall_i)
                                 if rng.random() > 0.08 else air_i)
                    else:
                        state = air_i
                    blocks.append({"pos": [x, y, z], "state": state})
                    if y == 1 and not edge:
                        interior_cells.append((x, z))
        for _ in range(rng.randint(2, 4)):    # обломки (центр — особый блок)
            x, z = rng.randint(1, sx - 2), rng.randint(1, sz - 2)
            if (x, z) == (sx // 2, sz // 2):
                continue
            for blk in blocks:
                if blk["pos"] == [x, 1, z]:
                    blk["state"] = col_i
                    occupied.add((x, z))
                    break
    elif kind == "tower":
        # башенка: угловые колонны, бойницы, лестница у стены — сквозь
        # дыру в площадке наверху; перила по периметру площадки
        s = rng.randint(5, 7)
        sx = sz = s
        h = rng.randint(9, 12)
        lz = rng.randint(1, s - 2)
        rail = set()
        for x in range(0, s, 2):
            rail.add((x, 0))
            rail.add((x, s - 1))
        for z in range(2, s - 1, 2):
            rail.add((0, z))
            rail.add((s - 1, z))
        for y in range(h):
            for x in range(s):
                for z in range(s):
                    edge = x in (0, s - 1) or z in (0, s - 1)
                    corner = x in (0, s - 1) and z in (0, s - 1)
                    if y == 0:
                        state = floor_i
                    elif y == h - 2:      # площадка (дыра — над лестницей)
                        state = ladder_i if (x, z) == (1, lz) else floor_i
                    elif y == h - 1:      # перила
                        state = col_i if (x, z) in rail else air_i
                    elif corner:
                        state = col_i
                    elif edge:
                        state = (wall_i if (y < 3 or rng.random() > 0.06)
                                 else air_i)              # бойницы
                    elif (x, z) == (1, lz) and y <= h - 3:
                        state = ladder_i                  # лестница у стены
                    else:
                        state = air_i
                    blocks.append({"pos": [x, y, z], "state": state})
                    if y == 1 and not edge:
                        interior_cells.append((x, z))
        if rng.random() < 0.40:           # сундук на площадке
            for blk in blocks:
                if blk["pos"] == [s - 2, h - 1, s - 2]:
                    blk["state"] = pal({
                        "Name": "minecraft:chest",
                        "Properties": {"facing": "west", "type": "single",
                                       "waterlogged": "false"}})
                    blk["nbt"] = dict(_rand_chest_nbt(rng, loot_alloc),
                                      id="minecraft:chest")
                    break
    elif kind == "platform":
        # помост на сваях: этаж декора — над землёй (stand_y = k+1)
        sx, sz = rng.randint(7, 11), rng.randint(7, 11)
        k = rng.randint(3, 5)
        h = k + 2
        stand_y = k + 1
        legs = ((1, 1), (sx - 2, 1), (1, sz - 2), (sx - 2, sz - 2),
                (sx // 2, 1), (sx // 2, sz - 2),
                (1, sz // 2), (sx - 2, sz // 2))
        for y in range(h):
            for x in range(sx):
                for z in range(sz):
                    edge = x in (0, sx - 1) or z in (0, sz - 1)
                    if y < k:
                        state = col_i if (x, z) in legs else air_i
                    elif y == k:
                        state = floor_i                  # помост
                    else:                                # y == k+1: перила
                        state = (col_i if edge and (x + z) % 2 == 0
                                 else air_i)
                    blocks.append({"pos": [x, y, z], "state": state})
                    if y == stand_y and 1 <= x <= sx - 2 \
                            and 1 <= z <= sz - 2:
                        interior_cells.append((x, z))
    else:  # shrine
        # павильон: колонны по углам (и серединам при s=7), крыша-плита,
        # стороны открыты
        s = rng.choice([5, 7])
        sx = sz = s
        h = rng.choice([4, 5, 6])
        cols = ((0, 0), (s - 1, 0), (0, s - 1), (s - 1, s - 1))
        if s == 7:
            cols += ((3, 0), (3, 6), (0, 3), (6, 3))
        for y in range(h):
            for x in range(s):
                for z in range(s):
                    if y == 0:
                        state = floor_i
                    elif y == h - 1:
                        state = wall_i                    # крыша-плита
                    elif (x, z) in cols:
                        state = col_i
                    else:
                        state = air_i
                    blocks.append({"pos": [x, y, z], "state": state})
                    if y == 1 and (x, z) not in cols:
                        interior_cells.append((x, z))

    # сундуки/бочки: 0-2, на клетках уровня декора у края
    rng.shuffle(interior_cells)
    near_wall = [(x, z) for (x, z) in interior_cells
                 if x == 1 or x == sx - 2 or z == 1 or z == sz - 2]
    n_chests = min(len(near_wall), 0 if rng.random() < 0.2 else rng.randint(1, 2))
    for (x, z) in near_wall[:n_chests]:
        if rng.random() < 0.35:
            state = {"Name": "minecraft:barrel",
                     "Properties": {"facing": "up", "open": "false"}}
            be_nbt = dict(_rand_chest_nbt(rng, loot_alloc),
                          id="minecraft:barrel")
        else:
            state = {"Name": "minecraft:chest",
                     "Properties": {"facing": rng.choice(
                         ["north", "south", "east", "west"]),
                         "type": "single", "waterlogged": "false"}}
            be_nbt = dict(_rand_chest_nbt(rng, loot_alloc),
                          id="minecraft:chest")
        for blk in blocks:
            if blk["pos"][0] == x and blk["pos"][1] == stand_y \
                    and blk["pos"][2] == z:
                blk["state"] = pal(state)
                blk["nbt"] = be_nbt
                break
        chest_cells.append((x, z))

    entities = []
    # «особый» блок постройки (в центре, на полу). С конфигами trial_spawner:
    # ~20% mob_spawner / ~25% trial_spawner / ~25% vault / ~30% ничего;
    # без конфигов — прежние ~18% mob_spawner.
    ts_pairs = _ts_pairs(trial_spawner_ids)
    special = None
    if sx >= 5 and sz >= 5:
        if ts_pairs:
            r = rng.random()
            if r < 0.20:
                special = "spawner"
            elif r < 0.45:
                special = "trial"
            elif r < 0.70:
                special = "vault"
        elif rng.random() < 0.18:
            special = "spawner"
    if special == "spawner":
        cx, cz = sx // 2, sz // 2
        for blk in blocks:
            if blk["pos"][0] == cx and blk["pos"][1] == stand_y \
                    and blk["pos"][2] == cz:
                # центр мог занять сундук — его слот лута освобождаем
                if loot_alloc is not None:
                    loot_alloc.release(
                        (blk.get("nbt") or {}).get("LootTable", ""))
                blk["state"] = pal({"Name": "minecraft:spawner"})
                blk["nbt"] = _rand_spawner_nbt(rng)
                break
    elif special == "trial":
        # trial_spawner: блок + ссылки normal_config/ominous_config на наши
        # конфиги (формат = ванильные trial_chambers/spawner/*.nbt);
        # properties — как в ванильных шаблонах
        normal_id, ominous_id = rng.choice(ts_pairs)
        cx, cz = sx // 2, sz // 2
        for blk in blocks:
            if blk["pos"][0] == cx and blk["pos"][1] == stand_y \
                    and blk["pos"][2] == cz:
                # центр мог занять сундук — его слот лута освобождаем
                if loot_alloc is not None:
                    loot_alloc.release(
                        (blk.get("nbt") or {}).get("LootTable", ""))
                blk["state"] = pal({
                    "Name": "minecraft:trial_spawner",
                    "Properties": {"ominous": "false",
                                   "trial_spawner_state":
                                       "waiting_for_players"}})
                blk["nbt"] = _rand_trial_spawner_nbt(rng, normal_id,
                                                     ominous_id)
                break
        # если спавнер есть — сундук иногда заменяем на волт: спавнер даст
        # ключ (loot_tables_to_eject в config), волт — награду (ПАРА)
        if chest_cells and rng.random() < 0.5:
            _place_vault(rng, blocks, pal, loot_alloc,
                         rng.choice(chest_cells), stand_y=stand_y)
    elif special == "vault":
        # волт; с trial_key/ominous_trial_key — обязательно ПАРОЙ со
        # спавнером (иначе ключ не достать), со случайным предметом — соло
        v_nbt = _rand_vault_nbt(rng, loot_alloc)
        key_id = v_nbt["config"]["key_item"]["id"]
        if key_id in ("minecraft:trial_key", "minecraft:ominous_trial_key"):
            normal_id, ominous_id = rng.choice(ts_pairs)
            cx, cz = sx // 2, sz // 2
            for blk in blocks:
                if (blk["pos"][0] == cx and blk["pos"][1] == stand_y
                        and blk["pos"][2] == cz):
                    # центр мог занять сундук — его слот лута освобождаем
                    if loot_alloc is not None:
                        loot_alloc.release(
                            (blk.get("nbt") or {}).get("LootTable", ""))
                    blk["state"] = pal({
                        "Name": "minecraft:trial_spawner",
                        "Properties": {"ominous": "false",
                                       "trial_spawner_state":
                                           "waiting_for_players"}})
                    blk["nbt"] = _rand_trial_spawner_nbt(rng, normal_id,
                                                         ominous_id)
                    break
        # сам волт — на клетке сундука (замещаем его) или у стены
        v_cells = [c for c in near_wall if c not in chest_cells]
        v_cells = v_cells or chest_cells or interior_cells
        if v_cells:
            _place_vault(rng, blocks, pal, loot_alloc, rng.choice(v_cells),
                         nbt=v_nbt, stand_y=stand_y)
        else:
            # поставить волт некуда — слот, взятый для него, освобождаем
            if loot_alloc is not None:
                loot_alloc.release(v_nbt["config"]["loot_table"])

    # особые мобы: ~40-70% шаблонов содержат 1-3
    mob_chance = rng.uniform(0.4, 0.7)
    if rng.random() < mob_chance and interior_cells:
        free = [(x, z) for (x, z) in interior_cells
                if (x, z) not in chest_cells and (x, z) not in occupied
                and (x, z) != (sx // 2, sz // 2)]
        for (x, z) in rng.sample(free, min(len(free), rng.randint(1, 3))):
            entities.append({
                "pos": [x + 0.5, float(stand_y), z + 0.5],  # List<Double>
                "blockPos": [x, stand_y, z],               # List<Int>
                "nbt": _rand_mob_nbt(rng, loot_alloc),
            })

    root = {
        "size": [sx, h, sz],
        "entities": entities,
        "blocks": blocks,
        "palette": palette,
        "DataVersion": DATA_VERSION,
    }
    return _nbt_bytes(root)


# ---------------------------------------------------------------------------
# Главная функция генерации структур
# ---------------------------------------------------------------------------

def rand_structures(rng, ns, name, min_y, max_y, biome_ids, count=None,
                    loot_alloc=None, trial_spawner_ids=None, has_ceiling=False,
                    roof_bottom=None):
    """Случайные структуры 15 из 16 типов 26.2 (ocean_monument исключён —
    всегда empty), привязанные к биомам ЭТОГО измерения, плюс:
      * ФОРКИ ванильных jigsaw-структур (~35% структур, VANILLA_JIGSAW_FORKS):
        деревни/бастион/древний город/trial chambers/... ЦЕЛИКОМ — start_pool
        ванильный, параметры случайные (size до 20 — огромные деревни);
      * свои jigsaw-данжи из СВОИХ .nbt-шаблонов с особыми мобами
        (отдельные ванильные куски в свои пулы НЕ подмешиваются).

    biome_ids — список ID биомов измерения; count — сколько структур
    создать (по умолчанию 0-3 — старое поведение; вызывается с числом из
    тяжело-хвостового распределения). loot_alloc — общий на измерение
    счётчик LootSlots: каждый сундук/бочка/волт/моб .nbt-шаблонов
    занимает СВОЙ уникальный слот "<ns>:<name>_lootN" (None → ванильные
    chest-таблицы и entities/<mob>); итоговое число занятых ЭТИМ вызовом
    слотов возвращается в ключе "loot_slots".
    trial_spawner_ids — опциональный список id конфигов trial_spawner
    (реестр data/<ns>/trial_spawner/, генерирует gen_trial_spawners.py):
    тогда в .nbt-постройках появляются блоки trial_spawner и vault
    (пара спавнер+волт); None/пусто → прежнее поведение (только
    mob_spawner). has_ceiling — мир с кровлей (запрещает
    project_start_to_heightmap: WORLD_SURFACE_WG там = крыша);
    roof_bottom — нижняя граница кровли (Y): jigsaw-старты не выше
    roof_bottom-24, чтобы куски не пересекали потолок мира.
    Возвращает dict с ключами "structures",
    "structure_sets", "template_pools", "processor_lists", "biome_tags",
    "nbt_files" (ключи nbt_files — пути относительно data/<ns>/structure/
    без расширения, значения — bytes gzip-NBT; файл <ключ>.nbt доступен
    из пулов как "<ns>:<ключ>") и "loot_slots" (int)."""
    gd = _gd()
    biome_ids = list(biome_ids) or ["minecraft:plains"]
    trial_spawner_ids = [t for t in (trial_spawner_ids or []) if t]
    _slots0 = loot_alloc.count if loot_alloc is not None else 0
    result = {"structures": {}, "structure_sets": {}, "template_pools": {},
              "processor_lists": {}, "biome_tags": {}, "nbt_files": {}}

    n = count if count is not None else rng.randint(0, 3)
    result["loot_slots"] = 0
    if n <= 0:
        return result

    # Свои .nbt-шаблоны (постройки с особыми мобами/сундуками) — ЛЕНИВО,
    # при первом СВОЁМ jigsaw (куски своих пулов — только свои .nbt):
    # 4-14 штук с планировками hut/ruin/tower/platform/shrine. Раньше их
    # генерировали заранее с шансом 85% и подмешивали в пулы к ванильным
    # кускам — теперь ванильских кусков в своих пулах нет (решение юзера:
    # «один дом а не целиком деревня — кринж»), а без своего jigsaw они
    # и не нужны вовсе (форкам — тоже: у них ванильные start_pool).
    own_keys = []

    def _gen_own_templates():
        for _ in range(rng.randint(4, 14)):
            kind = rng.choice(_NBT_LAYOUTS)
            key = "%s/%s%d" % (name, kind, len(result["nbt_files"]) + 1)
            result["nbt_files"][key] = _rand_nbt_template(
                rng, loot_alloc, trial_spawner_ids, kind=kind)
            own_keys.append("%s:%s" % (ns, key))

    # пул не-jigsaw типов ПОД ИЗМЕРЕНИЕ: woodland_mansion/end_city требуют
    # АБСОЛЮТНУЮ высоту getLowestY >= 60 (бокс 5x5 чанков) — при max_y < 100
    # рельеф туда не дотягивается, структуры ВСЕГДА empty (аудит)
    non_jigsaw = ([t for t in NON_JIGSAW_TYPES if t not in Y_GATED_TYPES]
                  if max_y < 100 else NON_JIGSAW_TYPES)

    struct_ids = []
    struct_biomes = []   # biomes_ref каждой структуры (для structure_set)
    n_jigsaw = 0         # все jigsaw (свои + форки)
    n_forks = 0          # из них форки ванильных структур
    for i in range(n):
        num = i + 1
        sid = "%s:%s_str%d" % (ns, name, num)
        struct_ids.append(sid)

        # тип структуры: ~35% — ФОРК ванильной jigsaw-структуры (деревня/
        # бастион/древний город/trial chambers/... ЦЕЛИКОМ, параметры
        # случайны — например огромные деревни size 13-20); из остальных
        # 40% jigsaw (свои .nbt-пулы) / 60% прочие типы равновероятно
        fork = None
        if rng.random() < FORK_SHARE:
            fork = rng.choice(_FORK_CHOICES)
            stype = JIGSAW_TYPE
        elif rng.random() < 0.40:
            stype = JIGSAW_TYPE
        else:
            stype = rng.choice(non_jigsaw)

        # привязка к биомам измерения: СВОИ биомы у каждой структуры —
        # сэмпл 2-5 биомов (было 1-3: маленькие сэмплы часто целиком
        # попадали в биомы, не выигрывающие Voronoi, — площадь ~0,
        # аудит находимости). Первая структура — ЯКОРНАЯ: ей ВСЕ биомы
        # измерения; климат (continentalness) в модуль не передаётся, а
        # крупнейшие по площади биомы — «центральные» кластера (ближайшие
        # к медиане continentalness 0), поэтому полный охват — единственная
        # ГАРАНТИЯ, что хотя бы одна структура измерения их получает
        if num == 1:
            tag_name = "has_structure/%s_str%d" % (name, num)
            result["biome_tags"][tag_name] = {"values": sorted(biome_ids)}
            biomes_ref = "#%s:%s" % (ns, tag_name)
        elif rng.random() < 0.55:
            tag_name = "has_structure/%s_str%d" % (name, num)
            k = min(len(biome_ids), rng.randint(2, 5))
            result["biome_tags"][tag_name] = {
                "values": sorted(rng.sample(biome_ids, k))}
            biomes_ref = "#%s:%s" % (ns, tag_name)
        else:
            k = min(len(biome_ids), rng.randint(2, 5))
            biomes_ref = sorted(rng.sample(biome_ids, k))
        struct_biomes.append(biomes_ref)

        if fork is not None:
            # ФОРК ванильной jigsaw-структуры: start_pool ванильный — свои
            # пул/процессоры/.nbt не нужны (лут ванильский, зашит в кусках)
            result["structures"][sid] = _rand_fork_structure_json(
                rng, fork, min_y, max_y, biomes_ref,
                has_ceiling=has_ceiling, roof_bottom=roof_bottom)
            n_jigsaw += 1
            n_forks += 1
        else:
            pool_id = "minecraft:empty"
            if stype == JIGSAW_TYPE:
                if not own_keys:      # лениво: свои куски к первому пулу
                    _gen_own_templates()
                pid = "%s:%s/pool%d" % (ns, name, num)
                plid = "%s:%s_proc%d" % (ns, name, num)
                result["processor_lists"][plid] = _rand_processor_list(rng)
                # пул становится start_pool структуры — пустой элемент
                # запрещён; куски — ТОЛЬКО свои .nbt
                result["template_pools"][pid] = _rand_template_pool(
                    rng, plid, own_keys, is_start=True)
                pool_id = pid
                n_jigsaw += 1

            result["structures"][sid] = _rand_structure_json(
                rng, stype, pool_id, min_y, max_y, biomes_ref,
                has_ceiling=has_ceiling, roof_bottom=roof_bottom)

    # structure_set'ы: по одному на структуру, иногда объединяем (как
    # ванильный nether_complexes: fortress + bastion в одном сете;
    # объединённый сет из нескольких структур всегда random_spread).
    # biomes_ref нужен concentric_rings: preferred_biomes = биомы структуры
    if len(struct_ids) > 1 and rng.random() < 0.3:
        ssid = "%s:%s_set1" % (ns, name)
        result["structure_sets"][ssid] = _rand_structure_set_json(
            rng, struct_ids, ns, name, 1, biome_ids, result["biome_tags"])
    else:
        for i, sid in enumerate(struct_ids):
            ssid = "%s:%s_set%d" % (ns, name, i + 1)
            result["structure_sets"][ssid] = _rand_structure_set_json(
                rng, [sid], ns, name, i + 1, biome_ids,
                result["biome_tags"], biomes_ref=struct_biomes[i])
    # сколько слотов лута заняли сундуки/волты/мобы .nbt-шаблонов
    result["loot_slots"] = (loot_alloc.count if loot_alloc is not None
                            else 0) - _slots0
    return result


# ---------------------------------------------------------------------------
# Самопроверка
# ---------------------------------------------------------------------------

def _self_test(seeds=20):
    import gzip as _gz
    import re as _re

    def _anchor_abs(a, lo, hi):
        """Якорь VerticalAnchor -> absolute Y."""
        if "absolute" in a:
            return a["absolute"]
        if "above_bottom" in a:
            return lo + a["above_bottom"]
        return hi - a["below_top"]

    def _sh_max(sh, lo, hi):
        """Максимальный absolute Y из start_height/height (одиночный
        якорь ИЛИ uniform-провайдер из двух якорей)."""
        if "absolute" in sh:
            return sh["absolute"]
        return max(_anchor_abs(sh["min_inclusive"], lo, hi),
                   _anchor_abs(sh["max_inclusive"], lo, hi))

    ok = 0
    total_fk = 0      # суммарно форков по всем сидам (доля ~35%)
    total_str = 0
    for seed in range(1, seeds + 1):
        rng = random.Random(seed)
        min_y = -64
        max_y = 320
        # общий счётчик слотов (как в интеграции из generate_dimension):
        # trial_spawner'ы → структуры; каждый id-ссылка уникальна
        import gen_trial_spawners
        alloc = LootSlots("rndim", "testdim")
        ts_data = gen_trial_spawners.rand_trial_spawners(
            rng, "rndim", "testdim", loot_alloc=alloc)
        ts_ids = sorted(ts_data["trial_spawners"])
        carvers = rand_carvers(rng, "rndim", "testdim", min_y, max_y)
        st = rand_structures(rng, "rndim", "testdim", min_y, max_y,
                             ["rndim:t_b1", "rndim:t_b2"], count=50,
                             loot_alloc=alloc,
                             trial_spawner_ids=ts_ids)
        for obj in list(carvers.values()):
            json.dumps(obj)
        for obj in ts_data["trial_spawners"].values():
            json.dumps(obj)
        n_tr = n_vt = n_pair = 0
        for key, d in st.items():
            if key == "loot_slots":
                assert isinstance(d, int) and d >= 0, key
                continue
            if key == "nbt_files":
                for k, b in d.items():
                    assert isinstance(b, bytes) and b[:2] == bytes((31, 139)), k
                    raw = _gz.decompress(b)   # парсим корень
                    assert raw[0] == 10 and raw[1] == 0 and raw[2] == 0, k
                    # мобы живые и уязвимые: NoAI/Invulnerable запрещены
                    assert b"NoAI" not in raw and b"Invulnerable" not in raw, k
                    has_ts = b"normal_config" in raw
                    has_vt = b"minecraft:vault" in raw
                    has_old = b"SpawnPotentials" in raw
                    if has_ts:
                        n_tr += 1
                        # ссылка на РЕАЛЬНЫЙ наш конфиг (реестр trial_spawner)
                        ids = {i.encode("utf-8") for i in ts_ids}
                        assert any(i in raw for i in ids), k
                    if has_vt:
                        n_vt += 1
                        # ключ trial_key => в той же постройке есть спавнер
                        if b"minecraft:trial_key" in raw:
                            assert has_ts, k
                            n_pair += 1
                    # спавнер и волт не совмещаются со старым mob_spawner
                    assert not (has_ts and has_old), k
                    # УНИКАЛЬНОСТЬ: каждая ссылка на наш лут встречается
                    # в шаблоне ровно один раз (сундук/волт/моб = свой слот)
                    refs = _re.findall(rb"rndim:testdim_loot\d+", raw)
                    assert len(refs) == len(set(refs)), (k, refs)
                continue
            for obj in d.values():
                json.dumps(obj)
        n_str = len(st["structures"])
        types = {}
        for sj in st["structures"].values():
            types[sj["type"]] = types.get(sj["type"], 0) + 1
        n_fk_seed = sum(1 for sj in st["structures"].values()
                        if sj["type"] == JIGSAW_TYPE
                        and sj["start_pool"] in VANILLA_FORK_BY_POOL)
        total_fk += n_fk_seed
        total_str += n_str
        n_rings = sum(1 for s in st["structure_sets"].values()
                      if s["placement"]["type"] == "minecraft:concentric_rings")
        print("seed %2d: carvers=%d structures=%d (jigsaw=%d forks=%d) "
              "sets=%d rings=%d pools=%d procs=%d tags=%d nbt=%d "
              "(trial_spawner=%d vault=%d пар=%d)" % (
                  seed, len(carvers), n_str, types.get("minecraft:jigsaw", 0),
                  n_fk_seed, len(st["structure_sets"]), n_rings,
                  len(st["template_pools"]), len(st["processor_lists"]),
                  len(st["biome_tags"]), len(st["nbt_files"]),
                  n_tr, n_vt, n_pair))
        # инварианты
        for sid, sj in st["structures"].items():
            if sj["type"] == "minecraft:jigsaw":
                # start_pool — ЛИБО свой пул (реестр template_pools), ЛИБО
                # ванильный из таблицы форков (извлечена из jar 26.2)
                assert sj["start_pool"] in st["template_pools"] \
                    or sj["start_pool"] in VANILLA_FORK_BY_POOL, sid
                # (б) size — в диапазоне кодека intRange(0, 20)
                assert 0 <= sj["size"] <= 20, (sid, sj["size"])
                # (в) verifyRange: при адаптации != none md+12 <= 128
                md = sj["max_distance_from_center"]
                if sj.get("terrain_adaptation", "none") != "none":
                    assert md + 12 <= 128, (sid, md)
                else:
                    assert md <= 128, (sid, md)
                if sj["start_pool"] in VANILLA_FORK_BY_POOL:
                    fk = VANILLA_FORK_BY_POOL[sj["start_pool"]]
                    # (а) форк ссылается на РЕАЛЬНЫЙ ванильный start_pool
                    # (таблица = все 10 jigsaw-структур из jar 26.2);
                    # use_expansion_hack — ванильный (апгрейд true роняет
                    # куски YSpan > 16 → дыры)
                    assert sj["use_expansion_hack"] == fk["use_expansion_hack"], sid
                    # именованный якорь старта скопирован (ancient_city:
                    # без city_anchor структура размещается по origin)
                    if fk["start_jigsaw_name"]:
                        assert sj.get("start_jigsaw_name") \
                            == fk["start_jigsaw_name"], sid
                    # (г) алиасы у trial_chambers-форка присутствуют
                    if fk["pool_aliases"]:
                        assert sj.get("pool_aliases") == fk["pool_aliases"], sid
                    else:
                        assert "pool_aliases" not in sj, sid
                    # md-пол 4*size — иначе обрубленное дерево кусков
                    cap = (116 if sj.get("terrain_adaptation", "none") != "none"
                           else 128)
                    assert sj["max_distance_from_center"] \
                        >= min(cap, max(30, 4 * sj["size"])), sid
                    # ванильные dimension_padding / liquid_settings
                    if fk["dimension_padding"] is not None:
                        assert sj["dimension_padding"] == fk["dimension_padding"], sid
                    if fk["liquid_settings"]:
                        assert sj["liquid_settings"] == fk["liquid_settings"], sid
            ref = sj["biomes"]
            if isinstance(ref, str):  # "#ns:tag"
                assert ref[1:] in {"%s:%s" % ("rndim", t)
                                   for t in st["biome_tags"]}, sid
            assert sj["type"] in (
                [JIGSAW_TYPE] + NON_JIGSAW_TYPES), sid
            assert sj.get("terrain_adaptation", "none") in TERRAIN_ADAPTATIONS
        # стартовые высоты ВСЕГДА оставляют запас до потолка мира:
        # jigsaw — 24 (самый высокий кусок) + 10, nether_fossil — 30
        # (якоря above_bottom/below_top раскрываются в те же absolute)
        for sid, sj in st["structures"].items():
            if sj["type"] == JIGSAW_TYPE:
                assert _sh_max(sj["start_height"], min_y, max_y) \
                    <= max_y - 34, sid
            elif sj["type"] == "minecraft:nether_fossil":
                assert _sh_max(sj["height"], min_y, max_y) <= max_y - 30, sid
        # находимость (аудит): каждая структура хотя бы в одном structure_set —
        # иначе она не генерится ВООБЩЕ (баг концентрических колец)
        in_set = set()
        for ss in st["structure_sets"].values():
            for se in ss["structures"]:
                in_set.add(se["structure"])
        assert in_set == set(st["structures"]), "структуры без сета"
        for ssid, ss in st["structure_sets"].items():
            p = ss["placement"]
            if p["type"] == "minecraft:random_spread":
                assert p["separation"] < p["spacing"], ssid
                assert 12 <= p["spacing"] <= 48, ssid
                if "frequency" in p:   # низкая частота = /locate впустую
                    assert 0.3 <= p["frequency"] <= 0.8, ssid
            else:  # concentric_rings: одна структура, те же биомы
                assert 6 <= p["distance"] <= 16, ssid
                assert p["spread"] >= 2, ssid
                assert 8 <= p["count"] <= 48, ssid
                assert len(ss["structures"]) == 1, ssid
                sid0 = ss["structures"][0]["structure"]
                assert p["preferred_biomes"] == \
                    st["structures"][sid0]["biomes"], ssid
        # якорная структура (первая) покрывает ВСЕ биомы измерения —
        # климат в модуль не передаётся, полный охват гарантирует самые
        # крупные «центральные» биомы (continentalness ~ 0) хотя бы одной
        # структуре измерения
        aref = st["structures"]["rndim:testdim_str1"]["biomes"]
        avals = (st["biome_tags"][aref[1:].split(":", 1)[1]]["values"]
                 if isinstance(aref, str) else aref)
        assert avals == sorted(["rndim:t_b1", "rndim:t_b2"]), \
            "якорь не все биомы"
        # сэмплы биомов остальных структур: 2-5 (в тесте биомов всего 2)
        for sid, sj in st["structures"].items():
            if sid == "rndim:testdim_str1":
                continue
            ref = sj["biomes"]
            vals = (st["biome_tags"][ref[1:].split(":", 1)[1]]["values"]
                    if isinstance(ref, str) else ref)
            assert 2 <= len(vals) <= 5, (sid, len(vals))
        # nbt-шаблоны адресуются пулами корректно; в стартовых пулах
        # (все наши — стартовые) нет пустых элементов
        own = {"rndim:%s" % k for k in st["nbt_files"]}
        for pid, pool in st["template_pools"].items():
            for el in pool["elements"]:
                loc = el["element"].get("location")
                # (д) в своих пулах — ТОЛЬКО свои .nbt: ни одного ванильского
                # куска (NBT_LOCATIONS) и вообще никаких чужих путей —
                # отдельные ванильские дома давали «обрубки» структур
                if loc is not None:
                    assert loc in own, (pid, loc)
                    assert loc not in NBT_LOCATIONS, (pid, loc)
                assert el["element"]["element_type"] != \
                    "minecraft:empty_pool_element", pid
        # block_rot всегда с rottable_blocks (без списка выедает ЛЮБЫЕ
        # блоки куска — аудит)
        for plid, pl in st["processor_lists"].items():
            for pr in pl["processors"]:
                if pr["processor_type"] == "minecraft:block_rot":
                    assert pr.get("rottable_blocks"), plid
        # воспроизводимость (свежий счётчик слотов — тот же порядок rng)
        rng2 = random.Random(seed)
        alloc2 = LootSlots("rndim", "testdim")
        gen_trial_spawners.rand_trial_spawners(
            rng2, "rndim", "testdim", loot_alloc=alloc2)
        rand_carvers(rng2, "rndim", "testdim", min_y, max_y)
        st2 = rand_structures(rng2, "rndim", "testdim", min_y, max_y,
                              ["rndim:t_b1", "rndim:t_b2"], count=50,
                              loot_alloc=alloc2,
                              trial_spawner_ids=ts_ids)
        assert st2 == st, seed
        # обратносовместимость: без trial_spawner_ids — без новых блоков
        rng3 = random.Random(seed + 1000)
        st3 = rand_structures(rng3, "rndim", "testdim", min_y, max_y,
                              ["rndim:t_b1", "rndim:t_b2"], count=4)
        for k, b in st3["nbt_files"].items():
            raw = _gz.decompress(b)
            assert b"normal_config" not in raw and b"minecraft:vault" not in raw, k
        # низкий мир (max_y < 100): mansion/end_city не выдаются — их
        # findGenerationPoint требует getLowestY >= 60 АБСОЛЮТНОЙ высоты
        rng4 = random.Random(seed + 5000)
        st4 = rand_structures(rng4, "rndim", "testdim", min_y, 80,
                              ["rndim:t_b1", "rndim:t_b2"], count=40)
        for sid, sj in st4["structures"].items():
            assert sj["type"] not in Y_GATED_TYPES, sid
            if sj["type"] == JIGSAW_TYPE:
                assert _sh_max(sj["start_height"], min_y, 80) \
                    <= 80 - 34, sid
        # мир с кровлей: jigsaw-старты ещё ниже (roof_bottom - 24 - 10),
        # heightmap-проекция запрещена (WORLD_SURFACE_WG там = крыша)
        rng5 = random.Random(seed + 9000)
        st5 = rand_structures(rng5, "rndim", "testdim", min_y, 256,
                              ["rndim:t_b1", "rndim:t_b2"], count=30,
                              has_ceiling=True, roof_bottom=200)
        for sid, sj in st5["structures"].items():
            assert "project_start_to_heightmap" not in sj, sid
            if sj["type"] == JIGSAW_TYPE:
                assert _sh_max(sj["start_height"], min_y, 256) \
                    <= 200 - 24 - 10, sid
        # крошечный мир (высота 40 <= 42): fallback — старт с тем же
        # запасом 34, но не ниже дна (24-блочный кусок не режется)
        rng6 = random.Random(seed + 777)
        st6 = rand_structures(rng6, "rndim", "testdim", 0, 40,
                              ["rndim:t_b1"], count=6)
        for sid, sj in st6["structures"].items():
            if sj["type"] == JIGSAW_TYPE:
                my6 = _sh_max(sj["start_height"], 0, 40)
                assert my6 == max(0, 40 - 34), (sid, my6)
        ok += 1

    # ------------------------------------------------------------------
    # ФОРКИ ванильных jigsaw-структур: таблица (эталон jar 26.2) +
    # прямые вызовы _rand_fork_structure_json во всех режимах мира
    # ------------------------------------------------------------------
    # таблица = все 10 jigsaw-структур jar 26.2 (34 worldgen/structure,
    # из них 10 "type": "minecraft:jigsaw"), start_pool уникальны
    assert len(VANILLA_JIGSAW_FORKS) == 10, len(VANILLA_JIGSAW_FORKS)
    assert len(VANILLA_FORK_BY_POOL) == 10, "start_pool не уникальны"
    for f in VANILLA_JIGSAW_FORKS:
        assert f["start_pool"].startswith("minecraft:"), f["key"]
        assert f["v_size"] <= 20 and f["v_max_distance"] <= 128, f["key"]
        if f["v_terrain_adaptation"] is not None:
            assert f["v_terrain_adaptation"] in TERRAIN_ADAPTATIONS, f["key"]
        assert f["v_step"] in STRUCTURE_STEPS, f["key"]
        assert isinstance(f["weight"], int) and f["weight"] >= 1, f["key"]
    # (г) trial_chambers: алиасы обязательны (куски тянут цепочку до
    # несуществующих пулов contents/* — без биндингов WARN и дыры)
    fk_tc = VANILLA_FORK_BY_POOL["minecraft:trial_chambers/chamber/end"]
    assert fk_tc["pool_aliases"] == TRIAL_POOL_ALIASES, \
        "trial_chambers-форок без алиасов не соберётся"
    assert fk_tc["dimension_padding"] == 10
    assert fk_tc["liquid_settings"] == "ignore_waterlogging"
    # ancient_city: именованный якорь есть во всех 3 кусках city_center
    # (проверено по jar) — копируем всегда
    fk_ac = VANILLA_FORK_BY_POOL["minecraft:ancient_city/city_center"]
    assert fk_ac["start_jigsaw_name"] == "minecraft:city_anchor"
    # деревни ванильно beard_thin + heightmap + expansion hack
    for f in VANILLA_JIGSAW_FORKS:
        if f["key"].startswith("village"):
            assert f["use_expansion_hack"] \
                and f["project_start_to_heightmap"] == "WORLD_SURFACE_WG" \
                and f["v_terrain_adaptation"] == "beard_thin", f["key"]

    # прямые вызовы: случайные параметры в границях кодека, ванильские
    # поля скопированы; 60 сэмплов на форк (600 всего) — и статистика
    rng = random.Random(31337)
    giants = 0
    village_hm = 0
    village_n = 0
    bastion_hm = 0
    bastion_n = 0
    for f in VANILLA_JIGSAW_FORKS:
        for _ in range(60):
            sj = _rand_fork_structure_json(rng, f, -64, 320, ["rndim:t_b1"])
            assert sj["type"] == JIGSAW_TYPE and sj["biomes"] == ["rndim:t_b1"]
            assert sj["start_pool"] == f["start_pool"]
            # size 4..20, гиганты 13-20 (~15%)
            assert 4 <= sj["size"] <= 20, sj["size"]
            giants += 1 if sj["size"] >= 13 else 0
            # (в) verifyRange + md-пол 4*size
            adapt = sj["terrain_adaptation"]
            assert adapt in TERRAIN_ADAPTATIONS
            md = sj["max_distance_from_center"]
            cap = 116 if adapt != "none" else 128
            assert 30 <= md <= cap, (md, cap)
            assert md >= min(cap, max(30, 4 * sj["size"])), (md, sj["size"])
            # ванильные поля — копии
            assert sj["use_expansion_hack"] == f["use_expansion_hack"]
            if f["start_jigsaw_name"]:
                assert sj["start_jigsaw_name"] == f["start_jigsaw_name"]
            if f["pool_aliases"]:
                assert sj["pool_aliases"] == f["pool_aliases"]
            else:
                assert "pool_aliases" not in sj
            if f["dimension_padding"] is not None:
                assert sj["dimension_padding"] == f["dimension_padding"]
            if f["liquid_settings"]:
                assert sj["liquid_settings"] == f["liquid_settings"]
            # старт-высота — в границах мира с запасом 34
            assert _sh_max(sj["start_height"], -64, 320) <= 320 - 34
            # heightmap: у деревень (ванильный WORLD_SURFACE_WG, мир без
            # кровли) — почти всегда; у бастиона (ванильного нет) — только
            # через surface-шаг (≈⅓)
            if f["key"].startswith("village"):
                village_n += 1
                village_hm += 1 if "project_start_to_heightmap" in sj else 0
            if f["key"] == "bastion_remnant":
                bastion_n += 1
                bastion_hm += 1 if "project_start_to_heightmap" in sj else 0
            json.dumps(sj)
    assert 0.08 < giants / 600 < 0.25, giants / 600        # гиганты ~15%
    assert village_hm / village_n > 0.8, village_hm / village_n
    assert bastion_hm / bastion_n < 0.5, bastion_hm / bastion_n
    # кровля: heightmap запрещён, старт ниже roof_bottom-24-10;
    # крошечный мир (0..40): старт на fallback-высоте 6
    rng = random.Random(4242)
    for f in VANILLA_JIGSAW_FORKS:
        sj = _rand_fork_structure_json(rng, f, -64, 256, ["rndim:t_b1"],
                                       has_ceiling=True, roof_bottom=200)
        assert "project_start_to_heightmap" not in sj, f["key"]
        assert _sh_max(sj["start_height"], -64, 256) <= 200 - 24 - 10
        sj = _rand_fork_structure_json(rng, f, 0, 40, ["rndim:t_b1"])
        assert _sh_max(sj["start_height"], 0, 40) == 6, f["key"]
    # доля форков среди всех структур ~35% (агрегат по seeds×50 структур;
    # p=0.35, σ на 1000 сэмплах ≈ 1.5% — допуск широкие 25-45%)
    fork_share = total_fk / max(1, total_str)
    assert 0.25 < fork_share < 0.45, fork_share
    print("форки: таблица %d ванильных jigsaw-структур, доля среди "
          "структур %.2f, гигантов (size 13-20) %.2f" % (
              len(VANILLA_JIGSAW_FORKS), fork_share, giants / 600))

    # распределение «особого» блока в _rand_nbt_template (прямые вызовы).
    # Ветки пересекаются по содержимому (волт с trial_key ставится парой со
    # спавнером, а в trial-ветке сундук иногда замещается волтом), поэтому
    # проверяем наблюдаемые частоты признаков, а не имена веток:
    #   mob_spawner (SpawnPotentials) = 0.20;
    #   ничего (ни спавнера, ни trial, ни волта) = 0.30;
    #   normal_config = 0.25 (trial) + 0.25 * P(trial-ключ в vault-ветке);
    #   vault = 0.25 (vault-ветка) + 0.25 * P(сундук) * 0.5 (trial-ветка).
    rng = random.Random(777)
    ts_ids = ["rndim:testdim_ts1", "rndim:testdim_ts1_om"]
    n = 600
    obs = {"spawner": 0, "none": 0, "trial_cfg": 0, "vault": 0}
    for _ in range(n):
        raw = _gz.decompress(_rand_nbt_template(
            rng, LootSlots("rndim", "testdim"), ts_ids))
        has_ts = b"normal_config" in raw
        has_vt = b"minecraft:vault" in raw
        has_old = b"SpawnPotentials" in raw
        if has_old:
            obs["spawner"] += 1
        if not (has_old or has_ts or has_vt):
            obs["none"] += 1
        if has_ts:
            obs["trial_cfg"] += 1
        if has_vt:
            obs["vault"] += 1
    for k, exp, tol in (("spawner", 0.20, 0.05), ("none", 0.30, 0.06),
                        ("trial_cfg", 0.4375, 0.09), ("vault", 0.35, 0.09)):
        got = obs[k] / n
        assert abs(got - exp) < tol, (k, got, exp)
    print("особые блоки: " + ", ".join(
        "%s=%.2f" % (k, v / n) for k, v in obs.items()))

    # ------------------------------------------------------------------
    # спавнеры (прямые вызовы _rand_spawner_nbt): валидность id
    # сущностей, разнообразие спектра, скорости и смесь NBT-глубины мобов
    # ------------------------------------------------------------------
    # id всех спец-типов (лодки раскрыты по породам; бамбук — рафт,
    # как в _boat_entity_id)
    boat_ids = set()
    for _w in _BOAT_WOODS:
        if _w == "bamboo":
            boat_ids |= {"minecraft:bamboo_raft",
                         "minecraft:bamboo_chest_raft"}
        else:
            boat_ids.add("minecraft:%s_boat" % _w)
            boat_ids.add("minecraft:%s_chest_boat" % _w)
    special_ids = {"minecraft:item", "minecraft:armor_stand",
                   "minecraft:tnt", "minecraft:falling_block",
                   "minecraft:experience_orb", "minecraft:chest_minecart",
                   "minecraft:minecart", "minecraft:item_frame",
                   "minecraft:glow_item_frame", "minecraft:firework_rocket",
                   "minecraft:area_effect_cloud", "minecraft:wind_charge"} \
        | boat_ids
    # STRUCTURE_MOBS и спец-id — только существующие типы реестра 26.2
    assert set("minecraft:" + m for m in STRUCTURE_MOBS) \
        <= ENTITY_TYPE_IDS, "моб вне реестра entity_type"
    assert special_ids <= ENTITY_TYPE_IDS, "спец-тип вне реестра"
    assert set(_SPECIAL_ENTITY_GENS) == set(SPAWNER_SPECIAL_WEIGHTS)

    rng = random.Random(2024)
    n_sp = 200                     # разнообразие — на 200 спавнерах
    n_share = 1200                 # доли — на большой выборке (устойчиво)
    kinds = {}                      # entity id -> сколько раз (первые 200)
    mob_depth = {"none": 0, "light": 0, "full": 0}
    mob_n = special_n = 0
    for i in range(n_share):
        nbt = _rand_spawner_nbt(rng)
        # скорости — в заданных диапазонах (и max > min гарантирован)
        assert 40 <= nbt["MinSpawnDelay"] <= 100, nbt
        assert 120 <= nbt["MaxSpawnDelay"] <= 240, nbt
        assert nbt["MaxSpawnDelay"] > nbt["MinSpawnDelay"], nbt
        assert 3 <= nbt["SpawnCount"] <= 5, nbt
        assert 6 <= nbt["MaxNearbyEntities"] <= 9, nbt
        assert 24 <= nbt["RequiredPlayerRange"] <= 32, nbt
        assert 4 <= nbt["SpawnRange"] <= 6, nbt
        assert nbt["SpawnPotentials"] == \
            [{"data": nbt["SpawnData"], "weight": 1}], nbt
        # NBT сериализуется целиком (ловит смешанные типы в списках)
        _nbt_bytes(nbt)
        ent = nbt["SpawnData"]["entity"]
        eid = ent["id"]
        assert eid in ENTITY_TYPE_IDS, eid   # суммон несуществующего id
        if i < n_sp:
            kinds[eid] = kinds.get(eid, 0) + 1
        if eid in special_ids:
            special_n += 1
            continue
        mob_n += 1
        # смесь NBT-глубины моба: 40% без NBT / 40% лёгкий / 20% полный
        if set(ent) == {"id"}:
            mob_depth["none"] += 1
        elif (set(ent) <= {"id", "CustomName", "CustomNameVisible",
                           "Health", "Glowing"}
                and ("CustomName" in ent or "Health" in ent)):
            mob_depth["light"] += 1
        else:
            mob_depth["full"] += 1
    # разнообразие: не менее 25 разных типов за 200 спавнеров
    assert len(kinds) >= 25, len(kinds)
    # мобы ~85%, спец-типы ~15%
    assert abs(mob_n / n_share - SPAWNER_MOB_SHARE) < 0.05, mob_n / n_share
    assert abs(special_n / n_share - (1 - SPAWNER_MOB_SHARE)) < 0.05, \
        special_n / n_share
    # глубина NBT мобов: 40/40/20 (допуск на случайность)
    for depth, exp, tol in (("none", 0.40, 0.07), ("light", 0.40, 0.07),
                            ("full", 0.20, 0.06)):
        got = mob_depth[depth] / max(1, mob_n)
        assert abs(got - exp) < tol, (depth, got, exp)

    # структурные проверки каждого спец-генератора (много сэмплов):
    # ключевые поля, диапазоны значений и валидность вложенных id
    rng = random.Random(777_000)
    palette_ids = {b[0] for b in _gd().PALETTE_BLOCKS}
    for kind, gen in _SPECIAL_ENTITY_GENS.items():
        for _ in range(120):
            ent = gen(rng)
            assert ent["id"] in ENTITY_TYPE_IDS, (kind, ent["id"])
            if kind == "item":
                st = ent["Item"]
                assert isinstance(st["id"], str) and st["count"] >= 1
                if "PickupDelay" in ent:
                    assert 10 <= ent["PickupDelay"] <= 100
            elif kind == "armor_stand":
                for slot, st in ent.get("equipment", {}).items():
                    assert slot in ("mainhand", "offhand", "head",
                                    "chest", "legs", "feet"), slot
                    assert st["count"] >= 1
            elif kind == "tnt":
                assert 20 <= ent["fuse"] <= 200, ent["fuse"]
                if "block_state" in ent:
                    assert ent["block_state"]["Name"] in palette_ids
                if "explosion_power" in ent:
                    assert 1.0 <= ent["explosion_power"] <= 6.0
            elif kind == "falling_block":
                assert ent["BlockState"]["Name"] in palette_ids
                assert ent["Time"] == 1
            elif kind == "experience_orb":
                assert 1 <= ent["Value"] <= 50, ent["Value"]
            elif kind in ("chest_boat", "chest_minecart"):
                assert 3 <= len(ent["Items"]) <= 6, len(ent["Items"])
                slots = [it["Slot"] for it in ent["Items"]]
                assert len(set(slots)) == len(slots)     # слоты без повторов
                assert all(0 <= s <= 26 for s in slots)
                if kind == "chest_boat":
                    assert ent["id"] in boat_ids
                else:
                    assert ent["id"] == "minecraft:chest_minecart"
            elif kind in ("item_frame", "glow_item_frame"):
                assert ent["Item"]["count"] >= 1
                if "ItemRotation" in ent:
                    assert 0 <= ent["ItemRotation"] <= 7
            elif kind == "firework_rocket":
                fw = ent["FireworksItem"]["components"]["minecraft:fireworks"]
                assert 1 <= fw["flight_duration"] <= 3
                assert 1 <= len(fw["explosions"]) <= 3
                for ex in fw["explosions"]:
                    assert ex["shape"] in FIREWORK_SHAPES
                    assert 1 <= len(ex["colors"]) <= 3
            elif kind == "area_effect_cloud":
                assert 2.0 <= ent["Radius"] <= 6.0
                assert 100 <= ent["Duration"] <= 800
                pc = ent["potion_contents"]
                if "potion" in pc:
                    assert pc["potion"][len("minecraft:"):] in AEC_POTIONS
                else:
                    for eff in pc["custom_effects"]:
                        assert eff["id"][len("minecraft:"):] in AEC_EFFECTS
                        assert 0 <= eff["amplifier"] <= 2
                        assert 100 <= eff["duration"] <= 600
            elif kind == "boat":
                assert ent["id"] in boat_ids
                assert len(ent["Rotation"]) == 2
            elif kind == "minecart":
                assert ent["id"] == "minecraft:minecart"
            elif kind == "wind_charge":
                assert set(ent) == {"id"}
            _nbt_bytes({"id": "minecraft:mob_spawner",
                        "SpawnData": {"entity": ent}})
    print("спавнеры: типов=%d/200, мобы=%.2f, спец=%.2f, глубина=%s" % (
        len(kinds), mob_n / n_share, special_n / n_share,
        ", ".join("%s=%.2f" % (k, v / max(1, mob_n))
                   for k, v in mob_depth.items())))
    print("OK: %d/%d seed'ов без исключений" % (ok, seeds))


if __name__ == "__main__":
    _self_test()
