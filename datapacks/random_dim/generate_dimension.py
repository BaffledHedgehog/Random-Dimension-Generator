#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_dimension.py — генератор ПОЛНОСТЬЮ случайных измерений для Minecraft 26.2
(pack_format 107). Синтаксис всех JSON сверён с ванильным jar-файлом версии 26.2
(dimension_type, noise_settings, noise, density functions, surface rules).

Каждый запуск добавляет в датапак +1 новое измерение со случайными:
  * размером и границами мира (min_y / height / logical_height)
  * типом измерения: свет, потолок/небо, coordinate_scale, ambient_light,
    небосклон (skybox), цвета неба/тумана/облаков, атрибуты геймплея и т.д.
  * шумами генерации: собственные случайные спектры — пять форм
    огибающей амплитуд (убывающая / пик / двугорбая / плоская
    «кристаллическая» / возрастающая), firstOctave -19..2 (чаще
    -10..-4), масштабы xz/y лог-равномерно 0.005..2.0 с сильной
    анизотропией (столбы/слои) — только для рельефа; climate-каналы
    держат свою нормализацию σ (находимость биомов)
  * noise_router: final_density — ГАРАНТИИ ПО КРАЯМ (у cavern —
    ПЛОСКИЕ ТВЁРДЫЕ КАПЫ дна/кровли: каменная плита +3.5 без
    пересечения нуля, на ней бедрок-полоса surface-правил) плюс
    ОГРАНИЧЕННЫЕ возмущения в середине (структурные градиенты НЕ
    зависят от шумов; каждый слой шума зажат clamp'ом — насыщение
    «мир насплочь» невозможно); 34 ИМЕНОВАННЫХ ПРЕСЕТА РЕЛЬЕФА с
    окнами параметров (overworld_classic — самый частый, thorns —
    шипы, dunes, canyons, craters, terraced, mesas, mountain_ridge,
    archipelago, swiss_cheese, shattered... веса: красивые ~75%,
    умеренные ~15%, скучные <=10%), рандомизация внутри окон даёт
    сотни комбинаций; формы мира: open (воздух у max_y, камень у
    min_y), cavern (массив у обоих краёв + гарантированный воздушный
    пояс в середине, как незер), void (воздух у обоих краёв, острова
    в середине); 10 характеров рельефа, региональный микс, сплайн
    кластеров по continents; прочие каналы — случайные деревья
    density-функций из ВСЕХ типов 26.2
    (add/mul/min/max/clamp/abs/square/cube/squeeze/interpolated/blend_density/
     noise/shifted_noise/shift_a/shift_b/y_clamped_gradient/range_choice/
     interval_select/spline/cache_once/cache_2d/flat_cache/end_islands/...)
  * поверхностью (surface_rule): случайные слои из случайных блоков
  * биомами: 20-30 полностью случайных биомов на измерение (свои цвета
    неба/травы/листвы, частицы, звуки, музыка, карверы, декорации, мобы
    и их веса, температура/осадки) — формат 26.2 с attributes
  * источником биомов: multi_noise (свои/пресет), checkerboard, fixed, the_end
  * подземными биомами: в мирах выше 256 с 6+ биомами 2-4 биома становятся
    пещерными — своя depth-полоса в подземной зоне, пещерные фичи/карверы/
    фауна, полы из sculk и мха (остальное подземное пространство остаётся
    за надземными биомами — как в ваниле); кровать в КАЖДОМ измерении
     разрешена и ставит точку спавна; руды: 5-9 видов с пер-биомными
    уровнями богатства ×0.3/×1/×2.5/×5 и высотами по долям высоты мира
  * каменным семейством: 3-7 доп. блоков с тирами частоты и РАЗНЫМИ
    методами генерации — большие блобы (как ванильные андезит/гранит,
    15-64×count 1-6), 1-2 глубинные полосы (как deepslate), 1-3
    поверхностные заплатки (как кальцит) и «жила-стержень»;
    в void-мирах сыпучие блоки (песок/гравий/бетонные порошки)
    ЗАПРЕЩЕНЫ во всём рельефе — иначе мир «сыпется» в пустоту
  * аквиферами, рудными жилами, уровнем моря, жидкостью и блоком-основой

Использование:
    python generate_dimension.py                 # +1 случайное измерение
    python generate_dimension.py --count 5       # +5 измерений
    python generate_dimension.py --seed 12345    # воспроизводимый результат
    python generate_dimension.py --name myworld  # задать имя измерения
    python generate_dimension.py --biomes 16     # сколько своих биомов (по умолч. случайно 20-30)
    python generate_dimension.py --namespace foo # свой namespace (по умолч. rndim)
    python generate_dimension.py --list          # список созданных измерений
    python generate_dimension.py --check         # проверка целостности данных
    python generate_dimension.py --print         # вывести JSON, не записывая
    python generate_dimension.py --regen         # удалить все сгенерированные измерения

После генерации: /reload в игре. Если измерение не появилось — перезайди в мир
(новые измерения иногда подхватываются только при повторном входе в мир).
"""

import argparse
import glob
import json
import math
import os
import random
import re
import shutil
import statistics
import sys
from pathlib import Path

import gen_advancements
import gen_features
import gen_structures
import gen_time


def _gl():
    """Ленивый импорт gen_loot — модуль может ещё не существовать."""
    global gen_loot
    try:
        import gen_loot
    except ImportError:
        return None
    return gen_loot


def _gts():
    """Ленивый импорт gen_trial_spawners (может ещё не существовать)."""
    global gen_trial_spawners
    try:
        import gen_trial_spawners
    except ImportError:
        return None
    return gen_trial_spawners


def _lazy(modname):
    """Ленивый импорт модуля-генератора (может ещё не существовать)."""
    import importlib
    try:
        return importlib.import_module(modname)
    except ImportError:
        return None

DATAPACK_ROOT = Path(__file__).resolve().parent
DATA_ROOT = DATAPACK_ROOT / "data"

# ---------------------------------------------------------------------------
# Данные, существование которых подтверждено в ванильном jar 26.2
# ---------------------------------------------------------------------------

BIOMES = [
    "badlands", "bamboo_jungle", "basalt_deltas", "beach", "birch_forest",
    "cherry_grove", "cold_ocean", "crimson_forest", "dark_forest",
    "deep_cold_ocean", "deep_dark", "deep_frozen_ocean", "deep_lukewarm_ocean",
    "deep_ocean", "desert", "dripstone_caves", "end_barrens", "end_highlands",
    "end_midlands", "eroded_badlands", "flower_forest", "forest", "frozen_ocean",
    "frozen_peaks", "frozen_river", "grove", "ice_spikes", "jagged_peaks",
    "jungle", "lukewarm_ocean", "lush_caves", "mangrove_swamp", "meadow",
    "mushroom_fields", "nether_wastes", "ocean", "old_growth_birch_forest",
    "old_growth_pine_taiga", "old_growth_spruce_taiga", "pale_garden", "plains",
    "river", "savanna", "savanna_plateau", "small_end_islands", "snowy_beach",
    "snowy_plains", "snowy_slopes", "snowy_taiga", "soul_sand_valley",
    "sparse_jungle", "stony_peaks", "stony_shore", "sulfur_caves",
    "sunflower_plains", "swamp", "taiga", "the_end", "the_void", "warm_ocean",
    "warped_forest", "windswept_forest", "windswept_gravelly_hills",
    "windswept_hills", "windswept_savanna", "wooded_badlands",
]

COLORS = ["white", "orange", "magenta", "light_blue", "yellow", "lime", "pink",
          "gray", "light_gray", "cyan", "purple", "blue", "brown", "green",
          "red", "black"]

# (block_id, properties|None) — полные кубы, пригодные для террейна.
#
# Блоки рассортированы по «тирам странности»: Т0 — обычный камень и земля,
# дальше — цветные/промышленные, редкие декоративные, функциональные
# (с block entity) и, наконец, технический сюрреализм (барьеры, командные
# блоки). Чем страннее блок, тем реже он выпадает: развёрнутый список
# дублирует каждый блок пропорционально весу тира, поэтому ЛЮБОЙ равномерный
# rng.choice() по списку автоматически соблюдает убывающую вероятность.
# Полный перечень сверен с lang-файлом jar 26.2; неполные кубы (ступени,
# плиты, заборы, растения...) и динамит не включаем.
_AXIS_BLOCKS = {"deepslate", "basalt", "polished_basalt", "quartz_pillar",
                "purpur_pillar", "bone_block", "hay_block", "bamboo_block",
                "stripped_bamboo_block"}
for _w in ["oak", "spruce", "birch", "jungle", "acacia", "dark_oak",
           "mangrove", "cherry", "pale_oak"]:
    _AXIS_BLOCKS |= {_w + "_log", _w + "_wood",
                     "stripped_" + _w + "_log", "stripped_" + _w + "_wood"}
for _s in ["crimson", "warped"]:
    _AXIS_BLOCKS |= {_s + "_stem", _s + "_hyphae",
                     "stripped_" + _s + "_stem", "stripped_" + _s + "_hyphae"}
_SNOWY_BLOCKS = {"grass_block", "podzol", "mycelium"}

_COPPER_STAGES = ["", "exposed_", "weathered_", "oxidized_"]


def _blk(name):
    if name in _AXIS_BLOCKS:
        return ("minecraft:" + name, {"axis": "y"})
    if name in _SNOWY_BLOCKS:
        return ("minecraft:" + name, {"snowy": "false"})
    return ("minecraft:" + name, None)


def _wood_family(out):
    for w in ["oak", "spruce", "birch", "jungle", "acacia", "dark_oak",
              "mangrove", "cherry", "pale_oak"]:
        out += [w + "_log", w + "_wood", "stripped_" + w + "_log",
                "stripped_" + w + "_wood", w + "_planks"]
    for s in ["crimson", "warped"]:
        out += [s + "_stem", s + "_hyphae", "stripped_" + s + "_stem",
                "stripped_" + s + "_hyphae", s + "_planks"]
    out += ["bamboo_block", "stripped_bamboo_block", "bamboo_planks",
            "bamboo_mosaic"]


# Камнеподобные (камень/кирпич/полированное) — ПРИОРИТЕТ рельефа
# (жалоба юзера: «почти в каждом мире рельеф из дерева, хочу чаще
# каменно-похожие блоки»): вес 20 против прежних 16 у всего T0
_T0_ROCK = [
    "stone", "granite", "diorite", "andesite", "tuff", "calcite",
    "polished_granite", "polished_diorite", "polished_andesite",
    "cobblestone", "mossy_cobblestone", "stone_bricks",
    "mossy_stone_bricks", "cracked_stone_bricks", "chiseled_stone_bricks",
    "smooth_stone", "sandstone", "cut_sandstone", "smooth_sandstone",
    "chiseled_sandstone", "red_sandstone", "cut_red_sandstone",
    "smooth_red_sandstone", "chiseled_red_sandstone", "basalt",
    "polished_basalt", "blackstone", "polished_blackstone",
    "polished_blackstone_bricks", "chiseled_polished_blackstone",
    "cracked_polished_blackstone_bricks", "obsidian", "crying_obsidian",
    "end_stone", "end_stone_bricks", "bricks", "nether_bricks",
    "red_nether_bricks", "chiseled_nether_bricks", "cracked_nether_bricks",
    "terracotta", "deepslate", "cobbled_deepslate", "polished_deepslate",
    "deepslate_bricks", "cracked_deepslate_bricks", "deepslate_tiles",
    "cracked_deepslate_tiles", "chiseled_deepslate", "tuff_bricks",
    "polished_tuff", "chiseled_tuff", "chiseled_tuff_bricks",
]
# Земляные/сыпучие/незер-органика — прежний вес 16
_T0_EARTH = [
    "dirt", "coarse_dirt", "rooted_dirt", "dirt_path",
    "mud", "packed_mud", "mud_bricks", "sand", "red_sand", "gravel",
    "netherrack", "smooth_basalt",
]
# ДРЕВЕСИНА — вес ×0.25 от прежнего (16 → 4): брёвна/обтёсанные/
# доски как материал РЕЛЬЕФА теперь редкость (жалоба юзера — дерево
# всюду); отдельный тир на уровне T0, в палитре остаётся
_T0_WOOD = []
_wood_family(_T0_WOOD)

_T1_FAMILIAR = [
    "glass", "tinted_glass", "quartz_block", "chiseled_quartz_block",
    "quartz_bricks", "quartz_pillar", "smooth_quartz", "purpur_block",
    "purpur_pillar", "prismarine", "prismarine_bricks", "dark_prismarine",
    "raw_iron_block", "raw_copper_block", "raw_gold_block", "iron_block",
    "gold_block", "diamond_block", "emerald_block", "netherite_block",
    "lapis_block", "redstone_block", "coal_block", "amethyst_block",
    "copper_ore", "coal_ore", "iron_ore", "gold_ore", "diamond_ore",
    "emerald_ore", "redstone_ore", "lapis_ore", "deepslate_copper_ore",
    "deepslate_coal_ore", "deepslate_iron_ore", "deepslate_gold_ore",
    "deepslate_diamond_ore", "deepslate_emerald_ore",
    "deepslate_redstone_ore", "deepslate_lapis_ore", "nether_gold_ore",
    "nether_quartz_ore", "moss_block", "pale_moss_block", "snow_block",
    "ice", "packed_ice", "blue_ice", "frosted_ice", "magma_block",
    "glowstone", "shroomlight", "sea_lantern", "dripstone_block", "sculk",
    "resin_block", "resin_bricks", "cinnabar", "cinnabar_bricks",
    "polished_cinnabar", "chiseled_cinnabar", "sulfur", "sulfur_bricks",
    "polished_sulfur", "chiseled_sulfur", "potent_sulfur",
    "honeycomb_block", "dried_kelp_block", "bookshelf",
    "chiseled_bookshelf", "melon", "pumpkin", "carved_pumpkin",
    "jack_o_lantern", "hay_block", "bone_block", "clay", "soul_sand",
    "soul_soil", "mycelium", "podzol", "grass_block", "crimson_nylium",
    "warped_nylium", "brown_mushroom_block", "red_mushroom_block",
    "mushroom_stem", "sponge", "wet_sponge", "slime_block", "honey_block",
    "suspicious_sand", "suspicious_gravel", "sniffer_egg",
]
for _c in COLORS:
    _T1_FAMILIAR += ["%s_wool" % _c, "%s_concrete" % _c,
                     "%s_concrete_powder" % _c, "%s_stained_glass" % _c,
                     "%s_terracotta" % _c]
_T1_FAMILIAR += ["copper_block", "exposed_copper", "weathered_copper",
                 "oxidized_copper"]
for _st in _COPPER_STAGES:
    _T1_FAMILIAR += ["%scut_copper" % _st, "%schiseled_copper" % _st]

# БЕДРОК — редкий «странный» блок рельефа (T2, вес 1 — решение юзера:
# редкие миры из бедрока допустимы). Отдельно от пулов он живёт в
# bedrock_floor/bedrock_roof условиях surface_rule (см. rand_surface_rule)
# и в спавн-тегах (_SPAWN_TAG_SAFE_IDS).
_T2_RARE = [
    "verdant_froglight", "ochre_froglight", "pearlescent_froglight",
    "infested_stone", "infested_cobblestone", "infested_stone_bricks",
    "infested_mossy_stone_bricks", "infested_cracked_stone_bricks",
    "infested_chiseled_stone_bricks", "infested_deepslate",
    "gilded_blackstone", "ancient_debris", "reinforced_deepslate",
    "sculk_catalyst", "spawner", "budding_amethyst",
    "powder_snow", "bedrock",
]
for _c in COLORS:
    _T2_RARE.append("%s_glazed_terracotta" % _c)
for _st in _COPPER_STAGES + ["waxed_", "waxed_exposed_",
                             "waxed_weathered_", "waxed_oxidized_"]:
    _T2_RARE += ["%scopper_grate" % _st, "%scopper_bulb" % _st,
                 "%scopper_golem_statue" % _st]

_T3_FUNCTIONAL = [
    "crafting_table", "furnace", "blast_furnace", "smoker", "dispenser",
    "dropper", "jukebox", "note_block", "chest", "trapped_chest",
    "ender_chest", "barrel", "beacon", "respawn_anchor", "lodestone",
    "target", "crafter", "trial_spawner", "vault", "loom",
    "cartography_table", "fletching_table", "smithing_table", "observer",
    "piston", "sticky_piston", "redstone_lamp", "composter",
]
for _st in _COPPER_STAGES + ["waxed_", "waxed_exposed_",
                             "waxed_weathered_", "waxed_oxidized_"]:
    _T3_FUNCTIONAL.append("%scopper_chest" % _st)

_T4_SURREAL = [
    "barrier", "light", "command_block", "chain_command_block",
    "repeating_command_block", "jigsaw", "structure_block", "test_block",
    "test_instance_block",
]

# (вес, имена) — вес = сколько копий блока в развёрнутом списке.
# Дерево — ОТДЕЛЬНЫЙ тир веса 4 (было 16 внутри T0 — кратно ниже,
# ×0.25): «рельеф из брёвен» теперь редкость, камнеподобные (вес 20)
# — наоборот, чаще
BLOCK_TIERS = [
    (20, _T0_ROCK),         # камень/кирпич/полированное — приоритет
    (16, _T0_EARTH),        # земля/песок/незер-органика
    (4, _T0_WOOD),          # древесина — редко (было 16)
    (8, _T1_FAMILIAR),      # цветное, промышленное, природное
    (4, _T2_RARE),          # редкие и странные декоративные
    (2, _T3_FUNCTIONAL),    # функциональные с block entity
    (1, _T4_SURREAL),       # технический сюрреализм
]


def _flatten_tiers(tiers):
    out = []
    for weight, names in tiers:
        for n in names:
            out.extend([_blk(n)] * weight)
    return out


SOLID_BLOCKS = _flatten_tiers(BLOCK_TIERS)

# ---------------------------------------------------------------------------
# Безопасный пул для МАССОВОЙ заливки (стены/полы/колонны структур, палитры
# jigsaw, default_block и слои surface rules — вплоть до половины мира).
# Жалоба пользователя: данж, все стены которого состояли из
# copper_golem_statue (block entity) — сильно грузил FPS. Поэтому из
# T0+T1+T2 выкидываем всё, что имеет block entity ИЛИ «порождает живность»;
# T3 (функциональные, ВСЕ с block entity) и T4 (командные/технические)
# исключены целиком. Полный перечень block entity сверен javap'ом
# BlockEntityTypes.class из jar 26.2 (регистрации): из наших T0-T2 это
#   spawner, sculk_catalyst, chiseled_bookshelf, suspicious_sand,
#   suspicious_gravel, potent_sulfur, copper_golem_statue (все 8 стадий
#   окисления/воскования; у медного семейства block entity имеют ТОЛЬКО
#   copper_chest (T3) и copper_golem_statue — copper_bulb/copper_grate
#   БЕЗ block entity и остаются в пуле).
# Дополнительно без block entity, но не менее вредные в стенах:
#   sniffer_egg — из яйца ВЫЛУПЛЯЕТСЯ моб (стена из яиц = тысячи
#     снифферов; по той же причине его исключает _mob_risk в gen_jigsaw);
#   powder_snow — не-solid: мобы и игрок проваливаются сквозь стену.
# SOLID_BLOCKS НЕ трогаем: он нужен карверам (replaceable — «что можно
# прокопать», не массовая заливка) и gen_features.
_PALETTE_EXCLUDE = {
    "minecraft:spawner", "minecraft:sculk_catalyst", "minecraft:powder_snow",
    "minecraft:chiseled_bookshelf", "minecraft:suspicious_sand",
    "minecraft:suspicious_gravel", "minecraft:potent_sulfur",
    "minecraft:sniffer_egg",
}
for _st in _COPPER_STAGES + ["waxed_", "waxed_exposed_",
                             "waxed_weathered_", "waxed_oxidized_"]:
    _PALETTE_EXCLUDE.add("minecraft:%scopper_golem_statue" % _st)

PALETTE_BLOCKS = [b for b in _flatten_tiers(BLOCK_TIERS[:3])
                  if b[0] not in _PALETTE_EXCLUDE]
# (спавн-теги собирают и floor/roof — там бедрок легитимен)

# Все блоки С block entity среди SOLID_BLOCKS: T3 целиком (функциональные),
# T4 без barrier/light (командные/технические — у всех BE, barrier и light
# — нет) и точечные BE-блоки T0-T2 (список сверен javap'ом
# BlockEntityTypes из jar 26.2; powder_snow в _PALETTE_EXCLUDE по другой
# причине — не-solid — и здесь BE нет). Нужно gen_features: фичи
# МАССОВОГО масштаба (деревья, диски, жеоды...) обязаны брать блоки без
# BE — тысячи стволов из copper_golem_statue = 20к+ block entity на мир
# и DUMMY-мусор над потолком (стволы, пробившие потолок мира).
BE_BLOCK_IDS = {b[0] for b in _flatten_tiers([(1, _T3_FUNCTIONAL)])}
BE_BLOCK_IDS |= {b[0] for b in _flatten_tiers([(1, _T4_SURREAL)])
                 if b[0] not in ("minecraft:barrier", "minecraft:light")}
BE_BLOCK_IDS |= (_PALETTE_EXCLUDE - {"minecraft:powder_snow"})

# СЫПУЧИЕ (гравитационные) блоки: пески/гравий/подозрительные +
# все 16 бетонных порошков. Правила 26.2-генератора (решение юзера:
# «сыпучие всё-таки МОЖНО использовать в рельефе, но только если блоки
# рельефа достаточно разнообразные И у мира есть бедроковое дно; и НЕ ВСЕ
# блоки рельефа могут быть сыпучими»):
#   - default_block (и «море»-из-блока) — НИКОГДА не сыпучие: основа
#     массива мира, обваливающаяся в каждую пещеру/carver;
#   - VOID-миры (нет твёрдого дна) — ЗАПРЕТ во всём рельефном
#     использовании: блок над пустотой обращается в entity
#     FALLING_BLOCK — весь мир «сыпется», сотни тысяч сущностей
#     (жалоба юзера); фильтрует _terrain_palette;
#   - open/cavern (бедрок-дно есть) — БЮДЖЕТ: суммарно не более 2
#     РАЗНЫХ сыпучих среди семейства + top-слоёв биомов + полос +
#     заплаток, и только при семействе >= 3 блоков (разнообразие).
#     Считает _falling_aware_choice / _select_stone_family
#     (self._falling_used / _falling_budget).
# В лут-таблицах/сундуках предметы-сыпучие ОСТАЮТСЯ — это предметы,
# не блоки рельефа. Критерий фильтрации — «блок становится частью
# массива рельефа»; предикаты МАТЧИНГА (matching_blocks/block_match/
# tag_match) сыпучие id сохраняют: совпадения просто не будет,
# размещения не происходит.
FALLING_BLOCK_IDS = {
    "minecraft:sand", "minecraft:red_sand", "minecraft:gravel",
    "minecraft:suspicious_sand", "minecraft:suspicious_gravel",
} | {"minecraft:%s_concrete_powder" % _c for _c in COLORS}


def _material_family(bid):
    """Грубая «семья материала» блока: stone/soil/wood/wool/metal/
    concrete/powder/terracotta/glass/ice/organic. Нужна для двух задач
    различимости биомов и рельефа: (а) top-блоки соседних биомов — из
    РАЗНЫХ семейств (камень vs дерево vs шерсть vs металл — не два
    биома с брёвнами подряд); (б) каменное семейство мира — с
    приоритетом камнеподобных, бревно — максимум одно и редко.
    Точность не критична: экзотика сваливается в 'stone' — важны
    только крупные различия."""
    n = bid.rsplit(":", 1)[-1]
    # органика — до дерева: mushroom_stem кончается на _stem, но это
    # гриб, не бревно
    if n in ("mushroom_stem", "melon", "pumpkin", "carved_pumpkin",
             "jack_o_lantern", "sponge", "wet_sponge", "slime_block",
             "honey_block", "honeycomb_block", "dried_kelp_block",
             "bookshelf", "chiseled_bookshelf", "hay_block",
             "moss_block", "pale_moss_block") \
            or n.endswith("mushroom_block") or n.endswith("mushroom"):
        return "organic"
    if (n.startswith("stripped_") or n == "bamboo_block"
            or n.endswith(("_log", "_wood", "_stem", "_hyphae",
                          "_planks", "_mosaic"))):
        return "wood"
    if n.endswith("_wool"):
        return "wool"
    if n.endswith("_concrete_powder"):
        return "powder"
    if n.endswith("_concrete"):
        return "concrete"
    if "terracotta" in n:
        return "terracotta"
    if (n.endswith("_ore") or "copper" in n or n in (
            "iron_block", "gold_block", "diamond_block", "emerald_block",
            "netherite_block", "lapis_block", "redstone_block",
            "coal_block", "raw_iron_block", "raw_copper_block",
            "raw_gold_block", "amethyst_block", "budding_amethyst")):
        return "metal"
    if "glass" in n:
        return "glass"
    if n in ("ice", "packed_ice", "blue_ice", "frosted_ice",
             "snow_block", "powder_snow"):
        return "ice"
    if n.endswith(("_dirt", "_sand", "_gravel", "_path", "_mud")) \
            or n in ("mud_bricks", "clay", "soul_sand", "soul_soil",
                     "grass_block", "podzol", "mycelium"):
        return "soil"
    return "stone"

# Поверхностные блоки — тот же безопасный пул: поверхность это тоже
# массовая заливка (block entity на каждом блоке поверхности лагает ещё
# хуже стен); «снежные» свойства проставляет _blk()
SURFACE_BLOCKS = PALETTE_BLOCKS

# Полы/потолки ПОДЗЕМНЫХ биомов теперь задаёт таблица АРХЕТИПОВ
# CAVE_ARCHETYPES ниже (главный блок пола + подповерхность + потолок
# + акценты — идентичность «как в ваниле», а не случайный пул; все
# блоки — полные кубы без block entity, глубокие/натёчные палитры
# стали подповерхностями соответствующих архетипов).

# АРХЕТИПЫ ПОДЗЕМНЫХ БИОМОВ — идентичность «как в ваниле» (жалоба:
# «нормальных подземных биомов не оказалось — только спам озёрами и
# структуры; в ваниле есть деление на подземные биоми с крутой
# генерацией — хочу такое в БОЛЬШИНСТВЕ миров»). Каждый архетип —
# узнаваемый ОБРАЗ из трёх частей:
#   floor/sub/ceiling — блоки surface rules: СИЛЬНЫЙ пол (основной блок
#     красит ВСЕ полы пещер биома) + акценты (accent — редкие пятна
#     поверх) + потолочный слой (ceiling=None — без потолка);
#   stone — «тело» биома: catch-all surface rule КРАЙНЕЙ (без условия),
#     весь объём биома, не попавший в полы/потолки/акценты, становится
#     этим камнем (как ванильный deep_dark — весь массив deepslate);
#   carvers — ТЕМАТИЧЕСКИЕ ванильные карверы архетипа: подземный биом
#     ВСЕГДА получает их (дедуп с выданными из общего пула);
#   recipes — СВОИ фичи (4-6 по весам, блоки фиксированы — см.
#     gen_features.rand_cave_features / _CAVE_RECIPE_SPEC); ВИДЫ фич
#     (поле type) у любых двух архетипов пересекаются ≤ 1 — различимость
#     биомов не зависит от рандома;
#   vanilla — 0-2 ванильные placed-фичи «для вкуса» (с вероятностью ~0.7
#     каждая; проверяются placed_fits по высоте мира);
#   mobs — фауна: monsters = ("none",) | ("dark", (lo, hi)) — выборка
#     DARK_MOBS | ("list", [ids], (lo, hi)); ambient_bat / glow_squid —
#     вероятности летучих мышей / светящихся кальмаров (в воде).
# ВАЖНО: блоки пола — только полные кубы БЕЗ block entity (sculk_sensor
# и shrieker НЕ используются: сенсоры — BE, максимум 0-2 через фичу
# sculk_patch с extra_rare_growths; powder_snow — только прожилками-
# фичами, не слоем поверхности). weight — вес архетипа при выборе в
# мир: ванильная тройка (пышная/натёчная/глубокая тьма) — эталон
# крутизны, потому чаще остальных.
CAVE_ARCHETYPES = {
    "lush": {
        "ru": "пышная",
        "stone": ("minecraft:stone", None),
        "carvers": ["minecraft:cave", "minecraft:cave_extra_underground"],
        "floor": ("minecraft:moss_block", None),
        "sub": [("minecraft:dirt", None), ("minecraft:mud", None),
                 ("minecraft:moss_block", None)],
        "accent": [("minecraft:clay", None),
                   ("minecraft:mossy_cobblestone", None)],
        "ceiling": ("minecraft:moss_block", None),
        "recipes": [("cave_vines", 3.0), ("moss_floor", 3.0),
                    ("moss_ceiling", 2.0), ("spore_blossom", 2.0),
                    ("dripleaf", 1.5), ("mossy_boulder", 1.0)],
        "vanilla": ["lush_caves_vegetation", "lush_caves_clay",
                    "classic_vines_cave_feature", "spore_blossom"],
        "mobs": {"monsters": ("dark", (2, 3)), "ambient_bat": 0.6,
                 "glow_squid": 1.0},
        "weight": 2.4,
    },
    "dripstone": {
        "ru": "натёчная",
        "stone": ("minecraft:calcite", None),
        "carvers": ["minecraft:cave", "minecraft:cave_extra_underground"],
        "floor": ("minecraft:dripstone_block", None),
        "sub": [("minecraft:dripstone_block", None),
                 ("minecraft:calcite", None), ("minecraft:tuff", None)],
        "accent": [("minecraft:calcite", None)],
        "ceiling": ("minecraft:dripstone_block", None),
        "recipes": [("dripstone_cluster", 3.0), ("pointed_dripstone", 3.0),
                    ("large_dripstone", 2.0), ("calcite_veins", 1.2)],
        "vanilla": ["large_dripstone"],
        "mobs": {"monsters": ("dark", (2, 4)), "ambient_bat": 0.6,
                 "glow_squid": 0.5},
        "weight": 2.4,
    },
    "deep_dark": {
        "ru": "глубокая тьма",
        # как ванильный deep_dark — весь массив deepslate
        "stone": ("minecraft:deepslate", None),
        # плотная сеть: оба ванильных кавер-карвера (третьего
        # «cave_extra_underground_extra» в 26.2 не существует)
        "carvers": ["minecraft:cave", "minecraft:cave_extra_underground"],
        "floor": ("minecraft:sculk", None),
        "sub": [("minecraft:sculk", None),
                 ("minecraft:deepslate", {"axis": "y"})],
        "accent": [("minecraft:deepslate", {"axis": "y"})],
        "ceiling": ("minecraft:sculk", None),
        "recipes": [("sculk_vein", 3.0), ("sculk_patch", 2.0),
                    ("glow_lichen_rare", 0.7), ("deepslate_veins", 1.0)],
        "vanilla": ["sculk_patch_deep_dark", "monster_room_deep"],
        # как ванильный deep_dark: НИ ОДНОЙ записи спавна (монстров нет —
        # тишина и мрак до первой чужой ошибки)
        "mobs": {"monsters": ("none",), "ambient_bat": 0.0,
                 "glow_squid": 0.0},
        "weight": 2.4,
    },
    "crystal": {
        "ru": "кристальная",
        "stone": ("minecraft:smooth_basalt", None),
        "carvers": ["minecraft:cave", "minecraft:cave_extra_underground"],
        "floor": ("minecraft:calcite", None),
        "sub": [("minecraft:smooth_basalt", None),
                 ("minecraft:calcite", None)],
        "accent": [("minecraft:amethyst_block", None),
                   ("minecraft:smooth_basalt", None)],
        "ceiling": ("minecraft:smooth_basalt", None),
        "recipes": [("amethyst_geode", 3.0), ("amethyst_cluster", 2.5),
                    ("amethyst_veins", 1.5), ("crystal_spikes", 1.0)],
        "vanilla": ["amethyst_geode"],
        "mobs": {"monsters": ("dark", (2, 4)), "ambient_bat": 0.6,
                 "glow_squid": 0.4},
        "weight": 1.0,
    },
    "mushroom": {
        "ru": "грибная",
        "stone": ("minecraft:stone", None),
        "carvers": ["minecraft:cave", "minecraft:cave_extra_underground"],
        "floor": ("minecraft:mycelium", None),
        "sub": [("minecraft:podzol", None), ("minecraft:dirt", None),
                 ("minecraft:mycelium", None)],
        "accent": [("minecraft:mushroom_stem", None)],
        "ceiling": None,
        "recipes": [("huge_brown", 2.5), ("huge_red", 2.5),
                    ("mushroom_patch", 2.0), ("mushroom_fungus", 0.8),
                    ("mycelium_veins", 1.0)],
        "vanilla": [],
        # как грибные поля ванили: без враждебных мобов
        "mobs": {"monsters": ("none",), "ambient_bat": 0.8,
                 "glow_squid": 0.0},
        "weight": 1.0,
    },
    "roots": {
        "ru": "корневая",
        # как ванильный roots — под землёй deepslate
        "stone": ("minecraft:deepslate", None),
        "carvers": ["minecraft:cave", "minecraft:cave_extra_underground"],
        "floor": ("minecraft:rooted_dirt", None),
        "sub": [("minecraft:mud", None), ("minecraft:dirt", None),
                 ("minecraft:rooted_dirt", None)],
        "accent": [("minecraft:pale_moss_block", None),
                   ("minecraft:mud", None)],
        "ceiling": ("minecraft:pale_moss_block", None),
        "recipes": [("root_system", 2.5), ("pale_moss_floor", 2.0),
                    ("pale_moss_ceiling", 1.5),
                    ("cave_vines_classic", 1.2), ("root_dirt_pile", 1.0)],
        "vanilla": ["rooted_azalea_tree", "pale_moss_patch"],
        "mobs": {"monsters": ("dark", (2, 4)), "ambient_bat": 0.6,
                 "glow_squid": 0.4},
        "weight": 1.0,
    },
    "magma": {
        "ru": "магмовая",
        "stone": ("minecraft:basalt", None),
        "carvers": ["minecraft:nether_cave", "minecraft:cave"],
        "floor": ("minecraft:basalt", {"axis": "y"}),
        "sub": [("minecraft:blackstone", None),
                 ("minecraft:basalt", {"axis": "y"})],
        "accent": [("minecraft:magma_block", None),
                   ("minecraft:blackstone", None)],
        "ceiling": ("minecraft:blackstone", None),
        "recipes": [("basalt_columns", 2.5), ("glowstone_blob", 2.5),
                    ("blackstone_veins", 1.5), ("magma_veins", 1.0),
                    ("basalt_pillar", 1.2)],
        "vanilla": ["glowstone", "glowstone_extra",
                    "large_basalt_columns", "small_basalt_columns",
                    "basalt_blobs"],
        "mobs": {"monsters": ("list",
                              ["minecraft:magma_cube", "minecraft:blaze",
                               "minecraft:zombified_piglin"], (2, 3)),
                 "ambient_bat": 0.5, "glow_squid": 0.0},
        "weight": 1.0,
    },
    "frozen": {
        "ru": "замёрзшая",
        # как ванильный frozen_caves — под землёй deepslate
        "stone": ("minecraft:deepslate", None),
        # разреженная сеть: только базовый cave-карвер
        "carvers": ["minecraft:cave"],
        "floor": ("minecraft:packed_ice", None),
        "sub": [("minecraft:packed_ice", None),
                 ("minecraft:blue_ice", None)],
        "accent": [("minecraft:blue_ice", None),
                   ("minecraft:snow_block", None)],
        "ceiling": ("minecraft:packed_ice", None),
        "recipes": [("blue_ice_blob", 2.5), ("snow_piles", 2.0),
                    ("packed_ice_veins", 1.5), ("powder_snow_pockets", 1.0)],
        "vanilla": ["blue_ice"],
        "mobs": {"monsters": ("list",
                              ["minecraft:stray", "minecraft:skeleton",
                               "minecraft:creeper", "minecraft:spider"],
                              (2, 3)),
                 "ambient_bat": 0.8, "glow_squid": 0.0},
        "weight": 1.0,
    },
}
for _ak, _av in CAVE_ARCHETYPES.items():
    # пол — всегда полный куб без block entity и не сыпучий (сыпучие
    # над пустотой void-миров обращаются в entity FALLING_BLOCK);
    # «тело» — тот же класс блоков (массовая заливка всего объёма биома)
    assert _av["floor"][0] not in BE_BLOCK_IDS | FALLING_BLOCK_IDS, _ak
    assert _av["floor"][0] not in _PALETTE_EXCLUDE, _ak
    assert _av["stone"][0] not in BE_BLOCK_IDS | FALLING_BLOCK_IDS, _ak
    assert _av["stone"][0] not in _PALETTE_EXCLUDE, _ak
    assert len(_av["recipes"]) >= 4, _ak
    assert _av["mobs"]["monsters"][0] in ("none", "dark", "list"), _ak
# ВИДЫ фич (type) любых двух архетипов пересекаются ≤ 1 — различимость
# биомов (инвариант _rand_biome_features) не зависит от рандома, т.к.
# набор архетипа фиксирован и фильтром не перегенерируется
def _arch_feature_types(arch):
    import gen_features as _gf
    return {_gf._CAVE_RECIPE_TYPE[r] for r, _w in arch["recipes"]}
_arch_ids = sorted(CAVE_ARCHETYPES)
for _i, _a1 in enumerate(_arch_ids):
    for _a2 in _arch_ids[_i + 1:]:
        _sh = _arch_feature_types(CAVE_ARCHETYPES[_a1]) \
            & _arch_feature_types(CAVE_ARCHETYPES[_a2])
        assert len(_sh) <= 1, \
            "архетипы %s и %s делят виды фич: %s" % (_a1, _a2, sorted(_sh))

# Ванильные блок-теги спавна (все 13 из jar 26.2): SpawnPlacements почти
# каждого «наземного» моба требует, чтобы блок пола состоял в СВОЁМ теге —
# animals_spawnable_on = только grass_block, bats = stone, mooshrooms =
# mycelium, camels = sand, wolves = grass/снег/подзол и т.д. Поверхности
# наших измерений — случайные блоки, поэтому генератор ДОПОЛНЯЕТ эти теги
# поверхностными блоками (файлы data/minecraft/tags/block/<tag>.json со
# values БЕЗ replace — значения добавляются К ванильным, стандартная
# механика тегов датапаков). См. write_spawnable_tags().
SPAWNABLE_TAGS = [
    "animals_spawnable_on", "armadillo_spawnable_on",
    "axolotls_spawnable_on", "bats_spawnable_on", "camels_spawnable_on",
    "foxes_spawnable_on", "frogs_spawnable_on", "goats_spawnable_on",
    "mooshrooms_spawnable_on", "parrots_spawnable_on",
    "polar_bears_spawnable_on_alternate", "rabbits_spawnable_on",
    "wolves_spawnable_on",
]

# Какие блоки допустимы в спавн-тегах: только полные кубы без block
# entity (тот же критерий, что у PALETTE_BLOCKS — поверхность и есть
# массовая заливка) плюс bedrock (дно/кровля мира). Поверхностные слои
# и так берутся из этого пула — фильтр страхует от будущих изменений
# генератора поверхности (block entity и не-полные блоки в спавн-теге
# бессмысленны).
_SPAWN_TAG_SAFE_IDS = {b[0] for b in PALETTE_BLOCKS} | {"minecraft:bedrock"}

# «Жидкость» мира: почти всегда вода/лава/воздух, порошковый снег — редко.
# Совсем безумный вариант (случайный твёрдый блок вместо моря) добавляется
# в месте выбора с шансом ~1.5%.
FLUIDS = ([("minecraft:water", {"level": "0"})] * 45
          + [("minecraft:lava", {"level": "0"})] * 35
          + [("minecraft:air", None)] * 15
          + [("minecraft:powder_snow", None)] * 4)

INFINIBURN = ["#minecraft:infiniburn_overworld", "#minecraft:infiniburn_nether",
              "#minecraft:infiniburn_end"]

TIMELINE_TAGS = ["#minecraft:in_overworld", "#minecraft:in_nether",
                 "#minecraft:in_end"]

# Ванильные configured_carver'ы из jar 26.2 (biome.carvers — строка ИЛИ список).
# Карверы 26.2 регистрируются КОДОМ (net.minecraft.data.worldgen.Carvers)
# с фиксированными якорями высот; якорь below_top(v) резолвится в top-1-v,
# above_bottom(v) — в min_y+v. Если resolved_min > resolved_max, на каждый
# чанк биома печатается WARN «Empty height range» — фильтруем по границам:
# (min_y, top) конкретного измерения.
CARVER_BOUNDS = {
    # [above_bottom(8), absolute(180)]
    "minecraft:cave": lambda min_y, top: min_y + 8 <= 180,
    # [above_bottom(8), absolute(47)]
    "minecraft:cave_extra_underground": lambda min_y, top: min_y + 8 <= 47,
    # [absolute(10), absolute(67)] — пустым быть не может
    "minecraft:canyon": lambda min_y, top: True,
    # [absolute(0), below_top(1)] — пуст при top < 2
    "minecraft:nether_cave": lambda min_y, top: top >= 2,
}
CARVERS = sorted(CARVER_BOUNDS)
# тематические карверы архетипов — только существующие ванильные ID 26.2
for _ak, _av in CAVE_ARCHETYPES.items():
    assert all(c in CARVER_BOUNDS for c in _av["carvers"]), _ak

# ПОДЗЕМНАЯ depth-зона: первая полоса начинается с CAVE_BAND_TOP (как в
# ваниле — пещерные биома сразу под поверхностью, без тонкой прослойки
# поверхностных биомов), последняя кончается у CAVE_BAND_BOTTOM (дно).
# ОДНА пара констант используется везде: generate() (тайлинг полос),
# _biome_source_multi_noise (докстринг/фолбэк) и самотест.
CAVE_BAND_TOP = 0.2
CAVE_BAND_BOTTOM = 1.45

GRASS_COLOR_MODIFIERS = ["swamp", "dark_forest"]

# Частицы ambient_particles, реально используемые ванильными биомами 26.2
AMBIENT_PARTICLES = ["minecraft:white_ash", "minecraft:ash",
                     "minecraft:crimson_spore", "minecraft:warped_spore"]

# Фоновая музыка из ванильных биомов 26.2
MUSIC_IDS = [
    "minecraft:music.game", "minecraft:music.nether.nether_wastes",
    "minecraft:music.nether.basalt_deltas", "minecraft:music.nether.crimson_forest",
    "minecraft:music.nether.soul_sand_valley", "minecraft:music.nether.warped_forest",
    "minecraft:music.overworld.badlands", "minecraft:music.overworld.bamboo_jungle",
    "minecraft:music.overworld.cherry_grove", "minecraft:music.overworld.deep_dark",
    "minecraft:music.overworld.desert", "minecraft:music.overworld.dripstone_caves",
    "minecraft:music.overworld.flower_forest", "minecraft:music.overworld.forest",
    "minecraft:music.overworld.frozen_peaks", "minecraft:music.overworld.grove",
    "minecraft:music.overworld.jagged_peaks", "minecraft:music.overworld.jungle",
    "minecraft:music.overworld.lush_caves", "minecraft:music.overworld.meadow",
    "minecraft:music.overworld.old_growth_taiga", "minecraft:music.overworld.snowy_slopes",
    "minecraft:music.overworld.sparse_jungle", "minecraft:music.overworld.stony_peaks",
    "minecraft:music.overworld.sulfur_caves", "minecraft:music.overworld.swamp",
]

# ambient_sounds из ванильных биомов: loop/additions/mood с общим префиксом
AMBIENT_SOUND_BASES = ["minecraft:ambient.crimson_forest",
                       "minecraft:ambient.warped_forest",
                       "minecraft:ambient.nether_wastes",
                       "minecraft:ambient.soul_sand_valley",
                       "minecraft:ambient.basalt_deltas"]

# Мобы по категориям и тирам «странности» (вес, [сущности]) — чем страннее
# моб, тем реже попадает в спавнеры. Список сверен с lang-файлом jar 26.2;
# не-Mob сущности (лодки, стрелы, таблички-дисплеи...) не включаем —
# движок их через натуральный спавн не создаёт. «misc» пуст: в этой
# категории натуральный спавн не работает. ОСТОРОЖНО: killer_bunny есть
# в lang-файле, но это НЕ entity type (вариант кролика) — сервер падает
# с "Unknown registry key ... entity_type".
#
# !!! ПЕРЕД ДОБАВЛЕНИЕМ НОВОГО МОБА В SPAWN_POOLS — ДВЕ ПРОВЕРКИ по
# байткоду jar 26.2 (javap):
#   1. Реестр SpawnPlacements (javap net.minecraft.world.entity.
#      SpawnPlacements): моб ОБЯЗАН иметь зарегистрированные правила
#      спавна. Если записи НЕТ — checkSpawnRules возвращает TRUE без
#      проверок (свет/поверхность/вода игнорируются) и моб спавнится
#      БЕЗ ограничений: в воздухе, тысячами, без капа (баг юзера:
#      allay/tadpole/zombie_nautilus копились в воздухе). Из-за этого
#      здесь НЕТ: allay, tadpole, zombie_nautilus, bee, sniffer,
#      copper_golem, piglin_brute.
#   2. Истинная категория из EntityTypes: моб кладём ТОЛЬКО в список
#      его СОБСТВЕННОЙ категории. Моб в ЧУЖОМ списке обходит моб-кап
#      (кап считается по MobCategory самой сущности) → бесконечное
#      накопление. Категория MISC для натурального спавна не работает
#      вовсе (из-за этого здесь нет villager/iron_golem/snow_golem).
SPAWN_POOLS = {
    # parrot убран из ambient: истинная категория CREATURE (в чужом списке
    # обходится моб-кап) — остался в creature тир10
    # ВЕСА ТИРОВ (жалобы: «обычных мобов/животных больше, боссы слишком
    # часты»): обычные 16→24, средние 8→10; боссы — отдельный тир 0.1
    # (в 10 раз реже прежнего веса 1, см. BOSS_MOBS ниже)
    "ambient": [(24, ["minecraft:bat"])],
    # после удаления tadpole (нет правил спавна) остаётся один axolotl — ок
    "axolotls": [(24, ["minecraft:axolotl"])],
    "creature": [
        (24, ["minecraft:cow", "minecraft:pig", "minecraft:sheep",
              "minecraft:chicken", "minecraft:horse", "minecraft:rabbit",
              "minecraft:fox", "minecraft:wolf"]),
        # frog вынесена из «тира 8» в собственный тир с малым весом
        # (жалоба: лягушки появлялись на поверхности слишком часто);
        # ocelot: истинная категория CREATURE (в ванильных биомах он в
        # monster-списках, но это их причуда — здесь кладём по категории)
        (10, ["minecraft:goat", "minecraft:donkey", "minecraft:mule",
             "minecraft:llama", "minecraft:mooshroom", "minecraft:ocelot",
             "minecraft:cat", "minecraft:panda", "minecraft:polar_bear",
             "minecraft:turtle", "minecraft:armadillo",
             "minecraft:camel", "minecraft:strider", "minecraft:parrot"]),
        # убраны: sniffer/copper_golem/allay (нет правил спавна),
        # iron_golem/snow_golem (MISC), zombie_horse (истинно MONSTER)
        (4, ["minecraft:happy_ghast", "minecraft:wandering_trader",
             "minecraft:trader_llama", "minecraft:skeleton_horse"]),
        (2, ["minecraft:frog"]),
    ],
    "misc": [],
    "monster": [
        (24, ["minecraft:zombie", "minecraft:skeleton",
              "minecraft:creeper", "minecraft:spider",
              "minecraft:zombie_villager", "minecraft:husk",
              "minecraft:stray", "minecraft:drowned", "minecraft:slime",
              "minecraft:enderman", "minecraft:cave_spider",
              "minecraft:witch", "minecraft:zombified_piglin"]),
        # убраны: piglin_brute (нет правил спавна), skeleton_horse
        # (истинно CREATURE — остался в creature тир4)
        (10, ["minecraft:magma_cube", "minecraft:silverfish",
             "minecraft:endermite", "minecraft:blaze", "minecraft:ghast",
             "minecraft:piglin", "minecraft:hoglin", "minecraft:bogged",
             "minecraft:phantom", "minecraft:guardian",
             "minecraft:wither_skeleton", "minecraft:shulker",
             "minecraft:creaking", "minecraft:parched",
             "minecraft:sulfur_cube", "minecraft:zombie_horse"]),
        # убран zombie_nautilus (нет правил спавна)
        (4, ["minecraft:giant", "minecraft:ravager", "minecraft:evoker",
             "minecraft:vindicator", "minecraft:pillager",
             "minecraft:vex", "minecraft:zoglin", "minecraft:breeze",
             "minecraft:elder_guardian"]),
        (2, ["minecraft:illusioner", "minecraft:camel_husk"]),
        # БОССЫ: дракон/визер/варден — вес 0.1, в 10 раз реже прежнего
        # веса 1 (жалоба: появляются слишком часто). _deal_mobs по весу
        # < 1 заносит их в фауну только 1 из 10 миров, в биомных спавнерах
        # — минимальная запись weight 1 группой в 1 (см. BOSS_MOBS)
        (0.1, ["minecraft:wither", "minecraft:ender_dragon",
               "minecraft:warden"]),
    ],
    # убраны: axolotl (истинно AXOLOTLS), nautilus (истинно
    # WATER_CREATURE), tadpole/zombie_nautilus (нет правил спавна)
    "underground_water_creature": [
        (24, ["minecraft:glow_squid"]),
    ],
    "water_ambient": [
        # рыбы — отдельный тир с малым весом (жалоба: поверхность кишела
        # рыбой; раньше тир с весом 16 выбирался почти всегда); редкие
        # tropical_fish/pufferfish — ещё реже, чем cod/salmon.
        # Убраны из чужого списка: tadpole/axolotl/nautilus/zombie_nautilus
        (4, ["minecraft:cod", "minecraft:salmon"]),
        (2, ["minecraft:pufferfish", "minecraft:tropical_fish"]),
    ],
    # убраны: glow_squid (истинно UNDERGROUND_WATER_CREATURE), turtle
    # (истинно CREATURE), guardian/elder_guardian (истинно MONSTER),
    # tadpole/zombie_nautilus (нет правил спавна)
    "water_creature": [
        (24, ["minecraft:squid", "minecraft:dolphin"]),
        (4, ["minecraft:nautilus"]),
    ],
}

# Мобы-«боссы» (тир весом 0.1 в SPAWN_POOLS["monster"]): в 10 раз реже
# прежнего веса 1 — _deal_mobs по весу < 1 заносит их в фауну мира с
# шансом 0.1, а в биомных спавнерах они всегда получают МИНИМАЛЬНУЮ
# запись: weight 1, группа ровно из 1 (стая визеров у точки спавна —
# не сюжет). Эндер-дракон дополнительно скриптовый (см.
# has_ender_dragon_fight), но натуральный спавн тоже урезан.
BOSS_MOBS = {"minecraft:wither", "minecraft:ender_dragon",
             "minecraft:warden"}


# Whitelist «моб -> его ИСТИННАЯ MobCategory» для SPAWN_POOLS. Сверено по
# байткоду jar 26.2 (реестр SpawnPlacements + EntityTypes): моб в этом
# словаре (а) имеет зарегистрированные правила спавна (незарегистрированные
# проходят checkSpawnRules == TRUE без проверок света/поверхности/воды и
# спавнятся в воздухе без капа), (б) состоит ТОЛЬКО в списке своей
# категории (моб в чужом списке обходит моб-кап этой категории).
# Проверяется при импорте функцией _validate_spawn_pools() ниже.
SPAWNABLE_MOBS = {
    # ambient
    "minecraft:bat": "ambient",
    # axolotls
    "minecraft:axolotl": "axolotls",
    # creature
    "minecraft:cow": "creature", "minecraft:pig": "creature",
    "minecraft:sheep": "creature", "minecraft:chicken": "creature",
    "minecraft:horse": "creature", "minecraft:rabbit": "creature",
    "minecraft:fox": "creature", "minecraft:wolf": "creature",
    "minecraft:goat": "creature", "minecraft:donkey": "creature",
    "minecraft:mule": "creature", "minecraft:llama": "creature",
    "minecraft:mooshroom": "creature", "minecraft:ocelot": "creature",
    "minecraft:cat": "creature", "minecraft:panda": "creature",
    "minecraft:polar_bear": "creature", "minecraft:turtle": "creature",
    "minecraft:armadillo": "creature", "minecraft:camel": "creature",
    "minecraft:strider": "creature", "minecraft:parrot": "creature",
    "minecraft:happy_ghast": "creature", "minecraft:frog": "creature",
    "minecraft:wandering_trader": "creature",
    "minecraft:trader_llama": "creature",
    "minecraft:skeleton_horse": "creature",
    # monster
    "minecraft:zombie": "monster", "minecraft:skeleton": "monster",
    "minecraft:creeper": "monster", "minecraft:spider": "monster",
    "minecraft:zombie_villager": "monster", "minecraft:husk": "monster",
    "minecraft:stray": "monster", "minecraft:drowned": "monster",
    "minecraft:slime": "monster", "minecraft:enderman": "monster",
    "minecraft:cave_spider": "monster", "minecraft:witch": "monster",
    "minecraft:zombified_piglin": "monster",
    "minecraft:magma_cube": "monster", "minecraft:silverfish": "monster",
    "minecraft:endermite": "monster", "minecraft:blaze": "monster",
    "minecraft:ghast": "monster", "minecraft:piglin": "monster",
    "minecraft:hoglin": "monster", "minecraft:bogged": "monster",
    "minecraft:phantom": "monster", "minecraft:guardian": "monster",
    "minecraft:wither_skeleton": "monster", "minecraft:shulker": "monster",
    "minecraft:creaking": "monster", "minecraft:parched": "monster",
    "minecraft:sulfur_cube": "monster", "minecraft:zombie_horse": "monster",
    "minecraft:giant": "monster", "minecraft:ravager": "monster",
    "minecraft:evoker": "monster", "minecraft:vindicator": "monster",
    "minecraft:pillager": "monster", "minecraft:vex": "monster",
    "minecraft:zoglin": "monster", "minecraft:breeze": "monster",
    "minecraft:elder_guardian": "monster",
    "minecraft:illusioner": "monster", "minecraft:warden": "monster",
    "minecraft:camel_husk": "monster",
    "minecraft:wither": "monster", "minecraft:ender_dragon": "monster",
    # water_ambient
    "minecraft:cod": "water_ambient", "minecraft:salmon": "water_ambient",
    "minecraft:pufferfish": "water_ambient",
    "minecraft:tropical_fish": "water_ambient",
    # water_creature
    "minecraft:squid": "water_creature", "minecraft:dolphin": "water_creature",
    "minecraft:nautilus": "water_creature",
    # underground_water_creature
    "minecraft:glow_squid": "underground_water_creature",
}


def _validate_spawn_pools():
    """Юнит-проверка SPAWN_POOLS (выполняется при импорте): каждый моб
    (а) есть в whitelist SPAWNABLE_MOBS (т.е. зарегистрирован в реестре
    SpawnPlacements 26.2 и разрешён для натурального спавна),
    (б) состоит ТОЛЬКО в списке своей истинной категории — иначе он
    обходит моб-кап и копится бесконечно (баг юзера)."""
    for cat, tiers in SPAWN_POOLS.items():
        for _w, mobs in tiers:
            for mob in mobs:
                if mob not in SPAWNABLE_MOBS:
                    raise AssertionError(
                        "SPAWN_POOLS: моб %s не в whitelist SPAWNABLE_MOBS "
                        "(нет зарегистрированных правил спавна или неизвестен "
                        "javap-проверке 26.2) — он будет спавниться без "
                        "ограничений; убери его" % mob)
                if SPAWNABLE_MOBS[mob] != cat:
                    raise AssertionError(
                        "SPAWN_POOLS: моб %s в списке «%s», но его истинная "
                        "категория «%s» — моб в чужом списке обходит "
                        "моб-кап; положи его только в родной список"
                        % (mob, cat, SPAWNABLE_MOBS[mob]))


_validate_spawn_pools()

# Тёмные мобы ПОДЗЕМНЫХ биомов — пещерная фауна: подземные биомы
# гарантированно получают 2-4 из них поверх своей разбивки _deal_mobs
# (в пещерах не должно быть пусто и коров). Каждый моб — категории
# monster из whitelist SPAWNABLE_MOBS: правила спавна зарегистрированы,
# спавн только в темноте (свет <= monster_spawn_light_level измерения)
DARK_MOBS = [
    "minecraft:zombie", "minecraft:skeleton", "minecraft:creeper",
    "minecraft:spider", "minecraft:cave_spider", "minecraft:silverfish",
    "minecraft:endermite", "minecraft:slime", "minecraft:enderman",
    "minecraft:witch", "minecraft:husk", "minecraft:stray",
    "minecraft:bogged", "minecraft:drowned",
]
for _m in DARK_MOBS:
    assert SPAWNABLE_MOBS.get(_m) == "monster", \
        "DARK_MOBS: %s не монстр из whitelist SPAWNABLE_MOBS" % _m


def _sample_mobs(rng, tiers, k):
    """k уникальных мобов: сначала тир по весу (странное — реже), потом моб."""
    weights = [w for w, _ in tiers]
    out, seen = [], set()
    guard = k * 12 + 24
    while len(out) < k and guard > 0:
        guard -= 1
        m = rng.choice(rng.choices(tiers, weights=weights)[0][1])
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


def _deal_mobs(rng, n_biomes):
    """Разложить мобов по биомам: каждый моб достаётся 1-2 биомам, у
    каждого биома СВОЙ набор фауны (пер-биомная идентичность; раньше все
    биомы брали выборку из одного общего пула — «везде одно и то же»).
    Вес тира здесь тоже работает: мобы с весом >= 1 раздаются ВСЕГДА
    (как раньше), а «боссы» (вес 0.1 — визер/дракон/варден) попадают
    в фауну мира с шансом 0.1 — в 10 раз реже прежнего веса 1 (жалоба:
    «слишком часто появляются»).
    Возвращает список {категория: [мобы]} по индексу биома."""
    dealt = [dict() for _ in range(n_biomes)]
    for cat, tiers in SPAWN_POOLS.items():
        if not tiers:
            continue
        pairs = [(m, w) for w, ms in tiers for m in ms]
        rng.shuffle(pairs)
        for m, w in pairs:
            # тир с весом < 1 («боссы») — редкий гость: 9 из 10 миров
            # вообще без него
            if w < 1.0 and rng.random() >= w:
                continue
            # 1 биом — три четверти мобов, 2 биома — четверть (для редких
            # пересечений фауны, как зомби и в пустыне, и в лесу)
            k = min(n_biomes, 1 if rng.random() < 0.75 else 2)
            for b in rng.sample(range(n_biomes), k):
                dealt[b].setdefault(cat, []).append(m)
    return dealt


# Водные стайные категории: maxCount спавнера жёстко урезаем (жалоба:
# слишком частые стаи рыб/лягушек на поверхности)
WATERY_SPAWN_CATS = {"water_ambient", "water_creature",
                     "underground_water_creature", "axolotls"}

# Ванильные placed features из jar 26.2 (без end/void-специфичных)
PLACED_FEATURES = [
    "acacia", "acacia_checked", "amethyst_geode", "bamboo", "bamboo_light",
    "bamboo_vegetation", "basalt_blobs", "basalt_pillar", "birch_bees_0002",
    "birch_bees_0002_leaf_litter", "birch_bees_002", "birch_checked",
    "birch_leaf_litter", "birch_tall", "blackstone_blobs", "blue_ice",
    "brown_mushroom_nether", "brown_mushroom_normal", "brown_mushroom_old_growth",
    "brown_mushroom_swamp", "brown_mushroom_taiga", "cave_vines",
    "cherry_bees_005", "cherry_checked", "classic_vines_cave_feature",
    "crimson_forest_vegetation", "crimson_fungi", "dark_forest_vegetation",
    "dark_oak_checked", "dark_oak_leaf_litter", "delta", "desert_well",
    "disk_clay", "disk_grass", "disk_gravel", "disk_sand", "dripstone_cluster",
    "fallen_birch_tree", "fallen_jungle_tree", "fallen_oak_tree",
    "fallen_spruce_tree", "fallen_super_birch_tree", "fancy_oak_bees",
    "fancy_oak_bees_0002_leaf_litter", "fancy_oak_bees_002",
    "fancy_oak_checked", "fancy_oak_leaf_litter", "flower_cherry",
    "flower_default", "flower_flower_forest", "flower_forest_flowers",
    "flower_meadow", "flower_pale_garden", "flower_plain", "flower_plains",
    "flower_swamp", "flower_warm", "forest_flowers", "forest_rock",
    "fossil_lower", "fossil_upper", "freeze_top_layer", "glow_lichen",
    "glowstone", "glowstone_extra", "grass_bonemeal", "ice_patch", "ice_spike",
    "iceberg_blue", "iceberg_packed", "jungle_bush", "jungle_tree", "kelp_cold",
    "kelp_warm", "lake_lava_surface", "lake_lava_underground",
    "large_basalt_columns", "large_dripstone", "lush_caves_ceiling_vegetation",
    "lush_caves_clay", "lush_caves_vegetation", "mangrove_checked",
    "mega_jungle_tree_checked", "mega_pine_checked", "mega_spruce_checked",
    "monster_room", "monster_room_deep", "mushroom_island_vegetation",
    "nether_sprouts", "oak", "oak_bees_0002_leaf_litter", "oak_bees_002",
    "oak_checked", "oak_leaf_litter", "ore_ancient_debris_large",
    "ore_andesite_lower", "ore_andesite_upper", "ore_blackstone", "ore_clay",
    "ore_coal_lower", "ore_coal_upper", "ore_copper", "ore_copper_large",
    "ore_debris_small", "ore_diamond", "ore_diamond_buried", "ore_diamond_large",
    "ore_diamond_medium", "ore_diorite_lower", "ore_diorite_upper", "ore_dirt",
    "ore_emerald", "ore_gold", "ore_gold_deltas", "ore_gold_extra",
    "ore_gold_lower", "ore_gold_nether", "ore_granite_lower", "ore_granite_upper",
    "ore_gravel", "ore_gravel_nether", "ore_infested", "ore_iron_middle",
    "ore_iron_small", "ore_iron_upper", "ore_lapis", "ore_lapis_buried",
    "ore_magma", "ore_quartz_deltas", "ore_quartz_nether", "ore_redstone",
    "ore_redstone_lower", "ore_soul_sand", "ore_tuff", "pale_garden_flowers",
    "pale_garden_vegetation", "pale_moss_patch", "pale_oak_checked",
    "pale_oak_creaking_checked", "patch_berry_bush", "patch_berry_common",
    "patch_berry_rare", "patch_bush", "patch_cactus", "patch_cactus_decorated",
    "patch_cactus_desert", "patch_crimson_roots", "patch_dead_bush",
    "patch_dead_bush_2", "patch_dead_bush_badlands", "patch_dry_grass_badlands",
    "patch_dry_grass_desert", "patch_fire", "patch_firefly_bush_near_water",
    "patch_firefly_bush_near_water_swamp", "patch_firefly_bush_swamp",
    "patch_grass_badlands", "patch_grass_forest", "patch_grass_jungle",
    "patch_grass_meadow", "patch_grass_normal", "patch_grass_plain",
    "patch_grass_savanna", "patch_grass_taiga", "patch_grass_taiga_2",
    "patch_large_fern", "patch_leaf_litter", "patch_melon", "patch_melon_sparse",
    "patch_pumpkin", "patch_soul_fire", "patch_sugar_cane",
    "patch_sugar_cane_badlands", "patch_sugar_cane_desert",
    "patch_sugar_cane_swamp", "patch_sunflower", "patch_taiga_grass",
    "patch_tall_grass", "patch_tall_grass_2", "patch_waterlily", "pile_hay",
    "pile_ice", "pile_melon", "pile_pumpkin", "pile_snow", "pine", "pine_checked",
    "pine_on_snow", "pointed_dripstone", "red_mushroom_nether",
    "red_mushroom_normal", "red_mushroom_old_growth", "red_mushroom_swamp",
    "red_mushroom_taiga", "rooted_azalea_tree", "rooted_sulfur_spring",
    "sculk_patch_ancient_city", "sculk_patch_deep_dark", "sculk_vein",
    "sea_pickle", "seagrass_cold", "seagrass_deep", "seagrass_deep_cold",
    "seagrass_deep_warm", "seagrass_normal", "seagrass_river", "seagrass_swamp",
    "seagrass_warm", "small_basalt_columns", "spore_blossom", "spring_closed",
    "spring_closed_double", "spring_delta", "spring_lava", "spring_lava_frozen",
    "spring_open", "spring_water", "spruce", "spruce_checked", "spruce_on_snow",
    "sulfur_pool", "sulfur_spike", "sulfur_spike_cluster", "super_birch_bees",
    "super_birch_bees_0002", "tall_mangrove_checked", "trees_badlands",
    "trees_birch", "trees_birch_and_oak_leaf_litter", "trees_cherry",
    "trees_flower_forest", "trees_grove", "trees_jungle", "trees_mangrove",
    "trees_meadow", "trees_old_growth_pine_taiga",
    "trees_old_growth_spruce_taiga", "trees_plains", "trees_savanna",
    "trees_snowy", "trees_sparse_jungle", "trees_swamp", "trees_taiga",
    "trees_water", "trees_windswept_forest", "trees_windswept_hills",
    "trees_windswept_savanna", "twisting_vines", "underwater_magma", "vines",
    "warm_ocean_vegetation", "warped_forest_vegetation", "warped_fungi",
    "weeping_vines", "wildflowers_birch_forest", "wildflowers_meadow",
]

# Ванильные placed-фичи, кладущие СЫПУЧИЕ блоки (диски песка/гравия,
# гравийные жилы): в void-мирах исключаются из биомных пулов — падающий
# блок над пустотой обращается в entity FALLING_BLOCK (см.
# FALLING_BLOCK_IDS). ore_soul_sand НЕ входит: soul_sand — не сыпучий.
VOID_UNSAFE_PLACED = {"disk_sand", "disk_gravel", "ore_gravel",
                      "ore_gravel_nether"}

# Ванильные placed-фичи с height_range в placement (скан jar 26.2):
# имя -> ((якорь_min, val), (якорь_max, val)); якорь 'a' = absolute,
# 'b' = above_bottom (min_y+v), 't' = below_top (top-1-v). Диапазон,
# пустой или целиком вне [min_y, top) измерения, даёт WARN «Empty height
# range» — такие фичи не семплируем в биомы этого измерения.
PLACED_BOUNDS = {
    "amethyst_geode": (("b", 6), ("a", 30)),
    "basalt_blobs": (("b", 0), ("t", 0)),
    "basalt_pillar": (("b", 0), ("t", 0)),
    "blackstone_blobs": (("b", 0), ("t", 0)),
    "blue_ice": (("a", 30), ("a", 61)),
    "brown_mushroom_nether": (("b", 0), ("t", 0)),
    "cave_vines": (("b", 0), ("a", 256)),
    "classic_vines_cave_feature": (("b", 0), ("a", 256)),
    "dripstone_cluster": (("b", 0), ("a", 256)),
    "end_island_decorated": (("a", 55), ("a", 70)),
    "fossil_lower": (("b", 0), ("a", -8)),
    "fossil_upper": (("a", 0), ("t", 0)),
    "glow_lichen": (("b", 0), ("a", 256)),
    "glowstone": (("b", 0), ("t", 0)),
    "glowstone_extra": (("b", 4), ("t", 4)),
    "lake_lava_underground": (("a", 0), ("t", 0)),
    "large_dripstone": (("b", 0), ("a", 256)),
    "lush_caves_ceiling_vegetation": (("b", 0), ("a", 256)),
    "lush_caves_clay": (("b", 0), ("a", 256)),
    "lush_caves_vegetation": (("b", 0), ("a", 256)),
    "monster_room": (("a", 0), ("t", 0)),
    "monster_room_deep": (("b", 6), ("a", -1)),
    "ore_ancient_debris_large": (("a", 8), ("a", 24)),
    "ore_andesite_lower": (("a", 0), ("a", 60)),
    "ore_andesite_upper": (("a", 64), ("a", 128)),
    "ore_blackstone": (("a", 5), ("a", 31)),
    "ore_clay": (("b", 0), ("a", 256)),
    "ore_coal_lower": (("a", 0), ("a", 192)),
    "ore_coal_upper": (("a", 136), ("t", 0)),
    "ore_copper": (("a", -16), ("a", 112)),
    "ore_copper_large": (("a", -16), ("a", 112)),
    "ore_debris_small": (("b", 8), ("t", 8)),
    "ore_diamond": (("b", -80), ("b", 80)),
    "ore_diamond_buried": (("b", -80), ("b", 80)),
    "ore_diamond_large": (("b", -80), ("b", 80)),
    "ore_diamond_medium": (("a", -64), ("a", -4)),
    "ore_diorite_lower": (("a", 0), ("a", 60)),
    "ore_diorite_upper": (("a", 64), ("a", 128)),
    "ore_dirt": (("a", 0), ("a", 160)),
    "ore_emerald": (("a", -16), ("a", 480)),
    "ore_gold": (("a", -64), ("a", 32)),
    "ore_gold_deltas": (("b", 10), ("t", 10)),
    "ore_gold_extra": (("a", 32), ("a", 256)),
    "ore_gold_lower": (("a", -64), ("a", -48)),
    "ore_gold_nether": (("b", 10), ("t", 10)),
    "ore_granite_lower": (("a", 0), ("a", 60)),
    "ore_granite_upper": (("a", 64), ("a", 128)),
    "ore_gravel": (("b", 0), ("t", 0)),
    "ore_gravel_nether": (("a", 5), ("a", 41)),
    "ore_infested": (("b", 0), ("a", 63)),
    "ore_iron_middle": (("a", -24), ("a", 56)),
    "ore_iron_small": (("b", 0), ("a", 72)),
    "ore_iron_upper": (("a", 80), ("a", 384)),
    "ore_lapis": (("a", -32), ("a", 32)),
    "ore_lapis_buried": (("b", 0), ("a", 64)),
    "ore_magma": (("a", 27), ("a", 36)),
    "ore_quartz_deltas": (("b", 10), ("t", 10)),
    "ore_quartz_nether": (("b", 10), ("t", 10)),
    "ore_redstone": (("b", 0), ("a", 15)),
    "ore_redstone_lower": (("b", -32), ("b", 32)),
    "ore_soul_sand": (("b", 0), ("a", 31)),
    "ore_tuff": (("b", 0), ("a", 0)),
    "patch_crimson_roots": (("b", 0), ("t", 0)),
    "patch_fire": (("b", 4), ("t", 4)),
    "patch_soul_fire": (("b", 4), ("t", 4)),
    "pointed_dripstone": (("b", 0), ("a", 256)),
    "red_mushroom_nether": (("b", 0), ("t", 0)),
    "rooted_azalea_tree": (("b", 0), ("a", 256)),
    "rooted_sulfur_spring": (("b", 0), ("a", 256)),
    "sculk_patch_deep_dark": (("b", 0), ("a", 256)),
    "sculk_vein": (("b", 0), ("a", 256)),
    "spore_blossom": (("b", 0), ("a", 256)),
    "spring_closed": (("b", 10), ("t", 10)),
    "spring_closed_double": (("b", 10), ("t", 10)),
    "spring_delta": (("b", 4), ("t", 4)),
    "spring_lava": (("b", 0), ("t", 8)),
    "spring_lava_frozen": (("b", 0), ("t", 8)),
    "spring_open": (("b", 4), ("t", 4)),
    "spring_water": (("b", 0), ("a", 192)),
    "sulfur_pool": (("b", 0), ("a", 256)),
    "sulfur_spike": (("b", 0), ("a", 256)),
    "sulfur_spike_cluster": (("b", 0), ("a", 256)),
    "twisting_vines": (("b", 0), ("t", 0)),
    "underwater_magma": (("b", 0), ("a", 256)),
    "vines": (("a", 64), ("a", 100)),
    "weeping_vines": (("b", 0), ("t", 0)),
}


def placed_fits(name, min_y, top):
    """Непустой ли height_range фичи и пересекает ли мир [min_y, top)."""
    b = PLACED_BOUNDS.get(name)
    if b is None:
        return True

    def res(k, v):
        return v if k == "a" else (min_y + v if k == "b" else top - 1 - v)

    (lk, lv), (hk, hv) = b
    lo, hi = res(lk, lv), res(hk, hv)
    return lo <= hi and hi >= min_y and lo < top

# Ванильные placed-фичи для ПОДЗЕМНЫХ биомов: пещерная флора и декорации,
# которые размещаются height_range/count_on_every_layer и не требуют ни
# неба, ни поверхности (glow_lichen, sculk, натёки, жеоды, комнаты
# монстров, подземные озёра/источники, незер-флора). placed_fits выше
# дополнительно отсекает фичи с высотными диапазонами вне границ
# конкретного измерения.
CAVE_PLACED_FEATURES = [
    "amethyst_geode", "basalt_blobs", "basalt_pillar", "blackstone_blobs",
    "brown_mushroom_nether", "cave_vines", "classic_vines_cave_feature",
    "delta", "dripstone_cluster", "fossil_lower", "fossil_upper",
    "glow_lichen", "glowstone", "glowstone_extra", "large_basalt_columns",
    "large_dripstone", "lush_caves_ceiling_vegetation", "lush_caves_clay",
    "lush_caves_vegetation", "monster_room", "monster_room_deep",
    "nether_sprouts", "patch_crimson_roots", "pointed_dripstone",
    "red_mushroom_nether", "rooted_azalea_tree", "rooted_sulfur_spring",
    "sculk_patch_deep_dark", "sculk_vein", "small_basalt_columns",
    "spore_blossom", "spring_closed", "spring_closed_double",
    "spring_lava", "spring_open", "sulfur_pool", "sulfur_spike",
    "sulfur_spike_cluster", "twisting_vines", "underwater_magma",
    "lake_lava_underground", "vines", "weeping_vines",
]

# «ОЗЁРНЫЙ КЛАСС» — ванильные placed-фичи, заливающие большие объёмы
# жидкостью (озеро лавы, лавовая дельта с ободком, серные бассейны).
# В ПОДЗЕМНЫХ биомах они вызывают «спам озёрами» (жалоба юзера):
# каждый такой биом получает МАКСИМУМ ОДНУ фичу класса — и то не в
# каждом (шанс 0.3), а у большинства подземных биомов озёр нет вовсе.
# Надземные биомы не затрагиваются (там lake_lava_surface и т.п. —
# обычный пул PLACED_FEATURES).
LAKE_CLASS_FEATURES = {"lake_lava_underground", "delta", "sulfur_pool"}

SYLL_A = ["vor", "zel", "kra", "myx", "quor", "fum", "dras", "ith", "nul",
          "per", "xar", "vex", "mor", "tha", "ul", "gor", "sha", "ryn",
          "blyx", "cza", "ny", "ost", "glim", "vau", "twi", "kro"]
SYLL_B = ["o", "a", "e", "i", "u", "ae", "ei", "ou", "y", "ya", "oi"]
SYLL_C = ["ron", "thar", "gath", "mir", "nox", "vel", "dun", "kar", "phos",
          "ryx", "loon", "wick", "zar", "dorn", "vane", "mire", "gloom",
          "spire", "hollow", "crest", "vault", "reaches", "depths"]


def rnd_f(rng, a, b, digits=3):
    return round(rng.uniform(a, b), digits)


def rand_color(rng):
    return "#%06x" % rng.getrandbits(24)


def _hex_rgb(c):
    """'#rrggbb' → (r, g, b)."""
    return (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16))


def _rgb_dist(a, b):
    """Евклидова дистанция двух hex-цветов (0..441)."""
    (r1, g1, b1), (r2, g2, b2) = _hex_rgb(a), _hex_rgb(b)
    return math.sqrt((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2)


def block_state(block):
    bid, props = block
    if props:
        return {"Name": bid, "Properties": dict(props)}
    return {"Name": bid}


def heavy_count(rng, mean, big_min, big_max, big_p):
    """Убывающее распределение с тяжёлым хвостом: почти всегда маленькие
    числа (экспоненциальное со средним ~mean, не выше big_min-1), но с
    шансом big_p — большой выброс, лог-равномерный в [big_min, big_max].
    Итог: «в среднем ~mean», а десятки/сотни возможны, но редки."""
    if rng.random() < big_p:
        return int(round(math.exp(
            rng.uniform(math.log(big_min), math.log(big_max)))))
    n = 1 + int(rng.expovariate(1.0 / max(0.5, mean - 1)))
    return max(1, min(n, big_min - 1))


# Квантильные центры кластеров рельефа: Φ⁻¹((2i+1)/(2n)) — медианы n
# равных долей N(0, σ_cont) (n=3 → квантили 1/6, 3/6, 5/6 и т.д.).
# Кластеры получают РАВНЫЕ площади канала continents; прежние
# равномерные центры (-0.85..0.85) отдавали крайним кластерам и свою
# долю, и хвосты нормального шума — крайние кластеры «съедали» карту.
_CLUSTER_Q = {
    3: [-0.967, 0.0, 0.967],
    4: [-1.15, -0.319, 0.319, 1.15],
    5: [-1.282, -0.524, 0.0, 0.524, 1.282],
    6: [-1.383, -0.674, -0.319, 0.319, 0.674, 1.383],
}


# ---------------------------------------------------------------------------
# ПРЕСЕТЫ РЕЛЬЕФА — именованные архетипы с ОКНАМИ параметров (жалоба
# юзера: «многие миры рельефно скучные — огромные пустыни/почти
# плоские; хочу сильнее разнообразить, но не все ультра-абстрактные;
# пару сотен интересных конфигурируемых пресетов; мир шипов — очень
# классно выглядел»). 34 архетипа × рандомизация внутри окон = сотни
# комбинаций. Пресет выбирается ВЗВЕШЕННО в rand_final_density и
# тюнит ТОЛЬКО дикую зону: гарантии краёв (градиенты + плоские капы)
# и climate-каналы (находимость биомов) пресетами НЕ трогаются.
#
# Поля пресета:
#   name/short — идентификатор и человеческое описание
#   w          — вес выбора; cat — категория веса:
#                  interesting (~75%: красивые/выразительные),
#                  moderate (~15%), boring (<=10%: почти плоские —
#                  юзер хочет МЕНЬШЕ скучных, но не ноль)
#   character  — характер base_form: строка ИЛИ список (имя, вес);
#                управляет скелетом дикой зоны (рампа/террасы/дюны/
#                каньоны/кратеры) и стилем островов void
#   b          — окно силы скелета B (больше B — жёстче рампа, при
#                том же P рельеф «спокойнее»)
#   p_frac     — доля доступного бюджета возмущений P (P = p_frac ×
#                (B − S − extra); бюджет насыщения P+S+extra ≤ B−0.2
#                соблюдается АВТОМАТИЧЕСКИ при любом p_frac ≤ 1)
#   layers     — число слоёв возмущений (окно)
#   cap_hi     — потолок clamp отдельного слоя (окно)
#   flavors    — веса флейворов слоёв:
#                  normal — общий случай (случайные масштабы/анизотропия),
#                  spire  — столбы (xz>>y): шпили и останцы, [0,cap],
#                  strata — пласты (y>>xz): горизонтальные слои,
#                  ridge  — хребты: почти-2D шум + ridged(abs) — гряды
#                           вдоль нулевых линий, эффект силен в max-
#                           композиции (ops),
#                  wave   — плавные волны: низкие частоты, без abs
#   env        — подсказка огибающей спектра для new_noise (70%)
#   ops        — веса (add, min, max) сборки стека слоёв
#   mix_p      — вероятность регионального микса (две половины мира с
#                РАЗНЫМИ стеками возмущений)
#   spline_p   — вероятность сплайна кластеров (свой уровень
#                поверхности у кластера биомов)
#   steps      — (опц.) окно числа ступеней terraced-базы
#   void_style — (опц.) стиль островов void-мира: rafts (плоты-пласты),
#                needles (иглы), blobs (блобы — умолчание по характеру),
#                chunky (крупные редкие массивы), shards (рваные
#                осколки — мельче и острее игл)
#   void_cut   — (опц.) окно порога среза островов (доля σ поля):
#                больше — реже/меньше островов (архипелаг), меньше —
#                гуще (небесные плоты); базовые 0.35..0.9, допускается
#                0.2..1.15 — симулятор самотеста держит 5-50% твёрдого
_TERRAIN_CHARS = ("flat", "rolling", "mountainous", "chaotic", "terraced",
                  "spiky", "dunes", "canyon", "craters", "strata")
_PERT_FLAVORS = ("normal", "spire", "strata", "ridge", "wave")

TERRAIN_PRESETS = [
    # --- ИНТЕРЕСНЫЕ (~75%): выразительные, узнаваемые архетипы ---
    dict(name="overworld_classic", w=9.0, cat="interesting",
         desc="классика как обычный мир: холмы, горы, долины",
         character=[("rolling", 3), ("mountainous", 2)],
         b=(0.60, 0.90), p_frac=(0.70, 1.00), layers=(2, 4),
         cap_hi=(0.28, 0.45),
         flavors={"normal": 8, "wave": 3, "spire": 1, "ridge": 1},
         env="decay", ops=(9, 1, 1), mix_p=0.55, spline_p=1.0),
    dict(name="highlands", w=4.0, cat="interesting",
         desc="высокогорье: мощные горы с пиками",
         character="mountainous",
         b=(0.55, 0.80), p_frac=(0.85, 1.00), layers=(3, 5),
         cap_hi=(0.35, 0.45),
         flavors={"normal": 6, "spire": 3, "ridge": 2},
         env="decay", ops=(9, 1, 1), mix_p=0.35, spline_p=1.0),
    dict(name="thorns", w=4.0, cat="interesting",
         desc="шипы: частокол игл и шпилей (любимец юзера)",
         character="spiky",
         b=(0.55, 0.75), p_frac=(0.85, 1.00), layers=(3, 5),
         cap_hi=(0.35, 0.45),
         flavors={"spire": 8, "normal": 2},
         env="rising", ops=(9, 1, 1), mix_p=0.15, spline_p=0.9,
         void_style="needles"),
    dict(name="mountain_ridge", w=3.5, cat="interesting",
         desc="горные хребты: вытянутые линейные гряды",
         character="mountainous",
         b=(0.60, 0.85), p_frac=(0.80, 1.00), layers=(2, 4),
         cap_hi=(0.32, 0.45),
         flavors={"ridge": 7, "normal": 3},
         env="decay", ops=(3, 1, 5), mix_p=0.30, spline_p=1.0),
    dict(name="knife_edge", w=2.0, cat="interesting",
         desc="острые гребни: тонкие частые хребты",
         character="mountainous",
         b=(0.55, 0.75), p_frac=(0.90, 1.00), layers=(3, 5),
         cap_hi=(0.35, 0.45),
         flavors={"ridge": 9, "spire": 1},
         env="peak", ops=(2, 1, 6), mix_p=0.20, spline_p=0.8),
    dict(name="dunes", w=3.0, cat="interesting",
         desc="дюны: волнистые гряды, валы и впадины",
         character="dunes",
         b=(0.60, 0.90), p_frac=(0.70, 1.00), layers=(1, 2),
         cap_hi=(0.18, 0.30),
         flavors={"wave": 6, "normal": 3},
         env="peak", ops=(9, 1, 1), mix_p=0.20, spline_p=0.9),
    dict(name="canyons", w=3.0, cat="interesting",
         desc="каньоны: сеть извилистых борозд",
         character="canyon",
         b=(0.60, 0.95), p_frac=(0.70, 1.00), layers=(1, 3),
         cap_hi=(0.25, 0.40),
         flavors={"normal": 5, "ridge": 3},
         env="decay", ops=(9, 1, 1), mix_p=0.25, spline_p=1.0),
    dict(name="craters", w=3.0, cat="interesting",
         desc="кратерные поля: чаши с валами",
         character="craters",
         b=(0.60, 0.95), p_frac=(0.70, 1.00), layers=(1, 3),
         cap_hi=(0.22, 0.38),
         flavors={"normal": 6, "wave": 2},
         env="peak", ops=(9, 1, 1), mix_p=0.20, spline_p=1.0),
    dict(name="terraced", w=3.0, cat="interesting",
         desc="террасы: ступенчатые плато",
         character="terraced", steps=(4, 7),
         b=(0.60, 0.95), p_frac=(0.70, 1.00), layers=(1, 3),
         cap_hi=(0.25, 0.40),
         flavors={"normal": 6, "strata": 2},
         env="decay", ops=(9, 1, 1), mix_p=0.25, spline_p=0.9),
    dict(name="mesas", w=3.0, cat="interesting",
         desc="столовые горы: плоские вершины, обрывы, слои",
         character="terraced", steps=(3, 5),
         b=(0.65, 1.00), p_frac=(0.75, 1.00), layers=(2, 4),
         cap_hi=(0.28, 0.42),
         flavors={"strata": 5, "ridge": 3, "normal": 2},
         env="decay", ops=(6, 1, 3), mix_p=0.30, spline_p=1.0),
    dict(name="badlands_eroded", w=2.0, cat="interesting",
         desc="эродированные бедленды: каньоны + террасы",
         character="canyon",
         b=(0.60, 0.95), p_frac=(0.75, 1.00), layers=(2, 4),
         cap_hi=(0.28, 0.42),
         flavors={"strata": 4, "ridge": 4, "normal": 2},
         env="decay", ops=(6, 1, 3), mix_p=0.30, spline_p=0.9),
    dict(name="strata", w=2.5, cat="interesting",
         desc="пласты: горизонтальные слои породы",
         character="strata",
         b=(0.60, 0.95), p_frac=(0.80, 1.00), layers=(2, 4),
         cap_hi=(0.30, 0.45),
         flavors={"strata": 7, "normal": 3},
         env="decay", ops=(9, 1, 1), mix_p=0.25, spline_p=0.9,
         void_style="rafts"),
    dict(name="waves", w=2.5, cat="interesting",
         desc="плавные волны рельефа",
         character="rolling",
         b=(0.65, 1.00), p_frac=(0.70, 1.00), layers=(2, 3),
         cap_hi=(0.25, 0.40),
         flavors={"wave": 8, "normal": 2},
         env="peak", ops=(9, 1, 1), mix_p=0.30, spline_p=1.0),
    dict(name="ocean_swells", w=2.0, cat="interesting",
         desc="океанские валы: очень широкие поднятия",
         character="rolling",
         b=(0.75, 1.10), p_frac=(0.50, 0.80), layers=(1, 2),
         cap_hi=(0.18, 0.30),
         flavors={"wave": 9, "normal": 1},
         env="peak", ops=(9, 1, 1), mix_p=0.10, spline_p=1.0),
    dict(name="swiss_cheese", w=2.5, cat="interesting",
         desc="изрытый рельеф: каверны, дыры, измельчение",
         character="chaotic",
         b=(0.60, 0.90), p_frac=(0.85, 1.00), layers=(4, 6),
         cap_hi=(0.22, 0.35),
         flavors={"normal": 7, "spire": 2, "strata": 1},
         env="rising", ops=(9, 1, 1), mix_p=0.35, spline_p=0.8),
    dict(name="shattered", w=3.0, cat="interesting",
         desc="расколотый мир: хаос + шпили",
         character="chaotic",
         b=(0.55, 0.80), p_frac=(0.90, 1.00), layers=(3, 6),
         cap_hi=(0.30, 0.45),
         flavors={"spire": 5, "ridge": 3, "normal": 2},
         env="rising", ops=(6, 1, 3), mix_p=0.30, spline_p=0.9,
         void_style="shards"),
    dict(name="broken_columns", w=2.5, cat="interesting",
         desc="колоннады останцов: столбы со шляпами",
         character="spiky",
         b=(0.60, 0.85), p_frac=(0.80, 1.00), layers=(2, 4),
         cap_hi=(0.30, 0.45),
         flavors={"spire": 5, "strata": 4, "normal": 1},
         env="peak", ops=(9, 1, 1), mix_p=0.25, spline_p=0.9),
    dict(name="pillars_of_creation", w=2.0, cat="interesting",
         desc="столпы творения: редкие гигантские колонны",
         character="spiky",
         b=(0.70, 1.00), p_frac=(0.75, 1.00), layers=(2, 3),
         cap_hi=(0.32, 0.45),
         flavors={"spire": 7, "strata": 2, "normal": 1},
         env="peak", ops=(9, 1, 1), mix_p=0.15, spline_p=0.8),
    dict(name="monolith_field", w=1.5, cat="interesting",
         desc="поле монолитов: ровное основание + глыбы",
         character="flat",
         b=(0.80, 1.10), p_frac=(0.60, 0.90), layers=(2, 3),
         cap_hi=(0.30, 0.45),
         flavors={"spire": 8, "wave": 2},
         env="peak", ops=(6, 1, 3), mix_p=0.20, spline_p=0.7),
    dict(name="crystal_fields", w=2.0, cat="interesting",
         desc="кристаллические поля: грани и ступени",
         character=[("terraced", 2), ("spiky", 1)], steps=(5, 8),
         b=(0.65, 1.00), p_frac=(0.70, 1.00), layers=(2, 4),
         cap_hi=(0.25, 0.42),
         flavors={"strata": 4, "spire": 4, "normal": 2},
         env="flat", ops=(9, 1, 1), mix_p=0.30, spline_p=0.8),
    dict(name="honeycomb", w=2.0, cat="interesting",
         desc="соты: плотная ячеистая структура",
         character="chaotic",
         b=(0.60, 0.90), p_frac=(0.85, 1.00), layers=(3, 5),
         cap_hi=(0.25, 0.40),
         flavors={"strata": 4, "ridge": 4, "normal": 2},
         env="flat", ops=(6, 1, 3), mix_p=0.30, spline_p=0.8),
    dict(name="pinnacle_peaks", w=2.5, cat="interesting",
         desc="пиковые вершины: острые пики над холмами",
         character="mountainous",
         b=(0.60, 0.85), p_frac=(0.85, 1.00), layers=(3, 4),
         cap_hi=(0.35, 0.45),
         flavors={"spire": 5, "ridge": 3, "normal": 2},
         env="decay", ops=(6, 1, 3), mix_p=0.35, spline_p=1.0),
    dict(name="glacier_valleys", w=2.0, cat="interesting",
         desc="ледниковые долины: широкие U-профили",
         character="canyon",
         b=(0.70, 1.00), p_frac=(0.60, 0.85), layers=(2, 3),
         cap_hi=(0.22, 0.35),
         flavors={"wave": 5, "ridge": 3, "normal": 2},
         env="decay", ops=(9, 1, 1), mix_p=0.35, spline_p=1.0),
    dict(name="sinkhole_steppes", w=1.5, cat="interesting",
         desc="степь с провалами: кратеры + террасы",
         character="craters",
         b=(0.70, 1.05), p_frac=(0.60, 0.90), layers=(1, 3),
         cap_hi=(0.22, 0.36),
         flavors={"wave": 4, "normal": 4, "strata": 2},
         env="decay", ops=(9, 1, 1), mix_p=0.25, spline_p=0.9),
    dict(name="archipelago", w=2.0, cat="interesting",
         desc="архипелаг: редкие крупные острова",
         character="rolling",
         b=(0.60, 0.90), p_frac=(0.65, 0.95), layers=(1, 3),
         cap_hi=(0.25, 0.40),
         flavors={"wave": 6, "normal": 3, "spire": 1},
         env="peak", ops=(9, 1, 1), mix_p=0.15, spline_p=1.0,
         void_style="chunky", void_cut=(0.70, 1.15)),
    dict(name="sky_isles", w=1.5, cat="interesting",
         desc="небесные острова: плоские парящие плоты",
         character="strata",
         b=(0.65, 1.00), p_frac=(0.60, 0.90), layers=(1, 2),
         cap_hi=(0.20, 0.35),
         flavors={"strata": 6, "wave": 3, "normal": 1},
         env="decay", ops=(9, 1, 1), mix_p=0.20, spline_p=0.9,
         void_style="rafts", void_cut=(0.30, 0.65)),
    dict(name="shard_storm", w=1.5, cat="interesting",
         desc="буря осколков: рваные парящие иглы",
         character="spiky",
         b=(0.55, 0.80), p_frac=(0.85, 1.00), layers=(2, 4),
         cap_hi=(0.30, 0.45),
         flavors={"spire": 7, "ridge": 2, "normal": 1},
         env="rising", ops=(6, 1, 3), mix_p=0.25, spline_p=0.8,
         void_style="shards", void_cut=(0.50, 1.00)),
    dict(name="chaos_realm", w=1.5, cat="interesting",
         desc="царство хаоса: максимум беспорядка",
         character="chaotic",
         b=(0.55, 0.80), p_frac=(0.90, 1.00), layers=(4, 6),
         cap_hi=(0.30, 0.45),
         flavors={"normal": 4, "spire": 3, "ridge": 2, "strata": 1},
         env="rising", ops=(6, 1, 3), mix_p=0.40, spline_p=0.7),
    dict(name="ripple_dunes", w=1.5, cat="interesting",
         desc="рябь дюн: мелкие регулярные гряды",
         character="dunes",
         b=(0.65, 1.00), p_frac=(0.70, 1.00), layers=(2, 3),
         cap_hi=(0.16, 0.28),
         flavors={"wave": 7, "ridge": 2, "normal": 1},
         env="peak", ops=(9, 1, 1), mix_p=0.15, spline_p=0.8),
    # --- УМЕРЕННЫЕ (~15%): спокойные, но живые ---
    dict(name="rolling_simple", w=6.0, cat="moderate",
         desc="простые холмы",
         character="rolling",
         b=(0.65, 1.00), p_frac=(0.50, 0.80), layers=(1, 2),
         cap_hi=(0.20, 0.32),
         flavors={"normal": 7, "wave": 3},
         env="decay", ops=(9, 1, 1), mix_p=0.30, spline_p=1.0),
    dict(name="gentle_waves", w=4.0, cat="moderate",
         desc="мягкие широкие волны",
         character="rolling",
         b=(0.75, 1.10), p_frac=(0.45, 0.70), layers=(1, 2),
         cap_hi=(0.16, 0.26),
         flavors={"wave": 8, "normal": 2},
         env="peak", ops=(9, 1, 1), mix_p=0.15, spline_p=1.0),
    dict(name="plains_dappled", w=3.0, cat="moderate",
         desc="равнина с лёгкой рябью",
         character="flat",
         b=(0.80, 1.10), p_frac=(0.40, 0.65), layers=(1, 2),
         cap_hi=(0.14, 0.22),
         flavors={"normal": 6, "wave": 4},
         env="decay", ops=(9, 1, 1), mix_p=0.20, spline_p=0.9),
    # --- СКУЧНЫЕ (<=10%): почти плоские — редко, но бывают ---
    dict(name="plains_boring", w=5.0, cat="boring",
         desc="почти плоская равнина",
         character="flat",
         b=(0.85, 1.15), p_frac=(0.30, 0.50), layers=(1, 1),
         cap_hi=(0.12, 0.16),
         flavors={"normal": 7, "wave": 3},
         env="decay", ops=(9, 1, 1), mix_p=0.10, spline_p=0.8),
    dict(name="dead_flat", w=2.5, cat="boring",
         desc="абсолютная плоскость",
         character="flat",
         b=(0.90, 1.20), p_frac=(0.20, 0.30), layers=(1, 1),
         cap_hi=(0.12, 0.14),
         flavors={"normal": 5, "wave": 5},
         env="decay", ops=(9, 1, 1), mix_p=0.0, spline_p=0.6,
         void_cut=(0.80, 1.10)),
]


def _pick_terrain_preset(rng):
    """Взвешенный выбор пресета рельефа (веса — поле w)."""
    return rng.choices(TERRAIN_PRESETS,
                       weights=[p["w"] for p in TERRAIN_PRESETS])[0]


def _validate_terrain_presets():
    """Юнит-проверка таблицы пресетов (выполняется при импорте):
    окна валидны, характеры/флейворы известны, веса положительны,
    доли категорий в целевых рамках (интересные >= 70%, скучные
    <= 10% — требование юзера: скучных меньше, но не ноль)."""
    names = set()
    for p in TERRAIN_PRESETS:
        pn = p["name"]
        assert re.match(r"^[a-z0-9_]+$", pn), "имя пресета: %s" % pn
        assert pn not in names, "дубль имени пресета: %s" % pn
        names.add(pn)
        assert p["w"] > 0 and p["cat"] in ("interesting", "moderate",
                                           "boring"), pn
        ch = p["character"]
        if isinstance(ch, str):
            assert ch in _TERRAIN_CHARS, "%s: характер %s" % (pn, ch)
        else:
            assert ch and all(c in _TERRAIN_CHARS and w > 0
                              for c, w in ch), pn
        for key in ("b", "p_frac", "layers", "cap_hi"):
            lo, hi = p[key]
            assert 0.0 < lo <= hi, "%s: окно %s = %s" % (pn, key, p[key])
        assert p["layers"][0] >= 1, pn
        assert p["cap_hi"][1] <= 0.45, "%s: cap_hi выше прежнего " \
            "потолка насыщения" % pn
        fl = p["flavors"]
        assert fl and all(f in _PERT_FLAVORS and w > 0
                          for f, w in fl.items()), pn
        assert p["env"] in (None, "decay", "peak", "bimodal", "flat",
                            "rising"), pn
        assert len(p["ops"]) == 3 and all(w > 0 for w in p["ops"]), pn
        assert 0.0 <= p["mix_p"] <= 1.0 and 0.0 <= p["spline_p"] <= 1.0, pn
        if "steps" in p:
            assert p["steps"][0] >= 3, "%s: ступеней < 3" % pn
        if "void_cut" in p:
            lo, hi = p["void_cut"]
            assert 0.2 <= lo <= hi <= 1.15, "%s: void_cut %s" % (pn, p["void_cut"])
    total = sum(p["w"] for p in TERRAIN_PRESETS)
    for cat, lo, hi in (("interesting", 0.70, 0.82),
                        ("moderate", 0.10, 0.20),
                        ("boring", 0.0, 0.10)):
        share = sum(p["w"] for p in TERRAIN_PRESETS
                    if p["cat"] == cat) / total
        assert lo <= share <= hi, \
            "доля категории %s вне рамок: %.1f%%" % (cat, share * 100)


_validate_terrain_presets()


# ---------------------------------------------------------------------------
# Генератор одного измерения
# ---------------------------------------------------------------------------

class DimensionGenerator:
    def __init__(self, rng, namespace, name):
        self.rng = rng
        self.ns = namespace
        self.name = name
        self.noises = {}          # noise id -> spectrum json
        self._noise_counter = 0
        self.biomes = {}          # biome id -> biome json (свои биомы измерения)
        self.dfs = {}             # density function id -> json (свои файлы)
        self._df_counter = 0
        # шаг декорации каждой placed-фичи фиксирован на ВСЁ измерение:
        # одна фича в разных шагах у разных биомов = "Feature order cycle
        # found" и Watchdog-краш генерации чанков (шаги 6/9 — руды/растения
        # — вероятнее, как в ванили)
        self._feature_step = {}
        self.feat_cfg = {}        # configured_feature id -> json (свои фичи)
        self.feat_placed = {}     # placed_feature id -> json
        self.feature_tags = {}    # tags/block id -> json (тег «земли» руд)
        self.carvers_cfg = {}     # configured_carver id -> json (свои карверы)
        self.structs = {}         # структуры: structures/structure_sets/...
        # форма мира / кровля / безопасный телепорт — определяются в generate()
        self.world_shape = "open"
        self.roof_h = 0
        self.tp_y = 0
        # пресет рельефа (имя из TERRAIN_PRESETS) и толщина плоских
        # твёрдых капов дна/кровли — заполняются в rand_final_density
        self.terrain_preset = ""
        self.flat_cap_h = 0
        # новые реестры 26.2 — заполняются в generate() (могут остаться пустыми)
        self.trial_spawners = {}
        self.trial_spawner_ids = []
        self.ench = {}
        self.ench_ids = []
        self.ench_functions = {}
        self.preds = {}
        self.mods = {}
        # climate-каналы router'а — заполняются в _prepare_climate()
        # (generate() зовёт её до кластеров и биом-сорса)
        self.climate_ch = {}
        self.climate_sigma = {}
        self.terr_sigma = 1.0
        self.terr_channel = None
        # геометрия гарантий final_density / пояс cavern / размах сплайна
        # кластеров — заполняются в generate()
        self.terr_S = 0.0            # ±S сдвигов базового уровня кластеров
        self.density_band = 16       # полоса гарантий у краёв мира
        self.belt_lo = self.belt_hi = 0   # воздушный пояс cavern
        # подземные биомы (id -> depth-полоса) и рудная система
        # (configured_id -> {вариант богатства: placed_id}) — заполняются
        # в generate(); здесь пустые, чтобы биом-сорс и rand_biome были
        # безопасны и до generate()
        self.biome_underground = set()
        self.biome_band = {}
        self.ore_variants = {}
        # default_block и КАМЕННОЕ СЕМЕЙСТВО — выбираются в generate()
        # ЗАРАНЕЕ (до биомов): семейству нужно исключить default_block
        # из своего пула, а блобам — попасть в общий пул фич каждого
        # биома. _n_deep_bands заполняет rand_surface_rule (для summary)
        self.default_block = None
        self.stone_family = []      # [(блок, тир common/normal/rare), ...]
        self._family_ids = set()
        self._family_bands = []     # 1-2 блока глубинных полос
        self._family_patches = []   # 1-3 блока поверхностных заплаток
        self._family_vein = None    # блок «жилы-стержня» (редкий тир)
        self._global_feats = []     # placed-id блобов семейства (всякий биом)
        self._n_deep_bands = 0
        # СЫПУЧИЕ: бюджет РАЗНЫХ сыпучих блоков рельефа на измерение —
        # open/cavern: 2 (семейство + top-слои + полосы + заплатки),
        # void: 0 (запрет целиком — палитра уже отфильтрована).
        # default_block не сыпучий ВООБЩЕ НИКОГДА (выбирается мимо
        # бюджета). Заполняется в generate() по форме мира
        self._falling_used = set()
        self._falling_budget = 0
        # цвета биомов по ролям (sky/fog/water/grass/...) — для контраста:
        # цвета одной роли у разных биомов должны заметно отличаться
        self._color_hist = {}

    # ---------------- вспомогательные ----------------

    def new_noise(self, pref=None):
        """Случайный шум РЕЛЬЕФА: пять форм огибающей амплитуд и
        firstOctave -19..2 с НЕравномерным распределением (чаще всего
        -10..-4 — «континентальные» октавы ванильных рельефных шумов).
        Возвращает ID. Формы огибающей (спектра), выбор случайно:
          decay   — классическая убывающая (каждая следующая ×0.3-0.7):
                    крупные формы с затухающей мелкой рябью, «натурный»;
          peak    — пик на случайной октаве (гаусс-подобная): доминирует
                    один масштаб — выраженные полосы/слои/пятна;
          bimodal — двугорбая: два конкурирующих масштаба;
          flat    — все амплитуды равны: жёсткий «кристаллический» узор;
          rising  — возрастающая (мелкая рябь сильнее крупной): зазуб-
                    ренный, «шумный» рельеф.
        pref — ПОДСКАЗКА пресета рельефа (decay/peak/bimodal/flat/
        rising): 70% берётся совет, 30% — случайная форма — архетип
        сохраняет узнаваемость, но не вырождается в шаблон.
        Это пул ШУМОВ РЕЛЬЕФА (final_density, аквиферы, поверхности) —
        climate-каналы его НЕ используют: у тех своя нормализация σ
        (climate_noise_2d/continents_noise_2d, xz 0.10-0.28), от которой
        зависит находимость биомов — её НЕ ТРОГАЕМ."""
        rng = self.rng
        self._noise_counter += 1
        nid = "%s:%s_g%d" % (self.ns, self.name, self._noise_counter)
        # firstOctave: 12% очень мелкий (0..2), 55% средний (-10..-4 —
        # чаще всего), 33% крупный (-19..-3) — весь диапазон -19..2
        r = rng.random()
        if r < 0.12:
            first = rng.randint(0, 2)
        elif r < 0.67:
            first = rng.randint(-10, -4)
        else:
            first = rng.randint(-19, -3)
        n_amps = rng.randint(1, 16)
        shape = rng.choices(
            ["decay", "peak", "bimodal", "flat", "rising"],
            weights=[34, 22, 14, 14, 16])[0]
        # подсказка пресета рельефа (см. докстринг)
        if pref is not None and rng.random() < 0.7:
            shape = pref
        # базовая амплитуда с тяжёлым хвостом — редкие жирные спектры
        base = rnd_f(rng, 0.3, 2.0) if rng.random() < 0.85 \
            else rnd_f(rng, 2.0, 4.0)
        amps = self._envelope(shape, n_amps, base)
        # лёгкое «выпадение» октав (нули в спектре — как у ванильных
        # шумов) — только для «мягких» форм; flat/rising держим чистыми
        if shape in ("decay", "peak", "bimodal"):
            amps = [0.0 if rng.random() < 0.12 else a for a in amps]
        # все амплитуды нулевые -> диапазон шума [0,0]; касание с ABS-
        # диапазоном [0,x] ваниль считает не-пересечением и сыплет WARN
        # «No min/max ... noise ranges ... do not overlap» — гарантируем
        # хотя бы одну ненулевую
        if not any(amps):
            amps[rng.randrange(len(amps))] = rnd_f(rng, 0.05, 2.0)
        self.noises[nid] = {"firstOctave": first, "amplitudes": amps}
        return nid

    def _envelope(self, shape, n, base):
        """Огибающая амплитуд n октав по форме shape (см. new_noise).
        base — амплитуда «главной» октавы, остальные масштабируются от
        неё; значения округлены до 4 знаков (как ванильные шумы)."""
        rng = self.rng
        if shape == "flat":          # все равны — «кристалл»
            return [round(base, 4)] * n
        if shape == "decay":         # классическая убывающая
            out, a = [], base
            for _ in range(n):
                out.append(round(a, 4))
                a *= rng.uniform(0.3, 0.7)
            return out
        if shape == "rising":        # возрастающая = убывающая наоборот
            out, a = [], base
            for _ in range(n):
                out.append(a)
                a /= rng.uniform(1.4, 3.0)
            out.reverse()
            return [round(x, 4) for x in out]
        if shape == "peak":          # гаусс-подобный пик на случайной октаве
            k = rng.randrange(n)
            sig = max(0.5, n / rng.uniform(2.0, 5.0))
            return [round(base * math.exp(-((i - k) ** 2)
                                          / (2.0 * sig * sig)), 4)
                    for i in range(n)]
        # bimodal — двугорбая (второй горб ниже первого)
        k1 = rng.randrange(n)
        k2 = rng.randrange(n)
        if k2 < k1:
            k1, k2 = k2, k1
        if k1 == k2:
            k2 = min(n - 1, k1 + max(1, n // 3))
        sig = max(0.5, n / rng.uniform(3.0, 7.0))
        w2 = rng.uniform(0.5, 1.0)

        def bell(i, k, w=1.0):
            return base * w * math.exp(-((i - k) ** 2) / (2.0 * sig * sig))

        return [round(max(bell(i, k1), bell(i, k2, w2)), 4)
                for i in range(n)]

    def _terrain_scales(self, xz_lo=0.005, xz_hi=2.0, y_lo=0.005,
                        y_hi=2.0, aniso_p=0.30):
        """xz_scale/y_scale шума РЕЛЬЕФА: лог-равномерно с широким
        разбросом (0.005..2.0 — длины волн от ~200 блоков до полблока),
        иногда СИЛЬНАЯ анизотропия: xz>>y (мелко по горизонтали, гладко
        по вертикали — столбы/иглы/кристаллы) или y>>xz (горизонтальные
        пласты/слои). Только для шумов рельефа — climate-каналы держат
        свои масштабы (xz 0.15-0.35, волны ~400-7000 блоков), их не
        трогаем (находимость биомов)."""
        rng = self.rng
        xz = math.exp(rng.uniform(math.log(xz_lo), math.log(xz_hi)))
        ys = math.exp(rng.uniform(math.log(y_lo), math.log(y_hi)))
        if rng.random() < aniso_p:
            if rng.random() < 0.5:   # xz>>y: вертикально вытянуто
                xz = math.exp(rng.uniform(math.log(0.3), math.log(2.0)))
                ys = math.exp(rng.uniform(math.log(0.005), math.log(0.05)))
            else:                    # y>>xz: горизонтальные слои/пласты
                xz = math.exp(rng.uniform(math.log(0.005), math.log(0.05)))
                ys = math.exp(rng.uniform(math.log(0.3), math.log(2.0)))
        return round(xz, 4), round(ys, 4)

    def new_df_file(self, df):
        """Вынести density-функцию в отдельный файл worldgen/density_function/
        и вернуть ссылку-ID: каналы router в 26.2 могут ссылаться на файлы."""
        # Голый end_islands — интернированный синглтон (у него нет
        # параметров), два таких файла дают один и тот же объект, и реестр
        # падает с "Adding duplicate value". Оборачиваем в cache_once —
        # свежий объект-обёртка на каждый файл (вложенные использования
        # внутри других DF не регистрируются и безопасны).
        if isinstance(df, dict) and df.get("type") == "minecraft:end_islands":
            df = {"type": "minecraft:cache_once", "argument": df}
        self._df_counter += 1
        did = "%s:%s/df%d" % (self.ns, self.name, self._df_counter)
        self.dfs[did] = df
        return did

    # веса шагов декорации: 6 (underground_ores) и 9 (vegetation) чаще
    _STEP_WEIGHTS = [2, 1, 1, 1, 1, 1, 5, 1, 1, 5, 1]

    def _feature_step_of(self, fid, prefer=None):
        """Шаг декорации фичи — фиксированный на всё измерение (см.
        self._feature_step): движок требует, чтобы фича во всех биомах
        стояла в одном шаге, иначе цикл порядка фич и краш генерации.
        prefer — предпочитаемый шаг для НОВЫХ id (рудные варианты — 6,
        underground_ores, как у ванильных ore_*); 20% всё же случайный,
        чтобы шаги не вырождались в один."""
        st = self._feature_step.get(fid)
        if st is None:
            if prefer is not None and self.rng.random() < 0.8:
                st = prefer
            else:
                st = self.rng.choices(range(11), weights=self._STEP_WEIGHTS)[0]
            self._feature_step[fid] = st
        return st

    def _y(self):
        return self.rng.randint(self.min_y, self.max_y - 1)

    def _pair_y(self):
        a, b = self._y(), self._y()
        if a > b:
            a, b = b, a
        if a == b:
            b = min(b + 8, self.max_y)
        return a, b

    # ---------------- density functions ----------------

    def _leaf(self):
        rng = self.rng
        r = rng.random()
        if r < 0.42:  # шум с полностью случайным спектром
            # масштабы — лог-равномерно 0.005..2.0, иногда сильная
            # анизотропия (столбы/слои) — см. _terrain_scales
            xz, ys = self._terrain_scales()
            return {"type": "minecraft:noise", "noise": self.new_noise(),
                    "xz_scale": xz, "y_scale": ys}
        if r < 0.55:  # shifted_noise: шум, сдвинутый другим шумом
            # В 26.2 shift_a/shift_b принимают ID шума (или inline firstOctave/
            # amplitudes), а не density-функцию!
            shifts = []
            for _ in range(3):
                if rng.random() < 0.5:
                    shifts.append(0.0)
                else:
                    st = rng.choice(["minecraft:shift_a", "minecraft:shift_b"])
                    shifts.append({"type": st, "argument": self.new_noise()})
            xz, ys = self._terrain_scales()
            return {"type": "minecraft:shifted_noise", "noise": self.new_noise(),
                    "xz_scale": xz, "y_scale": ys,
                    "shift_x": shifts[0], "shift_y": shifts[1], "shift_z": shifts[2]}
        if r < 0.70:  # вертикальный градиент
            fy, ty = self._pair_y()
            return {"type": "minecraft:y_clamped_gradient", "from_y": fy,
                    "to_y": ty, "from_value": rnd_f(rng, -2, 2),
                    "to_value": rnd_f(rng, -2, 2)}
        if r < 0.80:
            return rnd_f(rng, -1, 1)  # константа
        if r < 0.88:
            return {"type": "minecraft:end_islands"}
        return rnd_f(rng, -1, 1)

    _UNARY = ["minecraft:abs", "minecraft:square", "minecraft:cube",
              "minecraft:squeeze", "minecraft:half_negative",
              "minecraft:quarter_negative", "minecraft:cache_once",
              "minecraft:cache_2d", "minecraft:flat_cache",
              "minecraft:interpolated", "minecraft:blend_density"]

    def _leaf_overlapping(self):
        """Лист с диапазоном, гарантированно содержащим ноль: шум (±1) или
        симметричный вертикальный градиент. Для аргументов min/max — иначе
        ваниль WARN'ит «non-overlapping inputs»."""
        rng = self.rng
        if rng.random() < 0.5:
            xz, ys = self._terrain_scales()
            return {"type": "minecraft:noise", "noise": self.new_noise(),
                    "xz_scale": xz, "y_scale": ys}
        fy, ty = self._pair_y()
        s = rnd_f(rng, 0.3, 1.5)
        return {"type": "minecraft:y_clamped_gradient", "from_y": fy,
                "to_y": ty, "from_value": -s, "to_value": s}

    def rand_df(self, depth=0, max_depth=4):
        """Случайное дерево density-функций из всех типов, известных 26.2."""
        rng = self.rng
        if depth >= max_depth:
            return self._leaf()
        r = rng.random()
        if r < 0.30:
            return self._leaf()
        if r < 0.52:  # унарные
            t = rng.choice(self._UNARY)
            out = {"type": t, "argument": self.rand_df(depth + 1, max_depth)}
            if t == "minecraft:cache_2d":
                # cache_2d имеет смысл только для 2D-функций — обернём градиент
                fy, ty = self._pair_y()
                out = {"type": t, "argument": {
                    "type": "minecraft:y_clamped_gradient", "from_y": fy,
                    "to_y": ty, "from_value": rnd_f(rng, -2, 2),
                    "to_value": rnd_f(rng, -2, 2)}}
            return out
        if r < 0.62:  # clamp
            lo = rnd_f(rng, -2, 0)
            hi = rnd_f(rng, 0, 2)
            return {"type": "minecraft:clamp", "input": self.rand_df(depth + 1, max_depth),
                    "min": lo, "max": hi}
        if r < 0.82:  # бинарные
            t = rng.choice(["minecraft:add", "minecraft:mul", "minecraft:min",
                            "minecraft:max"])
            if t in ("minecraft:min", "minecraft:max"):
                # ваниль сверяет диапазоны аргументов min/max и WARN'ит при
                # непересекающихся (константа/градиент считаются точно) —
                # берём листья, чьи диапазоны гарантированно содержат ноль
                a1 = self._leaf_overlapping()
                a2 = self._leaf_overlapping()
            else:
                a1 = self.rand_df(depth + 1, max_depth)
                a2 = self.rand_df(depth + 1, max_depth)
            return {"type": t, "argument1": a1, "argument2": a2}
        if r < 0.90:  # range_choice
            lo = rnd_f(rng, -1, 0)
            hi = rnd_f(rng, 0, 1)
            return {"type": "minecraft:range_choice",
                    "input": self.rand_df(depth + 1, max_depth),
                    "min_inclusive": lo, "max_exclusive": hi,
                    "when_in_range": self.rand_df(depth + 1, max_depth),
                    "when_out_of_range": self.rand_df(depth + 1, max_depth)}
        if r < 0.96:  # interval_select
            n = rng.randint(1, 4)
            thresholds = sorted(rnd_f(rng, -1, 1) for _ in range(n))
            return {"type": "minecraft:interval_select",
                    "input": self.rand_df(depth + 1, max_depth),
                    "thresholds": thresholds,
                    "functions": [self.rand_df(depth + 1, max_depth)
                                  for _ in range(n + 1)]}
        # spline
        return {"type": "minecraft:spline",
                "spline": self._rand_spline(depth + 1, max_depth, allow_nested=False)}

    def _rand_spline(self, depth, max_depth, allow_nested=True):
        rng = self.rng
        n = rng.randint(2, 5)
        locs = sorted(rnd_f(rng, -1, 1) for _ in range(n))
        points = []
        for loc in locs:
            if allow_nested and rng.random() < 0.3 and depth < max_depth:
                value = self._rand_spline(depth + 1, max_depth, allow_nested=False)
            else:
                value = rnd_f(rng, -2, 2)
            points.append({"location": loc, "derivative": rnd_f(rng, -1, 1),
                           "value": value})
        return {"coordinate": self.rand_df(depth + 1, max_depth),
                "points": points}

    # ---------------- final_density ----------------

    def rand_final_density(self):
        """final_density: ГАРАНТИИ ПО КРАЯМ + ПРЕСЕТЫ РЕЛЬЕФА.

        Фикс регрессии «шум заполняет мир НАСПЛОТЬ от min_y до max_y»:
        ridged-шумы (abs) с большими амплитудами в max-позиции дерева
        давали плотность >= 0 ВЕЗДЕ (abs >= 0 в max-позиции = камень
        при любом шуме) — сплошной массив; структуры через /locate
        находились, но были погребены. Архитектура:

          final = ГАРАНТИИ( БАЗА + ВОЗМУЩЕНИЕ )

        * ПРЕСЕТ — именованный архетип рельефа из TERRAIN_PRESETS
          (34 штуки, веса: интересные ~75%, умеренные ~15%, скучные
          <=10%; жалоба юзера: «многие миры рельефно скучные, огромные
          пустыни/почти плоские — меньше таких, но не ноль; мир шипов
          очень классно выглядел»). Пресет тюнит ТОЛЬКО дикую зону:
          характер базы, окна B/P (сила скелета / доля бюджета
          возмущений), число и флейворы слоёв (normal/spire/strata/
          ridge/wave), огибающую спектра, композицию стека,
          региональный микс, сплайн кластеров, стиль/порог островов
          void. Рандомизация ВНУТРИ окон даёт сотни комбинаций;
          гарантии краёв и climate-каналы пресет НЕ трогает
          (находимость биомов!).
        * БАЗА — «скелет» рельефа дикой зоны [min_y+band, max_y-band]:
          рампа ±B (уровень поверхности ~ середина зоны) либо характер:
          террасы (interval_select по y-градиенту — слоёные плато),
          каньоны (min рампы с желобом вдоль нулевых линий 2D-шума),
          кратеры (чаши |n2d| с валами), дюны (низкочастотный 2D-сдвиг
          поверхности). Вся база ограничена: у нижней границы зоны
          >= +B-extra, у верхней <= -B+extra (extra — вынос дюн/кратеров,
          вычитается из бюджета возмущений).
        * ВОЗМУЩЕНИЕ — шум ПОВЕРХ скелета, а не замена: слои из окна
          пресета, каждый зажат clamp(±cap<=0.45), весь стек —
          clamp(±P). ridged (abs) и spire-формы допускаются ТОЛЬКО
          внутри clamp со сдвигом к нулю (голый abs >= 0 = постоянный
          «+» = насыщение). spiky — столбовые масштабы, strata —
          горизонтальные пласты, spire-слои [0,cap] — пики и парящие
          останцы, ridge — почти-2D ridged-гряды (сильны в max-
          композиции), wave — гладкие низкочастотные волны без abs.
        * БЮДЖЕТ: P + S + extra <= B - 0.2 (S — размах сплайна кластеров
          рельефа по continents; P = p_frac·(B−S−extra), p_frac <= 1
          из пресета): при ЛЮБОМ шуме низ дикой зоны твёрдый,
          верх воздушный — насыщение арифметически невозможно.
        * ГАРАНТИИ — у самых краёв, НЕЗАВИСИМЫЕ от шумов и пресетов
          (по образцу ванильного nether: у дна/кровли плотность
          прижата к константам y-градиентами, шум живёт в середине):
            open:   max( min(wild, воздух у max_y), ПЛОСКИЙ кап дна )
            cavern: max( min(wild, воздушный пояс в середине),
                    ПЛОСКИЙ кап дна, ПЛОСКИЙ кап кровли ) — дно и
                    кровля cavern — ГАРАНТИРОВАННАЯ каменная плита
                    БЕЗ пересечения нуля (жалоба юзера: «крыша бедрока
                    должна быть на максимальной высоте мира»): плита
                    [ty−H .. ty−2] держит плотность ровно +3.5 (H =
                    max(band//2, 8)), над ty−2 — +3.0 (существующий
                    кап); подход к плите — рампа −4→+3.5 НИЖЕ плиты,
                    внутри полосы гарантий. Дно симметрично: плита
                    [my+2 .. my+H] на +3.5, ряды my..my+1 — +3.0.
                    Плоскую плиту НЕЛЬЗЯ собрать одним y_clamped_
                    gradient с равными значениями: он продолжает
                    from_value и НИЖЕ from_y (константа +3.5 на всю
                    высоту + max() = сплошной мир), поэтому плита —
                    min(подъём-к-плите, потолочный-сброс) из ДВУХ
                    градиентов (см. сборку ниже).
            void:   min( wild, воздух у min_y, воздух у max_y ) —
                    острова только в средней зоне, края всегда пустота
        * КОМПОЗИЦИИ РАЗНООБРАЗИЯ: пресет × характер базы ×
          региональный микс (range_choice по медленному 2D-шуму — в
          двух половинах мира РАЗНЫЕ стеки возмущений) × вертикальный
          сплит cavern (свои возмущения под поясом и над) × сплайн
          кластеров по continents (у кластера биомов свой уровень
          поверхности; пресет может его выключить — бюджет S
          освобождается возмущениям)."""
        rng = self.rng
        my, ty = self.min_y, self.max_y
        band = self.density_band

        # ПРЕСЕТ РЕЛЬЕФА: взвешенный выбор (интересные ~75% / умеренные
        # ~15% / скучные <=10%). Выбирается ЗДЕСЬ — ПОСЛЕ подготовки
        # climate-каналов в _prepare_climate: rng-поток каналов не
        # сдвигается, находимость биомов не меняется
        pre = _pick_terrain_preset(rng)
        self.terrain_preset = pre["name"]
        # характер базы — из пресета (строка или взвешенный список)
        chs = pre["character"]
        if isinstance(chs, str):
            character = chs
        else:
            character = rng.choices([c for c, _ in chs],
                                    weights=[w for _, w in chs])[0]

        # бюджет плотности: B — сила скелета (окно пресета), S — сплайн
        # кластеров (пресет может выключить — бюджет S освобождается),
        # extra — вынос дюн/кратеров у границ зоны, P — возмущения
        # (ДОЛЯ p_frac от доступного бюджета: насыщение невозможно
        # при любом p_frac <= 1)
        extra = 0.35 if character in ("dunes", "craters") else 0.0
        use_spline = getattr(self, "terrain_corr", False) \
            and rng.random() < pre["spline_p"]
        S = getattr(self, "terr_S", 0.0) if use_spline else 0.0
        B = max(rnd_f(rng, *pre["b"]), S + extra + 0.25)
        P = max(0.12, (B - S - extra) * rnd_f(rng, *pre["p_frac"]))
        env = pre["env"]          # подсказка огибающей спектра (70%)

        # --- конструкторы узлов ---
        def grad(fy, tyy, fv, tv):
            return {"type": "minecraft:y_clamped_gradient", "from_y": int(fy),
                    "to_y": int(tyy), "from_value": round(fv, 3),
                    "to_value": round(tv, 3)}

        def cl(x, lo, hi):
            return {"type": "minecraft:clamp", "input": x,
                    "min": round(lo, 3), "max": round(hi, 3)}

        def add(a, b):
            return {"type": "minecraft:add", "argument1": a, "argument2": b}

        def mulc(c, x):
            return {"type": "minecraft:mul", "argument1": round(c, 3),
                    "argument2": x}

        def nz(xz, ys, env=None):
            return {"type": "minecraft:noise",
                    "noise": self.new_noise(env),
                    "xz_scale": round(xz, 4), "y_scale": round(ys, 4)}

        def nz2d(lo, hi, env=None):
            # плоский 2D-шум (y_scale=0): дюны/каньоны/кратеры/регионы
            return nz(rnd_f(rng, lo, hi, 4), 0.0, env)

        # --- БАЗА (скелет дикой зоны, ограничен) ---
        def base_form(zlo, zhi, flip=False, k=1.0):
            """Скелет дикой зоны [zlo, zhi]: +B у «твёрдого» края зоны,
            -k·B у «воздушного» (k>1 — перекос в воздух: этажи cavern —
            терраин, прижатый к дну/кровле, а не полномерный массив;
            иначе насыщенные возмущения заливают обе зоны и в мире
            остаётся только пояс); flip — обратная рампа (зона у кровли
            cavern: воздух у пояса, массив у потолка)."""
            if character == "terraced":
                # ступени: interval_select по y-градиенту — плато;
                # число ступеней — окно пресета (mesas — широкие,
                # crystal_fields — частые)
                n = rng.randint(*pre.get("steps", (3, 6)))
                vals = [B * (1.0 - (1.0 + k) * i / (n - 1))
                        + rnd_f(rng, -0.05, 0.05) for i in range(n)]
                if flip:
                    vals = list(reversed(vals))
                thr = sorted(rnd_f(rng, -0.8, 0.8) for _ in range(n - 1))
                return {"type": "minecraft:interval_select",
                        "input": grad(zlo, zhi, 1.0, -1.0),
                        "thresholds": [round(t, 3) for t in thr],
                        "functions": [round(v, 3) for v in vals]}
            ramp = grad(zlo, zhi, B, -k * B) if not flip \
                else grad(zlo, zhi, -k * B, B)
            if character == "dunes":
                # волновой сдвиг поверхности низкочастотным 2D-шумом
                return add(ramp, cl(mulc(rnd_f(rng, 0.6, 1.4),
                                         nz2d(0.004, 0.03, env)), -0.35, 0.35))
            if character == "canyon":
                # извилистые каньоны вдоль нулевых линий 2D-шума:
                # min(рампа, желоб) — желоб побеждает только у нулей
                # шума (узкая сеть борозд). ВАЖНО: каньон — ПОВЕРХНОСТНАЯ
                # форма, глубина реза гаснет к твёрдому краю зоны
                # (gradient-держатель): без него 2D-желоб, постоянный по
                # всей колонне, прорезал этаж дна cavern НАСКЛОТЬ
                # (seed-аудит: пояс был, а пола не было)
                groove = cl(add(mulc(rnd_f(rng, 1.2, 2.2),
                                     {"type": "minecraft:abs",
                                      "argument": mulc(rnd_f(rng, 0.5, 1.2),
                                                       nz2d(0.003, 0.02))}),
                                -rnd_f(rng, 0.25, 0.5)), -0.6, 2.0)
                keep = grad(zlo, zhi, 1.0, 0.0) if not flip \
                    else grad(zlo, zhi, 0.0, 1.0)
                return {"type": "minecraft:min", "argument1": ramp,
                        "argument2": add(groove, keep)}
            if character == "craters":
                # чаши с валами: |n2d| мало — чаша (вниз), велико — вал
                bowl = cl(add(mulc(rnd_f(rng, 0.9, 1.8),
                                   {"type": "minecraft:abs",
                                    "argument": mulc(rnd_f(rng, 0.5, 1.2),
                                                     nz2d(0.01, 0.08))}),
                              -rnd_f(rng, 0.25, 0.45)), -0.5, 0.35)
                return add(ramp, bowl)
            return ramp

        # --- ВОЗМУЩЕНИЕ (шум поверх скелета, ограничен) ---
        def pert_layer(cap, flavor):
            """Слой шума, зажатый в [-cap, cap] (spire — [0, cap]).
            ridged (abs) — ТОЛЬКО со сдвигом к нулю внутри clamp: сдвиг
            гасит среднее |n|, иначе слой постоянно «плюсует» и толкает
            мир к насыщению (регрессия «мир насплочь»). Флейворы
            (веса — из пресета рельефа):
              normal — общий случай (случайные масштабы/анизотропия);
              spire  — столбы (xz>>y): шпили и парящие останцы, [0,cap];
              strata — пласты (y>>xz): горизонтальные слои;
              ridge  — хребты: почти-2D шум (y почти постоянен по
                       колонке) + всегда ridged (abs со сдвигом) —
                       гряды вдоль нулевых линий 2D-поля; эффект силен
                       в max-композиции стека (ops пресета);
              wave   — плавные волны: низкие частоты, БЕЗ abs/cube —
                       гладкие поднятия и прогибы."""
            if flavor == "strata":       # горизонтальные пласты: y >> xz
                xz, ys = self._terrain_scales(0.004, 0.05, 0.3, 2.0, 0.0)
            elif flavor == "spire":      # столбы: xz мелко (крупный
                xz, ys = self._terrain_scales(0.3, 2.0, 0.005, 0.05, 0.0)
            elif flavor == "ridge":      # хребты: колонно-стабильный
                xz, ys = self._terrain_scales(0.008, 0.06, 0.002, 0.02, 0.0)
            elif flavor == "wave":       # волны: низкие частоты, гладко
                xz, ys = self._terrain_scales(0.004, 0.03, 0.05, 0.3, 0.0)
            else:
                xz, ys = self._terrain_scales()
            f = mulc(rnd_f(rng, 0.4, 2.2), nz(xz, ys, env))
            if flavor == "spire":
                # только вверх и редко (сдвиг гасит среднее) — пики и
                # парящие останцы, а не сплошное поле
                return cl(add(f, -rnd_f(rng, 0.45, 0.7)), 0.0, cap)
            op = rng.random()
            if flavor == "ridge":        # хребет — всегда ridged
                op = 0.0
            elif flavor == "wave":       # волна — без ridged/cube
                op = 0.9
            if op < 0.28:                # ridged: abs со сдвигом к нулю
                f = add({"type": "minecraft:abs", "argument": f},
                        -rnd_f(rng, 0.5, 1.0) * cap)
            elif op < 0.40:              # cube — знаковый, без сдвига
                f = {"type": "minecraft:cube", "argument": f}
            elif op < 0.50:              # half_negative — знаковый
                f = {"type": "minecraft:half_negative", "argument": f}
            return cl(f, -cap, cap)

        def perturbation():
            """Стек возмущений: слои с малыми clamp, весь стек —
            clamp(±P). Насыщение невозможно: даже если каждый слой
            сядет на свой предел, сумма не выходит за P < B. Число
            слоёв, потолки clamp, флейворы и композиция стека
            (add/min/max) — ОКНА пресета рельефа."""
            n = rng.randint(*pre["layers"])
            cap_hi = min(rnd_f(rng, *pre["cap_hi"]), P)
            fl = pre["flavors"]
            fl_names = sorted(fl)
            fl_weights = [fl[k] for k in fl_names]
            # фолбэк для исчерпанного лимита spire-слоёв: взвешенный
            # выбор среди НЕ-spire флейворов пресета (у knife_edge, где
            # normal нет, шпили сменяются хребтами, а не «общим» слоем)
            nsp = [(k, fl[k]) for k in fl_names if k != "spire"]
            nsp_names = [k for k, _ in nsp] or ["normal"]
            nsp_weights = [w for _, w in nsp] or [1]
            n_spires = 0
            layers = []
            for _ in range(n):
                cap = rnd_f(rng, 0.12, max(0.13, cap_hi))
                flavor = rng.choices(fl_names, weights=fl_weights)[0]
                if flavor == "spire" and n_spires >= 2:
                    flavor = rng.choices(nsp_names, weights=nsp_weights)[0]
                elif flavor == "spire":
                    n_spires += 1
                layers.append(pert_layer(cap, flavor))
            stack = layers[0]
            for lay in layers[1:]:
                op = rng.choices(
                    ["minecraft:add", "minecraft:min", "minecraft:max"],
                    weights=list(pre["ops"]))[0]
                stack = {"type": op, "argument1": stack, "argument2": lay}
            return cl(stack, -P, P)

        def mixed_perturbation():
            """Композиция «два региона»: медленный 2D-шум делит мир на
            области с РАЗНЫМИ стеками возмущений (у побережья ровно, за
            хребтом хаос); оба стека зажаты ±P — смесь тоже ограничена."""
            a = perturbation()
            b = perturbation()
            return {"type": "minecraft:range_choice",
                    "input": nz2d(0.002, 0.01),
                    "min_inclusive": -0.2, "max_exclusive": 0.2,
                    "when_in_range": a, "when_out_of_range": b}

        # --- сплайн кластеров (пер-кластерный уровень поверхности);
        # пресет мог его выключить (use_spline=False) — тогда бюджет S
        # уже освобождён возмущениям выше ---
        spline_df = None
        if use_spline:
            cs = sorted(self.terr_clusters)
            pts = [{"location": cs[0][0] - 0.25, "value": cs[0][1],
                    "derivative": 0.0}]
            pts += [{"location": c, "value": off, "derivative": 0.0}
                    for c, off in cs]
            pts.append({"location": cs[-1][0] + 0.25, "value": cs[-1][1],
                        "derivative": 0.0})
            spline_df = {"type": "minecraft:spline",
                         "spline": {"coordinate": self.terr_channel,
                                    "points": pts}}

        # --- острова void: НОРМАЛИЗОВАННЫЕ шумы с известной σ ---
        def island_field():
            """Поле островов void-мира: 1-2 3D-шума с ЗАРАНЕЕ известной
            σ (амплитуды нормированы как у climate-каналов — случайный
            спектр без нормализации то пуст (σ~0.05), то насыщен
            (σ~1.5): половина void-миров была без единого острова).
            Мягкий clamp поверх; сырой шум симметричен (среднее 0) —
            насыщение в одну сторону невозможно, abs не нужен."""
            sig = rnd_f(rng, 0.55, 0.95)
            two = rng.random() < 0.6
            layers = []
            for _ in range(2 if two else 1):
                sl = sig / math.sqrt(2.0 if two else 1.0)
                # firstOctave и xz_scale ОГРАНИЧЕНЫ: длина волны октавы-0
                # = 2^(-first)/xz держим в ~100..1600 блоков (масштаб
                # ванильных островов Края) — без ограничения выпадали
                # поля в 80 000 блоков: весь сэмпл-грид внутри одного
                # «острова» и мир выглядит сплошным/пустым
                first = rng.randint(-4, -2)
                amps = [rnd_f(rng, 0.3, 2.0)
                        for _ in range(rng.randint(2, 6))]
                k = sl / (0.25 * math.sqrt(sum(a * a for a in amps)))
                nid = self._add_octaved_noise(
                    first, [round(a * k, 4) for a in amps])
                # стиль островов — из пресета (void_style), по
                # умолчанию — по характеру базы: strata → плоты,
                # spiky → иглы, прочее → блобы/гряды
                vs = pre.get("void_style") or (
                    "rafts" if character == "strata" else
                    "needles" if character == "spiky" else "blobs")
                if vs == "rafts":         # плоты-пласты
                    xz, ys = self._terrain_scales(0.01, 0.05, 0.1, 0.5, 0.0)
                elif vs == "needles":     # столбы-иглы
                    xz, ys = self._terrain_scales(0.03, 0.12, 0.01, 0.06, 0.0)
                elif vs == "shards":      # рваные осколки — острее игл
                    xz, ys = self._terrain_scales(0.05, 0.2, 0.004, 0.04, 0.0)
                elif vs == "chunky":      # крупные редкие массивы
                    xz, ys = self._terrain_scales(0.006, 0.03, 0.04, 0.4, 0.0)
                else:                     # блобы/гряды
                    xz, ys = self._terrain_scales(0.01, 0.08, 0.02, 0.5, 0.25)
                layers.append({"type": "minecraft:noise", "noise": nid,
                               "xz_scale": xz, "y_scale": ys})
            f = layers[0]
            for lay in layers[1:]:
                f = add(f, lay)
            cap = sig * rnd_f(rng, 1.6, 2.4)
            return cl(f, -cap, cap), sig

        # --- ПЛОСКИЕ ТВЁРДЫЕ КАПЫ дна/кровли (гарантии cavern/open) ---
        # Жалоба юзера: «крыша бедрока должна быть на максимальной
        # высоте мира — сейчас бедрок ниже, сверху него ещё рельеф».
        # Плита гарантированного камня: [ty-H .. ty-2] у кровли и
        # [my+2 .. my+H] у дна (H = max(band//2, 8)) держит плотность
        # РОВНО +3.5 — без пересечения нуля; над ty-2 / под my+2 —
        # +3.0 (существующий кап); подход к плите — рампа -4 -> +3.5
        # (кровля) / +3.5 -> -4 (дно) ЦЕЛИКОМ внутри полосы гарантий
        # [band], ниже плиты. Плоскую плиту НЕЛЬЗЯ собрать одним
        # y_clamped_gradient с равными значениями: он продолжает
        # from_value и НИЖЕ from_y (константа +3.5 на всю высоту +
        # max() = сплошной мир), поэтому плита = min(подъём-к-плите,
        # ограничитель) из ДВУХ градиентов:
        #   кровля: min(grad(ty-band, ty-H, -4, +3.5),      <- подъём
        #                grad(ty-2,   ty-1, +3.5, +3.0))    <- сброс
        #   дно:    min(grad(my+H,   my+band, +3.5, -4),    <- спуск
        #                grad(my+1,   my+2, +3.0, +3.5))    <- подъём дна
        # На плиту сверху ложится бедрок-полоса surface-правил
        # (below_top 0..thick+1, thick 3-5 — заведомо внутри плиты).
        H = min(max(band // 2, 8), max(2, band - 2))
        self.flat_cap_h = H

        def roof_cap():
            # кровля: плита [ty-H .. ty-2] на +3.5, выше — +3.0
            return {"type": "minecraft:min",
                    "argument1": grad(ty - band, ty - H, -4.0, 3.5),
                    "argument2": grad(ty - 2, ty - 1, 3.5, 3.0)}

        def floor_cap():
            # дно: плита [my+2 .. my+H] на +3.5, ниже — +3.0
            return {"type": "minecraft:min",
                    "argument1": grad(my + H, my + band, 3.5, -4.0),
                    "argument2": grad(my + 1, my + 2, 3.0, 3.5)}

        # --- сборка по форме мира ---
        if self.world_shape == "void":
            # пустота: острова из нормализованных шумов с порогом от σ
            # (окно порога — из пресета: архипелаг — реже и крупнее,
            # небесные плоты — гуще); оба края — гарантированная пустота
            field, sig = island_field()
            cut = sig * rnd_f(rng, *pre.get("void_cut", (0.35, 0.9)))
            wild = add(field, -cut)
            if spline_df:
                # кластеры: у региона своя густота островов (±50% от S)
                wild = add(wild, mulc(0.5, spline_df))
            core = {"type": "minecraft:min", "argument1": wild,
                    "argument2": grad(my, my + band, -3.0, 4.0)}
            core = {"type": "minecraft:min", "argument1": core,
                    "argument2": grad(ty - band, ty - 2, 4.0, -3.0)}
        elif self.world_shape == "open":
            wild = add(base_form(my + band, ty - band),
                       mixed_perturbation() if rng.random() < pre["mix_p"]
                       else perturbation())
            if spline_df:
                wild = add(wild, spline_df)
            # воздух у потолка (высотные фичи не выходят за top) и
            # ПЛОСКИЙ твёрдый кап дна (бедрок-полоса surface-правил
            # лежит на гарантированной каменной плите, не на рельефе)
            core = {"type": "minecraft:min", "argument1": wild,
                    "argument2": grad(ty - band, ty - 2, 4.0, -3.0)}
            core = {"type": "minecraft:max", "argument1": core,
                    "argument2": floor_cap()}
        else:  # cavern — дно и кровля из массива, в середине пояс воздуха
            zlo, zhi = my + band, ty - band
            # этажи cavern прижаты к дну/кровле (k>1 — перекос рампы в
            # воздух), бюджет возмущений урезан: насыщенный стек не должен
            # заливать этажи до самого пояса (аудит: seed-354 давал 76%
            # твёрдого — обе зоны налитые)
            kk = rnd_f(rng, 1.3, 1.7)
            P = P * 0.85
            base = {"type": "minecraft:max",
                    "argument1": base_form(zlo, self.belt_lo, k=kk),
                    "argument2": base_form(self.belt_hi, zhi, flip=True, k=kk)}
            pert = mixed_perturbation() if rng.random() < pre["mix_p"] \
                else perturbation()
            if rng.random() < 0.4:
                # вертикальный сплит: под поясом и над ним — СВОИ
                # возмущения (этаж дна и этаж кровли различаются)
                mid = (self.belt_lo + self.belt_hi) // 2
                pert = {"type": "minecraft:range_choice",
                        "input": grad(mid, mid + 1, 0.0, 1.0),
                        "min_inclusive": 0.5, "max_exclusive": 1.5,
                        "when_in_range": pert,
                        "when_out_of_range": perturbation()}
            wild = add(base, pert)
            if spline_df:
                wild = add(wild, spline_df)
            # гарантированный пояс воздуха в середине (t — переходник);
            # массив у дна и у кровли — ПЛОСКИЕ ТВЁРДЫЕ КАПЫ: у самой
            # кровли/дна плотность прижата к +3.5/+3.0 БЕЗ пересечения
            # нуля (жалоба юзера: «крыша бедрока на максимальной
            # высоте мира, без рельефа над ней») — см. roof_cap/
            # floor_cap выше; градиенты сильнее любого шума
            t = max(4, band // 2)
            belt_air = {"type": "minecraft:max",
                        "argument1": grad(self.belt_lo - t, self.belt_lo,
                                          4.0, -4.0),
                        "argument2": grad(self.belt_hi, self.belt_hi + t,
                                          -4.0, 4.0)}
            core = {"type": "minecraft:min", "argument1": wild,
                    "argument2": belt_air}
            core = {"type": "minecraft:max", "argument1": core,
                    "argument2": floor_cap()}
            core = {"type": "minecraft:max", "argument1": core,
                    "argument2": roof_cap()}
        # interpolated — всегда: рельеф сглаживается по ячейкам шума
        # (как во всех ванильных noise_settings)
        core = {"type": "minecraft:interpolated", "argument": core}
        if rng.random() < 0.25:
            core = {"type": "minecraft:blend_density", "argument": core}
        return core

    # ---------------- climate-каналы router'а ----------------

    def _add_octaved_noise(self, first, amps):
        """Зарегистрировать шум с ЗАДАННОЙ структурой октав, вернуть ID
        (new_noise рандомизирует структуру сам — здесь она вычислена)."""
        self._noise_counter += 1
        nid = "%s:%s_g%d" % (self.ns, self.name, self._noise_counter)
        self.noises[nid] = {"firstOctave": first, "amplitudes": amps}
        return nid

    def climate_noise_2d(self):
        """Climate-канал router'а (temperature/vegetation/erosion/
        ridges): горизонтальный 2D-шум с ЗАРАНЕЕ ИЗВЕСТНОЙ σ — амплитуды
        нормируем к target 0.35..0.7 (каждая октава ~N(0,(0.25·amp)²),
        итог 0.25·sqrt(Σamp²)). σ канала размечает квантильную решётку
        биом-сорса (_biome_source_multi_noise), поэтому канал обязан
        быть плоским шумом предсказуемого разброса: прежние
        rand_climate_df-каналы (константы, 3D-шумы, случайные деревья
        DF) делали любую решётку бессмысленной — bias решал всё (по
        аудиту на 31 мире: медиана топ-2 биомов 71% площади). Масштаб —
        как в ванили у temperature: firstOctave -10..-7 + xz_scale
        0.10..0.28 = длины волн ~460..10200 блоков (ваниль — 4096);
        окно УЖЕ прежнего (0.15..0.35) — биомы КРУПНЕЕ по площади
        (юзер: «сами биомы чуть больше по размерам»), а σ-нормализация
        и решётки биом-сорса не меняются (находимость биомов)."""
        rng = self.rng
        first = rng.randint(-10, -7)
        amps = [rnd_f(rng, 0.5, 2.0) for _ in range(rng.randint(2, 6))]
        target = rnd_f(rng, 0.35, 0.7)
        k = target / (0.25 * math.sqrt(sum(a * a for a in amps)))
        nid = self._add_octaved_noise(first, [round(a * k, 4) for a in amps])
        return {"type": "minecraft:noise", "noise": nid,
                "xz_scale": rnd_f(rng, 0.10, 0.28), "y_scale": 0.0}

    def continents_noise_2d(self):
        """continents-канал: 2D-шум с σ 0.6..1.1 (крупнее климатических —
        на нём держатся кластеры рельефа) и длиной волны октавы-0 ровно
        768..2560 блоков (xz_scale = 2^(-first)/U: октава-0 растянута
        на U блоков; УЖЕ прежних 512..2048 — клетка кластеров чуть
        крупнее, юзер: «сами биомы чуть больше по размерам»). Прежняя
        связка new_noise + xz_scale 0.002..0.02 давала волны до 9 млн
        блоков (в ванили continents — 8192): кластер рельефа не найти
        и за час полёта."""
        rng = self.rng
        first = rng.choice([-9, -8, -7])
        amps = [rnd_f(rng, 0.5, 2.0) for _ in range(rng.randint(2, 6))]
        target = rnd_f(rng, 0.6, 1.1)
        k = target / (0.25 * math.sqrt(sum(a * a for a in amps)))
        nid = self._add_octaved_noise(first, [round(a * k, 4) for a in amps])
        xz = 2.0 ** (-first) / rng.uniform(768.0, 2560.0)
        return {"type": "minecraft:noise", "noise": nid,
                "xz_scale": round(xz, 4), "y_scale": 0.0}

    def _channel_sigma(self, df):
        """σ климатического канала по его DF (нужна квантильной решётке
        биом-сорса): шум — 0.25·sqrt(Σamp²); всё прочее (константа,
        y-градиент, составные DF) — консервативные 0.5."""
        if isinstance(df, (int, float)):
            return 0.5
        if isinstance(df, str):  # ссылка на DF-файл — смотрим внутрь
            return self._channel_sigma(self.dfs.get(df, 0.0))
        if isinstance(df, dict):
            if df.get("type") == "minecraft:noise":
                spec = df.get("noise")
                if isinstance(spec, str) and spec in self.noises:
                    amps = self.noises[spec]["amplitudes"]
                    return 0.25 * math.sqrt(sum(a * a for a in amps))
                if isinstance(spec, dict):  # встроенный спек (на всякий)
                    amps = spec.get("amplitudes") or [1.0]
                    return 0.25 * math.sqrt(sum(a * a for a in amps))
            if df.get("type") == "minecraft:flat_cache":
                return self._channel_sigma(df.get("argument"))
        return 0.5

    def _prepare_climate(self):
        """Climate-каналы router'а готовим ЗАРАНЕЕ — до кластеров
        рельефа и биом-сорса: σ temperature/vegetation нужна квантильной
        решётке биом-сорса, σ continents — квантильным центрам кластеров,
        а сами DF потом просто вставляются в router
        (rand_noise_settings). depth — рампа 1.5→-1.5 по всей высоте
        мира (как ванильный overworld-depth): ~0 у середины высоты
        (примерный уровень поверхности), отрицательная в воздухе.
        ПОДЗЕМНЫЕ биомы (self.biome_underground, полосы — в generate)
        тайлят свои непересекающиеся полосы в подземной зоне
        [CAVE_BAND_TOP, CAVE_BAND_BOTTOM] (0.2..1.45 — первая полоса
        сразу под поверхностью, как в ваниле) — как ванильные
        dripstone_caves/lush_caves, но системой из 2-6 биомов."""
        self.climate_ch = {
            "temperature": self.climate_noise_2d(),
            "vegetation": self.climate_noise_2d(),
            "erosion": self.climate_noise_2d(),
            "ridges": self.climate_noise_2d(),
            "depth": {"type": "minecraft:y_clamped_gradient",
                      "from_y": self.min_y, "to_y": self.max_y,
                      "from_value": 1.5, "to_value": -1.5},
        }
        self.climate_sigma = {k: self._channel_sigma(v)
                              for k, v in self.climate_ch.items()}
        # continents при climate-корреляции — DF-файл (flat_cache поверх
        # 2D-шума, как ванильный overworld/continents): на файл ссылается
        # И router (размещение биомов multi_noise), И spline в
        # final_density — один шум, две роли
        if getattr(self, "terrain_corr", False):
            noise_df = self.continents_noise_2d()
            self.terr_sigma = self._channel_sigma(noise_df)
            self.terr_channel = self.new_df_file({
                "type": "minecraft:flat_cache", "argument": noise_df})

    # ---------------- каменное семейство / пулы рельефа ----------------

    def _terrain_palette(self):
        """Пул блоков РЕЛЬЕФА (default_block, поверхности, семейства,
        «жидкость»-из-блока): PALETTE_BLOCKS, а в void-мирах — БЕЗ
        сыпучих (падающий блок над пустотой обращается в entity
        FALLING_BLOCK — весь мир сыплется в пустоту; см.
        FALLING_BLOCK_IDS). В open/cavern-мирах сыпучие — по БЮДЖЕТУ
        (≤ 2 разных, решает _falling_aware_choice): сам пул их
        содержит, расход контролируется при выборе."""
        if self.world_shape == "void":
            return [b for b in PALETTE_BLOCKS
                    if b[0] not in FALLING_BLOCK_IDS]
        return PALETTE_BLOCKS

    def _ng_pool(self, pool):
        """Произвольный пул блоков без сыпучих (void-миры) — для
        статических пулов вроде CAVE_FLOOR_BLOCKS (сыпучих там сейчас
        нет — фильтр как страховка от будущих правок)."""
        if self.world_shape != "void":
            return pool
        return [b for b in pool if b[0] not in FALLING_BLOCK_IDS]

    def _surface_pool(self):
        """Пул поверхностных СЛОЁВ биомов: палитра рельефа БЕЗ блоков
        каменного семейства — у семейства СВОИ методы появления (блобы/
        полосы/заплатки), поверхность не должна его дублировать
        (условие задачи: семейство отлично от поверхностных блоков)."""
        fam = self._family_ids
        pool = [b for b in self._terrain_palette() if b[0] not in fam]
        return pool or self._terrain_palette()

    def _falling_aware_choice(self, rng, pool):
        """Выбор блока для массива рельефа с учётом бюджета сыпучих:
        пока не исчерпан — любой (сыпучий регистрируется в бюджете),
        после — только несыпучие. В void-мирах бюджет 0 И палитра уже
        без сыпучих — двойная страховка. Бюджет считают РАЗНЫЕ id:
        один и тот же песок в двух слоях — по-прежнему один блок."""
        if len(self._falling_used) < self._falling_budget:
            b = rng.choice(pool)
            if b[0] in FALLING_BLOCK_IDS:
                self._falling_used.add(b[0])
            return b
        nf = [x for x in pool if x[0] not in FALLING_BLOCK_IDS]
        return rng.choice(nf or pool)

    def _pick_top_block(self, rng, pool, used_top, recent_fams):
        """top-блок поверхности биома — максимально непохожий на соседей
        (жалоба: «до сих пор не всегда могу отличить 2 биома измерения
        друг от друга"):
          1. УНИКАЛЬНЫЙ блок — не повторяется ни у одного биома мира;
          2. семейство материала — не из последних двух биомов («по
             возможности»: камень vs дерево vs шерсть vs металл — не
             два биома с брёвнами подряд; при пустом фильтре — что есть);
          3. сыпучие — по бюджету измерения.
        Дерево в top само по себе теперь редко (вес ×0.25 в
        BLOCK_TIERS) — отдельного запрета не нужно."""
        cand = [b for b in pool if b[0] not in used_top] or list(pool)
        fresh = [b for b in cand
                 if _material_family(b[0]) not in recent_fams]
        if fresh:
            cand = fresh
        return self._falling_aware_choice(rng, cand)

    def _select_stone_family(self):
        """КАМЕННОЕ СЕМЕЙСТВО измерения: 3-7 дополнительных полных
        блоков из палитры (НЕ default_block; поверхностные слои сами
        исключают семейство — см. _surface_pool), с тирами: 1-2
        «частых», 1-3 «обычных», 1-2 «редких» (сумма всегда 3-7).

        Методы генерации — как ваниль (у разных блоков по-разному):
          (а) БОЛЬШИЕ БЛОБЫ (андезит/диорит/гранит/туф): у ВСЕХ членов
              семейства — ore-фича size 15-64, count 1-6/чанк, полоса
              высот по долям высоты мира («частые» крупнее и гуще,
              «редкие» — rarity 1/4-1/16); генерирует gen_features.
              rand_stone_blobs, блобы идут в КАЖДЫЙ биом (общий пул,
              не пер-биомный — пер-биомные множители только у руд);
          (б) ГЛУБИННЫЕ ПОЛОСЫ (deepslate): 1-2 члена — ниже порога
              весь массив становится блоком B, ещё ниже — C
              (rand_surface_rule, п.5);
          (в) ПОВЕРХНОСТНЫЕ ЗАПЛАТКИ (кальцит у пиков): 1-3 члена в
              noise_threshold-условиях surface rules (п.3b);
          (г) «ЖИЛА-СТЕРЖЕНЬ»: 50% — один РЕДКИЙ блок с вертикальными
              узкими блобами (size мал + count высок).

        Роли раздаются РАЗНЫМ блокам когда семейство позволяет (у блока
        один основной способ, как у ванильного кальцита/туфа), блобы
        при этом есть у всех. В void-мирах сыпучие исключены (пул
        _terrain_palette); в open/cavern — по бюджету (≤ 2 разных на
        измерение). Дерево — максимум один блок и редко: семейство
        должно быть камнеподобным (жалоба «рельеф из дерева»)."""
        rng = self.rng
        pool = self._terrain_palette()
        n_common = rng.randint(1, 2)
        n_normal = rng.randint(1, 3)
        n_rare = rng.randint(1, 2)
        want = n_common + n_normal + n_rare          # всегда 3-7
        # взвешенный выбор (веса странности — в самой палитре) с
        # гарантией уникальности блоков; ПРИОРИТЕТ КАМНЕПОДОБНЫХ:
        # бревно в семействе — максимум ОДНО и редко (12%; жалоба
        # «почти в каждом мире рельеф из дерева»), сыпучие — только
        # при свободном бюджете (open/cavern; см. _falling_budget)
        seen = {self.default_block[0]}
        fam = []
        wood_taken = False
        guard = want * 30 + 80
        while len(fam) < want and guard > 0:
            guard -= 1
            b = rng.choice(pool)
            if b[0] in seen:
                continue
            if _material_family(b[0]) == "wood" \
                    and (wood_taken or rng.random() > 0.12):
                continue
            if b[0] in FALLING_BLOCK_IDS \
                    and len(self._falling_used) >= self._falling_budget:
                continue
            if _material_family(b[0]) == "wood":
                wood_taken = True
            if b[0] in FALLING_BLOCK_IDS:
                self._falling_used.add(b[0])
            seen.add(b[0])
            fam.append(b)
        self.stone_family = (
            [(b, "common") for b in fam[:n_common]]
            + [(b, "normal") for b in fam[n_common:n_common + n_normal]]
            + [(b, "rare") for b in fam[n_common + n_normal:]])
        self._family_ids = {b[0] for b, _ in self.stone_family}
        blocks = [b for b, _ in self.stone_family]
        rare_blocks = [b for b, t in self.stone_family if t == "rare"]
        # (г) жила-стержень: 50% и если есть редкие — один РЕДКИЙ блок
        self._family_vein = (rng.choice(rare_blocks)
                             if rare_blocks and rng.random() < 0.5 else None)
        # раздача ролей: полосы и заплатки — блокам, не занятым жилой;
        # при маленьком семействе допустимы повторы
        rest = [b for b in blocks if b != self._family_vein] or list(blocks)
        # (б) полосы: высокие миры — всегда 2 (средняя + глубокая),
        # низкие — 1-2; void-мирам полосы не нужны (rand_surface_rule)
        n_bands = 2 if self.height >= 256 else 1 + rng.randint(0, 1)
        self._family_bands = rest[:n_bands]
        while len(self._family_bands) < n_bands:
            self._family_bands.append(rng.choice(blocks))
        # (в) заплатки: 1-3 блока, не занятых полосами/жилой
        taken = {b[0] for b in self._family_bands}
        rest2 = [b for b in rest if b[0] not in taken]
        n_patches = rng.randint(1, 3)
        self._family_patches = rest2[:n_patches]
        while len(self._family_patches) < n_patches:
            self._family_patches.append(rng.choice(blocks))

    # ---------------- surface rules ----------------

    def _rand_anchor(self):
        rng = self.rng
        r = rng.random()
        if r < 0.5:
            return {"absolute": rng.randint(self.min_y, self.max_y)}
        if r < 0.75:
            return {"above_bottom": rng.randint(0, 32)}
        return {"below_top": rng.randint(0, 32)}

    def _rand_condition(self):
        rng = self.rng
        r = rng.random()
        if r < 0.22:
            return {"type": "minecraft:stone_depth",
                    "surface_type": rng.choice(["floor", "ceiling"]),
                    "offset": rng.randint(0, 3),
                    "add_surface_depth": rng.random() < 0.5,
                    "secondary_depth_range": rng.randint(0, 8)}
        if r < 0.42:
            return {"type": "minecraft:y_above", "add_stone_depth": rng.random() < 0.5,
                    "anchor": self._rand_anchor(),
                    "surface_depth_multiplier": rng.randint(-2, 2)}
        if r < 0.56:
            lo, hi = sorted(rnd_f(rng, -1, 1) for _ in range(2))
            if lo == hi:
                hi = lo + 0.1
            cond = {"type": "minecraft:noise_threshold",
                    "noise": rng.random() < 0.6 and self.new_noise()
                             or rng.choice(["minecraft:surface", "minecraft:patch",
                                            "minecraft:ice", "minecraft:gravel",
                                            "minecraft:calcite"]),
                    "min_threshold": lo, "max_threshold": hi}
            if rng.random() < 0.3:
                cond["is_3d"] = True
            return cond
        if r < 0.68:
            k = rng.randint(1, 3)
            return {"type": "minecraft:biome",
                    "biome_is": [self._rand_biome() for _ in range(k)] if k > 1
                                else self._rand_biome()}
        if r < 0.76:
            return {"type": "minecraft:water", "add_stone_depth": rng.random() < 0.5,
                    "offset": rng.randint(-6, 6),
                    "surface_depth_multiplier": rng.randint(-2, 2)}
        if r < 0.84:
            return {"type": rng.choice(["minecraft:hole", "minecraft:steep",
                                        "minecraft:temperature"])}
        if r < 0.94:
            return {"type": "minecraft:vertical_gradient",
                    "random_name": "%s:%s/srf%d" % (self.ns, self.name,
                                                    self._noise_counter),
                    "true_at_and_below": self._rand_anchor(),
                    "false_at_and_above": self._rand_anchor()}
        return {"type": "minecraft:not", "invert": self._rand_condition()}

    def _rand_biome(self):
        """Биом для условий surface rule: чаще свой, реже ванильный."""
        if self.biomes and self.rng.random() < 0.6:
            return self.rng.choice(sorted(self.biomes))
        return "minecraft:" + self.rng.choice(BIOMES)

    def _block_rule(self):
        # палитра рельефа: в void-мирах уже без сыпучих; в open/cavern
        # сыпучие — по бюджету измерения (≤ 2 разных: заплатка из
        # песка над бедроковым дном — можно, «мир из бетонной пыли» — нет)
        return {"type": "minecraft:block",
                "result_state": block_state(
                    self._falling_aware_choice(
                        self.rng, self._terrain_palette()))}

    def rand_surface_rule(self, default_block):
        rng = self.rng
        seq = []

        # 1. Бедрок ДНА — во ВСЕХ мирах с дном (open/cavern), всегда
        #    ТОЛЬКО бедрок. Рваная полоса 0..(4-6) как ванильный
        #    bedrock_floor (jar 26.2: true above_bottom 0 / false
        #    above_bottom 5): при полосе >= 4 vertical_gradient даёт
        #    характерный «рваный» переход (раньше thick был 0-5 — почти
        #    плоское дно выпадало в половине миров). Раньше: 30% миров
        #    вообще без дна, ещё 40% — «дно» из случайного блока палитры.
        #    Бедрок исключён из всех пулов рельефа — он живёт ТОЛЬКО
        #    здесь и в кровле (см. _T2_RARE)
        if self.world_shape != "void":
            thick = rng.randint(3, 5)
            seq.append({
                "type": "minecraft:condition",
                "if_true": {"type": "minecraft:vertical_gradient",
                            "random_name": "%s:%s/bedrock_floor" % (self.ns, self.name),
                            "true_at_and_below": {"above_bottom": 0},
                            "false_at_and_above": {"above_bottom": thick + 1}},
                "then_run": {"type": "minecraft:block",
                             "result_state": {"Name": "minecraft:bedrock"}},
            })
        # 2. Бедрок КРОВЛИ — ТОЛЬКО cavern-миры, полосой 0..(4-6) от
        #    верха. Формат сверен с ванильным nether.json (jar 26.2):
        #    градиент обязан быть завёрнут в minecraft:not — семантика
        #    vertical_gradient «true_at_and_below = истинно НИЖЕ якоря»,
        #    и БЕЗ обёртки условие красило бы бедроком весь массив ниже
        #    верхней полосы (скрытый баг: cavern-миры были монолитом
        #    бедрока, слои биомов перекрывались). not(...) инвертирует:
        #    бедрок только у самой кровли, рваной полосой вниз
        if self.world_shape == "cavern":
            thick = rng.randint(3, 5)
            seq.append({
                "type": "minecraft:condition",
                "if_true": {"type": "minecraft:not",
                            "invert": {
                                "type": "minecraft:vertical_gradient",
                                "random_name": "%s:%s/bedrock_roof" % (
                                    self.ns, self.name),
                                "true_at_and_below": {"below_top": thick + 1},
                                "false_at_and_above": {"below_top": 0}}},
                "then_run": {"type": "minecraft:block",
                             "result_state": {"Name": "minecraft:bedrock"}},
            })
        # 3. Случайные заплатки: ванильные surface-шумы с центрированными
        #    порогами (надёжно матчатся — так ваниль делает гравий/патчи),
        #    плюс пара экзотических условий из _rand_condition().
        #    ВАЖНО: до биомных слоёв — иначе не видны (первое совпадение
        #    побеждает в sequence).
        for _ in range(rng.randint(1, 4)):
            lo = rnd_f(rng, -0.6, -0.1)
            hi = rnd_f(rng, 0.1, 0.6)
            seq.append({
                "type": "minecraft:condition",
                "if_true": {"type": "minecraft:noise_threshold",
                            "noise": rng.choice(
                                ["minecraft:surface", "minecraft:patch",
                                 "minecraft:ice", "minecraft:gravel",
                                 "minecraft:calcite", self.new_noise()]),
                            "min_threshold": lo, "max_threshold": hi},
                "then_run": self._block_rule(),
            })
        for _ in range(rng.randint(0, 3)):
            seq.append({"type": "minecraft:condition",
                        "if_true": self._rand_condition(),
                        "then_run": self._block_rule()})
        # 3b. Заплатки КАМЕННОГО СЕМЕЙСТВА: 1-3 камня семейства в тех же
        #     noise_threshold-условиях (у ванили так проступают кальцит
        #     у пиков и гравий на ветру) — «свой камень» пятнами в
        #     поверхности, как блобы андезита в обрывах. До биомных
        #     слоёв — первым совпадением побеждает заплатка
        for blk in getattr(self, "_family_patches", []):
            lo = rnd_f(rng, -0.6, -0.1)
            hi = rnd_f(rng, 0.1, 0.6)
            seq.append({
                "type": "minecraft:condition",
                "if_true": {"type": "minecraft:noise_threshold",
                            "noise": rng.choice(
                                ["minecraft:surface", "minecraft:patch",
                                 "minecraft:ice", "minecraft:gravel",
                                 "minecraft:calcite", self.new_noise()]),
                            "min_threshold": lo, "max_threshold": hi},
                "then_run": {"type": "minecraft:block",
                             "result_state": block_state(blk)},
            })
        # 4. ПОВЕРХНОСТЬ — гарантированные слои как у ванили (grass на dirt):
        #    stone_depth матчится у самой поверхности ВСЕГДА, поэтому разные
        #    биомы получают свой верхний/подповерхностный блок. СВОЙ профиль
        #    у КАЖДОГО биома (раньше биомы бились на 2-6 общих групп —
        #    соседние выглядели одинаково): свой верхний блок, своя
        #    подповерхность и своя её глубина.
        biome_ids = sorted(self.biomes) or []
        groups = [[bid] for bid in biome_ids]
        # top-блоки биомов — МАКСИМАЛЬНО разные (жалоба: «не всегда могу
        # отличить 2 биома друг от друга»): уникальный блок у КАЖДОГО
        # биома (used_top) + чередование семейств материалов
        # (recent_fams — последние 2 биома: камень/дерево/шерсть/металл
        # не должны идти подряд). ПОДЗЕМНЫЕ биомы-архетипы: top = ГЛАВНЫЙ
        # блок пола архетипа (мох/скалк/натёчный камень/мицелий/...) —
        # резервируем ЗАРАНЕЕ, ДО выбора поверхностных топов: их
        # идентичность важнее случайных коллизий (пол пышной пещеры —
        # ВСЕГДА мох), а поверхностные биомы просто обходят занятое
        # (пул палитры ~400 блоков — места хватает всем)
        used_top = set()
        arch_floor = {}
        arch_ceil = {}
        for bid in biome_ids:
            if bid in self.biome_underground:
                spec = CAVE_ARCHETYPES[self.biome_archetype[bid]]
                blk = spec["floor"]
                if self.world_shape == "void" \
                        and blk[0] in FALLING_BLOCK_IDS:
                    blk = (("minecraft:stone", None)
                           if blk[0] not in _PALETTE_EXCLUDE else blk)
                arch_floor[bid] = blk
                used_top.add(blk[0])
                if spec["ceiling"] is not None:
                    arch_ceil[bid] = spec["ceiling"]
        recent_fams = []
        for group in groups:
            bid = group[0]
            band = self.biome_band.get(bid)
            if band is not None:
                # ПОДЗЕМНЫЙ биом-АРХЕТИП: СИЛЬНЫЙ пол — главный блок
                # архетипа красит ВСЕ полы пещер биома (80-100% площади
                # пола), плюс 0-2 акцентных пятна (noise_threshold поверх
                # пола — как заплатки гравия у ванили) и подповерхностная
                # полоса из блоков архетипа. stone_depth матчит ЛЮБОЙ
                # пол/потолок с воздухом — в том числе пещерные
                spec = CAVE_ARCHETYPES[self.biome_archetype[bid]]
                top_blk = arch_floor[bid]
                sub_pool = [b for b in spec["sub"]
                            if b[0] != top_blk[0]] or [top_blk]
                sub_blk = self._falling_aware_choice(rng, sub_pool)
                sub_depth = rng.randint(4, 16)
                layers_seq = []
                # акцентные пятна: ВНУТРИ биомных слоёв, ДО основного
                # пола (первое совпадение побеждает) — условие шумовое,
                # оборачивает stone_depth (условия surface rules не
                # комбинируются all_of — только вложенностью)
                for _ in range(rng.randint(0, 2)):
                    if not spec["accent"]:
                        break
                    lo = rnd_f(rng, -0.6, -0.1)
                    hi = rnd_f(rng, 0.1, 0.6)
                    layers_seq.append({
                        "type": "minecraft:condition",
                        "if_true": {"type": "minecraft:noise_threshold",
                                    "noise": rng.choice(
                                        ["minecraft:surface",
                                         "minecraft:patch", "minecraft:ice",
                                         "minecraft:gravel",
                                         "minecraft:calcite",
                                         self.new_noise()]),
                                    "min_threshold": lo,
                                    "max_threshold": hi},
                        "then_run": {"type": "minecraft:sequence",
                                     "sequence": [{
                                         "type": "minecraft:condition",
                                         "if_true": {
                                             "type": "minecraft:stone_depth",
                                             "surface_type": "floor",
                                             "offset": 0,
                                             "add_surface_depth": False,
                                             "secondary_depth_range": 0},
                                         "then_run": {
                                             "type": "minecraft:block",
                                             "result_state": block_state(
                                                 rng.choice(
                                                     spec["accent"]))}}]}})
                layers_seq.append({
                    "type": "minecraft:condition",
                    "if_true": {"type": "minecraft:stone_depth",
                                "surface_type": "floor", "offset": 0,
                                "add_surface_depth": False,
                                "secondary_depth_range": 0},
                    "then_run": {"type": "minecraft:block",
                                 "result_state": block_state(top_blk)}})
                layers_seq.append({
                    "type": "minecraft:condition",
                    "if_true": {"type": "minecraft:stone_depth",
                                "surface_type": "floor", "offset": 0,
                                "add_surface_depth": True,
                                "secondary_depth_range": sub_depth},
                    "then_run": {"type": "minecraft:block",
                                 "result_state": block_state(sub_blk)}})
                # потолочный слой архетипа: ГАРАНТИРОВАН (где задан) —
                # мох на сводах пышной пещеры, скалк в глубокой тьме;
                # условие ceiling дизъюнктно с floor — порядок не важен
                if bid in arch_ceil:
                    layers_seq.append({
                        "type": "minecraft:condition",
                        "if_true": {"type": "minecraft:stone_depth",
                                    "surface_type": "ceiling", "offset": 0,
                                    "add_surface_depth": False,
                                    "secondary_depth_range": 0},
                        "then_run": {"type": "minecraft:block",
                                     "result_state": block_state(
                                         arch_ceil[bid])}})
                # «тело» биома (как ванильный deep_dark — весь массив
                # deepslate): catch-all ПОСЛЕДНИМ в последовательности
                # биома (без условия) — surface rules оцениваются на
                # КАЖДЫЙ блок биома, поэтому весь объём биома, не
                # попавший в акценты/полы/потолки, становится этим
                # камнем (стены/полы/потолки пещер)
                layers_seq.append({
                    "type": "minecraft:block",
                    "result_state": block_state(spec["stone"])})
                layers = {"type": "minecraft:sequence",
                          "sequence": layers_seq}
            else:
                # поверхностные слои — из палитры БЕЗ каменного семейства
                # (у семейства свои методы появления — блобы/полосы/
                # заплатки), без сыпучих в void-мирах и с уникальным
                # top-блоком (не как у соседей, семейство материалов
                # отличается от двух предыдущих)
                spool = self._surface_pool()
                top_blk = self._pick_top_block(rng, spool, used_top,
                                               recent_fams)
                fam = _material_family(top_blk[0])
                recent_fams.append(fam)
                if len(recent_fams) > 2:
                    recent_fams.pop(0)
                sub_blk = self._falling_aware_choice(
                    rng, [b for b in spool if b[0] != top_blk[0]] or spool)
                sub_depth = rng.randint(2, 12)
                layers = {
                    "type": "minecraft:sequence",
                    "sequence": [
                        # верхний блок (самая поверхность)
                        {"type": "minecraft:condition",
                         "if_true": {"type": "minecraft:stone_depth",
                                     "surface_type": "floor", "offset": 0,
                                     "add_surface_depth": False,
                                     "secondary_depth_range": 0},
                         "then_run": {"type": "minecraft:block",
                                      "result_state": block_state(top_blk)}},
                        # подповерхностная полоса на несколько блоков вглубь
                        {"type": "minecraft:condition",
                         "if_true": {"type": "minecraft:stone_depth",
                                     "surface_type": "floor", "offset": 0,
                                     "add_surface_depth": True,
                                     "secondary_depth_range": sub_depth},
                         "then_run": {"type": "minecraft:block",
                                      "result_state": block_state(sub_blk)}},
                    ],
                }
            used_top.add(top_blk[0])
            seq.append({
                "type": "minecraft:condition",
                "if_true": {"type": "minecraft:biome", "biome_is": group},
                "then_run": layers,
            })
        # если своих биомов не оказалось — один общий слоистый профиль
        if not biome_ids:
            spool = self._surface_pool()
            top_blk = self._falling_aware_choice(rng, spool)
            sub_blk = self._falling_aware_choice(rng, spool)
            seq.append({
                "type": "minecraft:condition",
                "if_true": {"type": "minecraft:stone_depth",
                            "surface_type": "floor", "offset": 0,
                            "add_surface_depth": False,
                            "secondary_depth_range": 0},
                "then_run": {"type": "minecraft:block",
                             "result_state": block_state(top_blk)},
            })
            seq.append({
                "type": "minecraft:condition",
                "if_true": {"type": "minecraft:stone_depth",
                            "surface_type": "floor", "offset": 0,
                            "add_surface_depth": True,
                            "secondary_depth_range": rng.randint(2, 12)},
                "then_run": {"type": "minecraft:block",
                             "result_state": block_state(sub_blk)},
            })
        # 5. ГЛУБИННЫЕ ПОЛОСЫ (как deepslate у камня, но 1-2 штуки с
        #    РАЗНЫМИ блоками каменного семейства): ниже порога весь
        #    массив становится блоком B, ещё ниже — блоком C. ПОСЛЕ
        #    биомных слоёв (у поверхности побеждают слои, в глубине —
        #    полоса), ГЛУБОКАЯ полоса — ПЕРВОЙ в sequence: внизу должно
        #    выиграть первое совпадение, т.е. самый глубокий блок.
        #    Высокие миры — всегда 2 полосы, ниже — 1-2. В void-мирах
        #    полос нет: острова тонкие, «глубина» внутри острова не
        #    имеет смысла (и сыпучие исключены уже на выборе семейства)
        self._n_deep_bands = 0
        if self.world_shape != "void":
            band_blks = list(getattr(self, "_family_bands", []))
            if not band_blks:
                band_blks = [self._falling_aware_choice(
                    rng, self._terrain_palette())]
            anchor_mid = self.min_y + max(
                16, int(self.height * rng.uniform(0.25, 0.45)))
            # КАП: средняя полоса — нижняя четверть-почти-половина мира
            # (как ванильный deepslate с ~25% высоты). Было randint от
            # min_y+8 (!) — полоса могла начаться у самого дна и
            # ЗАЛИВАТЬ одним блоком всю толщу мира («мир из одного блока»)
            band_rules = []
            if len(band_blks) >= 2:
                # глубокая полоса: у самого дна (5-18% высоты, всегда
                # ниже средней хотя бы на 16 блоков)
                anchor_deep = min(
                    self.min_y + max(4, int(self.height * rng.uniform(0.05, 0.18))),
                    anchor_mid - 16)
                band_rules.append((anchor_deep, band_blks[1],
                                   rng.randint(8, 48), 2))
            band_rules.append((anchor_mid, band_blks[0],
                               rng.randint(16, 96), 1))
            for ay, blk, trans, idx in band_rules:
                seq.append({
                    "type": "minecraft:condition",
                    "if_true": {"type": "minecraft:vertical_gradient",
                                "random_name": "%s:%s/deep_band%d" % (
                                    self.ns, self.name, idx),
                                "true_at_and_below": {"absolute": ay},
                                "false_at_and_above": {
                                    "absolute": min(ay + trans, self.max_y)}},
                    "then_run": {"type": "minecraft:block",
                                 "result_state": block_state(blk)},
                })
                self._n_deep_bands += 1
        # ВАЖНО: без catch-all! Раньше финальный случайный блок перекрашивал
        # ВСЁ тело мира одним блоком (однообразные равнины) — теперь база
        # это default_block, а разнообразие дают слои выше.
        return {"type": "minecraft:sequence", "sequence": seq}

    # ---------------- биомы ----------------

    def _deal_carvers(self, n_biomes, boost=()):
        """Карверы общего пула — каждому биому СВОИ (каждый карвер достаётся
        ровно одному биому; у биома 0-3 своих карвера). Непересекающиеся
        порции вместо общего пула = пер-биомная идентичность пещер.
        boost — индексы ПОДЗЕМНЫХ биомов с тройным весом: пещерным биомам
        нужно больше карверов (плотная сеть пещер — их суть), надземным
        от этого хуже не становится — пул общий, просто перераспределяется."""
        rng = self.rng
        ids = sorted(self.carvers_cfg)
        rng.shuffle(ids)
        out = [[] for _ in range(n_biomes)]
        weights = [3 if i in boost else 1 for i in range(n_biomes)]
        for cid in ids:
            out[rng.choices(range(n_biomes), weights=weights)[0]].append(cid)
        return out

    def _contrast_color(self, rng, role, min_dist=80.0, tries=32):
        """Цвет, ЗАМЕТНО отличающийся от уже назначенных цветов ТОЙ ЖЕ
        роли (небо/туман/вода/трава/листва) у других биомов измерения:
        евклидова дистанция RGB >= min_dist. Роли разделены — небеса
        двух биомов обязаны отличаться, а небо и туман одного биома
        могут быть близки (в ванили они часто тонально связаны).
        Если за tries случайных кандидатов порог не найден (много
        биомов — пространство насыщается), берём САМОГО дальнего от
        уже занятых (maximin) — распределение всё равно остаётся
        равномерно-разведённым, зависнуть нельзя."""
        hist = self._color_hist.setdefault(role, [])
        best, best_d = None, -1.0
        for _ in range(tries):
            c = rand_color(rng)
            if not hist:
                hist.append(c)
                return c
            d = min(_rgb_dist(h, c) for h in hist)
            if d >= min_dist:
                hist.append(c)
                return c
            if d > best_d:
                best, best_d = c, d
        hist.append(best)
        return best

    def _feature_types(self, cfg):
        """Множество «видов» набора СВОИХ фич биома — по полю type
        configured-фичи (minecraft:tree / minecraft:disk /
        minecraft:simple_block / ...): вид = воспринимаемая игроком
        суть декорации (random_patch в 26.2 стал simple_block — «вид»
        по type честнее внутреннего имени генератора)."""
        return frozenset(v.get("type") for v in cfg.values()
                         if isinstance(v, dict) and v.get("type"))

    @staticmethod
    def _feature_signature_score(kinds, prev_sets):
        """Число НАРУШЕНИЙ сигнатурности набора видов фич против уже
        принятых наборов остальных биомов (0 = идеально):
          1. «2+ общих вида с каким-то одним биомом» — пересечения
             должны быть редки (при 2+ набор перегенерируется);
          2. у НОВОГО биома нет ни одного вида вне чужих наборов —
             нечему отличаться от соседей;
          3. набор крадёт последнюю сигнатуру прежнего биома (после
             вставки у того не остаётся ни одного уникального вида)."""
        shared = 0
        for other in prev_sets:
            if other:
                shared = max(shared, len(kinds & other))
        viol = max(0, shared - 1)
        if kinds:
            union = frozenset().union(*prev_sets) if prev_sets \
                else frozenset()
            if not (kinds - union):
                viol += 1
        for j, other in enumerate(prev_sets):
            if not other:
                continue
            rest = [s for k, s in enumerate(prev_sets) if k != j]
            rest.append(kinds)
            union_rest = frozenset().union(*rest)
            if not (other - union_rest):
                viol += 1
        return viol

    def _rand_biome_features(self, idx, band, prev_sets):
        """Свои фичи биома (1-6 configured × 1-2 placed, префикс
        <name>_b<idx>) с проверкой СИГНАТУРНОСТИ (жалоба: «до сих пор
        не всегда могу отличить 2 биома измерения»): у биома — хотя бы
        один вид фич, которого нет НИ У ОДНОГО соседа, и не больше
        одного общего вида с любым отдельным биомом. Механика:
          1. до 6 попыток перегенерации (Reject-попытки в реестры не
             попадают — id между попытками совпадают из-за общего
             префикса, конфликтов нет);
          2. ФИКС-АП: если у лучшего набора нет своего вида — ДОБАВЛЯЕМ
             одну фичу свежего вида (отдельный префикс _x — id не
             пересекаются с основным набором). Свежий вид ничью
             сигнатуру не крадёт и ни с кем не пересекается — нарушения
             не растут; базовый count урезан до 1-5, чтобы с фикс-апом
             остаться в рамках «свои фичи 1-6».
        В конце — лучший по числу нарушений (зависнуть нельзя: пул
        видов ~50, биомов <= 20)."""
        rng = self.rng
        prefix = "%s_b%d" % (self.name, idx)
        cave = band is not None
        union = frozenset().union(*prev_sets) if prev_sets else frozenset()
        best, best_score = None, None
        for _ in range(6):
            cfg, placed, tags = gen_features.rand_features(
                rng, self.ns, prefix, self.min_y, self.max_y - 1,
                count=rng.randint(1, 5), cave=cave,
                no_gravity=self.world_shape == "void")
            kinds = self._feature_types(cfg)
            score = self._feature_signature_score(kinds, prev_sets)
            if best_score is None or score < best_score:
                best, best_score = (cfg, placed, tags, kinds), score
            if score == 0:
                break
        cfg, placed, tags, kinds = best
        # ФИЛЬТР попарных пересечений: best-of-6 — ВЕРОЯТНОСТНЫЙ, и при
        # 15-20 биомах (пул ~50 видов) лучший набор всё ещё может делить
        # 2+ вида с каким-то одним биомом. Выбрасываем лишние общие
        # виды, пока пересечение с каждым прежним набором не станет <= 1
        # — инвариант различимости биомов (жалоба юзера) становится
        # детерминированным. Набор не пустеет: при одном виде
        # пересечение >= 2 невозможно, цикл всегда завершается.
        tmap = {cid: v.get("type") for cid, v in cfg.items()
                if isinstance(v, dict) and v.get("type")}
        killed_all = set()
        while len(kinds) >= 2:
            over = None
            for other in prev_sets:
                shared = kinds & other
                if len(shared) >= 2:
                    over = shared
                    break
            if over is None:
                break
            # удаляем общий вид с наименьшим числом фич в наборе
            drop = min(over, key=lambda t: sum(
                1 for v in tmap.values() if v == t))
            kill = {cid for cid, t in tmap.items() if t == drop}
            killed_all |= kill
            cfg = {cid: v for cid, v in cfg.items() if cid not in kill}
            placed = {pid: p for pid, p in placed.items()
                      if p["feature"] not in kill}
            for cid in kill:
                tmap.pop(cid, None)
            kinds = frozenset(t for t in tmap.values() if t)
        # чиним ВИСЯЧИЕ ссылки селекторов: selector/sequence-фичи ссылаются
        # «назад» на уже созданные id (inline {"feature": id}) — фильтр
        # выше мог УБИТЬ цель (реальный случай: ostyadorn_b18_fossil1 —
        # сервер «Unbound values in registry configured_feature» при
        # отсутствующем файле-цели). Заменяем битые ссылки на ванильные
        if killed_all:
            def _fix_refs(node):
                if isinstance(node, dict):
                    f = node.get("feature")
                    if isinstance(f, str) and f in killed_all:
                        node["feature"] = rng.choice(
                            gen_features.VANILLA_CFG_IDS)
                    for v in node.values():
                        _fix_refs(v)
                elif isinstance(node, list):
                    for v in node:
                        _fix_refs(v)
            for c in cfg.values():
                _fix_refs(c)
            for p in placed.values():
                _fix_refs(p)
        if kinds and not (kinds - union):
            # нет НИ ОДНОГО своего вида — добавляем фичу свежего вида
            for _ in range(8):
                cfg2, placed2, tags2 = gen_features.rand_features(
                    rng, self.ns, prefix + "_x", self.min_y,
                    self.max_y - 1, count=1, cave=cave,
                    no_gravity=self.world_shape == "void")
                k2 = self._feature_types(cfg2)
                if k2 and not (k2 & union) and not (k2 & kinds):
                    cfg.update(cfg2)
                    placed.update(placed2)
                    tags.update(tags2)
                    kinds = kinds | k2
                    break
        if kinds and any(kinds == s for s in prev_sets):
            # ТОЧНЫЙ дубликат набора видов (одиночный вид, уже занятый
            # другим биомом; возможен при 25-30 биомах, когда пул ~50
            # видов исчерпан и фикс-ап не нашёл свежего) — оставляем
            # биому только общий пул измерения: биом без своих фич
            # легален (~10% биомов и так без них), а инвариант
            # различимости наборов (никакие два не совпадают) держится
            return {}, {}, {}
        return cfg, placed, tags

    def rand_biome(self, biome_feats, biome_carvers, biome_mobs, band=None,
                   arch=None):
        """Полностью случайный биом (формат 26.2: почти всё из старых
        effects переехало в attributes, carvers — строка/список).
        Пер-биомный контекст: biome_feats — СВОИ placed-фичи биома,
        biome_carvers — СВОИ карверы (непересекающиеся с другими биомами),
        biome_mobs — СВОЯ фауна {категория: [мобы]}. band — depth-полоса
        ПОДЗЕМНОГО биома (None = надземный): подземному — пещерный
        ванильный пул фич, плотнее карверы, тёмная фауна, руды побогаче
        и никаких осадков (небо ему не видно). arch — АРХЕТИП подземного
        биома (CAVE_ARCHETYPES[...]): его сигнатурные ванильные фичи-
        бонусы (arch["vanilla"]), themed-фауна (arch["mobs"]) и лимит
        озёрного класса (максимум 0-1 озёрной фичи, не в каждом биоме —
        раньше «спам подземными озёрами»)."""
        rng = self.rng
        underground = band is not None

        # effects: в 26.2 остались только цвета (туман/небо — в attributes).
        # Все цвета — КОНТРАСТНЫЕ между биомами (жалоба «не всегда могу
        # отличить 2 биома»): _contrast_color разводит цвета одной роли
        # у разных биомов на дистанцию >= 80 RGB; вероятности повышены —
        # у большего числа биомов свои небо/туман/вода/трава
        effects = {"water_color": self._contrast_color(rng, "water")}
        if rng.random() < 0.55:
            effects["grass_color"] = self._contrast_color(rng, "grass")
        if rng.random() < 0.45:
            effects["foliage_color"] = self._contrast_color(rng, "foliage")
        if rng.random() < 0.20:
            effects["dry_foliage_color"] = self._contrast_color(
                rng, "dry_foliage")
        if rng.random() < 0.12:
            effects["grass_color_modifier"] = rng.choice(GRASS_COLOR_MODIFIERS)

        attrs = {}
        if rng.random() < 0.80:
            attrs["minecraft:visual/sky_color"] = self._contrast_color(
                rng, "sky")
        if rng.random() < 0.55:
            attrs["minecraft:visual/fog_color"] = self._contrast_color(
                rng, "fog")
        if rng.random() < 0.40:
            attrs["minecraft:visual/water_fog_color"] = self._contrast_color(
                rng, "water_fog")
        if rng.random() < 0.12:
            attrs["minecraft:visual/water_fog_end_distance"] = {
                "argument": rnd_f(rng, 0.1, 1.5), "modifier": "multiply"}
        if rng.random() < 0.35:
            attrs["minecraft:visual/ambient_particles"] = [{
                "particle": {"type": rng.choice(AMBIENT_PARTICLES)},
                "probability": rnd_f(rng, 0.005, 0.05, 4)}]
        if rng.random() < 0.15:
            attrs["minecraft:gameplay/increased_fire_burnout"] = rng.random() < 0.5
        if rng.random() < 0.10:
            attrs["minecraft:gameplay/snow_golem_melts"] = rng.random() < 0.5
        if rng.random() < 0.08:
            attrs["minecraft:gameplay/can_pillager_patrol_spawn"] = rng.random() < 0.5
        if rng.random() < 0.10:
            attrs["minecraft:audio/music_volume"] = rnd_f(rng, 0.0, 1.0)
        if rng.random() < 0.30:
            lo = rng.randint(3000, 12000)
            attrs["minecraft:audio/background_music"] = {"default": {
                "sound": rng.choice(MUSIC_IDS),
                "min_delay": lo, "max_delay": lo + rng.randint(4000, 24000)}}
        if rng.random() < 0.12:
            base = rng.choice(AMBIENT_SOUND_BASES)
            attrs["minecraft:audio/ambient_sounds"] = {
                "loop": base + ".loop",
                "additions": {"sound": base + ".additions",
                              "tick_chance": rnd_f(rng, 0.001, 0.02, 4)},
                "mood": {"sound": base + ".mood",
                         "tick_delay": rng.randint(2000, 10000),
                         "block_search_extent": rng.randint(4, 16),
                         "offset": rng.choice([1.0, 2.0])}}

        # ванильные карверы: подземным биомам — чаще (плотная пещерная
        # сеть — суть пещерного биома)
        carvers = [c for c in CARVERS
                   if rng.random() < (0.6 if underground else 0.35)
                   and CARVER_BOUNDS[c](self.min_y, self.max_y)]
        # СВОИ карверы биома — из непересекающейся порции общего пула
        # (подземные получают тройную долю — см. _deal_carvers)
        carvers += biome_carvers
        # ТЕМАТИЧЕСКИЕ карверы архетипа: подземный биом ВСЕГДА получает
        # карверы своего архетипа (дедуп с уже выданными; случайный
        # общий пул с бустом остаётся как дополнение)
        if arch:
            for c in arch["carvers"]:
                if c not in carvers \
                        and CARVER_BOUNDS[c](self.min_y, self.max_y):
                    carvers.append(c)

        # 11 шагов декорации; шаг каждой фичи фиксирован на всё измерение
        # (см. _feature_step_of) — иначе цикл порядка фич и краш генерации
        features = [[] for _ in range(11)]
        # ванильные фичи — меньше, чем раньше: основа идентичности биома
        # теперь его СОБСТВЕННЫЕ фичи; ваниль идёт фоном (руда/трава)
        total = rng.randint(0, 4)
        if rng.random() < 0.6:   # ~underground_ores
            total += rng.randint(2, 8)
        if rng.random() < 0.5:   # ~vegetation
            total += rng.randint(0, 4)
        # ванильные фичи — только с height_range, непустым для ГРАНИЦ
        # этого измерения (иначе «Empty height range» на каждый чанк).
        # Подземным биомам — только пещерная кунсткамера (glow_lichen,
        # large_dripstone, sculk, жеоды, комнаты монстров...): прочие
        # ванильные фичи завязаны на поверхность. ОЗЁРНЫЙ КЛАСС исключён
        # из общего пула подземных (спам озёрами): максимум 0-1 таких
        # фичи на биом и не в каждом (шанс 0.3). VOID-миры: ванильные
        # диски песка/гравия и гравийные жилы исключены — сыпучие над
        # пустотой обращаются в entity FALLING_BLOCK (см.
        # FALLING_BLOCK_IDS / VOID_UNSAFE_PLACED)
        vpool = [f for f in (CAVE_PLACED_FEATURES if underground
                             else PLACED_FEATURES)
                 if placed_fits(f, self.min_y, self.max_y)]
        if self.world_shape == "void":
            vpool = [f for f in vpool if f not in VOID_UNSAFE_PLACED]
        if underground:
            vpool = [f for f in vpool if f not in LAKE_CLASS_FEATURES]
        vfeats = set(rng.sample(vpool, min(total, len(vpool))))
        if underground:
            lakes = [f for f in LAKE_CLASS_FEATURES
                     if placed_fits(f, self.min_y, self.max_y)]
            if lakes and rng.random() < 0.3:
                vfeats.add(rng.choice(lakes))
            # ванильные фичи-бонусы АРХЕТИПА: тематический вкус поверх
            # сигнатурных СВОИХ фич (каждая — с вероятностью 0.7)
            if arch:
                for f in arch.get("vanilla", []):
                    if f not in vfeats and rng.random() < 0.7 \
                            and placed_fits(f, self.min_y, self.max_y):
                        vfeats.add(f)
        for f in sorted(vfeats):
            fid = "minecraft:" + f
            features[self._feature_step_of(fid)].append(fid)

        # СВОИ placed-фичи биома — все до единого (1-6 configured × 1-2
        # placed, сгенерированы с префиксом <name>_b<i> только для него)
        for fid in biome_feats:
            features[self._feature_step_of(fid)].append(fid)

        # КАМЕННЫЕ БЛОБЫ семейства — в КАЖДЫЙ биом (включая подземные):
        # как ванильные ore_andesite/ore_granite, камень генерится ВЕЗДЕ,
        # это не пер-биомная декорация (пер-биомные множители — только у
        # руд, их не трогаем). Шаг — underground_ores, как у ванильных
        # блобов камня; шаг фиксирован на всё измерение (_feature_step_of)
        for fid in getattr(self, "_global_feats", []):
            features[self._feature_step_of(fid, prefer=6)].append(fid)

        # из общего пула измерения — 0-2 фичи для связности мира
        # (только надземным: общий пул — поверхностные декорации)
        if self._shared_feats and not underground and rng.random() < 0.5:
            k = min(rng.randint(0, 2), len(self._shared_feats))
            for fid in rng.sample(self._shared_feats, k):
                features[self._feature_step_of(fid)].append(fid)

        # РУДНАЯ СИСТЕМА: каждый вид руды измерения входит в биом на
        # СВОЁМ уровне богатства — ×0.3/×1/×2.5/×5 (или отсутствует, 12%).
        # В одном биоме руда богатая, в другом бедная — биомы минируются
        # по-разному. Подземным — сдвиг к богатым вариантам: добыча в
        # пещерном биоме должна награждаться. Шаг — почти всегда 6
        # (underground_ores, как у ванильных руд)
        for tiers in getattr(self, "ore_variants", {}).values():
            if rng.random() < 0.12:
                continue          # этой руды в биоме нет совсем
            if underground:
                tier = rng.choices(
                    ("poor", "normal", "rich", "motherlode"),
                    weights=[8, 30, 42, 20])[0]
            else:
                tier = rng.choices(
                    ("poor", "normal", "rich", "motherlode"),
                    weights=[25, 45, 22, 8])[0]
            fid = tiers[tier]
            features[self._feature_step_of(fid, prefer=6)].append(fid)

        # FeatureSorter требует не только одинаковый ШАГ фичи во всех
        # биомах, но и одинаковый ОТНОСИТЕЛЬНЫЙ ПОРЯДОК внутри шага —
        # иначе "Feature order cycle found" и краш генерации чанков.
        # Лексикографическая сортировка даёт единый порядок везде.
        for lst in features:
            lst.sort()

        # фауна: подземным биомам — фауна АРХЕТИПА (тематика как в
        # ваниле: глубокая тьма и грибная — БЕЗ монстров вообще, как
        # deep_dark/mushroom_fields; магмовая — незер-эскадра, замёрзшая
        # — страй-скелеты; остальные — своя разбивка + 2-4 тёмных
        # моба). Надземным — своя разбивка _deal_mobs без изменений
        pool_mobs = biome_mobs
        if underground:
            spec = (arch or {}).get("mobs", {})
            ms = spec.get("monsters", ("dark", (2, 4)))
            pool_mobs = {c: list(v) for c, v in biome_mobs.items()}
            if ms[0] == "list":
                # themed-список ЗАМЕНЯЕТ монстров биома — как у ванильных
                # биомов с фиксированным списком (dripstone: drowned)
                themed = list(dict.fromkeys(ms[1]))
                k = min(rng.randint(*ms[2]), len(themed))
                pool_mobs["monster"] = rng.sample(themed, k)
            elif ms[0] == "dark":
                own = biome_mobs.get("monster") or []
                k = rng.randint(*ms[1])
                pool_mobs["monster"] = own + [
                    m for m in rng.sample(DARK_MOBS, min(k, len(DARK_MOBS)))
                    if m not in own]
            else:                     # "none" — как ванильный deep_dark
                pool_mobs["monster"] = []
            bat_p = spec.get("ambient_bat", 0.6)
            gs_p = spec.get("glow_squid", 0.5)
            if ms[0] == "none" and bat_p <= 0.0 and gs_p <= 0.0:
                # глубокая тьма: НИ ОДНОЙ записи спавна — мёртвая
                # тишина, как vanilla deep_dark (все категории пусты)
                pool_mobs = {c: [] for c in biome_mobs}
            else:
                if bat_p <= 0.0:
                    pool_mobs["ambient"] = []
                elif rng.random() < bat_p:
                    amb = pool_mobs.get("ambient") or []
                    if "minecraft:bat" not in amb:
                        pool_mobs["ambient"] = amb + ["minecraft:bat"]
                if rng.random() < gs_p:
                    uw = pool_mobs.get("underground_water_creature") or []
                    if "minecraft:glow_squid" not in uw:
                        pool_mobs["underground_water_creature"] = \
                            uw + ["minecraft:glow_squid"]
            # пасивных животных в пещерах не оставляем — им там нечего
            # есть (коровы на мхе под землёй — не пещерная фауна)
            pool_mobs["creature"] = []

        spawners = {}
        for cat, tiers in SPAWN_POOLS.items():
            # СВОЯ фауна биома: раскладка _deal_mobs (каждый моб — 1-2
            # биома). Пустая категория = «тихий» биом — нормально
            pool = pool_mobs.get(cat) or []
            if not pool:
                spawners[cat] = []
                continue
            # ЖЁСТКИЕ лимиты плотности спавна: мало записей (иначе локальный
            # моб-кап постоянно переполняется и чанк-спавнер без остановки
            # плодит новых), маленькие группы, скромные веса.
            cap = {"monster": 4, "creature": 3}.get(cat, 1)
            # подземный биом без монстров — не пещера: тёмная фауна
            # гарантирована (тихими бывают только надземные биомы)
            quiet = 0.0 if (underground and cat == "monster") else 0.25
            k = 0 if rng.random() < quiet else rng.randint(1, min(cap, len(pool)))
            entries = []
            for etype in rng.sample(pool, k):
                # боссы (висер/дракон/варден) — МИНИМАЛЬНАЯ запись:
                # вес 1 (обычные получают 1-30) и группа ровно из 1
                if etype in BOSS_MOBS:
                    entries.append({"type": etype, "weight": 1,
                                    "minCount": 1, "maxCount": 1})
                    continue
                lo = rng.randint(1, 2)
                # водные стайные мобы и лягушки: maxCount не выше 2 —
                # меньше «стай» на один спавн-цикл
                hi = 2 if (cat in WATERY_SPAWN_CATS
                           or etype == "minecraft:frog") else 4
                entries.append({"type": etype, "weight": rng.randint(1, 30),
                                "minCount": lo, "maxCount": rng.randint(lo, hi)})
            spawners[cat] = entries

        # spawn_costs на ВСЕ монстров биома: energy_budget жёстко режет
        # плотность спавна вокруг игрока (низкий бюджет = мало спавнов)
        costs = {}
        mtiers = SPAWN_POOLS["monster"]
        for e in spawners.get("monster", []):
            costs[e["type"]] = {"energy_budget": rnd_f(rng, 0.02, 0.12),
                                "charge": rnd_f(rng, 0.3, 1.5)}

        biome = {
            # подземным биомам осадки ни к чему — их «небо» это камень
            "has_precipitation": False if underground else rng.random() < 0.6,
            "temperature": rnd_f(rng, -0.5, 2.0),
            "downfall": rnd_f(rng, 0.0, 1.0),
            "effects": effects,
            "carvers": carvers,
            "features": features,
            "spawners": spawners,
            "spawn_costs": costs,
        }
        if rng.random() < 0.08:
            biome["temperature_modifier"] = "frozen"
        if attrs:
            biome["attributes"] = attrs
        return biome

    # ---------------- biome source ----------------

    def _biome_source_multi_noise(self, ids):
        """multi_noise из СВОИХ биомов (основной вид биом-сорса).

        Параметры биомов — ДИАПАЗОНЫ [min,max], как у ванили (её биомы —
        узкие полосы, тайлящие пространство каналов; формат массива из
        2 чисел стабилен с 1.18), а не точки в 6-мерном кубе: случайные
        точки почти не накрывают реальные значения каналов, и размещение
        решает bias (аудит на 31 мире: медиана топ-2 биомов 71% площади,
        56% биомов мельче 2% — /locate biome их не находил).

        НАДЗЕМНЫЕ биомы: erosion/weirdness/depth/offset — ОДИНАКОВЫ у
        всех (depth 0.0, как у поверхностных биомов ванили), разведение —
        по temperature/humidity (квантильная решётка a×b внутри
        кластера) и continentalness (непересекающиеся диапазоны
        кластеров рельефа).

        ПОДЗЕМНЫЕ биомы (self.biome_underground, полосы — в generate):
        depth — своя НЕПЕРЕСЕКАЮЩАЯСЯ полоса внутри подземной зоны
        [CAVE_BAND_TOP, CAVE_BAND_BOTTOM] (0.2..1.45; канал depth —
        рампа 1.5 у дна → -1.5 у потолка; ~0 — середина высоты,
        примерный уровень поверхности). Математика расстояний
        multi_noise: на поверхности и выше канал <= 0 — надземный биом
        (depth 0.0) ближе любого подземного (полосы >= 0.2 — расстояние
        с запасом больше); в подземной полосе
        побеждает биом своей полосы; между полосами и в остальном
        подземном пространстве — надземные биомы (как в ваниле:
        dripstone_caves тайлят только свой пояс, а «под столицей» —
        обычные биомы). continentalness подземных нейтрализован
        [-1.5, 1.5] — пещеры не зависят от кластеров рельефа;
        temperature/humidity — СВОЯ квантильная решётка (тайлит
        пространство внутри полосы)."""
        rng = self.rng
        # надземные — по кластерам рельефа (биомы кластера делят
        # пространство temperature×humidity, кластеры разведены по
        # continentalness); подземные — отдельной системой ниже
        groups = {}
        under = []
        for bid in ids:
            if bid in self.biome_underground:
                under.append(bid)
            else:
                groups.setdefault(self.biome_cluster.get(bid, 0), []).append(bid)
        corr = getattr(self, "terrain_corr", False)
        half = 0.06
        if corr:
            # полуширина continentalness-диапазона кластера: не больше
            # 0.06 (как раньше) и не больше четверти минимального зазора
            # между центрами — диапазоны кластеров не пересекаются
            cs = sorted(c for c, _ in self.terr_clusters)
            gaps = [y - x for x, y in zip(cs, cs[1:])] or [1.0]
            half = min(0.06, min(gaps) / 4.0)
        inv = statistics.NormalDist().inv_cdf
        biomes = []
        for cid in sorted(groups):
            group = groups[cid]
            k = len(group)
            # решётка a×b ячеек (a=ceil(sqrt(k)), b=ceil(k/a)) ≥ k:
            # temperature делится на a полос, humidity — на b
            a = max(1, math.ceil(math.sqrt(k)))
            b = max(1, math.ceil(k / a))
            # границы ячеек — квантили нормальной маргинали канала
            # (σ вычислена в _prepare_climate): ячейки равновелики по
            # площади и вместе тайлят распределение канала. Квантиль 0
            # бесконечна — нижняя ячейка продлевается до -1.5 (~ -3σ,
            # хвост пренебрежимо мал)
            st = self.climate_sigma.get("temperature", 0.5)
            sh = self.climate_sigma.get("vegetation", 0.5)
            tcells = [[-1.5 if i == 0 else round(st * inv(i / (a + 1)), 3),
                       round(st * inv((i + 1) / (a + 1)), 3)]
                      for i in range(a)]
            hcells = [[-1.5 if j == 0 else round(sh * inv(j / (b + 1)), 3),
                       round(sh * inv((j + 1) / (b + 1)), 3)]
                      for j in range(b)]
            if corr:
                cc = self.terr_clusters[cid][0]
                cont = [round(cc - half, 3), round(cc + half, 3)]
            else:
                # без climate-корреляции канал continents с кластерами
                # не согласован — нейтрализуем общим диапазоном
                cont = [-1.5, 1.5]
            for m, bid in enumerate(group):
                params = {
                    "temperature": tcells[m // b],
                    "humidity": hcells[m % b],
                    "continentalness": cont,
                    "erosion": 0.0,
                    "weirdness": 0.0,
                    "depth": 0.0,
                    "offset": 0.0,
                }
                biomes.append({"biome": bid, "parameters": params})
        # ПОДЗЕМНЫЕ биомы: своя квантильная решётка temperature/humidity
        # (по СВОИМ ячейкам — тайлит пространство внутри полосы, как у
        # надземных, но глобально, без кластеров), нейтрализованный
        # continentalness и своя depth-полоса из biome_band
        if under:
            k = len(under)
            a = max(1, math.ceil(math.sqrt(k)))
            b = max(1, math.ceil(k / a))
            st = self.climate_sigma.get("temperature", 0.5)
            sh = self.climate_sigma.get("vegetation", 0.5)
            tcells = [[-1.5 if i == 0 else round(st * inv(i / (a + 1)), 3),
                       round(st * inv((i + 1) / (a + 1)), 3)]
                      for i in range(a)]
            hcells = [[-1.5 if j == 0 else round(sh * inv(j / (b + 1)), 3),
                       round(sh * inv((j + 1) / (b + 1)), 3)]
                      for j in range(b)]
            for m, bid in enumerate(under):
                params = {
                    "temperature": tcells[m // b],
                    "humidity": hcells[m % b],
                    "continentalness": [-1.5, 1.5],
                    "erosion": 0.0,
                    "weirdness": 0.0,
                    "depth": list(self.biome_band.get(
                        bid, [CAVE_BAND_TOP, 0.9])),
                    "offset": 0.0,
                }
                biomes.append({"biome": bid, "parameters": params})
        return {"type": "minecraft:multi_noise", "biomes": biomes}

    def rand_biome_source(self):
        """Биом-сорс. Вид решён заранее в generate() (self.bs_kind) —
        multi_noise из СВОИХ биомов основной (пер-биомная генерация),
        при climate-корреляции continentalness биома задаёт его кластер
        рельефа (см. self.terr_clusters / spline в rand_final_density)."""
        rng = self.rng
        ids = sorted(self.biomes) or [self._rand_biome()]
        kind = getattr(self, "bs_kind", "multi_noise")
        if kind == "multi_noise":
            return self._biome_source_multi_noise(ids)
        if kind == "checkerboard":  # шахматка из своих биомов
            # ВСЕ биомы измерения (не выборка): шахматка проходит список
            # по кругу — каждый биом получает ровно 1/len(ids) площади и
            # находится через /locate. scale 8 (256 блоков) убран —
            # слишком крупные клетки
            shuffled = list(ids)
            rng.shuffle(shuffled)
            return {"type": "minecraft:checkerboard",
                    "biomes": shuffled,
                    "scale": rng.choice([0, 1, 2, 4])}
        if kind == "fixed":
            return {"type": "minecraft:fixed", "biome": rng.choice(ids)}
        if kind == "preset":  # ванильный пресет для разнообразия
            # пресет тянет КОДОВЫЕ ванильные structure sets с фиксированными
            # якорями: nether_fossil [absolute(32), below_top(2)] требует
            # top >= 35, ore_coal_upper [absolute(136), below_top(0)] —
            # top >= 137; иначе «Empty height range». Низкие миры уходят
            # на multi_noise из СВОИХ биомов.
            if self.max_y >= 137:
                preset = rng.choice(["minecraft:overworld", "minecraft:nether"])
            elif self.max_y >= 35:
                preset = "minecraft:nether"
            else:
                return self._biome_source_multi_noise(ids)
            return {"type": "minecraft:multi_noise", "preset": preset}
        return {"type": "minecraft:the_end"}

    # ---------------- dimension type ----------------

    def rand_dimension_type(self):
        rng = self.rng
        dt = {
            "ambient_light": rnd_f(rng, 0.0, 0.4),
            "coordinate_scale": rng.choice([0.03125, 0.0625, 0.125, 0.25, 0.5,
                                            1.0, 1.0, 2.0, 4.0, 8.0]),
            # skylight: светлое небо (15) — почти всегда; тьма — редкость
            # (cavern-миры под кровлей всегда без skylight)
            "has_ceiling": self.world_shape == "cavern",
            "has_skylight": (False if self.world_shape == "cavern"
                             else rng.random() < 0.93),
            "has_ender_dragon_fight": rng.random() < 0.1,
            "height": self.height,
            "infiniburn": rng.choice(INFINIBURN),
            "logical_height": rng.random() < 0.7 and self.height
                              or max(16, (self.height // rng.choice([2, 3, 4])
                                          // 16) * 16),
            "min_y": self.min_y,
            # СТРОГО: монстры спавнятся только в темноте — block_light_limit
            # низкий (факелы реально защищают), как в ванильном overworld
            "monster_spawn_block_light_limit": rng.choice([0, 0, 1, 2, 3, 4, 5,
                                                          6, 7, 8]),
            "monster_spawn_light_level": self._rand_light_level(),
            "infiniburn": ("#%s:%s" % (self.ns, self.name))
                          if self.infiniburn_tag else rng.choice(INFINIBURN),
        }
        if rng.random() < 0.25:
            dt["skybox"] = rng.choice(["none", "end"])
        if rng.random() < 0.15:
            dt["cardinal_light"] = "nether"
        if self.custom_time:
            # 26.2: время через свои world_clock + тег timeline
            dt["default_clock"] = "%s:%s" % (self.ns, self.name)
            dt["timelines"] = "#%s:%s" % (self.ns, self.name)
        else:
            if rng.random() < 0.3:
                dt["default_clock"] = rng.choice(["minecraft:overworld",
                                                  "minecraft:the_end"])
            if rng.random() < 0.3:
                dt["timelines"] = rng.choice(TIMELINE_TAGS)
        dt["attributes"] = self._rand_attributes()
        return dt

    def _rand_light_level(self):
        """Уровень света, при котором спавнятся монстры. СТРОГО ТЕМНОЙ
        стороной: никогда не выше 7 (как ванильный overworld), иначе монстры
        плодятся круглосуточно и моб-кап захлёбывается."""
        rng = self.rng
        if rng.random() < 0.6:
            return rng.randint(0, 4)      # фикс. тьма
        lo = rng.randint(0, 3)
        return {"type": "minecraft:uniform", "min_inclusive": lo,
                "max_inclusive": rng.randint(lo, 7)}

    def _rand_attributes(self):
        rng = self.rng
        attrs = {}

        def chance(p):
            return rng.random() < p

        if chance(0.35):  # цвета неба/тумана
            attrs["minecraft:visual/sky_color"] = rand_color(rng)
        if chance(0.35):
            attrs["minecraft:visual/fog_color"] = rand_color(rng)
        if chance(0.25):
            attrs["minecraft:visual/ambient_light_color"] = rand_color(rng)
        if chance(0.2):
            attrs["minecraft:visual/cloud_color"] = "#%02x%06x" % (
                rng.randint(0, 255), rng.getrandbits(24))
        if chance(0.2):
            attrs["minecraft:visual/cloud_height"] = rnd_f(rng, -16.0, 320.0)
        if chance(0.2):
            start = rnd_f(rng, 0.0, 128.0)
            attrs["minecraft:visual/fog_start_distance"] = start
            attrs["minecraft:visual/fog_end_distance"] = start + rnd_f(rng, 16.0, 256.0)
        if chance(0.15):
            attrs["minecraft:visual/sky_light_color"] = rand_color(rng)
        if chance(0.15):
            attrs["minecraft:visual/sky_light_factor"] = rnd_f(rng, 0.0, 1.0)
        if chance(0.15):
            attrs["minecraft:gameplay/sky_light_level"] = rnd_f(rng, 0.0, 15.0)
        if chance(0.15):
            attrs["minecraft:gameplay/respawn_anchor_works"] = rng.random() < 0.5
        # КРОВАТЬ: в КАЖДОМ измерении разрешена и устанавливает точку
        # спавна. Раньше bed_rule рандомизировался (12% миров, и половина
        # из них получала взрывающуюся кровать, как в незере): смерть в
        # «неудачном» измерении лишала игрока базы. Теперь:
        # can_set_spawn = always — кровать ставит спавн ВСЕГДА (даже днём,
        # как в overworld), can_sleep = when_dark — ванильное поведение
        # сна, взрыв (explodes) убран полностью. respawn_anchor_works не
        # трогаем — якорь по-прежнему случаен (по заданию: только кровать)
        attrs["minecraft:gameplay/bed_rule"] = {
            "can_set_spawn": "always", "can_sleep": "when_dark"}
        if chance(0.1):
            attrs["minecraft:gameplay/water_evaporates"] = rng.random() < 0.5
        if chance(0.1):
            attrs["minecraft:gameplay/fast_lava"] = rng.random() < 0.5
        if chance(0.1):
            attrs["minecraft:gameplay/snow_golem_melts"] = rng.random() < 0.5
        if chance(0.1):
            attrs["minecraft:gameplay/piglins_zombify"] = rng.random() < 0.5
        if chance(0.1):
            attrs["minecraft:gameplay/can_start_raid"] = rng.random() < 0.5
        if chance(0.08):
            attrs["minecraft:visual/default_dripstone_particle"] = {
                "type": rng.choice([
                    "minecraft:dripping_dripstone_lava",
                    "minecraft:dripping_dripstone_water",
                    "minecraft:falling_dripstone_lava",
                    "minecraft:falling_dripstone_water",
                ])}
        if chance(0.1):
            attrs["minecraft:audio/ambient_sounds"] = {"mood": {
                "sound": "minecraft:ambient.cave",
                "tick_delay": rng.randint(1000, 12000),
                "block_search_extent": rng.randint(4, 16),
                "offset": rng.choice([1.0, 2.0, 4.0, 8.0]),
            }}
        # редкие остатки из EnvironmentAttributes (26.2)
        if chance(0.25):
            attrs["minecraft:visual/block_light_tint"] = rand_color(rng)
        if chance(0.2):
            attrs["minecraft:visual/night_vision_color"] = rand_color(rng)
        if chance(0.3):
            attrs["minecraft:visual/sky_fog_end_distance"] = rnd_f(rng, 64.0, 2048.0)
        if chance(0.3):
            attrs["minecraft:visual/cloud_fog_end_distance"] = rnd_f(rng, 64.0, 2048.0)
        if chance(0.3):
            attrs["minecraft:visual/water_fog_start_distance"] = rnd_f(rng, 0.0, 64.0)
        if chance(0.3):
            attrs["minecraft:gameplay/nether_portal_spawns_piglin"] = rng.random() < 0.5
        return attrs

    # ---------------- noise settings ----------------

    def rand_noise_settings(self):
        rng = self.rng
        size_h = rng.choice([1, 1, 2, 2, 4])
        size_v = rng.choice([1, 2, 2, 4])
        # default_block — тело ВСЕГО мира: только безопасный пул (block
        # entity в каждом блоке недр = катастрофа FPS). Выбран ЗАРАНЕЕ
        # в generate() (нужен каменному семейству); в void-мирах пул
        # уже без сыпучих (_terrain_palette)
        default_block = self.default_block
        # почти всегда вода/лава/воздух/снег, но изредка «жидкость» —
        # вообще любой solid-блок (сюрреалистичные миры из камня-в-море);
        # тоже из безопасного пула РЕЛЬЕФА и БЕЗ сыпучих (жалоба на
        # лавины entity): «море» заливает целые слои мира, а в void-мирах
        # «море» из сыпучего = лавина entity
        _fl_pool = [b for b in self._terrain_palette()
                    if b[0] not in FALLING_BLOCK_IDS] \
            or self._terrain_palette()
        fluid = rng.choice(_fl_pool) if rng.random() < 0.015 \
            else rng.choice(FLUIDS)
        aquifers = rng.random() < 0.4
        ore_veins = rng.random() < 0.3

        # МОРЕ: шанс мира без моря 45% (решение юзера: побольше миров
        # без моря — было 25%); воздух-«жидкость» — всегда без моря
        if fluid[0] == "minecraft:air" or rng.random() < 0.45:
            sea_level = self.min_y - 16  # ниже дна — «моря нет»
        else:
            # КАП 45% высоты (было 75%!): при лраве море выше средней
            # поверхности ЗАТАПЛИВАЕТ почти весь мир — мир из лавы
            # (баг «fumugath»: сплошной массив + лравовый океан до 3/4
            # высоты). Поверхность дикой зоны — в середине, море должно
            # быть НИЖЕ неё; ваниль: море на ~33% высоты мира
            sea_level = rng.randint(
                self.min_y + 16,
                self.min_y + max(24, self.height * 9 // 20))

        def aquifer_noise():
            return {"type": "minecraft:noise", "noise": self.new_noise(),
                    "xz_scale": rnd_f(rng, 0.5, 1.5), "y_scale": rnd_f(rng, 0.4, 1.0)}

        def vein_noise():
            return {"type": "minecraft:noise", "noise": self.new_noise(),
                    "xz_scale": rnd_f(rng, 0.3, 1.5), "y_scale": rnd_f(rng, 0.3, 1.0)}

        # climate-каналы (temperature/vegetation/erosion/ridges/depth, а
        # при climate-корреляции и continents) уже подготовлены в
        # _prepare_climate: это плоские шумы с ЗАРАНЕЕ известной σ, по
        # квантилям которой биом-сорс тайлит пространство параметров
        # (прежде rand_climate_df давал константы/3D-шумы — bias решал
        # всё, по аудиту медиана топ-2 биомов была 71% площади)
        cc = self.climate_ch
        router = {
            "barrier": aquifers and aquifer_noise() or 0.0,
            "continents": self.terr_channel
            if getattr(self, "terrain_corr", False)
            else self.continents_noise_2d(),
            "depth": cc["depth"],
            "erosion": cc["erosion"],
            "final_density": self.rand_final_density(),
            "fluid_level_floodedness": aquifers and aquifer_noise() or 0.0,
            "fluid_level_spread": aquifers and aquifer_noise() or 0.0,
            "lava": aquifers and aquifer_noise() or 0.0,
            "preliminary_surface_level": self._rand_prelim(size_v),
            "ridges": cc["ridges"],
            "temperature": cc["temperature"],
            "vegetation": cc["vegetation"],
            "vein_gap": ore_veins and vein_noise() or 0.0,
            "vein_ridged": ore_veins and vein_noise() or 0.0,
            "vein_toggle": ore_veins and vein_noise() or 0.0,
        }

        # часть каналов router выносим в отдельные файлы density_function —
        # так одну функцию можно переиспользовать в нескольких каналах
        if rng.random() < 0.3 and isinstance(router["final_density"], dict):
            router["final_density"] = self.new_df_file(router["final_density"])
        chan_keys = ["continents", "erosion", "ridges", "depth",
                     "temperature", "vegetation"]
        for key in chan_keys:
            if rng.random() < 0.3 and isinstance(router[key], dict):
                router[key] = self.new_df_file(router[key])
        if rng.random() < 0.25:  # один и тот же файл в двух каналах
            # только erosion/ridges: их параметры у всех биомов одинаковы
            # (нейтрализованы в _biome_source_multi_noise), содержимое
            # канала на размещение биомов не влияет. temperature/
            # vegetation — оси квантильной решётки биом-сорса, depth —
            # вертикальный пояс «пещерных» биомов, continents — опора
            # кластеров и spline: их не подменяем
            pool = [k for k in ("erosion", "ridges")
                    if isinstance(router[k], str)]
            if len(pool) == 2:
                router["ridges"] = router["erosion"]

        spawn_target = []
        if rng.random() < 0.2:
            for _ in range(rng.randint(1, 2)):
                spawn_target.append({
                    "temperature": self._rand_range(-1.0, 2.0),
                    "humidity": self._rand_range(-1.0, 1.0),
                    "continentalness": self._rand_range(-1.0, 1.0),
                    "erosion": self._rand_range(-1.0, 1.0),
                    "weirdness": self._rand_range(-1.0, 1.0),
                    "depth": rnd_f(rng, -1.0, 1.5),
                    "offset": rnd_f(rng, 0.0, 0.2),
                })

        return {
            "aquifers_enabled": aquifers,
            "default_block": block_state(default_block),
            "default_fluid": block_state(fluid),
            "disable_mob_generation": rng.random() < 0.2,
            "legacy_random_source": rng.random() < 0.5,
            "noise": {"height": self.height, "min_y": self.min_y,
                      "size_horizontal": size_h, "size_vertical": size_v},
            "noise_router": router,
            "ore_veins_enabled": ore_veins,
            "sea_level": sea_level,
            "spawn_target": spawn_target,
            "surface_rule": self.rand_surface_rule(default_block),
        }

    def _rand_range(self, lo, hi):
        a = rnd_f(self.rng, lo, hi)
        b = rnd_f(self.rng, lo, hi)
        if a > b:
            a, b = b, a
        if a == b:
            b = a + 0.01
        return [a, b]

    def _rand_prelim(self, size_v):
        rng = self.rng
        if rng.random() < 0.6:
            return 0.0
        fy, ty = self._pair_y()
        density = {"type": "minecraft:y_clamped_gradient", "from_y": fy,
                   "to_y": ty, "from_value": rnd_f(rng, -1.0, 0.0),
                   "to_value": rnd_f(rng, 0.0, 1.0)}
        # find_top_surface (26.2): lower_bound — ЧИСЛО (Y), upper_bound — density-функция
        lower = rng.randint(self.min_y, self.min_y + self.height // 2)
        r = rng.random()
        if r < 0.5:  # градиент, значения — Y-координаты
            fy3, ty3 = self._pair_y()
            upper = {"type": "minecraft:y_clamped_gradient", "from_y": fy3,
                     "to_y": ty3,
                     "from_value": float(rng.randint(self.min_y, self.max_y)),
                     "to_value": float(rng.randint(self.min_y, self.max_y))}
        elif r < 0.8:
            upper = float(rng.randint(self.min_y, self.max_y))
        else:
            upper = {"type": "minecraft:clamp",
                     "input": self.rand_df(depth=1, max_depth=3),
                     "min": float(self.min_y), "max": float(self.max_y)}
        return {"type": "minecraft:find_top_surface",
                "cell_height": size_v * 4,
                "density": density,
                "lower_bound": lower,
                "upper_bound": upper}

    # ---------------- функции зачарований ----------------

    def _rand_ench_functions(self, rng):
        """mcfunction для run_function-эффектов зачарований: id функции =
        id зачарования (на такой контракт рассчитан модуль gen_enchantments).

        Тексты генерирует сам gen_enchantments (result['functions'] —
        разнообразные команды с execute-геометрией и гейтами, см.
        _gen_ench_function): они приходят сюда ГОТОВЫМИ через self.ench.
        Гейт-предикаты команд (random_chance) доливаем в общий реестр
        predicates — файлы из него пишет write_dimension, а ссылки из
        mcfunction проверяет --check. Фолбэк на старое поведение (одна
        команда перекраски либо particle+playsound) — только если функций
        от генератора нет (старый gen_enchantments/пропуск)."""
        out = {}
        if not self.ench:
            return out
        for pid, pjson in self.ench.get("gate_predicates", {}).items():
            self.preds.setdefault(pid, pjson)
        funcs = self.ench.get("functions") or {}
        for eid, ejson in self.ench.get("enchantments", {}).items():
            if "run_function" not in json.dumps(ejson):
                continue
            fname = eid.split(":", 1)[1]  # <name>_enchN
            if fname in funcs:
                out[fname] = funcs[fname]
                continue
            # --- фолбэк: генератор не дал функции (старый модуль) ---
            mod_ids = sorted(self.mods)
            pred_ids = sorted(self.preds)
            lines = ["# %s — вызывается run_function-эффектом зачарования"
                     % eid]
            if mod_ids and pred_ids:
                lines.append(
                    "execute if predicate %s run item modify entity @s "
                    "weapon.mainhand %s"
                    % (rng.choice(pred_ids), rng.choice(mod_ids)))
            elif mod_ids:
                lines.append("item modify entity @s weapon.mainhand %s"
                             % rng.choice(mod_ids))
            else:
                lines.append("particle minecraft:enchanted_hit ~ ~1 ~ "
                             "0.4 0.6 0.4 0 6")
                lines.append("playsound minecraft:block.enchantment_table.use "
                             "master @s ~ ~ ~ 0.7 1.4")
            out[fname] = "\n".join(lines) + "\n"
        return out

    # ---------------- главная сборка ----------------

    def generate(self, biome_count=None, prev_dim=None):
        """Сгенерировать измерение. prev_dim — имя ПРЕДЫДУЩЕГО измерения
        ЦЕПОЧКИ достижений (parent видимой ачивки = его ачивка, условия
        шагов фильтруются по доступности его мира); None — первое (из
        ванильного оверворлда)."""
        rng = self.rng
        # геометрия мира: min_y и height кратны 16, сумма не выше 2032
        self.min_y = rng.randrange(-2032, 1, 16)
        max_height = 2032 - self.min_y
        # убывающая вероятность: чем выше мир, тем реже он выпадает
        self.height = min(rng.choices(
            [128, 192, 256, 320, 384, 512, 640, 768, 1024, 1536, 2032],
            weights=[46, 26, 17, 12, 9, 7, 5, 4, 3, 2, 1])[0], max_height)
        self.height = max(128, (self.height // 16) * 16)
        if self.min_y + self.height > 2032:
            self.height = 2032 - self.min_y
        self.max_y = self.min_y + self.height

        # ФОРМА МИРА: не всегда «дно есть, потолка нет».
        #   open   (~60%) — твёрдое дно, воздух до неба (как overworld)
        #   cavern (~13%) — дно И кровля: пещерный мир наизнанку (как nether)
        #   void   (~27%) — БЕЗ дна: парящие острова, внизу пустота
        self.world_shape = rng.choices(
            ["open", "cavern", "void"], weights=[60, 13, 27])[0]
        # бюджет сыпучих в рельефе: только мирам с бедроковым дном
        # (open/cavern) разрешено до 2 РАЗНЫХ сыпучих блоков — и то
        # лишь при разнообразном окружении (семейство >= 3 блоков,
        # см. _select_stone_family); void — полный запрет
        self._falling_budget = 0 if self.world_shape == "void" else 2
        # кровля для cavern: толщина и нижняя граница (для телепорта)
        self.roof_h = min(rng.choice([16, 32, 48, 64, 96, 128]),
                          self.height // 3)
        # ПОЛОСА ГАРАНТИЙ ПЛОТНОСТИ (final_density): 10-15% высоты
        # (8-56 блоков). У краёв мира плотность задается ГРАДИЕНТАМИ, а
        # не шумами — регрессия «мир насплочь из камня» происходила из-за
        # насыщения шумов; градиенты шумам не подчиняются. Кровля cavern
        # не тоньше полосы — иначе структуры попадают в сплошной массив
        # у потолка (жалоба: «/locate находит, а структуры нет»)
        self.density_band = int(min(56, max(
            8, self.height * rng.randint(10, 15) // 100)))
        if self.world_shape == "cavern":
            self.roof_h = max(self.roof_h, self.density_band)
            # ВОЗДУШНЫЙ ПОЯС cavern — гарантированная пустота в середине
            # (как большие каверны незера): центр 44-56% высоты, полуширина
            # 9-17%; не залезает на полосы гарантий у дна и кровли
            t_band = max(8, self.density_band // 2)
            bc = self.min_y + int(self.height * rnd_f(rng, 0.44, 0.56))
            half = max(6, int(self.height * rnd_f(rng, 0.09, 0.17)))
            blo = max(self.min_y + self.density_band + t_band, bc - half)
            bhi = min(self.max_y - self.density_band - t_band, bc + half)
            self.belt_lo, self.belt_hi = blo, max(blo + 6, bhi)
        else:
            self.belt_lo = self.belt_hi = (self.min_y + self.max_y) // 2
        # безопасная высота телепорта в измерение (для reward-функций ачивок);
        # платформу НЕ ставим (решение юзера): игрок падает/телепортируется
        # на высоту, поверхность под ней — дело мира
        if self.world_shape == "open":
            self.tp_y = self.max_y - 8          # падение с неба, дно гарантировано
        elif self.world_shape == "cavern":
            # центр воздушного пояса — гарантированный воздух измерения
            # (раньше считался от кровли и мог попасть в сплошной массив)
            self.tp_y = (self.belt_lo + self.belt_hi) // 2
        else:  # void
            self.tp_y = self.min_y + self.height * rng.randint(35, 60) // 100
            self.tp_y = max(self.min_y + 16, min(self.tp_y, self.max_y - 16))

        # КОЛИЧЕСТВО БИОМОВ: 20-30 на измерение (юзер: «на каждое
        # измерение в среднем 20-30 биомов»); --biomes — явный оверрайд
        # (1-30; потолок 30: при 40+ биомах доля ≥2% арифметически
        # невозможна (1/40) — /locate biome не нашёл бы половину
        # биомов). Квантильные решётки биом-сорса держат большие наборы:
        # до 12 ячеек на кластер (a=ceil(sqrt(k)), k<=12 при 30 биомах
        # и 3 кластерах), ячейки равновелики по квантилям σ-каналов
        if biome_count is None:
            biome_count = rng.randint(20, 30)
        biome_count = min(30, biome_count)

        # биом-сорс решаем ЗАРАНЕЕ (а не в момент сборки dimension.json):
        # от него зависит пер-биомный рельеф — climate-корреляция возможна
        # только в multi_noise из СВОИХ биомов. multi_noise 95% — только он
        # даёт пер-биомную генерацию; остальные 5% (checkerboard/fixed/
        # preset/end) оставлены для редкого разнообразия
        self.bs_kind = rng.choices(
            ["multi_noise", "checkerboard", "fixed", "preset", "end"],
            weights=[95, 2, 1, 1, 1])[0]
        # пер-биомный рельеф: биомы бьём на 3-6 «кластеров рельефа», кластер
        # получает СВОЙ диапазон continentalness (не пересекается с другими),
        # а в final_density добавляется spline по каналу continents — у
        # кластера свой базовый уровень поверхности (равнины у «побережий»,
        # горы у «континентов»). Сдвиг плотности до ~±0.5 — заметный рельеф
        # без тотальных гор/пустот. Включён всегда при multi_noise (95% миров)
        self.terrain_corr = self.bs_kind == "multi_noise"
        # climate-каналы router'а готовим ЗАРАНЕЕ: σ continents нужна
        # квантильным центрам кластеров ниже, σ temperature/vegetation —
        # решётке биом-сорса (_biome_source_multi_noise), а сами DF потом
        # уйдут в router (rand_noise_settings)
        self._prepare_climate()
        n_clusters = rng.randint(3, 6)
        # центры кластеров — КВАНТИЛИ N(0, σ_cont): медианы n равных
        # долей распределения канала continents — кластеры получают
        # РАВНЫЕ площади (равномерные центры отдавали крайним кластерам
        # и свою долю, и хвосты шума)
        if self.terrain_corr:
            centers = [q * self.terr_sigma for q in _CLUSTER_Q[n_clusters]]
        else:  # без climate-корреляции геометрия кластеров не важна
            centers = [-0.85 + 1.7 * i / max(1, n_clusters - 1)
                       for i in range(n_clusters)]
        # размах сплайна кластеров S: сдвиги базового уровня рельефа
        # ограничены ±S — бюджет плотности final_density (P + S + вынос
        # базы <= B) гарантирует воздух/камень у границ дикой зоны при
        # ЛЮБОМ шуме (см. rand_final_density)
        self.terr_S = rnd_f(rng, 0.15, 0.35)
        self.terr_clusters = [(c + rnd_f(rng, -0.04, 0.04),
                               rnd_f(rng, -self.terr_S, self.terr_S))
                              for c in centers]
        self.biome_cluster = {}

        # фичи декорации: НЕБОЛЬШОЙ общий пул измерения + СВОИ у каждого
        # биома (генерируются в цикле биомов ниже, со своим префиксом) —
        # пер-биомная идентичность декораций
        if rng.random() < 0.95:
            # max_y — ЭКСКЛЮЗИВНЫЙ верх; rand_features/rand_carvers ждут
            # включительный последний блок (иначе absolute(top) у фич и
            # above_bottom(height) карверов дают высоты ВНЕ мира)
            self.feat_cfg, self.feat_placed, ftags = gen_features.rand_features(
                rng, self.ns, self.name, self.min_y, self.max_y - 1,
                count=heavy_count(rng, 4, 10, 60, 0.05),
                no_gravity=self.world_shape == "void")
            self.feature_tags = ftags
        # общий пул — только фичи, созданные ЗДЕСЬ (до биомов): для
        # «связности» биом может взять из него пару штук
        self._shared_feats = sorted(self.feat_placed)
        # РУДНАЯ СИСТЕМА — отдельный проход (НЕ через общий пул, чтобы
        # варианты богатства не утекали в случайные общие выборки):
        # 5-9 видов руд на измерение, у каждого 4 placed-варианта
        # богатства ×0.3/×1/×2.5/×5 с id <name>_oreM_pK. Биомы получают
        # СВОИ варианты (в одном руда богатая, в другом бедная —
        # раздача в rand_biome), высоты — относительные якоря по долям
        # высоты мира, смещённые в рельеф (см. gen_features.rand_ores)
        ocfg, oplaced, otags, self.ore_variants = gen_features.rand_ores(
            rng, self.ns, self.name, self.min_y, self.max_y - 1,
            count=rng.randint(5, 9),
            no_gravity=self.world_shape == "void")
        self.feat_cfg.update(ocfg)
        self.feat_placed.update(oplaced)
        self.feature_tags.update(otags)

        # default_block — выбираем ЗАРАНЕЕ (раньше он выбирался внутри
        # rand_noise_settings в самом конце generate): каменному
        # семейству нужно исключить его из своего пула, а блобам —
        # попасть в общий пул фич ДО генерации биомов. Пул рельефа —
        # БЕЗ сыпучих в void-мирах (_terrain_palette) и БЕЗ сыпучих
        # ВООБЩЕ (жалоба юзера на лавины entity): default_block — основа
        # всего массива мира, сыпучая основа обваливается в каждую
        # полость/carver-пещеру тысячами FALLING_BLOCK. ВСТАВКА ПОСЛЕ
        # _prepare_climate: climate-каналы уже готовы, их rng-поток
        # не сдвигается (находимость биомов не меняется)
        _db_pool = [b for b in self._terrain_palette()
                    if b[0] not in FALLING_BLOCK_IDS] \
            or self._terrain_palette()
        self.default_block = rng.choice(_db_pool)
        # КАМЕННОЕ СЕМЕЙСТВО: 3-7 доп. блоков с тирами «частый/обычный/
        # редкий» и РАЗНЫМИ методами генерации — большие блобы (как
        # ванильные андезит/диорит/гранит), 1-2 глубинные полосы (как
        # deepslate), 1-3 поверхностные заплатки (как кальцит у пиков)
        # и редкая «жила-стержень»; см. _select_stone_family
        self._select_stone_family()
        # БЛОБЫ семейства — в ОБЩИЙ пул измерения: каждый биом получает
        # их все (как ванильные ore_granite/ore_tuff — камень везде, а
        # не пер-биомная декорация). Пер-биомные множители руд НЕ
        # трогаем — это отдельная система (ore_variants выше)
        bcfg, bplaced, btags = gen_features.rand_stone_blobs(
            rng, self.ns, self.name, self.min_y, self.max_y - 1,
            family=self.stone_family, vein=self._family_vein)
        self.feat_cfg.update(bcfg)
        self.feat_placed.update(bplaced)
        self.feature_tags.update(btags)
        self._global_feats = sorted(bplaced)
        # карверы: общий пул размером под все биомы — ниже раскладываем
        # непересекающимися порциями по биомам (у биома СВОИ карверы)
        n_carv = heavy_count(rng, biome_count, max(16, biome_count + 4),
                             150, 0.05) if rng.random() < 0.9 else 0
        if n_carv:
            self.carvers_cfg = gen_structures.rand_carvers(
                rng, self.ns, self.name, self.min_y, self.max_y - 1,
                count=n_carv)
        # ПОДЗЕМНЫЕ БИОМЫ-АРХЕТИПЫ: в multi_noise-мирах от 128 высоты
        # и 6+ биомами (жалоба: «подземных биомов не оказалось» — раньше
        # только в мирах >= 256, т.е. меньше половины). 128-255 — 2-3
        # биома, >= 256 — 3-6, у КАЖДОГО свой АРХЕТИП из CAVE_ARCHETYPES
        # (пышная/натёчная/глубокая тьма/кристальная/грибная/корневая/
        # магмовая/замёрзшая — без повторов в мире; ванильная тройка —
        # вес выше, они эталон крутизны). Канал depth — рампа 1.5 (дно)
        # → -1.5 (потолок), ~0 — середина высоты, а поверхность open-
        # миров ~40-46% высоты = канал ~0.2-0.3, поэтому полосы режут
        # зону [0.2, 1.45]: от самой поверхности до дна, БЕЗ тонкой
        # прослойки поверхностных биомов между травой и подземкой (в
        # ваниле под землёй биомы тоже 3D). Полосы не пересекаются,
        # зазоры 0.05 между ними — там побеждают надземные биомы (как
        # в ванили между поясами пещерных биомов). Контент: пол/потолок/
        # акценты/фичи/фауна архетипа (rand_surface_rule +
        # gen_features.rand_cave_features + rand_biome)
        self.biome_underground = set()
        self.biome_band = {}
        self.biome_archetype = {}
        self.biome_idx = {}
        band_of_idx = {}
        arch_of_idx = {}
        if (biome_count >= 6 and self.height >= 128
                and self.bs_kind == "multi_noise"):
            n_under = rng.randint(3, 6) if self.height >= 256 \
                else rng.randint(2, 3)
            n_under = min(n_under, len(CAVE_ARCHETYPES),
                          max(2, biome_count - 2))
            under_idx = sorted(rng.sample(range(biome_count), n_under))
            # архетипы: взвешенная выборка БЕЗ повторов — ванильная
            # тройка lush/dripstone/deep_dark (вес 2.4) чаще остальных
            apool = sorted(CAVE_ARCHETYPES)
            arch_list = []
            for _ in range(n_under):
                weights = [CAVE_ARCHETYPES[a]["weight"] for a in apool]
                pick = rng.choices(apool, weights=weights)[0]
                arch_list.append(pick)
                apool = [a for a in apool if a != pick]
            for j, idx in enumerate(under_idx):
                arch_of_idx[idx] = arch_list[j]
            # режем подземную зону [CAVE_BAND_TOP, CAVE_BAND_BOTTOM]
            # (0.2..1.45) на n_under полос: зазоры 0.05, ширины с джиттером
            # (веса 0.7..1.3); первая полоса начинается ровно у
            # поверхности (CAVE_BAND_TOP), последняя кончается ровно у дна
            # (CAVE_BAND_BOTTOM) — полосы покрывают ВСЮ подземку
            gap = 0.05
            budget = (CAVE_BAND_BOTTOM - CAVE_BAND_TOP
                      - gap * (n_under - 1))
            wts = [rnd_f(rng, 0.7, 1.3) for _ in range(n_under)]
            wsum = sum(wts)
            edge = CAVE_BAND_TOP
            for j, idx in enumerate(under_idx):
                w = budget * wts[j] / wsum
                hi = (CAVE_BAND_BOTTOM if j == n_under - 1
                      else round(edge + w, 3))
                band_of_idx[idx] = (round(edge, 3), hi)
                edge += w + gap
        # карверы: подземным биомам — тройной вес в раздаче пула
        carver_deal = self._deal_carvers(biome_count, boost=set(band_of_idx))

        # мобы: каждый моб достаётся 1-2 биомам — у биома СВОЯ фауна,
        # а не общая выборка на всё измерение
        mob_deal = _deal_mobs(rng, biome_count)

        # собственные биомы измерения: каждый со СВОИМИ фичами, карверами,
        # фауной, профилем поверхности и кластером рельефа. own_sets — виды
        # СВОИХ фич уже принятых биомов: против них проверяется
        # сигнатурность следующего (1+ вид вне чужих, <= 1 общего с каждым)
        self.biomes = {}
        own_sets = []
        for i in range(biome_count):
            while True:
                bid = "%s:%s_%s" % (self.ns, self.name, random_name(rng))
                if bid not in self.biomes:
                    break
            self.biome_idx[bid] = i
            band = band_of_idx.get(i)   # depth-полоса подземного биома
            arch = None
            if band is not None:
                arch = CAVE_ARCHETYPES[arch_of_idx[i]]
            bfp = {}
            if band is not None:
                # подземный биом: СВОИ фичи — сигнатурный набор АРХЕТИПА
                # (4-6 рецептов по весам; блоки фиксированы рецептом —
                # идентичность «как в ваниле», см. gen_features.
                # _CAVE_RECIPE_SPEC; префикс <name>_b<i> как у всех)
                bfc, bfp, btags = gen_features.rand_cave_features(
                    rng, self.ns, "%s_b%d" % (self.name, i),
                    self.min_y, self.max_y - 1, arch["recipes"],
                    terrain=self.default_block[0],
                    floor_blocks=[arch["floor"]] + arch["sub"],
                    no_gravity=self.world_shape == "void")
                self.feat_cfg.update(bfc)
                self.feat_placed.update(bfp)
                self.feature_tags.update(btags)
                own_sets.append(self._feature_types(bfc))
            elif rng.random() < 0.9:  # ~10% биомов — только ванильные фичи
                # надземным — случайные виды и placement;
                # набор — СИГНАТУРНЫЙ (см. _rand_biome_features)
                bfc, bfp, btags = self._rand_biome_features(
                    i, band, own_sets)
                self.feat_cfg.update(bfc)
                self.feat_placed.update(bfp)
                self.feature_tags.update(btags)
                own_sets.append(self._feature_types(bfc))
            else:
                own_sets.append(frozenset())
            self.biome_cluster[bid] = i % n_clusters
            self.biomes[bid] = self.rand_biome(
                sorted(bfp), carver_deal[i], mob_deal[i], band=band,
                arch=arch)
            if band is not None:
                self.biome_underground.add(bid)
                self.biome_band[bid] = band
                self.biome_archetype[bid] = arch_of_idx[i]

        # predicates: в ~75% измерений, в среднем ~3, выбросы до ~20
        gp = _lazy("gen_predicates")
        self.preds = {}
        if gp is not None and rng.random() < 0.75:
            self.preds = gp.rand_predicates(
                rng, self.ns, self.name)["predicates"]

        # item_modifiers («персонажи» предметов): в ~70% измерений
        gim = _lazy("gen_item_modifiers")
        self.mods = {}
        if gim is not None and rng.random() < 0.7:
            self.mods = gim.rand_item_modifiers(
                rng, self.ns, self.name)["item_modifiers"]

        # зачарования + enchantment_provider: в ~85% измерений, в среднем
        # ~5, редкие выбросы до ~30. Генерируем ДО лута и мобов (их id идут
        # в set_enchantments таблиц лута и в снаряжение мобов-боссов), но
        # ПОСЛЕ predicates/item_modifiers: генератору mcfunction-функций
        # зачарований нужны их id (категория перекраски item modify)
        ge = _lazy("gen_enchantments")
        self.ench = {}
        if ge is not None and rng.random() < 0.85:
            self.ench = ge.rand_enchantments(
                rng, self.ns, self.name,
                mod_ids=sorted(self.mods), pred_ids=sorted(self.preds))
        self.ench_ids = sorted(self.ench.get("enchantments", {}))

        # .mcfunction для run_function-эффектов зачарований (id функции =
        # id зачарования) — тексты генерирует gen_enchantments; здесь
        # доливаем его гейт-предикаты в общий реестр predicates
        self.ench_functions = self._rand_ench_functions(rng)

        # связка зачарований с лутом и мобами: подмешиваем их id в модули
        # (в _enchantments_map/set_enchantments таблиц лута и в снаряжение
        # мобов-«боссов» .nbt-шаблонов)
        gl = _gl()
        if gl is not None and hasattr(gl, "set_custom_enchants"):
            gl.set_custom_enchants(self.ench_ids)
        if hasattr(gen_structures, "set_custom_enchants"):
            gen_structures.set_custom_enchants(self.ench_ids)

        # ЛУТ-ТАБЛИЦЫ: у каждой особой сущности/контейнера измерения — СВОЯ
        # уникальная таблица. Ссылки на таблицы (сундуки/бочки и волты из
        # .nbt-шаблонов, DeathLootTable мобов-«боссов», призы trial_spawner'ов)
        # выделяют слоты "<ns>:<name>_lootN" ОБЩИМ счётчиком LootSlots по мере
        # своей генерации, а сами таблицы создаёт ОДИН вызов rand_loot уже
        # ПОСЛЕ всех ссылок — count = занятые слоты (+минимум 1-2 на награды
        # достижений, там повторное использование допустимо). Порядок вызовов:
        # trial_spawner'ы → структуры → jigsaw (конфиги спавнеров нужны
        # .nbt-шаблонам структур). Без gen_loot счётчик не заводим —
        # генераторы уходят в ванильные fallback-таблицы.
        loot_alloc = gen_structures.LootSlots(self.ns, self.name) \
            if gl is not None else None

        # конфиги trial_spawner (пары normal + ominous) — ДО структур:
        # .nbt-шаблоны ссылаются на их id. В ~90% измерений, в среднем ~3
        # пары, редкие выбросы до ~20
        gts = _gts()
        self.trial_spawners = {}
        if gts is not None and rng.random() < 0.9:
            self.trial_spawners = gts.rand_trial_spawners(
                rng, self.ns, self.name,
                loot_alloc=loot_alloc)["trial_spawners"]
        self.trial_spawner_ids = sorted(self.trial_spawners)

        # структуры, привязанные к биомам измерения: в среднем ~0.7 на
        # биом (каждая принадлежит 1-3 биомам — см. gen_structures),
        # каждый седьмой мир — большой выброс (тяжёлый хвост урезан с
        # 200 до 40 — раньше «структурный спам»); сундуки/волты/мобы
        # .nbt-шаблонов занимают слоты лута через общий счётчик
        n_str = heavy_count(rng, max(6, biome_count // 2 + 3), 15, 40,
                            0.15) if rng.random() < 0.95 else 0
        _rs_vars = gen_structures.rand_structures.__code__.co_varnames
        _rs_kw = {}
        if "loot_alloc" in _rs_vars and loot_alloc is not None:
            _rs_kw["loot_alloc"] = loot_alloc
        if "trial_spawner_ids" in _rs_vars and self.trial_spawner_ids:
            _rs_kw["trial_spawner_ids"] = self.trial_spawner_ids
        # cavern-мир: кровля [max_y-roof_h, max_y-1] — структуры не должны
        # ни проецироваться на крышу (heightmap), ни стартовать так, чтобы
        # куски пересекли потолок мира (block entity вне мира = DUMMY WARN)
        if "has_ceiling" in _rs_vars:
            _rs_kw["has_ceiling"] = self.world_shape == "cavern"
        if "roof_bottom" in _rs_vars and self.world_shape == "cavern":
            _rs_kw["roof_bottom"] = self.max_y - self.roof_h
        # структуры привязываются ТОЛЬКО к надземным биомам: подземные
        # (пещерные) из выборки исключены (как в ваниле — структуры в
        # пещерных биомах не спавнятся); если надземных нет (не бывает:
        # подземных <= biome_count-2) — всякий список
        surface_biomes = [b for b in self.biomes
                          if b not in self.biome_underground]
        self.structs = gen_structures.rand_structures(
            rng, self.ns, self.name, self.min_y, self.max_y - 1,
            sorted(surface_biomes) or sorted(self.biomes),
            count=n_str, **_rs_kw)

        # свои МНОГОЧАСТНЫЕ jigsaw-структуры (модуль gen_jigsaw): тот же
        # формат словаря, что rand_structures — просто докладываем сверху.
        # По умолчанию 0–3 структуры на мир, каждый десятый мир — до 8
        gj = _lazy("gen_jigsaw")
        if gj is not None:
            _gj_vars = gj.rand_jigsaw.__code__.co_varnames
            _gj_kw = {}
            if "has_ceiling" in _gj_vars:
                _gj_kw["has_ceiling"] = self.world_shape == "cavern"
            if "roof_bottom" in _gj_vars and self.world_shape == "cavern":
                _gj_kw["roof_bottom"] = self.max_y - self.roof_h
            jj = gj.rand_jigsaw(
                rng, self.ns, self.name, self.min_y, self.max_y - 1,
                sorted(surface_biomes) or sorted(self.biomes),
                loot_alloc=loot_alloc, **_gj_kw)
            for k in ("structures", "structure_sets", "template_pools",
                      "processor_lists", "biome_tags"):
                self.structs.setdefault(k, {}).update(jj.get(k) or {})
            self.structs.setdefault("nbt_files", {}).update(
                jj.get("nbt_files") or {})

        # сами таблицы: ровно по одной на каждый занятый слот; минимум
        # 1-2 — чтобы награды достижений всегда имели что выдавать
        # (rewards.loot у ачивок использует rng.sample по loot_ids —
        # повторное использование для наград допустимо)
        if gl is not None:
            self.loot = gl.rand_loot(
                rng, self.ns, self.name,
                count=max(loot_alloc.count, rng.randint(1, 2)))
        else:
            self.loot = {}
        self.loot_ids = sorted(self.loot.get("loot_tables", {}))

        # собственное время (world_clock + timeline, реестры 26.2) и
        # собственный тег infiniburn — с некоторой вероятностью.
        # infiniburn: в среднем ~1 блок, почти всегда 0–2, редкие выбросы
        # вплоть до сотни блоков.
        self.custom_time = gen_time.rand_time(rng, self.ns, self.name) \
            if rng.random() < 0.65 else None
        self.infiniburn_tag = None
        if rng.random() < 0.45:
            if rng.random() < 0.04:  # редкий большой выброс
                ib_n = int(round(math.exp(
                    rng.uniform(math.log(5), math.log(100)))))
            else:                    # почти всегда 1–2
                ib_n = 1 + int(rng.expovariate(1.25))
            self.infiniburn_tag = gen_time.rand_infiniburn_tag(
                rng, self.ns, self.name, count=ib_n)

        dim_id = "%s:%s" % (self.ns, self.name)
        settings_id = dim_id
        type_id = dim_id

        dimension = {
            "type": type_id,
            "generator": {
                "type": "minecraft:noise",
                "biome_source": self.rand_biome_source(),
                "settings": settings_id,
            },
        }
        dimension_type = self.rand_dimension_type()
        noise_settings = self.rand_noise_settings()

        # достижения-телепорты: видимая ачивка + скрытая (критерии DUMMY —
        # грантуются ТОЛЬКО шагами) + видимые ШАГИ пути (реальные триггеры,
        # по одному на группу — ПРОГРЕСС: выполненные светятся под ачивкой
        # измерения) + reward-функции с телепортом на безопасную высоту
        # self.tp_y (уже учтена форма мира: open — у неба, cavern — ниже
        # кровли, void — у островов; без платформы). Дерево вкладки =
        # ЦЕПОЧКА достижимости: parent видимой — ачивка prev_dim
        # (первое — root), условия каждого следующего мира на 100% достижимы
        # из предыдущего (пулы фильтруются по его террейну/мобам/луту;
        # сундучные таблицы — только prev-мира). rewards скрытой ачивки:
        # наша функция-телепорт + часто опыт / лут данжей / рецепты.
        self.adv = gen_advancements.rand_advancements(
            rng, self.ns, self.name,
            default_block=noise_settings["default_block"]["Name"],
            tp_y=self.tp_y,
            data_root=DATA_ROOT, loot_ids=self.loot_ids,
            prev_dim=prev_dim)

        return {
            "dimension": dimension,
            "dimension_type": dimension_type,
            "noise_settings": noise_settings,
            "noises": dict(self.noises),
            "biomes": dict(self.biomes),
            "density_functions": dict(self.dfs),
            "features_configured": dict(self.feat_cfg),
            "features_placed": dict(self.feat_placed),
            "feature_tags": dict(self.feature_tags),
            "carvers": dict(self.carvers_cfg),
            "structures_data": self.structs,
            "loot_tables": dict(self.loot.get("loot_tables", {})),
            "trial_spawners": dict(self.trial_spawners),
            "enchantments": dict(self.ench.get("enchantments", {})),
            "enchantment_providers": dict(
                self.ench.get("enchantment_providers", {})),
            "ench_functions": dict(self.ench_functions),
            "predicates": dict(self.preds),
            "item_modifiers": dict(self.mods),
            "custom_time": self.custom_time,
            "infiniburn_tag": self.infiniburn_tag,
            "advancements": dict(self.adv["advancements"]),
            "adv_functions": dict(self.adv["functions"]),
            "summary": {
                "id": dim_id,
                "min_y": self.min_y,
                "height": self.height,
                "default_block": noise_settings["default_block"]["Name"],
                "default_fluid": noise_settings["default_fluid"]["Name"],
                "sea_level": noise_settings["sea_level"],
                "biome_source": dimension["generator"]["biome_source"]["type"],
                "biomes": len(self.biomes),
                "underground_biomes": len(self.biome_underground),
                "ores": len(self.ore_variants),
                "stone_family": len(self.stone_family),
                "stone_blobs": len(self._global_feats),
                "stone_bands": self._n_deep_bands,
                "stone_patches": len(self._family_patches),
                "stone_vein": self._family_vein is not None,
                "terrain_corr": getattr(self, "terrain_corr", False),
                "terrain_preset": getattr(self, "terrain_preset", ""),
                "noises": len(self.noises),
                "dfs": len(self.dfs),
                "custom_time": self.custom_time is not None,
                "timelines": len(self.custom_time["timeline"]) if self.custom_time else 0,
                "features": len(self.feat_placed),
                "carvers": len(self.carvers_cfg),
                "structures": len(self.structs.get("structures", {})),
                "nbt_templates": len(self.structs.get("nbt_files", {})),
                "loot_tables": len(self.loot.get("loot_tables", {})),
                "trial_spawners": len(self.trial_spawners),
                "enchantments": len(self.ench.get("enchantments", {})),
                "predicates": len(self.preds),
                "item_modifiers": len(self.mods),
                "ench_functions": len(self.ench_functions),
                "has_ceiling": dimension_type["has_ceiling"],
                "has_skylight": dimension_type["has_skylight"],
                "spawn_y": self.tp_y,
                "adv_trigger": self.adv.get("trigger"),
                "adv_hint": self.adv.get("hint"),
                "adv_parent": self.adv.get("parent"),
                "adv_steps": self.adv.get("n_steps"),
                "adv_step_titles": self.adv.get("step_titles"),
                "adv_expansions": self.adv.get("expansions"),
            },
        }


# ---------------------------------------------------------------------------
# Запись файлов / CLI
# ---------------------------------------------------------------------------

def dump_json(obj):
    return json.dumps(obj, indent=2, sort_keys=True,
                      separators=(",", ": ")) + "\n"


def random_name(rng):
    name = (rng.choice(SYLL_A) + rng.choice(SYLL_B) + rng.choice(SYLL_C))
    name = re.sub(r"[^a-z0-9_]", "", name.lower())
    if rng.random() < 0.3:
        name += str(rng.randint(2, 99))
    return name


def cleanup_dimension(pack_ns, name):
    """Удаляет ВСЕ файлы измерения перед перегенерацией с тем же именем.

    Файлы измерения называются <name>.json, <name>_*.json или лежат в
    каталоге <name>/, поэтому ищем их по всему namespace. Если найдется
    другое измерение, чьё имя начинается с <name>_ (например foo и
    foo_bar), очистку пропускаем — иначе задели бы его файлы.

    Спавн-теги (data/minecraft/tags/block) здесь НЕ трогаем: они общие
    на весь пак, а полная пересборка по оставшимся измерениям не нужна —
    write_spawnable_tags при следующей генерации сама собирает блоки
    заново по ВСЕМ noise_settings на диске. Оставшиеся от удалённого
    измерения блоки в тегах безвредны: тег лишь РАЗРЕШАЕТ спавн на
    блоке, которого в мире больше нет.
    """
    base = DATA_ROOT / pack_ns
    if not base.exists():
        return 0
    for p in glob.glob(str(base / "dimension" / "*.json")):
        stem = re.sub(r"\.json$", "", os.path.basename(p))
        if stem != name and stem.startswith(name + "_"):
            print("!! очистка %s пропущена: найдено измерение %s"
                  " с пересекающимся именем" % (name, stem))
            return 0
    seg_rx = re.compile(r"^%s(?=[_.]|$)" % re.escape(name))
    removed = 0
    for root, _dirs, fnames in os.walk(base):
        for fn in fnames:
            # .json (все реестры), .nbt (шаблоны структур) и .mcfunction
            # (reward-функции достижений)
            if not (fn.endswith(".json") or fn.endswith(".nbt")
                    or fn.endswith(".mcfunction")):
                continue
            rel = os.path.relpath(os.path.join(root, fn), base)
            if any(seg_rx.match(seg) for seg in rel.replace("\\", "/").split("/")):
                os.remove(os.path.join(root, fn))
                removed += 1
    # если измерений в namespace не осталось — убираем и корень вкладки
    # достижений (дерево adv/root живёт, пока есть хоть одно измерение)
    if not glob.glob(str(base / "dimension" / "*.json")):
        root_adv = base / "advancement" / "adv" / "root.json"
        if root_adv.exists():
            root_adv.unlink()
            removed += 1
    # прибираем опустевшие каталоги (например density_function/<name>/)
    for root, dirs, _files in os.walk(base, topdown=False):
        for d in dirs:
            p = os.path.join(root, d)
            if not os.listdir(p):
                os.rmdir(p)
    return removed


# ---------------------------------------------------------------------------
# Ванильные спавн-теги: дополнение поверхностными блоками измерений
# (без этого животные не спавнятся на случайных поверхностях)
# ---------------------------------------------------------------------------

def _collect_surface_block_names(node, out):
    """Рекурсивный обход дерева surface_rule: собирает ВСЕ result_state.Name
    (верхний слой каждого биома, подповерхностная полоса, заплатки,
    глубинная полоса, bedrock-дно/кровля — всё это потенциальный пол,
    на котором стоит разрешить спавн)."""
    if isinstance(node, dict):
        rs = node.get("result_state")
        if isinstance(rs, dict) and isinstance(rs.get("Name"), str):
            out.add(rs["Name"])
        for v in node.values():
            _collect_surface_block_names(v, out)
    elif isinstance(node, list):
        for v in node:
            _collect_surface_block_names(v, out)


def noise_settings_surface_blocks(settings):
    """Поверхностные блоки ОДНОГО noise_settings: default_block (тело
    всего террейна) + все блоки surface_rule. Возвращает set из id
    блоков (minecraft:...) — state-параметры тегам не нужны."""
    out = set()
    db = settings.get("default_block")
    if isinstance(db, dict) and isinstance(db.get("Name"), str):
        out.add(db["Name"])
    _collect_surface_block_names(settings.get("surface_rule"), out)
    return out


def write_spawnable_tags():
    """Дописывает поверхностные блоки измерений во все 13 ванильных
    блок-тегов спавна — файлы data/minecraft/tags/block/<tag>.json вида
    {"values": [...]} БЕЗ replace: значения ДОБАВЛЯЮТСЯ к ванильным
    (grass_block/stone/mycelium/... остаются), это стандартная механика
    тегов датапаков.

    ЗАЧЕМ: SpawnPlacements «наземных» мобов требует блок пола из
    ванильного тега (animals_spawnable_on = только grass_block, bats =
    stone, mooshrooms = mycelium, camels = sand, wolves = ...), а
    поверхности наших измерений — случайные блоки (шерсть/андезит/...),
    поэтому без дополнения тегов животные не спавнятся ВООБЩЕ.

    КАК: блоки собираем не только из свежесгенерированного измерения,
    а из ВСЕХ noise_settings пака на диске (data/*/worldgen/...) — теги
    общие на весь пак, поэтому каждая генерация заодно «лечит» и все
    ранее созданные измерения (включая времена до этого фикса).
    Существующее содержимое файлов сохраняется (merge): ручные
    дополнения не теряются; блоки удалённых измерений могут остаться в
    файлах — это безвредно, тег лишь РАЗРЕШАЕТ спавн на блоке, которого
    в мире больше нет.

    Возвращает (сколько файлов записано, set добавленных id)."""
    blocks = set()
    for p in glob.glob(str(DATA_ROOT / "*" / "worldgen" / "noise_settings"
                           / "*.json")):
        try:
            with open(p, encoding="utf-8") as f:
                settings = json.load(f)
        except Exception:
            continue  # битый JSON — не наш случай, --check его покажет
        blocks |= noise_settings_surface_blocks(settings)
    # страховочный фильтр: только полные кубы без block entity
    blocks &= _SPAWN_TAG_SAFE_IDS
    if not blocks:
        return 0, set()
    tag_dir = DATA_ROOT / "minecraft" / "tags" / "block"
    written, added = 0, set()
    for tag in SPAWNABLE_TAGS:
        path = tag_dir / (tag + ".json")
        values = []
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    old = json.load(f)
                if isinstance(old, dict) \
                        and isinstance(old.get("values"), list):
                    values = old["values"]
            except Exception:
                values = []  # битый файл — переписываем заново
        have = {v for v in values if isinstance(v, str)}
        new = blocks - have
        if not new and path.exists():
            continue  # добавлять нечего — файл не трогаем
        # строки сортируем; словари-опции ({"id":..., "required": false})
        # возможны только после ручной правки — сохраняем как есть
        merged = sorted(have | blocks) + \
            [v for v in values if not isinstance(v, str)]
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(dump_json({"values": merged}))
        written += 1
        added |= new
    return written, added


def _remove_spawnable_tags():
    """Удаляет наши 13 спавн-тегов и опустевшие каталоги
    (minecraft/tags/block → tags → minecraft; data/ не трогаем)."""
    tag_dir = DATA_ROOT / "minecraft" / "tags" / "block"
    removed = 0
    for tag in SPAWNABLE_TAGS:
        p = tag_dir / (tag + ".json")
        if p.exists():
            p.unlink()
            removed += 1
    d = tag_dir
    for _ in range(3):  # block → tags → minecraft
        try:
            if any(d.iterdir()):
                break
            d.rmdir()
        except OSError:  # каталога нет или он не пуст
            break
        d = d.parent
    return removed


def regen_spawnable_tags():
    """--regen: спавн-теги лежат в data/minecraft и ОБЩИЕ для всех
    namespace'ов. Если измерений не осталось ни в одном — удаляем все
    13 файлов (полная очистка); если остались в другом namespace —
    файлы оставляем (merge ничего не удаляет, лишние блоки безвредны;
    write_spawnable_tags при следующей генерации допишет недостающее).
    Возвращает текст статуса для печати."""
    left = glob.glob(str(DATA_ROOT / "*" / "worldgen" / "noise_settings"
                         / "*.json"))
    if left:
        write_spawnable_tags()
        return "оставлены (в паке ещё %d измерений)" % len(left)
    n = _remove_spawnable_tags()
    return ("удалено файлов: %d" % n) if n else "нечего удалять"


def write_dimension(pack_ns, result, force_name=None):
    name = force_name or result["summary"]["id"].split(":")[1]
    base = DATA_ROOT / pack_ns
    files = {
        base / "dimension" / ("%s.json" % name): result["dimension"],
        base / "dimension_type" / ("%s.json" % name): result["dimension_type"],
        base / "worldgen" / "noise_settings" / ("%s.json" % name): result["noise_settings"],
    }
    for nid, spectrum in result["noises"].items():
        fname = nid.split(":", 1)[1] + ".json"
        files[base / "worldgen" / "noise" / fname] = spectrum
    for bid, bjson in result["biomes"].items():
        fname = bid.split(":", 1)[1] + ".json"
        files[base / "worldgen" / "biome" / fname] = bjson
    for did, dfjson in result.get("density_functions", {}).items():
        fname = did.split(":", 1)[1] + ".json"  # имя вида <name>/dfN.json
        files[base / "worldgen" / "density_function" / fname] = dfjson
    # время 26.2: world_clock/ и timeline/ — БЕЗ префикса worldgen/ (по jar)
    ct = result.get("custom_time")
    if ct:
        for cid, cjson in ct["world_clock"].items():
            files[base / "world_clock" / (cid.split(":", 1)[1] + ".json")] = cjson
        for tid, tjson in ct["timeline"].items():
            files[base / "timeline" / (tid.split(":", 1)[1] + ".json")] = tjson
        for tname, tjson in ct["timeline_tags"].items():
            files[base / "tags" / "timeline" / (tname + ".json")] = tjson
    ib = result.get("infiniburn_tag")
    if ib:
        files[base / "tags" / "block" / (name + ".json")] = ib
    # фичи декорации, карверы и структуры
    for fid, fjson in result.get("features_configured", {}).items():
        files[base / "worldgen" / "configured_feature"
              / (fid.split(":", 1)[1] + ".json")] = fjson
    for fid, fjson in result.get("features_placed", {}).items():
        files[base / "worldgen" / "placed_feature"
              / (fid.split(":", 1)[1] + ".json")] = fjson
    # block-теги фич («земля» измерения — цели руд/дисков/валунов)
    for tid, tjson in result.get("feature_tags", {}).items():
        files[base / "tags" / "block"
              / (tid.split(":", 1)[1] + ".json")] = tjson
    for cid, cjson in result.get("carvers", {}).items():
        files[base / "worldgen" / "configured_carver"
              / (cid.split(":", 1)[1] + ".json")] = cjson
    st = result.get("structures_data") or {}
    st_folders = {"structures": "structure", "structure_sets": "structure_set",
                  "template_pools": "template_pool",
                  "processor_lists": "processor_list"}
    for sub, folder in st_folders.items():
        for sid, sjson in (st.get(sub) or {}).items():
            files[base / "worldgen" / folder
                  / (sid.split(":", 1)[1] + ".json")] = sjson
    for tag_path, tjson in (st.get("biome_tags") or {}).items():
        files[base / "tags" / "worldgen" / "biome" / (tag_path + ".json")] = tjson
    # таблицы лута (реестр loot_table, БЕЗ префикса worldgen/)
    for lid, ljson in result.get("loot_tables", {}).items():
        files[base / "loot_table"
              / (lid.split(":", 1)[1] + ".json")] = ljson
    # конфиги trial_spawner (реестр trial_spawner, тоже БЕЗ worldgen/);
    # id вида <ns>:<name>_tsN[_om] — суффикс _om = ominous-режим
    for tid, tjson in result.get("trial_spawners", {}).items():
        files[base / "trial_spawner"
              / (tid.split(":", 1)[1] + ".json")] = tjson
    # зачарования и enchantment_provider (реестры 26.2, без worldgen/)
    for eid, ejson in result.get("enchantments", {}).items():
        files[base / "enchantment"
              / (eid.split(":", 1)[1] + ".json")] = ejson
    for pid, pjson in result.get("enchantment_providers", {}).items():
        files[base / "enchantment_provider"
              / (pid.split(":", 1)[1] + ".json")] = pjson
    # predicates и item_modifiers (реестры без worldgen/)
    for pid, pjson in result.get("predicates", {}).items():
        files[base / "predicate"
              / (pid.split(":", 1)[1] + ".json")] = pjson
    for mid, mjson in result.get("item_modifiers", {}).items():
        files[base / "item_modifier"
              / (mid.split(":", 1)[1] + ".json")] = mjson
    # достижения-телепорты (реестр advancement, свои пути adv/...):
    # <ns>:adv/<name> — видимая, <ns>:adv/<name>_tp — скрытая,
    # <ns>:adv/root — корень вкладки (создаётся один раз)
    for aid, ajson in result.get("advancements", {}).items():
        files[base / "advancement"
              / (aid.split(":", 1)[1] + ".json")] = ajson
    for path, obj in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(dump_json(obj))
    # .nbt-шаблоны структур с сущностями (мобы с NBT) — БИНАРНЫЙ gzip-NBT:
    # сервер 26.2 читает их из data/<ns>/structure/<имя>.nbt
    # (NbtIo.readCompressed; текстовый .snbt — только gametest-каталог)
    for sname, nbt_bytes in (st.get("nbt_files") or {}).items():
        p = base / "structure" / (sname + ".nbt")
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "wb") as f:
            f.write(nbt_bytes)
        files[p] = nbt_bytes
    # reward-функции достижений — реестр function (единственное число),
    # текстовые .mcfunction, UTF-8 без BOM, юниксовые переводы строк
    for fname, ftext in result.get("adv_functions", {}).items():
        p = base / "function" / (fname + ".mcfunction")
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(ftext)
        files[p] = ftext
    # функции run_function-эффектов зачарований — тот же реестр function,
    # id файла = имени зачарования без namespace
    for fname, ftext in result.get("ench_functions", {}).items():
        p = base / "function" / (fname + ".mcfunction")
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(ftext)
        files[p] = ftext
    # ванильные спавн-теги: дописать поверхностные блоки (сбор — по ВСЕМ
    # noise_settings пака на диске, включая только что записанные: теги
    # общие, заодно лечим измерения, созданные до появления фикса)
    write_spawnable_tags()
    return files


def list_dimensions(pack_ns):
    dim_dir = DATA_ROOT / pack_ns / "dimension"
    if not dim_dir.exists():
        return []
    out = []
    for p in sorted(glob.glob(str(dim_dir / "*.json"))):
        try:
            with open(p, encoding="utf-8") as f:
                dim = json.load(f)
            sid = dim.get("generator", {}).get("settings", "?")
            info = {}
            stem = re.sub(r"\.json$", "", os.path.basename(p))
            info["biomes"] = len(glob.glob(
                str(DATA_ROOT / pack_ns / "worldgen" / "biome" / (stem + "_*.json"))))
            if isinstance(sid, str) and ":" in sid:
                p_ns, p_name = sid.split(":", 1)
                settings_path = (DATA_ROOT / p_ns / "worldgen" / "noise_settings"
                                 / (p_name + ".json"))
                if settings_path.exists():
                    with open(settings_path, encoding="utf-8") as f:
                        st = json.load(f)
                    info = {"block": st.get("default_block", {}).get("Name"),
                            "height": st.get("noise", {}).get("height"),
                            "min_y": st.get("noise", {}).get("min_y")}
            out.append((dim.get("type", "?"), info))
        except Exception as e:
            out.append((p, {"error": str(e)}))
    return out


def check_dimensions(pack_ns):
    """Проверка: весь JSON парсится, все ссылки на шумы и биомы существуют."""
    root = DATA_ROOT / pack_ns
    if not root.exists():
        print("Нет данных для namespace %s" % pack_ns)
        return
    defined = {"%s:%s" % (pack_ns, re.sub(r"\.json$", "", os.path.basename(p)))
               for p in glob.glob(str(root / "worldgen" / "noise" / "*.json"))}
    defined_biomes = {
        "%s:%s" % (pack_ns, re.sub(r"\.json$", "", os.path.basename(p)))
        for p in glob.glob(str(root / "worldgen" / "biome" / "*.json"))}
    defined_dfs = set()
    df_dir = root / "worldgen" / "density_function"
    for p in glob.glob(str(df_dir / "**" / "*.json"), recursive=True):
        rel = Path(p).resolve().relative_to(df_dir.resolve()).as_posix()[:-5]
        defined_dfs.add("%s:%s" % (pack_ns, rel))
    refs = set()

    def collect_biome_refs(obj, out):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "biome" and isinstance(v, str):
                    out.add(v)
                elif k == "biome_is":
                    if isinstance(v, str):
                        out.add(v)
                    elif isinstance(v, list):
                        out.update(x for x in v if isinstance(x, str))
                elif k == "biomes" and isinstance(v, list):
                    for x in v:
                        if isinstance(x, str):
                            out.add(x)
                        elif isinstance(x, dict) and isinstance(x.get("biome"), str):
                            out.add(x["biome"])
                else:
                    collect_biome_refs(v, out)
        elif isinstance(obj, list):
            for x in obj:
                collect_biome_refs(x, out)

    biome_refs = set()
    df_refs = set()
    _DF_CH = ("final_density|continents|erosion|ridges|depth|temperature|"
              "vegetation|preliminary_surface_level|barrier|lava|"
              "fluid_level_floodedness|fluid_level_spread|vein_toggle|"
              "vein_ridged|vein_gap")
    for p in glob.glob(str(root / "worldgen" / "noise_settings" / "*.json")):
        txt = open(p, encoding="utf-8").read()
        for m in re.finditer(r'"noise"\s*:\s*"([^"]+)"', txt):
            refs.add(m.group(1))
        for m in re.finditer(r'"(?:%s)":\s*"([^"]+)"' % _DF_CH, txt):
            df_refs.add(m.group(1))
    for sub in ("dimension", "worldgen/noise_settings"):
        for p in glob.glob(str(root / sub / "*.json")):
            try:
                collect_biome_refs(json.load(open(p, encoding="utf-8")), biome_refs)
            except Exception:
                pass
    missing = {r for r in refs if not r.startswith("minecraft:") and r not in defined}
    missing_b = {r for r in biome_refs
                 if not r.startswith("minecraft:") and r not in defined_biomes}
    missing_df = {r for r in df_refs if not r.startswith("minecraft:")
                  and r not in defined_dfs and r not in defined}
    print("шумов создано: %d, ссылок: %d, битых ссылок: %s"
          % (len(defined), len(refs), missing or "нет"))
    print("биомов создано: %d, ссылок: %d, битых ссылок: %s"
          % (len(defined_biomes), len(biome_refs), missing_b or "нет"))
    # INLINE-ССЫЛКИ фич: селекторы (random_boolean_selector и пр.) ссылаются
    # на configured-фичи полем {"feature": "<id>"} внутри JSON — цель
    # обязана существовать (реальный случай: ostyadorn_b18_fossil1 —
    # сервер «Unbound values in registry configured_feature")
    defined_cfg = {
        "%s:%s" % (pack_ns, re.sub(r"\.json$", "", os.path.basename(p)))
        for p in glob.glob(str(root / "worldgen" / "configured_feature" / "**" / "*.json"), recursive=True)}
    bad_inline = []

    def _collect_inline(o, path):
        if isinstance(o, dict):
            f = o.get("feature")
            if isinstance(f, str) and f.startswith(pack_ns + ":") \
                    and "placement" in o:
                if f not in defined_cfg:
                    bad_inline.append("%s: %s" % (path, f))
            for k, v in o.items():
                _collect_inline(v, path + "/" + k)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                _collect_inline(v, "%s[%d]" % (path, i))

    for p in glob.glob(str(root / "worldgen" / "configured_feature" / "**" / "*.json"), recursive=True) \
            + glob.glob(str(root / "worldgen" / "placed_feature" / "**" / "*.json"), recursive=True):
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        _collect_inline(d, Path(p).name)
    if bad_inline:
        print("INLINE-ССЫЛКИ ФИЧ: БИТЫЕ (%d):" % len(bad_inline))
        for m in bad_inline[:10]:
            print("  ! " + m)
    else:
        print("inline-ссылки фич: все ок")
    print("density_function файлов: %d, ссылок: %d, битых ссылок: %s"
          % (len(defined_dfs), len(df_refs), missing_df or "нет"))
    # время 26.2: default_clock/timelines/infiniburn из dimension_type
    clocks = {"%s:%s" % (pack_ns, re.sub(r"\.json$", "", os.path.basename(p)))
              for p in glob.glob(str(root / "world_clock" / "*.json"))}
    bad_time = []
    for p in glob.glob(str(root / "dimension_type" / "*.json")):
        try:
            dt = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        clock = dt.get("default_clock")
        if isinstance(clock, str) and ":" in clock \
                and not clock.startswith("minecraft:") \
                and clock not in clocks:
            bad_time.append("нет world_clock " + clock)
        for key, folder in (("timelines", "tags/timeline"),
                            ("infiniburn", "tags/block")):
            v = dt.get(key)
            if isinstance(v, str) and v.startswith("#%s:" % pack_ns):
                if not (root / folder / (v.split(":", 1)[1] + ".json")).exists():
                    bad_time.append("нет %s %s" % (key, v))
    print("время/теги: %s" % ("все ок" if not bad_time else "; ".join(bad_time)))
    # спавн-теги (data/minecraft/tags/block/*.json): 13 ванильных тегов,
    # куда генератор дописывает поверхностные блоки всех измерений (без
    # них животные не спавнятся — SpawnPlacements требует блок пола из
    # ванильного тега). Файлы общие на весь пак (вне namespace).
    # Отсутствие тегов — НЕ ошибка: измерения могли быть созданы до
    # фикса (теги появятся при следующей генерации — она пересобирает
    # их по всем noise_settings на диске); а вот битый файл — ошибка.
    dims_exist = bool(glob.glob(str(root / "dimension" / "*.json")))
    tag_dir = DATA_ROOT / "minecraft" / "tags" / "block"
    present = [t for t in SPAWNABLE_TAGS
               if (tag_dir / (t + ".json")).exists()]
    bad_tags, sizes = [], {}
    for t in present:
        try:
            with open(tag_dir / (t + ".json"), encoding="utf-8") as f:
                d = json.load(f)
            vals = d.get("values") if isinstance(d, dict) else None
            if not isinstance(vals, list):
                bad_tags.append("%s: values не список" % t)
            else:
                sizes[t] = len(vals)
        except Exception as e:
            bad_tags.append("%s: %s" % (t, e))
    if bad_tags:
        for m in bad_tags:
            print("БИТЫЙ СПАВН-ТЕГ:", m)
        print("спавн-теги: ошибок %d" % len(bad_tags))
    elif not present:
        if dims_exist:
            print("спавн-теги: отсутствуют — измерения созданы до фикса; "
                  "появятся при следующей генерации")
        # измерений нет и тегов нет — чисто, молчим
    elif len(present) < len(SPAWNABLE_TAGS):
        missing = [t for t in SPAWNABLE_TAGS if t not in present]
        print("спавн-теги: только %d из 13 (нет: %s)"
              % (len(present), ", ".join(missing)))
    else:
        print("спавн-теги: 13/13, все парсятся (блоков в теге: %d-%d)"
              % (min(sizes.values()), max(sizes.values())))

    # универсальная проверка: все ссылки "<ns>:..." во всех JSON ведут на
    # существующие файлы реестров/тегов (кроме random_name — это просто строка)
    registry_prefixes = [
        "worldgen/configured_feature", "worldgen/placed_feature",
        "worldgen/configured_carver", "worldgen/structure",
        "worldgen/structure_set", "worldgen/template_pool",
        "worldgen/processor_list", "worldgen/density_function",
        "worldgen/noise_settings", "worldgen/noise", "worldgen/biome",
        "loot_table", "dimension", "dimension_type", "world_clock", "timeline",
        "advancement", "trial_spawner", "enchantment",
        "enchantment_provider", "predicate", "item_modifier",
    ]
    tag_prefixes = ["tags/worldgen/biome", "tags/timeline", "tags/block"]
    defined_ids = set()
    for p in glob.glob(str(root / "**" / "*.json"), recursive=True):
        rel = Path(p).resolve().relative_to(root.resolve()).as_posix()[:-5]
        hit = False
        for pref in tag_prefixes:  # tags/worldgen/biome/x/y → ns:x/y
            if rel.startswith(pref + "/"):
                defined_ids.add("%s:%s" % (pack_ns, rel[len(pref) + 1:]))
                hit = True
                break
        if not hit:
            for pref in registry_prefixes:  # worldgen/biome/x → ns:x
                if rel.startswith(pref + "/"):
                    defined_ids.add("%s:%s" % (pack_ns, rel[len(pref) + 1:]))
                    break
    # .nbt-шаблоны структур — тоже реестр (structure/<путь>.nbt → ns:<путь>)
    for p in glob.glob(str(root / "structure" / "**" / "*.nbt"), recursive=True):
        rel = Path(p).resolve().relative_to(root.resolve()).as_posix()[:-4]
        defined_ids.add("%s:%s" % (pack_ns, rel[len("structure/"):]))
    # reward-функции достижений — реестр function (function/<путь>.mcfunction
    # → ns:<путь>); заодно проверяем содержимое: файл непустой и все команды
    # начинаются с валидного слова (полноценный парсер не нужен)
    _VALID_CMDS = set(
        "advancement attribute ban ban-ip banlist bossbar clear clone damage "
        "data datapack debug defaultgamemode deop dialog difficulty effect "
        "enchant execute experience fetchprofile fill fillbiome forceload "
        "function gamemode gamerule give help item jfr kick kill list locate "
        "loot me msg op pardon pardon-ip particle perf place playsound "
        "publish random recipe reload return ride rotate save-all save-off "
        "save-on say schedule scoreboard seed setblock setidletimeout "
        "setworldspawn spawnpoint spectate spreadplayers stop stopsound "
        "stopwatch summon swing tag team teammsg teleport tell tellraw test "
        "tick time title tm tp transfer trigger unpublish version w waypoint "
        "weather whitelist worldborder xp".split())
    func_files = glob.glob(str(root / "function" / "**" / "*.mcfunction"),
                           recursive=True)
    bad_funcs = []
    for p in func_files:
        rel = Path(p).resolve().relative_to(root.resolve()).as_posix()[:-11]
        defined_ids.add("%s:%s" % (pack_ns, rel[len("function/"):]))
        try:
            lines = [l.strip() for l in open(p, encoding="utf-8").read().splitlines()]
        except Exception as e:
            bad_funcs.append("%s: %s" % (os.path.basename(p), e))
            continue
        body = [l for l in lines if l and not l.startswith("#")]
        if not body:
            bad_funcs.append("%s: пустая функция" % os.path.basename(p))
            continue
        for l in body:
            word = l.split(None, 1)[0].lower()
            if word not in _VALID_CMDS:
                bad_funcs.append("%s: неизвестная команда %r"
                                 % (os.path.basename(p), l[:60]))
                break

    def collect_refs(obj, out):
        if isinstance(obj, dict):
            for k, v in obj.items():
                # random_name — просто строка; id — АРБИТРАРНЫЙ идентификатор
                # (модификаторы атрибутов зачарований "_a0"/"_loc", id
                # pool_aliases), а не ссылка на реестр; start_jigsaw_name —
                # имя jigsaw-блока в шаблоне (у нас совпадает с путём якоря)
                if k in ("random_name", "id", "start_jigsaw_name", "alias"):
                    continue
                collect_refs(v, out)
        elif isinstance(obj, list):
            for x in obj:
                collect_refs(x, out)
        elif isinstance(obj, str) and (obj.startswith("%s:" % pack_ns)
                                       or obj.startswith("#%s:" % pack_ns)):
            out.add(obj.lstrip("#"))

    all_refs = set()
    for p in glob.glob(str(root / "**" / "*.json"), recursive=True):
        try:
            collect_refs(json.load(open(p, encoding="utf-8")), all_refs)
        except Exception:
            pass
    # .nbt-шаблоны: бинарные (gzip-NBT), текстовые ссылки из них не достать —
    # но их LootTable/DeathLootTable ссылаются на loot-таблицы этого же пака,
    # которые уже покрыты проверкой JSON-реестров
    nbt_count = len(glob.glob(str(root / "structure" / "**" / "*.nbt"),
                              recursive=True))
    # ссылки "<ns>:..." из mcfunction-текстов (advancement revoke/grant,
    # execute in, rewards) — общий сборщик сканирует только JSON
    for p in func_files:
        try:
            txt = open(p, encoding="utf-8").read()
        except Exception:
            continue
        for m in re.finditer(r"#?%s:[a-z0-9_./\-]+" % re.escape(pack_ns), txt):
            all_refs.add(m.group(0).lstrip("#"))
    broken = sorted(r for r in all_refs if r not in defined_ids)
    print("реестры: определено %d ID, ссылок %d (nbt-шаблонов %d), битых: %s"
          % (len(defined_ids), len(all_refs), nbt_count, broken or "нет"))
    # достижения: дерево вкладки — один корень, у узла <= 2 видимых детей
    # (ачивки-ШАГИ _stepN из подсчёта ИСКЛЮЧЕНЫ — прогресс-узлы), все
    # parent-ссылки ведут на существующие ачивки этого пака. Шаги
    # проверяются МЯГКО: файла нет — не проверяем (старые измерения
    # живут без шагов), есть — parent и rewards.function обязаны быть
    adv_tree = {}
    step_advs = []
    _step_rx = re.compile(r"_step[0-9]+$")
    for p in glob.glob(str(root / "advancement" / "**" / "*.json"),
                       recursive=True):
        try:
            a = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        rel = Path(p).resolve().relative_to(root.resolve()).as_posix()[:-5]
        aid = "%s:%s" % (pack_ns, rel[len("advancement/"):])
        if not isinstance(a, dict):
            continue
        if _step_rx.search(rel):          # шаги — прогресс-узлы
            if "display" in a:
                step_advs.append((aid, a))
            continue
        if "display" in a:                # скрытые не в дереве
            adv_tree[aid] = a.get("parent")
    bad_tree = []
    roots = [i for i, p in adv_tree.items() if not p or p not in adv_tree]
    if len(adv_tree) > 1 and len(roots) != 1:
        bad_tree.append("корней %d (%s)" % (len(roots), roots[:3]))
    children = {}
    for i, p in adv_tree.items():
        if p:
            children.setdefault(p, []).append(i)
    for i, ch in children.items():
        if len(ch) > 2:
            bad_tree.append("у %s детей %d (>2)" % (i, len(ch)))
    for i, p in adv_tree.items():
        if p and p not in adv_tree:
            bad_tree.append("битый parent у %s: %s" % (i, p))
    # мягкая проверка шагов (только существующие _step-файлы)
    bad_steps = []
    for aid, a in step_advs:
        parent = a.get("parent")
        if not parent or parent not in adv_tree:
            bad_steps.append("%s: битый parent %s" % (aid, parent))
        rw = a.get("rewards") or {}
        fid = rw.get("function")
        if not fid:
            bad_steps.append("%s: нет rewards.function" % aid)
        elif fid not in defined_ids:
            bad_steps.append("%s: функция %s не найдена" % (aid, fid))
        if not a.get("criteria"):
            bad_steps.append("%s: нет критериев" % aid)
    n_hidden = sum(1 for p in glob.glob(
        str(root / "advancement" / "**" / "*.json"), recursive=True)
        if os.path.basename(p).endswith("_tp.json"))
    print("достижений: видимых %d (шагов %d), скрытых %d, функций %d; "
          "дерево: %s; шаги: %s; функции: %s" % (
              len(adv_tree), len(step_advs), n_hidden, len(func_files),
              "все ок" if not bad_tree else "; ".join(bad_tree),
              "все ок" if not bad_steps else "; ".join(bad_steps[:5]),
              "все ок" if not bad_funcs else "; ".join(bad_funcs[:5])))
    # провайдеры trapezoid: plateau СТРОГО <= max-min («Plateau can at most
    # be the full span» на реальном сервере валидит при загрузке реестров
    # и роняет ВЕСЬ пак — ловим заранее)
    def _trap_bad(node, path):
        out = []
        if isinstance(node, dict):
            if node.get("type") == "minecraft:trapezoid":
                mn = node.get("min", node.get("min_inclusive"))
                mx = node.get("max", node.get("max_exclusive",
                                              node.get("max_inclusive")))
                pl = node.get("plateau", 0)
                if (isinstance(mn, (int, float))
                        and isinstance(mx, (int, float))
                        and isinstance(pl, (int, float))
                        # строгий порог: сервер (float-арифметика) отвергает
                        # plateau == span даже когда Python-дабл mx-mn == pl
                        # (perycrest_cav4: [0.4,5.2] p=4.8) — требуем запас 0.1
                        and pl >= round(mx - mn, 6) - 0.1):
                    out.append("%s [%s, %s] plateau=%s" % (path, mn, mx, pl))
            for k, v in node.items():
                out += _trap_bad(v, path + "/" + k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                out += _trap_bad(v, "%s[%d]" % (path, i))
        return out

    bad_trap = []
    for p in glob.glob(str(root / "**" / "*.json"), recursive=True):
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        for msg in _trap_bad(d, ""):
            bad_trap.append("%s: %s" % (
                Path(p).resolve().relative_to(root.resolve()).as_posix(), msg))
    if bad_trap:
        for m in bad_trap:
            print("ТРАПЕЦОИД plateau>span:", m)
    print("trapezoid-провайдеры: %s"
          % ("все ок" if not bad_trap else "%d ошибок" % len(bad_trap)))
    # loot-предикаты: КОРЕНЬ файла не может быть голым безпараметрическим
    # условием-синглтоном (survives_explosion/killed_by_player держат
    # interned-INSTANCE — два таких корня в паке = «Adding duplicate
    # value ... to registry», падает весь пак; как end_islands в DF)
    _LOOT_SINGLETONS = ("minecraft:survives_explosion",
                        "minecraft:killed_by_player")
    bad_single = []
    for sub in ("predicate", "item_modifier"):
        for p in glob.glob(str(root / sub / "**" / "*.json"), recursive=True):
            try:
                d = json.load(open(p, encoding="utf-8"))
            except Exception:
                continue
            roots = d if isinstance(d, list) else [d]
            if len(roots) == 1 and isinstance(roots[0], dict) and \
                    roots[0].get("condition") in _LOOT_SINGLETONS:
                bad_single.append(
                    "%s: голый синглтон-корень %s"
                    % (Path(p).resolve().relative_to(root.resolve()).as_posix(),
                       roots[0]["condition"]))
    if bad_single:
        for m in bad_single:
            print("СИНГЛТОН-КОРЕНЬ:", m)
    print("loot-корни: %s"
          % ("все ок" if not bad_single
             else "%d ошибок" % len(bad_single)))
    # damageable-предметы + max_stack_size>1: валидатор 26.2 отвергает
    # ПАТЧ целиком («Item cannot be both damageable and stackable») —
    # предмет не создастся. Список _DAMAGEABLE в gen_loot получен
    # серверной пробой всех 1523 предметов реестра
    _gl_mod = _gl()
    _damageable = getattr(_gl_mod, "_DAMAGEABLE", frozenset()) \
        if _gl_mod is not None else frozenset()
    # стек-1 предметы внутри container/bundle_contents с count>1 —
    # validateContainedItemSizes («Item stack with count of N was larger
    # than maximum: 1»), патч отвергается целиком. Список _STACK1 тоже
    # из серверной пробы (240 предметов)
    _stack1 = getattr(_gl_mod, "_STACK1", frozenset()) \
        if _gl_mod is not None else frozenset()

    def _stack_bad(node, item, path, out):
        # item — имя предмета ближайшей записи-предка (для вложенных
        # пулов наследуем, set_components может висеть и на записи, и
        # в списке функций)
        if isinstance(node, dict):
            if node.get("type") == "minecraft:item" and \
                    isinstance(node.get("name"), str):
                item = node["name"]
            # стек-1 предмет с count>1: container/bundle_contents кладут
            # предметы как {"id":..., "count":...} (без type) — их id и
            # проверяем; записи-предметы count в комп. не имеют, но
            # проверка безвредна и для них
            cnt = node.get("count")
            cid = node.get("id")
            if isinstance(cnt, int) and cnt > 1:
                cur = cid if isinstance(cid, str) else item
                if cur in _stack1:
                    out.append("%s: %s count=%d (stack-1)"
                               % (path, cur, cnt))
            for f in node.get("functions") or []:
                if not isinstance(f, dict):
                    continue
                if f.get("function") == "minecraft:set_count":
                    c = f.get("count")
                    if isinstance(c, int) and c > 1 and item in _stack1:
                        out.append("%s: %s set_count=%d (stack-1)"
                                   % (path, item or "?", c))
                comps = f.get("components") or {}
                if not isinstance(comps, dict):
                    continue
                mss = comps.get("minecraft:max_stack_size")
                if isinstance(mss, int) and mss > 1 and (
                        item in _damageable
                        or "minecraft:max_damage" in comps):
                    out.append("%s: %s max_stack_size=%d"
                               % (path, item or "?", mss))
            for k, v in node.items():
                _stack_bad(v, item, path + "/" + k, out)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                _stack_bad(v, item, "%s[%d]" % (path, i), out)

    bad_stack = []
    for p in glob.glob(str(root / "loot_table" / "**" / "*.json"),
                       recursive=True):
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        _stack_bad(d, None, "", bad_stack)
    if bad_stack:
        for m in bad_stack:
            print("СТЕК-НАРУШЕНИЕ (damageable/stack-1):", m)
    print("стек-нарушения (damageable + stack-1): %s"
          % ("все ок" if not bad_stack else "%d ошибок" % len(bad_stack)))
    bad = 0
    for p in glob.glob(str(root / "**" / "*.json"), recursive=True):
        try:
            json.load(open(p, encoding="utf-8"))
        except Exception as e:
            bad += 1
            print("БИТЫЙ JSON:", p, e)
    print("JSON: %s" % ("все ок" if not bad else "%d ошибок" % bad))


def _self_test():
    """Самотест спавн-тегов (data/minecraft/tags/block): генерация
    измерений во ВРЕМЕННЫЙ каталог (основной пак не трогается) пишет
    все 13 ванильных тегов с поверхностными блоками (default_block +
    surface_rule каждого измерения, объединение по всему паку, включая
    другие namespace), а regen-логика корректно удаляет/сохраняет
    файлы в зависимости от оставшихся измерений."""
    import tempfile
    global DATA_ROOT
    old_root = DATA_ROOT
    td = tempfile.mkdtemp(prefix="rndim_tags_selftest_")
    try:
        DATA_ROOT = Path(td) / "data"
        # 1) два измерения в одном namespace — теги пишутся, валидны и
        #    содержат поверхностные блоки КАЖДОГО измерения
        for seed, nm in ((11, "alpha"), (22, "beta")):
            res = DimensionGenerator(
                random.Random(seed), "rndim", nm).generate()
            write_dimension("rndim", res)
        tag_dir = DATA_ROOT / "minecraft" / "tags" / "block"
        found = glob.glob(str(tag_dir / "*.json"))
        assert len(found) == len(SPAWNABLE_TAGS), \
            "ожидались 13 тегов, есть %d" % len(found)
        per_tag = {}
        for tag in SPAWNABLE_TAGS:
            with open(tag_dir / (tag + ".json"), encoding="utf-8") as f:
                d = json.load(f)
            assert set(d) == {"values"}, "%s: лишние ключи (replace?)" % tag
            vals = d["values"]
            assert all(isinstance(v, str) for v in vals), tag
            assert vals == sorted(set(vals)), "%s: дубли/не сортировано" % tag
            per_tag[tag] = set(vals)
        # все 13 тегов получают один и тот же набор поверхностных блоков
        assert len({frozenset(v) for v in per_tag.values()}) == 1, \
            "теги различаются между собой"
        got = next(iter(per_tag.values()))
        for nm in ("alpha", "beta"):
            with open(DATA_ROOT / "rndim" / "worldgen" / "noise_settings"
                      / (nm + ".json"), encoding="utf-8") as f:
                want = noise_settings_surface_blocks(json.load(f))
            want &= _SPAWN_TAG_SAFE_IDS
            assert want, "%s: пустой набор поверхностных блоков" % nm
            assert want <= got, "%s: в тегах нет %s" % (
                nm, sorted(want - got)[:3])
        # 2) измерение в ДРУГОМ namespace — теги общие на пак: блоки
        #    обоих namespace'ов объединяются в одних и тех же файлах
        res = DimensionGenerator(
            random.Random(33), "otherns", "gamma").generate()
        write_dimension("otherns", res)
        with open(tag_dir / "animals_spawnable_on.json",
                  encoding="utf-8") as f:
            got2 = set(json.load(f)["values"])
        with open(DATA_ROOT / "otherns" / "worldgen" / "noise_settings"
                  / "gamma.json", encoding="utf-8") as f:
            want_g = noise_settings_surface_blocks(json.load(f))
        want_g &= _SPAWN_TAG_SAFE_IDS
        assert want_g, "gamma: пустой набор поверхностных блоков"
        assert want_g <= got2, "блоки другого namespace не попали в тег"
        # 3) regen при оставшемся namespace: файлы остаются, блоки
        #    оставшегося измерения на месте
        shutil.rmtree(DATA_ROOT / "rndim")
        regen_spawnable_tags()
        with open(tag_dir / "animals_spawnable_on.json",
                  encoding="utf-8") as f:
            got3 = set(json.load(f)["values"])
        assert want_g <= got3, "regen потерял блоки оставшегося namespace"
        # 4) regen при пустом паке: все 13 файлов удаляются вместе с
        #    опустевшими каталогами minecraft/tags/block
        shutil.rmtree(DATA_ROOT / "otherns")
        regen_spawnable_tags()
        assert not glob.glob(str(tag_dir / "*.json")), \
            "теги не удалены при пустом паке"
        assert not tag_dir.exists(), "каталог tags/block не убран"
        assert not (DATA_ROOT / "minecraft").exists(), \
            "каталог minecraft не убран"
        print("самотест спавн-тегов: OK (%d блоков в каждом теге)"
              % len(got))
    finally:
        DATA_ROOT = old_root
        shutil.rmtree(td, ignore_errors=True)


def _resolve_anchor_y(anchor, min_y, max_y_inc):
    """Якорь height_range → абсолютный Y (для самотеста; max_y_inc —
    включительный верх, как в gen_features)."""
    if "absolute" in anchor:
        return anchor["absolute"]
    if "above_bottom" in anchor:
        return min_y + anchor["above_bottom"]
    return max_y_inc - anchor["below_top"]


# ---------------------------------------------------------------------------
# Мини-симулятор density-функций (самотест): численная проверка того, что
# final_density НЕ насыщается — доля твёрдого в разумных пределах, воздух
# у краёв есть в каждом столбце, пояс cavern пуст. Появилось после
# регрессии «шум заполняет мир насплочь от min_y до max_y»: abs-ridged
# слои с большими амплитудами сажали плотность > 0 ВЕЗДЕ.
# ---------------------------------------------------------------------------

def _fnv1a(s):
    """FNV-1a 32 бит — детерминированный хэш строк (seed шума)."""
    h = 2166136261
    for ch in s.encode("utf-8"):
        h = ((h ^ ch) * 16777619) & 0xFFFFFFFF
    return h


def _vn_h(ix, iy, iz, s):
    """Хэш целочисленной решётки → [-1, 1)."""
    h = (ix * 0x27D4EB2D) ^ (iy * 0x165667B1) ^ (iz * 0x9E3779B1) \
        ^ (s * 0x85EBCA6B)
    h &= 0xFFFFFFFF
    h ^= h >> 15
    h = (h * 0x2C1B3C6D) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 0x297A2D39) & 0xFFFFFFFF
    h ^= h >> 16
    return (h & 0xFFFF) / 32768.0 - 1.0


def _vnoise(x, y, z, s):
    """3D value-noise [-1, 1] с квинтическим сглаживанием,
    ОТКАЛИБРОВАННЫЙ под ванильный NormalNoise: масштаб 0.617 подобран
    так, чтобы σ октавы равнялась ванильной 0.25*amp (без калибровки
    симулятор завышал амплитуду в 1.62 раза — нормировки climate-
    каналов и пороги островов плыли)."""
    x0, y0, z0 = math.floor(x), math.floor(y), math.floor(z)
    fx, fy, fz = x - x0, y - y0, z - z0
    fx = fx * fx * fx * (fx * (fx * 6.0 - 15.0) + 10.0)
    fy = fy * fy * fy * (fy * (fy * 6.0 - 15.0) + 10.0)
    fz = fz * fz * fz * (fz * (fz * 6.0 - 15.0) + 10.0)
    a = _vn_h(x0, y0, z0, s) + (_vn_h(x0 + 1, y0, z0, s)
                                - _vn_h(x0, y0, z0, s)) * fx
    b = _vn_h(x0, y0 + 1, z0, s) + (_vn_h(x0 + 1, y0 + 1, z0, s)
                                    - _vn_h(x0, y0 + 1, z0, s)) * fx
    c = _vn_h(x0, y0, z0 + 1, s) + (_vn_h(x0 + 1, y0, z0 + 1, s)
                                    - _vn_h(x0, y0, z0 + 1, s)) * fx
    d = _vn_h(x0, y0 + 1, z0 + 1, s) + (_vn_h(x0 + 1, y0 + 1, z0 + 1, s)
                                        - _vn_h(x0, y0 + 1, z0 + 1, s)) * fx
    v = a + (b - a) * fy + (c + (d - c) * fy - a - (b - a) * fy) * fz
    return v * 0.617


def _sim_noise_sample(spec, x, y, z, s):
    """Октавный value-noise по спектру (firstOctave/amplitudes):
    статистика (σ ~ 0.25*sqrt(Σamp²)) достаточно близка к ванильному
    NormalNoise, чтобы ловить насыщение плотности."""
    first = spec.get("firstOctave", 0)
    total = 0.0
    for i, amp in enumerate(spec.get("amplitudes") or ()):
        if not amp:
            continue
        f = 2.0 ** (first + i)
        total += amp * _vnoise(x * f, y * f, z * f, (s + i * 1013) & 0xFFFF)
    return total


def _sim_df(df, x, y, z, gen, zero_noise=False):
    """Оценка density-функции в точке (x, y, z) для самотеста.
    zero_noise=True — все шумы нейтральны (0.0): так проверяются
    СТРУКТУРНЫЕ гарантии — градиенты/min/max обязаны давать воздух/камень
    у краёв мира при любом шуме. interpolated/cache_*/blend_density —
    тождества (сглаживание ячеек реальной игры на статистику плотности
    не влияет); squeeze — по вики: clamp(x,-1,1) затем x/2 - x³/24."""
    while isinstance(df, str):            # ссылка на DF-файл
        df = gen.dfs[df]
    if isinstance(df, (int, float)):
        return float(df)
    t = df.get("type")

    def a(k):
        return _sim_df(df[k], x, y, z, gen, zero_noise)

    if t == "minecraft:noise":
        if zero_noise:
            return 0.0
        return _sim_noise_sample(
            gen.noises[df["noise"]], x * df["xz_scale"],
            y * df["y_scale"], z * df["xz_scale"],
            _fnv1a(df["noise"]) & 0xFFFF)
    if t == "minecraft:shifted_noise":
        if zero_noise:
            return 0.0

        def shift(v):
            if isinstance(v, (int, float)):
                return float(v)
            return _sim_df(v, x, y, z, gen, zero_noise) * 16.0

        sx = shift(df.get("shift_x", 0.0))
        sy = shift(df.get("shift_y", 0.0))
        sz = shift(df.get("shift_z", 0.0))
        return _sim_noise_sample(
            gen.noises[df["noise"]], (x + sx) * df["xz_scale"],
            (y + sy) * df["y_scale"], (z + sz) * df["xz_scale"],
            _fnv1a(df["noise"]) & 0xFFFF)
    if t in ("minecraft:shift_a", "minecraft:shift_b"):
        if zero_noise:
            return 0.0
        arg = df.get("argument")
        spec = gen.noises.get(arg) if isinstance(arg, str) else arg
        if not isinstance(spec, dict):
            return 0.0
        return _sim_noise_sample(spec, x * 0.25, 0.0, z * 0.25,
                                 _fnv1a(str(arg)) & 0xFFFF)
    if t == "minecraft:y_clamped_gradient":
        fy, tyy = float(df["from_y"]), float(df["to_y"])
        fv, tv = float(df["from_value"]), float(df["to_value"])
        if y <= fy:
            return fv
        if y >= tyy:
            return tv
        return fv + (tv - fv) * (y - fy) / (tyy - fy)
    if t == "minecraft:add":
        return a("argument1") + a("argument2")
    if t == "minecraft:mul":
        return a("argument1") * a("argument2")
    if t == "minecraft:min":
        return min(a("argument1"), a("argument2"))
    if t == "minecraft:max":
        return max(a("argument1"), a("argument2"))
    if t == "minecraft:clamp":
        return min(max(a("input"), float(df["min"])), float(df["max"]))
    if t == "minecraft:abs":
        return abs(a("argument"))
    if t == "minecraft:square":
        v = a("argument")
        return v * v
    if t == "minecraft:cube":
        v = a("argument")
        return v * v * v
    if t == "minecraft:half_negative":
        v = a("argument")
        return v * 0.5 if v < 0 else v
    if t == "minecraft:quarter_negative":
        v = a("argument")
        return v * 0.25 if v < 0 else v
    if t == "minecraft:squeeze":
        v = min(1.0, max(-1.0, a("argument")))
        return v / 2.0 - v * v * v / 24.0
    if t in ("minecraft:interpolated", "minecraft:cache_once",
             "minecraft:cache_2d", "minecraft:flat_cache",
             "minecraft:blend_density"):
        return a("argument")
    if t == "minecraft:range_choice":
        v = a("input")
        if float(df["min_inclusive"]) <= v < float(df["max_exclusive"]):
            return a("when_in_range")
        return a("when_out_of_range")
    if t == "minecraft:interval_select":
        v = a("input")
        for thr, f in zip(df["thresholds"], df["functions"]):
            if v < float(thr):
                return _sim_df(f, x, y, z, gen, zero_noise)
        return _sim_df(df["functions"][-1], x, y, z, gen, zero_noise)
    if t == "minecraft:spline":
        sp = df["spline"]
        c = _sim_df(sp["coordinate"], x, y, z, gen, zero_noise)
        pts = sp["points"]

        def val(p):
            v = p["value"]
            if isinstance(v, (int, float)):
                return float(v)
            return _sim_df({"type": "minecraft:spline", "spline": v},
                           x, y, z, gen, zero_noise)

        if c <= float(pts[0]["location"]):
            return val(pts[0])
        for p0, p1 in zip(pts, pts[1:]):
            l0, l1 = float(p0["location"]), float(p1["location"])
            if c < l1:
                w = 0.0 if l1 <= l0 else (c - l0) / (l1 - l0)
                return val(p0) + w * (val(p1) - val(p0))
        return val(pts[-1])
    if t == "minecraft:end_islands":
        # в final_density не попадает (только rand_df других каналов);
        # приблизительно по диапазону вики [-0.84375, 0.5625]
        if zero_noise:
            return 0.0
        return min(0.5625, max(-0.84375,
                               _vnoise(x * 0.05, 0.0, z * 0.05, 7777) * 1.4))
    return 0.0


def _abs_outside_clamp(df, gen, bounded=False):
    """Есть ли в дереве DF узел abs, НЕ накрытый clamp-ом с диапазоном,
    содержащим ноль (min <= 0 <= max) — по пути к корню. Голый abs >= 0
    в max-позиции дерева — механика регрессии «мир насплочь из камня»."""
    if isinstance(df, str):
        df = gen.dfs.get(df)
        if df is None:
            return False
    if isinstance(df, (int, float)):
        return False
    if isinstance(df, list):
        return any(_abs_outside_clamp(v, gen, bounded) for v in df)
    if df.get("type") == "minecraft:clamp":
        try:
            bounded = float(df["min"]) <= 0.0 <= float(df["max"])
        except (KeyError, TypeError, ValueError):
            bounded = False
    if df.get("type") == "minecraft:abs" and not bounded:
        return True
    for v in df.values():
        if isinstance(v, (dict, list, str)) \
                and _abs_outside_clamp(v, gen, bounded):
            return True
    return False


def _count_block_rules(node, name):
    """Сколько раз блок name ставится result_state-ом в дереве
    surface_rule (счётчик вхождений, не множество)."""
    n = 0
    if isinstance(node, dict):
        rs = node.get("result_state")
        if isinstance(rs, dict) and rs.get("Name") == name:
            n += 1
        for v in node.values():
            n += _count_block_rules(v, name)
    elif isinstance(node, list):
        for v in node:
            n += _count_block_rules(v, name)
    return n


def _bedrock_conditions(rule):
    """Все условия surface_rule, чей then_run ставит minecraft:bedrock.
    Возвращает список 'floor'/'roof'/'OTHER' — по random_name условия."""
    out = []

    def walk(node):
        if isinstance(node, dict):
            it, tr = node.get("if_true"), node.get("then_run")
            if isinstance(it, dict) and isinstance(tr, dict):
                if _count_block_rules(tr, "minecraft:bedrock"):
                    # кровля по ванили завёрнута в minecraft:not —
                    # random_name лежит внутри invert
                    inv = it.get("invert")
                    rn = str(it.get("random_name")
                             or (inv.get("random_name")
                                 if isinstance(inv, dict) else "")
                             or "")
                    if "bedrock_floor" in rn:
                        out.append("floor")
                    elif "bedrock_roof" in rn:
                        out.append("roof")
                    else:
                        out.append("OTHER")
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(rule)
    return out


def _bedrock_bands(rule):
    """Якоря vertical_gradient-условий бедрока: {'floor': (true, false,
    wrapped), 'roof': (...)} — с учётом ванильной обёртки minecraft:not
    у кровли. Для самотеста: полоса дна = 0..(4-6) above_bottom БЕЗ
    обёртки, кровля = (4-6)..0 below_top В обёртке not (рваный рельеф
    как в nether.json 26.2)."""
    out = {}

    def walk(node):
        if isinstance(node, dict):
            it, tr = node.get("if_true"), node.get("then_run")
            if isinstance(it, dict) and isinstance(tr, dict) \
                    and _count_block_rules(tr, "minecraft:bedrock"):
                wrapped = it.get("type") == "minecraft:not"
                g = it.get("invert") if wrapped else it
                if isinstance(g, dict) \
                        and g.get("type") == "minecraft:vertical_gradient":
                    rn = str(g.get("random_name", ""))
                    ta, fa = g.get("true_at_and_below") or {}, \
                        g.get("false_at_and_above") or {}
                    if "bedrock_floor" in rn:
                        out["floor"] = (dict(ta), dict(fa), wrapped)
                    elif "bedrock_roof" in rn:
                        out["roof"] = (dict(ta), dict(fa), wrapped)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(rule)
    return out


def _biome_top_blocks(rule):
    """top-блок каждого биомного условия surface_rule (первый
    floor-слой stone_depth offset 0 / без surface_depth) — для
    самотеста уникальности top-блоков между биомами."""
    out = []

    def walk(node):
        if isinstance(node, dict):
            it = node.get("if_true")
            if isinstance(it, dict) and it.get("type") == "minecraft:biome" \
                    and isinstance(it.get("biome_is"), (str, list)):
                tr = node.get("then_run") or {}
                for sub in (tr.get("sequence") or []):
                    if not isinstance(sub, dict):
                        continue
                    c = sub.get("if_true") or {}
                    if c.get("type") == "minecraft:stone_depth" \
                            and c.get("surface_type") == "floor" \
                            and c.get("offset") == 0 \
                            and not c.get("add_surface_depth"):
                        rs = (sub.get("then_run") or {}).get(
                            "result_state") or {}
                        if rs.get("Name"):
                            out.append(rs["Name"])
                        break
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(rule)
    return out


def _simulate_density(gen, df, cols=4, ysteps=30):
    """Численная симуляция final_density: сетка (x,z) x y — доля
    твёрдых блоков (density > 0), воздух у краёв по столбцам, пустота
    пояса cavern. Шаг по y ограничен полосой гарантий, чтобы градиенты
    у краёв не проскочили между выборками."""
    step = max(2, min(gen.height // ysteps,
                      max(3, gen.density_band // 3)))
    ys = list(range(gen.min_y, gen.max_y, step))
    # принудительные точки гарантий — не зависят от шага сетки
    for yy in (gen.min_y, gen.min_y + 1, gen.max_y - 2, gen.max_y - 3):
        if gen.min_y <= yy < gen.max_y:
            ys.append(yy)
    if gen.world_shape == "cavern":
        for yy in (gen.belt_lo + 2, (gen.belt_lo + gen.belt_hi) // 2,
                   gen.belt_hi - 2):
            if gen.min_y <= yy < gen.max_y:
                ys.append(yy)
    ys = sorted(set(ys))
    top20 = gen.max_y - gen.height // 5
    bot20 = gen.min_y + gen.height // 5
    solid = total = 0
    air_top = air_bot = 0
    belt_air = belt_total = 0
    # колонны РАЗБРОСАНЫ по ±1000 блоков с джиттером (хэш от имени
    # мира): октава-0 островных шумов тянет волны до ~1600 блоков —
    # регулярная сетка в 550 блоков сидела внутри одной волны и
    # показывала «пустой мир» там, где он просто локально пуст
    base = _fnv1a(gen.name)
    for ci in range(cols):
        for cj in range(cols):
            x = _vn_h(ci + 31, cj + 7, 0, base) * 1000.0
            z = _vn_h(ci + 7, cj + 31, 1, base) * 1000.0
            has_top = has_bot = False
            for yy in ys:
                v = _sim_df(df, x, float(yy), z, gen)
                total += 1
                if v > 0.0:
                    solid += 1
                if yy >= top20 and v <= 0.0:
                    has_top = True
                if yy <= bot20 and v <= 0.0:
                    has_bot = True
                if gen.world_shape == "cavern" \
                        and gen.belt_lo + 1 <= yy <= gen.belt_hi - 1:
                    belt_total += 1
                    if v <= 0.0:
                        belt_air += 1
            if has_top:
                air_top += 1
            if has_bot:
                air_bot += 1
    return {"solid": solid / max(1, total), "cols": cols * cols,
            "air_top": air_top, "air_bot": air_bot,
            "belt_air": belt_air / max(1, belt_total)}


def _self_test_worldgen():
    """Самотест новых систем — генерация ТОЛЬКО в память (файлы не
    пишутся, основной пак не трогается):
    - кровать: во ВСЕХ мирах bed_rule = can_set_spawn: always (взрыва
      больше не бывает);
    - final_density: (а) СТРУКТУРНЫЕ гарантии — при нейтральных шумах
      (zero_noise) края мира обязаны быть воздухом/камнем по форме
      (open: воздух у max_y + камень у min_y; cavern: камень у ОБЕИХ
      краёв + воздух в поясе; void: воздух у обоих краёв); (б) НИ
      ОДНОГО abs вне clamp с диапазоном через ноль — механика
      регрессии «мир насплочь из камня» (abs >= 0 в max-позиции);
      (в) численная симуляция плотности (_simulate_density): доля
      твёрдого 20-80% (open) / 20-84% (cavern — потолок конверта:
      пояс ≥ 17% высоты) / 5-50% (void), воздух
      в верхних 20% высоты есть в КАЖДОМ столбце (open/void, у void —
      и в нижних 20%), пояс cavern пуст; (г) бедрок — только
      bedrock_floor/bedrock_roof, floor ⟺ форма != void, roof ⟺
      cavern, вхождений bedrock в surface_rule <= 2; ПОЛОСЫ рваные
      как в nether.json 26.2: дно 0..(4-6) above_bottom, кровля
      (4-6)..0 below_top и ОБЯЗАТЕЛЬНО в обёртке minecraft:not
      (без неё «true_at_and_below» красит бедроком весь массив
      ниже кровли);
    - СЫПУЧИЕ: default_block и default_fluid — НИКОГДА не сыпучие (в
      любой форме мира); void — ни одного сыпучего в рельефе/фичах
      (прежняя проверка); open/cavern — не более 2 РАЗНЫХ сыпучих
      среди surface_rule, и только при семействе >= 3 блоков;
    - мобы: боссы (визер/дракон/варден) — тир веса 0.1 в
      SPAWN_POOLS, а в биомных спавнерах всегда минимальная запись
      weight 1 группой ровно из 1; веса обычных тиров 24/10;
    - руды: 5-9 видов, у каждого 4 варианта богатства со строго
      возрастающим count; height_range всех вариантов — внутри границ
      мира; в одном биоме — не более одного варианта каждой руды;
    - подземные биомы: в мирах с высотой >= 128, биомами >= 6 и
      multi_noise их 2-3 (высота 128-255) или 3-6 (>= 256); depth-полосы
      непересекающиеся, внутри [CAVE_BAND_TOP, CAVE_BAND_BOTTOM]
      (0.2..1.45 — первая полоса сразу под поверхностью, как в ваниле;
      не залезают на поверхность — у надземных depth ровно 0.0),
      continentalness нейтрализован; в остальных мирах подземных
      биомов нет;
    - climate-каналы: окна спеки (юзер: биомы чуть крупнее) —
      firstOctave -10..-7, xz 0.10..0.28, y 0.0, σ 0.35..0.7;
      continents: firstOctave -9..-7, σ 0.6..1.1, волна октавы-0
      768..2560; пресеты рельефа эти каналы НЕ трогают (находимость
      биомов), как и климатические решётки биом-сорса (до 12 ячеек
      на кластер при 20-30 биомах);
    - шумы рельефа: firstOctave -19..2, хотя бы одна ненулевая
      амплитуда;
    - каменное семейство: 3-7 блоков, тиры 1-2/1-3/1-2, уникальны и
      != default_block; блобы (id <name>_stoneN/<name>_blobN) — в
      КАЖДОМ биоме, size <= 64, «редкие» с rarity 1/4-1/16; полосы
      1-2 (высокие миры — ровно 2, void — нет), заплатки 1-3;
    - void-миры: НИ ОДНОГО сыпучего блока в рельефе — default_block,
      default_fluid, surface rules, blockstate-позиции фич (блобы/
      диски/слои/жеоды...); ванильные диски песка/гравия и гравийные
      жилы не попадают в биомы."""
    import tempfile
    global DATA_ROOT
    old_root = DATA_ROOT
    td = tempfile.mkdtemp(prefix="rndim_worldgen_selftest_")
    tall = flat = voids = 0
    seed = 0
    # веса мобов: боссы — отдельный тир 0.1 (в 10 раз реже веса 1)
    mtiers = SPAWN_POOLS["monster"]
    boss_tiers = [t for t in mtiers if t[1] and set(t[1]) == BOSS_MOBS]
    assert len(boss_tiers) == 1 and abs(boss_tiers[0][0] - 0.1) < 1e-9, \
        "боссы должны быть отдельным тиром веса 0.1"
    assert not (BOSS_MOBS & {m for w, ms in mtiers if w >= 1
                             for m in ms}), \
        "боссы не должны попадать в обычные тиры"
    try:
        DATA_ROOT = Path(td) / "data"
        while (tall < 4 or flat < 3 or voids < 3) and seed < 250:
            seed += 1
            rng = random.Random(seed)
            gen = DimensionGenerator(rng, "rndim", "wst%d" % seed)
            res = gen.generate()
            # пресет рельефа записан и известен таблице; биомов 20-30
            assert gen.terrain_preset in {p["name"]
                                          for p in TERRAIN_PRESETS}, \
                "неизвестный пресет рельефа: %s" % gen.terrain_preset
            assert 20 <= len(gen.biomes) <= 30, \
                "биомов %d — должно быть 20-30" % len(gen.biomes)
            # --- final_density: гарантии / насыщение / бедрок ---
            fd = res["noise_settings"]["noise_router"]["final_density"]
            # (а) структурные гарантии при нейтральных шумах
            def _z(yy):
                return _sim_df(fd, 7.0, float(yy), 13.0, gen,
                               zero_noise=True)
            if gen.world_shape == "open":
                assert _z(gen.min_y) > 0.0, "open: нет твёрдого у min_y"
                assert _z(gen.max_y - 2) < 0.0, "open: нет воздуха у max_y"
                # ПЛОСКИЙ кап дна: плита [my+2 .. my+H] на +3.5
                Ho = gen.flat_cap_h
                assert Ho >= 2 and _z(gen.min_y) >= 3.0 \
                    and _z(gen.min_y + Ho) >= 3.0, \
                    "open: плита дна не твёрдая (H=%d)" % Ho
            elif gen.world_shape == "cavern":
                assert _z(gen.min_y) > 0.0 and _z(gen.max_y - 2) > 0.0, \
                    "cavern: нет твёрдых дна/кровли"
                # ПЛОСКИЕ ТВЁРДЫЕ КАПЫ: плита потолка [ty-H .. ty-2] и
                # дна [my+2 .. my+H] держат плотность РОВНО +3.5 БЕЗ
                # пересечения нуля, крайние ряды — +3.0 (жалоба юзера:
                # «крыша бедрока на максимальной высоте мира — сейчас
                # бедрок ниже, сверху него ещё рельеф»); на плиту сверху
                # ложится бедрок-полоса surface-правил (below_top
                # 0..thick+1, thick 3-5 — заведомо внутри плиты)
                Hc = gen.flat_cap_h
                assert Hc >= 2 and _z(gen.max_y - 2) >= 3.0 \
                    and _z(gen.max_y - 3) >= 3.0 \
                    and _z(gen.max_y - Hc) >= 3.0, \
                    "cavern: плита потолка не твёрдая (H=%d)" % Hc
                assert _z(gen.min_y) >= 3.0 and _z(gen.min_y + 1) >= 3.0 \
                    and _z(gen.min_y + Hc) >= 3.0, \
                    "cavern: плита дна не твёрдая (H=%d)" % Hc
                assert _z((gen.belt_lo + gen.belt_hi) // 2) < 0.0, \
                    "cavern: нет воздуха в поясе"
                assert gen.belt_lo > gen.min_y + gen.density_band \
                    and gen.belt_hi < gen.max_y - gen.density_band, \
                    "пояс cavern залезает на полосы гарантий"
            else:
                assert _z(gen.min_y) < 0.0 and _z(gen.max_y - 2) < 0.0, \
                    "void: нет воздуха у краёв"
            # (б) abs вне clamp (механика «мира насплочь»)
            assert not _abs_outside_clamp(fd, gen), \
                "abs вне clamp с диапазоном через ноль — насыщение"
            # (в) численная симуляция плотности
            st = _simulate_density(gen, fd)
            # потолок cavern — по КОНСТРУКЦИИ генератора: воздушный пояс
            # ≥ 2×max(6, 9%·h) ширины (см. belt в generate) → доля
            # твёрдого ≤ ~83%; пояс пуст и края-градиенты проверяются
            # ОТДЕЛЬНО ниже, так что 0.84 — потолок конверта, а не калибровка
            # по выборке (при сдвиге rng-потока узкая калибровка 0.75
            # ловила легитимные «густые» пещеры — плотный пояс 17%)
            lo, hi = {"open": (0.20, 0.80), "cavern": (0.20, 0.84),
                      "void": (0.05, 0.50)}[gen.world_shape]
            if gen.world_shape == "void" and not (lo <= st["solid"] <= hi):
                # острова void кластеруются сплайном ПО РЕГИОНАМ (густота
                # ±50% от базы): 16 колонн могут целиком попасть между
                # островами — мир при этом нормальный; перепроверяем ШИРЕ
                st = _simulate_density(gen, fd, cols=7)
            assert lo <= st["solid"] <= hi, \
                "плотность вне нормы: твёрдых %.0f%% (форма %s, seed %d)" \
                % (st["solid"] * 100, gen.world_shape, seed)
            if gen.world_shape != "cavern":
                assert st["air_top"] == st["cols"], \
                    "столбцы без воздуха в верхних 20%%: %d из %d" % (
                        st["cols"] - st["air_top"], st["cols"])
            else:
                assert st["belt_air"] >= 0.999, \
                    "воздушный пояс cavern не пуст: %.1f%%" % (
                        st["belt_air"] * 100)
            if gen.world_shape == "void":
                assert st["air_bot"] == st["cols"], \
                    "столбцы без воздуха в нижних 20%%: %d из %d" % (
                        st["cols"] - st["air_bot"], st["cols"])
            # (г) бедрок: floor/roof строго по форме мира; в остальном
            # рельефе (полосы/заплатки/семейство) бедрок ДОПУСТИМ как
            # редкий «странный» блок (решение юзера) — проверяем только
            # наличие/отсутствие floor и roof
            rule = res["noise_settings"]["surface_rule"]
            bed = _bedrock_conditions(rule)
            assert ("floor" in bed) == (gen.world_shape != "void"), \
                "bedrock_floor должен быть ⟺ форма != void"
            assert ("roof" in bed) == (gen.world_shape == "cavern"), \
                "bedrock_roof должен быть ⟺ форма == cavern"
            # (г2) ПОЛОСЫ бедрока — рваные, как в nether.json 26.2:
            #     дно 0..(4-6) above_bottom (thick 3-5) БЕЗ обёртки,
            #     кровля (4-6)..0 below_top В обёртке minecraft:not (без
            #     неё градиент «true_at_and_below» истинен ниже якоря —
            #     бедрок залил бы весь массив под кровлей)
            bands = _bedrock_bands(rule)
            if gen.world_shape != "void":
                ta, fa, wrapped = bands["floor"]
                assert ta == {"above_bottom": 0} and len(fa) == 1 \
                    and list(fa.values())[0] in (4, 5, 6) and not wrapped, \
                    "полоса бедрока дна не 0..(4-6): %s / %s/%s" % (
                        ta, fa, wrapped)
            if gen.world_shape == "cavern":
                ta, fa, wrapped = bands["roof"]
                assert fa == {"below_top": 0} and len(ta) == 1 \
                    and list(ta.values())[0] in (4, 5, 6) and wrapped, \
                    "полоса бедрока кровли не (4-6)..0/not: %s / %s/%s" % (
                        ta, fa, wrapped)
            # --- СЫПУЧИЕ: основа мира — никогда; рельеф — по бюджету ---
            assert gen.default_block[0] not in FALLING_BLOCK_IDS, \
                "default_block сыпучий: %s" % gen.default_block[0]
            assert res["noise_settings"]["default_fluid"]["Name"] \
                not in FALLING_BLOCK_IDS, "default_fluid сыпучий"
            if gen.world_shape != "void":
                names = set()
                _collect_surface_block_names(rule, names)
                fell = names & FALLING_BLOCK_IDS
                assert len(fell) <= 2, \
                    "сыпучих в рельефе %d (> 2): %s" % (
                        len(fell), sorted(fell))
                if fell:
                    assert len(gen.stone_family) >= 3, \
                        "сыпучие при семействе < 3 блоков"
            # --- TOP-БЛОКИ биомов: уникальны (каждому биому — свой) ---
            tops = _biome_top_blocks(rule)
            assert len(tops) == len(set(tops)), \
                "top-блоки биомов повторяются: %s" % sorted(
                    set(tops) - {t for t in tops
                                 if tops.count(t) == 1})
            # --- ЦВЕТА биомов: одной роли — разные, с запасом ---
            role_cols = {}
            for bjson in gen.biomes.values():
                for key, role in (("water_color", "water"),
                                  ("grass_color", "grass"),
                                  ("foliage_color", "foliage"),
                                  ("dry_foliage_color", "dry_foliage")):
                    c = bjson["effects"].get(key)
                    if c:
                        role_cols.setdefault(role, []).append(c)
                for key, role in (("minecraft:visual/sky_color", "sky"),
                                  ("minecraft:visual/fog_color", "fog"),
                                  ("minecraft:visual/water_fog_color",
                                   "water_fog")):
                    c = (bjson.get("attributes") or {}).get(key)
                    if c:
                        role_cols.setdefault(role, []).append(c)
            for role, cols in role_cols.items():
                assert len(cols) == len(set(cols)), \
                    "%s: одинаковые цвета у биомов" % role
                if len(cols) > 1:
                    mind = min(_rgb_dist(a, b)
                               for i, a in enumerate(cols)
                               for b in cols[i + 1:])
                    assert mind >= 60.0, \
                        "%s: цвета биомов слишком близки (%.0f < 60)" % (
                            role, mind)
            # --- мобы: боссы в спавнерах — минимальная запись ---
            for bjson in gen.biomes.values():
                for entries in bjson["spawners"].values():
                    for e in entries:
                        if e["type"] in BOSS_MOBS:
                            assert e["weight"] == 1 and e["minCount"] == 1 \
                                and e["maxCount"] == 1, \
                                "босс %s не минимальная запись: %s" % (
                                    e["type"], e)
            # --- кровать ---
            attrs = res["dimension_type"].get("attributes", {})
            assert attrs.get("minecraft:gameplay/bed_rule") == {
                "can_set_spawn": "always", "can_sleep": "when_dark"}, \
                "bed_rule должен быть always/when_dark в каждом мире"
            # --- рудная система ---
            variants = gen.ore_variants
            assert 5 <= len(variants) <= 9, \
                "видов руд %d — должно быть 5-9" % len(variants)
            ore_placed_ids = set()
            top = gen.max_y - 1     # включительный верх для gen_features
            for cid, tiers in variants.items():
                assert sorted(tiers) == \
                    ["motherlode", "normal", "poor", "rich"], tiers
                counts = []
                for tier in ("poor", "normal", "rich", "motherlode"):
                    pid = tiers[tier]
                    ore_placed_ids.add(pid)
                    pl = gen.feat_placed[pid]
                    assert pl["feature"] == cid
                    cnt = [m["count"] for m in pl["placement"]
                           if m.get("type") == "minecraft:count"]
                    assert len(cnt) == 1 and 1 <= cnt[0] <= 100, cnt
                    counts.append(cnt[0])
                    hp = [m["height"] for m in pl["placement"]
                          if m.get("type") == "minecraft:height_range"]
                    assert len(hp) == 1, "у руды нет height_range"
                    lo = _resolve_anchor_y(hp[0]["min_inclusive"],
                                           gen.min_y, top)
                    hi = _resolve_anchor_y(hp[0]["max_inclusive"],
                                           gen.min_y, top)
                    assert gen.min_y <= lo <= hi <= top, \
                        "полоса руды вне мира: %s..%s (мир %s..%s)" % (
                            lo, hi, gen.min_y, top)
                assert counts[0] < counts[1] < counts[2] < counts[3], \
                    "богатство не возрастает: %s" % counts
            # в одном биоме — не более одного варианта каждой руды
            for bjson in gen.biomes.values():
                feats = {f for lst in bjson["features"] for f in lst}
                for cid in variants:
                    assert len(set(variants[cid].values()) & feats) <= 1, \
                        "два варианта руды %s в одном биоме" % cid
            # --- СИГНАТУРНЫЕ фичи: у каждого биома со своими фичами —
            #     хотя бы один вид, которого нет НИ У ОДНОГО соседа;
            #     с любым отдельным биомом — не более ОДНОГО общего вида
            #     (жалоба «не всегда могу отличить 2 биома»). Свои фичи —
            #     placed-id с префиксом <name>_b<номер биома>_ (общий пул
            #     измерения и руды — другие префиксы)
            own_by_biome = {}
            _own_pat = re.compile("^%s_b(\\d+)_" % re.escape(gen.name))
            for pid in gen.feat_placed:
                m = _own_pat.match(pid.split(":", 1)[1])
                if m:
                    cid2 = gen.feat_placed[pid]["feature"]
                    own_by_biome.setdefault(
                        int(m.group(1)), set()).add(
                        gen.feat_cfg[cid2]["type"])
            own_sets2 = [frozenset(s) for s in own_by_biome.values()]
            # СВОЙ вид не всегда возможен: при 15-20 биомах пул ~50 видов
            # исчерпывается — тогда различимость гарантирует УНИКАЛЬНОСТЬ
            # набора (попарное пересечение <= 1 ниже это обеспечивает)
            for i2, s1 in enumerate(own_sets2):
                for s2 in own_sets2[i2 + 1:]:
                    assert len(s1 & s2) <= 1, \
                        "у двух биомов 2+ общих вида фич: %s" % sorted(s1 & s2)
                    assert s1 != s2, "два биома с одинаковым набором фич"
            # --- climate-каналы: инварианты спеки (код не менялся, rng-
            #     поток до _prepare_climate тоже — каналы идентичны
            #     прежним; здесь проверяем САМИ инварианты) ---
            def _cl_df(v):
                while isinstance(v, str):    # канал мог уйти в DF-файл
                    v = gen.dfs[v]
                if isinstance(v, dict) and \
                        v.get("type") == "minecraft:flat_cache":
                    v = v.get("argument")
                return v

            router = res["noise_settings"]["noise_router"]
            for ch in ("temperature", "vegetation", "erosion", "ridges"):
                v = _cl_df(router[ch])
                assert v.get("type") == "minecraft:noise", ch
                spec = gen.noises[v["noise"]]
                assert -10 <= spec["firstOctave"] <= -7, (ch, spec)
                assert 0.10 <= v["xz_scale"] <= 0.28, (ch, v)
                assert v["y_scale"] == 0.0, (ch, v)
                _sig = 0.25 * math.sqrt(
                    sum(a * a for a in spec["amplitudes"]))
                assert 0.34 <= _sig <= 0.71, (ch, _sig)
            v = _cl_df(router["continents"])
            spec = gen.noises[v["noise"]]
            assert spec["firstOctave"] in (-9, -8, -7), spec
            _lam = (2.0 ** (-spec["firstOctave"])) / v["xz_scale"]
            assert 760.0 <= _lam <= 2600.0, _lam
            _sig = 0.25 * math.sqrt(sum(a * a for a in spec["amplitudes"]))
            assert 0.59 <= _sig <= 1.11, _sig
            # шумы рельефа (весь остальной пул): расширенный firstOctave
            # и непустой спектр (гарантия new_noise)
            for _nid, spec2 in gen.noises.items():
                assert -19 <= spec2["firstOctave"] <= 2, _nid
                assert any(spec2["amplitudes"]), _nid
            # --- каменное семейство: тиры/роли/блобы ---
            fam = gen.stone_family
            assert 3 <= len(fam) <= 7, \
                "семейство %d — должно быть 3-7" % len(fam)
            tiers = [t for _, t in fam]
            for tname, lo, hi in (("common", 1, 2), ("normal", 1, 3),
                                  ("rare", 1, 2)):
                assert lo <= tiers.count(tname) <= hi, tiers
            assert len({b[0] for b, _ in fam}) == len(fam), \
                "дубли блоков в семействе"
            assert gen.default_block[0] not in {b[0] for b, _ in fam}, \
                "default_block попал в семейство"
            # блобы: у каждого камня configured+placed, параметры по тиру
            blobs_by_state = {}
            for pid in gen._global_feats:
                pl = gen.feat_placed[pid]
                cid = pl["feature"]
                cfgj = gen.feat_cfg[cid]
                assert cid.split(":", 1)[1].split("_")[-1].startswith(
                    "stone"), cid
                assert pid.split(":", 1)[1].split("_")[-1].startswith(
                    "blob"), pid
                assert cfgj["type"] == "minecraft:ore"
                assert cfgj["config"]["size"] <= 64, cfgj
                blobs_by_state.setdefault(
                    cfgj["config"]["targets"][0]["state"]["Name"],
                    []).append(pid)
            assert set(blobs_by_state) == {b[0] for b, _ in fam}, \
                "не у всех камней семейства есть блоб"
            for blk, tier in fam:
                ok = False
                for pid in blobs_by_state[blk[0]]:
                    pl = gen.feat_placed[pid]
                    rars = [m["chance"] for m in pl["placement"]
                            if m.get("type") == "minecraft:rarity_filter"]
                    cnts = [m["count"] for m in pl["placement"]
                            if m.get("type") == "minecraft:count"]
                    if tier == "rare":
                        ok = ok or (rars and 4 <= rars[0] <= 16
                                    and cnts and 1 <= cnts[0] <= 6)
                    elif tier == "common":
                        ok = ok or (not rars and cnts
                                    and 3 <= cnts[0] <= 6)
                    else:               # normal
                        ok = ok or (not rars and cnts
                                    and 2 <= cnts[0] <= 4)
                assert ok, "блоб %s не соответствует тиру %s" % (
                    blk[0], tier)
            # блобы — в КАЖДОМ биоме (в биомных мирах)
            if gen.bs_kind in ("multi_noise", "checkerboard", "fixed"):
                for bjson in gen.biomes.values():
                    feats = {f for lst in bjson["features"] for f in lst}
                    missing = set(gen._global_feats) - feats
                    assert not missing, \
                        "биом без блобов семейства: %s" % sorted(missing)[:3]
            # полосы: 1-2 (void — нет), высокие миры — ровно 2;
            # заплатки 1-3
            if gen.world_shape == "void":
                assert gen._n_deep_bands == 0, "полосы в void-мире"
            else:
                assert 1 <= gen._n_deep_bands <= 2, gen._n_deep_bands
                if gen.height >= 256:
                    assert gen._n_deep_bands == 2, \
                        "высокий мир без двух глубинных полос"
            assert 1 <= len(gen._family_patches) <= 3, \
                len(gen._family_patches)
            # --- void-миры: НИ ОДНОГО сыпучего в рельефе ---
            if gen.world_shape == "void":
                voids += 1
                names = set()
                st = res["noise_settings"]
                names.add(st["default_block"]["Name"])
                names.add(st["default_fluid"]["Name"])
                _collect_surface_block_names(st["surface_rule"], names)
                bad = names & FALLING_BLOCK_IDS
                assert not bad, \
                    "сыпучие в рельефе void-мира: %s" % sorted(bad)
                fbad = set()
                for fjson in list(gen.feat_cfg.values()) \
                        + list(gen.feat_placed.values()):
                    gen_features._collect_state_names(fjson, fbad)
                bad2 = fbad & FALLING_BLOCK_IDS
                assert not bad2, \
                    "сыпучие в фичах void-мира: %s" % sorted(bad2)
                for bjson in gen.biomes.values():
                    for lst in bjson["features"]:
                        for f in lst:
                            assert f.split(":", 1)[1] \
                                not in VOID_UNSAFE_PLACED, f
            # --- подземные биомы ---
            bs = res["dimension"]["generator"]["biome_source"]
            qualified = (gen.height >= 128 and len(gen.biomes) >= 6
                         and gen.bs_kind == "multi_noise")
            if qualified:
                tall += 1
                # 128-255 — 2-3 биома, >= 256 — 3-6 (как в generate)
                lo_n, hi_n = ((3, 6) if gen.height >= 256 else (2, 3))
                assert lo_n <= len(gen.biome_underground) <= hi_n, \
                    "подземных биомов %d — должно быть %d-%d" \
                    % (len(gen.biome_underground), lo_n, hi_n)
                params = {e["biome"]: e["parameters"] for e in bs["biomes"]}
                ranges = []
                for bid in gen.biome_underground:
                    p = params[bid]
                    assert p["depth"] == list(gen.biome_band[bid])
                    assert p["continentalness"] == [-1.5, 1.5], \
                        "continentalness подземных не нейтрализован"
                    lo, hi = p["depth"]
                    assert CAVE_BAND_TOP <= lo < hi <= CAVE_BAND_BOTTOM, \
                        "полоса depth вне подземной зоны: %s" % p["depth"]
                    ranges.append((lo, hi))
                ranges.sort()
                for (l1, h1), (l2, _h2) in zip(ranges, ranges[1:]):
                    assert h1 < l2, "полосы depth пересекаются: %s" % ranges
                # надземные — depth ровно 0.0: подземка не заезжает
                # на поверхность и наоборот
                for bid, p in params.items():
                    if bid not in gen.biome_underground:
                        assert p["depth"] == 0.0, \
                            "надземный биом с depth %s" % p["depth"]
            else:
                flat += 1
                assert not gen.biome_underground, \
                    "подземные биомы в мире без условий (высота/число биомов/сорс)"
        assert tall >= 4 and flat >= 3 and voids >= 3, \
            "не набралось миров для проверки (tall=%d, flat=%d, voids=%d)" \
            % (tall, flat, voids)
        print("самотест миров (плотность/бедрок/мобы/кровать/руды/"
              "подземка/climate/семейство/void): OK (проверено миров: "
              "%d, высоких: %d, void: %d — во всех гарантии краёв, "
              "доля твёрдого в норме, abs под clamp, бедрок только "
              "floor/roof)" % (seed, tall, voids))
    finally:
        DATA_ROOT = old_root
        shutil.rmtree(td, ignore_errors=True)


def _self_test_presets():
    """Самотест ПРЕСЕТОВ РЕЛЬЕФА (см. TERRAIN_PRESETS — главная фича
    этого релиза, жалоба юзера: «многие миры рельефно скучные —
    огромные пустыни/почти плоские; хочу сильнее разнообразить, но не
    все миры ультра-абстрактными; может пару сотен интересных
    конфигурируемых пресетов; мир шипов — очень классно»):
    (а) достижимость: 4000 взвешенных выборок — каждый из архетипов
        встречается (минимум 10 раз); доли категорий уже проверены
        импортом (_validate_terrain_presets: интересные >= 70%,
        скучные <= 10%);
    (б) 100 мини-миров (только rand_final_density, без биомов/фич —
        быстро): все три формы мира, ДЛЯ КАЖДОГО — структурные
        гарантии плотности при нейтральных шумах (zero_noise:
        плиты дна/кровли +3.5 у open/cavern, воздух у краёв void,
        пояс cavern пуст), ни одного abs вне clamp и симуляция
        насыщения в норме; скучных среди 100 миров <= 10 (сиды
        фиксированные — проверка детерминированная); разных пресетов
        встретилось >= 25 (разнообразие, а не перекос в один)."""
    rng = random.Random(20240)
    names = [p["name"] for p in TERRAIN_PRESETS]
    counts = dict.fromkeys(names, 0)
    for _ in range(4000):
        counts[_pick_terrain_preset(rng)["name"]] += 1
    rare = sorted(k for k, v in counts.items() if v < 10)
    assert not rare, "недостижимые пресеты: %s" % rare
    cat = {p["name"]: p["cat"] for p in TERRAIN_PRESETS}
    seen = {}
    boring = 0
    for i in range(100):
        gen = DimensionGenerator(random.Random(1000 + i), "rndim",
                                 "pt%d" % i)
        gen.min_y = -64
        gen.height = 256
        gen.max_y = 192
        gen.density_band = 24
        gen.world_shape = ("open", "cavern", "void")[i % 3]
        gen.belt_lo, gen.belt_hi = 48, 80
        gen.terrain_corr = True
        gen.terr_S = 0.25
        gen.terr_clusters = [(-0.9, -0.2), (0.0, 0.1), (0.9, 0.2)]
        gen.terr_channel = gen.new_df_file({
            "type": "minecraft:flat_cache",
            "argument": gen.continents_noise_2d()})
        fd = gen.rand_final_density()
        assert gen.terrain_preset in cat, gen.terrain_preset
        seen[gen.terrain_preset] = seen.get(gen.terrain_preset, 0) + 1
        if cat[gen.terrain_preset] == "boring":
            boring += 1

        def _z(yy):
            return _sim_df(fd, 7.0, float(yy), 13.0, gen, zero_noise=True)

        Hc = gen.flat_cap_h
        if gen.world_shape == "open":
            assert _z(gen.min_y) >= 3.0 and _z(gen.min_y + Hc) >= 3.0, \
                "open: плита дна не твёрдая (%s)" % gen.terrain_preset
            assert _z(gen.max_y - 2) < 0.0, \
                "open: нет воздуха у max_y (%s)" % gen.terrain_preset
        elif gen.world_shape == "cavern":
            assert _z(gen.max_y - 2) >= 3.0 and _z(gen.max_y - Hc) >= 3.0, \
                "cavern: плита потолка не твёрдая (%s)" % gen.terrain_preset
            assert _z(gen.min_y) >= 3.0 and _z(gen.min_y + Hc) >= 3.0, \
                "cavern: плита дна не твёрдая (%s)" % gen.terrain_preset
            assert _z((gen.belt_lo + gen.belt_hi) // 2) < 0.0, \
                "cavern: нет воздуха в поясе (%s)" % gen.terrain_preset
        else:
            assert _z(gen.min_y) < 0.0 and _z(gen.max_y - 2) < 0.0, \
                "void: нет воздуха у краёв (%s)" % gen.terrain_preset
        assert not _abs_outside_clamp(fd, gen), \
            "abs вне clamp (%s)" % gen.terrain_preset
        st = _simulate_density(gen, fd)
        lo, hi = {"open": (0.20, 0.80), "cavern": (0.20, 0.84),
                  "void": (0.05, 0.50)}[gen.world_shape]
        if gen.world_shape == "void" and not (lo <= st["solid"] <= hi):
            # острова кластеруются сплайном по регионам — перепроверка
            # ШИРЕ (как в _self_test_worldgen)
            st = _simulate_density(gen, fd, cols=7)
        assert lo <= st["solid"] <= hi, \
            "плотность вне нормы: твёрдых %.0f%% (%s, %s)" % (
                st["solid"] * 100, gen.world_shape, gen.terrain_preset)
    assert boring <= 10, \
        "скучных пресетов среди 100 миров %d (> 10)" % boring
    assert len(seen) >= 25, \
        "мало разных пресетов в 100 мирах: %d" % len(seen)
    print("самотест пресетов рельефа: OK (%d архетипов; 100 мини-миров: "
          "%d разных, скучных %d%%; во всех плиты дна/кровли +3.5 "
          "твёрдые, насыщения нет)" % (len(TERRAIN_PRESETS), len(seen),
                                       boring))


def main():
    # консоль Windows по умолчанию cp1251 — «✔» и юникод в именах падают на
    # печати; переводим stdout на utf-8 с заменой непечатаемых символов
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(
        description="Генератор полностью случайных измерений (MC 26.2, pack_format 107)")
    ap.add_argument("--count", type=int, default=1, help="сколько измерений создать")
    ap.add_argument("--seed", type=int, default=None,
                    help="seed генератора (для воспроизводимости)")
    ap.add_argument("--namespace", default="rndim", help="namespace (по умолчанию rndim)")
    ap.add_argument("--name", default=None, help="имя измерения (только латиница/цифры/_)")
    ap.add_argument("--biomes", type=int, default=None,
                    help="сколько своих биомов на измерение (оверрайд "
                         "1-30; по умолчанию случайно 20-30)")
    ap.add_argument("--list", action="store_true", help="показать созданные измерения")
    ap.add_argument("--check", action="store_true",
                    help="проверить целостность сгенерированных данных")
    ap.add_argument("--print", action="store_true", help="не записывать, только вывести JSON")
    ap.add_argument("--selftest", action="store_true",
                    help="самотест: спавн-теги + миры (гарантии "
                         "плотности/симуляция насыщения, плоские капы "
                         "дна/кровли, бедрок, мобы, руды, подземка...) "
                         "+ пресеты рельефа (достижимость/распределение/"
                         "плотности; генерация во временный каталог, "
                         "основной пак не трогается)")
    ap.add_argument("--regen", action="store_true",
                    help="УДАЛИТЬ все сгенерированные данные namespace")
    args = ap.parse_args()

    ns = re.sub(r"[^a-z0-9_.\-]", "", args.namespace.lower()) or "rndim"

    if args.selftest:
        _self_test()
        _self_test_worldgen()
        _self_test_presets()
        return

    if args.regen:
        target = DATA_ROOT / ns
        if target.exists():
            shutil.rmtree(target)
            print("Удалено: %s" % target)
        else:
            print("Нечего удалять: %s" % target)
        # спавн-теги лежат в data/minecraft и общие на весь пак — их
        # судьба при полной очистке зависит от оставшихся namespace'ов
        print("Спавн-теги: %s" % regen_spawnable_tags())
        return

    if args.check:
        check_dimensions(ns)
        return

    if args.list:
        dims = list_dimensions(ns)
        if not dims:
            print("Измерений пока нет. Запусти без аргументов, чтобы создать первое.")
        for type_id, info in dims:
            extra = " ".join("%s=%s" % kv for kv in info.items())
            print("  %s  %s" % (type_id, extra))
        return

    count = max(1, min(args.count, 64))
    if args.name and count > 1:
        count = 1  # имя задано — только одно измерение

    existing = {p for p in glob.glob(str(DATA_ROOT / ns / "dimension" / "*.json"))}
    created = []
    prev_dim = None   # ЦЕПОЧКА достижений: предыдущее измерение (или None)
    for i in range(count):
        seed = args.seed if (args.seed is not None and count == 1) else random.SystemRandom().randrange(1 << 30)
        rng = random.Random(seed)
        name = args.name and re.sub(r"[^a-z0-9_]", "", args.name.lower()) or None
        if not name:
            while True:
                name = random_name(rng)
                if str(DATA_ROOT / ns / "dimension" / ("%s.json" % name)) not in existing:
                    break
        gen = DimensionGenerator(rng, ns, name)
        if not args.print:
            # перегенерация с существующим именем: убрать старые файлы ДО
            # генерации — генератор достижений читает дерево ачивок с диска
            # (при удалении последнего измерения уходит и корень дерева,
            # и новый результат обязан знать об этом)
            if (DATA_ROOT / ns / "dimension" / ("%s.json" % name)).exists():
                n = cleanup_dimension(ns, name)
                if n:
                    print("   очищено старых файлов: %d" % n)
            # цепочка достижений: prev = хвост цепочки с диска ПОСЛЕ
            # очистки (перегенерация середины осиротивает ветку ниже —
            # хвост вычисляется по досягаемым от root узлам, всё честно)
            prev_dim = gen_advancements.chain_tail(DATA_ROOT, ns)
        result = gen.generate(
            biome_count=None if args.biomes is None
            else max(1, min(args.biomes, 30)),
            prev_dim=prev_dim)
        created.append((seed, result))
        if not args.print:
            files = write_dimension(ns, result)
            existing |= {str(p) for p in files}
        else:
            print(dump_json(result["dimension"]))
            print(dump_json(result["dimension_type"]))
            print(dump_json(result["noise_settings"]))
            for bid, bjson in result["biomes"].items():
                print(dump_json({bid: bjson}))
            for nid, spec in result["noises"].items():
                print(nid, dump_json(spec))
        # следующее измерение цепляется за это (в --print диск не пишется —
        # цепочка ведётся в памяти)
        prev_dim = name

    for seed, result in created:
        s = result["summary"]
        print()
        print("✔ Создано измерение: %s   (seed=%d)" % (s["id"], seed))
        print("   границы: %d .. %d (высота %d), %s, рельеф: %s" % (
            s["min_y"], s["min_y"] + s["height"], s["height"],
            "с потолком" if s["has_ceiling"] else "без потолка",
            s.get("terrain_preset") or "?"))
        print("   основа: %s, жидкость: %s, море: %s" % (
            s["default_block"].split(":")[1], s["default_fluid"].split(":")[1],
            "нет" if s["sea_level"] < s["min_y"] else "уровень %d" % s["sea_level"]))
        print("   биомы: %s (своих: %d, подземных: %d%s), руд: %d видов, "
              "шумов: %d, density_function файлов: %d" % (
                  s["biome_source"].split(":")[1], s["biomes"],
                  s.get("underground_biomes", 0),
                  ", пер-биомный рельеф" if s.get("terrain_corr") else "",
                  s.get("ores", 0), s["noises"], s["dfs"]))
        print("   каменное семейство: %d блоков (блобы: %d, полосы: %d, "
              "заплатки: %d%s)" % (
                  s.get("stone_family", 0), s.get("stone_blobs", 0),
                  s.get("stone_bands", 0), s.get("stone_patches", 0),
                  ", жила-стержень" if s.get("stone_vein") else ""))
        if s.get("custom_time"):
            print("   время: своё (шкал: %d), длина суток/цикла своя" % s["timelines"])
        print("   фич: %d, карверов: %d, структур: %d (nbt-шаблонов: %d), "
              "таблиц лута: %d, trial_spawner конфигов: %d" % (
                  s["features"], s["carvers"], s["structures"],
                  s.get("nbt_templates", 0), s.get("loot_tables", 0),
                  s.get("trial_spawners", 0)))
        if (s.get("enchantments") or s.get("predicates")
                or s.get("item_modifiers") or s.get("ench_functions")):
            print("   зачарований: %d, predicates: %d, item_modifiers: %d, "
                  "функций зачарований: %d"
                  % (s.get("enchantments", 0), s.get("predicates", 0),
                     s.get("item_modifiers", 0), s.get("ench_functions", 0)))
        if s.get("adv_trigger"):
            parent = s.get("adv_parent") or ""
            parent_short = "корень" if parent.endswith("/root") else (
                parent.split("/", 1)[1] if "/" in parent else "?")
            print("   достижение: %s:adv/%s (в дереве: после %s; "
                  "путь из %s шагов; триггеры: %s — «%s»)"
                  % (ns, s["id"].split(":", 1)[1], parent_short,
                     s.get("adv_steps"), s["adv_trigger"],
                     s.get("adv_hint", "")))
            if s.get("adv_step_titles"):
                print("   шаги: %s" % "; ".join(s["adv_step_titles"]))
            if s.get("adv_expansions"):
                print("   !! пулы расширены до ванильных (в prev-мире пусто):"
                      " %s" % ", ".join(s["adv_expansions"]))
        print("   зайти:  /execute in %s run tp @s 0 %d 0" % (s["id"], s["spawn_y"]))
    if created and not args.print:
        print()
        print("Спавн-теги: поверхностные блоки всех измерений дописаны в 13"
              " ванильных тегов (data/minecraft/tags/block/) — животные"
              " спавнятся на любых поверхностях")
        print("Готово. В игре: /reload  (если измерение не появилось — перезайди в мир).")


if __name__ == "__main__":
    main()
