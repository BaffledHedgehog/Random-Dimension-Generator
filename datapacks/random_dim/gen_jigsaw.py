def _fnv1a(s):
    h = 2166136261
    for c in s.encode('utf-8'):
        h = ((h ^ c) * 16777619) & 0xffffffff
    return h

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_jigsaw.py — генератор случайных МНОГОЧАСТНЫХ jigsaw-структур для Minecraft 26.2
(pack_format 107). В отличие от gen_structures (который миксует ВАНИЛЬНЫЕ .nbt в
случайных пулов), этот модуль строит ПОЛНОСТЬЮ свои процедурные данжи: свои
.nbt-кушки с jigsaw-блоками внутри + свои template_pool'ы, связывающие куски в
цепи/деревья/башни.

Весь формат сверен с ванильным jar 26.2 (minecraft-26.2-client.jar):
  * structure JSON (type minecraft:jigsaw) — поля из data/minecraft/worldgen/
    structure/village_plains.json, trial_chambers.json, ancient_city.json:
    biomes, step, spawn_overrides, terrain_adaptation, start_pool,
    start_height (VerticalAnchor / uniform-провайдер), start_jigsaw_name,
    size (intRange 0..20), use_expansion_hack, project_start_to_heightmap,
    max_distance_from_center (int 1..128; при terrain_adaptation != none
    проверка verifyRange: max_distance + 12 <= 128), pool_aliases,
    dimension_padding, liquid_settings.
  * jigsaw-блок в .nbt (сверено с plains_small_house_1.nbt и байткодом
    JigsawBlockEntity): state {"Name":"minecraft:jigsaw","Properties":
    {"orientation":<одна из 12>}}, nbt {id, pool, name, target, final_state,
    joint, selection_priority?, placement_priority?}. Ориентации (enum
    FrontAndTop, по байткоду): north_up/east_up/south_up/west_up +
    up_north/up_east/up_south/up_west + down_north/down_east/down_south/
    down_west.
  * ПРАВИЛО СОЕДИНЕНИЯ (байткод JigsawBlock.canAttach(A, B)):
    front(A) == opposite(front(B))  И  (joint(A)=="rollable" ИЛИ top(A)==top(B))
    И  target(A) == name(B).  Поэтому у ВСЕХ наших jigsaw-блоков joint="rollable"
    (верхняя ось не важна — вертикальные порты работают при любом повороте
    куска) и симметричные ключи name==target.
  * ПОЗИЦИОНИРОВАНИЕ КУСКА (байткод JigsawPlacement$Placer.tryPlacingChildren):
    дочерний кусок B сдвигается так, что его jigsaw-блок попадает ТОЧНО в
    позицию родительского jigsaw-блока + 1 блок по направлению front
    родителя. Оба jigsaw-блока затем заменяются на final_state
    (JigsawReplacementProcessor применяется к ЛЮБОМУ поставленному куску:
    BlockStateParser разбирает строки вида "minecraft:stone" или
    "minecraft:oak_log[axis=y]"; несоединённые jigsaw тоже заменяются).
  * template_pool: elements[{element{element_type
    minecraft:single_pool_element, location, processors, projection}, weight}],
    fallback (формат data/minecraft/worldgen/template_pool/*.json).

АРХИТЕКТУРА ДАНЖА. Для одной структуры случайно выбираются:
  * профиль проёма: ширина W (3|5) и высота H (2..4) — ОДИНАКОВЫ для всех
    горизонтальных разъёмов структуры, поэтому любые куски сходятся встык.
    jigsaw-блок ставится В ПЛОСКОСТИ ПОЛА (y=0 относительно этажа порта) в
    центре проёма; над ним H клеток воздуха шириной W. После соединения
    final_state = блок пола → непрерывный пол через шов.
  * роли кусков: start (1 шт), room / corridor / tower / bridge / stairs /
    gate / courtyard / spire / terrace / pit / viaduct + НОВЫЕ архетипы
    (кратно расширенный набор): rotunda (октагональный зал с куполом и
    колоннадой), arena (овальная чаша с трибунами-уступами), workshop
    (мастерская с верстаками/печами и нишами-полками), treasury
    (сейф-комната с двойными стенами: 1-2 сундука/волта), greenhouse
    (оранжерея со стеклянной крышей и растениями на подставках),
    mausoleum (зал с саркофагом, колоннами и глоустоун-точками),
    chainbridge (подвесной мост: пилоны + «цепи»-параболы), ruins
    (полуразрушенная комната: рваные стены/обломки), labyrinth
    (сегмент лабиринта: DFS-проходы, 2 входа, тупики), observatory
    (башня-обсерватория с круглой площадкой и «телескопом»), kitchen
    (кухня с котлами/очагом/сеном), mine (колодец-шахта с рудами в
    стенах — вертикаль ВНИЗ, как pit) (состав случаен, 1-6 шт на роль,
    cap присутствует всегда), tower_top (1-3), cap (2-6, тупики).
    Вариативность существующих ролей: room — plain/pillared/pit
    (центральная яма с кладом на дне)/gallery (двухуровневый с
    галереей-кольцом); tower — ladder/spiral (винтовая вокруг столба)/
    platforms (ярусные площадки); corridor — straight/sshape
    (S-образный со смещёнными портами)/slope (пологий наклонный).
  * случайная матрица связей: с какого роли какие роли можно дёргать
    (пулы ps_<role>); вертикаль: потолки комнат → башни/шпили (tbase),
    башни/шпили → башни/шпили/вершины (tchain), полы комнат/двориков →
    колодцы/шахты (pbase, ВНИЗ). Форма данжа (лабиринт/дерево комнат/
    башня) emerges из матрицы.
  * палитра: случайные полные кубы из generate_dimension.PALETTE_BLOCKS
    (пол/стены/акцент/каркас), окна-дыры, декор; декоративные НЕ-кубы
    (факелы/лестницы/растения) и точечные block-entity (сундуки/печи/
    волты — как в ванильных деревнях) — только штучно, не в массовой
    заливке.

ЖИВНОСТЬ — РЕДКАЯ (лимиты спавна после инцидента с 8000 мобов):
  * мобы в entities[] куска: максимум 1-2, с малым шансом на кусок; NBT —
    из gen_structures._rand_mob_nbt, БЕЗ NoAI/Invulnerable (мобы живут
    своей жизнью и уязвимы);
  * mob_spawner: шанс <= 10-12% только в комнатах, NBT берётся из
    gen_structures._rand_spawner_nbt КАК ЕСТЬ (спавнер «быстрый»:
    MinSpawnDelay 40-100 / MaxSpawnDelay 120-240 / SpawnCount 3-5 /
    MaxNearbyEntities 6-9 / RequiredPlayerRange 24-32 / SpawnRange 4-6;
    спектр сущностей — мобы 85% + спец-типы 15% (item/tnt/лодки/
    фейерверк/...). Все константы — централизованно в gen_structures,
    своих весов/скоростей здесь НЕТ — не дублировать!).

Контракт (как у gen_structures.rand_structures):

    rand_jigsaw(rng, ns, name, min_y, max_y, biome_ids, loot_alloc=None,
                count=None)
        -> {"structures":      {id: json},   # data/<ns>/worldgen/structure/
            "structure_sets":  {id: json},   # data/<ns>/worldgen/structure_set/
            "template_pools":  {id: json},   # data/<ns>/worldgen/template_pool/<путь>.json
            "processor_lists": {id: json},   # data/<ns>/worldgen/processor_list/<путь>.json
            "biome_tags":      {tag: json},  # data/<ns>/tags/worldgen/biome/<tag>.json
            "nbt_files":       {ключ: bytes} # data/<ns>/structure/<ключ>.nbt (gzip-NBT)
            "loot_slots":      <int>         # сколько слотов лута занял вызов
           }

НИЧЕГО не пишет на диск. Кусок <= 16x24x16; projection везде rigid (мобы и
сундуки в terrain_matching-кусках смещаются по heightmap); все jigsaw-блоки
валидны, все пулы существуют, все ссылки резолвятся (проверяется самотестом).
"""

import json
import random

# NBT-писатель и проверенные генераторы начинки — из gen_structures (не дублируем)
from gen_structures import (
    DATA_VERSION,               # 4903 (26.2)
    STRUCTURE_STEPS,            # шаги генерации структур
    TAG_MATCH_TAGS,             # ванильные блок-теги (protected_blocks)
    TRIAL_POOL_ALIASES,         # ванильные алиасы спавнер-пулов trial_chambers
    LootSlots,                  # общий счётчик слотов лут-таблиц измерения
    _gd,                        # ленивый доступ к константам generate_dimension
    _nbt_bytes,                 # python-дерево -> gzip-NBT (корень .nbt)
    _rand_chest_nbt,            # {LootTable: ...} для сундука/бочки
    _rand_spawner_nbt,          # быстрый mob_spawner: любые сущности
                                # (мобы 85% / спец-типы 15%), скорости —
                                # централизованно в gen_structures
    _rand_mob_nbt,              # NBT «особого» моба
    _rand_structure_set_json,   # random_spread / concentric_rings
    _rand_vault_nbt,            # config волта (лут-слот + ключ)
)

# ---------------------------------------------------------------------------
# Проверенные константы
# ---------------------------------------------------------------------------

# Все 12 ориентаций jigsaw-блока (enum FrontAndTop, байткод 26.2)
JIGSAW_ORIENTATIONS = [
    "north_up", "east_up", "south_up", "west_up",
    "up_north", "up_east", "up_south", "up_west",
    "down_north", "down_east", "down_south", "down_west",
]

# Ориентация горизонтального порта по грани (front перпендикулярен грани, top=up)
_FACE_ORIENT = {"west": "west_up", "east": "east_up",
                "north": "north_up", "south": "south_up"}

# Грани -> противоположная (для коридоров/мостов: порты с двух концов)
_FACES = ("west", "east", "north", "south")
_OPPOSITE_FACE = {"west": "east", "east": "west", "north": "south",
                  "south": "north"}

# Матрица связей: какие роли может дёргать роль с боковыми портами
# (вес -> вероятность попадания куска этой роли в пул). Фильтруется по
# реально выбранным ролям; cap присутствует всегда. Новые архетипы:
# gate (ворота) / courtyard (дворик) / terrace (терраса) ↔ room/corridor,
# viaduct/chainbridge — мостовые; rotunda/arena/workshop/treasury/
# greenhouse/mausoleum/ruins/labyrinth/observatory/kitchen — планировки;
# spire/pit/mine — вертикальные, боковых портов не имеют (см.
# вертикальные пулы в _rand_jigsaw_one)
_SIDE_MATRIX = {
    "start":    (("corridor", 5), ("room", 5), ("bridge", 2),
                 ("stairs", 2), ("gate", 2), ("courtyard", 2), ("cap", 1),
                 ("rotunda", 2), ("arena", 1), ("workshop", 1),
                 ("greenhouse", 1), ("labyrinth", 1), ("observatory", 1)),
    "room":     (("corridor", 5), ("room", 2), ("bridge", 2),
                 ("stairs", 2), ("gate", 2), ("courtyard", 2),
                 ("terrace", 1), ("cap", 3),
                 ("rotunda", 1), ("arena", 1), ("workshop", 1),
                 ("treasury", 1), ("greenhouse", 1), ("mausoleum", 1),
                 ("ruins", 1), ("labyrinth", 1), ("observatory", 1),
                 ("kitchen", 1)),
    "corridor": (("room", 5), ("corridor", 3), ("cap", 3),
                 ("stairs", 1), ("bridge", 1), ("gate", 2),
                 ("courtyard", 2), ("terrace", 1),
                 ("rotunda", 1), ("workshop", 1), ("treasury", 1),
                 ("greenhouse", 1), ("mausoleum", 1), ("ruins", 1),
                 ("labyrinth", 1), ("kitchen", 1)),
    "bridge":   (("room", 5), ("cap", 3), ("bridge", 2),
                 ("corridor", 1), ("stairs", 1), ("viaduct", 2),
                 ("chainbridge", 2), ("observatory", 1)),
    "stairs":   (("room", 5), ("corridor", 3), ("cap", 3), ("bridge", 1),
                 ("terrace", 2), ("courtyard", 1),
                 ("rotunda", 1), ("arena", 1), ("observatory", 1)),
    "gate":     (("corridor", 5), ("room", 4), ("courtyard", 2),
                 ("terrace", 1), ("cap", 2),
                 ("rotunda", 1), ("arena", 1), ("labyrinth", 1)),
    "courtyard": (("room", 5), ("corridor", 4), ("gate", 2),
                  ("bridge", 2), ("terrace", 1), ("cap", 2),
                  ("greenhouse", 1), ("arena", 1), ("rotunda", 1)),
    "terrace":  (("room", 5), ("corridor", 3), ("courtyard", 2),
                 ("stairs", 1), ("cap", 2), ("observatory", 1)),
    "viaduct":  (("room", 5), ("bridge", 3), ("corridor", 2), ("cap", 2),
                 ("chainbridge", 2)),
    # --- новые архетипы: что они дёргают сами ---
    "rotunda":    (("corridor", 5), ("room", 4), ("courtyard", 2),
                   ("mausoleum", 1), ("treasury", 1), ("cap", 2)),
    "arena":      (("corridor", 5), ("room", 4), ("courtyard", 2),
                   ("cap", 2)),
    "workshop":   (("corridor", 5), ("room", 4), ("kitchen", 2),
                   ("treasury", 1), ("cap", 2)),
    "treasury":   (("corridor", 5), ("room", 4), ("cap", 3)),
    "greenhouse": (("corridor", 5), ("room", 4), ("courtyard", 2),
                   ("kitchen", 1), ("cap", 2)),
    "mausoleum":  (("corridor", 5), ("room", 4), ("labyrinth", 2),
                   ("treasury", 1), ("cap", 2)),
    "chainbridge": (("room", 5), ("cap", 3), ("bridge", 2),
                    ("viaduct", 2), ("corridor", 1), ("observatory", 1)),
    "ruins":      (("corridor", 5), ("room", 4), ("courtyard", 2),
                   ("labyrinth", 1), ("cap", 2)),
    "labyrinth":  (("room", 5), ("corridor", 3), ("cap", 3),
                   ("treasury", 1), ("workshop", 1)),
    "observatory": (("corridor", 4), ("room", 4), ("bridge", 2),
                    ("cap", 2)),
    "kitchen":    (("corridor", 5), ("room", 4), ("workshop", 2),
                   ("greenhouse", 1), ("cap", 2)),
}

# Роли с боковыми портами (им нужен пул ps_<role>) — ключи матрицы
_SIDE_ROLES = tuple(_SIDE_MATRIX)

# Состав ролей на структуру (без start и cap, которые всегда есть).
# spire/pit/mine — вертикальные (tbase/tchain/pbase), не в _SIDE_ROLES
_CORE_ROLES = ["room", "corridor", "tower", "bridge", "stairs",
               "gate", "courtyard", "spire", "terrace", "pit", "viaduct",
               "rotunda", "arena", "workshop", "treasury", "greenhouse",
               "mausoleum", "chainbridge", "ruins", "labyrinth",
               "observatory", "kitchen", "mine"]

# Декоративные некубические блоки (properties сверены с blockstates в jar)
_TORCH = {"Name": "minecraft:torch"}
_LANTERN = {"Name": "minecraft:lantern",
            "Properties": {"hanging": "false", "waterlogged": "false"}}
_AIR = {"Name": "minecraft:air"}

# ---------------------------------------------------------------------------
# Константы новых архетипов (все id — древние ванильные блоки либо сверены
# с gen_features.PLANT_BLOCKS/ORE_BLOCKS, которые проверялись по jar 26.2;
# всё это ШТУЧНЫЙ декор, не массовая заливка: block-entity блоки (печи —
# как в ванильных деревнях, по 1-2 на кусок) точечны и FPS не грузят)
# ---------------------------------------------------------------------------

# Полные светокубы БЕЗ block entity (для цепей моста, точек мавзолея и т.д.)
_LIGHT_BLOCKS = (
    {"Name": "minecraft:glowstone"},
    {"Name": "minecraft:sea_lantern"},
    {"Name": "minecraft:shroomlight"},
)

# Растения оранжереи — подмножество проверенного gen_features.PLANT_BLOCKS
# (jar 26.2): только без свойств либо с безопасными дефолтами
_GREEN_PLANTS = (
    {"Name": "minecraft:poppy"}, {"Name": "minecraft:dandelion"},
    {"Name": "minecraft:blue_orchid"}, {"Name": "minecraft:allium"},
    {"Name": "minecraft:cornflower"}, {"Name": "minecraft:red_tulip"},
    {"Name": "minecraft:oxeye_daisy"}, {"Name": "minecraft:short_grass"},
    {"Name": "minecraft:fern"}, {"Name": "minecraft:dead_bush"},
    {"Name": "minecraft:bush"}, {"Name": "minecraft:firefly_bush"},
    {"Name": "minecraft:azalea"}, {"Name": "minecraft:flowering_azalea"},
    {"Name": "minecraft:red_mushroom"}, {"Name": "minecraft:brown_mushroom"},
    {"Name": "minecraft:crimson_roots"}, {"Name": "minecraft:short_dry_grass"},
    {"Name": "minecraft:closed_eyeblossom"},
)
_MOSS_CARPETS = ({"Name": "minecraft:moss_carpet"},
                 {"Name": "minecraft:pale_moss_carpet"})
_SPORE_BLOSSOM = {"Name": "minecraft:spore_blossom"}
_GLASS = {"Name": "minecraft:glass"}
_BOOKSHELF = {"Name": "minecraft:bookshelf"}
_CANDLE_LIT = {"Name": "minecraft:candle",
               "Properties": {"candles": "1", "lit": "true",
                              "waterlogged": "false"}}

# Ступени для саркофага (древние ванильные, все есть в 26.2)
_STAIRS_POOL = (
    "minecraft:cobblestone_stairs", "minecraft:stone_brick_stairs",
    "minecraft:brick_stairs", "minecraft:sandstone_stairs",
    "minecraft:purpur_stairs", "minecraft:quartz_stairs",
    "minecraft:blackstone_stairs",
    "minecraft:polished_blackstone_brick_stairs",
)

# Столы-верстаки мастерской (полные блоки, БЕЗ block entity)
_WORKSHOP_STATIONS = (
    {"Name": "minecraft:crafting_table"},
    {"Name": "minecraft:smithing_table"},
    {"Name": "minecraft:fletching_table"},
    {"Name": "minecraft:cartography_table"},
    {"Name": "minecraft:loom"},
)

# Руды шахты-колодца (сверены с gen_features.ORE_BLOCKS — jar 26.2)
_MINE_ORES = (
    "minecraft:coal_ore", "minecraft:copper_ore", "minecraft:iron_ore",
    "minecraft:gold_ore", "minecraft:redstone_ore",
    "minecraft:lapis_ore", "minecraft:diamond_ore",
    "minecraft:emerald_ore", "minecraft:deepslate_coal_ore",
    "minecraft:deepslate_copper_ore", "minecraft:deepslate_iron_ore",
    "minecraft:deepslate_gold_ore", "minecraft:deepslate_redstone_ore",
    "minecraft:deepslate_lapis_ore", "minecraft:deepslate_diamond_ore",
    "minecraft:deepslate_emerald_ore", "minecraft:nether_gold_ore",
    "minecraft:nether_quartz_ore", "minecraft:ancient_debris",
)

# Ключи соло-волтов сокровищницы (НЕ trial_key: без парного спавнера
# ключ недобываем — формат пары см. gen_structures._place_vault)
_VAULT_KEY_ITEMS = ("minecraft:emerald", "minecraft:diamond",
                    "minecraft:gold_ingot", "minecraft:iron_ingot",
                    "minecraft:amethyst_shard", "minecraft:echo_shard")

# Ванильные блок-теги для protected_blocks (существование проверено:
# gen_structures.TAG_MATCH_TAGS + features_cannot_replace, который уже
# используется ванилью в processor_list)
_PROTECTED_TAGS = tuple(["#minecraft:features_cannot_replace"]
                        + ["#%s" % t for t in TAG_MATCH_TAGS])


def _stairs_state(rng, facing):
    """Ступень из ванильного пула (саркофаг и др.)."""
    return {"Name": rng.choice(_STAIRS_POOL),
            "Properties": {"facing": facing, "half": "bottom",
                           "shape": "straight", "waterlogged": "false"}}


def _furnace_state(rng, name, facing):
    """Печь/дымарь/взрывная печь (block entity — штучно, как в деревнях)."""
    return {"Name": name,
            "Properties": {"facing": facing, "lit": "false"}}


def _wall_torch(facing):
    return {"Name": "minecraft:wall_torch",
            "Properties": {"facing": facing}}


def _ladder(facing):
    return {"Name": "minecraft:ladder",
            "Properties": {"facing": facing, "waterlogged": "false"}}


def _state_str(state):
    """{"Name","Properties"} -> строка для final_state jigsaw-блока
    (BlockStateParser: 'minecraft:stone' или 'minecraft:oak_log[axis=y]')."""
    s = state["Name"]
    props = state.get("Properties")
    if props:
        s += "[%s]" % ",".join("%s=%s" % kv for kv in sorted(props.items()))
    return s


def _weighted_sample(rng, cands, k):
    """k разных (роль, вес) из cands, выбор с весами (без возвращений)."""
    pool = list(cands)
    out = []
    while pool and len(out) < k:
        weights = [w for _, w in pool]
        pick = rng.choices(pool, weights=weights)[0]
        pool.remove(pick)
        out.append(pick)
    return out


# ---------------------------------------------------------------------------
# Сетка куска + экспорт в gzip-NBT
# ---------------------------------------------------------------------------

class _Grid(object):
    """3D-сетка куска: cells[x][y][z] = (state, nbt|None)."""

    __slots__ = ("sx", "sy", "sz", "cells")

    def __init__(self, sx, sy, sz):
        self.sx, self.sy, self.sz = sx, sy, sz
        self.cells = [[[None] * sz for _ in range(sy)] for _ in range(sx)]

    def set(self, x, y, z, state, nbt=None):
        self.cells[x][y][z] = (state, nbt)

    def get(self, x, y, z):
        return self.cells[x][y][z]

    def fill(self, x0, y0, z0, x1, y1, z1, state):
        for x in range(max(0, x0), min(self.sx, x1 + 1)):
            for y in range(max(0, y0), min(self.sy, y1 + 1)):
                for z in range(max(0, z0), min(self.sz, z1 + 1)):
                    self.cells[x][y][z] = (state, None)

    def in_bounds(self, x, y, z):
        return 0 <= x < self.sx and 0 <= y < self.sy and 0 <= z < self.sz


def _export_piece(g, entities):
    """Сетка -> bytes gzip-NBT (формат ванильных structure/*.nbt,
    DataVersion 4903). Каждая клетка попадает в blocks[] — включая воздух:
    иначе интерьер куска не вырезается из террейна."""
    palette = []
    pal_idx = {}

    def pal(state):
        key = (state.get("Name"),
               tuple(sorted((state.get("Properties") or {}).items())))
        i = pal_idx.get(key)
        if i is None:
            i = len(palette)
            pal_idx[key] = i
            palette.append(state)
        return i

    blocks = []
    for x in range(g.sx):
        for y in range(g.sy):
            for z in range(g.sz):
                cell = g.cells[x][y][z] or (_AIR, None)
                entry = {"pos": [x, y, z], "state": pal(cell[0])}
                if cell[1] is not None:
                    entry["nbt"] = cell[1]
                blocks.append(entry)
    root = {"size": [g.sx, g.sy, g.sz], "entities": entities,
            "blocks": blocks, "palette": palette,
            "DataVersion": DATA_VERSION}
    return _nbt_bytes(root)


# ---------------------------------------------------------------------------
# Порты (jigsaw-блоки)
# ---------------------------------------------------------------------------

def _jigsaw_nbt(rng, pool, key, final_state, name=None):
    """NBT jigsaw-блока (теги сверены по JigsawBlockEntity): name==target
    (симметричный ключ — canAttach односторонний, симметрия покрывает оба
    направления), joint rollable (top-ось не проверяется)."""
    nbt = {"id": "minecraft:jigsaw", "pool": pool,
           "name": name or key, "target": key,
           "final_state": final_state, "joint": "rollable"}
    if rng.random() < 0.25:
        nbt["selection_priority"] = rng.randint(1, 5)
    if rng.random() < 0.25:
        nbt["placement_priority"] = rng.randint(1, 5)
    return nbt


def _carve_side_port(rng, g, ctx, face, floor_y, along, pool, name=None):
    """Боковой порт: проём WxH в грани face, jigsaw в плоскости пола.
    along — координата ЦЕНТРА проёма вдоль грани. Возвращает (x, y, z)
    jigsaw-блока."""
    W, H = ctx["W"], ctx["H"]
    half = W // 2
    if face in ("west", "east"):
        fx = 0 if face == "west" else g.sx - 1
        for z in range(along - half, along - half + W):
            for y in range(floor_y + 1, floor_y + H + 1):
                g.set(fx, y, z, _AIR)
        jpos = (fx, floor_y, along)
    else:
        fz = 0 if face == "north" else g.sz - 1
        for x in range(along - half, along - half + W):
            for y in range(floor_y + 1, floor_y + H + 1):
                g.set(x, y, fz, _AIR)
        jpos = (along, floor_y, fz)
    g.set(jpos[0], jpos[1], jpos[2],
          {"Name": "minecraft:jigsaw",
           "Properties": {"orientation": _FACE_ORIENT[face]}},
          nbt=_jigsaw_nbt(rng, pool, ctx["port_key"], ctx["floor_str"],
                          name=name))
    return jpos


def _carve_up_port(rng, g, ctx, x, z, pool):
    """Вертикальный порт ВВЕРХ: jigsaw в крыше (y=sy-1), up_north.
    final_state = лестница — вместе с лестничным столбом внутри куска даёт
    непрерывный лаз сквозь шов (опора: блок крыши соседний с дырой)."""
    g.set(x, g.sy - 1, z,
          {"Name": "minecraft:jigsaw",
           "Properties": {"orientation": "up_north"}},
          nbt=_jigsaw_nbt(rng, pool, ctx["vport_key"], ctx["ladder_str"]))


def _carve_down_port(rng, g, ctx, x, z, pool="minecraft:empty"):
    """Вертикальный порт ВНИЗ: jigsaw в полу (y=0), down_north. По умолчанию
    терминальный (minecraft:empty — вход башни снизу); pool=pbase — дёргает
    КОЛОДЦЫ под собой (final_state = лестница: шов проходим вниз, опора —
    блок к западу от порта)."""
    g.set(x, 0, z,
          {"Name": "minecraft:jigsaw",
           "Properties": {"orientation": "down_north"}},
          nbt=_jigsaw_nbt(rng, pool, ctx["vport_key"], ctx["ladder_str"]))


def _ladder_column(g, x, z, facing, y0, y1):
    """Столб лестницы (x, ·, z) — опорная стена должна быть ЗА блоком
    (напр. x-1 при facing=east)."""
    for y in range(y0, y1 + 1):
        g.set(x, y, z, _ladder(facing))


# ---------------------------------------------------------------------------
# Начинка кусков (редкая живность — см. шапку модуля)
# ---------------------------------------------------------------------------

def _add_chest(rng, g, ctx, cell):
    x, y, z = cell
    if rng.random() < 0.3:
        state = {"Name": "minecraft:barrel",
                 "Properties": {"facing": "up", "open": "false"}}
        nbt = dict(_rand_chest_nbt(rng, ctx["loot_alloc"]),
                   id="minecraft:barrel")
    else:
        state = {"Name": "minecraft:chest",
                 "Properties": {"facing": rng.choice(
                     ("north", "south", "east", "west")),
                     "type": "single", "waterlogged": "false"}}
        nbt = dict(_rand_chest_nbt(rng, ctx["loot_alloc"]),
                   id="minecraft:chest")
    g.set(x, y, z, state, nbt=nbt)


def _add_mob(rng, ctx, entities, cell):
    x, y, z = cell
    entities.append({"pos": [x + 0.5, float(y), z + 0.5],
                     "blockPos": [x, y, z],
                     "nbt": _rand_mob_nbt(rng, ctx["loot_alloc"])})


def _add_spawner(rng, g, cell):
    x, y, z = cell
    g.set(x, y, z, {"Name": "minecraft:spawner"},
          nbt=_rand_spawner_nbt(rng))     # параметры и спектр сущностей —
                                          # в gen_structures (не дублируем)


def _decor_room(rng, g, ctx, entities, floor_y, free_cells,
                chest_n, torch_n, mob_p, spawner_p, furniture=True):
    """Общий декор интерьера: сундуки/факелы/мебель/редкие мобы/редкий
    спавнер. free_cells — свободные клетки НАД полом (floor_y+1).
    furniture=False — без случайной мебели (для узких проходов:
    лабиринт/шахта, где полные блоки перегораживают единственный путь)."""
    rng.shuffle(free_cells)
    used = set()
    # сундуки
    for _ in range(chest_n):
        if not free_cells:
            break
        cell = free_cells.pop()
        _add_chest(rng, g, ctx, (cell[0], floor_y + 1, cell[2]))
        used.add(cell)
    # спавнер (редко!) — в центре свободной зоны
    if rng.random() < spawner_p and free_cells:
        cell = free_cells.pop(len(free_cells) // 2)
        _add_spawner(rng, g, (cell[0], floor_y + 1, cell[2]))
        used.add(cell)
    # факелы/фонарь
    for _ in range(torch_n):
        if not free_cells:
            break
        cell = free_cells.pop()
        g.set(cell[0], floor_y + 1, cell[2],
              _LANTERN if rng.random() < 0.3 else _TORCH)
        used.add(cell)
    # случайная «мебель» из полных кубов (фильтрованная палитра — без
    # спавнеров/jigsaw, см. _mob_risk в _rand_jigsaw_one)
    if furniture:
        for _ in range(rng.randint(0, 2)):
            if not free_cells:
                break
            cell = free_cells.pop()
            g.set(cell[0], floor_y + 1, cell[2],
                  _gd().block_state(rng.choice(ctx["solid"])))
            used.add(cell)
    # мобы: максимум 2, с малым шансом
    r = rng.random()
    if r < mob_p and free_cells:
        cell = free_cells.pop()
        _add_mob(rng, ctx, entities, (cell[0], floor_y + 1, cell[2]))
        if rng.random() < 0.25 and free_cells:
            cell = free_cells.pop()
            _add_mob(rng, ctx, entities, (cell[0], floor_y + 1, cell[2]))


# ---------------------------------------------------------------------------
# Строители кусков по ролям
# ---------------------------------------------------------------------------

def _build_start_room(rng, ctx):
    """start: большая комната, 2-4 порта по разным граням, иногда потолочный
    порт. Один из портов получает имя anchor (для start_jigsaw_name)."""
    sx, sz = rng.randint(9, 15), rng.randint(9, 15)
    h = max(rng.randint(5, 8), ctx["H"] + 2)   # потолок выше проёма
    g = _Grid(sx, h, sz)
    _shell_room(rng, g, ctx, windows=True)
    n_ports = rng.randint(2, 4)
    faces = rng.sample(_FACES, n_ports)
    W = ctx["W"]
    anchor_face = rng.choice(faces)
    for face in faces:
        lo = 1 + W // 2
        hi = (sz if face in ("west", "east") else sx) - 2 - W // 2
        along = rng.randint(lo, hi)
        name = ctx["anchor_key"] if face == anchor_face else None
        _carve_side_port(rng, g, ctx, face, 0, along,
                         ctx["side_pool"]["start"], name=name)
    if ctx["has_vertical"] and rng.random() < 0.25:
        _room_ceiling_port(rng, g, ctx)
    free = _interior_free(g, 0)
    entities = []      # ВАЖНО: передаём и возвращаем один и тот же список —
    _decor_room(rng, g, ctx, entities, 0, free,   # иначе мобы (и их слоты
                chest_n=rng.randint(1, 2), torch_n=rng.randint(1, 3),  # лута)
                mob_p=0.40, spawner_p=0.08)       # терялись
    # «колодец» в полу старта (изредка): pbase — шахта вниз
    if ctx.get("has_down") and rng.random() < 0.20:
        zt = rng.randint(1, g.sz - 2)
        _carve_down_port(rng, g, ctx, 1, zt, pool=ctx["pbase_pool"])
        g.set(1, 1, zt, _AIR)   # лаз из колодца не забит декором
    return g, entities


def _build_room(rng, ctx):
    """room: коробка 7-15 x 4-8 x 7-15, 1-3 боковых порта, изредка
    потолочный порт (к башне/шпилю) и пол-порт (к колодцу/шахте).
    Планировки: plain (изредка угловые колонны) / pillared (колоннада
    вдоль длинной оси) / pit (центральная яма глубиной 2-3 со ступенями,
    лестницей и кладом на дне) / gallery (двухуровневый: кольцо-галерея
    на y=3..4 с лестницей и своим сундуком)."""
    style = rng.choice(("plain", "pillared", "pit", "gallery"))
    if style == "pit":
        return _build_room_pit(rng, ctx)
    if style == "gallery":
        return _build_room_gallery(rng, ctx)
    W, H = ctx["W"], ctx["H"]
    sx, sz = rng.randint(7, 15), rng.randint(7, 15)
    h = max(rng.randint(4, 8), ctx["H"] + 2)   # потолок выше проёма
    g = _Grid(sx, h, sz)
    _shell_room(rng, g, ctx, windows=True)
    n_ports = rng.randint(1, 3)
    W = ctx["W"]
    entities = []
    for face in rng.sample(_FACES, n_ports):
        lo = 1 + W // 2
        hi = (sz if face in ("west", "east") else sx) - 2 - W // 2
        _carve_side_port(rng, g, ctx, face, 0, rng.randint(lo, hi),
                         ctx["side_pool"]["room"])
    if ctx["has_vertical"] and rng.random() < 0.20:
        _room_ceiling_port(rng, g, ctx)
    if style == "pillared" and sx >= 9 and sz >= 9:
        # колоннада: два ряда колонн вдоль длинной оси
        if sx >= sz:
            for x in range(3, sx - 2, 3):
                for z in (2, sz - 3):
                    for y in range(1, h - 1):
                        g.set(x, y, z, ctx["accent"])
        else:
            for z in range(3, sz - 2, 3):
                for x in (2, sx - 3):
                    for y in range(1, h - 1):
                        g.set(x, y, z, ctx["accent"])
    elif sx >= 9 and sz >= 9 and rng.random() < 0.6:
        for (px, pz) in ((2, 2), (sx - 3, 2), (2, sz - 3), (sx - 3, sz - 3)):
            if rng.random() < 0.7:
                for y in range(1, h - 1):
                    g.set(px, y, pz, ctx["accent"])
    free = _interior_free(g, 0)
    _decor_room(rng, g, ctx, entities, 0, free,
                chest_n=rng.randint(0, 2), torch_n=rng.randint(0, 3),
                mob_p=0.30, spawner_p=0.10)
    # «колодец» в полу комнаты: pbase — шахта вниз (лестница у стены x=0)
    if ctx.get("has_down") and rng.random() < 0.30:
        zt = rng.randint(1, g.sz - 2)
        _carve_down_port(rng, g, ctx, 1, zt, pool=ctx["pbase_pool"])
        g.set(1, 1, zt, _AIR)   # лаз из колодца не забит декором
    return g, entities


def _build_room_pit(rng, ctx):
    """room/pit: зал с ямой — основной пол поднят на pb (2-3), в центре
    яма до самого низа куска; спуск — ступени-уступы с одной стороны и
    страховочная лестница у стенки, на дне клад/свет. Порты на основном
    уровне (этаж смещается, как у stairs)."""
    W, H = ctx["W"], ctx["H"]
    sx, sz = rng.randint(9, 13), rng.randint(9, 13)
    pb = rng.randint(2, 3)                   # глубина ямы = подъём пола
    h = pb + max(rng.randint(4, 6), H + 2)
    g = _Grid(sx, h, sz)
    entities = []
    # массив 0..pb-1 + основной пол y=pb + стены + крыша
    for x in range(sx):
        for z in range(sz):
            for y in range(pb):
                g.set(x, y, z, ctx["wall"])
            g.set(x, pb, z, ctx["floor"])
            edge = x in (0, sx - 1) or z in (0, sz - 1)
            corner = x in (0, sx - 1) and z in (0, sz - 1)
            for y in range(pb + 1, h - 1):
                g.set(x, y, z, ctx["accent"] if corner
                      else (ctx["wall"] if edge else _AIR))
            g.set(x, h - 1, z, ctx["frame"] if corner else ctx["wall"])
    # яма в центре
    pw, pd = rng.randint(3, 5), rng.randint(3, 5)
    x0, z0 = (sx - pw) // 2, (sz - pd) // 2
    for x in range(x0, x0 + pw):
        for z in range(z0, z0 + pd):
            for y in range(1, pb + 1):
                g.set(x, y, z, _AIR)
            g.set(x, 0, z, ctx["floor"])
    # ступени-уступы с западной стороны ямы
    for k in range(1, pb + 1):
        x = x0 - k
        if x < 1:
            break
        for z in range(z0, z0 + pd):
            for y in range(pb - k + 1, pb + 1):
                g.set(x, y, z, _AIR)
            g.set(x, pb - k, z, ctx["floor"])
    # страховочная лестница у восточной стенки ямы (опора — массив за ней)
    zm = z0 + pd // 2
    for y in range(1, pb + 1):
        g.set(x0 + pw - 1, y, zm, _ladder("west"))
    # порты на основном уровне
    for face in rng.sample(_FACES, rng.randint(1, 3)):
        lo = 1 + W // 2
        hi = (sz if face in ("west", "east") else sx) - 2 - W // 2
        _carve_side_port(rng, g, ctx, face, pb, rng.randint(lo, hi),
                         ctx["side_pool"]["room"])
    # клад на дне ямы + свет (ПОСЛЕ декора: лимит мобов ≤ 2 на кусок;
    # клетки ямы не пересекаются с free декора — он только над цельным полом)
    free = []
    for x in range(1, sx - 1):
        for z in range(1, sz - 1):
            below = g.get(x, pb, z)
            cell = g.get(x, pb + 1, z)
            if below is not None and below[0] is not _AIR \
                    and below[0] != _AIR \
                    and (cell is None or cell[0] is _AIR
                         or cell[0] == _AIR):
                free.append((x, pb + 1, z))
    _decor_room(rng, g, ctx, entities, pb, free,
                chest_n=rng.randint(0, 2), torch_n=rng.randint(0, 3),
                mob_p=0.30, spawner_p=0.10)
    if rng.random() < 0.55:
        _add_chest(rng, g, ctx, (x0 + pw // 2, 1, z0 + pd // 2))
    if rng.random() < 0.40:
        g.set(x0, 0, z0, ctx["light"])
    if rng.random() < 0.20 and len(entities) < 2:
        _add_mob(rng, ctx, entities, (x0 + pw // 2, 1, z0 + pd // 2 + 1))
    # шахта вниз из основного пола (продолжение массива — чистим лаз)
    if ctx.get("has_down") and rng.random() < 0.25:
        zt = rng.randint(1, sz - 2)
        _carve_down_port(rng, g, ctx, 1, zt, pool=ctx["pbase_pool"])
        for y in range(1, pb + 1):
            g.set(1, y, zt, _AIR)
    return g, entities


def _build_room_gallery(rng, ctx):
    """room/gallery: двухуровневый зал — кольцо-галерея шириной 2 на
    y=ug вдоль стен (перила по внутреннему краю, опорные колонны),
    лестница с пола; на галерее свой сундук/фонарь. Порты на уровне 0."""
    W, H = ctx["W"], ctx["H"]
    sx, sz = rng.randint(9, 15), rng.randint(9, 15)
    ug = rng.randint(3, 4)
    h = max(rng.randint(6, 8), ug + 4)
    g = _Grid(sx, h, sz)
    _shell_room(rng, g, ctx, windows=True)
    entities = []
    for face in rng.sample(_FACES, rng.randint(1, 3)):
        lo = 1 + W // 2
        hi = (sz if face in ("west", "east") else sx) - 2 - W // 2
        _carve_side_port(rng, g, ctx, face, 0, rng.randint(lo, hi),
                         ctx["side_pool"]["room"])
    if ctx["has_vertical"] and rng.random() < 0.15:
        _room_ceiling_port(rng, g, ctx)
    # галерея-кольцо шириной 2
    for x in range(1, sx - 1):
        for z in range(1, sz - 1):
            if x in (1, 2, sx - 3, sx - 2) or z in (1, 2, sz - 3, sz - 2):
                g.set(x, ug, z, ctx["floor"])
    # перила по внутреннему краю (каждый 2-й блок)
    for x in range(2, sx - 2):
        for z in range(2, sz - 2):
            if (x in (2, sx - 3) or z in (2, sz - 3)) \
                    and (x + z) % 2 == 0:
                g.set(x, ug + 1, z, ctx["frame"])
    # опорные колонны галереи
    for (px, pz) in ((2, 2), (sx - 3, 2), (2, sz - 3), (sx - 3, sz - 3),
                     (sx // 2, 2), (sx // 2, sz - 3),
                     (2, sz // 2), (sx - 3, sz // 2)):
        for y in range(1, ug):
            g.set(px, y, pz, ctx["accent"])
    # лестница на галерею (у западной стены; дыра в кольце — сама лестница)
    zt = rng.randint(3, sz - 4)
    for y in range(1, ug + 1):
        g.set(0, y, zt, ctx["wall"])
        g.set(1, y, zt, _ladder("east"))
    free = _interior_free(g, 0)
    _decor_room(rng, g, ctx, entities, 0, free,
                chest_n=rng.randint(0, 2), torch_n=rng.randint(0, 3),
                mob_p=0.30, spawner_p=0.10)
    if rng.random() < 0.40:                 # сундук на галерее
        _add_chest(rng, g, ctx, (rng.choice((2, sx - 3)), ug + 1,
                                 rng.randint(3, sz - 4)))
    if rng.random() < 0.35:
        g.set(sx - 2, ug + 1, sz - 2,
              _LANTERN if rng.random() < 0.3 else _TORCH)
    if ctx.get("has_down") and rng.random() < 0.25:
        zt2 = rng.randint(1, sz - 2)
        _carve_down_port(rng, g, ctx, 1, zt2, pool=ctx["pbase_pool"])
        g.set(1, 1, zt2, _AIR)
    return g, entities


def _shell_room(rng, g, ctx, windows):
    """Пол/стены/крыша комнаты: пол y=0, стены по периметру y=1..h-2
    (окна-дыры), крыша y=h-1, углы — акцент."""
    sx, sy, sz = g.sx, g.sy, g.sz
    for x in range(sx):
        for y in range(sy):
            for z in range(sz):
                edge = x in (0, sx - 1) or z in (0, sz - 1)
                corner = x in (0, sx - 1) and z in (0, sz - 1)
                if y == 0:
                    st = ctx["floor"]
                elif y == sy - 1:
                    st = ctx["frame"] if corner else ctx["wall"]
                elif corner:
                    st = ctx["accent"]
                elif edge:
                    if windows and 2 <= y <= sy - 3 and rng.random() < 0.08:
                        st = _AIR
                    else:
                        st = ctx["wall"]
                else:
                    st = _AIR
                g.set(x, y, z, st)


def _room_ceiling_port(rng, g, ctx):
    """Потолочный порт комнаты + лестничный столб к нему (лаз наверх —
    к башне/шпилю через tbase)."""
    zt = rng.randint(1, g.sz - 2)
    xt = 1                                   # опора — западная стена (x=0)
    for y in range(1, g.sy - 1):
        g.set(0, y, zt, ctx["wall"])         # опора лестницы всегда цельная
        g.set(xt, y, zt, _ladder("east"))
    _carve_up_port(rng, g, ctx, xt, zt, ctx["tbase_pool"])


def _interior_free(g, floor_y):
    """Свободные внутренние клетки над полом (не периметр)."""
    out = []
    for x in range(1, g.sx - 1):
        for z in range(1, g.sz - 1):
            cell = g.get(x, floor_y + 1, z)
            if cell is None or cell[0] is _AIR or cell[0] == _AIR:
                out.append((x, floor_y + 1, z))
    return out


def _build_corridor(rng, ctx):
    """corridor: труба W+2 в сечении, длина 5-12, порты с двух концов.
    Варианты: straight (прямой) / sshape (S-образный: два прямых плеча
    со смещёнными портами + диагональный переход — решает смещение
    стыков в данже) / slope (пологий склон: +1 блок каждые 2 колонки,
    закрытый потолок; круче — роль stairs)."""
    style = rng.choice(("straight", "sshape", "slope"))
    if style == "sshape":
        return _build_corridor_s(rng, ctx)
    if style == "slope":
        return _build_corridor_slope(rng, ctx)
    W, H = ctx["W"], ctx["H"]
    length = rng.randint(5, 12)
    h = H + 2
    along_x = rng.random() < 0.5
    sx, sz = (length, W + 2) if along_x else (W + 2, length)
    g = _Grid(sx, h, sz)
    entities = []
    for x in range(sx):
        for y in range(h):
            for z in range(sz):
                side = (z in (0, sz - 1)) if along_x else (x in (0, sx - 1))
                if y == 0 or y == h - 1:
                    st = ctx["floor"]
                elif side:
                    st = ctx["wall"]
                else:
                    st = _AIR
                g.set(x, y, z, st)
    # порты с двух концов
    for face in (("west", "east") if along_x else ("north", "south")):
        span = sz if along_x else sx
        _carve_side_port(rng, g, ctx, face, 0, span // 2,
                         ctx["side_pool"]["corridor"])
    # настенные факелы (каждые ~4 клетки, с шансом); facing = ОТ стены
    # (wall_torch[facing=F] держится на блоке с противоположной стороны)
    for i in range(2, length - 1, 4):
        if rng.random() < 0.5:
            if along_x:
                g.set(i, 2, 1, _wall_torch("south"))   # стена z=0
            else:
                g.set(1, 2, i, _wall_torch("east"))    # стена x=0
    free = _interior_free(g, 0)
    _decor_room(rng, g, ctx, entities, 0, free,
                chest_n=1 if rng.random() < 0.10 else 0, torch_n=0,
                mob_p=0.08, spawner_p=0.0)
    return g, entities


def _build_corridor_s(rng, ctx):
    """corridor/sshape: S-образный коридор — два плеча на разных
    z-линиях, соединённые диагональю (сдвиг ±1 на колонку); портам
    Запада/Востока соответствуют РАЗНЫЕ along — стыки расходятся по
    ширине куска. Массив вокруг трубы — сплошной (зарытый ход)."""
    W, H = ctx["W"], ctx["H"]
    length = rng.randint(9, 13)
    sz = W + 6
    h = H + 2
    cz = sz // 2
    z1, z2 = cz - 2, cz + 2
    if rng.random() < 0.5:
        z1, z2 = z2, z1
    diag = abs(z2 - z1)
    xd = rng.randint(2, length - 2 - diag)   # старт диагонали

    def zc(x):
        if x < xd:
            return z1
        if x < xd + diag:
            return z1 + (z2 - z1) * (x - xd + 1) // diag
        return z2

    g = _Grid(length, h, sz)
    entities = []
    half = W // 2
    for x in range(length):
        zc_ = zc(x)
        for z in range(sz):
            g.set(x, 0, z, ctx["floor"])
            g.set(x, h - 1, z, ctx["floor"])
            for y in range(1, h - 1):
                if zc_ - half <= z <= zc_ + half:
                    g.set(x, y, z, _AIR)       # внутренний объём
                else:
                    g.set(x, y, z, ctx["wall"])   # стены + массив вокруг
    # факелы на внутренней грани стены (стена — к северу от факела)
    for i in range(2, length - 1, 4):
        if rng.random() < 0.4:
            g.set(i, 2, zc(i) - half, _wall_torch("south"))
    # порты: запад — плечо z1, восток — плечо z2
    _carve_side_port(rng, g, ctx, "west", 0, z1,
                     ctx["side_pool"]["corridor"])
    _carve_side_port(rng, g, ctx, "east", 0, z2,
                     ctx["side_pool"]["corridor"])
    free = _interior_free(g, 0)
    _decor_room(rng, g, ctx, entities, 0, free,
                chest_n=1 if rng.random() < 0.10 else 0, torch_n=0,
                mob_p=0.08, spawner_p=0.0)
    return g, entities


def _build_corridor_slope(rng, ctx):
    """corridor/slope: пологий наклонный коридор — +1 блок каждые 2
    колонки (у stairs — каждая колонка), закрытый потолок, следующий
    уклону; порты на разных уровнях (этаж смещается)."""
    W, H = ctx["W"], ctx["H"]
    length = rng.randint(8, 12)
    rise = rng.randint(2, 5)
    h = rise + H + 2
    sz = W + 2
    g = _Grid(length, h, sz)
    entities = []

    def ramp(x):
        return min(rise, (x + 1) // 2)

    for x in range(length):
        gh = ramp(x)
        g.fill(x, 0, 1, x, gh - 1, sz - 2, ctx["floor"])       # марш
        g.fill(x, 0, 0, x, gh + H, 0, ctx["wall"])             # стены
        g.fill(x, 0, sz - 1, x, gh + H, sz - 1, ctx["wall"])
        g.fill(x, gh + H + 1, 0, x, gh + H + 1, sz - 1, ctx["floor"])  # крыша
    _carve_side_port(rng, g, ctx, "west", 0, sz // 2,
                     ctx["side_pool"]["corridor"])
    _carve_side_port(rng, g, ctx, "east", rise, sz // 2,
                     ctx["side_pool"]["corridor"])
    if rng.random() < 0.5:
        xm = length // 2
        g.set(xm, ramp(xm) + 1, 1, _wall_torch("south"))
    free = _interior_free(g, 0)
    _decor_room(rng, g, ctx, entities, 0, free,
                chest_n=0, torch_n=0, mob_p=0.06, spawner_p=0.0)
    return g, entities


def _build_bridge(rng, ctx):
    """bridge: открытая переправа — пол шириной W + перила, порты с концов."""
    W, H = ctx["W"], ctx["H"]
    length = rng.randint(5, 12)
    h = H + 2
    along_x = rng.random() < 0.5
    sx, sz = (length, W + 2) if along_x else (W + 2, length)
    g = _Grid(sx, h, sz)
    entities = []
    for x in range(sx):
        for y in range(h):
            for z in range(sz):
                g.set(x, y, z, _AIR)
    if along_x:
        g.fill(0, 0, 0, sx - 1, 0, sz - 1, ctx["floor"])
        # перила по краям (не на торцевых колоннах — там проёмы)
        g.fill(1, 1, 0, sx - 2, 1, 0, ctx["frame"])
        g.fill(1, 1, sz - 1, sx - 2, 1, sz - 1, ctx["frame"])
        for i in range(2, sx - 1, 3):        # факелы на перилах
            if rng.random() < 0.5:
                g.set(i, 2, 0, _TORCH)
                g.set(i, 1, 0, ctx["accent"])
        for face in ("west", "east"):
            _carve_side_port(rng, g, ctx, face, 0, sz // 2,
                             ctx["side_pool"]["bridge"])
    else:
        g.fill(0, 0, 0, sx - 1, 0, sz - 1, ctx["floor"])
        g.fill(0, 1, 1, 0, 1, sz - 2, ctx["frame"])
        g.fill(sx - 1, 1, 1, sx - 1, 1, sz - 2, ctx["frame"])
        for i in range(2, sz - 1, 3):
            if rng.random() < 0.5:
                g.set(0, 2, i, _TORCH)
                g.set(0, 1, i, ctx["accent"])
        for face in ("north", "south"):
            _carve_side_port(rng, g, ctx, face, 0, sx // 2,
                             ctx["side_pool"]["bridge"])
    if rng.random() < 0.04 and sx > 3 and sz > 3:
        _add_mob(rng, ctx, entities, (sx // 2, 1, sz // 2))
    return g, entities


def _build_stairs(rng, ctx):
    """stairs: террасная лестница из полных кубов, поднимается или опускается
    на 3-6 блоков; порты на разных высотах (этаж смещается)."""
    W, H = ctx["W"], ctx["H"]
    length = rng.randint(6, 10)
    rise = rng.randint(3, 6)
    h = rise + H + 2
    descend = rng.random() < 0.5
    sz = W + 2
    g = _Grid(length, h, sz)
    entities = []

    def ramp(x):
        t = min(rise, (x * rise) // max(1, length - 1))
        return rise - t if descend else t

    for x in range(length):
        gh = ramp(x)
        g.fill(x, 0, 1, x, gh - 1, sz - 2, ctx["floor"])       # марш
        g.fill(x, 0, 0, x, gh + H, 0, ctx["wall"])             # стены
        g.fill(x, 0, sz - 1, x, gh + H, sz - 1, ctx["wall"])
    # порты: вход у пола 0-го края, выход у пола rise-го
    if descend:
        _carve_side_port(rng, g, ctx, "west", rise, sz // 2,
                         ctx["side_pool"]["stairs"])
        _carve_side_port(rng, g, ctx, "east", 0, sz // 2,
                         ctx["side_pool"]["stairs"])
    else:
        _carve_side_port(rng, g, ctx, "west", 0, sz // 2,
                         ctx["side_pool"]["stairs"])
        _carve_side_port(rng, g, ctx, "east", rise, sz // 2,
                         ctx["side_pool"]["stairs"])
    # факел на стене в середине марша (стена z=0 → факел смотрит на юг)
    if rng.random() < 0.5:
        xm = length // 2
        ym = ramp(xm) + 1
        g.set(xm, ym, 1, _wall_torch("south"))
    if rng.random() < 0.06:
        xm = length // 2
        _add_mob(rng, ctx, entities, (xm, ramp(xm) + 1, sz // 2))
    return g, entities


def _build_tower(rng, ctx):
    """tower: вертикальный кусок 5-9 x 10-{max_tower_h} x 5-9: вход в полу
    (down), выход в крыше (up), сквозной лаз. Варианты: ladder (столб
    лестницы) / spiral (винтовая лестница вокруг центрального столба,
    для s>=7) / platforms (ярусные площадки с дырой под лестницу)."""
    s = rng.randint(5, 9)
    lo_h, hi_h = 10, ctx["max_tower_h"]
    h = rng.randint(lo_h, hi_h)
    g = _Grid(s, h, s)
    entities = []
    style = rng.choice(("ladder", "spiral", "platforms"))
    for x in range(s):
        for y in range(h):
            for z in range(s):
                edge = x in (0, s - 1) or z in (0, s - 1)
                if y == 0 or y == h - 1:
                    st = ctx["floor"]
                elif edge:
                    if 3 <= y <= h - 4 and rng.random() < 0.04:
                        st = _AIR              # бойницы
                    else:
                        st = ctx["wall"]
                else:
                    st = _AIR
                g.set(x, y, z, st)
    zt = rng.randint(1, s - 2)
    xt = 1                                    # опора — западная стена
    if style == "spiral" and s >= 7:
        # винт вокруг центрального столба: 4 позиции кольца, +1 y за шаг
        c = s // 2
        ring = ((c - 1, c), (c, c + 1), (c + 1, c), (c, c - 1))
        for y in range(1, h - 1):
            g.set(c, y, c, ctx["wall"])
        y = 2
        i = 0
        while y <= h - 3:
            px, pz = ring[i % 4]
            if (px, pz) != (xt, zt):
                g.set(px, y, pz,
                      ctx["accent"] if i % 4 == 0 else ctx["floor"])
            y += 1
            i += 1
    elif style == "platforms":
        # ярусные площадки: сплошные диски с дырой у лестницы
        step = rng.randint(3, 4)
        for p in range(3, h - 1, step):
            for x in range(1, s - 1):
                for z in range(1, s - 1):
                    if (x, z) != (xt, zt):
                        g.set(x, p, z, ctx["floor"])
    for y in range(1, h - 1):
        g.set(0, y, zt, ctx["wall"])          # опора лестницы цельная
        g.set(xt, y, zt, _ladder("east"))
    _carve_down_port(rng, g, ctx, xt, zt)
    _carve_up_port(rng, g, ctx, xt, zt, ctx["tchain_pool"])
    # факелы на разных высотах (не на линии лестницы); стена x=0 → facing east
    for y in range(3, h - 2, max(3, h // 4)):
        if rng.random() < 0.4 and zt != s - 2:
            g.set(1, y, s - 2, _wall_torch("east"))
    if rng.random() < 0.15:
        _add_chest(rng, g, ctx, (s - 2, 1, 1))
    if rng.random() < 0.05:
        _add_mob(rng, ctx, entities, (s // 2, 1, s // 2))
    return g, entities


def _build_tower_top(rng, ctx):
    """tower_top: вершина башни — вход в полу, зубцы, сундук-награда."""
    s = rng.randint(5, 9)
    h = rng.randint(4, 7)
    g = _Grid(s, h, s)
    entities = []
    for x in range(s):
        for y in range(h):
            for z in range(s):
                edge = x in (0, s - 1) or z in (0, s - 1)
                st = ctx["floor"] if y in (0, h - 1) else (
                    ctx["wall"] if edge else _AIR)
                g.set(x, y, z, st)
    # зубцы по периметру крыши
    for x in range(0, s, 2):
        g.set(x, h - 1, 0, ctx["accent"])
        g.set(x, h - 1, s - 1, ctx["accent"])
    for z in range(0, s, 2):
        g.set(0, h - 1, z, ctx["accent"])
        g.set(s - 1, h - 1, z, ctx["accent"])
    zt = rng.randint(1, s - 2)
    xt = 1
    for y in range(1, h - 1):
        g.set(0, y, zt, ctx["wall"])
        g.set(xt, y, zt, _ladder("east"))
    _carve_down_port(rng, g, ctx, xt, zt)
    if rng.random() < 0.45 and s >= 4:
        _add_chest(rng, g, ctx, (s - 2, 1, 1))
    if rng.random() < 0.30:
        g.set(s - 2, 1, s - 2, _TORCH)
    if rng.random() < 0.20:
        _add_mob(rng, ctx, entities, (s // 2, 1, s // 2))
    return g, entities


def _build_cap(rng, ctx):
    """cap: тупик-финишер — короткий карман с торцевой стеной; иногда
    открытый балкон. Единственный порт терминальный (pool minecraft:empty)."""
    W, H = ctx["W"], ctx["H"]
    length = rng.randint(3, 5)
    h = H + 2
    sz = W + 2
    g = _Grid(length, h, sz)
    entities = []
    balcony = rng.random() < 0.3
    for x in range(length):
        for y in range(h):
            for z in range(sz):
                if y == 0:
                    st = ctx["floor"]
                elif balcony:
                    st = _AIR
                elif y == h - 1:
                    st = ctx["wall"]
                elif x == length - 1 or z in (0, sz - 1):
                    st = ctx["wall"]
                else:
                    st = _AIR
                g.set(x, y, z, st)
    if balcony:                                # перила
        g.fill(0, 1, 0, length - 2, 1, 0, ctx["frame"])
        g.fill(0, 1, sz - 1, length - 2, 1, sz - 1, ctx["frame"])
        g.fill(length - 1, 1, 1, length - 1, 1, sz - 2, ctx["frame"])
        g.fill(length - 1, 0, 0, length - 1, 1, 0, ctx["frame"])
        g.fill(length - 1, 0, sz - 1, length - 1, 1, sz - 1, ctx["frame"])
        if rng.random() < 0.4:
            g.set(1, 2, 0, _TORCH)
    _carve_side_port(rng, g, ctx, "west", 0, sz // 2, "minecraft:empty")
    free = _interior_free(g, 0)
    _decor_room(rng, g, ctx, entities, 0, free,
                chest_n=1 if rng.random() < 0.35 else 0,
                torch_n=1 if rng.random() < 0.25 else 0,
                mob_p=0.08, spawner_p=0.0)
    return g, entities


# ---------------------------------------------------------------------------
# Новые архетипы кусков: gate / courtyard / spire / terrace / pit / viaduct
# (портовый профиль общий со всеми: боковые WxH в плоскости пола,
# joint=rollable, симметричные name==target — куски стыкуются с любыми)
# ---------------------------------------------------------------------------

def _build_gate(rng, ctx):
    """gate: ворота/арка — массивная рама толщиной 2-4 с проёмом ровно
    в профиль WxH (стыкуется с коридорами/комнатами встык), над проёмом —
    перемычка, сверху декоративная перекладина из акцента по всей ширине.
    Порты с двух концов прохода."""
    W, H = ctx["W"], ctx["H"]
    length = rng.randint(2, 4)              # толщина ворот
    wide = W + 2 * rng.randint(1, 2)        # рама шире проёма на 1-2 с боков
    h = H + 2 + rng.randint(1, 3)           # проём + перемычка + перекладина
    along_x = rng.random() < 0.5
    sx, sz = (length, wide) if along_x else (wide, length)
    g = _Grid(sx, h, sz)
    entities = []
    o0 = (wide - W) // 2                    # начало проёма поперёк прохода
    o1 = o0 + W - 1
    for a in range(length):
        for y in range(1, h):
            for b in range(wide):
                if y == h - 1:
                    st = ctx["accent"]             # перекладина поверху
                elif o0 <= b <= o1 and y <= H:
                    st = _AIR                      # сквозной проём WxH
                else:
                    st = ctx["wall"]               # быки + перемычка
                if along_x:
                    g.set(a, y, b, st)
                else:
                    g.set(b, y, a, st)
    g.fill(0, 0, 0, sx - 1, 0, sz - 1, ctx["floor"])
    faces = ("west", "east") if along_x else ("north", "south")
    for face in faces:
        _carve_side_port(rng, g, ctx, face, 0,
                         sz // 2 if along_x else sx // 2,
                         ctx["side_pool"]["gate"])
    # факелы на внутренних гранях быков (опора — блок быка позади факела);
    # только когда быки ≥ 2 шириной, иначе факелу не на чем держаться
    if wide - W >= 4:
        mid = length // 2
        if along_x:
            if rng.random() < 0.5:
                g.set(mid, 2, o0 - 1, _wall_torch("south"))
            if rng.random() < 0.5:
                g.set(mid, 2, o1 + 1, _wall_torch("north"))
        else:
            if rng.random() < 0.5:
                g.set(o0 - 1, 2, mid, _wall_torch("east"))
            if rng.random() < 0.5:
                g.set(o1 + 1, 2, mid, _wall_torch("west"))
    # редкая живность/сундук в проёме (как у коридора)
    if rng.random() < 0.10:
        _add_chest(rng, g, ctx, (sx // 2, 1, sz // 2))
    if rng.random() < 0.08:
        _add_mob(rng, ctx, entities, (sx // 2, 1, sz // 2))
    return g, entities


def _build_courtyard(rng, ctx):
    """courtyard: открытый дворик — площадка 9-15x9-15 (в пределах 16x16),
    колоннада по внутреннему периметру (углы — акцент, колонны выше стен),
    БЕЗ кровли (верхний слой — воздух), пол из палитры; в центре иногда
    постамент с фонарём, изредка «колодец»-порт в полу. 1-3 боковых порта."""
    sx, sz = rng.randint(9, 15), rng.randint(9, 15)
    h = ctx["H"] + 2 + rng.randint(0, 1)    # низкие стены, потолка нет
    g = _Grid(sx, h, sz)
    entities = []
    # стены по периметру y=1..h-2 (окна-пролёты); верхний слой НЕ заполняем
    for x in range(sx):
        for y in range(1, h - 1):
            for z in range(sz):
                edge = x in (0, sx - 1) or z in (0, sz - 1)
                corner = x in (0, sx - 1) and z in (0, sz - 1)
                if corner:
                    g.set(x, y, z, ctx["accent"])
                elif edge and not (2 <= y <= h - 3
                                   and rng.random() < 0.08):
                    g.set(x, y, z, ctx["wall"])
    g.fill(0, 0, 0, sx - 1, 0, sz - 1, ctx["floor"])
    # колоннада: кольцо с отступом 2 от стен, колонны до h-1 (выше стен)
    for x in range(2, sx - 2):
        for z in range(2, sz - 2):
            if not (x in (2, sx - 3) or z in (2, sz - 3)):
                continue
            if (x + z) % 3 == 0 or rng.random() < 0.25:
                for y in range(1, h):
                    g.set(x, y, z, ctx["wall"])
    for (px, pz) in ((2, 2), (sx - 3, 2), (2, sz - 3), (sx - 3, sz - 3)):
        for y in range(1, h):
            g.set(px, y, pz, ctx["accent"])   # угловые колонны — акцент
    W = ctx["W"]
    for face in rng.sample(_FACES, rng.randint(1, 3)):
        lo = 1 + W // 2
        hi = (sz if face in ("west", "east") else sx) - 2 - W // 2
        _carve_side_port(rng, g, ctx, face, 0, rng.randint(lo, hi),
                         ctx["side_pool"]["courtyard"])
    # постамент в центре — ДО расчёта свободных клеток (исключится из decor)
    if rng.random() < 0.6:
        g.set(sx // 2, 1, sz // 2, ctx["accent"])
        if rng.random() < 0.5:
            g.set(sx // 2, 2, sz // 2,
                  _LANTERN if rng.random() < 0.4 else _TORCH)
    free = _interior_free(g, 0)
    _decor_room(rng, g, ctx, entities, 0, free,
                chest_n=rng.randint(0, 2), torch_n=rng.randint(1, 3),
                mob_p=0.25, spawner_p=0.06)
    # «колодец» во дворике (между стеной и колоннадой): x=1 / sx-2
    if ctx.get("has_down") and rng.random() < 0.35:
        wx = 1 if rng.random() < 0.5 else sx - 2
        wz = rng.randint(2, sz - 3)
        _carve_down_port(rng, g, ctx, wx, wz, pool=ctx["pbase_pool"])
        g.set(wx, 1, wz, _AIR)   # лаз из колодца не забит декором
    return g, entities


def _build_spire(rng, ctx):
    """spire: обелиск/шпиль — узкая полая стела 3x3 или 5x5 в основании,
    сужается кверху (5x5 → 3x3 → «плюс» без углов), высота 8..max_tower_h;
    вершина — сплошная площадка с «глазком» из акцента по углам. Вход в
    полу (down, терминальный), выход в вершине (up, tchain) — вертикальная
    цепочка как у башни; лестница идёт сквозь всю стелу."""
    s = rng.choice([3, 5])
    h = rng.randint(8, ctx["max_tower_h"])
    g = _Grid(s, h, s)
    entities = []
    ins = (s - 3) // 2                     # 1 для s=5, 0 для s=3
    t1 = (h // 3) if s == 5 else 0         # y<=t1 — широкое основание 5x5
    t2 = (2 * h) // 3                      # t1<y<=t2 — среднее сечение 3x3
    for y in range(h):
        lo = 0 if y <= t1 else ins
        hi = s - 1 if y <= t1 else s - 1 - ins
        for x in range(s):
            for z in range(s):
                if not (lo <= x <= hi and lo <= z <= hi):
                    continue               # вне сечения — воздух
                corner = x in (lo, hi) and z in (lo, hi)
                if t2 < y < h - 1 and corner:
                    continue               # верхний ярус — «плюс» без углов
                if y == 0:
                    g.set(x, y, z, ctx["floor"])
                elif y == h - 1:
                    g.set(x, y, z,         # вершина: углы — «глазок»
                          ctx["accent"] if corner else ctx["wall"])
                elif not corner and not (x in (lo, hi) or z in (lo, hi)):
                    continue               # полость сечения — воздух (лаз)
                elif y >= 2 and rng.random() < 0.04:
                    continue               # редкие бойницы в стенах
                else:
                    g.set(x, y, z, ctx["wall"])
    # лестница по центру + цельная опора к западу (как у башни): непрерывный
    # лаз от пол-порта до вершинного порта
    c = s // 2
    for y in range(1, h - 1):
        g.set(c - 1, y, c, ctx["wall"])
        g.set(c, y, c, _ladder("east"))
    _carve_down_port(rng, g, ctx, c, c)
    _carve_up_port(rng, g, ctx, c, c, ctx["tchain_pool"])
    # базовая камера (только s=5): редкий сундук/свет/моб — клетки
    # кроме лестницы и опоры
    if s == 5:
        if rng.random() < 0.20:
            _add_chest(rng, g, ctx, (3, 1, 3))
        if rng.random() < 0.40:
            g.set(3, 1, 1, _LANTERN if rng.random() < 0.3 else _TORCH)
        if rng.random() < 0.05:
            _add_mob(rng, ctx, entities, (2, 1, 1))
    return g, entities


def _build_terrace(rng, ctx):
    """terrace: 2-3 уступа-платформы из полных кубов, между уступами
    короткие марши (по +1 блоку на колонку, как stairs); на каждом
    уступе СВОЯ декорация (факел на стене / сундук / моб / фонарь).
    Порты с концов на уровнях первого и последнего уступа (этаж смещается)."""
    W, H = ctx["W"], ctx["H"]
    length = rng.randint(8, 12)
    n_tiers = rng.randint(2, 3)
    # перепад на уступ: площадки ≥ 2 колонки + марши по rise колонок
    max_rise = max(1, (length - 2 * n_tiers) // (n_tiers - 1))
    rise = rng.randint(1, min(3, max_rise))
    h = (n_tiers - 1) * rise + H + 2
    sz = W + 2 + 2 * rng.randint(0, 1)      # иногда пошире
    g = _Grid(length, h, sz)
    entities = []
    # ширины площадок (сумма = length − марши), лишнее — случайно по площадкам
    widths = [2] * n_tiers
    for _ in range(length - (n_tiers - 1) * rise - 2 * n_tiers):
        widths[rng.randrange(n_tiers)] += 1
    # высота колонок: площадка t — поверхность y = 1 + t*rise (пол всегда
    # есть, швов-дыр как у stairs не бывает); марш — по +1 блоку на колонку
    ch = []
    for t in range(n_tiers):
        ch += [1 + t * rise] * widths[t]
        if t < n_tiers - 1:
            for k in range(1, rise + 1):
                ch.append(1 + t * rise + k)
    for x in range(length):
        c = ch[x]
        g.fill(x, 0, 1, x, c - 1, sz - 2, ctx["floor"])   # массив уступа
        g.fill(x, 0, 0, x, c + H, 0, ctx["wall"])         # стены
        g.fill(x, 0, sz - 1, x, c + H, sz - 1, ctx["wall"])
    # порты: вход у пола 1-го уступа, выход у пола последнего
    top = 1 + (n_tiers - 1) * rise
    _carve_side_port(rng, g, ctx, "west", 0, sz // 2,
                     ctx["side_pool"]["terrace"])
    _carve_side_port(rng, g, ctx, "east", top - 1, sz // 2,
                     ctx["side_pool"]["terrace"])
    # декорации: на каждой площадке своя (не в торцевых колонках)
    x0 = 0
    for t in range(n_tiers):
        xm = min(x0 + widths[t] // 2, length - 2)
        surf = 1 + t * rise
        if rng.random() < 0.5:               # факел на стене z=0
            g.set(xm, surf + 1, 1, _wall_torch("south"))
        r = rng.random()
        if r < 0.15:
            _add_chest(rng, g, ctx, (xm, surf, sz // 2))
        elif r < 0.21:
            _add_mob(rng, ctx, entities, (xm, surf, sz // 2))
        elif rng.random() < 0.4:
            g.set(xm, surf, sz // 2,
                  _LANTERN if rng.random() < 0.3 else _TORCH)
        x0 += widths[t] + rise
    return g, entities


def _build_pit(rng, ctx):
    """pit: колодец — закрытая шахта ПОД комнатой/двориком: вход — порт
    в крыше (up, терминальный; дёргается пол-портом через pbase, шов —
    лестница), внутри спиральная лестница вокруг центрального столба,
    на дне «комнатка» с декором. Высота 8..max_tower_h (YSpan ≤ 16 при
    use_expansion_hack)."""
    s = rng.choice([5, 7])
    h = rng.randint(8, ctx["max_tower_h"])
    g = _Grid(s, h, s)
    entities = []
    # замкнутая оболочка: стены, дно y=0, крыша y=h-1
    for x in range(s):
        for y in range(h):
            for z in range(s):
                edge = x in (0, s - 1) or z in (0, s - 1)
                if y in (0, h - 1):
                    st = ctx["floor"]
                elif edge:
                    st = ctx["wall"]
                else:
                    st = _AIR
                g.set(x, y, z, st)
    c = s // 2
    # центральный столб (ядро спирали) + непрерывная лестница у стены x=0
    for y in range(1, h - 1):
        g.set(c, y, c, ctx["wall"])
        g.set(1, y, c, _ladder("east"))
    _carve_up_port(rng, g, ctx, 1, c, "minecraft:empty")
    # спиральная лестница: кольцо позиций вокруг столба (радиус 1), каждая
    # следующая ступень на 1 ниже; клетку лестницы пропускаем
    ring = []
    for k in range(-1, 2):
        ring.append((c - 1, c + k))          # западная грань (на юг)
    for k in range(0, 2):
        ring.append((c + k, c + 1))          # южная грань (на восток)
    for k in range(1, -2, -1):
        ring.append((c + 1, c + k))          # восточная грань (на север)
    for k in range(1, 0, -1):
        ring.append((c + k, c - 1))          # северная грань (на запад)
    y = h - 4
    i = 0
    while y >= 2 and i < 80:
        px, pz = ring[i % len(ring)]
        if (px, pz) != (1, c):
            g.set(px, y, pz,
                  ctx["accent"] if i % 4 == 0 else ctx["floor"])
            y -= 1
        i += 1
    # «комнатка» на дне: декор по свободным клеткам y=1
    free = _interior_free(g, 0)
    _decor_room(rng, g, ctx, entities, 0, free,
                chest_n=1 if rng.random() < 0.5 else 0,
                torch_n=rng.randint(0, 1), mob_p=0.25, spawner_p=0.10)
    return g, entities


def _build_viaduct(rng, ctx):
    """viaduct: мост на опорах — палуба с перилами (как bridge), но
    поднята на 2-5 блоков от низа куска, под ней столбы-опоры по линиям
    перил каждые 3 клетки (с акцент-капителью). Порты с концов на уровне
    палубы."""
    W, H = ctx["W"], ctx["H"]
    length = rng.randint(5, 12)
    pd = rng.randint(2, 5)                  # клиренс под палубой
    h = pd + H + 2
    along_x = rng.random() < 0.5
    sx, sz = (length, W + 2) if along_x else (W + 2, length)
    g = _Grid(sx, h, sz)
    entities = []
    if along_x:
        for i in range(2, sx - 1, 3):       # опоры под палубой
            for y in range(pd):
                g.set(i, y, 0, ctx["frame"])
                g.set(i, y, sz - 1, ctx["frame"])
            if pd >= 2:                     # капитель под палубой
                g.set(i, pd - 1, 0, ctx["accent"])
                g.set(i, pd - 1, sz - 1, ctx["accent"])
        g.fill(0, pd, 0, sx - 1, pd, sz - 1, ctx["floor"])     # палуба
        g.fill(1, pd + 1, 0, sx - 2, pd + 1, 0, ctx["frame"])  # перила
        g.fill(1, pd + 1, sz - 1, sx - 2, pd + 1, sz - 1, ctx["frame"])
        for i in range(2, sx - 1, 3):       # факелы на перилах
            if rng.random() < 0.5:
                g.set(i, pd + 2, 0, _TORCH)
                g.set(i, pd + 1, 0, ctx["accent"])
        for face in ("west", "east"):
            _carve_side_port(rng, g, ctx, face, pd, sz // 2,
                             ctx["side_pool"]["viaduct"])
    else:
        for i in range(2, sz - 1, 3):
            for y in range(pd):
                g.set(0, y, i, ctx["frame"])
                g.set(sx - 1, y, i, ctx["frame"])
            if pd >= 2:
                g.set(0, pd - 1, i, ctx["accent"])
                g.set(sx - 1, pd - 1, i, ctx["accent"])
        g.fill(0, pd, 0, sx - 1, pd, sz - 1, ctx["floor"])
        g.fill(0, pd + 1, 1, 0, pd + 1, sz - 2, ctx["frame"])
        g.fill(sx - 1, pd + 1, 1, sx - 1, pd + 1, sz - 2, ctx["frame"])
        for i in range(2, sz - 1, 3):
            if rng.random() < 0.5:
                g.set(0, pd + 2, i, _TORCH)
                g.set(0, pd + 1, i, ctx["accent"])
        for face in ("north", "south"):
            _carve_side_port(rng, g, ctx, face, pd, sx // 2,
                             ctx["side_pool"]["viaduct"])
    if rng.random() < 0.10:
        _add_chest(rng, g, ctx, (sx // 2, pd + 1, sz // 2))
    if rng.random() < 0.04:
        _add_mob(rng, ctx, entities, (sx // 2, pd + 1, sz // 2))
    return g, entities


# ---------------------------------------------------------------------------
# НОВЫЕ архетипы кусков (портовый профиль общий со всеми: боковые WxH в
# плоскости пола, joint=rollable, симметричные name==target — куски
# стыкуются с любыми). Живность — как у существующих ролей: мобы ≤ 2
# с малым шансом, спавнер ≤ 10-12% и только в «комнатных» архетипах
# ---------------------------------------------------------------------------

def _oct_inside(x, z, c, r, lim):
    """Клетка внутри октагона (грани: |dx|<=r, |dz|<=r, |dx|+|dz|<=lim)."""
    dx, dz = abs(x - c), abs(z - c)
    return dx <= r and dz <= r and dx + dz <= lim


def _oct_edge(x, z, c, r, lim):
    dx, dz = abs(x - c), abs(z - c)
    return _oct_inside(x, z, c, r, lim) and (
        dx == r or dz == r or dx + dz == lim)


def _build_rotunda(rng, ctx):
    """rotunda: ротонда — октагональный зал 11-15 в диаметре, кольцо
    колонн с отступом 2, купол-свод из сужающихся октагональных колец
    (2-3 яруса + акцент-макушка). Размер подбирается под профиль W —
    чтобы проём WxH попадал в грань октагона (|dz| <= lim-R)."""
    W, H = ctx["W"], ctx["H"]
    s = rng.choice([13, 15] if W == 5 else [11, 13, 15])
    c = s // 2
    R = s // 2
    lim = R + max(1, R // 3)          # срез углов октагона
    wall_h = max(rng.randint(4, 6), H + 2)
    dome = rng.randint(2, 3)
    h = wall_h + dome + 1
    g = _Grid(s, h, s)
    entities = []
    # стены-кольцо (вершины октагона — акцент) + редкие бойницы
    verts = set()
    for sx_ in (-1, 1):
        for sz_ in (-1, 1):
            verts.add((c + sx_ * R, c + sz_ * (lim - R)))
            verts.add((c + sx_ * (lim - R), c + sz_ * R))
    for x in range(s):
        for z in range(s):
            if not _oct_edge(x, z, c, R, lim):
                if _oct_inside(x, z, c, R, lim):
                    g.set(x, 0, z, ctx["floor"])   # пол — октагон
                continue
            g.set(x, 0, z, ctx["floor"])
            for y in range(1, wall_h):
                if 2 <= y <= wall_h - 2 and rng.random() < 0.05:
                    continue                          # бойницы
                g.set(x, y, z, ctx["accent"] if (x, z) in verts
                      else ctx["wall"])
    # купол: сужающиеся октагональные слои
    for k in range(dome + 1):
        rk, limk = R - k, lim - k
        if rk < 1:
            break
        for x in range(s):
            for z in range(s):
                if _oct_inside(x, z, c, rk, limk):
                    g.set(x, wall_h + k, z,
                          ctx["accent"] if k == dome else ctx["wall"])
    # колоннада: кольцо с отступом 2, каждая 3-я клетка — колонна
    ri, limi = R - 2, lim - 2
    for x in range(s):
        for z in range(s):
            if _oct_edge(x, z, c, ri, limi) and (x + z) % 3 == 0:
                for y in range(1, wall_h):
                    g.set(x, y, z, ctx["accent"])
    # порты (1-3): вдоль грани, в пределах стенки октагона
    m = max(0, (lim - R) - W // 2)
    for face in rng.sample(_FACES, rng.randint(1, 3)):
        along = c + rng.randint(-m, m)
        _carve_side_port(rng, g, ctx, face, 0, along,
                         ctx["side_pool"]["rotunda"])
    # свет под куполом
    if rng.random() < 0.5:
        g.set(c, wall_h - 1, c, ctx["light"])
    free = []
    for x in range(1, s - 1):
        for z in range(1, s - 1):
            if not _oct_inside(x, z, c, R, lim) or _oct_edge(x, z, c, R, lim):
                continue
            cell = g.get(x, 1, z)
            if cell is None or cell[0] is _AIR or cell[0] == _AIR:
                free.append((x, 1, z))
    _decor_room(rng, g, ctx, entities, 0, free,
                chest_n=rng.randint(0, 2), torch_n=rng.randint(1, 3),
                mob_p=0.25, spawner_p=0.08)
    return g, entities


def _build_arena(rng, ctx):
    """arena: овальная чаша 13-15 — поле на уровне пола, вокруг 2-3
    яруса трибун-уступов (ступенчатые овалы, +1 блок на ярус), внешняя
    стена выше, небо открыто. Порты (1-2) на уровне поля; над портом —
    «вомиторий»: туннель сквозь трибуны к полю."""
    W, H = ctx["W"], ctx["H"]
    s = rng.randint(13, 15)
    c = s // 2
    rim = rng.randint(2, 3)                # ярусы трибун
    r_field = s / 2.0 - 3.0                # радиус поля чаши
    step_t = rng.uniform(0.35, 0.55)       # порог яруса в метрике овала
    h = max(H + 2, rim + 3)
    g = _Grid(s, h, s)
    entities = []

    def seat_level(x, z):
        t = ((x - c) / r_field) ** 2 + ((z - c) / r_field) ** 2
        if t <= 1.0:
            return 0
        return min(rim, 1 + int((t - 1.0) / step_t))

    for x in range(s):
        for z in range(s):
            edge = x in (0, s - 1) or z in (0, s - 1)
            corner = x in (0, s - 1) and z in (0, s - 1)
            lvl = seat_level(x, z)
            g.set(x, 0, z, ctx["floor"])
            for y in range(1, h - 1):
                if corner:
                    st = ctx["accent"]
                elif edge:
                    st = ctx["wall"]
                elif y <= lvl:
                    st = ctx["accent"] if y == lvl else ctx["wall"]
                else:
                    st = _AIR
                g.set(x, y, z, st)
    # порты + вомитории
    half = W // 2
    for face in rng.sample(_FACES, rng.randint(1, 2)):
        lo = 1 + W // 2
        hi = s - 2 - W // 2
        along = rng.randint(lo, hi)
        _carve_side_port(rng, g, ctx, face, 0, along,
                         ctx["side_pool"]["arena"])
        for k in (1, 2, 3):                 # туннель сквозь трибуны
            for w in range(along - half, along + half + 1):
                for y in range(1, H + 1):
                    if face == "west":
                        g.set(k, y, w, _AIR)
                    elif face == "east":
                        g.set(s - 1 - k, y, w, _AIR)
                    elif face == "north":
                        g.set(w, y, k, _AIR)
                    else:
                        g.set(w, y, s - 1 - k, _AIR)
    if rng.random() < 0.35:                # подиум в центре арены
        g.set(c, 1, c, ctx["accent"])
    free = _interior_free(g, 0)
    _decor_room(rng, g, ctx, entities, 0, free,
                chest_n=rng.randint(0, 1), torch_n=rng.randint(0, 2),
                mob_p=0.30, spawner_p=0.10)
    return g, entities


def _build_workshop(rng, ctx):
    """workshop: мастерская — 2-4 верстака у стены (crafting/smithing/
    fletching/cartography/loom — полные блоки без block entity), 1-2
    печи (furnace-семейство, штучно — как в ванильных деревнях),
    ниши-полки из bookshelf в стенах."""
    W, H = ctx["W"], ctx["H"]
    sx, sz = rng.randint(9, 13), rng.randint(7, 11)
    h = max(rng.randint(4, 6), H + 2)
    g = _Grid(sx, h, sz)
    _shell_room(rng, g, ctx, windows=True)
    entities = []
    # ниши-полки ДО портов (проём прорежет своё)
    for x in range(sx):
        for z in range(sz):
            if (x in (0, sx - 1)) != (z in (0, sz - 1)):   # стены без углов
                if rng.random() < 0.14:
                    for y in range(2, 2 + rng.randint(1, 2) + 1):
                        if y < h - 1:
                            g.set(x, y, z, _BOOKSHELF)
    for face in rng.sample(_FACES, rng.randint(1, 2)):
        lo = 1 + W // 2
        hi = (sz if face in ("west", "east") else sx) - 2 - W // 2
        _carve_side_port(rng, g, ctx, face, 0, rng.randint(lo, hi),
                         ctx["side_pool"]["workshop"])
    if ctx["has_vertical"] and rng.random() < 0.15:
        _room_ceiling_port(rng, g, ctx)
    # верстаки у северной стены
    for x in rng.sample(range(2, sx - 2), min(rng.randint(2, 4), sx - 4)):
        g.set(x, 1, 1, rng.choice(_WORKSHOP_STATIONS))
    # печи у южной (front — в комнату)
    for x in rng.sample(range(2, sx - 2), rng.randint(1, 2)):
        g.set(x, 1, sz - 2,
              _furnace_state(rng, rng.choice(
                  ("minecraft:furnace", "minecraft:blast_furnace",
                   "minecraft:smoker")), "north"))
    free = _interior_free(g, 0)
    _decor_room(rng, g, ctx, entities, 0, free,
                chest_n=rng.randint(0, 2), torch_n=rng.randint(1, 3),
                mob_p=0.25, spawner_p=0.06)
    return g, entities


def _add_vault_solo(rng, g, ctx, cell):
    """Волт-«загадка»: ключ — случайный предмет (НЕ trial_key: без
    парного спавнера ключ недобываем; см. gen_structures._place_vault).
    Лут-слот — свой уникальный, как у сундука."""
    x, y, z = cell
    nbt = _rand_vault_nbt(rng, ctx["loot_alloc"])
    nbt["config"]["key_item"] = {"id": rng.choice(_VAULT_KEY_ITEMS),
                                 "count": 1}
    g.set(x, y, z, {"Name": "minecraft:vault",
                    "Properties": {"facing": rng.choice(
                        ("north", "south", "east", "west")),
                        "vault_state": "inactive",
                        "ominous": "false"}}, nbt=nbt)


def _build_treasury(rng, ctx):
    """treasury: сейф-комната 7-9 — ДВОЙНЫЕ стены (кольца 0 и 1, углы
    акцент), интерьер 3-5: ГАРАНТИРОВАННЫЕ 1-2 сундука/волта по углам,
    декоративные блоки, свет в крыше. Живность редкая (охрана)."""
    W, H = ctx["W"], ctx["H"]
    sx, sz = rng.randint(7, 9), rng.randint(7, 9)
    h = max(rng.randint(4, 5), H + 2)
    g = _Grid(sx, h, sz)
    entities = []
    for x in range(sx):
        for y in range(h):
            for z in range(sz):
                if y == 0 or y == h - 1:
                    g.set(x, y, z, ctx["floor"])
                    continue
                c0 = x in (0, sx - 1) and z in (0, sz - 1)
                c1 = x in (1, sx - 2) and z in (1, sz - 2)
                r0 = x in (0, sx - 1) or z in (0, sz - 1)
                r1 = x in (1, sx - 2) or z in (1, sz - 2)
                if c0 or c1:
                    st = ctx["accent"]
                elif r0 or r1:
                    st = ctx["wall"]
                else:
                    st = _AIR
                g.set(x, y, z, st)
    # порты: проём прорезаем и во втором кольце стен
    half = W // 2
    for face in rng.sample(_FACES, rng.randint(1, 2)):
        lo = 1 + W // 2
        hi = (sz if face in ("west", "east") else sx) - 2 - W // 2
        along = rng.randint(lo, hi)
        _carve_side_port(rng, g, ctx, face, 0, along,
                         ctx["side_pool"]["treasury"])
        if face in ("west", "east"):
            fx2 = 1 if face == "west" else sx - 2
            for z in range(along - half, along + half + 1):
                for y in range(1, H + 1):
                    g.set(fx2, y, z, _AIR)
        else:
            fz2 = 1 if face == "north" else sz - 2
            for x in range(along - half, along + half + 1):
                for y in range(1, H + 1):
                    g.set(x, y, fz2, _AIR)
    # сокровища: гарантированные 1-2 сундука/волта по углам интерьера
    spots = [(2, 2), (sx - 3, sz - 3), (2, sz - 3), (sx - 3, 2)]
    rng.shuffle(spots)
    for (x, z) in spots[:rng.randint(1, 2)]:
        if rng.random() < 0.40:
            _add_vault_solo(rng, g, ctx, (x, 1, z))
        else:
            _add_chest(rng, g, ctx, (x, 1, z))
    for (x, z) in spots[2:]:                # декоративные блоки
        if rng.random() < 0.5:
            g.set(x, 1, z, ctx["accent"])
    if rng.random() < 0.50:                 # свет в крыше
        g.set(sx // 2, h - 1, sz // 2, ctx["light"])
    sp = rng.random() < 0.08                # редкий страж
    if sp:
        _add_spawner(rng, g, (sx // 2, 1, sz // 2))
    elif rng.random() < 0.20:
        _add_mob(rng, ctx, entities, (sx // 2, 1, sz // 2))
    return g, entities


def _build_greenhouse(rng, ctx):
    """greenhouse: оранжерея — стеклянная крыша (сетка рам + стекло),
    2-4 подставки с растениями (пьедестал из акцента + растение — все
    id сверены с реестром 26.2), мох на полу, изредка споре-блоссом под
    крышей."""
    W, H = ctx["W"], ctx["H"]
    sx, sz = rng.randint(9, 13), rng.randint(7, 11)
    h = max(rng.randint(5, 7), H + 2)
    g = _Grid(sx, h, sz)
    _shell_room(rng, g, ctx, windows=True)
    entities = []
    # стеклянная крыша: рамы сеткой + стекло
    for x in range(sx):
        for z in range(sz):
            if x % 3 == 0 or z % 3 == 0 or x in (0, sx - 1) \
                    or z in (0, sz - 1):
                g.set(x, h - 1, z, ctx["frame"])
            else:
                g.set(x, h - 1, z, _GLASS)
    for face in rng.sample(_FACES, rng.randint(1, 2)):
        lo = 1 + W // 2
        hi = (sz if face in ("west", "east") else sx) - 2 - W // 2
        _carve_side_port(rng, g, ctx, face, 0, rng.randint(lo, hi),
                         ctx["side_pool"]["greenhouse"])
    free = _interior_free(g, 0)
    _decor_room(rng, g, ctx, entities, 0, free,
                chest_n=rng.randint(0, 1), torch_n=rng.randint(0, 2),
                mob_p=0.15, spawner_p=0.04)
    # подставки с растениями
    for _ in range(rng.randint(2, 4)):
        if not free:
            break
        x, y, z = free.pop()
        g.set(x, y, z, ctx["accent"])
        if rng.random() < 0.85:
            g.set(x, y + 1, z, rng.choice(_GREEN_PLANTS))
    # мох по полу
    for x in range(1, sx - 1):
        for z in range(1, sz - 1):
            cell = g.get(x, 1, z)
            if (cell is None or cell[0] is _AIR or cell[0] == _AIR) \
                    and rng.random() < 0.12:
                g.set(x, 1, z, rng.choice(_MOSS_CARPETS))
    # споре-блоссом под крышей
    if rng.random() < 0.5:
        for _ in range(rng.randint(1, 2)):
            g.set(rng.randint(1, sx - 2), h - 2, rng.randint(1, sz - 2),
                  _SPORE_BLOSSOM)
    return g, entities


def _build_mausoleum(rng, ctx):
    """mausoleum: мавзолей — зал без окон, колонны вдоль стен (шаг 2),
    саркофаг в центре (акцент-база + рамка + ступени по бокам +
    свеча), приглушённый свет — глоустоун-точки в полу по углам."""
    W, H = ctx["W"], ctx["H"]
    sx, sz = rng.randint(9, 13), rng.randint(7, 11)
    h = max(rng.randint(5, 7), H + 2)
    g = _Grid(sx, h, sz)
    _shell_room(rng, g, ctx, windows=False)
    entities = []
    for face in rng.sample(_FACES, rng.randint(1, 2)):
        lo = 1 + W // 2
        hi = (sz if face in ("west", "east") else sx) - 2 - W // 2
        _carve_side_port(rng, g, ctx, face, 0, rng.randint(lo, hi),
                         ctx["side_pool"]["mausoleum"])
    if ctx["has_vertical"] and rng.random() < 0.15:
        _room_ceiling_port(rng, g, ctx)
    # колонны вдоль стен
    for x in range(3, sx - 3, 2):
        for y in range(1, h - 1):
            g.set(x, y, 1, ctx["accent"])
            g.set(x, y, sz - 2, ctx["accent"])
    for z in range(3, sz - 3, 2):
        for y in range(1, h - 1):
            g.set(1, y, z, ctx["accent"])
            g.set(sx - 2, y, z, ctx["accent"])
    # саркофаг в центре
    cx, cz = sx // 2, sz // 2
    g.set(cx, 1, cz, ctx["accent"])
    g.set(cx, 2, cz, ctx["frame"])
    for (dx, dz, fc) in ((1, 0, "east"), (-1, 0, "west"),
                         (0, 1, "south"), (0, -1, "north")):
        g.set(cx + dx, 1, cz + dz, _stairs_state(rng, fc))
    if rng.random() < 0.6:
        g.set(cx, 3, cz, _CANDLE_LIT)
    # приглушённый свет: точки в полу
    for (px, pz) in ((2, 2), (sx - 3, 2), (2, sz - 3), (sx - 3, sz - 3)):
        if rng.random() < 0.6:
            g.set(px, 0, pz, ctx["light"])
    free = _interior_free(g, 0)
    _decor_room(rng, g, ctx, entities, 0, free,
                chest_n=rng.randint(0, 1), torch_n=rng.randint(0, 1),
                mob_p=0.30, spawner_p=0.08)
    return g, entities


def _build_chainbridge(rng, ctx):
    """chainbridge: подвесной мост — палуба с перилами, пилоны на
    концах (высота 4-6), «цепи» из блоков палитры: парабола от вершины
    одного пилона через провис к другому; свет — glowstone/sea_lantern/
    shroomlight в цепях каждые 3 клетки (латерн — не из палитры).
    Порты с концов, как у bridge."""
    W, H = ctx["W"], ctx["H"]
    length = rng.randint(7, 12)
    pt = rng.randint(4, 6)                # высота пилонов над палубой
    sag = rng.randint(2, 3)               # провис цепей
    h = max(pt + 2, H + 2)
    along_x = rng.random() < 0.5
    sx, sz = (length, W + 2) if along_x else (W + 2, length)
    g = _Grid(sx, h, sz)
    entities = []
    mid = (length - 1) / 2.0
    halfspan = max(1.0, (length - 3) / 2.0)
    # палуба
    for i in range(length):
        for j in range(W + 2):
            if along_x:
                g.set(i, 0, j, ctx["floor"])
            else:
                g.set(j, 0, i, ctx["floor"])
    # пилоны (по краям палубы на концах)
    for p in (1, length - 2):
        for edge in (0, W + 1):
            for y in range(1, pt + 1):
                st = ctx["accent"] if y == pt else ctx["frame"]
                if along_x:
                    g.set(p, y, edge, st)
                else:
                    g.set(edge, y, p, st)
    # цепи-параболы + перила
    for i in range(1, length - 1):
        cy = pt - round(sag * (1.0 - ((i - mid) / halfspan) ** 2))
        for edge in (0, W + 1):
            if i in (1, length - 2):
                continue                      # там пилоны
            st = ctx["accent"]
            if i % 3 == 0:
                st = ctx["light"]            # фонари в цепи
            if 1 <= cy <= h - 1:
                if along_x:
                    g.set(i, cy, edge, st)
                else:
                    g.set(edge, cy, i, st)
            if 2 <= i <= length - 3:          # перила палубы
                if along_x:
                    g.set(i, 1, edge, ctx["frame"])
                else:
                    g.set(edge, 1, i, ctx["frame"])
    if along_x:
        for face in ("west", "east"):
            _carve_side_port(rng, g, ctx, face, 0, sz // 2,
                             ctx["side_pool"]["chainbridge"])
    else:
        for face in ("north", "south"):
            _carve_side_port(rng, g, ctx, face, 0, sx // 2,
                             ctx["side_pool"]["chainbridge"])
    if rng.random() < 0.08:
        _add_chest(rng, g, ctx, (sx // 2, 1, sz // 2))
    if rng.random() < 0.04:
        _add_mob(rng, ctx, entities, (sx // 2, 1, sz // 2))
    return g, entities


def _build_ruins(rng, ctx):
    """ruins: полуразрушенная комната — рваные стены (у каждой колонки
    периметра случайная высота + поклеточная эрозия), крыша либо
    снесена (70%), либо фрагменты; сломанные колонны и обломки внутри.
    Порты прорезаются ПОСЛЕ разрушения — проёмы гарантированы."""
    W, H = ctx["W"], ctx["H"]
    sx, sz = rng.randint(9, 15), rng.randint(9, 15)
    h = max(rng.randint(4, 6), H + 2)
    g = _Grid(sx, h, sz)
    _shell_room(rng, g, ctx, windows=False)
    entities = []
    # крыша: 70% снос целиком, иначе фрагменты
    roof_p = 0.0 if rng.random() < 0.7 else 0.35
    for x in range(sx):
        for z in range(sz):
            if rng.random() > roof_p:
                g.set(x, h - 1, z, _AIR)
    # стены: рваные высоты + эрозия
    for x in range(sx):
        for z in range(sz):
            if not (x in (0, sx - 1) or z in (0, sz - 1)):
                continue
            if rng.random() < 0.45:
                col_h = rng.randint(0, h - 2)
                for y in range(1, h - 1):
                    if y > col_h or (y > 1 and rng.random() < 0.12):
                        g.set(x, y, z, _AIR)
            else:
                for y in range(2, h - 1):
                    if rng.random() < 0.10:
                        g.set(x, y, z, _AIR)
    # сломанные колонны внутри
    for _ in range(rng.randint(2, 5)):
        px, pz = rng.randint(2, sx - 3), rng.randint(2, sz - 3)
        for y in range(1, 1 + rng.randint(1, 3)):
            g.set(px, y, pz, ctx["accent"])
    # обломки на полу
    for _ in range(rng.randint(2, 6)):
        px, pz = rng.randint(1, sx - 2), rng.randint(1, sz - 2)
        if g.get(px, 1, pz) is None or g.get(px, 1, pz)[0] == _AIR \
                or g.get(px, 1, pz)[0] is _AIR:
            g.set(px, 1, pz, ctx["frame"])
    # порты — после разрушения
    for face in rng.sample(_FACES, rng.randint(1, 3)):
        lo = 1 + W // 2
        hi = (sz if face in ("west", "east") else sx) - 2 - W // 2
        _carve_side_port(rng, g, ctx, face, 0, rng.randint(lo, hi),
                         ctx["side_pool"]["ruins"])
    free = _interior_free(g, 0)
    _decor_room(rng, g, ctx, entities, 0, free,
                chest_n=rng.randint(0, 2), torch_n=rng.randint(0, 2),
                mob_p=0.30, spawner_p=0.08)
    return g, entities


def _build_labyrinth(rng, ctx):
    """labyrinth: сегмент лабиринта 11-15 — идеальный DFS-лабиринт
    (recursive backtracker: связность ВСЕХ клеток гарантирована, тупики
    возникают сами), коридоры шириной 1, стены толщиной 1; крыша 50%.
    Порты на 2 гранях по линиям клеток; клад/спавнер — ТОЛЬКО в тупиках
    (не на сквозном пути между портами)."""
    W, H = ctx["W"], ctx["H"]
    s = rng.choice([11, 13, 15])
    ncell = (s - 1) // 2
    h = H + 2
    has_roof = rng.random() < 0.5
    g = _Grid(s, h, s)
    entities = []
    # DFS-лабиринт
    visited = [[False] * ncell for _ in range(ncell)]
    opened = set()
    stack = [(0, 0)]
    visited[0][0] = True
    while stack:
        ci, cj = stack[-1]
        nbrs = []
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ni, nj = ci + di, cj + dj
            if 0 <= ni < ncell and 0 <= nj < ncell \
                    and not visited[nj][ni]:
                nbrs.append((ni, nj))
        if not nbrs:
            stack.pop()
            continue
        ni, nj = rng.choice(nbrs)
        visited[nj][ni] = True
        opened.add(frozenset(((ci, cj), (ni, nj))))
        stack.append((ni, nj))

    def is_open(x, z):
        if x in (0, s - 1) or z in (0, s - 1):
            return False                       # внешняя стена
        if x % 2 == 1 and z % 2 == 1:
            return True                        # клетка лабиринта
        if x % 2 == 0 and z % 2 == 1:          # стена (i-1,j)|(i,j)
            i, j = x // 2, (z - 1) // 2
            return frozenset(((i - 1, j), (i, j))) in opened
        if x % 2 == 1 and z % 2 == 0:          # стена (i,j-1)|(i,j)
            i, j = (x - 1) // 2, z // 2
            return frozenset(((i, j - 1), (i, j))) in opened
        return False                           # столб (обе чётные)

    for x in range(s):
        for z in range(s):
            g.set(x, 0, z, ctx["floor"])
            if has_roof:
                g.set(x, h - 1, z, ctx["floor"])
            st = _AIR if is_open(x, z) else ctx["wall"]
            for y in range(1, h - 1):
                g.set(x, y, z, st)
    for (px, pz) in ((0, 0), (s - 1, 0), (0, s - 1), (s - 1, s - 1)):
        for y in range(1, h - 1):
            g.set(px, y, pz, ctx["accent"])
    # порты на 2 гранях — по линиям клеток (нечётные)
    lo, hi = 1 + W // 2, s - 2 - W // 2
    rows = [v for v in range(1, s - 1) if v % 2 == 1 and lo <= v <= hi]
    entrance = set()
    for face in rng.sample(_FACES, 2):
        along = rng.choice(rows)
        _carve_side_port(rng, g, ctx, face, 0, along,
                         ctx["side_pool"]["labyrinth"])
        if face == "west":
            entrance.add((1, along))
        elif face == "east":
            entrance.add((s - 2, along))
        elif face == "north":
            entrance.add((along, 1))
        else:
            entrance.add((along, s - 2))
    # тупики (<= 1 открытая стена) — туда клад/спавнер (не вход!)
    dead = []
    for i in range(ncell):
        for j in range(ncell):
            sides = 0
            for (di, dj) in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ni, nj = i + di, j + dj
                if 0 <= ni < ncell and 0 <= nj < ncell \
                        and frozenset(((i, j), (ni, nj))) in opened:
                    sides += 1
            if sides <= 1:
                cell = (2 * i + 1, 2 * j + 1)
                if cell not in entrance:
                    dead.append(cell)
    rng.shuffle(dead)
    if dead and rng.random() < 0.45:
        x, z = dead.pop()
        _add_chest(rng, g, ctx, (x, 1, z))
    if dead and rng.random() < 0.12:
        x, z = dead.pop()
        _add_spawner(rng, g, (x, 1, z))
    # факелы/мобы по коридорам (факелы не блокируют; мебель — нельзя:
    # коридор шириной 1)
    free = _interior_free(g, 0)
    _decor_room(rng, g, ctx, entities, 0, free,
                chest_n=0, torch_n=rng.randint(1, 3),
                mob_p=0.15, spawner_p=0.0, furniture=False)
    return g, entities


def _build_observatory(rng, ctx):
    """observatory: башня-обсерватория — круглый корпус 7-11, наверху
    КРУГЛАЯ площадка с перилами (зубцы через 2) и «телескопом»
    (столб-рамка + акцент-блок), внутренняя лестница сквозь дыру в
    площадке. Порты внизу (1-2). Терминальная сверху (телескоп)."""
    W, H = ctx["W"], ctx["H"]
    s = rng.choice([7, 9, 11])
    c = s // 2
    h = rng.randint(8, max(9, ctx["max_tower_h"] - 3))
    sy = h + 3
    g = _Grid(s, sy, s)
    entities = []
    r2 = (s / 2.0) ** 2

    def inside(x, z):
        return (x - c) ** 2 + (z - c) ** 2 <= r2

    def on_edge(x, z):
        return inside(x, z) and not (inside(x + 1, z) and inside(x - 1, z)
                                     and inside(x, z + 1)
                                     and inside(x, z - 1))

    # корпус + площадка-крыша
    for x in range(s):
        for z in range(s):
            if not inside(x, z):
                continue
            g.set(x, 0, z, ctx["floor"])
            g.set(x, h - 1, z, ctx["floor"])
            for y in range(1, h - 1):
                if on_edge(x, z):
                    if 3 <= y <= h - 4 and rng.random() < 0.05:
                        continue                # бойницы
                    g.set(x, y, z, ctx["wall"])
    # порты (1-2)
    port_span = {}
    for face in rng.sample(_FACES, rng.randint(1, 2)):
        lo = 1 + W // 2
        hi = s - 2 - W // 2
        along = rng.randint(lo, hi)
        _carve_side_port(rng, g, ctx, face, 0, along,
                         ctx["side_pool"]["observatory"])
        port_span[face] = along
    # лестница: грань без порта (или позиция вне проёма), до площадки
    _lad_face_of = {"west": "east", "east": "west",
                    "north": "south", "south": "north"}
    lx = lz = lface = None
    for face in rng.sample(_FACES, len(_FACES)):
        span = port_span.get(face)
        cands = []
        for v in range(1, s - 1):
            if face == "west" and inside(1, v) and inside(0, v):
                cell = (1, v)
            elif face == "east" and inside(s - 2, v) and inside(s - 1, v):
                cell = (s - 2, v)
            elif face == "north" and inside(v, 1) and inside(v, 0):
                cell = (v, 1)
            elif face == "south" and inside(v, s - 2) and inside(v, s - 1):
                cell = (v, s - 2)
            else:
                continue
            if span is not None and abs(v - span) <= W // 2 + 1:
                continue                       # не в проёме порта
            cands.append(cell)
        if cands:
            lx, lz = rng.choice(cands)
            lface = face
            break
    if lx is not None:
        for y in range(1, h):
            if lface == "west":
                g.set(0, y, lz, ctx["wall"])
            elif lface == "east":
                g.set(s - 1, y, lz, ctx["wall"])
            elif lface == "north":
                g.set(lx, y, 0, ctx["wall"])
            else:
                g.set(lx, y, s - 1, ctx["wall"])
            g.set(lx, y, lz, _ladder(_lad_face_of[lface]))
        # перила по краю площадки (через 2, не у выхода лестницы)
        for x in range(s):
            for z in range(s):
                if on_edge(x, z) and (x + z) % 2 == 0 \
                        and abs(x - lx) + abs(z - lz) > 1:
                    g.set(x, h, z, ctx["frame"])
    # телескоп: столб + акцент
    g.set(c, h, c, ctx["frame"])
    g.set(c, h + 1, c, ctx["frame"])
    g.set(c, h + 2, c, ctx["accent"])
    if rng.random() < 0.40:
        g.set(c + 1, h, c + 1, ctx["light"])
    # сундук на площадке
    if rng.random() < 0.40 and inside(c + 1, c):
        _add_chest(rng, g, ctx, (c + 1, h, c))
    # декор первого этажа
    in_cells = [(x, z) for x in range(1, s - 1) for z in range(1, s - 1)
                if inside(x, z) and not on_edge(x, z)]
    if in_cells and rng.random() < 0.20:
        x, z = rng.choice(in_cells)
        _add_chest(rng, g, ctx, (x, 1, z))
    if in_cells and rng.random() < 0.30:
        x, z = rng.choice(in_cells)
        g.set(x, 1, z, _LANTERN if rng.random() < 0.3 else _TORCH)
    if in_cells and rng.random() < 0.05:
        x, z = rng.choice(in_cells)
        _add_mob(rng, ctx, entities, (x, 1, z))
    return g, entities


def _build_kitchen(rng, ctx):
    """kitchen: кухня — очаг-костёр у стены, 1-2 котла (пустой/с водой/
    с лавой — блоки без BE, как и cauldron), дымарь (front в комнату),
    поленница-сено. Полные блоки-декор без BE, кроме штучных печей."""
    W, H = ctx["W"], ctx["H"]
    sx, sz = rng.randint(7, 11), rng.randint(7, 9)
    h = max(rng.randint(4, 5), H + 2)
    g = _Grid(sx, h, sz)
    _shell_room(rng, g, ctx, windows=True)
    entities = []
    for face in rng.sample(_FACES, rng.randint(1, 2)):
        lo = 1 + W // 2
        hi = (sz if face in ("west", "east") else sx) - 2 - W // 2
        _carve_side_port(rng, g, ctx, face, 0, rng.randint(lo, hi),
                         ctx["side_pool"]["kitchen"])
    if ctx["has_vertical"] and rng.random() < 0.10:
        _room_ceiling_port(rng, g, ctx)
    # очаг-костёр (не вплотную к стене — тлеет безопасно)
    if rng.random() < 0.7:
        g.set(rng.randint(2, sx - 3), 1, 2,
              {"Name": "minecraft:campfire",
               "Properties": {"facing": rng.choice(
                   ("north", "south", "east", "west")),
                   "lit": "true" if rng.random() < 0.7 else "false",
                   "signal_fire": "false", "waterlogged": "false"}})
    # котлы 1-2 (вода — с уровнем, иначе рендер пустого)
    for _ in range(rng.randint(1, 2)):
        x, z = rng.randint(1, sx - 2), rng.randint(1, sz - 2)
        cell = g.get(x, 1, z)
        if cell is not None and cell[0] is not _AIR and cell[0] != _AIR:
            continue
        r = rng.random()
        if r < 0.4:
            st = {"Name": "minecraft:cauldron"}
        elif r < 0.8:
            st = {"Name": "minecraft:water_cauldron",
                  "Properties": {"level": str(rng.randint(1, 3))}}
        else:
            st = {"Name": "minecraft:lava_cauldron"}
        g.set(x, 1, z, st)
    # дымарь у южной стены + сено
    if rng.random() < 0.6:
        g.set(rng.randint(2, sx - 3), 1, sz - 2,
              _furnace_state(rng, "minecraft:smoker", "north"))
    if rng.random() < 0.5:
        g.set(1, 1, sz - 2, {"Name": "minecraft:hay_block",
                             "Properties": {"axis": "y"}})
        if rng.random() < 0.4:
            g.set(1, 2, sz - 2, {"Name": "minecraft:hay_block",
                                 "Properties": {"axis": "y"}})
    free = _interior_free(g, 0)
    _decor_room(rng, g, ctx, entities, 0, free,
                chest_n=rng.randint(0, 2), torch_n=rng.randint(0, 2),
                mob_p=0.20, spawner_p=0.06)
    return g, entities


def _build_mine(rng, ctx):
    """mine: колодец-шахта — закрытая шахта ПОД комнатой (как pit, но
    индустриальная): прямая лестница у стены, рудные кластеры в стенах
    (2-3 сорта на шахту), крепёжные кольца из рамки каждые 4. Вход —
    порт в крыше (терминальный; дёргается пол-портами комнат через
    pbase)."""
    s = rng.choice([5, 7])
    h = rng.randint(8, ctx["max_tower_h"])
    g = _Grid(s, h, s)
    entities = []
    for x in range(s):
        for y in range(h):
            for z in range(s):
                edge = x in (0, s - 1) or z in (0, s - 1)
                if y in (0, h - 1):
                    st = ctx["floor"]
                elif edge:
                    st = ctx["wall"]
                else:
                    st = _AIR
                g.set(x, y, z, st)
    # руды (до лестницы — опору не трогаем)
    ores = rng.sample(_MINE_ORES, rng.randint(2, 3))
    for x in range(s):
        for z in range(s):
            if not (x in (0, s - 1) or z in (0, s - 1)):
                continue
            if rng.random() < 0.35:            # рудная колонка-кластер
                ore = rng.choice(ores)
                for y in range(2, h - 2):
                    if rng.random() < 0.6:
                        g.set(x, y, z, {"Name": ore})
    # крепёжные кольца
    for y in range(4, h - 2, 4):
        for x in range(s):
            for z in range(s):
                if x in (0, s - 1) or z in (0, s - 1):
                    g.set(x, y, z, ctx["frame"])
    c = s // 2
    for y in range(1, h - 1):
        g.set(0, y, c, ctx["wall"])            # опора лестницы
        g.set(1, y, c, _ladder("east"))
    _carve_up_port(rng, g, ctx, 1, c, "minecraft:empty")
    if rng.random() < 0.6:
        g.set(1, 2, 1, ctx["light"])
    if rng.random() < 0.4:
        g.set(s - 2, h - 3, s - 2, ctx["light"])
    free = _interior_free(g, 0)
    _decor_room(rng, g, ctx, entities, 0, free,
                chest_n=1 if rng.random() < 0.55 else 0,
                torch_n=0, mob_p=0.25, spawner_p=0.10, furniture=False)
    return g, entities


_BUILDERS = {
    "start": _build_start_room,
    "room": _build_room,
    "corridor": _build_corridor,
    "bridge": _build_bridge,
    "stairs": _build_stairs,
    "tower": _build_tower,
    "tower_top": _build_tower_top,
    "gate": _build_gate,
    "courtyard": _build_courtyard,
    "spire": _build_spire,
    "terrace": _build_terrace,
    "pit": _build_pit,
    "viaduct": _build_viaduct,
    "rotunda": _build_rotunda,
    "arena": _build_arena,
    "workshop": _build_workshop,
    "treasury": _build_treasury,
    "greenhouse": _build_greenhouse,
    "mausoleum": _build_mausoleum,
    "chainbridge": _build_chainbridge,
    "ruins": _build_ruins,
    "labyrinth": _build_labyrinth,
    "observatory": _build_observatory,
    "kitchen": _build_kitchen,
    "mine": _build_mine,
    "cap": _build_cap,
}

# Сколько кусков на роль (start всегда 1)
_PIECE_COUNTS = {"room": (2, 6), "corridor": (2, 6), "tower": (2, 6),
                 "bridge": (2, 6), "stairs": (2, 6), "tower_top": (1, 3),
                 "gate": (1, 3), "courtyard": (1, 3), "spire": (1, 3),
                 "terrace": (1, 4), "pit": (1, 2), "viaduct": (1, 3),
                 "rotunda": (1, 2), "arena": (1, 2), "workshop": (1, 3),
                 "treasury": (1, 3), "greenhouse": (1, 3),
                 "mausoleum": (1, 2), "chainbridge": (1, 3),
                 "ruins": (1, 3), "labyrinth": (1, 2),
                 "observatory": (1, 2), "kitchen": (1, 3),
                 "mine": (1, 2), "cap": (2, 6)}


# ---------------------------------------------------------------------------
# Одна jigsaw-структура
# ---------------------------------------------------------------------------

def _rand_spawn_overrides(rng):
    """Консервативные spawn_overrides (живность редкая): 60% пусто, иначе
    1-2 моба с minCount 1, maxCount 2, bounding_box piece."""
    if rng.random() < 0.6:
        return {}
    cat = "monster" if rng.random() < 0.7 else "creature"
    k = rng.randint(1, 2)
    spawns = []
    for etype in rng.sample(STRUCTURE_MOBS_LIST, k):
        spawns.append({"type": "minecraft:" + etype,
                       "weight": rng.randint(1, 10),
                       "minCount": 1, "maxCount": 2})
    return {cat: {"bounding_box": "piece", "spawns": spawns}}


# безвредные для структур мобы (подмножество gen_structures.STRUCTURE_MOBS;
# импорт на уровне модуля — чтобы не тянуть gen_structures в шапку дважды)
STRUCTURE_MOBS_LIST = None


def _init_mobs():
    global STRUCTURE_MOBS_LIST
    if STRUCTURE_MOBS_LIST is None:
        import gen_structures
        STRUCTURE_MOBS_LIST = list(gen_structures.STRUCTURE_MOBS)



JIGSAW_ARCHETYPES = {
    "citadel": {
        "roles": ["gate", "courtyard", "tower", "viaduct", "arena", "workshop", "treasury"],
        "terrain_adaptation": "beard_thin",
        "step": "surface_structures",
    },
    "sanctuary": {
        "roles": ["rotunda", "courtyard", "spire", "terrace", "greenhouse"],
        "terrain_adaptation": "beard_box",
        "step": "surface_structures",
    },
    "dungeon_keep": {
        "roles": ["pit", "labyrinth", "treasury", "workshop", "stairs", "corridor"],
        "terrain_adaptation": "encapsulate",
        "step": "underground_structures",
    },
    "observatory_tower": {
        "roles": ["stairs", "tower", "observatory", "terrace", "corridor"],
        "terrain_adaptation": "beard_thin",
        "step": "surface_structures",
    },
    "undercity_mine": {
        "roles": ["mine", "corridor", "pit", "workshop", "ruins"],
        "terrain_adaptation": "none",
        "step": "underground_structures",
    },
    "necropolis": {
        "roles": ["mausoleum", "labyrinth", "pit", "corridor", "ruins"],
        "terrain_adaptation": "bury",
        "step": "underground_structures",
    },
    "sky_viaduct": {
        "roles": ["viaduct", "bridge", "chainbridge", "terrace", "tower"],
        "terrain_adaptation": "none",
        "step": "surface_structures",
    },
    "sunken_ruins": {
        "roles": ["ruins", "courtyard", "gate", "pit", "corridor"],
        "terrain_adaptation": "bury",
        "step": "surface_structures",
    },
    "botanical_greenhouse": {
        "roles": ["greenhouse", "courtyard", "terrace", "corridor", "room"],
        "terrain_adaptation": "beard_thin",
        "step": "surface_structures",
    },
    "grand_palace": {
        "roles": ["courtyard", "room", "workshop", "kitchen", "treasury", "stairs", "gate"],
        "terrain_adaptation": "beard_box",
        "step": "surface_structures",
    },
}

def _rand_jigsaw_one(rng, ns, name, num, min_y, max_y, biome_ids,
                     loot_alloc, result, has_ceiling=False, roof_bottom=None, palette=None):
    gd = _gd()
    # палитра — ТОЛЬКО безопасные для массовой заливки кубы
    # (gd.PALETTE_BLOCKS: без block entity — spawner/trial_spawner/vault/
    # chest/furnace/... и без «живородящих» вроде sniffer_egg — стены
    # данжа из block-entity блоков сильно грузят FPS). Фильтр _mob_risk
    # оставлен как защита: spawner без NBT спавнит дефолтных свиней,
    # jigsaw замещается final_state = дыры.
    _mob_risk = {"minecraft:spawner", "minecraft:trial_spawner",
                 "minecraft:vault", "minecraft:sniffer_egg",
                 "minecraft:jigsaw"}
    solid = [b for b in gd.PALETTE_BLOCKS if b[0] not in _mob_risk]

    base = "%s/jig%d" % (name, num)                  # путь кусков в structure/
    jid = "%s_jig%d" % (name, num)                   # суффикс id структуры

    # --- профиль проёма и палитра (одни на всю структуру) ---
    # use_expansion_hack решаем ЗАРАНЕЕ: при hack=true движок отвергает
    # дочерние куски с YSpan > 16 (JigsawPlacement) — башни ужимаем до 16
    use_hack = rng.random() < 0.5
    ctx = {
        "W": rng.choice([3, 5]),
        "H": rng.choice([2, 3, 4]),
        "loot_alloc": loot_alloc,
        "solid": solid,                              # фильтрованная палитра
        "max_tower_h": 16 if use_hack else 24,
    }
    from gen_structures import _get_native_blocks
    native = [b for b in _get_native_blocks(palette) if b[0] not in _mob_risk]
    def _pick_mat():
        return gd.block_state(rng.choice(native if rng.random() < 0.85 else solid))
    ctx["floor"] = _pick_mat()
    ctx["wall"] = _pick_mat()
    ctx["accent"] = _pick_mat()
    ctx["frame"] = _pick_mat()
    ctx["light"] = rng.choice(_LIGHT_BLOCKS)       # светокуб без BE
    ctx["floor_str"] = _state_str(ctx["floor"])
    ctx["ladder_str"] = _state_str(_ladder("east"))

    # --- роли ---
    archetype_keys = list(JIGSAW_ARCHETYPES.keys())
    pref_adapt = None
    pref_step = None
    if rng.random() < 0.75:
        chosen_arch = rng.choice(archetype_keys)
        arch_data = JIGSAW_ARCHETYPES[chosen_arch]
        core_cands = arch_data["roles"]
        n_roles = rng.randint(4, min(9, len(core_cands) + 2))
        core = rng.sample(core_cands, min(len(core_cands), n_roles - 2))
        pref_adapt = arch_data.get("terrain_adaptation")
        pref_step = arch_data.get("step")
    else:
        n_roles = rng.randint(4, 9)
        core = rng.sample(_CORE_ROLES, min(len(_CORE_ROLES), n_roles - 2))
    if "room" not in core and "corridor" not in core:
        core.append("room")                          # гарантия связности
    roles = ["start", "cap"] + core
    ctx["has_tower"] = "tower" in core
    ctx["has_spire"] = "spire" in core
    ctx["has_pit"] = "pit" in core
    ctx["has_mine"] = "mine" in core
    # вертикаль ВНИЗ: колодцы (pit) и шахты (mine) — общий пул pbase
    ctx["has_down"] = ctx["has_pit"] or ctx["has_mine"]
    # вертикаль ВВЕРХ — общие пулы у башен и шпилей (tbase/tchain)
    ctx["has_vertical"] = ctx["has_tower"] or ctx["has_spire"]

    # ключи портов (name==target)
    ctx["port_key"] = "%s:%s/port" % (ns, base)
    ctx["vport_key"] = "%s:%s/vport" % (ns, base)
    ctx["anchor_key"] = "%s:%s/anchor" % (ns, base)

    # --- имена кусков (нужны пулам до построения геометрии) ---
    # порядок обхода детерминированный (никаких set-итераций — иначе порядок
    # расхода rng зависит от хэшей строк и воспроизводимость ломается)
    all_roles = list(roles)
    if ctx["has_vertical"] and "tower_top" not in all_roles:
        all_roles.append("tower_top")
    pieces = {}                                      # role -> [nbt-ключи]
    for role in all_roles:
        if role == "start":
            keys = ["%s/start" % base]
        else:
            lo, hi = _PIECE_COUNTS[role]
            keys = ["%s/%s%d" % (base, role, i + 1)
                    for i in range(rng.randint(lo, hi))]
        pieces[role] = keys

    # --- пулы ---
    proc_id = "%s:%s/proc" % (ns, base)
    result["processor_lists"][proc_id] = _rand_proc_list(rng, ctx)

    def _elements(role_keys, weight_scale=(1, 3)):
        els = []
        for key in role_keys:
            els.append({
                "element": {
                    "element_type": "minecraft:single_pool_element",
                    "location": "%s:%s" % (ns, key),
                    "processors": (proc_id if rng.random() < 0.4
                                   else "minecraft:empty"),
                    "projection": "rigid"},
                "weight": rng.randint(*weight_scale)})
        return els

    # пул старта (1 кусок — проверка граничного случая «пул из 1 куска»)
    start_pool = "%s:%s/start" % (ns, base)
    result["template_pools"][start_pool] = {
        "elements": _elements(pieces["start"]), "fallback": "minecraft:empty"}

    # боковые пулы по матрице связей
    ctx["side_pool"] = {}
    present = set(roles)
    alias_bindings = []
    for role in _SIDE_ROLES:
        if role not in present:
            continue
        cands = [(r, w) for r, w in _SIDE_MATRIX[role]
                 if r in present or r == "cap"]
        if not cands:
            cands = [("cap", 3)]
        k = rng.randint(2, min(4, len(cands)))
        chosen = _weighted_sample(rng, cands, k)
        els = []
        for s, w in chosen:
            for key in pieces[s]:
                els.append({
                    "element": {
                        "element_type": "minecraft:single_pool_element",
                        "location": "%s:%s" % (ns, key),
                        "processors": (proc_id if rng.random() < 0.4
                                       else "minecraft:empty"),
                        "projection": "rigid"},
                    "weight": w * rng.randint(1, 3)})
        pid = "%s:%s/ps_%s" % (ns, base, role)
        result["template_pools"][pid] = {"elements": els,
                                         "fallback": "minecraft:empty"}
        # pool_aliases (иногда): куски роли дёргают алиас, а не пул напрямую
        if rng.random() < 0.15:
            alias_id = "%s:%s/pa_%s" % (ns, base, role)
            alias_bindings.append({
                "type": "minecraft:direct",
                "alias": alias_id, "target": pid})
            ctx["side_pool"][role] = alias_id
        else:
            ctx["side_pool"][role] = pid

    # вертикальные пулы: ВВЕРХ — башни и/или шпили (общие tbase/tchain,
    # завершает цепочку tower_top), ВНИЗ — колодцы и шахты (pbase дёргают
    # пол-порты комнат/двориков)
    if ctx["has_vertical"]:
        ctx["tbase_pool"] = "%s:%s/tbase" % (ns, base)
        base_els = []
        if ctx["has_tower"]:
            base_els += _elements(pieces["tower"])
        if ctx["has_spire"]:
            base_els += _elements(pieces["spire"])
        result["template_pools"][ctx["tbase_pool"]] = {
            "elements": base_els, "fallback": "minecraft:empty"}
        ctx["tchain_pool"] = "%s:%s/tchain" % (ns, base)
        chain_els = []
        if ctx["has_tower"]:
            chain_els += _elements(pieces["tower"], (1, 2))
        if ctx["has_spire"]:
            chain_els += _elements(pieces["spire"], (1, 2))
        for el in _elements(pieces["tower_top"], (3, 5)):
            chain_els.append(el)
        result["template_pools"][ctx["tchain_pool"]] = {
            "elements": chain_els, "fallback": "minecraft:empty"}
    if ctx["has_down"]:
        ctx["pbase_pool"] = "%s:%s/pbase" % (ns, base)
        down_els = []
        if ctx["has_pit"]:
            down_els += _elements(pieces["pit"])
        if ctx["has_mine"]:
            down_els += _elements(pieces["mine"])
        result["template_pools"][ctx["pbase_pool"]] = {
            "elements": down_els, "fallback": "minecraft:empty"}

    # --- геометрия кусков ---
    for role, keys in pieces.items():
        for key in keys:
            g, entities = _BUILDERS[role](rng, ctx)
            assert g.sx <= 16 and g.sy <= 24 and g.sz <= 16, \
                "кусок %s больше 16x24x16: %dx%dx%d" % (
                    key, g.sx, g.sy, g.sz)
            result["nbt_files"][key] = _export_piece(g, entities)

    # --- structure JSON ---
    sid = "%s:%s" % (ns, jid)
    lo_y, hi_y = min_y + 12, max_y - 12
    # мир с кровлей: свои куски до 24 блоков высотой — старт ниже кровли
    # с запасом, иначе верхние блоки (в т.ч. block entity спавнеров)
    # окажутся вне мира → DUMMY-теги и WARN на каждой загрузке чанка
    if roof_bottom is not None:
        hi_y = min(hi_y, roof_bottom - 24)
    if hi_y <= lo_y:
        lo_y = hi_y = (min_y + max_y) // 2
    sj = {
        "type": "minecraft:jigsaw",
        "biomes": None,                             # ниже
        "step": (pref_step if pref_step and rng.random() < 0.8 else rng.choice(STRUCTURE_STEPS)),
        "spawn_overrides": _rand_spawn_overrides(rng),
        "start_pool": start_pool,
        "size": rng.randint(3, 7),
        "use_expansion_hack": use_hack,
        "max_distance_from_center": rng.randint(20, 80),
    }
    if rng.random() < 0.6:
        sj["start_height"] = {"absolute": rng.randint(lo_y, hi_y)}
    else:
        ya = rng.randint(lo_y, hi_y)
        yb = rng.randint(ya, hi_y)
        sj["start_height"] = {"type": "minecraft:uniform",
                              "min_inclusive": {"absolute": ya},
                              "max_inclusive": {"absolute": yb}}
    if rng.random() < 0.85:
        if pref_adapt and rng.random() < 0.80:
            sj["terrain_adaptation"] = pref_adapt
        else:
            sj["terrain_adaptation"] = rng.choices(
                ["beard_thin", "beard_box", "bury", "encapsulate", "none"],
                weights=[65, 22, 8, 3, 2])[0]
    # heightmap projection: maintain exact RNG draw count if step == surface_structures
    _draw_hm = (rng.random() < 0.98) if (sj["step"] == "surface_structures" and not has_ceiling) else True
    if not has_ceiling and (_draw_hm or (_fnv1a(sid + "_hm") % 100 < 96)):
        sj["project_start_to_heightmap"] = "WORLD_SURFACE_WG"
        if hi_y <= lo_y:
            sj["start_height"] = {"absolute": lo_y}
        else:
            sj["start_height"] = {"absolute": 0}
    elif not has_ceiling:
        sj["start_height"] = {"absolute": rng.randint(lo_y, min(hi_y, lo_y + 30))}
    if rng.random() < 0.30:
        sj["start_jigsaw_name"] = ctx["anchor_key"]
    if rng.random() < 0.15:
        sj["dimension_padding"] = rng.choice([4, 6, 8, 10, 16])
    if rng.random() < 0.12:
        sj["liquid_settings"] = "ignore_waterlogging"
    # ванильные алиасы спавнер-пулов trial_chambers — всегда: side-пулы
    # подмешивают ванильные куски любых семейств, и кусок trial_chambers
    # тянет цепочку до алиаса contents/* (неиспользуемые алиасы безвредны)
    sj["pool_aliases"] = TRIAL_POOL_ALIASES + alias_bindings

    # привязка к биомам измерения: СВОИ биомы у каждой структуры — сэмпл
    # 2-5 биомов (было 1-3: маленькие сэмплы часто целиком попадали в
    # биомы, не выигрывающие Voronoi, — площадь ~0, аудит находимости).
    # Первая структура вызова — ЯКОРНАЯ: ей ВСЕ биомы измерения. Климат
    # (continentalness) в модуль не передаётся, а крупнейшие по площади
    # биомы — «центральные» кластера (ближайшие к медиане continentalness
    # 0), поэтому полный охват — единственная ГАРАНТИЯ, что хотя бы одна
    # структура измерения их получает
    if num == 1:
        tag_name = "has_structure/%s" % jid
        sj["biomes"] = "#%s:%s" % (ns, tag_name)
        result["biome_tags"][tag_name] = {"values": sorted(biome_ids)}
    elif rng.random() < 0.55:
        tag_name = "has_structure/%s" % jid
        sj["biomes"] = "#%s:%s" % (ns, tag_name)
        result["biome_tags"][tag_name] = {
            "values": sorted(rng.sample(
                biome_ids, min(len(biome_ids), max(3, int(len(biome_ids) * 0.75)))))}
    else:
        sj["biomes"] = sorted(rng.sample(
            biome_ids, min(len(biome_ids), max(3, int(len(biome_ids) * 0.75)))))

    result["structures"][sid] = sj

    # --- structure_set ---
    ssid = "%s:%s_jigset%d" % (ns, name, num)
    # biomes_ref: concentric_rings ищет позиции в preferred_biomes = ТЕ ЖЕ
    # биомы, что у структуры (независимый сэмпл давал пустые кольца)
    result["structure_sets"][ssid] = _rand_structure_set_json(
        rng, [sid], ns, name, num, biome_ids, result["biome_tags"],
        biomes_ref=sj["biomes"])


def _rand_proc_list(rng, ctx):
    """Свой processor_list: ~45% пустая, иначе rule + вариации: block_rot
    (только rottable стены), protected_blocks с разными ванильными
    блок-тегами (формат 26.2: value = TagKey<Block>), capped с делегатом
    rule и разными лимитами (CappedProcessor: delegate + limit)."""
    from gen_structures import _rand_rule_processor
    if rng.random() < 0.45:
        return {"processors": []}
    processors = [_rand_rule_processor(rng)]
    r = rng.random()
    if r < 0.40:
        processors.append({
            "processor_type": "minecraft:block_rot",
            "rottable_blocks": [ctx["wall"]["Name"]],
            "integrity": round(rng.uniform(0.6, 0.95), 3)})
    elif r < 0.62:
        processors.append({
            "processor_type": "minecraft:protected_blocks",
            "value": rng.choice(_PROTECTED_TAGS)})
    elif r < 0.85:
        processors.append({
            "processor_type": "minecraft:capped",
            "delegate": _rand_rule_processor(rng),
            "limit": rng.randint(2, 12)})
    return {"processors": processors}


# ---------------------------------------------------------------------------
# Главная функция
# ---------------------------------------------------------------------------

def rand_jigsaw(rng, ns, name, min_y, max_y, biome_ids, loot_alloc=None,
                count=None, has_ceiling=False, roof_bottom=None, palette=None):
    """Случайные МНОГОЧАСТНЫЕ jigsaw-структуры для измерения <name>.

    Возвращает dict с теми же ключами, что gen_structures.rand_structures:
    structures / structure_sets / template_pools / processor_lists /
    biome_tags / nbt_files (ключи nbt_files — пути относительно
    data/<ns>/structure/ без расширения; значения — bytes gzip-NBT) плюс
    "loot_slots" — сколько слотов лута занял этот вызов. НИЧЕГО не пишет
    на диск.

    count — сколько структур (по умолчанию 0-3 с тяжёлым хвостом до 8 —
    распределение делает вызывающий). loot_alloc — общий на измерение
    счётчик gen_structures.LootSlots: каждый сундук и каждый моб куска
    занимает СВОЙ уникальный слот лут-таблицы (None → ванильские)."""
    _init_mobs()
    result = {"structures": {}, "structure_sets": {}, "template_pools": {},
              "processor_lists": {}, "biome_tags": {}, "nbt_files": {}}
    biome_ids = list(biome_ids) or ["minecraft:plains"]
    _slots0 = loot_alloc.count if loot_alloc is not None else 0

    if count is None:
        count = rng.randint(0, 3) if rng.random() < 0.9 else rng.randint(4, 8)
    for num in range(1, int(count) + 1):
        _rand_jigsaw_one(rng, ns, name, num, min_y, max_y, biome_ids,
                         loot_alloc, result, has_ceiling=has_ceiling,
                         roof_bottom=roof_bottom, palette=palette)
    result["loot_slots"] = (loot_alloc.count if loot_alloc is not None
                            else 0) - _slots0
    return result


# ---------------------------------------------------------------------------
# Самопроверка
# ---------------------------------------------------------------------------

def _parse_nbt(data):
    """Мини-парсер NBT (для инвариантов самотеста)."""
    import gzip
    import struct

    pos = [0]

    def payload(tid):
        if tid == 1:
            v = data[pos[0]]; pos[0] += 1; return v
        if tid == 2:
            v = struct.unpack_from(">h", data, pos[0])[0]; pos[0] += 2
            return v
        if tid == 3:
            v = struct.unpack_from(">i", data, pos[0])[0]; pos[0] += 4
            return v
        if tid == 4:
            v = struct.unpack_from(">q", data, pos[0])[0]; pos[0] += 8
            return v
        if tid == 5:
            v = struct.unpack_from(">f", data, pos[0])[0]; pos[0] += 4
            return v
        if tid == 6:
            v = struct.unpack_from(">d", data, pos[0])[0]; pos[0] += 8
            return v
        if tid == 8:
            n = struct.unpack_from(">H", data, pos[0])[0]; pos[0] += 2
            s = data[pos[0]:pos[0] + n].decode("utf-8"); pos[0] += n
            return s
        if tid == 9:
            it = data[pos[0]]; pos[0] += 1
            n = struct.unpack_from(">i", data, pos[0])[0]; pos[0] += 4
            return [payload(it) for _ in range(n)]
        if tid == 10:
            d = {}
            while True:
                t = data[pos[0]]; pos[0] += 1
                if t == 0:
                    return d
                n = struct.unpack_from(">H", data, pos[0])[0]; pos[0] += 2
                k = data[pos[0]:pos[0] + n].decode("utf-8"); pos[0] += n
                d[k] = payload(t)
        raise ValueError("bad tag %d" % tid)

    t = data[0]
    assert t == 10 and data[1:3] == b"\x00\x00"
    pos[0] = 3
    return payload(10)


def _self_test_builders(iterations=6):
    """Прямой матричный тест строителей кусков: КАЖДАЯ роль x W{3,5} x
    H{2,3,4} x N повторов — размеры ≤16x24x16, ≥1 валидный порт
    (canAttach-совместимость: joint=rollable, name==target, ключи
    port/vport/anchor), у боковых ролей — ≥1 горизонтальный порт,
    живность в лимитах (мобы ≤ 2, спавнер ≤ 1), экспорт NBT
    идентично парсится."""
    import gzip as _gz
    rng = random.Random(20240601)
    gd = _gd()
    _mob_risk = {"minecraft:spawner", "minecraft:trial_spawner",
                 "minecraft:vault", "minecraft:sniffer_egg",
                 "minecraft:jigsaw"}
    solid = [b for b in gd.PALETTE_BLOCKS if b[0] not in _mob_risk]
    horiz = {"west_up", "east_up", "north_up", "south_up"}
    checked = {}
    for role, builder in sorted(_BUILDERS.items()):
        for W in (3, 5):
            for H in (2, 3, 4):
                for _ in range(iterations):
                    ctx = {
                        "W": W, "H": H,
                        "loot_alloc": None,
                        "solid": solid,
                        "max_tower_h": 24,
                        "has_vertical": True,
                        "has_down": True,
                        "port_key": "t:t/port",
                        "vport_key": "t:t/vport",
                        "anchor_key": "t:t/anchor",
                        "side_pool": {r: "t:t/ps_%s" % r
                                      for r in _SIDE_ROLES},
                        "tbase_pool": "t:t/tbase",
                        "tchain_pool": "t:t/tchain",
                        "pbase_pool": "t:t/pbase",
                    }
                    ctx["floor"] = gd.block_state(rng.choice(solid))
                    ctx["wall"] = gd.block_state(rng.choice(solid))
                    ctx["accent"] = gd.block_state(rng.choice(solid))
                    ctx["frame"] = gd.block_state(rng.choice(solid))
                    ctx["light"] = rng.choice(_LIGHT_BLOCKS)
                    ctx["floor_str"] = _state_str(ctx["floor"])
                    ctx["ladder_str"] = _state_str(_ladder("east"))
                    g, entities = builder(rng, ctx)
                    assert g.sx <= 16 and g.sy <= 24 and g.sz <= 16, \
                        (role, W, H, g.sx, g.sy, g.sz)
                    assert len(entities) <= 2, (role, len(entities))
                    jigsaws = []
                    spawners = 0
                    for x in range(g.sx):
                        for y in range(g.sy):
                            for z in range(g.sz):
                                cell = g.get(x, y, z)
                                if not cell:
                                    continue
                                name = cell[0].get("Name")
                                if name == "minecraft:jigsaw":
                                    jigsaws.append(cell)
                                elif name == "minecraft:spawner":
                                    spawners += 1
                    assert jigsaws, "кусок без портов: %s" % role
                    assert spawners <= 1, (role, spawners)
                    n_horiz = 0
                    for cell in jigsaws:
                        nbt = cell[1]
                        assert nbt["joint"] == "rollable", (role, nbt)
                        # симметричный ключ ИЛИ якорь старта (name=anchor,
                        # target=port — точка start_jigsaw_name, как в ванили)
                        assert (nbt["name"] == nbt["target"]
                                or (nbt["name"] == "t:t/anchor"
                                    and nbt["target"] == "t:t/port")), \
                            (role, nbt)
                        assert nbt["target"] in ("t:t/port", "t:t/vport"), \
                            (role, nbt)
                        assert nbt["name"] in ("t:t/port", "t:t/vport",
                                               "t:t/anchor"), (role, nbt)
                        orient = cell[0]["Properties"]["orientation"]
                        assert orient in JIGSAW_ORIENTATIONS, (role, orient)
                        if orient in horiz:
                            n_horiz += 1
                    # боковая роль обязана иметь горизонтальный порт —
                    # иначе её НЕВОЗМОЖНО прицепить боковой тягой
                    if role in _SIDE_ROLES:
                        assert n_horiz >= 1, ("нет бокового порта", role)
                    checked[role] = checked.get(role, 0) + 1
                    blob = _export_piece(g, entities)
                    root = _parse_nbt(_gz.decompress(blob))
                    assert root["size"] == [g.sx, g.sy, g.sz], role
                    assert root["DataVersion"] == DATA_VERSION, role
    print("строители: %d ролей x W{3,5} x H{2,3,4} x %d = %d кусков OK"
          % (len(checked), iterations, sum(checked.values())))


def _self_test(seeds=25):
    import gzip
    import re

    _self_test_builders()
    ok = 0
    stats_all = {"pieces": 0, "mobs": 0, "spawners": 0, "chests": 0}
    role_pieces = {}      # роль -> кусков за все сиды (новые архетипы живые?)
    for seed in range(1, seeds + 1):
        rng = random.Random(seed)
        alloc = LootSlots("rndim", "testdim")
        res = rand_jigsaw(rng, "rndim", "testdim", -64, 320,
                          ["rndim:t_b1", "rndim:t_b2", "rndim:t_b3"],
                          loot_alloc=alloc,
                          count=(seed % 5) + 1)
        assert res["loot_slots"] == alloc.count, (res["loot_slots"],
                                                  alloc.count)
        own_pools = set(res["template_pools"])
        own_pieces = {"rndim:%s" % k for k in res["nbt_files"]}
        # алиасы пулов (pool_aliases в structure JSON резолвятся в реальные
        # пулы при сборке — ссылки на алиас в кусках легальны). Три формы
        # (байткод 26.2): direct {alias,target}; random {alias,targets[
        # {weight,data}]}; random_group {groups[{weight,data:[direct...]}]}
        # без топ-уровневого alias. Для _pool_ok достаточно ЛЮБОГО
        # допустимого цели (наши куски дёргают только свои direct-алиасы;
        # алиасы trial_chambers нужны ванильным кускам и ведут в ванильные
        # пулы, которых нет в own_pools)
        aliases = {}
        for sj in res["structures"].values():
            for al in sj.get("pool_aliases", []):
                if al["type"] == "minecraft:direct":
                    aliases[al["alias"]] = al["target"]
                elif al["type"] == "minecraft:random":
                    aliases[al["alias"]] = al["targets"][0]["data"]
                elif al["type"] == "minecraft:random_group":
                    for grp in al["groups"]:
                        for bnd in grp["data"]:
                            aliases[bnd["alias"]] = bnd["target"]
        def _pool_ok(pool):
            while pool in aliases:
                pool = aliases[pool]
            return pool == "minecraft:empty" or pool in own_pools

        # JSON сериализуем
        for key in ("structures", "structure_sets", "template_pools",
                    "processor_lists", "biome_tags"):
            for obj in res[key].values():
                json.dumps(obj)

        for sid, sj in res["structures"].items():
            assert sj["type"] == "minecraft:jigsaw"
            assert sj["start_pool"] in own_pools, sid
            assert sj["biomes"], sid
            if isinstance(sj["biomes"], str):        # "#ns:tag"
                assert sj["biomes"][1:] in \
                    {"rndim:%s" % t for t in res["biome_tags"]}, sid
            md = sj["max_distance_from_center"]
            assert 20 <= md <= 80, sid
            if sj.get("terrain_adaptation", "none") != "none":
                assert md + 12 <= 128, sid           # verifyRange в 26.2
            assert 0 <= sj["size"] <= 20, sid
            if sj.get("use_expansion_hack"):
                # YSpan дочерних кусков <= 16 (проверка JigsawPlacement)
                num = sid.rsplit("jig", 1)[1]
                for pkey, blob in res["nbt_files"].items():
                    if pkey.startswith("testdim/jig%s/" % num):
                        root = _parse_nbt(gzip.decompress(blob))
                        assert root["size"][1] <= 16, (sid, pkey)
            if "start_jigsaw_name" in sj:
                # стартовый кусок обязан содержать jigsaw с этим name,
                # иначе findGenerationPoint пуст и структура не генерится
                num = sid.rsplit("jig", 1)[1]
                root = _parse_nbt(gzip.decompress(
                    res["nbt_files"]["testdim/jig%s/start" % num]))
                names = {b.get("nbt", {}).get("name")
                         for b in root["blocks"]
                         if root["palette"][b["state"]].get("Name")
                         == "minecraft:jigsaw"}
                assert sj["start_jigsaw_name"] in names, sid

        # якорная структура (первая) покрывает ВСЕ биомы измерения —
        # климат в модуль не передаётся, полный охват гарантирует самые
        # крупные «центральные» биомы (continentalness ~ 0) хотя бы одной
        # структуре измерения
        aref = res["structures"]["rndim:testdim_jig1"]["biomes"]
        avals = (res["biome_tags"][aref[1:].split(":", 1)[1]]["values"]
                 if isinstance(aref, str) else aref)
        assert avals == sorted(["rndim:t_b1", "rndim:t_b2",
                                "rndim:t_b3"]), "якорь не все биомы"
        # сэмплы биомов остальных структур: 2-5 (в тесте биомов всего 3)
        for sid, sj in res["structures"].items():
            if sid == "rndim:testdim_jig1":
                continue
            ref = sj["biomes"]
            vals = (res["biome_tags"][ref[1:].split(":", 1)[1]]["values"]
                    if isinstance(ref, str) else ref)
            assert 2 <= len(vals) <= 5, (sid, len(vals))

        for ssid, ss in res["structure_sets"].items():
            for st in ss["structures"]:
                assert st["structure"] in res["structures"], ssid
            # инварианты находимости (аудит): placement-параметры
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
                    res["structures"][sid0]["biomes"], ssid

        for pid, pool in res["template_pools"].items():
            assert pool["fallback"] == "minecraft:empty", pid
            assert pool["elements"], pid
            for el in pool["elements"]:
                loc = el["element"].get("location")
                if loc:
                    assert loc in own_pieces, (pid, loc)
                assert el["element"]["projection"] == "rigid", pid

        # куски: gzip-NBT, размеры, jigsaw-блоки валидны, живность редкая
        for key, blob in res["nbt_files"].items():
            assert isinstance(blob, bytes) and blob[:2] == b"\x1f\x8b", key
            raw = gzip.decompress(blob)
            # мобы живые и уязвимые: NoAI/Invulnerable запрещены
            assert b"NoAI" not in raw and b"Invulnerable" not in raw, key
            root = _parse_nbt(raw)
            assert root["DataVersion"] == 4903, key
            sx, sy, sz = root["size"]
            assert sx <= 16 and sy <= 24 and sz <= 16, key
            assert len(root["palette"]) >= 1, key
            assert re.fullmatch(r"[a-z0-9_/]+", key), key
            palette = root["palette"]
            mobs = spawners = chests = 0
            jigsaws = []
            for blk in root["blocks"]:
                st = palette[blk["state"]]
                if st.get("Name") == "minecraft:jigsaw":
                    nbt = blk.get("nbt") or {}
                    assert st["Properties"]["orientation"] in \
                        JIGSAW_ORIENTATIONS, key
                    assert nbt.get("pool"), key
                    assert _pool_ok(nbt["pool"]), (key, nbt["pool"])
                    assert nbt.get("name") and nbt.get("target"), key
                    jigsaws.append(blk)
                if st.get("Name") == "minecraft:spawner":
                    spawners += 1
                if st.get("Name") in ("minecraft:chest", "minecraft:barrel"):
                    chests += 1
                    # палитра — gd.PALETTE_BLOCKS (без block entity),
                    # поэтому контейнер в куске бывает только НАСТОЯЩИЙ
                    # (из _add_chest, всегда с LootTable)
                    if "nbt" in blk:
                        assert blk["nbt"].get("LootTable"), key
            # УНИКАЛЬНОСТЬ: каждая ссылка на наш лут — свой слот
            refs = re.findall(rb"rndim:testdim_loot\d+", raw)
            assert len(refs) == len(set(refs)), (key, refs)
            mobs = len(root["entities"])
            assert mobs <= 2, (key, mobs)
            # у каждого куска ≥ 1 порт — иначе его НЕВОЗМОЖНО прицепить
            # (соединение идёт через jigsaw-блок в самом куске)
            assert jigsaws, "кусок без jigsaw-портов: %s" % key
            stats_all["pieces"] += 1
            stats_all["mobs"] += mobs
            stats_all["spawners"] += spawners
            stats_all["chests"] += chests
            role = re.sub(r"\d+$", "", key.rsplit("/", 1)[1])
            role_pieces[role] = role_pieces.get(role, 0) + 1
            # у стартового куска >= 2 порта (структура должна тянуть куски)
            if key.endswith("/start"):
                assert len(jigsaws) >= 2, key

        # воспроизводимость
        rng2 = random.Random(seed)
        res2 = rand_jigsaw(rng2, "rndim", "testdim", -64, 320,
                           ["rndim:t_b1", "rndim:t_b2", "rndim:t_b3"],
                           loot_alloc=LootSlots("rndim", "testdim"),
                           count=(seed % 5) + 1)
        assert json.dumps(res2["structures"], sort_keys=True) == \
            json.dumps(res["structures"], sort_keys=True)
        assert res2["nbt_files"] == res["nbt_files"]
        ok += 1
        print("seed %2d: structures=%d pieces=%d pools=%d sets=%d tags=%d"
              % (seed, len(res["structures"]), len(res["nbt_files"]),
                 len(res["template_pools"]), len(res["structure_sets"]),
                 len(res["biome_tags"])))
    # НОВЫЕ архетипы реально генерируются (не мёртвый код): каждый
    # встречается хотя бы раз за N сидов
    for role in ("gate", "courtyard", "spire", "terrace", "pit",
                 "viaduct", "rotunda", "arena", "workshop", "treasury",
                 "greenhouse", "mausoleum", "chainbridge", "ruins",
                 "labyrinth", "observatory", "kitchen", "mine"):
        assert role_pieces.get(role, 0) >= 1, \
            "архетип %s не сгенерировался ни разу за %d сидов" % (
                role, seeds)
    print("роли кусков за все сиды: %s" % ", ".join(
        "%s=%d" % (r, n) for r, n in sorted(role_pieces.items())))
    print("итого: кусков=%d мобов=%d спавнеров=%d сундуков=%d "
          "(мобов/кусок=%.2f, спавнеров/кусок=%.2f)" % (
              stats_all["pieces"], stats_all["mobs"], stats_all["spawners"],
              stats_all["chests"],
              stats_all["mobs"] / max(1, stats_all["pieces"]),
              stats_all["spawners"] / max(1, stats_all["pieces"])))
    print("OK: %d/%d seed'ов без исключений" % (ok, seeds))


if __name__ == "__main__":
    _self_test()