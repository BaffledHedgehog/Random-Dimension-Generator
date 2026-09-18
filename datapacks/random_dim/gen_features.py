#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_features.py — генератор случайных декораций (configured_feature +
placed_feature) для Minecraft 26.2 (data format 107).

Формат КАЖДОГО типа, ключа и поля сверен с ванильным jar 26.2
(minecraft-26.2-client.jar, data/minecraft/worldgen/configured_feature/*
и placed_feature/*). Ничего не придумано «по памяти».

Поддержанные configured-фичи (типы подтверждены jar + javap кодеков):
  minecraft:tree, minecraft:ore, minecraft:scattered_ore, minecraft:disk,
  minecraft:lake, minecraft:simple_block (замена random_patch — его в 26.2
  больше НЕТ, патчи делаются simple_block + random_offset в placement),
  minecraft:spring_feature, minecraft:block_blob (лесные валуны),
  minecraft:block_column (кактусы/тростник), minecraft:block_pile (стога),
  minecraft:netherrack_replace_blobs (базальтовые пятна),
  minecraft:bamboo, minecraft:basalt_columns, minecraft:basalt_pillar,
  minecraft:blue_ice, minecraft:coral_tree/claw/mushroom,
  minecraft:delta_feature, minecraft:desert_well, minecraft:fallen_tree,
  minecraft:fill_layer, minecraft:fossil, minecraft:geode,
  minecraft:glowstone_blob, minecraft:huge_brown_mushroom,
  minecraft:huge_fungus, minecraft:huge_red_mushroom, minecraft:iceberg,
  minecraft:kelp, minecraft:large_dripstone, minecraft:monster_room,
  minecraft:multiface_growth, minecraft:replace_single_block,
  minecraft:root_system, minecraft:sculk_patch, minecraft:sea_pickle,
  minecraft:seagrass, minecraft:simple_random_selector,
  minecraft:twisting_vines, minecraft:underwater_magma,
  minecraft:vegetation_patch, minecraft:waterlogged_vegetation_patch,
  minecraft:weeping_vines, minecraft:weighted_random_selector,
  minecraft:sequence, minecraft:nether_forest_vegetation,
  minecraft:random_selector, minecraft:random_boolean_selector,
  minecraft:speleothem (остроконечный натёк), minecraft:speleothem_cluster,
  minecraft:spike, minecraft:vines.

Поддержанные placement-модификаторы (14 из 15 реестра 26.2):
  count, count_on_every_layer (только пещерному режиму cave=True: сам
  находит Y по слоям, после него НИ in_square, НИ heightmap, как в
  ванили; на поверхности отключён — «фичи в воздухе»), rarity_filter,
  noise_threshold_count, noise_based_count, in_square,
  height_range (uniform/trapezoid + якоря
  absolute/above_bottom/below_top), heightmap (все 6 Heightmap.Types),
  biome, block_predicate_filter (+ would_survive), environment_scan,
  surface_relative_threshold_filter, surface_water_depth_filter,
  random_offset. Поверхностной растительности count собирается по
  ванильным «рецептам естественной плотности»: count-провайдер с
  дисперсией / rarity / рощи rarity+count / noise_based_count /
  noise_threshold_count — фиксированный count на чанк дал бы почти
  равномерную сетку «1 дерево/чанк».
Исключение: fixed_placement — его позиции абсолютны и годятся только
для разовых фич (end_platform), в пер-чанковой декорации биома он
ломает генерацию (запись в далёкие чанки из каждого чанка).

ИНВАРИАНТЫ РАЗМЕЩЕНИЯ «НЕ В ВОЗДУХЕ» (правка по жалобе юзера: «в
каждом мире большинство деревьев/грибов/других фич просто висят в
воздухе»; главный виновник — height_range с равномерным Y у наземных
видов + count_on_every_layer без фильтра земли). Высота теперь СТРОГО
по классу вида (_FeatureFactory._GROUND_KINDS / _WATER_KINDS):
  - «растущие с земли» (деревья/грибы/патчи/диски/озёра/столбы/
    selector'ы...) — ТОЛЬКО heightmap поверхности (MOTION_BLOCKING /
    MOTION_BLOCKING_NO_LEAVES / WORLD_SURFACE_WG) + ОБЯЗАТЕЛЬНЫЙ
    block_predicate_filter «твёрдый блок ПОД позицией» (minecraft:solid
    c offset [0,-1,0]); height_range им запрещён;
  - подводные — heightmap дна OCEAN_FLOOR / OCEAN_FLOOR_WG;
  - подземные (руда/жеода/monster_room/источники/натёки/sculk/...)
    — height_range по долям высоты мира, как ванильные ore_*/geode;
  - count_on_every_layer — только cave-режим, и то с фильтром
    «твёрдое снизу».
Фильтр «твёрдое снизу» выбран вместо would_survive-логики: он
проверяет САМ БЛОК под позицией, а не ванильную землю (саженцу нужны
dirt-подобные блоки — в мирах из камня/кварца он убил бы фичи
целиком); работает на ЛЮБОМ рельефе случайных измерений.

Публичные функции:

    rand_features(rng, ns, name, min_y, max_y, count=None, cave=False,
                 no_gravity=False)
        -> (configured, placed, tags)

    rng    — random.Random (весь рандом только через него);
    ns     — namespace ('rndim');
    name   — имя измерения или биома (префикс id);
    min_y / max_y — границы мира по Y, max_y ВКЛЮЧИТЕЛЬНО (для якорей
    height_range; эксклюзивный top мира = max_y + 1);
    cave   — пещерный режим для ПОДЗЕМНЫХ биомов: только виды, не
    требующие ни неба, ни поверхности (CAVE_FEATURE_KINDS), и placement
    без heightmap (он ставит фичу на верх мира, а не на пол пещеры;
    см. _cave_placement).
    no_gravity — VOID-режим: из ВСЕХ пулов размещения исключаются сыпучие
    блоки (generate_dimension.FALLING_BLOCK_IDS: песок/гравий/подозри-
    тельные + 16 бетонных порошков). Блок, поставленный генерацией над
    пустотой, обращается в entity FALLING_BLOCK — весь мир «сыпется» в
    пустоту, сотни тысяч сущностей, игра виснет (жалоба юзера). В
    open/cavern-мирах дно есть — сыпучие разрешены.

    Возвращает (configured, placed, tags): три dict {id: json}, где id —
    namespaced строки 'ns:...'. На каждый configured создаётся 1-2 placed,
    каждый ссылается на свой configured полем "feature". tags — block-теги
    («земля» измерения — цели руд/дисков/валунов).

    rand_ores(rng, ns, name, min_y, max_y, count=None, no_gravity=False)
        -> (configured, placed, tags, variants)

    Рудная система измерения — отдельный проход поверх rand_features:
    5-9 видов руд (было 3-7 — юзер просил «ещё немного больше»), у
    каждого ЧЕТЫРЕ placed-варианта богатства
    (×0.3/×1/×2.5/×5, id <name>_oreM_p1..p4) — биомы получают СВОИ
    варианты (в одном биоме руда богатая, в другом бедная; раздача в
    generate_dimension.rand_biome). Высоты — относительные якоря
    (above_bottom/below_top) по ДОЛЯМ высоты мира, смещённые вниз, в
    рельеф. variants — {configured_id: {"poor"/"normal"/"rich"/
    "motherlode": placed_id}}. no_gravity — void-режим (см. rand_features).

    rand_stone_blobs(rng, ns, name, min_y, max_y, family, vein=None)
        -> (configured, placed, tags)

    Блобы КАМЕННОГО СЕМЕЙСТВА — как ванильные андезит/диорит/гранит/
    туф: ore-фичи с size 15-64 и count 1-6 на чанк, полоса высот — по
    ДОЛЯМ высоты мира (относительные якоря, как у руд). Тиры:
    «частые» — крупнее и гуще (size 33-64, count 3-6), «обычные» —
    size 20-48, count 2-4, «редкие» — size 15-33, count 1-2 +
    rarity_filter 1/4-1/16. vein — опциональная «жила-стержень» одного
    редкого блока: вертикальные узкие блобы (size 2-6 + count 8-24).
    configured id — <name>_stoneN, placed id — <name>_blobN. Блобы
    кладём в ОБЩИЙ пул измерения (каждый биом — как ванильные
    ore_granite/ore_andesite), НЕ в пер-биомные множители руд.
    Семейство (и жилу) фильтрует от сыпучих вызывающий код — здесь
    они приходят уже чистыми.
"""

import re


def _gd():
    """Ленивый доступ к generate_dimension — циклический импорт безопасен
    в любом порядке (generate_dimension импортирует этот модуль первым)."""
    import generate_dimension
    return generate_dimension


def rnd_f(rng, a, b, digits=3):
    return _gd().rnd_f(rng, a, b, digits)


def block_state(block):
    return _gd().block_state(block)


_SOLIDS = None
_FEATURE_SOLIDS = None


def _solids():
    global _SOLIDS
    if _SOLIDS is None:
        _SOLIDS = _gd().SOLID_BLOCKS
    return _SOLIDS


def _feature_solids():
    """Блоки для ФИЧ (не террейна!): все solid + редкий динамит.

    Динамит исключён из SOLID_BLOCKS (default_block/surface rules), чтобы он
    не покрывал целые чанки, но как блок фичи или «рудная жила» — редкий
    сюрприз: 4 записи на ~3785 (вес ~0.1%, реже чем самый странный тир).
    """
    global _FEATURE_SOLIDS
    if _FEATURE_SOLIDS is None:
        _FEATURE_SOLIDS = _solids() + [("minecraft:tnt", None)] * 4
    return _FEATURE_SOLIDS


_PALETTE = None


def _palette():
    """Безопасный пул БЕЗ block entity (generate_dimension.PALETTE_BLOCKS) —
    для фич МАССШТАБА РЕЛЬЕФА (fill_layer заливает ЦЕЛЫЙ Y-слой мира) и
    для тега «земли» измерения. Странность уже распределена весами тиров."""
    global _PALETTE
    if _PALETTE is None:
        _PALETTE = _gd().PALETTE_BLOCKS
    return _PALETTE


_PALETTE_IDS = None


def _palette_ids():
    """Уникальные id блоков палитры (для тега «земли» и matching_blocks)."""
    global _PALETTE_IDS
    if _PALETTE_IDS is None:
        _PALETTE_IDS = sorted({b[0] for b in _palette()})
    return _PALETTE_IDS


_SAFE_SOLIDS = None


def _safe_solids():
    """Блоки для фич МАССОВОГО масштаба: как _feature_solids, но БЕЗ block
    entity (деревья/диски/жеоды ставят сотни и тысячи блоков — ствол из
    copper_golem_statue даёт BE на каждой клетке + DUMMY-мусор над
    потолком мира) и БЕЗ динамита (ствол из ТНТ — цепной взрыв от первой
    кирки). Странность сохранена: веса тиров 16/8/4/2/1 остаются, барьер
    и свет (T4 без BE) — редкий сюрреализм. Руды/патчи/столбы/кучи —
    маленькие, им _feature_solids() по-прежнему разрешён."""
    global _SAFE_SOLIDS
    if _SAFE_SOLIDS is None:
        be = _gd().BE_BLOCK_IDS
        _SAFE_SOLIDS = [b for b in _feature_solids()
                        if b[0] not in be and b[0] != "minecraft:tnt"]
    return _SAFE_SOLIDS

# ---------------------------------------------------------------------------
# Данные, существование которых подтверждено в ванильном jar 26.2
# ---------------------------------------------------------------------------

# (бревно, листья) — пары из ванильных tree-фич 26.2 (39 файлов просканировано)
TREE_WOODS = [
    ("minecraft:oak_log", "minecraft:oak_leaves"),
    ("minecraft:spruce_log", "minecraft:spruce_leaves"),
    ("minecraft:birch_log", "minecraft:birch_leaves"),
    ("minecraft:jungle_log", "minecraft:jungle_leaves"),
    ("minecraft:acacia_log", "minecraft:acacia_leaves"),
    ("minecraft:dark_oak_log", "minecraft:dark_oak_leaves"),
    ("minecraft:mangrove_log", "minecraft:mangrove_leaves"),
    ("minecraft:cherry_log", "minecraft:cherry_leaves"),
    ("minecraft:pale_oak_log", "minecraft:pale_oak_leaves"),
]

# дополнительная листва из ванильной azalea_tree (weighted_state_provider)
EXTRA_LEAVES = ["minecraft:azalea_leaves", "minecraft:flowering_azalea_leaves"]

# блоки «под ствол» — из below_trunk_provider ванильных деревьев
# (oak -> dirt, azalea_tree -> rooted_dirt)
DIRT_BLOCKS = ["minecraft:dirt", "minecraft:coarse_dirt",
               "minecraft:rooted_dirt", "minecraft:mud"]

# саженцы для предиката would_survive (проверены по loot_table/blocks в jar)
SAPLINGS = ["minecraft:oak_sapling", "minecraft:spruce_sapling",
            "minecraft:birch_sapling", "minecraft:jungle_sapling",
            "minecraft:acacia_sapling", "minecraft:dark_oak_sapling",
            "minecraft:cherry_sapling", "minecraft:pale_oak_sapling",
            "minecraft:mangrove_propagule"]

# растения из ванильных simple_block-фич 26.2 (grass, flower_*, patch_*, ...)
PLANT_BLOCKS = [
    "minecraft:azalea", "minecraft:blue_orchid", "minecraft:brown_mushroom",
    "minecraft:bush", "minecraft:closed_eyeblossom", "minecraft:crimson_roots",
    "minecraft:dandelion", "minecraft:dead_bush", "minecraft:fern",
    "minecraft:fire", "minecraft:firefly_bush", "minecraft:flowering_azalea",
    "minecraft:large_fern", "minecraft:leaf_litter", "minecraft:lily_pad",
    "minecraft:melon", "minecraft:moss_carpet", "minecraft:pale_moss_carpet",
    "minecraft:pink_petals", "minecraft:poppy", "minecraft:pumpkin",
    "minecraft:red_mushroom", "minecraft:short_dry_grass",
    "minecraft:short_grass", "minecraft:soul_fire", "minecraft:spore_blossom",
    "minecraft:sunflower", "minecraft:sweet_berry_bush",
    "minecraft:tall_dry_grass", "minecraft:tall_grass", "minecraft:wildflowers",
]

# рудные блоки — все state-блоки из 30 ванильных ore-фич 26.2
ORE_BLOCKS = [(b, None) for b in [
    "minecraft:ancient_debris", "minecraft:clay", "minecraft:coal_ore",
    "minecraft:copper_ore", "minecraft:deepslate_coal_ore",
    "minecraft:deepslate_copper_ore", "minecraft:deepslate_diamond_ore",
    "minecraft:deepslate_emerald_ore", "minecraft:deepslate_gold_ore",
    "minecraft:deepslate_iron_ore", "minecraft:deepslate_lapis_ore",
    "minecraft:deepslate_redstone_ore", "minecraft:diamond_ore",
    "minecraft:emerald_ore", "minecraft:gold_ore", "minecraft:infested_stone",
    "minecraft:infested_deepslate", "minecraft:iron_ore",
    "minecraft:lapis_ore", "minecraft:magma_block",
    "minecraft:nether_gold_ore", "minecraft:nether_quartz_ore",
    "minecraft:redstone_ore", "minecraft:soul_sand",
]]

# теги рудных целей (predicate_type tag_match) — из ванильных ore-фич
ORE_TARGET_TAGS = [
    "minecraft:stone_ore_replaceables",
    "minecraft:deepslate_ore_replaceables",
    "minecraft:base_stone_overworld",
    "minecraft:base_stone_nether",
]

# каменистые блоки для block_match-целей руд и target'ов netherrack_replace_blobs
STONE_BLOCKS = [
    "minecraft:stone", "minecraft:netherrack", "minecraft:deepslate",
    "minecraft:granite", "minecraft:diorite", "minecraft:andesite",
    "minecraft:tuff", "minecraft:basalt", "minecraft:blackstone",
    "minecraft:end_stone",
]

# «земляные» блоки — цели disk'ов (matching_blocks), can_place_on и т.п.;
# список собран из ванильных disk_sand/disk_grass/ice_patch
GROUND_BLOCKS = [
    "minecraft:dirt", "minecraft:grass_block", "minecraft:podzol",
    "minecraft:coarse_dirt", "minecraft:mycelium", "minecraft:mud",
    "minecraft:snow_block", "minecraft:ice", "minecraft:sand",
    "minecraft:gravel", "minecraft:stone", "minecraft:deepslate",
]

# ванильные block-теги, реально встречающиеся в предикатах фич 26.2
BLOCK_TAGS = [
    "minecraft:air", "minecraft:features_cannot_replace",
    "minecraft:stone_ore_replaceables", "minecraft:deepslate_ore_replaceables",
    "minecraft:base_stone_overworld", "minecraft:base_stone_nether",
    "minecraft:forest_rock_can_place_on",
]

# каменистые блоки для valid_blocks источников (из ванильных spring-фич)
SPRING_BLOCKS = [
    "minecraft:stone", "minecraft:granite", "minecraft:diorite",
    "minecraft:andesite", "minecraft:deepslate", "minecraft:tuff",
    "minecraft:calcite", "minecraft:dirt", "minecraft:snow_block",
    "minecraft:powder_snow", "minecraft:packed_ice", "minecraft:netherrack",
    "minecraft:basalt", "minecraft:blackstone", "minecraft:end_stone",
]

# все 6 типов Heightmap.Types (codecs сериализуют любой; _WG-варианты
# валидны только при генерации мира — как в ванильных placed-фичах)
HEIGHTMAPS = ["MOTION_BLOCKING", "MOTION_BLOCKING_NO_LEAVES", "OCEAN_FLOOR",
              "OCEAN_FLOOR_WG", "WORLD_SURFACE", "WORLD_SURFACE_WG"]

FLUIDS = ["minecraft:water", "minecraft:lava"]

# стволы для fallen_tree / huge_fungus (свойства axis поставит сам feature)
STEM_BLOCKS = ["minecraft:crimson_stem", "minecraft:warped_stem"] \
              + [w[0] for w in TREE_WOODS]

# «земля» под huge_fungus (valid_base_block)
FUNGUS_BASES = ["minecraft:crimson_nylium", "minecraft:warped_nylium",
                "minecraft:netherrack", "minecraft:grass_block",
                "minecraft:dirt", "minecraft:mycelium", "minecraft:podzol",
                "minecraft:moss_block"]

# multiface_growth: block ДОЛЖЕН быть MultifaceSpreadableBlock (иначе кодек
# отклонит — «Growth block should be a multiface spreadeable block»)
MULTIFACE_BLOCKS = ["minecraft:glow_lichen", "minecraft:sculk_vein"]

# льды для iceberg
ICE_BLOCKS = ["minecraft:blue_ice", "minecraft:packed_ice",
              "minecraft:ice", "minecraft:snow_block"]

# «остроконечные» блоки speleothem/speleothem_cluster (оба из jar 26.2)
POINTED_BLOCKS = ["minecraft:pointed_dripstone", "minecraft:sulfur_spike"]

# ванильные теги для replaceable-полей (все встречаются в jar 26.2)
REPLACEABLE_TAGS = [
    "#minecraft:moss_replaceable",
    "#minecraft:lush_ground_replaceable",
    "#minecraft:azalea_root_replaceable",
    "#minecraft:dripstone_replaceable_blocks",
    "#minecraft:sulfur_spike_replaceable_blocks",
]

# ванильные части окаменелостей и процессоры (fossil, из jar 26.2)
FOSSIL_PARTS = ["spine_1", "spine_2", "spine_3", "spine_4",
                "skull_1", "skull_2", "skull_3", "skull_4"]

# ванильные configured-фичи для «внутренних» ссылок селекторов, если своих
# фич ещё не создано (все есть в jar 26.2)
VANILLA_CFG_IDS = ["minecraft:grass", "minecraft:oak", "minecraft:birch",
                   "minecraft:pile_hay", "minecraft:bush", "minecraft:melon"]

# виды фич и их веса: (kind, вес) — kind это суффикс id и ключ builder'а.
# Обычные декорации — весомее; дикие/редкие (geode, monster_room, sequence,
# fossil, sculk_patch) — реже. Руд ЗДЕСЬ больше нет: ими ведёт отдельная
# система rand_ores (5-9 видов на измерение с вариантами богатства
# ×0.3/×1/×2.5/×5 и высотами по долям высоты мира) — случайная примесь
# руд в общем пуле давала неуправляемое количество видов (аудит: медиана
# 1 руда на измерение при разбросе 0-6) и высоты, не привязанные к рельефу.
FEATURE_KINDS = [
    ("tree", 3.0),          # деревья
    ("patch", 2.5),         # «патчи» растений (simple_block)
    ("disk", 1.2),          # диски (песок/глина/лёд)
    ("lake", 0.8),          # озёра
    ("spring", 1.2),        # источники жидкостей
    ("block_blob", 1.0),    # валуны (forest_rock)
    ("block_column", 0.8),  # столбы (кактус/тростник)
    ("block_pile", 0.7),    # кучи (стог/тыквы)
    ("replace_blobs", 0.8), # пятна замены (базальт в незераке)
    # --- новые типы (26.2) ---
    ("bamboo", 0.7),          # бамбук
    ("basalt_columns", 0.7),  # базальтовые колонны
    ("basalt_pillar", 0.6),   # базальтовые столбы (незер)
    ("blue_ice", 0.5),        # глыбы синего льда
    ("coral", 0.6),           # кораллы (tree/claw/mushroom)
    ("delta", 0.6),           # дельты лавы (с ободком)
    ("desert_well", 0.4),     # колодцы в пустыне
    ("fallen_tree", 0.9),     # поваленные деревья
    ("fill_layer", 0.6),      # сплошной слой блока
    ("fossil", 0.35),         # окаменелости (редко)
    ("geode", 0.25),          # жеоды (редко, дикий тип)
    ("glowstone_blob", 0.6),  # пятна светокамня
    ("huge_brown_mushroom", 0.6),
    ("huge_fungus", 0.7),     # огромные грибы-грибы (незер)
    ("huge_red_mushroom", 0.6),
    ("iceberg", 0.6),         # айсберги
    ("kelp", 0.5),            # ламинария
    ("large_dripstone", 0.6), # большие сталактиты/сталагмиты
    ("monster_room", 0.25),   # комнаты монстров (редко)
    ("multiface", 0.6),       # лишайник/sculk-вены на стенах
    ("replace_single_block", 1.0),  # точечная замена блока
    ("root_system", 0.6),     # корневые системы с деревом
    ("sculk_patch", 0.4),     # пятна sculk (редко)
    ("sea_pickle", 0.5),      # морские огурцы
    ("seagrass", 0.6),        # морская трава
    ("simple_random_selector", 0.7),  # выбор случайной подфичи
    ("twisting_vines", 0.5),  # закрученные лозы
    ("underwater_magma", 0.5),# подводная магма
    ("vegetation_patch", 0.8),# пятна поверхности с растительностью
    ("waterlogged_vegetation_patch", 0.5),
    ("weeping_vines", 0.5),   # плакучие лозы
    ("weighted_random_selector", 0.6),
    ("sequence", 0.3),        # цепочка фич подряд (редко)
    ("nether_vegetation", 0.7),   # незер-растительность
    ("random_selector", 0.7), # вероятностный выбор + default
    ("random_boolean_selector", 0.5),
    ("speleothem", 0.6),      # одиночные натёки
    ("speleothem_cluster", 0.6),  # гроздья натёков
    ("spike", 0.5),           # шипы (sulfur spike)
    ("vines", 0.4),           # свисающие лозы
]

# Пещерные виды фич для ПОДЗЕМНЫХ биомов (rand_features(cave=True)):
# только то, что не требует ни неба, ни поверхности. Две группы:
#  - фичи, которые САМИ находят пол/потолок пещер, сканируя пространство
#    вокруг позиции (multiface, sculk_patch, large_dripstone, speleothem,
#    geode, monster_room, root_system, lake, spring...);
#  - растительность и «напольные» декорации — им placement даёт
#    count_on_every_layer (ванильный пещерный механизм, находит позиции
#    на твёрдых блоках в воздушных слоях) или height_range с широкой
#    полосой + фильтр «снизу твёрдое».
# Деревьев/дисков/кактусов/кораллов/айсбергов здесь НЕТ: их placement
# завязан на heightmap (первый воздух ПОВЕРХ мира) и поверхность, а
# пещерам не нужно ни небо, ни верх мира.
CAVE_FEATURE_KINDS = [
    ("multiface", 1.6),          # лишайник/sculk-вены на стенах пещер
    ("speleothem", 1.4),         # одиночные натёки
    ("speleothem_cluster", 1.4), # гроздья натёков (dripstone_cluster)
    ("large_dripstone", 1.3),    # большие сталактиты/сталагмиты
    ("sculk_patch", 0.9),        # пятна sculk (сильный визуал — реже)
    ("glowstone_blob", 1.0),     # пятна светокамня у потолка
    ("vines", 1.0),              # свисающие лозы (classic_vines_cave_feature)
    ("twisting_vines", 0.7),
    ("weeping_vines", 0.7),
    ("huge_brown_mushroom", 0.9),
    ("huge_red_mushroom", 0.9),
    ("huge_fungus", 0.9),
    ("nether_vegetation", 1.0),  # корни/ростки (как в незере)
    ("patch", 0.9),              # простая растительность на полах
    ("block_pile", 0.6),
    ("block_column", 0.6),
    ("block_blob", 0.7),         # валуны на пещерных полах
    ("fallen_tree", 0.3),        # поваленный ствол — редкость в пещере
    ("replace_blobs", 0.8),      # пятна замены породы
    ("basalt_columns", 0.7),
    ("basalt_pillar", 0.7),
    ("blue_ice", 0.4),
    ("delta", 0.5),              # лавовые дельты с ободком
    ("underwater_magma", 0.5),
    ("spring", 1.0),             # источники (в т.ч. лавовые)
    ("lake", 0.4),               # подземные озёра (lake_lava_underground)
    ("monster_room", 0.5),       # комнаты монстров
    ("geode", 0.5),              # жеоды (ваниль: выше дна на 6..30)
    ("fossil", 0.3),
    ("root_system", 0.5),        # корни + азалея (как lush caves)
    ("vegetation_patch", 0.7),   # моховые пятна на полах
    ("waterlogged_vegetation_patch", 0.35),
    ("spike", 0.4),
    ("replace_single_block", 0.8),
    ("simple_random_selector", 0.5),
    ("weighted_random_selector", 0.4),
    ("random_selector", 0.4),
    ("random_boolean_selector", 0.3),
    ("sequence", 0.2),
]

# Варианты богатства руды: множитель на базовый count. Именно ОТДЕЛЬНЫЕ
# placed-фичи (а не один count-провайдер) позволяют разным биомам
# получать РАЗНЫЙ уровень богатства ОДНОЙ руды: биом A — бедную ×0.3,
# биом B — материнскую жилу ×5 (раздача — rand_biome в
# generate_dimension; id вариантов <name>_oreM_p1..p4 по порядку
# множителей).
ORE_MULTIPLIERS = [
    ("poor", 0.3),        # бедная россыпь
    ("normal", 1.0),      # обычная (базовый count 2-20)
    ("rich", 2.5),        # богатая
    ("motherlode", 5.0),  # материнская жила
]


class _FeatureFactory:
    """Внутренняя фабрика: собирает configured и placed фичи."""

    def __init__(self, rng, ns, name, min_y, max_y, cave=False,
                 no_gravity=False):
        self.rng = rng
        self.ns = ns
        self.name = name
        self.min_y = min_y
        self.max_y = max_y
        self.cave = cave       # пещерный режим (фичи подземных биомов)
        # VOID-режим (no_gravity): из ВСЕХ пулов размещения исключаются
        # сыпучие блоки — падающий блок, поставленный генерацией над
        # пустотой, обращается в entity FALLING_BLOCK (весь мир
        # «сыпется», сотни тысяч сущностей, игра виснет; жалоба юзера).
        # Пулы предрассчитаны один раз в конструкторе; предикаты
        # МАТЧИНГА (matching_blocks/block_match) сыпучие id сохраняют —
        # совпадения просто не будет, размещения не происходит.
        self.no_gravity = no_gravity
        if no_gravity:
            _fall = _gd().FALLING_BLOCK_IDS
            self._feat_pool = [b for b in _feature_solids()
                               if b[0] not in _fall]
            self._safe_pool = [b for b in _safe_solids()
                               if b[0] not in _fall]
            self._pal_pool = [b for b in _palette() if b[0] not in _fall]
        else:
            self._feat_pool = _feature_solids()
            self._safe_pool = _safe_solids()
            self._pal_pool = _palette()
        self.configured = {}
        self.placed = {}
        self.ground_needed = False   # создана ли цель с тегом «земли»
        self._counters = {}
        self._builders = {
            "tree": self._tree, "ore": self._ore, "patch": self._patch,
            "disk": self._disk, "lake": self._lake, "spring": self._spring,
            "block_blob": self._block_blob, "block_column": self._block_column,
            "block_pile": self._block_pile, "replace_blobs": self._replace_blobs,
            "bamboo": self._bamboo, "basalt_columns": self._basalt_columns,
            "basalt_pillar": self._basalt_pillar, "blue_ice": self._blue_ice,
            "coral": self._coral, "delta": self._delta,
            "desert_well": self._desert_well, "fallen_tree": self._fallen_tree,
            "fill_layer": self._fill_layer, "fossil": self._fossil,
            "geode": self._geode, "glowstone_blob": self._glowstone_blob,
            "huge_brown_mushroom": self._huge_brown_mushroom,
            "huge_fungus": self._huge_fungus,
            "huge_red_mushroom": self._huge_red_mushroom,
            "iceberg": self._iceberg, "kelp": self._kelp,
            "large_dripstone": self._large_dripstone,
            "monster_room": self._monster_room, "multiface": self._multiface,
            "replace_single_block": self._replace_single_block,
            "root_system": self._root_system, "sculk_patch": self._sculk_patch,
            "sea_pickle": self._sea_pickle, "seagrass": self._seagrass,
            "simple_random_selector": self._simple_random_selector,
            "twisting_vines": self._twisting_vines,
            "underwater_magma": self._underwater_magma,
            "vegetation_patch": self._vegetation_patch,
            "waterlogged_vegetation_patch": self._waterlogged_vegetation_patch,
            "weeping_vines": self._weeping_vines,
            "weighted_random_selector": self._weighted_random_selector,
            "sequence": self._sequence, "nether_vegetation": self._nether_vegetation,
            "random_selector": self._random_selector,
            "random_boolean_selector": self._random_boolean_selector,
            "speleothem": self._speleothem,
            "speleothem_cluster": self._speleothem_cluster,
            "spike": self._spike, "vines": self._vines,
        }

    # ---------------- вспомогательные ----------------

    def _uid(self, kind):
        self._counters[kind] = self._counters.get(kind, 0) + 1
        return "%s:%s_%s%d" % (self.ns, self.name, kind, self._counters[kind])

    def _block(self):
        return self.rng.choice(self._feat_pool)

    def _safe_block(self):
        """Блок для фич МАССОВОГО масштаба — без block entity и TNT
        (в void-режиме пул уже без сыпучих — см. __init__)."""
        return self.rng.choice(self._safe_pool)

    def _provider(self, block=None):
        """simple_state_provider случайного (или переданного) блока."""
        return {"type": "minecraft:simple_state_provider",
                "state": block_state(block or self._block())}

    def _safe_provider(self, block=None):
        """simple_state_provider блока БЕЗ block entity — для массовых фич."""
        return {"type": "minecraft:simple_state_provider",
                "state": block_state(block or self._safe_block())}

    def _pair_y(self):
        a = self.rng.randint(self.min_y, self.max_y)
        b = self.rng.randint(self.min_y, self.max_y)
        if a > b:
            a, b = b, a
        if a == b:
            b = min(b + 8, self.max_y)
            if a == b:  # совсем плоский мир — хотя бы разнесём на 1
                a = max(self.min_y, a - 1)
        return a, b

    def _int_provider(self, lo, hi):
        """Случайный IntProvider (uniform/biased_to_bottom/trapezoid/
        weighted_list) — все четыре типа есть в ванильных фичах 26.2."""
        rng = self.rng
        r = rng.random()
        if r < 0.45:
            a = rng.randint(lo, hi)
            return {"type": "minecraft:uniform", "min_inclusive": a,
                    "max_inclusive": rng.randint(a, hi)}
        if r < 0.70:
            a = rng.randint(lo, hi)
            return {"type": "minecraft:biased_to_bottom", "min_inclusive": a,
                    "max_inclusive": rng.randint(a, hi)}
        # ОГРАНИЧЕНИЕ trapezoid: plateau <= max-min (РАЗМАХ, не диапазон
        # значений!) — иначе «Plateau can at most be the full span» и
        # падает загрузка ВСЕГО пака (поймано на реальном сервере)
        if r < 0.85 and hi - lo >= 2:
            return {"type": "minecraft:trapezoid", "min": lo, "max": hi,
                    "plateau": rng.randint(0, hi - lo)}
        vals = rng.sample(range(lo, hi + 1), min(rng.randint(2, 4), hi - lo + 1))
        dist = []
        for v in vals:
            # data может быть и ВЛОЖЕННЫМ провайдером (vanilla cave_vine:
            # weighted_list поверх uniform) — усиливает дисперсию
            if rng.random() < 0.3:
                b = rng.randint(v, hi)
                dist.append({"data": {"type": "minecraft:uniform",
                                      "min_inclusive": v,
                                      "max_inclusive": b},
                             "weight": rng.randint(1, 5)})
            else:
                dist.append({"data": v, "weight": rng.randint(1, 5)})
        return {"type": "minecraft:weighted_list", "distribution": dist}

    def _float_provider(self, a, b):
        """Случайный FloatProvider в [a, b]: uniform (max_exclusive!) или
        clamped_normal — оба типа есть в ванильных фичах 26.2.
        ВАЖНО: uniform/clamped_normal с min == max НЕПАРСЯТСЯ ("Max must
        be larger than min") и роняют загрузку ВСЕГО пака — при вырождении
        диапазона (lo == b после округления rnd_f) отдаём голое число
        (константа — валидный FloatProvider в JSON)."""
        rng = self.rng
        lo = rnd_f(rng, a, b)
        hi = rnd_f(rng, lo, b)
        if hi <= lo:
            hi = b
        if hi <= lo:  # lo == b: диапазон выродился в точку
            return round(lo, 3)
        if rng.random() < 0.75:
            return {"type": "minecraft:uniform", "min_inclusive": lo,
                    "max_exclusive": hi}
        return {"type": "minecraft:clamped_normal", "mean": rnd_f(rng, lo, hi),
                "deviation": rnd_f(rng, 0.05, max(0.06, (hi - lo) / 2.0)),
                "min": lo, "max": hi}

    def _placed_ref(self):
        """Inline placed_feature-ссылка: своя уже созданная configured-фича
        (селекторы ссылаются только «назад», поэтому циклов не бывает),
        а если своих ещё нет — ванильная из jar."""
        if self.configured and self.rng.random() < 0.85:
            fid = self.rng.choice(sorted(self.configured))
        else:
            fid = self.rng.choice(VANILLA_CFG_IDS)
        return {"feature": fid, "placement": []}

    def _height_provider(self):
        """HeightProvider для height_range: ПОЛОСА ПО ДОЛЯМ ВЫСОТЫ МИРА с
        относительными якорями above_bottom/below_top (масштабируется под
        любую геометрию измерения; absolute — редко и тоже из _pair_y, в
        границах мира). Рудам — свой провайдер с приглубным смещением
        (_ore_height_provider), пещерным фичам — широкий (_cave_height_provider)."""
        rng = self.rng
        if rng.random() < 0.25:  # изредка — absolute-якоря в границах мира
            lo, hi = self._pair_y()
            kind = "minecraft:uniform" if rng.random() < 0.7 \
                else "minecraft:trapezoid"
            return {"type": kind, "min_inclusive": {"absolute": lo},
                    "max_inclusive": {"absolute": hi}}
        # полоса по долям высоты: позиция и ширина случайны
        w = rnd_f(rng, 0.10, 0.80)
        lo = rnd_f(rng, 0.0, max(0.0, 1.0 - w))
        return self._frac_height_provider(lo, lo + w)

    def _frac_height_provider(self, lo_f, hi_f):
        """Якоря height_range по ДОЛЯМ высоты мира (0.0 = дно, 1.0 =
        верхний блок): нижняя граница — above_bottom, верхняя —
        below_top. Полоса всегда внутри [min_y, max_y] и непустая при
        ЛЮБОЙ геометрии мира — в отличие от фиксированных значений, не
        привязанных к высоте конкретного измерения."""
        rng = self.rng
        span = max(1, self.max_y - self.min_y)
        lo_f = min(max(lo_f, 0.0), 0.95)
        hi_f = min(max(hi_f, lo_f + 0.05), 1.0)
        a = int(round(lo_f * span))
        b = int(round((1.0 - hi_f) * span))
        if a + b > span - 1:
            b = max(0, span - 1 - a)
        kind = "minecraft:uniform" if rng.random() < 0.7 \
            else "minecraft:trapezoid"
        return {"type": kind, "min_inclusive": {"above_bottom": a},
                "max_inclusive": {"below_top": b}}

    def _ore_height_provider(self):
        """Полоса высот РУДЫ в долях высоты мира — СМЕЩЕНА ВНИЗ, в
        рельеф: раньше absolute-полосы из _pair_y могли целиком попасть
        в воздух над поверхностью (а низкие миры — выше половины высоты),
        и жилы с discard_chance_on_air_exposure просто исчезали — «руды
        не спавнятся». Типы полос — как в ванили: придонная «алмазная»,
        глубокая, средняя (уголь/железо), сквозная на всю высоту и
        редкая верхняя (ore_iron_upper)."""
        rng = self.rng
        r = rng.random()
        if r < 0.30:      # «алмазная»: придонная полоса
            lo, hi = 0.0, rnd_f(rng, 0.15, 0.40)
        elif r < 0.55:    # глубокая, но не придонная
            lo = rnd_f(rng, 0.0, 0.25)
            hi = rnd_f(rng, 0.30, 0.60)
        elif r < 0.78:    # средняя глубина (как уголь/железо)
            lo = rnd_f(rng, 0.10, 0.45)
            hi = rnd_f(rng, 0.50, 0.85)
        elif r < 0.92:    # сквозная (ванильное железо: почти вся высота)
            lo, hi = 0.0, rnd_f(rng, 0.85, 1.0)
        else:             # верхняя (редкость, как ore_iron_upper)
            lo = rnd_f(rng, 0.40, 0.65)
            hi = rnd_f(rng, 0.75, 1.0)
        return self._frac_height_provider(lo, hi)

    def _blob_height_provider(self, tier=None):
        """Полоса высот БЛОБА каменного семейства в долях высоты мира
        (относительные якоря — тот же подход, что у руд, см.
        _ore_height_provider): «частым» камням — широкие пласты (как
        ванильный гранит верхней/нижней полосы), «обычным» — средние,
        «редким» — узкие пояса."""
        rng = self.rng
        if tier == "common":
            w = rnd_f(rng, 0.30, 0.80)
        elif tier == "rare":
            w = rnd_f(rng, 0.08, 0.25)
        else:               # normal и без тира (запасной путь)
            w = rnd_f(rng, 0.15, 0.50)
        lo = rnd_f(rng, 0.0, max(0.0, 1.0 - w))
        return self._frac_height_provider(lo, lo + w)

    def _vein_height_provider(self):
        """Полоса высот «жилы-стержня»: высокий пояс (0.5-1.0 высоты
        мира) — узкие блобы редкого камня пронизывают массив по
        вертикали, а не стелются горизонтальным слоем."""
        rng = self.rng
        w = rnd_f(rng, 0.50, 1.00)
        lo = rnd_f(rng, 0.0, max(0.0, 1.0 - w))
        return self._frac_height_provider(lo, lo + w)

    def _blob_targets(self, blk):
        """Цели БЛОБА каменного семейства: state — ВСЕГДА переданный
        блок (в отличие от рудных _ore_targets с их случайными state),
        target — почти всегда тег «земли» измерения (блоб заменяет
        фактический рельеф, как ванильный гранит — stone_ore_replaceables),
        изредка block_match по палитре."""
        self.ground_needed = True
        rng = self.rng
        if rng.random() < 0.2:
            target = {"predicate_type": "minecraft:block_match",
                      "block": rng.choice(_palette_ids())}
        else:
            target = {"predicate_type": "minecraft:tag_match",
                      "tag": "%s:%s_ground" % (self.ns, self.name)}
        return [{"state": block_state(blk), "target": target}]

    def _cave_height_provider(self):
        """Полоса высот пещерных фич: почти вся высота мира — как у
        ванильных пещерных placed-фич (glow_lichen: above_bottom(0)..
        absolute(256)). multiface/large_dripstone/sculk_patch/geode сами
        сканируют пространство вокруг позиции, полоса лишь задаёт
        диапазон поиска."""
        rng = self.rng
        lo = rng.choice([0.0, 0.0, 0.02, 0.05, 0.10])
        hi = rng.choice([0.90, 0.95, 0.98, 1.0])
        return self._frac_height_provider(lo, hi)

    def _predicate(self, depth=0):
        """Случайный block predicate. Форматы всех типов сверенены по
        placed/configured-фичам jar 26.2."""
        rng = self.rng
        r = rng.random()
        if depth < 2 and r < 0.16:
            return {"type": "minecraft:all_of",
                    "predicates": [self._predicate(depth + 1)
                                   for _ in range(rng.randint(2, 3))]}
        if depth < 2 and r < 0.26:
            return {"type": "minecraft:any_of",
                    "predicates": [self._predicate(depth + 1)
                                   for _ in range(rng.randint(2, 3))]}
        if depth < 2 and r < 0.36:
            return {"type": "minecraft:not",
                    "predicate": self._predicate(depth + 1)}
        if r < 0.55:  # matching_blocks: блок ИЛИ список блоков (+offset)
            pool = GROUND_BLOCKS + [b[0] for b in _feature_solids()]
            k = rng.randint(1, 3)
            blocks = rng.sample(pool, k) if k > 1 else rng.choice(pool)
            pred = {"type": "minecraft:matching_blocks", "blocks": blocks}
            if rng.random() < 0.4:
                pred["offset"] = [rng.randint(-1, 1), rng.randint(-1, 1),
                                  rng.randint(-1, 1)]
            return pred
        if r < 0.70:
            return {"type": "minecraft:matching_block_tag",
                    "tag": rng.choice(BLOCK_TAGS)}
        if r < 0.78:
            return {"type": "minecraft:matching_fluids",
                    "fluids": rng.choice(FLUIDS)}
        if r < 0.86:
            pred = {"type": "minecraft:solid"}
            if rng.random() < 0.5:
                pred["offset"] = [0, rng.choice([-1, 1]), 0]
            return pred
        if r < 0.93:  # как ванильные *_checked placed-фичи
            return {"type": "minecraft:would_survive",
                    "state": {"Name": rng.choice(SAPLINGS),
                              "Properties": {"stage": "0"}}}
        return {"type": "minecraft:true"}

    # ---------------- configured: деревья ----------------

    def _tree_decorator(self):
        """Декораторы, форматы которых подтверждены в ванильных tree-фичах."""
        rng = self.rng
        t = rng.random()
        if t < 0.25:
            return {"type": "minecraft:trunk_vine"}
        if t < 0.45:
            return {"type": "minecraft:leave_vine",
                    "probability": rnd_f(rng, 0.0, 1.0)}
        if t < 0.60:
            return {"type": "minecraft:cocoa",
                    "probability": rnd_f(rng, 0.0, 1.0)}
        if t < 0.75:  # подмена земли под деревом (как mega_spruce)
            return {"type": "minecraft:alter_ground",
                    "provider": {
                        "type": "minecraft:rule_based_state_provider",
                        "rules": [{
                            "if_true": {"type": "minecraft:matching_block_tag",
                                        "tag": "minecraft:beneath_tree_podzol_replaceable"},
                            "then": self._provider((rng.choice(
                                ["minecraft:podzol", "minecraft:dirt",
                                 "minecraft:mud", "minecraft:coarse_dirt"]), None)),
                        }]}}
        if t < 0.90:  # как pale_oak
            return {"type": "minecraft:pale_moss",
                    "ground_probability": rnd_f(rng, 0.0, 1.0),
                    "leaves_probability": rnd_f(rng, 0.0, 1.0),
                    "trunk_probability": rnd_f(rng, 0.0, 1.0)}
        return {"type": "minecraft:creaking_heart",
                "probability": rnd_f(rng, 0.0, 1.0)}

    def _trunk_placer(self):
        """Все 9 типов trunk placer'ов из ванильных tree-фич 26.2."""
        rng = self.rng
        t = rng.choices(
            ["straight", "forking", "fancy", "dark_oak", "giant",
             "mega_jungle", "bending", "cherry", "upwards_branching"],
            weights=[30, 12, 10, 10, 6, 6, 10, 8, 8])[0]
        if t in ("straight", "forking", "fancy", "dark_oak"):
            return {"type": "minecraft:%s_trunk_placer" % t,
                    "base_height": rng.randint(4, 12),
                    "height_rand_a": rng.randint(0, 4),
                    "height_rand_b": rng.randint(0, 3)}
        if t in ("giant", "mega_jungle"):  # толстые 2x2 стволы — повыше
            return {"type": "minecraft:%s_trunk_placer" % t,
                    "base_height": rng.randint(8, 16),
                    "height_rand_a": rng.randint(0, 6),
                    "height_rand_b": rng.randint(0, 14)}
        if t == "bending":  # формат из azalea_tree
            return {"type": "minecraft:bending_trunk_placer",
                    "base_height": rng.randint(4, 9),
                    "height_rand_a": rng.randint(0, 3),
                    "height_rand_b": rng.randint(0, 2),
                    "bend_length": {"type": "minecraft:uniform",
                                    "min_inclusive": rng.randint(1, 2),
                                    "max_inclusive": rng.randint(2, 3)},
                    "min_height_for_leaves": rng.randint(2, 5)}
        if t == "cherry":  # формат из cherry.json
            start = -rng.randint(3, 5)
            return {"type": "minecraft:cherry_trunk_placer",
                    "base_height": rng.randint(5, 10),
                    "height_rand_a": rng.randint(0, 2),
                    "height_rand_b": 0,
                    "branch_count": self._int_provider(1, 3),
                    "branch_end_offset_from_top": {
                        "type": "minecraft:uniform",
                        "min_inclusive": -1, "max_inclusive": 0},
                    "branch_horizontal_length": {
                        "type": "minecraft:uniform",
                        "min_inclusive": rng.randint(2, 3),
                        "max_inclusive": rng.randint(3, 5)},
                    # движок требует >=2 разных значения (branch starts),
                    # поэтому разброс всегда хотя бы 2 блока
                    "branch_start_offset_from_top": {
                        "min_inclusive": start,
                        "max_inclusive": start + rng.randint(1, 2)}}
        # upwards_branching — формат из mangrove.json
        return {"type": "minecraft:upwards_branching_trunk_placer",
                "base_height": rng.randint(2, 6),
                "height_rand_a": rng.randint(1, 3),
                "height_rand_b": rng.randint(0, 5),
                "extra_branch_length": {"type": "minecraft:uniform",
                                        "min_inclusive": 0,
                                        "max_inclusive": rng.randint(1, 2)},
                "extra_branch_steps": {"type": "minecraft:uniform",
                                       "min_inclusive": 1,
                                       "max_inclusive": rng.randint(2, 5)},
                "place_branch_per_log_probability": rnd_f(rng, 0.0, 1.0),
                "can_grow_through": rng.choice(
                    ["#minecraft:mangrove_logs_can_grow_through",
                     "#minecraft:air"])}

    def _foliage_placer(self):
        """Все 11 типов foliage placer'ов из ванильных tree-фич 26.2."""
        rng = self.rng
        t = rng.choices(
            ["blob", "bush", "jungle", "fancy", "acacia", "dark_oak",
             "spruce", "pine", "mega_pine", "cherry", "random_spread"],
            weights=[22, 8, 8, 10, 10, 10, 10, 8, 5, 5, 4])[0]
        if t in ("blob", "bush", "jungle"):
            return {"type": "minecraft:%s_foliage_placer" % t,
                    "height": rng.randint(2, 4), "offset": rng.randint(0, 2),
                    "radius": rng.randint(1, 3)}
        if t == "fancy":
            return {"type": "minecraft:fancy_foliage_placer",
                    "height": rng.randint(3, 5), "offset": rng.randint(2, 4),
                    "radius": rng.randint(1, 2)}
        if t in ("acacia", "dark_oak"):
            return {"type": "minecraft:%s_foliage_placer" % t,
                    "offset": rng.randint(0, 1), "radius": rng.randint(0, 3)}
        if t == "spruce":  # IntProvider-поля (spruce.json)
            return {"type": "minecraft:spruce_foliage_placer",
                    "offset": {"type": "minecraft:uniform",
                               "min_inclusive": 0, "max_inclusive": 2},
                    "radius": {"type": "minecraft:uniform",
                               "min_inclusive": 2, "max_inclusive": 3},
                    "trunk_height": {"type": "minecraft:uniform",
                                     "min_inclusive": 0, "max_inclusive": 2}}
        if t == "pine":  # height — IntProvider (pine.json)
            return {"type": "minecraft:pine_foliage_placer",
                    "height": {"type": "minecraft:uniform",
                               "min_inclusive": rng.randint(3, 4),
                               "max_inclusive": rng.randint(4, 6)},
                    "offset": rng.randint(0, 2), "radius": rng.randint(0, 2)}
        if t == "mega_pine":  # crown_height — IntProvider (mega_spruce.json)
            return {"type": "minecraft:mega_pine_foliage_placer",
                    "crown_height": {"type": "minecraft:uniform",
                                     "min_inclusive": rng.randint(8, 14),
                                     "max_inclusive": rng.randint(14, 20)},
                    "offset": 0, "radius": rng.randint(0, 2)}
        if t == "cherry":  # cherry.json — шансы «дырок» в кроне
            return {"type": "minecraft:cherry_foliage_placer",
                    # height — IntProvider с минимумом 4 (IntProviders.codec(4, 16))
                    "height": rng.randint(4, 8), "offset": 0,
                    "radius": rng.randint(2, 5),
                    "corner_hole_chance": rnd_f(rng, 0.0, 0.5),
                    "hanging_leaves_chance": rnd_f(rng, 0.0, 0.5),
                    "hanging_leaves_extension_chance": rnd_f(rng, 0.0, 0.5),
                    "wide_bottom_layer_hole_chance": rnd_f(rng, 0.0, 0.5)}
        # random_spread — формат из azalea_tree
        return {"type": "minecraft:random_spread_foliage_placer",
                "foliage_height": rng.randint(1, 3),
                "leaf_placement_attempts": rng.randint(20, 80),
                "offset": rng.randint(0, 1), "radius": rng.randint(2, 4)}

    def _tree(self):
        rng = self.rng
        # материал: обычно ванильная порода, но ~25% деревьев — «из чего
        # попало»: ствол и листва из случайных solid-блоков БЕЗ block
        # entity (стволов тысячи — BE в каждом = «чанки из сундуков» и
        # DUMMY-мусор над потолком мира). Странность распределена весами
        # тиров (16/8/4/2/1) — почти всегда обычный камень, барьер/свет —
        # редкий сюрреализм. Безопасность для произвольных блоков сверена
        # javap: trunk placer'ы 26.2 не трогают свойства ствола (Cherry —
        # trySetValue), foliage — hasProperty.
        custom = rng.random() < 0.25
        if custom:
            log = rng.choice(self._safe_pool)[0]
            leaf = rng.choice(self._safe_pool)[0]
        else:
            log, leaf = rng.choice(TREE_WOODS)
        # листва: своя порода, иногда с примесью азалиевых; простой или
        # взвешенный провайдер (как azalea_tree). Properties не задаём —
        # значения по умолчанию совпадают с ванильными (distance=7 и т.д.)
        pool = [leaf]
        if not custom and rng.random() < 0.35:
            pool += EXTRA_LEAVES
        if len(pool) > 1 and rng.random() < 0.5:
            foliage_provider = {
                "type": "minecraft:weighted_state_provider",
                "entries": [{"data": {"Name": lv},
                             "weight": rng.randint(1, 5)} for lv in pool]}
        else:
            foliage_provider = {"type": "minecraft:simple_state_provider",
                                "state": {"Name": rng.choice(pool)}}
        # ствол: Properties не задаём — trunk placer сам ставит axis
        trunk_provider = {"type": "minecraft:simple_state_provider",
                          "state": {"Name": log}}
        # блок под стволом: как ванильные деревья (rule_based) или просто
        # простой провайдер (как azalea_tree)
        if rng.random() < 0.8:
            below = {"type": "minecraft:rule_based_state_provider",
                     "rules": [{
                         "if_true": {"type": "minecraft:not",
                                     "predicate": {
                                         "type": "minecraft:matching_block_tag",
                                         "tag": "minecraft:cannot_replace_below_tree_trunk"}},
                         "then": {"type": "minecraft:simple_state_provider",
                                  "state": {"Name": rng.choice(DIRT_BLOCKS)}}}]}
        else:
            below = {"type": "minecraft:simple_state_provider",
                     "state": {"Name": rng.choice(DIRT_BLOCKS)}}
        # декораторы — обычно пусто (как у простых деревьев)
        decorators = []
        if rng.random() < 0.35:
            for _ in range(rng.randint(1, 2)):
                decorators.append(self._tree_decorator())
        # minimum_size: two_layers (4 поля подтверждены) или three_layers
        if rng.random() < 0.75:
            ms = {"type": "minecraft:two_layers_feature_size"}
            if rng.random() < 0.6:
                ms["limit"] = rng.randint(0, 2)
            if rng.random() < 0.6:
                ms["lower_size"] = rng.randint(0, 2)
            if rng.random() < 0.6:
                ms["upper_size"] = rng.randint(0, 2)
            if rng.random() < 0.25:
                ms["min_clipped_height"] = rng.randint(1, 4)
        else:  # в 26.2 у three_layers в данных встречается только upper_size
            ms = {"type": "minecraft:three_layers_feature_size",
                  "upper_size": rng.randint(0, 2)}
        return {"type": "minecraft:tree", "config": {
            "below_trunk_provider": below,
            "decorators": decorators,
            "foliage_placer": self._foliage_placer(),
            "foliage_provider": foliage_provider,
            "ignore_vines": rng.random() < 0.5,
            "minimum_size": ms,
            "trunk_placer": self._trunk_placer(),
            "trunk_provider": trunk_provider,
        }}

    # ---------------- configured: руды ----------------

    def _ground_tag(self):
        """Тег «земли» измерения: все блоки палитры рельефа. Рельеф мира
        состоит ИМЕННО из них (default_block + слои surface rules), поэтому
        tag_match на этот тег заменяет блок В ЛЮБОМ месте рельефа — в отличие
        от ванильных #stone_ore_replaceables, которые в случайном рельефе
        не встречаются и руды из-за этого не генерировались вовсе.
        Файл тега создаёт rand_features (по self.ground_needed)."""
        self.ground_needed = True
        return "%s:%s_ground" % (self.ns, self.name)

    def _ore_targets(self, safe=False):
        """1-3 цели замены: почти всегда — тег «земли» измерения (жила
        заменяет фактический рельеф); изредка ванильный тег/блок (миры, где
        рельеф совпал с ванильным камнем, и просто разнообразие).
        safe=True — блоки жилы из БЕЗОПАСНОГО пула (без block entity и
        ТНТ): рудная система даёт до count 100/чанк (×5), жилы такого
        масштаба — уже «массовая заливка», как стены структур. Маленькие
        пользователи целей (replace_single_block) оставляют полный пул.
        В void-режиме оба пула уже без сыпучих (см. __init__)."""
        rng = self.rng
        pool = (self._safe_pool if safe else self._feat_pool) + ORE_BLOCKS
        targets = []
        for _ in range(rng.randint(1, 3)):
            r = rng.random()
            if r < 0.75:
                target = {"predicate_type": "minecraft:tag_match",
                          "tag": self._ground_tag()}
            elif r < 0.9:
                target = {"predicate_type": "minecraft:tag_match",
                          "tag": rng.choice(ORE_TARGET_TAGS)}
            else:
                # block_match: цель — блок из палитры (могла попасть в рельеф)
                target = {"predicate_type": "minecraft:block_match",
                          "block": rng.choice(_palette_ids())}
            targets.append({"state": block_state(rng.choice(pool)),
                            "target": target})
        return targets

    def _ore(self):
        rng = self.rng
        ftype = "minecraft:scattered_ore" if rng.random() < 0.2 else "minecraft:ore"
        # размер жилы: 2-20 с тяжёлым хвостом — обычные жилы компактные
        # (2-9), каждый четвёртый вид руды — «толстожильный» до 20
        size = rng.randint(10, 20) if rng.random() < 0.25 else rng.randint(2, 9)
        # discard_on_air_exposure: ваниль у большинства руд 0.0, у
        # «погребённых» (ore_diamond_buried) — до 1.0; большой discard +
        # полоса у поверхности = руда исчезает целиком, поэтому веса
        # смещены к нулю
        discard = rng.choice([0.0, 0.0, 0.0, rnd_f(rng, 0.1, 0.5), 1.0])
        return {"type": ftype, "config": {
            "discard_chance_on_air_exposure": discard,
            "size": size,
            # блоки жилы — БЕЗ block entity и ТНТ (жилы до 100 попыток/чанк)
            "targets": self._ore_targets(safe=True),
        }}

    # ---------------- configured: патчи растений ----------------

    def _patch(self):
        # В 26.2 random_patch УДАЛЁН: патчи теперь simple_block +
        # random_offset в placed_feature (как ванильный patch_grass_normal)
        rng = self.rng
        if rng.random() < 0.45:  # микс из 2-4 растений (как flower_*)
            entries = [{"data": {"Name": p}, "weight": rng.randint(1, 6)}
                       for p in rng.sample(PLANT_BLOCKS, rng.randint(2, 4))]
            to_place = {"type": "minecraft:weighted_state_provider",
                        "entries": entries}
        else:
            to_place = {"type": "minecraft:simple_state_provider",
                        "state": {"Name": rng.choice(PLANT_BLOCKS)}}
        return {"type": "minecraft:simple_block", "config": {"to_place": to_place}}

    # ---------------- configured: диски ----------------

    def _disk(self):
        rng = self.rng
        rmin = rng.randint(1, 3)
        radius = {"type": "minecraft:uniform", "min_inclusive": rmin,
                  "max_inclusive": rng.randint(rmin, 8)}
        # state_provider: простой или rule_based (как disk_sand/disk_grass);
        # блоки — ТОЛЬКО без block entity: диск радиусом до 8 и толщиной
        # до 4 — это сотни блоков «рельефа» (сундук-диск = чанк сундуков)
        if rng.random() < 0.4:
            if rng.random() < 0.5:  # disk_sand: под воздухом — другой блок
                rule = {"if_true": {"type": "minecraft:matching_blocks",
                                    "blocks": "minecraft:air",
                                    "offset": [0, -1, 0]},
                        "then": self._safe_provider()}
            else:  # disk_grass: сверху не твёрдое и не вода — трава
                rule = {"if_true": {"type": "minecraft:not",
                                    "predicate": {
                                        "type": "minecraft:any_of",
                                        "predicates": [
                                            {"type": "minecraft:solid",
                                             "offset": [0, 1, 0]},
                                            {"type": "minecraft:matching_fluids",
                                             "fluids": "minecraft:water",
                                             "offset": [0, 1, 0]}]}},
                        "then": self._safe_provider()}
            state_provider = {"type": "minecraft:rule_based_state_provider",
                              "fallback": self._safe_provider(),
                              "rules": [rule]}
        else:
            state_provider = self._safe_provider()
        # target: чаще тег «земли» измерения (диск реально появится —
        # ванильные dirt/grass в случайном рельефе почти не встречаются),
        # изредка список блоков (формат из disk-фич)
        if rng.random() < 0.6:
            target = {"type": "minecraft:matching_block_tag",
                      "tag": self._ground_tag()}
        else:
            k = rng.randint(1, 4)
            pool = GROUND_BLOCKS + _palette_ids()
            blocks = rng.sample(pool, k) if k > 1 else rng.choice(pool)
            target = {"type": "minecraft:matching_blocks", "blocks": blocks}
        return {"type": "minecraft:disk", "config": {
            "half_height": rng.randint(1, 4),
            "radius": radius,
            "state_provider": state_provider,
            "target": target,
        }}

    # ---------------- configured: озёра ----------------

    def _lake(self):
        # Формат 26.2 (lake_lava.json): 5 полей — fluid, barrier,
        # can_place_feature, can_replace_with_air_or_fluid,
        # can_replace_with_barrier. В 1.21.x были только fluid+barrier!
        rng = self.rng
        return {"type": "minecraft:lake", "config": {
            "barrier": self._provider(),
            "can_place_feature": {"type": "minecraft:true"},
            "can_replace_with_air_or_fluid": {
                "type": "minecraft:not",
                "predicate": {"type": "minecraft:matching_block_tag",
                              "tag": "minecraft:features_cannot_replace"}},
            "can_replace_with_barrier": {
                "type": "minecraft:not",
                "predicate": {"type": "minecraft:matching_block_tag",
                              "tag": "minecraft:lava_pool_stone_cannot_replace"}},
            "fluid": {"type": "minecraft:simple_state_provider",
                      "state": {"Name": rng.choice(FLUIDS),
                                "Properties": {"level": "0"}}},
        }}

    # ---------------- configured: источники ----------------

    def _spring(self):
        rng = self.rng
        config = {"state": {"Name": rng.choice(FLUIDS),
                            "Properties": {"falling": "true"}}}
        # valid_blocks: один блок (строка) или список — оба варианта в jar
        if rng.random() < 0.35:
            config["valid_blocks"] = rng.choice(SPRING_BLOCKS)
        else:
            config["valid_blocks"] = rng.sample(SPRING_BLOCKS, rng.randint(2, 6))
        # необязательные поля — формат из spring_nether_closed
        if rng.random() < 0.3:
            config["hole_count"] = rng.randint(0, 2)
            config["requires_block_below"] = rng.random() < 0.5
            config["rock_count"] = rng.randint(1, 8)
        return {"type": "minecraft:spring_feature", "config": config}

    # ---------------- configured: валуны ----------------

    def _block_blob(self):
        # forest_rock.json: "state" — blockstate (НЕ provider!), can_place_on —
        # предикат. В 1.21.x были state_provider + tries.
        rng = self.rng
        if rng.random() < 0.3:
            can_place_on = {"type": "minecraft:matching_block_tag",
                            "tag": "minecraft:forest_rock_can_place_on"}
        elif rng.random() < 0.5:  # тег «земли» — валун встанет на рельеф
            can_place_on = {"type": "minecraft:matching_block_tag",
                            "tag": self._ground_tag()}
        else:
            can_place_on = {"type": "minecraft:matching_blocks",
                            "blocks": rng.sample(
                                GROUND_BLOCKS + _palette_ids(),
                                rng.randint(1, 3))}
        return {"type": "minecraft:block_blob", "config": {
            "can_place_on": can_place_on,
            "state": block_state(self._block()),
        }}

    # ---------------- configured: столбы ----------------

    def _block_column(self):
        # cactus.json / sugar_cane.json: direction, layers (height -
        # IntProvider + provider), allowed_placement, prioritize_tip
        rng = self.rng
        layers = []
        for _ in range(rng.randint(1, 3)):
            if rng.random() < 0.4:  # кактус/тростник — растение
                state = {"Name": rng.choice(PLANT_BLOCKS)}
            else:  # или просто случайный блок
                state = block_state(self._block())
            layers.append({"height": self._int_provider(1, 6),
                           "provider": {"type": "minecraft:simple_state_provider",
                                        "state": state}})
        return {"type": "minecraft:block_column", "config": {
            "allowed_placement": {"type": "minecraft:matching_block_tag",
                                  "tag": "minecraft:air"},
            "direction": "up" if rng.random() < 0.85 else "down",
            "layers": layers,
            "prioritize_tip": rng.random() < 0.5,
        }}

    # ---------------- configured: кучи ----------------

    def _block_pile(self):
        # pile_hay.json: state_provider — rotated_block_provider или простой
        rng = self.rng
        state = block_state(self._block())
        if rng.random() < 0.4:
            sp = {"type": "minecraft:rotated_block_provider", "state": state}
        else:
            sp = {"type": "minecraft:simple_state_provider", "state": state}
        return {"type": "minecraft:block_pile", "config": {"state_provider": sp}}

    # ---------------- configured: пятна замены ----------------

    def _replace_blobs(self):
        # basalt_blobs.json: radius (IntProvider), state и target —
        # ОБА простые blockstate (не провайдеры!)
        rng = self.rng
        rmin = rng.randint(1, 4)
        # target — простой blockstate: блок из ВЗВЕШЕННОЙ палитры (веса
        # тиров: обычные блоки рельефа вероятнее), а не ванильный камень,
        # которого в случайном рельефе может не быть; state — без BE
        # (пятно радиуса до 9 — массовая заливка). В void-режиме оба из
        # уже отфильтрованных пулов (без сыпучих)
        return {"type": "minecraft:netherrack_replace_blobs", "config": {
            "radius": {"type": "minecraft:uniform", "min_inclusive": rmin,
                       "max_inclusive": rng.randint(rmin, 9)},
            "state": block_state(self._safe_block()),
            "target": block_state(rng.choice(self._pal_pool)),
        }}

    # ---------------- configured: новые типы 26.2 ----------------

    def _none_cfg(self, ftype):
        """Фичи с пустым конфигом (NoneFeatureConfiguration)."""
        return {"type": "minecraft:%s" % ftype, "config": {}}

    def _bamboo(self):
        # bamboo_some_podzol.json: только probability
        return {"type": "minecraft:bamboo", "config": {
            "probability": rnd_f(self.rng, 0.0, 1.0)}}

    def _basalt_columns(self):
        # ColumnFeatureConfiguration: reach 0-3, height 1-10 (IntProviders)
        return {"type": "minecraft:basalt_columns", "config": {
            "height": self._int_provider(1, 10),
            "reach": self._int_provider(0, 3)}}

    def _basalt_pillar(self):
        return self._none_cfg("basalt_pillar")

    def _blue_ice(self):
        return self._none_cfg("blue_ice")

    def _coral(self):
        # все три типа — NoneFeatureConfiguration (warm_ocean_vegetation.json)
        return self._none_cfg(self.rng.choice(
            ["coral_tree", "coral_claw", "coral_mushroom"]))

    def _delta(self):
        # delta.json: contents/rim — blockstate, size/rim_size — IntProvider
        rng = self.rng
        smin = rng.randint(0, 4)
        rmin = rng.randint(0, 2)
        # size+rim держим <= 11 (ваниль: 7+2): больший радиус с позиции у
        # края чанка пишет блоки на 2+ чанка в сторону («setBlock in a
        # far chunk» на сервере)
        return {"type": "minecraft:delta_feature", "config": {
            "contents": {"Name": rng.choice(FLUIDS),
                         "Properties": {"level": "0"}},
            "rim": block_state(self._block()),
            "size": {"type": "minecraft:uniform", "min_inclusive": smin,
                     "max_inclusive": rng.randint(smin + 1, 8)},
            "rim_size": {"type": "minecraft:uniform", "min_inclusive": rmin,
                         "max_inclusive": rng.randint(rmin + 1, 3)}}}

    def _desert_well(self):
        return self._none_cfg("desert_well")

    def _fallen_tree(self):
        # fallen_oak_tree.json: trunk_provider, log_length (IntProvider 0-16),
        # декораторы attached_to_logs / trunk_vine (поля по javap)
        rng = self.rng
        # обычно ванильный ствол, но ~25% — из любого solid-блока
        # БЕЗ block entity (массовая фича; странность — веса тиров)
        if rng.random() < 0.25:
            log = rng.choice(self._safe_pool)[0]
        else:
            log = rng.choice(STEM_BLOCKS)
        lmin = rng.randint(2, 6)

        def dec():
            if rng.random() < 0.4:
                return {"type": "minecraft:trunk_vine"}
            return {"type": "minecraft:attached_to_logs",
                    "probability": rnd_f(rng, 0.0, 1.0),
                    "block_provider": self._provider(
                        (rng.choice(PLANT_BLOCKS), None)),
                    "directions": rng.sample(
                        ["up", "down", "north", "south", "east", "west"],
                        rng.randint(1, 3))}

        return {"type": "minecraft:fallen_tree", "config": {
            "trunk_provider": {"type": "minecraft:simple_state_provider",
                               "state": {"Name": log,
                                         "Properties": {"axis": "y"}}},
            "log_length": {"type": "minecraft:uniform",
                           "min_inclusive": lmin,
                           "max_inclusive": rng.randint(lmin + 1, 14)},
            "stump_decorators": [dec() for _ in range(rng.randint(0, 1))],
            "log_decorators": [dec() for _ in range(rng.randint(0, 2))],
        }}

    def _fill_layer(self):
        # LayerConfiguration: height — ОБЫЧНОЕ int (intRange 0..MAX), state
        # Слой заливает ЦЕЛЫЙ Y-слой ВСЕГО мира — это масштаб рельефа:
        # только безопасный пул БЕЗ block entity (сундук в каждом чанке
        # на одной высоте = катастрофа) и БЕЗ сыпучих в void-режиме.
        # Руды/патчи/диски — локальные, им _feat_pool по-прежнему разрешён.
        return {"type": "minecraft:fill_layer", "config": {
            "height": self.rng.randint(0, 24),
            "state": block_state(self.rng.choice(self._pal_pool))}}

    def _fossil(self):
        # fossil_coal.json: структуры/процессоры ванильные, углов 0-7
        rng = self.rng
        overlay = rng.choice(["coal", "diamonds"])
        parts = rng.sample(FOSSIL_PARTS, rng.randint(2, 8))
        return {"type": "minecraft:fossil", "config": {
            "fossil_processors": "minecraft:fossil_rot",
            "fossil_structures": ["minecraft:fossil/%s" % p for p in parts],
            "max_empty_corners_allowed": rng.randint(0, 7),
            "overlay_processors": "minecraft:fossil_%s" % overlay,
            "overlay_structures": ["minecraft:fossil/%s_%s" % (p, overlay)
                                   for p in parts]}}

    def _geode(self):
        # Формат 26.2 (amethyst_geode.json + javap GeodeConfiguration):
        # блоки слоёв вынесены в "blocks", толщины — в "layers" (все double
        # 0.01-50), crack — {generate_crack_chance, base_crack_size 0-5,
        # crack_point_offset 0-10}; outer_wall_distance 1-20,
        # distribution_points 1-20, point_offset 0-10 (IntProviders).
        rng = self.rng
        buds = ["minecraft:small_amethyst_bud", "minecraft:medium_amethyst_bud",
                "minecraft:large_amethyst_bud", "minecraft:amethyst_cluster"]
        inner = []
        for _ in range(rng.randint(1, 4)):
            if rng.random() < 0.35:  # кластеры аметиста как в ванили
                inner.append({"Name": rng.choice(buds), "Properties": {
                    "facing": "up", "waterlogged": "false"}})
            else:  # или случайные блоки (жеод — сфера в сотни блоков: без BE)
                inner.append(block_state(self._safe_block()))
        wall = rng.randint(1, 5)
        # Радиусы держим ванильными (ваниль: wall 4-6, сумма толщин ~4,
        # point_offset ~1): большой геод с позиции у края чанка пишет
        # блоки на 2+ чанка в сторону («setBlock in a far chunk»)
        return {"type": "minecraft:geode", "config": {
            "blocks": {
                "filling_provider": self._provider((rng.choice(
                    ["minecraft:air", "minecraft:water", "minecraft:lava"]), None)),
                "inner_layer_provider": self._safe_provider(),
                "alternate_inner_layer_provider": self._safe_provider(),
                "middle_layer_provider": self._safe_provider(),
                "outer_layer_provider": self._safe_provider(),
                "inner_placements": inner,
                "cannot_replace": "#minecraft:features_cannot_replace",
                "invalid_blocks": "#minecraft:geode_invalid_blocks",
            },
            "layers": {
                "filling": rnd_f(rng, 0.3, 1.0),
                "inner_layer": rnd_f(rng, 0.6, 1.6),
                "middle_layer": rnd_f(rng, 0.8, 2.4),
                "outer_layer": rnd_f(rng, 1.0, 3.0),
            },
            "crack": {
                "generate_crack_chance": rnd_f(rng, 0.0, 1.0),
                "base_crack_size": rnd_f(rng, 0.0, 3.0),
                "crack_point_offset": rng.randint(0, 4),
            },
            "use_potential_placements_chance": rnd_f(rng, 0.0, 1.0),
            "use_alternate_layer0_chance": rnd_f(rng, 0.0, 1.0),
            "placements_require_layer0_alternate": rng.random() < 0.5,
            "outer_wall_distance": {"type": "minecraft:uniform",
                                    "min_inclusive": wall,
                                    "max_inclusive": rng.randint(wall, 6)},
            "distribution_points": self._int_provider(1, 12),
            "point_offset": self._int_provider(0, 2),
            # min/max_gen_offset (рамка итерации геода): ванильные дефолты
            # ±16 + граничный peek на 1 блок у FluidState = 17 от позиции,
            # что у края чанка даёт «unsafe terrain read» (distance 2);
            # держим ±14, чтобы записи/чтения не выходили за соседний чанк
            "min_gen_offset": rng.randint(-14, -1),
            "max_gen_offset": rng.randint(1, 14),
            "noise_multiplier": rnd_f(rng, 0.01, 0.3),
            "invalid_blocks_threshold": rng.randint(1, 8),
        }}

    def _glowstone_blob(self):
        return self._none_cfg("glowstone_blob")

    def _mushroom_faces(self):
        rng = self.rng
        return {d: ("true" if rng.random() < 0.7 else "false")
                for d in ("down", "east", "north", "south", "up", "west")}

    def _huge_mushroom(self, red):
        # HugeMushroomFeatureConfiguration (javap): cap/stem — провайдеры,
        # foliage_radius — опционально (по умолч. 2), can_place_on — предикат.
        rng = self.rng
        cap = (("minecraft:%s_mushroom_block" % ("red" if red else "brown"),
                self._mushroom_faces()) if rng.random() < 0.7
               else self._safe_block())
        stem = (("minecraft:mushroom_stem",
                 {"down": "false", "east": "true", "north": "true",
                  "south": "true", "up": "false", "west": "true"})
                if rng.random() < 0.75 else self._safe_block())
        cfg = {
            "cap_provider": {"type": "minecraft:simple_state_provider",
                             "state": block_state(cap)},
            "stem_provider": {"type": "minecraft:simple_state_provider",
                              "state": block_state(stem)},
            "can_place_on": self._predicate(),
        }
        if rng.random() < 0.6:
            cfg["foliage_radius"] = rng.randint(0, 5)
        return {"type": "minecraft:huge_%s_mushroom" % ("red" if red else "brown"),
                "config": cfg}

    def _huge_brown_mushroom(self):
        return self._huge_mushroom(red=False)

    def _huge_red_mushroom(self):
        return self._huge_mushroom(red=True)

    def _huge_fungus(self):
        # HugeFungusConfiguration (javap): 5 обязательных полей + planted.
        # replaceable_blocks — BlockPredicate (в ванили — matching_blocks).
        rng = self.rng
        base = (rng.choice(FUNGUS_BASES), None) if rng.random() < 0.5 \
            else self._safe_block()
        # обычно ванильский ствол, но ~30% — из любого solid-блока БЕЗ
        # block entity (шляпка гриба большая, стволов много; свойства
        # ствола placer'ы не трогают — javap)
        if rng.random() < 0.3:
            stem = self._safe_block()
        else:
            stem = (rng.choice(STEM_BLOCKS), {"axis": "y"})
        return {"type": "minecraft:huge_fungus", "config": {
            "valid_base_block": block_state(base),
            "stem_state": block_state(stem),
            "hat_state": block_state(self._safe_block()),
            "decor_state": block_state(self._safe_block()),
            "replaceable_blocks": self._predicate(),
            "planted": rng.random() < 0.5,
        }}

    def _iceberg(self):
        # iceberg_blue.json: только state (BlockStateConfiguration)
        rng = self.rng
        state = (rng.choice(ICE_BLOCKS), None) if rng.random() < 0.7 \
            else self._safe_block()
        return {"type": "minecraft:iceberg", "config": {"state": block_state(state)}}

    def _kelp(self):
        return self._none_cfg("kelp")

    def _large_dripstone(self):
        # large_dripstone.json + javap: column_radius — IntProvider 1-16,
        # height_scale — Float 0-20, bluntness — Float 0.1-10,
        # wind_speed — Float 0-2, floor_to_ceiling_search_range 1-512.
        rng = self.rng
        return {"type": "minecraft:large_dripstone", "config": {
            "replaceable_blocks": rng.choice(
                ["#minecraft:dripstone_replaceable_blocks",
                 "#minecraft:sulfur_spike_replaceable_blocks"]),
            "floor_to_ceiling_search_range": rng.randint(4, 60),
            "column_radius": self._int_provider(1, 8),
            "height_scale": self._float_provider(0.2, 2.0),
            "max_column_radius_to_cave_height_ratio": rnd_f(rng, 0.1, 0.9),
            "stalactite_bluntness": self._float_provider(0.1, 1.0),
            "stalagmite_bluntness": self._float_provider(0.1, 1.0),
            "wind_speed": self._float_provider(0.0, 0.5),
            "min_radius_for_wind": rng.randint(0, 20),
            "min_bluntness_for_wind": rnd_f(rng, 0.0, 1.0),
        }}

    def _monster_room(self):
        return self._none_cfg("monster_room")

    def _multiface(self):
        # glow_lichen.json + javap: block обязан быть multiface-spreadeable;
        # search_range 1-64, chance_of_spreading 0-1 (по умолч. 0.5).
        rng = self.rng
        cfg = {
            "block": rng.choice(MULTIFACE_BLOCKS),
            "can_be_placed_on": rng.sample(SPRING_BLOCKS, rng.randint(1, 6)),
            "search_range": rng.randint(1, 64),
        }
        if rng.random() < 0.7:
            cfg["can_place_on_floor"] = rng.random() < 0.5
        if rng.random() < 0.8:
            cfg["can_place_on_ceiling"] = rng.random() < 0.8
        if rng.random() < 0.8:
            cfg["can_place_on_wall"] = rng.random() < 0.8
        if rng.random() < 0.5:
            cfg["chance_of_spreading"] = rnd_f(rng, 0.0, 1.0)
        return {"type": "minecraft:multiface_growth", "config": cfg}

    def _replace_single_block(self):
        # ReplaceBlockConfiguration — только targets (наследник OreConfiguration)
        return {"type": "minecraft:replace_single_block", "config": {
            "targets": self._ore_targets()}}

    def _root_system(self):
        # rooted_azalea_tree.json + javap: 15 полей, почти все с диапазонами.
        rng = self.rng
        tree_ids = [i for i in self.configured if "_tree" in i]
        fid = rng.choice(tree_ids) if tree_ids and rng.random() < 0.7 \
            else "minecraft:oak"
        if rng.random() < 0.6:  # ванильный предикат позиции дерева
            pos_pred = {"type": "minecraft:all_of", "predicates": [
                {"type": "minecraft:any_of", "predicates": [
                    {"type": "minecraft:matching_block_tag", "tag": "minecraft:air"},
                    {"type": "minecraft:matching_block_tag",
                     "tag": "minecraft:replaceable_by_trees"}]},
                {"type": "minecraft:matching_block_tag", "offset": [0, -1, 0],
                 "tag": "minecraft:azalea_grows_on"}]}
        else:
            pos_pred = self._predicate()
        return {"type": "minecraft:root_system", "config": {
            "feature": {"feature": fid, "placement": []},
            "required_vertical_space_for_tree": rng.randint(1, 32),
            "level_test_distance": rng.randint(0, 16),
            "max_level_deviation": rng.randint(0, 32),
            "root_radius": rng.randint(1, 12),
            "root_replaceable": rng.choice(REPLACEABLE_TAGS[:3]),
            "root_state_provider": self._provider(
                (rng.choice(DIRT_BLOCKS), None)),
            "root_placement_attempts": rng.randint(1, 64),
            "root_column_max_height": rng.randint(4, 120),
            "hanging_root_radius": rng.randint(1, 12),
            "hanging_roots_vertical_span": rng.randint(1, 16),
            "hanging_root_state_provider": self._provider(
                (rng.choice(["minecraft:hanging_roots",
                             "minecraft:mangrove_roots"]), None)),
            "hanging_root_placement_attempts": rng.randint(1, 64),
            "allowed_vertical_water_for_tree": rng.randint(1, 12),
            "allowed_tree_position": pos_pred,
        }}

    def _sculk_patch(self):
        # sculk_patch_deep_dark.json + javap: charge_count 1-32,
        # amount_per_charge 1-500, spread_attempts 1-64, rounds 0-8,
        # extra_rare_growths — IntProvider, catalyst_chance 0-1.
        rng = self.rng
        return {"type": "minecraft:sculk_patch", "config": {
            "charge_count": rng.randint(1, 32),
            "amount_per_charge": rng.randint(1, 128),
            "spread_attempts": rng.randint(1, 64),
            "growth_rounds": rng.randint(0, 8),
            "spread_rounds": rng.randint(0, 8),
            "extra_rare_growths": self._int_provider(0, 4),
            "catalyst_chance": rnd_f(rng, 0.0, 1.0)}}

    def _sea_pickle(self):
        # CountConfiguration: count — int ИЛИ IntProvider, диапазон 0-256
        rng = self.rng
        if rng.random() < 0.5:
            count = rng.randint(0, 40)
        else:
            count = self._int_provider(0, 40)
        return {"type": "minecraft:sea_pickle", "config": {"count": count}}

    def _seagrass(self):
        # ProbabilityFeatureConfiguration: probability 0-1
        return {"type": "minecraft:seagrass", "config": {
            "probability": rnd_f(self.rng, 0.0, 1.0)}}

    def _simple_random_selector(self):
        # pointed_dripstone.json: features — список placed-фич (inline)
        return {"type": "minecraft:simple_random_selector", "config": {
            "features": [self._placed_ref()
                         for _ in range(self.rng.randint(1, 3))]}}

    def _twisting_vines(self):
        # twisting_vines.json: три обычных int
        rng = self.rng
        return {"type": "minecraft:twisting_vines", "config": {
            "spread_width": rng.randint(4, 16),
            "spread_height": rng.randint(1, 8),
            "max_height": rng.randint(4, 24)}}

    def _underwater_magma(self):
        # underwater_magma.json + javap: floor 0-512, radius 0-64, prob 0-1
        rng = self.rng
        return {"type": "minecraft:underwater_magma", "config": {
            "floor_search_range": rng.randint(1, 32),
            "placement_radius_around_floor": rng.randint(0, 8),
            "placement_probability_per_valid_position": rnd_f(rng, 0.0, 1.0)}}

    def _vegetation_patch_cfg(self):
        # moss_patch.json + javap: depth — IntProvider 1-128,
        # vertical_range 1-256, xz_radius — IntProvider, шансы 0-1.
        rng = self.rng
        veg_ids = [i for i in self.configured
                   if "_patch" in i or "simple" in i]
        fid = rng.choice(veg_ids) if veg_ids and rng.random() < 0.7 \
            else "minecraft:grass"
        rmin = rng.randint(1, 3)
        return {
            "replaceable": rng.choice(["#minecraft:moss_replaceable",
                                       "#minecraft:lush_ground_replaceable"]),
            "ground_state": self._safe_provider(),
            "vegetation_feature": {"feature": fid, "placement": []},
            "surface": rng.choice(["floor", "ceiling"]),
            "depth": self._int_provider(1, 6),
            "extra_bottom_block_chance": rnd_f(rng, 0.0, 1.0),
            "vertical_range": rng.randint(1, 16),
            "vegetation_chance": rnd_f(rng, 0.0, 1.0),
            "xz_radius": {"type": "minecraft:uniform", "min_inclusive": rmin,
                          "max_inclusive": rng.randint(rmin + 1, 7)},
            "extra_edge_column_chance": rnd_f(rng, 0.0, 1.0),
        }

    def _vegetation_patch(self):
        return {"type": "minecraft:vegetation_patch",
                "config": self._vegetation_patch_cfg()}

    def _waterlogged_vegetation_patch(self):
        # clay_pool_with_dripleaves.json: те же поля, другой тип
        return {"type": "minecraft:waterlogged_vegetation_patch",
                "config": self._vegetation_patch_cfg()}

    def _weeping_vines(self):
        return self._none_cfg("weeping_vines")

    def _weighted_random_selector(self):
        # WeightedList: элементы {"data": placed, "weight": int>=0};
        # нужен хотя бы один ненулевой вес (валидация кодека).
        rng = self.rng
        return {"type": "minecraft:weighted_random_selector", "config": {
            "features": [{"data": self._placed_ref(),
                          "weight": rng.randint(1, 9)}
                         for _ in range(rng.randint(1, 4))]}}

    def _sequence(self):
        # CompositeFeatureConfiguration: features — список placed-фич,
        # размещаются по очереди до первой удачной
        return {"type": "minecraft:sequence", "config": {
            "features": [self._placed_ref()
                         for _ in range(self.rng.randint(1, 3))]}}

    def _nether_vegetation(self):
        # crimson_forest_vegetation.json: state_provider + два int
        rng = self.rng
        if rng.random() < 0.4:
            sp = {"type": "minecraft:weighted_state_provider",
                  "entries": [{"data": {"Name": p}, "weight": rng.randint(1, 30)}
                              for p in rng.sample(PLANT_BLOCKS,
                                                  rng.randint(2, 5))]}
        else:
            sp = self._provider((rng.choice(PLANT_BLOCKS), None))
        return {"type": "minecraft:nether_forest_vegetation", "config": {
            "state_provider": sp,
            "spread_width": rng.randint(1, 16),
            "spread_height": rng.randint(1, 8)}}

    def _random_selector(self):
        # mangrove_vegetation.json: features с chance + default
        rng = self.rng
        return {"type": "minecraft:random_selector", "config": {
            "default": self._placed_ref(),
            "features": [{"chance": rnd_f(rng, 0.0, 1.0),
                          "feature": self._placed_ref()}
                         for _ in range(rng.randint(1, 3))]}}

    def _random_boolean_selector(self):
        # feature_true / feature_false — placed-фичи
        return {"type": "minecraft:random_boolean_selector", "config": {
            "feature_true": self._placed_ref(),
            "feature_false": self._placed_ref()}}

    def _pointed_block_state(self):
        rng = self.rng
        return {"Name": rng.choice(POINTED_BLOCKS), "Properties": {
            "thickness": "tip",
            "vertical_direction": rng.choice(["up", "down"]),
            "waterlogged": "false"}}

    def _speleothem(self):
        # speleothem (из pointed_dripstone.json): base/pointed/replaceable
        # + 4 опциональных шанса 0-1
        rng = self.rng
        cfg = {
            "base_block": block_state(self._block()),
            "pointed_block": self._pointed_block_state(),
            "replaceable_blocks": rng.choice(
                ["#minecraft:dripstone_replaceable_blocks",
                 "#minecraft:sulfur_spike_replaceable_blocks"]),
        }
        for field in ("chance_of_taller_generation",
                      "chance_of_directional_spread",
                      "chance_of_spread_radius2", "chance_of_spread_radius3"):
            if rng.random() < 0.5:
                cfg[field] = rnd_f(rng, 0.0, 1.0)
        return {"type": "minecraft:speleothem", "config": cfg}

    def _speleothem_cluster(self):
        # dripstone_cluster.json + javap: height/radius — IntProvider 1-128,
        # thickness 0-128, floor_to_ceiling 1-512, height_deviation 1-64.
        rng = self.rng
        hmin = rng.randint(1, 3)
        rmin = rng.randint(1, 3)
        tmin = rng.randint(0, 2)
        return {"type": "minecraft:speleothem_cluster", "config": {
            "base_block": block_state(self._block()),
            "pointed_block": self._pointed_block_state(),
            "replaceable_blocks": rng.choice(
                ["#minecraft:dripstone_replaceable_blocks",
                 "#minecraft:sulfur_spike_replaceable_blocks"]),
            "floor_to_ceiling_search_range": rng.randint(4, 60),
            "height": {"type": "minecraft:uniform", "min_inclusive": hmin,
                       "max_inclusive": rng.randint(hmin + 1, 8)},
            "radius": {"type": "minecraft:uniform", "min_inclusive": rmin,
                       "max_inclusive": rng.randint(rmin + 1, 8)},
            "max_stalagmite_stalactite_height_diff": rng.randint(0, 8),
            "height_deviation": rng.randint(1, 8),
            "speleothem_block_layer_thickness": {
                "type": "minecraft:uniform", "min_inclusive": tmin,
                "max_inclusive": rng.randint(tmin + 1, 5)},
            "density": self._float_provider(0.1, 0.9),
            "wetness": self._float_provider(0.0, 0.9),
            "chance_of_speleothem_at_max_distance_from_center": rnd_f(rng, 0.0, 1.0),
            "max_distance_from_edge_affecting_chance_of_speleothem": rng.randint(1, 8),
            "max_distance_from_center_affecting_height_bias": rng.randint(1, 12),
        }}

    def _spike(self):
        # SpikeConfiguration (javap): state + два предиката, все обязательны;
        # state — без BE: шип — высокий столб до потолка, BE-блок лезет
        # выше потолка мира и оставляет DUMMY-мусор
        return {"type": "minecraft:spike", "config": {
            "state": block_state(self._safe_block()),
            "can_place_on": self._predicate(),
            "can_replace": self._predicate()}}

    def _vines(self):
        return self._none_cfg("vines")

    # ---------------- placed: placement-конвейер ----------------

    # Поверхностная растительность: ей нужны «рецепты естественной
    # плотности» (см. _count_modifier) — иначе фиксированный count на
    # чанк даёт равномерную «дрожащую сетку» 1 дерево/чанк.
    _SURFACE_VEG = {
        "tree", "fallen_tree", "root_system", "bamboo",
        "huge_brown_mushroom", "huge_red_mushroom", "huge_fungus",
        "block_pile", "block_blob", "vegetation_patch",
        "waterlogged_vegetation_patch",
    }

    # Незер/пещерные виды — единственные ванильные пользователи
    # count_on_every_layer (crimson_forest_vegetation, delta, basalt_columns,
    # cave_vine...): он сам находит Y по слоям, heightmap после него не нужен
    _LAYERED_KINDS = {
        "nether_vegetation", "basalt_columns", "basalt_pillar", "delta",
        "replace_blobs", "glowstone_blob", "multiface", "vines",
        "twisting_vines", "weeping_vines", "speleothem", "speleothem_cluster",
    }

    # Пещерным видам, которым подходит послойное размещение: к незерным
    # добавлена «напольная» растительность и грибы — в пещерах им нужен
    # пол, который count_on_every_layer находит сам (ваниль размещает
    # так огромные грибы и растительность незера)
    _CAVE_LAYERED = _LAYERED_KINDS | {
        "patch", "nether_vegetation", "block_pile", "block_column",
        "block_blob", "huge_brown_mushroom", "huge_red_mushroom",
        "huge_fungus", "fallen_tree",
    }

    # Этим видам в пещерном height_range-пути нужен фильтр «под позицией
    # твёрдый блок» — иначе растения и валуны висят в воздухе
    _CAVE_FLOOR = {
        "patch", "block_pile", "block_column", "block_blob", "fallen_tree",
        "huge_brown_mushroom", "huge_red_mushroom", "huge_fungus",
        "root_system", "vegetation_patch", "waterlogged_vegetation_patch",
    }

    def _count_modifier(self, kind):
        """Count-часть конвейера. Возвращает СПИСОК модификаторов (иногда
        их несколько: rarity + count = «рощи»).

        Для поверхностной растительности — ванильные рецепты естественной
        плотности (почему это важно: фиксированный count даёт каждому чанку
        одинаковое число попыток, а in_square лишь равномерно бросает позицию
        внутри чанка — получается почти равномерная сетка «1 дерево/чанк»;
        ваниль рвёт её тремя способами: ДИСПЕРСИЯ count (IntProvider —
        trees_birch: weighted_list 10/11), РЕГИОНАЛЬНЫЙ шум (noise_based_count
        — бамбук; noise_threshold_count — цветы) и RARITY (луга: 1/100
        чанков; грибы: 1/256..512)."""
        rng = self.rng
        if kind == "patch":  # «tries» патча: 8-96 попыток
            if rng.random() < 0.8:
                return [{"type": "minecraft:count",
                         "count": rng.randint(8, 96)}]
            return [{"type": "minecraft:count",
                     "count": self._int_provider(8, 96)}]

        if kind == "ore":
            # руды — ванильные масштабы жил (coal 20, iron 8-16, diamond
            # 4-8 попыток/чанк): чаще всего густо, изредка «редкая руда»
            # (rarity + несколько жил), как древние обломки в незере
            r = rng.random()
            if r < 0.55:
                return [{"type": "minecraft:count",
                         "count": rng.randint(4, 24)}]
            if r < 0.75:
                return [{"type": "minecraft:count",
                         "count": self._int_provider(2, 24)}]
            if r < 0.9:
                return [{"type": "minecraft:rarity_filter",
                         "chance": rng.choice([2, 4, 8, 16, 32])},
                        {"type": "minecraft:count",
                         "count": rng.randint(1, 4)}]
            return [{"type": "minecraft:count", "count": rng.randint(1, 8)}]

        if kind in self._SURFACE_VEG:
            r = rng.random()
            if r < 0.30:
                # густой лес: count-провайдер с большой дисперсией —
                # соседние чанки получают РАЗНЫЕ значения (2 и 16) → рощи
                lo = rng.randint(0, 3)
                hi = rng.randint(6, 20)
                prov = self._int_provider(lo, hi)
                if prov["type"] == "minecraft:weighted_list":
                    # в weighted_list подмешиваем 0 — пустые прогалы
                    prov["distribution"].insert(
                        0, {"data": 0, "weight": rng.randint(1, 3)})
                return [{"type": "minecraft:count", "count": prov}]
            if r < 0.50:
                # редкие одиночки/пары: rarity как у деревьев луга (1/100)
                # и грибов (1/256..512) — изолированные, пуассоново
                return [{"type": "minecraft:rarity_filter",
                         "chance": rng.choice([4, 8, 16, 32, 64, 100,
                                               171, 256, 384])}]
            if r < 0.65:
                # рощи: 1/N чанков, но сразу по несколько (count 2-5)
                return [{"type": "minecraft:rarity_filter",
                         "chance": rng.randint(3, 24)},
                        {"type": "minecraft:count",
                         "count": self._int_provider(2, 5)}]
            if r < 0.80:
                # региональный шум (бамбук: factor 80, offset 0.3, ratio 160)
                return [{"type": "minecraft:noise_based_count",
                         "noise_factor": rnd_f(rng, 40.0, 120.0),
                         "noise_offset": rnd_f(rng, -0.2, 0.4),
                         "noise_to_count_ratio": rng.randint(60, 200)}]
            if r < 0.92:
                # порог по шуму (flower_plains: above 4, below 15, -0.8)
                return [{"type": "minecraft:noise_threshold_count",
                         "above_noise": rng.randint(4, 12),
                         "below_noise": rng.randint(0, 15),
                         "noise_level": -0.8}]
            # старый вид: фиксированный count — редко и маленький
            return [{"type": "minecraft:count", "count": rng.randint(1, 3)}]

        if kind == "lake":
            # озёра: 1-3 на чанк (раньше шли через общий branch —
            # 1-24 озера на чанк = «спам озёрами»)
            return [{"type": "minecraft:count", "count": rng.randint(1, 3)}]

        # прочие виды (руды, диски, спринги...): как раньше
        r = rng.random()
        if r < 0.50:
            return [{"type": "minecraft:count", "count": rng.randint(1, 24)}]
        if r < 0.58:  # count тоже принимает IntProvider
            return [{"type": "minecraft:count",
                     "count": self._int_provider(1, 24)}]
        if r < 0.72 and kind in self._LAYERED_KINDS:
            # count_on_every_layer: count опционален, int/провайдер;
            # только незер/пещерным — деревьям он не нужен (ваниль им его
            # не даёт), и после него heightmap не ставится (см. _placement)
            if rng.random() < 0.5:
                return [{"type": "minecraft:count_on_every_layer",
                         "count": rng.randint(1, 8)}]
            return [{"type": "minecraft:count_on_every_layer",
                     "count": self._int_provider(1, 8)}]
        if r < 0.88:
            return [{"type": "minecraft:rarity_filter",
                     "chance": rng.randint(2, 96)}]
        if r < 0.95:  # flower_plains.json
            return [{"type": "minecraft:noise_threshold_count",
                     "above_noise": rng.randint(1, 8),
                     "below_noise": rng.randint(1, 32),
                     "noise_level": rnd_f(rng, -1.0, 1.0)}]
        # patch_large_fern.json
        return [{"type": "minecraft:noise_based_count",
                 "noise_factor": rnd_f(rng, 40.0, 120.0),
                 "noise_offset": rnd_f(rng, -0.5, 0.5),
                 "noise_to_count_ratio": rng.randint(40, 240)}]

    def _random_offset(self):
        """Разброс патча — формат patch_grass_normal.json (провайдеры)
        или pointed_dripstone.json (простые int)."""
        rng = self.rng
        xz = rng.randint(1, 7)
        y = rng.randint(1, 5)
        if rng.random() < 0.4:  # простые int — как pointed_dripstone
            return {"type": "minecraft:random_offset",
                    "xz_spread": xz, "y_spread": y}
        return {"type": "minecraft:random_offset",
                "xz_spread": {"type": "minecraft:trapezoid", "min": -xz,
                              "max": xz, "plateau": 0},
                "y_spread": {"type": "minecraft:trapezoid", "min": -y,
                             "max": y, "plateau": 0}}

    def _filter_modifier(self, kind):
        rng = self.rng
        r = rng.random()
        if r < 0.35:
            return {"type": "minecraft:biome"}
        if r < 0.62:
            # деревьям часто — проверку «саженец выживет» (как *_checked)
            if kind == "tree" and rng.random() < 0.6:
                predicate = {"type": "minecraft:would_survive",
                             "state": {"Name": rng.choice(SAPLINGS),
                                       "Properties": {"stage": "0"}}}
            else:
                predicate = self._predicate()
            return {"type": "minecraft:block_predicate_filter",
                    "predicate": predicate}
        if r < 0.78:  # lake_lava_underground.json
            mod = {"type": "minecraft:environment_scan",
                   "direction_of_search": rng.choice(["up", "down"]),
                   "max_steps": rng.randint(4, 32),
                   "target_condition": self._predicate()}
            if rng.random() < 0.3:
                mod["allowed_search_condition"] = {
                    "type": "minecraft:matching_block_tag",
                    "tag": "minecraft:air"}
            return mod
        if r < 0.90:  # lake_lava_underground.json; min/max — оба опциональны
            mod = {"type": "minecraft:surface_relative_threshold_filter",
                   "heightmap": rng.choice(HEIGHTMAPS),
                   "max_inclusive": rng.randint(-16, 0)}
            if rng.random() < 0.5:
                mod["min_inclusive"] = rng.randint(-24, -1)
            return mod
        # patch_sugar_cane.json
        return {"type": "minecraft:surface_water_depth_filter",
                "max_water_depth": rng.randint(0, 8)}

    def _placement(self, kind):
        """Конвейер placement длиной 1-4 (патчу — до 5: нужен random_offset).
        Порядок как в ванильных фичах: count -> in_square -> высота ->
        random_offset -> фильтры.
        Ванильные инварианты (проверено на сервере 26.2):
        - count_on_every_layer сам рандомизирует позицию внутри чанка и
          НИКОГДА не идёт вместе с in_square — иначе позиции уходят на
          2 чанка в сторону («setBlock in a far chunk»/«unsafe terrain
          read», вплоть до зависания генерации);
        - fixed_placement задаёт АБСОЛЮТНЫЕ координаты и годится только
          для разовых фич (end_platform) — в пер-чанковой декорации он
          писал бы в далёкие чанки из каждого чанка, поэтому здесь
          не используется."""
        if self.cave:
            return self._cave_placement(kind)
        rng = self.rng
        pipeline = []
        first_mods = []
        if rng.random() < 0.9:  # сколько раз в чанке
            first_mods = self._count_modifier(kind)
            pipeline.extend(first_mods)
        first_types = {m["type"] for m in first_mods}
        layered = "minecraft:count_on_every_layer" in first_types
        # in_square — ОБЯЗАТЕЛЕН (кроме layered): без него x/z остаются
        # УГЛОМ ЧАНКА и фичи встают в идеальную сетку с шагом 16. В ванили
        # у каждой пер-чанковой фичи есть in_square / random_offset /
        # count_on_every_layer — что-то одно всегда рандомизирует позицию.
        if not layered:
            pipeline.append({"type": "minecraft:in_square"})
        if rng.random() < 0.9 and not layered:  # высота (не после layered!)
            # руды — ВСЕГДА height_range: жила должна быть ВНУТРИ рельефа
            # (как ванильные ore_*), heightmap ставил бы её на поверхность;
            # подводным фичам — дно океана, остальным — любой heightmap
            if kind == "ore":
                pipeline.append({"type": "minecraft:height_range",
                                 "height": self._height_provider()})
            elif kind in ("kelp", "seagrass", "sea_pickle", "coral",
                          "underwater_magma", "waterlogged_vegetation_patch"):
                hm = rng.choice(["OCEAN_FLOOR", "OCEAN_FLOOR_WG",
                                 "WORLD_SURFACE_WG"])
                if rng.random() < 0.55:
                    pipeline.append({"type": "minecraft:heightmap",
                                     "heightmap": hm})
                else:
                    pipeline.append({"type": "minecraft:height_range",
                                     "height": self._height_provider()})
            else:
                hm = rng.choice(HEIGHTMAPS)
                if rng.random() < 0.55:
                    pipeline.append({"type": "minecraft:heightmap",
                                     "heightmap": hm})
                else:
                    pipeline.append({"type": "minecraft:height_range",
                                     "height": self._height_provider()})
        if kind == "patch":  # обязателен: без него патч — точка
            pipeline.append(self._random_offset())
        for _ in range(rng.randint(0, 2)):  # фильтры
            pipeline.append(self._filter_modifier(kind))
        # деревьям с высокой плотностью — прореживание как в ванили
        # (trees_birch: count 10-16 + would_survive/surface_water_depth —
        # иначе «густой лес» из count-провайдера стоит стеной). Работает на
        # любой поверхности — в отличие от would_survive (тому нужна земля).
        if kind == "tree" and not any(
                m["type"] == "minecraft:block_predicate_filter"
                for m in pipeline) and rng.random() < 0.75:
            if rng.random() < 0.5:
                pipeline.append({"type": "minecraft:block_predicate_filter",
                                 "predicate": {
                                     "type": "minecraft:would_survive",
                                     "state": {"Name": rng.choice(SAPLINGS),
                                               "Properties": {"stage": "0"}}}})
            else:
                pipeline.append({"type": "minecraft:surface_water_depth_filter",
                                 "max_water_depth": 0})
        if not pipeline:
            pipeline.append({"type": "minecraft:in_square"})
        cap = 5 if kind == "patch" else 4
        return pipeline[:cap]

    def _cave_placement(self, kind):
        """Placement для ПОДЗЕМНЫХ биомов (self.cave). ГЛАВНОЕ: никогда
        heightmap — он ставит фичу на ПОВЕРХНОСТЬ мира (первый воздух
        сверху), а нужен пол пещеры. Вместо него:
        - count_on_every_layer (ванильный пещерный механизм, см.
          _LAYERED_KINDS): сам находит позиции на твёрдых блоках в
          воздушных слоях — так размещают растительность незера и пещер;
        - height_range с широкой относительной полосой (почти вся
          высота мира, как ванильные glow_lichen/large_dripstone) —
          фичи, которые сами сканируют пространство (multiface,
          sculk_patch, speleothem, geode, monster_room), находят стены,
          полы и потолки сами.
        Растительности — фильтр «под позицией твёрдое»: не висит в
        воздухе. surface_relative_threshold_filter не используем: он
        сравнивает Y с ПОВЕРХНОСТЬЮ мира и в пещерах режет всё."""
        rng = self.rng
        if kind in self._CAVE_LAYERED and rng.random() < 0.6:
            if rng.random() < 0.7:
                cnt = rng.randint(1, 8)
            else:
                cnt = self._int_provider(1, 8)
            return [{"type": "minecraft:count_on_every_layer", "count": cnt}]
        pipeline = self._count_modifier(kind)
        if any(m["type"] == "minecraft:count_on_every_layer" for m in pipeline):
            return pipeline  # слойный механизм уже нашёл Y — после него ничего
        pipeline.append({"type": "minecraft:in_square"})
        pipeline.append({"type": "minecraft:height_range",
                         "height": self._cave_height_provider()})
        if kind in self._CAVE_FLOOR:
            # «под позицией твёрдое»: растения и валуны — на полу
            pipeline.append({"type": "minecraft:block_predicate_filter",
                             "predicate": {"type": "minecraft:solid",
                                           "offset": [0, -1, 0]}})
        elif rng.random() < 0.2:
            pipeline.append({"type": "minecraft:block_predicate_filter",
                             "predicate": self._predicate()})
        if kind == "patch":
            pipeline.append(self._random_offset())
        return pipeline[:5]


# ---------------------------------------------------------------------------
# Публичная функция
# ---------------------------------------------------------------------------

def rand_features(rng, ns, name, min_y, max_y, count=None, cave=False,
                 no_gravity=False):
    """Случайные configured+placed features. Возвращает
    (configured, placed, tags): три dict {id: json}, id — namespaced строки
    'ns:...'. tags — block-теги («земля» измерения для рудных целей),
    пишутся в data/<ns>/tags/block/.

    count — сколько configured-фич создать (по умолчанию 4-14 — старое
    поведение; вызывается с числом из тяжело-хвостового распределения).
    cave=True — пещерный режим для ПОДЗЕМНЫХ биомов: только виды, не
    требующие ни неба, ни поверхности (CAVE_FEATURE_KINDS), и placement
    без heightmap — он ставит фичу на верх мира, а не на пол пещеры
    (см. _cave_placement). no_gravity=True — VOID-режим: пулы
    размещения без сыпучих (падающий блок над пустотой обращается в
    entity FALLING_BLOCK; см. _FeatureFactory.__init__). Формат каждой фичи подтверждён ванильным
    jar 26.2, по 1-2 placed на каждую. Весь рандом — только через rng
    (random.Random)."""
    factory = _FeatureFactory(rng, ns, name, min_y, max_y, cave=cave,
                              no_gravity=no_gravity)
    kinds_cfg = CAVE_FEATURE_KINDS if cave else FEATURE_KINDS
    kinds = [k for k, _ in kinds_cfg]
    weights = [w for _, w in kinds_cfg]
    n = count if count is not None else rng.randint(4, 14)
    for _ in range(n):
        kind = rng.choices(kinds, weights=weights)[0]
        cid = factory._uid(kind)
        factory.configured[cid] = factory._builders[kind]()
        for p in range(rng.randint(1, 2)):
            pid = "%s_p%d" % (cid, p + 1)
            factory.placed[pid] = {"feature": cid,
                                   "placement": factory._placement(kind)}
    tags = {}
    if factory.ground_needed:
        # тег «земли»: вся палитра рельефа (default_block + surface rules).
        # id цели уже раздали фичи через factory._ground_tag()
        tags["%s:%s_ground" % (ns, name)] = {
            "replace": False, "values": _palette_ids()}
    return dict(factory.configured), dict(factory.placed), tags


def rand_ores(rng, ns, name, min_y, max_y, count=None, no_gravity=False):
    """Рудная система измерения — отдельный проход поверх rand_features
    (руды убраны из общего FEATURE_KINDS, чтобы число видов было
    управляемым: по аудиту существующих данных медиана была 1 руда на
    измерение, а 3 мира из 32 — вообще без руд).

    Что создаёт на каждое измерение:
    - count (по умолчанию 5-9) ВИДОВ руд: свои блоки/цели/размер жилы
      (2-20 с тяжёлым хвостом; обычным, НЕ-редким видам нижняя
      граница count поднята до 3 — юзер просил гуще обычные руды),
      иногда scattered_ore;
    - у каждого вида ЧЕТЫРЕ placed-варианта богатства — ×0.3/×1/×2.5/×5
      от базового count 2-20 (id <name>_oreM_p1..p4 по порядку
      множителей); ~20% видов — «редкие» (rarity_filter 1/2-1/8 чанков,
      как древние обломки в незере);
    - высоты — ОТНОСИТЕЛЬНЫЕ якоря (above_bottom/below_top) по ДОЛЯМ
      высоты мира, полосы смещены вниз, в рельеф (см.
      _ore_height_provider): absolute-полосы из _pair_y могли целиком
      попасть в воздух над поверхностью — и жилы с
      discard_chance_on_air_exposure не спавнились вовсе.

    Цели замены (targets) — как раньше: почти всегда тег «земли»
    измерения (вся палитра рельефа) — руда заменяет фактический рельеф,
    а не ванильный камень, которого в случайном мире может не быть.

    Возвращает (configured, placed, tags, variants): variants —
    {configured_id: {"poor": placed_id, "normal": ..., "rich": ...,
    "motherlode": ...}} для пер-биомной раздачи в generate_dimension.
    no_gravity=True — VOID-режим: блоки жил без сыпучих (см.
    _FeatureFactory.__init__)."""
    factory = _FeatureFactory(rng, ns, name, min_y, max_y,
                              no_gravity=no_gravity)
    n = count if count is not None else rng.randint(5, 9)
    configured, placed, tags, variants = {}, {}, {}, {}
    for _ in range(n):
        cid = factory._uid("ore")
        configured[cid] = factory._ore()
        hp = factory._ore_height_provider()
        # базовый count (он же «normal»-вариант): 2-20 (НЕ-редким видам
        # нижняя граница 3 — обычные руды встречаются почаще), мелкие
        # чаще — дисперсия между видами руд одного мира
        rare = rng.random() < 0.2
        base = rng.randint(2 if rare else 3, 10) \
            if rng.random() < 0.7 else rng.randint(11, 20)
        tiers = {}
        for k, (tier, mult) in enumerate(ORE_MULTIPLIERS):
            # конвейер как у ванильных ore_*: count -> in_square ->
            # height_range -> biome (биом-фильтр — двойная проверка, что
            # позиция всё ещё в биоме, разместившем фичу)
            mods = []
            if rare:
                mods.append({"type": "minecraft:rarity_filter",
                             "chance": rng.choice([2, 4, 8])})
            mods.append({"type": "minecraft:count",
                         "count": max(1, int(round(base * mult)))})
            mods.append({"type": "minecraft:in_square"})
            mods.append({"type": "minecraft:height_range", "height": hp})
            mods.append({"type": "minecraft:biome"})
            pid = "%s_p%d" % (cid, k + 1)
            placed[pid] = {"feature": cid, "placement": mods}
            tiers[tier] = pid
        variants[cid] = tiers
    if factory.ground_needed:
        tags["%s:%s_ground" % (ns, name)] = {
            "replace": False, "values": _palette_ids()}
    return configured, placed, tags, variants


def rand_stone_blobs(rng, ns, name, min_y, max_y, family, vein=None):
    """Блобы КАМЕННОГО СЕМЕЙСТВА — «большие блобы» как ванильные
    андезит/диорит/гранит/туф: ore-фича с size 15-64 и count 1-6 на
    чанк, полоса высот по ДОЛЯМ высоты мира (относительные якоря,
    _blob_height_provider), discard_on_air_exposure 0.0 (камень не
    прячется от воздуха, как ванильные блобы гранита).

    family — [(блок, тир), ...] от generate_dimension._select_stone_family
    (тиры "common"/"normal"/"rare"; блоки — (id, props) кортежи, уже без
    сыпучих для void-миров). Параметры по тирам:
      «частые»  — size 33-64, count 3-6 (гуще и крупнее);
      «обычные» — size 20-48, count 2-4;
      «редкие»  — size 15-33, count 1-2 + rarity_filter 1/4-1/16
                  (редкие — ещё реже).
    vein — опциональная «жила-стержень» одного РЕДКОГО блока:
    вертикальные узкие блобы (size 2-6 + count 8-24, rarity 1/2-1/8,
    высокий пояс высот — см. _vein_height_provider).

    id: configured <name>_stoneN, placed <name>_blobN — один блоб на
    камень (+жила). Блобы кладём в ОБЩИЙ пул измерения (каждый биом,
    как ванильные ore_granite/ore_andesite — камень генерится везде,
    это не пер-биомная декорация); пер-биомные множители руд НЕ трогаем.

    Возвращает (configured, placed, tags): tags — тег «земли» (цели
    блобов tag_match). Семейство фильтрует от сыпучих вызывающий код —
    сюда блоки приходят уже чистыми, отдельный флаг не нужен."""
    factory = _FeatureFactory(rng, ns, name, min_y, max_y)
    configured, placed = {}, {}
    tier_cfg = {           # (size_lo, size_hi, count_lo, count_hi, rarity)
        "common": (33, 64, 3, 6, None),
        "normal": (20, 48, 2, 4, None),
        "rare":   (15, 33, 1, 2, "rare"),
    }
    for blk, tier in family:
        cid = factory._uid("stone")           # <ns>:<name>_stoneN
        n = factory._counters["stone"]
        slo, shi, clo, chi, rar = tier_cfg[tier]
        configured[cid] = {
            "type": "minecraft:ore",
            "config": {
                "discard_chance_on_air_exposure": 0.0,
                "size": rng.randint(slo, shi),
                "targets": factory._blob_targets(blk),
            }}
        # конвейер как у ванильных ore_granite: [rarity ->] count ->
        # in_square -> height_range -> biome (двойная проверка позиции)
        mods = []
        if rar:
            mods.append({"type": "minecraft:rarity_filter",
                         "chance": rng.choice([4, 8, 16])})
        mods.append({"type": "minecraft:count",
                     "count": rng.randint(clo, chi)})
        mods.append({"type": "minecraft:in_square"})
        mods.append({"type": "minecraft:height_range",
                     "height": factory._blob_height_provider(tier)})
        mods.append({"type": "minecraft:biome"})
        pid = "%s:%s_blob%d" % (ns, name, n)   # <ns>:<name>_blobN
        placed[pid] = {"feature": cid, "placement": mods}
    if vein is not None:
        cid = factory._uid("stone")
        n = factory._counters["stone"]
        configured[cid] = {
            "type": "minecraft:ore",
            "config": {
                "discard_chance_on_air_exposure": 0.0,
                "size": rng.randint(2, 6),
                "targets": factory._blob_targets(vein),
            }}
        placed["%s:%s_blob%d" % (ns, name, n)] = {
            "feature": cid,
            "placement": [
                {"type": "minecraft:rarity_filter",
                 "chance": rng.choice([2, 4, 8])},
                {"type": "minecraft:count", "count": rng.randint(8, 24)},
                {"type": "minecraft:in_square"},
                {"type": "minecraft:height_range",
                 "height": factory._vein_height_provider()},
                {"type": "minecraft:biome"},
            ]}
    tags = {}
    if factory.ground_needed:
        tags["%s:%s_ground" % (ns, name)] = {
            "replace": False, "values": _palette_ids()}
    return configured, placed, tags


# ---------------------------------------------------------------------------
# Сигнатурные фичи АРХЕТИПОВ подземных биомов (rand_cave_features)
# ---------------------------------------------------------------------------
# Восемь архетипов «как в ваниле» (lush/dripstone/deep_dark — эталонная
# тройка, плюс кристальная/грибная/корневая/магмовая/замёрзшая). Фичи
# архетипа строятся ПО ЗАДАННЫМ блокам (не случайным пулом) — это и есть
# идентичность: пышная пещера = мох + светящиеся ягоды + споры, натёчная
# = кластеры натёков, глубокая тьма = вены скалка без монстров.
#
# Все форматы скопированы с ванильных configured/placed-фич jar 26.2:
#   cave_vine.json          — block_column ВНИЗ (cave_vines_plant + ягоды)
#   moss_patch.json         — vegetation_patch (пол, ground=moss_block)
#   spore_blossom.json/pl.  — simple_block + environment_scan ВВЕРХ
#   dripleaf.json           — simple_random_selector малой/большой листвы
#   dripstone_cluster.json  — speleothem_cluster (dripstone_block)
#   pointed_dripstone.json  — simple_random_selector из двух speleothem
#                             (с INLINE-сканом пола/потолка)
#   sculk_patch_deep_dark.. — sculk_patch (extra_rare_growths 0 — у нас
#                             0-2: сенсоры это block entity, ≤2 на пятно)
#   amethyst_geode.json     — geode с аметистовыми слоями
#   huge_brown_mushroom...  — огромные грибы (стволы/шляпки ванильские)
#   rooted_azalea_tree.json — root_system (корни + свисающие корни)
# Плотности — ванильные (count на чанк; большинство попыток не проходит
# скан — поэтому у cave_vines/sculk_vein счётёт трёхзначный).
#
# ВИДЫ (поле type configured-фичи) у ЛЮБЫХ двух архетипов пересекаются
# не более чем на один — инвариант различимости биомов сохраняется без
# перегенераций (набор архетипа фиксирован, фильтр сигнатурности
# _rand_biome_features его менять не может). Таблицу соответствия см.
# _CAVE_RECIPE_TYPE — самотест проверяет попарные пересечения.

# (placement-стиль, (count_lo, count_hi)) для каждого рецепта.
# Стили placement (все заканчиваются biome-фильтром, как ваниль):
#   "floor"   — count → in_square → height_range → environment_scan ВНИЗ
#               (воздух → solid) → random_offset(+1) → biome: на пол пещеры
#   "ceil"    — то же, но скан ВВЕРХ и offset(-1): под потолок
#   "berries" — скан ВВЕРХ до has_sturdy_face down: свисающие лозы/ягоды
#   "wide"    — без скана (фича сама ищет пространство вокруг позиции):
#               speleothem_cluster/large_dripstone/sculk/geode/multiface
#   "rare"    — wide + rarity_filter (жеоды: 1/8-1/24 чанков)
#   "layer"   — count_on_every_layer (незер-механизм: сам находит слой)
_CAVE_RECIPE_SPEC = {
    # --- пышная (lush) ---
    "cave_vines":      ("berries", (96, 188)),
    "moss_floor":      ("floor", (48, 125)),
    "moss_ceiling":    ("ceil", (24, 96)),
    "spore_blossom":   ("ceil", (8, 25)),
    "dripleaf":        ("floor", (16, 64)),
    "mossy_boulder":   ("floor", (1, 6)),
    # --- натёчная (dripstone) ---
    "dripstone_cluster": ("wide", (24, 96)),
    "pointed_dripstone": ("wide", (96, 256)),
    "large_dripstone":   ("wide", (8, 48)),
    "calcite_veins":     ("wide", (2, 12)),
    # --- глубокая тьма (deep_dark) ---
    "sculk_vein":        ("wide", (96, 250)),
    "sculk_patch":       ("wide", (16, 64)),
    "glow_lichen_rare":  ("wide", (8, 32)),
    "deepslate_veins":   ("wide", (2, 10)),
    # --- кристальная (crystal) ---
    "amethyst_geode":    ("rare", (1, 2)),
    "amethyst_cluster":  ("floor", (16, 64)),
    "amethyst_veins":    ("wide", (2, 10)),
    "crystal_spikes":    ("floor", (2, 8)),
    # --- грибная (mushroom) ---
    "huge_brown":        ("floor", (3, 12)),
    "huge_red":          ("floor", (3, 12)),
    "mushroom_patch":    ("floor", (24, 96)),
    "mushroom_fungus":   ("floor", (1, 4)),
    "mycelium_veins":    ("wide", (2, 10)),
    # --- корневая (roots) ---
    "root_system":       ("wide", (2, 8)),
    "pale_moss_floor":   ("floor", (32, 96)),
    "pale_moss_ceiling": ("ceil", (16, 64)),
    "cave_vines_classic": ("wide", (8, 32)),
    "root_dirt_pile":    ("floor", (2, 12)),
    # --- магмовая (magma) ---
    "basalt_columns":    ("layer", (2, 8)),
    "glowstone_blob":    ("wide", (8, 24)),
    "magma_veins":       ("wide", (1, 6)),
    "blackstone_veins":  ("wide", (2, 12)),
    "basalt_pillar":     ("layer", (2, 8)),
    # --- замёрзшая (frozen) ---
    "blue_ice_blob":     ("floor", (2, 10)),
    "snow_piles":        ("floor", (8, 32)),
    "packed_ice_veins":  ("wide", (2, 12)),
    "powder_snow_pockets": ("wide", (1, 8)),
}

# type configured-фичи каждого рецепта (для самотеста попарных
# пересечений видов между архетипами — см. таблицу в generate_dimension)
_CAVE_RECIPE_TYPE = {
    "cave_vines": "minecraft:block_column",
    "moss_floor": "minecraft:vegetation_patch",
    "moss_ceiling": "minecraft:vegetation_patch",
    "spore_blossom": "minecraft:simple_block",
    "dripleaf": "minecraft:simple_random_selector",
    "mossy_boulder": "minecraft:block_blob",
    "dripstone_cluster": "minecraft:speleothem_cluster",
    "pointed_dripstone": "minecraft:simple_random_selector",
    "large_dripstone": "minecraft:large_dripstone",
    "calcite_veins": "minecraft:netherrack_replace_blobs",
    "sculk_vein": "minecraft:multiface_growth",
    "sculk_patch": "minecraft:sculk_patch",
    "glow_lichen_rare": "minecraft:multiface_growth",
    "deepslate_veins": "minecraft:netherrack_replace_blobs",
    "amethyst_geode": "minecraft:geode",
    "amethyst_cluster": "minecraft:block_column",
    "amethyst_veins": "minecraft:netherrack_replace_blobs",
    "crystal_spikes": "minecraft:spike",
    "huge_brown": "minecraft:huge_brown_mushroom",
    "huge_red": "minecraft:huge_red_mushroom",
    "mushroom_patch": "minecraft:simple_block",
    "mushroom_fungus": "minecraft:huge_fungus",
    "mycelium_veins": "minecraft:netherrack_replace_blobs",
    "root_system": "minecraft:root_system",
    "pale_moss_floor": "minecraft:vegetation_patch",
    "pale_moss_ceiling": "minecraft:vegetation_patch",
    "cave_vines_classic": "minecraft:vines",
    "root_dirt_pile": "minecraft:block_pile",
    "basalt_columns": "minecraft:basalt_columns",
    "glowstone_blob": "minecraft:glowstone_blob",
    "magma_veins": "minecraft:netherrack_replace_blobs",
    "blackstone_veins": "minecraft:netherrack_replace_blobs",
    "basalt_pillar": "minecraft:basalt_pillar",
    "blue_ice_blob": "minecraft:blue_ice",
    "snow_piles": "minecraft:block_pile",
    "packed_ice_veins": "minecraft:netherrack_replace_blobs",
    "powder_snow_pockets": "minecraft:netherrack_replace_blobs",
}


def _cave_recipe_placement(factory, style, count, rarity=None):
    """Placement сигнатурной фичи архетипа — ванильные конвейеры
    пещерных фич (см. placed_feature/cave_vines.json, lush_caves_
    vegetation.json, dripstone_cluster.json). height_range — ВСЯ высота
    мира относительными якорями (выше/ниже — пусто, ваниль использует
    above_bottom(0)..absolute(256) — у нас миры до 2032, поэтому доли).
    Никогда heightmap (ставит на ПОВЕРХНОСТЬ мира) и никогда ничего
    после count_on_every_layer."""
    rng = factory.rng
    if style == "layer":
        return [{"type": "minecraft:count_on_every_layer", "count": count}]
    pipeline = []
    if style == "rare":
        pipeline.append({"type": "minecraft:rarity_filter",
                         "chance": rarity or rng.choice([8, 12, 24])})
    pipeline.append({"type": "minecraft:count", "count": count})
    pipeline.append({"type": "minecraft:in_square"})
    pipeline.append({"type": "minecraft:height_range",
                     "height": factory._frac_height_provider(0.0, 1.0)})
    if style in ("floor", "ceil", "berries"):
        # environment_scan — ванильный механизм «найди пол/потолок пещеры»
        target = {"type": "minecraft:solid"}
        if style == "berries":
            target = {"type": "minecraft:has_sturdy_face",
                      "direction": "down"}
        pipeline.append({
            "type": "minecraft:environment_scan",
            "direction_of_search": "down" if style == "floor" else "up",
            "max_steps": 12,
            "allowed_search_condition": {
                "type": "minecraft:matching_block_tag",
                "tag": "minecraft:air"},
            "target_condition": target})
        pipeline.append({"type": "minecraft:random_offset",
                         "xz_spread": 0,
                         "y_spread": 1 if style == "floor" else -1})
    pipeline.append({"type": "minecraft:biome"})
    return pipeline


def _cave_recipe(factory, rname, ctx):
    """configured-фича рецепта архетипа. ctx — контекст измерения:
    ground_tag (тег «земли» палитры), terrain (id default_block — цель
    прожилок), floor/sub (блоки пола архетипа — в предикатах replaceable
    и can_be_placed_on: рельеф случайный, ванильные теги stone-семейства
    его не покрывают). Возвращает (configured, placement)."""
    rng = factory.rng
    style, (clo, chi) = _CAVE_RECIPE_SPEC[rname]
    count = rng.randint(clo, chi)

    def _sp(blk):
        return {"type": "minecraft:simple_state_provider",
                "state": block_state(blk)}

    def _wsp(entries):
        # entries — [(имя_блока, свойства|None, вес), ...]
        return {"type": "minecraft:weighted_state_provider",
                "entries": [{"data": block_state((b, p)), "weight": w}
                            for b, p, w in entries]}

    def _replaceable():
        # ванильные теги (moss/dripstone_replaceable) покрывают только
        # stone-семейство — наш рельеф случайный; поэтому ИЛИ тег «земли»
        # измерения (вся палитра рельефа), ИЛИ блоки пола архетипа
        preds = [{"type": "minecraft:matching_block_tag",
                  "tag": factory._ground_tag()}]
        if ctx["floor"]:
            preds.append({"type": "minecraft:matching_blocks",
                          "blocks": sorted({b[0] for b in ctx["floor"]})})
        return {"type": "minecraft:any_of", "predicates": preds}

    def _blobs(state_blk, target_blk=None):
        # netherrack_replace_blobs: state — блок прожилки, target — порода
        rmin = rng.randint(1, 4)
        return {"type": "minecraft:netherrack_replace_blobs", "config": {
            "radius": {"type": "minecraft:uniform", "min_inclusive": rmin,
                       "max_inclusive": rng.randint(rmin, 9)},
            "state": block_state((state_blk, None)),
            "target": block_state((target_blk or ctx["terrain"], None))}}

    if rname == "cave_vines":
        # ТОЧНАЯ копия ванильного cave_vine.json (block_column вниз,
        # cave_vines_plant с ягодами 1:4 + кончик age 23-25)
        cfg = {"type": "minecraft:block_column", "config": {
            "allowed_placement": {"type": "minecraft:matching_block_tag",
                                   "tag": "minecraft:air"},
            "direction": "down",
            "layers": [
                {"height": {"type": "minecraft:weighted_list",
                            "distribution": [
                                {"data": {"type": "minecraft:uniform",
                                          "min_inclusive": 0,
                                          "max_inclusive": 19},
                                 "weight": 2},
                                {"data": {"type": "minecraft:uniform",
                                          "min_inclusive": 0,
                                          "max_inclusive": 2},
                                 "weight": 3},
                                {"data": {"type": "minecraft:uniform",
                                          "min_inclusive": 0,
                                          "max_inclusive": 6},
                                 "weight": 10}]},
                 "provider": _wsp([
                     ("minecraft:cave_vines_plant",
                      {"berries": "false"}, 4),
                     ("minecraft:cave_vines_plant",
                      {"berries": "true"}, 1)])},
                {"height": 1,
                 "provider": {
                     "type": "minecraft:randomized_int_state_provider",
                     "property": "age",
                     "source": _wsp([
                         ("minecraft:cave_vines",
                          {"age": "0", "berries": "false"}, 4),
                         ("minecraft:cave_vines",
                          {"age": "0", "berries": "true"}, 1)]),
                     "values": {"type": "minecraft:uniform",
                                "min_inclusive": 23,
                                "max_inclusive": 25}}},
            ],
            "prioritize_tip": True}}
    elif rname == "hanging_roots":  # запасной (не в списке архетипов)
        cfg = {"type": "minecraft:block_column", "config": {
            "allowed_placement": {"type": "minecraft:matching_block_tag",
                                   "tag": "minecraft:air"},
            "direction": "down",
            "layers": [{
                "height": {"type": "minecraft:weighted_list",
                            "distribution": [
                                {"data": {"type": "minecraft:uniform",
                                          "min_inclusive": 0,
                                          "max_inclusive": 3},
                                 "weight": 5},
                                {"data": {"type": "minecraft:uniform",
                                          "min_inclusive": 1,
                                          "max_inclusive": 7},
                                 "weight": 1}]},
                "provider": _sp(("minecraft:hanging_roots",
                                 {"waterlogged": "false"}))}],
            "prioritize_tip": True}}
    elif rname in ("moss_floor", "pale_moss_floor"):
        pale = rname.startswith("pale")
        ground = ("minecraft:pale_moss_block" if pale
                  else "minecraft:moss_block")
        if pale:
            veg = _wsp([("minecraft:pale_moss_carpet", None, 35),
                        ("minecraft:short_grass", None, 45),
                        ("minecraft:tall_grass",
                         {"half": "lower"}, 10),
                        ("minecraft:pale_hanging_roots", None, 10)])
        else:
            # копия ванильного moss_vegetation.json
            veg = _wsp([("minecraft:flowering_azalea", None, 4),
                        ("minecraft:azalea", None, 7),
                        ("minecraft:moss_carpet", None, 25),
                        ("minecraft:short_grass", None, 50),
                        ("minecraft:tall_grass",
                         {"half": "lower"}, 10)])
        rmin = rng.randint(2, 4)
        cfg = {"type": "minecraft:vegetation_patch", "config": {
            "replaceable": _replaceable(),
            "ground_state": _sp((ground, None)),
            "vegetation_feature": {
                "feature": {"type": "minecraft:simple_block",
                            "config": {"to_place": veg}},
                "placement": []},
            "surface": "floor",
            "depth": 1,
            "extra_bottom_block_chance": 0.0,
            "vertical_range": 5,
            "vegetation_chance": rnd_f(rng, 0.3, 0.8),
            "xz_radius": {"type": "minecraft:uniform",
                          "min_inclusive": rmin,
                          "max_inclusive": rng.randint(rmin + 1, 7)},
            "extra_edge_column_chance": 0.3}}
    elif rname in ("moss_ceiling", "pale_moss_ceiling"):
        ground = ("minecraft:pale_moss_block"
                  if rname.startswith("pale") else "minecraft:moss_block")
        rmin = rng.randint(2, 4)
        cfg = {"type": "minecraft:vegetation_patch", "config": {
            "replaceable": _replaceable(),
            "ground_state": _sp((ground, None)),
            "vegetation_feature": {
                "feature": {"type": "minecraft:simple_block",
                            "config": {"to_place": _sp(
                                ("minecraft:spore_blossom", None))}},
                "placement": []},
            "surface": "ceiling",
            "depth": 1,
            "extra_bottom_block_chance": 0.0,
            "vertical_range": 5,
            "vegetation_chance": rnd_f(rng, 0.2, 0.5),
            "xz_radius": {"type": "minecraft:uniform",
                          "min_inclusive": rmin,
                          "max_inclusive": rng.randint(rmin + 1, 6)},
            "extra_edge_column_chance": 0.3}}
    elif rname == "spore_blossom":
        cfg = {"type": "minecraft:simple_block", "config": {
            "to_place": _sp(("minecraft:spore_blossom", None))}}
    elif rname == "dripleaf":
        # копия ванильного dripleaf.json: малая листва (4 поворота) +
        # большая (стебель + шляпка, 4 поворота)
        def _small():
            return {"feature": {
                "type": "minecraft:simple_block",
                "config": {"to_place": _wsp([
                    ("minecraft:small_dripleaf",
                     {"facing": d, "half": "lower",
                      "waterlogged": "false"}, 1)
                    for d in ("east", "west", "north", "south")])}},
                "placement": []}

        def _big(d):
            return {"feature": {
                "type": "minecraft:block_column",
                "config": {
                    "allowed_placement": {
                        "type": "minecraft:any_of", "predicates": [
                            {"type": "minecraft:matching_block_tag",
                             "tag": "minecraft:air"},
                            {"type": "minecraft:matching_blocks",
                             "blocks": "minecraft:water"}]},
                    "direction": "up",
                    "layers": [
                        {"height": {"type": "minecraft:weighted_list",
                                    "distribution": [
                                        {"data": {"type": "minecraft:uniform",
                                                  "min_inclusive": 0,
                                                  "max_inclusive": 4},
                                         "weight": 2},
                                        {"data": 0, "weight": 1}]},
                         "provider": _sp(("minecraft:big_dripleaf_stem",
                                           {"facing": d,
                                            "waterlogged": "false"}))},
                        {"height": 1,
                         "provider": _sp(("minecraft:big_dripleaf",
                                           {"facing": d, "tilt": "none",
                                            "waterlogged": "false"}))}],
                    "prioritize_tip": True}},
                "placement": []}

        cfg = {"type": "minecraft:simple_random_selector", "config": {
            "features": [_small()] + [_big(d) for d in
                                       ("east", "west", "south", "north")]}}
    elif rname == "mossy_boulder":
        cfg = {"type": "minecraft:block_blob", "config": {
            "can_place_on": _replaceable(),
            "state": block_state(("minecraft:mossy_cobblestone", None))}}
    elif rname == "dripstone_cluster":
        # ванильный dripstone_cluster.json с джиттером параметров
        hmin = rng.randint(2, 4)
        rmin = rng.randint(2, 4)
        tmin = rng.randint(1, 3)
        cfg = {"type": "minecraft:speleothem_cluster", "config": {
            "base_block": block_state(("minecraft:dripstone_block", None)),
            "pointed_block": {"Name": "minecraft:pointed_dripstone",
                              "Properties": {"thickness": "tip",
                                             "vertical_direction": "up",
                                             "waterlogged": "false"}},
            "replaceable_blocks": _replaceable(),
            "floor_to_ceiling_search_range": rng.randint(8, 24),
            "height": {"type": "minecraft:uniform", "min_inclusive": hmin,
                       "max_inclusive": rng.randint(hmin + 1, 8)},
            "radius": {"type": "minecraft:uniform", "min_inclusive": rmin,
                       "max_inclusive": rng.randint(rmin + 1, 8)},
            "max_stalagmite_stalactite_height_diff": rng.randint(0, 2),
            "height_deviation": rng.randint(1, 5),
            "speleothem_block_layer_thickness": {
                "type": "minecraft:uniform", "min_inclusive": tmin,
                "max_inclusive": rng.randint(tmin + 1, 5)},
            "density": {"type": "minecraft:uniform",
                        "min_inclusive": 0.3, "max_exclusive": 0.7},
            "wetness": {"type": "minecraft:clamped_normal",
                        "mean": 0.1, "deviation": 0.3,
                        "min": 0.1, "max": 0.9},
            "chance_of_speleothem_at_max_distance_from_center": 0.1,
            "max_distance_from_edge_affecting_chance_of_speleothem": 3,
            "max_distance_from_center_affecting_height_bias": 8}}
    elif rname == "pointed_dripstone":
        # копия ванильного pointed_dripstone.json: два speleothem —
        # «вверх» (скан ВНИЗ до пола) и «вниз» (скан ВВЕРХ до потолка),
        # INLINE-placement внутри configured-фичи
        def _sph(direction):
            return {
                "feature": {
                    "type": "minecraft:speleothem",
                    "config": {
                        "base_block": block_state(
                            ("minecraft:dripstone_block", None)),
                        "pointed_block": {
                            "Name": "minecraft:pointed_dripstone",
                            "Properties": {
                                "thickness": "tip",
                                "vertical_direction": "up",
                                "waterlogged": "false"}},
                        "replaceable_blocks": _replaceable()}},
                "placement": [
                    {"type": "minecraft:environment_scan",
                     "direction_of_search": "down" if direction == "up"
                     else "up",
                     "max_steps": 12,
                     "allowed_search_condition": {
                         "type": "minecraft:any_of", "predicates": [
                             {"type": "minecraft:matching_block_tag",
                              "tag": "minecraft:air"},
                             {"type": "minecraft:matching_blocks",
                              "blocks": "minecraft:water"}]},
                     "target_condition": {
                         "type": "minecraft:solid"}},
                    {"type": "minecraft:random_offset", "xz_spread": 0,
                     "y_spread": 1 if direction == "up" else -1}]}

        cfg = {"type": "minecraft:simple_random_selector", "config": {
            "features": [_sph("up"), _sph("down")]}}
    elif rname == "large_dripstone":
        cfg = factory._large_dripstone()
    elif rname == "calcite_veins":
        cfg = _blobs("minecraft:calcite")
    elif rname in ("sculk_vein", "glow_lichen_rare"):
        # multiface: вены скалка на стенах (ванильный sculk_vein)
        bases = sorted({ctx["terrain"],
                        "minecraft:stone", "minecraft:deepslate"} |
                       {b[0] for b in ctx["floor"]})
        cfg = {"type": "minecraft:multiface_growth", "config": {
            "block": ("minecraft:sculk_vein"
                      if rname == "sculk_vein" else "minecraft:glow_lichen"),
            "can_be_placed_on": bases,
            "search_range": rng.randint(8, 24),
            "can_place_on_floor": True,
            "can_place_on_ceiling": True,
            "can_place_on_wall": True,
            "chance_of_spreading": 0.5}}
    elif rname == "sculk_patch":
        # sculk_patch_deep_dark.json; extra_rare_growths 0-2 — сенсоры
        # это block entity: не больше пары на пятно (не массовая заливка)
        cfg = {"type": "minecraft:sculk_patch", "config": {
            "charge_count": rng.randint(8, 16),
            "amount_per_charge": rng.randint(24, 48),
            "spread_attempts": rng.randint(48, 64),
            "growth_rounds": 0,
            "spread_rounds": 1,
            "extra_rare_growths": {"type": "minecraft:uniform",
                                   "min_inclusive": 0,
                                   "max_inclusive": 2},
            "catalyst_chance": 0.5}}
    elif rname == "deepslate_veins":
        cfg = _blobs("minecraft:deepslate")
    elif rname == "amethyst_geode":
        # ванильный amethyst_geode.json (все слои аметистовые); рамка
        # итерации ±14 — граничный peek геода не читает соседний+1 чанк
        cfg = {"type": "minecraft:geode", "config": {
            "blocks": {
                "filling_provider": _sp(("minecraft:air", None)),
                "inner_layer_provider": _sp(("minecraft:amethyst_block",
                                              None)),
                "alternate_inner_layer_provider": _sp(
                    ("minecraft:budding_amethyst", None)),
                "middle_layer_provider": _sp(("minecraft:calcite", None)),
                "outer_layer_provider": _sp(("minecraft:smooth_basalt",
                                              None)),
                "inner_placements": [
                    {"Name": b, "Properties": {"facing": "up",
                                                "waterlogged": "false"}}
                    for b in ("minecraft:small_amethyst_bud",
                              "minecraft:medium_amethyst_bud",
                              "minecraft:large_amethyst_bud",
                              "minecraft:amethyst_cluster")],
                "cannot_replace": "#minecraft:features_cannot_replace",
                "invalid_blocks": "#minecraft:geode_invalid_blocks"},
            "layers": {},
            "crack": {"generate_crack_chance": 0.95},
            "use_alternate_layer0_chance": 0.083,
            "outer_wall_distance": {"type": "minecraft:uniform",
                                     "min_inclusive": 4,
                                     "max_inclusive": rng.choice([5, 6])},
            "invalid_blocks_threshold": 1,
            "min_gen_offset": -14,
            "max_gen_offset": 14}}
    elif rname == "amethyst_cluster":
        # кластеры аметиста на полах (height-1 колонна = «куст» кристаллов)
        cfg = {"type": "minecraft:block_column", "config": {
            "allowed_placement": {"type": "minecraft:matching_block_tag",
                                   "tag": "minecraft:air"},
            "direction": "up",
            "layers": [{
                "height": 1,
                "provider": _wsp([
                    ("minecraft:amethyst_cluster",
                     {"facing": "up", "waterlogged": "false"}, 50),
                    ("minecraft:large_amethyst_bud",
                     {"facing": "up", "waterlogged": "false"}, 20),
                    ("minecraft:medium_amethyst_bud",
                     {"facing": "up", "waterlogged": "false"}, 20),
                    ("minecraft:small_amethyst_bud",
                     {"facing": "up", "waterlogged": "false"}, 10)])}],
            "prioritize_tip": True}}
    elif rname == "amethyst_veins":
        cfg = _blobs("minecraft:amethyst_block")
    elif rname == "crystal_spikes":
        cfg = {"type": "minecraft:spike", "config": {
            "state": block_state(("minecraft:amethyst_block", None)),
            "can_place_on": _replaceable(),
            "can_replace": {"type": "minecraft:matching_block_tag",
                            "tag": "minecraft:air"}}}
    elif rname == "huge_brown":
        cfg = {"type": "minecraft:huge_brown_mushroom", "config": {
            "cap_provider": _sp(("minecraft:brown_mushroom_block",
                                  {"down": "false", "east": "true",
                                   "north": "true", "south": "true",
                                   "up": "true", "west": "true"})),
            "stem_provider": _sp(("minecraft:mushroom_stem",
                                   {"down": "false", "east": "true",
                                    "north": "true", "south": "true",
                                    "up": "false", "west": "true"})),
            "can_place_on": _replaceable(),
            "foliage_radius": 3}}
    elif rname == "huge_red":
        cfg = {"type": "minecraft:huge_red_mushroom", "config": {
            "cap_provider": _sp(("minecraft:red_mushroom_block",
                                  {"down": "false", "east": "true",
                                   "north": "true", "south": "true",
                                   "up": "true", "west": "true"})),
            "stem_provider": _sp(("minecraft:mushroom_stem",
                                   {"down": "false", "east": "true",
                                    "north": "true", "south": "true",
                                    "up": "false", "west": "true"})),
            "can_place_on": _replaceable()}}
    elif rname == "mushroom_patch":
        cfg = {"type": "minecraft:simple_block", "config": {
            "to_place": _wsp([("minecraft:brown_mushroom", None, 1),
                              ("minecraft:red_mushroom", None, 1)])}}
    elif rname == "mushroom_fungus":
        cfg = factory._huge_fungus()
    elif rname == "mycelium_veins":
        cfg = _blobs("minecraft:mycelium")
    elif rname == "root_system":
        # rooted_azalea_tree.json: корни + свисающие корни + дерево
        # (ванильные azalea_tree/pale_oak — деревья не наши случайные)
        tree = rng.choice(["minecraft:azalea_tree", "minecraft:pale_oak"])
        cfg = {"type": "minecraft:root_system", "config": {
            "feature": {"feature": tree, "placement": []},
            "required_vertical_space_for_tree": rng.randint(3, 8),
            "level_test_distance": 0,
            "max_level_deviation": 0,
            "root_radius": rng.randint(2, 4),
            "root_replaceable": "#minecraft:azalea_root_replaceable",
            "root_state_provider": _sp(("minecraft:rooted_dirt", None)),
            "root_placement_attempts": rng.randint(12, 24),
            "root_column_max_height": rng.randint(20, 100),
            "hanging_root_radius": rng.randint(2, 4),
            "hanging_roots_vertical_span": rng.randint(2, 4),
            "hanging_root_state_provider": _sp(
                ("minecraft:hanging_roots", {"waterlogged": "false"})),
            "hanging_root_placement_attempts": rng.randint(12, 24),
            "allowed_vertical_water_for_tree": 2,
            "allowed_tree_position": {
                "type": "minecraft:all_of", "predicates": [
                    {"type": "minecraft:any_of", "predicates": [
                        {"type": "minecraft:matching_block_tag",
                         "tag": "minecraft:air"},
                        {"type": "minecraft:matching_block_tag",
                         "tag": "minecraft:replaceable_by_trees"}]},
                    {"type": "minecraft:matching_block_tag",
                     "offset": [0, -1, 0],
                     "tag": "minecraft:azalea_grows_on"}]}}}
    elif rname == "cave_vines_classic":
        cfg = factory._vines()
    elif rname == "root_dirt_pile":
        cfg = {"type": "minecraft:block_pile", "config": {
            "state_provider": {
                "type": "minecraft:rotated_block_provider",
                "state": block_state(("minecraft:rooted_dirt", None))}}}
    elif rname == "basalt_columns":
        cfg = {"type": "minecraft:basalt_columns", "config": {
            "height": {"type": "minecraft:uniform",
                       "min_inclusive": rng.randint(1, 5),
                       "max_inclusive": rng.randint(6, 10)},
            "reach": {"type": "minecraft:uniform",
                      "min_inclusive": rng.randint(0, 2),
                      "max_inclusive": rng.randint(2, 3)}}}
    elif rname == "glowstone_blob":
        cfg = factory._glowstone_blob()
    elif rname == "magma_veins":
        cfg = _blobs("minecraft:magma_block")
    elif rname == "blackstone_veins":
        cfg = _blobs("minecraft:blackstone")
    elif rname == "basalt_pillar":
        cfg = factory._basalt_pillar()
    elif rname == "blue_ice_blob":
        cfg = factory._blue_ice()
    elif rname == "snow_piles":
        cfg = {"type": "minecraft:block_pile", "config": {
            "state_provider": {
                "type": "minecraft:rotated_block_provider",
                "state": block_state(("minecraft:snow_block", None))}}}
    elif rname == "packed_ice_veins":
        cfg = _blobs("minecraft:packed_ice")
    elif rname == "powder_snow_pockets":
        cfg = _blobs("minecraft:powder_snow")
    else:
        raise ValueError("неизвестный рецепт архетипа: %s" % rname)
    return cfg, _cave_recipe_placement(factory, style, count)


def rand_cave_features(rng, ns, name, min_y, max_y, recipes, terrain=None,
                       floor_blocks=(), no_gravity=False):
    """Сигнатурные фичи ПОДЗЕМНОГО БИОМА-АРХЕТИПА (generate_dimension.
    CAVE_ARCHETYPES[...]["recipes"]). recipes — [(имя, вес), ...]: 4-6
    рецептов выбираются взвешенной выборкой БЕЗ повторов — вес решает,
    что попадёт почти всегда (cave_vines у пышной), а что изредка.
    Все блоки фиксированы рецептом (идентичность!), случайны только
    плотности и мелкие параметры. terrain — id блока рельефа
    (default_block измерения): цель прожилок netherrack_replace_blobs.
    floor_blocks — блоки пола архетипа (в any_of-предикатах replaceable:
    рельеф случайный, ванильные теги stone-семейства его не покрывают).

    Возвращает (configured, placed, tags) — как rand_features; id вида
    <ns>:<name>_<рецепт>N, по ОДНОМУ placed на configured (у сигнатурных
    фич размножать размещение незачем — плотность уже ванильная)."""
    factory = _FeatureFactory(rng, ns, name, min_y, max_y, cave=True,
                              no_gravity=no_gravity)
    ctx = {"terrain": terrain or "minecraft:stone",
           "floor": [b for b in floor_blocks if isinstance(b, tuple)]}
    pool = list(recipes)
    k = min(len(pool), rng.randint(4, 6))
    k = max(3, k)
    chosen = []
    while pool and len(chosen) < k:
        names = [r for r, _ in pool]
        weights = [w for _, w in pool]
        pick = rng.choices(names, weights=weights)[0]
        chosen.append(pick)
        pool = [r for r in pool if r[0] != pick]
    configured, placed = {}, {}
    for rname in chosen:
        cid = factory._uid(rname)
        cfg, placement = _cave_recipe(factory, rname, ctx)
        configured[cid] = cfg
        placed["%s_p1" % cid] = {"feature": cid, "placement": placement}
    tags = {}
    if factory.ground_needed:
        tags["%s:%s_ground" % (ns, name)] = {
            "replace": False, "values": _palette_ids()}
    return configured, placed, tags


def _collect_state_names(node, out):
    """Рекурсивно собрать все имена blockstate'ов (поле "Name") из JSON
    фичи — для самотестов VOID-миров: blockstate-позиции — это
    РАЗМЕЩЕНИЕ блоков (сыпучие там запрещены), а предикаты
    matching_blocks/block_match/matching_block_tag используют другие
    ключи ("blocks"/"block"/"tag") и в выборку не попадают.
    Используется и самотестом generate_dimension (через import)."""
    if isinstance(node, dict):
        nm = node.get("Name")
        if isinstance(nm, str):
            out.add(nm)
        for v in node.values():
            _collect_state_names(v, out)
    elif isinstance(node, list):
        for v in node:
            _collect_state_names(v, out)


# ---------------------------------------------------------------------------
# Самотест (python -X utf8 gen_features.py)
# ---------------------------------------------------------------------------

def _resolve_anchor_y(anchor, min_y, max_y):
    """Якорь height_range → абсолютный Y (max_y — включительный верх,
    как везде в этом модуле)."""
    if "absolute" in anchor:
        return anchor["absolute"]
    if "above_bottom" in anchor:
        return min_y + anchor["above_bottom"]
    return max_y - anchor["below_top"]


def _kind_of(fid, name):
    """Вид фичи из её id: <ns>:<name>_<kind><N> → kind."""
    rest = fid.split(":", 1)[1]
    assert rest.startswith(name + "_"), fid
    return re.sub(r"\d+$", "", rest[len(name) + 1:])


def _self_test():
    """Самотест без записи файлов:
    - rand_ores: 5-9 видов, у каждого 4 placed-варианта богатства со
      строго возрастающим count; height_range всех вариантов —
      относительные якоря, полоса внутри [min_y, max_y] и непустая при
      ЛЮБОЙ геометрии мира;
    - cave-режим rand_features: только пещерные виды (CAVE_FEATURE_KINDS),
      placement БЕЗ heightmap (heightmap ставит фичу на поверхность
      мира, а не на пол пещеры), после count_on_every_layer — ни
      in_square, ни heightmap; «напольной» растительности в
      height_range-пути — фильтр твёрдого блока снизу;
    - rand_stone_blobs: id <name>_stoneN / <name>_blobN, size <= 64,
      count по тирам (частые 3-6, обычные 2-4, редкие 1-2 + rarity
      1/4-1/16, жила 8-24), высоты — относительные якоря внутри мира;
    - no_gravity (VOID-режим): ни одного сыпучего блока в blockstate-
      позициях фич (диски/слои/жеоды/деревья/руды...) — падающий блок
      над пустотой обращается в entity FALLING_BLOCK."""
    import random
    falling = _gd().FALLING_BLOCK_IDS
    cave_kinds = {k for k, _ in CAVE_FEATURE_KINDS}
    for seed in (1, 2, 3, 7, 42, 777, 31337):
        rng = random.Random(seed)
        for min_y, max_y in ((-2032, -1905), (-64, 63), (0, 127),
                             (0, 511), (-512, 1519)):
            nm = "st%d" % seed
            cfg, placed, tags, variants = rand_ores(
                rng, "rndim", nm, min_y, max_y)
            assert 5 <= len(cfg) <= 9, "видов руд %d — должно быть 5-9" % len(cfg)
            assert all(v["type"] in ("minecraft:ore",
                                     "minecraft:scattered_ore")
                       for v in cfg.values())
            for cid, tiers in variants.items():
                assert sorted(tiers) == ["motherlode", "normal", "poor",
                                         "rich"], tiers
                counts = []
                for tier in ("poor", "normal", "rich", "motherlode"):
                    pid = tiers[tier]
                    pl = placed[pid]
                    assert pl["feature"] == cid
                    cnt = [m["count"] for m in pl["placement"]
                           if m.get("type") == "minecraft:count"]
                    assert len(cnt) == 1 and 1 <= cnt[0] <= 100, cnt
                    counts.append(cnt[0])
                    hp = [m["height"] for m in pl["placement"]
                          if m.get("type") == "minecraft:height_range"]
                    assert len(hp) == 1, "у руды нет height_range"
                    lo = _resolve_anchor_y(hp[0]["min_inclusive"], min_y, max_y)
                    hi = _resolve_anchor_y(hp[0]["max_inclusive"], min_y, max_y)
                    assert min_y <= lo <= hi <= max_y, \
                        "полоса руды вне мира: %s..%s (мир %s..%s)" % (
                            lo, hi, min_y, max_y)
                    # якоря — относительные (масштаб под высоту мира)
                    assert "above_bottom" in hp[0]["min_inclusive"] \
                        and "below_top" in hp[0]["max_inclusive"], hp[0]
                assert counts[0] < counts[1] < counts[2] < counts[3], \
                    "богатство не возрастает: %s" % counts
            for t in tags.values():
                assert t["values"], "пустой тег земли"
            # cave-режим: пещерные виды и placement без поверхности
            ccfg, cplaced, _ctags = rand_features(
                rng, "rndim", nm, min_y, max_y, count=8, cave=True)
            assert len(ccfg) == 8
            for cid, _cjson in ccfg.items():
                assert _kind_of(cid, nm) in cave_kinds, \
                    "непещерный вид %s в cave-режиме" % cid
            for pid, pl in cplaced.items():
                kind = _kind_of(pl["feature"], nm)
                types = [m.get("type") for m in pl["placement"]]
                assert "minecraft:heightmap" not in types, \
                    "heightmap в пещерном placement ставит фичу на поверхность"
                assert ("minecraft:count_on_every_layer" in types
                        or "minecraft:height_range" in types), pid
                if "minecraft:count_on_every_layer" in types:
                    i = types.index("minecraft:count_on_every_layer")
                    tail = types[i + 1:]
                    assert "minecraft:in_square" not in tail \
                        and "minecraft:heightmap" not in tail, pid
                elif kind in _FeatureFactory._CAVE_FLOOR:
                    assert any(t == "minecraft:block_predicate_filter"
                               for t in types), \
                        "%s в пещере без фильтра пола" % pid
            # --- каменные блобы семейства: id/размеры/тиры/высоты ---
            fam = [("minecraft:granite", None), ("minecraft:tuff", None),
                   ("minecraft:calcite", None),
                   ("minecraft:dripstone_block", None)]
            tiers = ["common", "normal", "rare", "rare"]
            vein = ("minecraft:ancient_debris", None)
            bcfg, bplaced, btags = rand_stone_blobs(
                rng, "rndim", nm, min_y, max_y,
                family=list(zip(fam, tiers)), vein=vein)
            assert len(bcfg) == len(fam) + 1 == len(bplaced), \
                "блобов %d, камней %d" % (len(bplaced), len(fam))
            state_tier = {b[0]: t for b, t in zip(fam, tiers)}
            for cid, cjson in bcfg.items():
                assert _kind_of(cid, nm) == "stone", cid
                assert cjson["type"] == "minecraft:ore"
                assert 2 <= cjson["config"]["size"] <= 64, cjson
                st = cjson["config"]["targets"][0]["state"]["Name"]
                assert st in set(state_tier) | {vein[0]}, st
            for pid, pl in bplaced.items():
                assert _kind_of(pl["feature"], nm) == "stone", pid
                assert _kind_of(pid, nm) == "blob", pid
                types = [m.get("type") for m in pl["placement"]]
                assert "minecraft:height_range" in types, pid
                hp = [m["height"] for m in pl["placement"]
                      if m.get("type") == "minecraft:height_range"][0]
                lo = _resolve_anchor_y(hp["min_inclusive"], min_y, max_y)
                hi = _resolve_anchor_y(hp["max_inclusive"], min_y, max_y)
                assert min_y <= lo <= hi <= max_y, \
                    "полоса блоба вне мира: %s..%s" % (lo, hi)
                assert "above_bottom" in hp["min_inclusive"], hp
                rars = [m["chance"] for m in pl["placement"]
                        if m.get("type") == "minecraft:rarity_filter"]
                cnts = [m["count"] for m in pl["placement"]
                        if m.get("type") == "minecraft:count"]
                st = bcfg[pl["feature"]]["config"]["targets"][0]
                st = st["state"]["Name"]
                if st == vein[0]:          # жила: count высокий
                    assert cnts and 8 <= cnts[0] <= 24, (pid, cnts)
                elif state_tier[st] == "rare":
                    assert rars and 4 <= rars[0] <= 16, (pid, rars)
                    assert cnts and 1 <= cnts[0] <= 2, (pid, cnts)
                elif state_tier[st] == "common":
                    assert not rars and cnts and 3 <= cnts[0] <= 6, \
                        (pid, rars, cnts)
                else:                      # normal
                    assert not rars and cnts and 2 <= cnts[0] <= 4, \
                        (pid, rars, cnts)
            assert any(t.endswith("_ground") for t in btags), \
                "нет тега земли для целей блобов"
            # --- no_gravity (VOID): сыпучих нет в blockstate-позициях ---
            cfg, placed, _tg = rand_features(
                rng, "rndim", nm, min_y, max_y, count=30, no_gravity=True)
            names = set()
            for j in list(cfg.values()) + list(placed.values()):
                _collect_state_names(j, names)
            bad = names & falling
            assert not bad, "сыпучие в no_gravity-фичах: %s" % sorted(bad)
            ocfg2, oplaced2, _t2, _v2 = rand_ores(
                rng, "rndim", nm, min_y, max_y, no_gravity=True)
            names2 = set()
            for j in list(ocfg2.values()) + list(oplaced2.values()):
                _collect_state_names(j, names2)
            bad2 = names2 & falling
            assert not bad2, "сыпучие в no_gravity-рудах: %s" % sorted(bad2)
            # --- фичи АРХЕТИПОВ подземных биомов (rand_cave_features) ---
            all_recipes = [(r, 1) for r in sorted(_CAVE_RECIPE_SPEC)]
            acfg, aplaced, _at = rand_cave_features(
                rng, "rndim", nm, min_y, max_y, all_recipes,
                terrain="minecraft:stone",
                floor_blocks=[("minecraft:moss_block", None)],
                no_gravity=((seed % 2) == 0))
            assert 3 <= len(acfg) <= 6, \
                "фичей архетипа %d — должно быть 3-6" % len(acfg)
            for cid, cjson in acfg.items():
                rname = _kind_of(cid, nm)
                assert cjson["type"] == _CAVE_RECIPE_TYPE[rname], \
                    "рецепт %s: тип %s != %s" % (
                        rname, cjson["type"], _CAVE_RECIPE_TYPE[rname])
            for pid, pl in aplaced.items():
                types = [m.get("type") for m in pl["placement"]]
                assert pid == pl["feature"] + "_p1", pid
                assert "minecraft:heightmap" not in types, \
                    "heightmap в placement архетипа: %s" % pid
                if "minecraft:count_on_every_layer" in types:
                    assert types[-1] == "minecraft:count_on_every_layer", pid
                else:
                    assert types[-1] == "minecraft:biome", pid
                    hp = [m["height"] for m in pl["placement"]
                          if m.get("type") == "minecraft:height_range"]
                    assert len(hp) == 1, "нет height_range: %s" % pid
                    lo = _resolve_anchor_y(hp[0]["min_inclusive"],
                                           min_y, max_y)
                    hi = _resolve_anchor_y(hp[0]["max_inclusive"],
                                           min_y, max_y)
                    assert min_y <= lo <= hi <= max_y, \
                        "полоса архетипа вне мира: %s" % pid
                    assert "above_bottom" in hp[0]["min_inclusive"], pid
                cnt = [m["count"] for m in pl["placement"]
                       if m.get("type") == "minecraft:count"]
                if cnt:
                    clo, chi = _CAVE_RECIPE_SPEC[
                        _kind_of(pl["feature"], nm)][1]
                    assert len(cnt) == 1 and clo <= cnt[0] <= chi, \
                        "count %s вне диапазона %s: %s" % (
                            cnt, (clo, chi), pid)
            if (seed % 2) == 0:      # no_gravity — сыпучих нет нигде
                anames = set()
                for j in list(acfg.values()) + list(aplaced.values()):
                    _collect_state_names(j, anames)
                abad = anames & falling
                assert not abad, \
                    "сыпучие в no_gravity-фичах архетипа: %s" % sorted(abad)
        print("  seed %d: OK" % seed)
    # каждый рецепт строится и даёт заявленный тип (в т.ч. не вошедшие
    # в выборку выше — по одному разу на фиксированном rng)
    import random as _random
    _f = _FeatureFactory(_random.Random(99), "rndim", "rectest", -64, 63,
                         cave=True)
    _ctx = {"terrain": "minecraft:stone",
            "floor": [("minecraft:moss_block", None)]}
    for _rname in sorted(_CAVE_RECIPE_SPEC):
        _cfg, _pl = _cave_recipe(_f, _rname, _ctx)
        assert _cfg["type"] == _CAVE_RECIPE_TYPE[_rname], _rname
        assert _pl and _pl[-1]["type"] in ("minecraft:biome",
                                           "minecraft:count_on_every_layer"), \
            _rname
    print("gen_features: самотест OK (руды + пещерный режим + каменные "
          "блобы + no_gravity + фичи архетипов подземки)")


if __name__ == "__main__":
    try:
        import sys
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    _self_test()
