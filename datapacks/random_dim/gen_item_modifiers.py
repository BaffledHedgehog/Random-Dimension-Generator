#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_item_modifiers.py - генератор случайных item_modifiers для Minecraft 26.2
(data format 107; каталог data/<ns>/item_modifier/ - единственное число;
в имени файла ТОЛЬКО basename, id хранится в возвращаемом dict).

ФОРМАТ КОРНЯ ФАЙЛА (сверено байткодом jar 26.2):
  LootDataType.MODIFIER = new LootDataType<>(Registries.ITEM_MODIFIER,
      LootItemFunctions.ROOT_CODEC...) - root = ОДИН объект функции
  {"function": "...", ...} ИЛИ ГОЛЫЙ МАССИВ функций [f, f, ...]
  (SequenceFunction.INLINE_CODEC через withAlternative; обёртки
  {"functions": [...} на корне НЕТ - это поле типа minecraft:sequence).
  Как и predicates, модификаторы парсятся ЛЕНИВО: ошибки не видны при
  старте сервера; тест - /item modify entity <цель> <слот> <ns>:<id>.

  44 типа loot_function 26.2 (реестр LootItemFunctions.bootstrap,
  диспетчеризация по ключу "function"; НИЖЕ каждый помечен
  [bytecode] = поля сверены javap):
    set_count{count,add}[bytecode], set_item{item}[bytecode],
    set_lore{lore,mode,entity}[bytecode - mode ОБЯЗАТЕЛЕН и ВЫПРЯМЛЕН:
    ListOperation-СТРОКА «mode»: replace_all|replace_section|insert|
    append (+соседние int-поля offset/size), НЕ вложенный объект],
    enchant_randomly{options,only_compatible,
    include_additional_cost_component}[bytecode],
    enchant_with_levels{levels,options,
    include_additional_cost_component}[bytecode],
    set_enchantments{enchantments,add}, set_damage{damage,add},
    set_attributes{modifiers,replace} - записи {id, attribute, amount
    (NumberProvider), operation, slot} - ключ «attribute», НЕ «type»
    (кодек функции отличается от кодека компонента!),
    furnace_smelt,
    enchanted_count_increase{count,enchantment,limit}[bytecode],
    apply_bonus{enchantment,formula,parameters}[bytecode],
    limit_count{limit}, set_potion{id}, set_stew_effect{effects}[bytecode],
    set_custom_data{tag}[bytecode], set_components{components},
    copy_name{source}[bytecode - LootContextArg.ENTITY_OR_BLOCK:
    "this"|"attacker"|"direct_attacker"|"attacking_player"|
    "target_entity"|"block_entity"], copy_state{block,properties},
    copy_components{source,include,exclude}[bytecode],
    set_loot_table{name,seed,type} (класс SetContainerLootTable)[bytecode],
    set_contents{entries,component} (класс SetContainerContents)[bytecode],
    modify_contents{component,modifier} (класс
    ModifyContainerContents)[bytecode], filtered{item_filter,on_pass,
    on_fail}[bytecode], reference{name}[bytecode - FunctionReference],
    sequence{functions}, set_banner_pattern{patterns,append}[bytecode],
    set_random_dyes{number_of_dyes}[bytecode],
    set_random_potion{options}, set_instrument{options}[bytecode],
    set_fireworks{explosions,flight_duration}[bytecode - explosions =
    ListOperation$StandAlone {"values":[FireworkExplosion-компоненты
    БЕЗ ключа «function»], "mode":...} - НЕ голый массив;
    flight_duration = int 0..255],
    set_firework_explosion{shape,colors,fade_colors,has_trail,has_twinkle},
    set_book_cover{title,author,generation}[bytecode],
    set_written_book_pages{pages,mode}[bytecode - mode ОБЯЗАТЕЛЕН и
    ВЫПРЯМЛЕН (ListOperation-строка)],
    set_writable_book_pages{pages,mode}[bytecode - то же], toggle_tooltips
    {toggles} [bytecode], set_custom_model_data{colors,flags,floats,
    strings}[bytecode - КАЖДОЕ поле = ListOperation$StandAlone
    {"values":[...], "mode":...}, НЕ голый массив], set_ominous_bottle_amplifier{amplifier}[bytecode],
    exploration_map{destination,decoration,zoom,search_radius,
    skip_existing_chunks}[bytecode], fill_player_head{entity}[bytecode],
    discard, function.
  У КАЖДОЙ функции есть общее опциональное поле "conditions" (список
  loot-условий; gen_loot.py это уже проверял на сервере).

  МОСТИК ПОДТВЕРЖДЁН: функция
      {"function": "minecraft:reference", "name": "<ns>:<id>"}
  (FunctionReference.class - ResourceKey над Registries.ITEM_MODIFIER,
  поле "name") ссылается на другой модификатор. Модификаторы из
  лут-таблиц (поле "functions" записи) и /item modify видят ОДИН реестр.

  apply_bonus formulas (ApplyBonusCount, [bytecode]):
    {"formula":"minecraft:ore_drops","parameters":{}},
    {"formula":"minecraft:uniform_bonus_count",
     "parameters":{"bonusMultiplier":float}},
    {"formula":"minecraft:binomial_with_bonus_count",
     "parameters":{"extra":int,"probability":float}}.

  Реестры-справочники (из data/ в jar 26.2): banner_pattern - base,
  border, bricks, circle, creeper, cross, curly_border, diagonal_left,
  diagonal_right, diagonal_up_left, diagonal_up_right, flow, flower,
  globe, gradient, gradient_up, guster, half_horizontal,
  half_horizontal_bottom, half_vertical, half_vertical_right, mojang,
  piglin, rhombus, skull, small_stripes, square_bottom_left,
  square_bottom_right, square_top_left, square_top_right,
  straight_cross, stripe_* (bottom/center/downleft/downright/left/
  middle/right/top), triangle_bottom, triangle_top, triangles_bottom,
  triangles_top; instrument - admire/call/dream/feel/ponder/seek/
  sing/yearn_goat_horn; map_decoration (MapDecorationTypes) - player,
  frame, red_marker, blue_marker, target_x, target_point,
  player_off_map, player_off_limits, mansion, monument, banner_<16
  цветов>, red_x, village_desert/plains/savanna/snowy/taiga,
  jungle_temple, swamp_hut, trial_chambers; теги структур для
  exploration_map.destination - on_treasure_maps,
  on_woodland_explorer_maps, eye_of_ender_located, village,
  mineshaft, ocean_ruin, ruined_portal, shipwreck, on_*_maps...

«ПЕРСОНАЖИ»: каждый модификатор = характер с согласованным набором
1-6 функций и тематическим базовым предметом:
  оружейник, бронник, алхимик, чародей, проклинатель, портной,
  писец, пиротехник, картограф, падальщик, витринщик, кузнец,
  трюкач, мистик, даритель, охотник за головами.

ЕДИНСТВЕННАЯ публичная функция:

    rand_item_modifiers(rng, ns, name, count=None)
        -> {"item_modifiers": {id: json}}

    rng    - random.Random (весь рандом только через него);
    ns     - namespace ('rndim');
    name   - имя измерения (id: <ns>:<name>_modN);
    count  - сколько модификаторов создать (None -> тяжёлый хвост:
             в среднем ~2, выбросы до 15).

Константы и помощники переиспользуются из gen_loot.py (серверно
проверенного соседа): ENCHANTS, ATTRIBUTES, _WILD_SLOTS, ALL_ITEMS,
_num_provider, _weighted, _enchantments_map, _attribute_modifiers,
rand_name, _hex_color, _firework_explosion, _book_pages,
POTIONS_IDS, MOB_EFFECTS, VANILLA_TABLES, BLOCK_STATE_PROPS...
Модуль НИЧЕГО не пишет на диск - возвращает dict.
"""

import math

import gen_loot as gl  # соседний серверно-проверенный генератор


# ---------------------------------------------------------------------------
# Справочники, отсутствующие в gen_loot.py (id из jar 26.2)
# ---------------------------------------------------------------------------

# типы banner_pattern (data/minecraft/banner_pattern/ в jar)
_BANNER_PATTERNS = ["base", "border", "bricks", "circle", "creeper",
                    "cross", "curly_border", "diagonal_left",
                    "diagonal_right", "diagonal_up_left",
                    "diagonal_up_right", "flow", "flower", "globe",
                    "gradient", "gradient_up", "guster",
                    "half_horizontal", "half_horizontal_bottom",
                    "half_vertical", "half_vertical_right", "mojang",
                    "piglin", "rhombus", "skull", "small_stripes",
                    "square_bottom_left", "square_bottom_right",
                    "square_top_left", "square_top_right",
                    "straight_cross", "stripe_bottom", "stripe_center",
                    "stripe_downleft", "stripe_downright",
                    "stripe_left", "stripe_middle", "stripe_right",
                    "stripe_top", "triangle_bottom", "triangle_top",
                    "triangles_bottom", "triangles_top"]

# инструменты (реестр instrument в jar)
_INSTRUMENTS = ["minecraft:admire_goat_horn", "minecraft:call_goat_horn",
                "minecraft:dream_goat_horn", "minecraft:feel_goat_horn",
                "minecraft:ponder_goat_horn", "minecraft:seek_goat_horn",
                "minecraft:sing_goat_horn", "minecraft:yearn_goat_horn"]

# типы map_decoration (MapDecorationTypes, javap)
_MAP_DECORATIONS = ["player", "frame", "red_marker", "blue_marker",
                    "target_x", "target_point", "player_off_map",
                    "player_off_limits", "mansion", "monument",
                    "banner_white", "banner_red", "banner_black",
                    "red_x", "village_desert", "village_plains",
                    "village_savanna", "village_snowy", "village_taiga",
                    "jungle_temple", "swamp_hut", "trial_chambers"]

# теги структур для exploration_map.destination (tags/worldgen/structure/)
_STRUCTURE_TAGS = ["minecraft:on_treasure_maps",
                   "minecraft:on_woodland_explorer_maps",
                   "minecraft:on_ocean_explorer_maps",
                   "minecraft:on_jungle_explorer_maps",
                   "minecraft:on_trial_chambers_maps",
                   "minecraft:eye_of_ender_located", "minecraft:village",
                   "minecraft:mineshaft", "minecraft:ocean_ruin",
                   "minecraft:ruined_portal", "minecraft:shipwreck"]

# компоненты для toggle_tooltips / copy_components include/exclude
_TOOLTIP_COMPONENTS = ["minecraft:custom_name", "minecraft:enchantments",
                       "minecraft:stored_enchantments", "minecraft:lore",
                       "minecraft:attribute_modifiers", "minecraft:trim",
                       "minecraft:dyed_color", "minecraft:unbreakable"]

# контейнеры для set_contents / modify_contents
_CONTAINER_COMPONENTS = ["minecraft:container", "minecraft:bundle_contents"]

# базовые предметы по характерам
_WEAPONS = gl.SWORDS + gl.SPEARS + gl.AXES + gl.MACES + gl.TRIDENTS \
    + gl.BOWS + gl.CROSSBOWS
_ARMOR = gl._HELMETS + gl._CHESTPLATES + gl._LEGGINGS + gl._BOOTS \
    + gl.ELYTRA + gl.SHIELDS


# ---------------------------------------------------------------------------
# Мелкие помощники
# ---------------------------------------------------------------------------

def _frac_provider(rng, lo=0.0, hi=1.0):
    """NumberProvider долей (для set_damage)."""
    if rng.random() < 0.6:
        return round(rng.uniform(lo, hi), 3)
    # A quantity NumberProvider, not a continuous predicate or FloatProvider.
    # Keep both draws (and valid equal endpoints), but never cross the bounds.
    a, b = sorted((round(rng.uniform(lo, hi), 3),
                   round(rng.uniform(lo, hi), 3)))
    return {"type": "minecraft:uniform", "min": a, "max": b}


def _maybe_conditions(rng, f):
    """Изредка вешаем на функцию БЕЗОПАСНОЕ условие (без параметров
    контекста - /item modify строит COMMAND-контекст с ORIGIN и,
    для entity-цели, THIS_ENTITY)."""
    if rng.random() < 0.07:
        c = {"condition": "minecraft:random_chance",
             "chance": round(rng.uniform(0.3, 0.9), 3)}
        f["conditions"] = [c]
    return f


def _modifier_count(rng):
    """Тяжёлый хвост: в среднем ~2, выбросы до 15."""
    r = rng.random()
    if r < 0.70:
        return rng.randint(1, 2)
    if r < 0.94:
        return rng.randint(1, 4)
    return int(round(math.exp(rng.uniform(math.log(5), math.log(15)))))


# ---------------------------------------------------------------------------
# Строители функций (каждая возвращает dict с ключом "function")
# ---------------------------------------------------------------------------

def _list_op(rng, with_offset=False):
    """ListOperation 26.2, ВЫПРЯМЛЕННЫЙ в поля родителя (javap: кодек
    входит в group БЕЗ fieldOf): «mode» - СТРОКА на верхнем уровне
    (replace_all | replace_section | insert | append), «offset»/«size» -
    её соседи. НЕ вложенный объект!"""
    r = rng.random()
    if r < 0.55 or not with_offset:
        return {"mode": "replace_all"}
    if r < 0.80:
        return {"mode": "insert", "offset": rng.randint(0, 2)}
    if r < 0.92:
        return {"mode": "replace_section", "offset": rng.randint(0, 2)}
    return {"mode": "append"}


def _f_set_count(rng, item, env):
    f = {"function": "minecraft:set_count",
         "count": gl._num_provider(rng, 1, 5)}
    if rng.random() < 0.5:
        f["add"] = rng.random() < 0.6
    return f


def _f_set_item(rng, item, env):
    return {"function": "minecraft:set_item",
            "item": rng.choice(gl.ALL_ITEMS)}


def _f_set_name(rng, item, env):
    f = {"function": "minecraft:set_name",
         "name": gl.rand_name(rng, item),
         "target": rng.choice(["custom_name", "item_name"])}
    return f


def _f_set_lore(rng, item, env):
    lines = [{"text": rng.choice(gl._LORE_LINES),
              "color": rng.choice(["gray", "dark_gray", "blue",
                                   "dark_aqua", "dark_purple"]),
              "italic": True}
             for _ in range(rng.randint(1, 3))]
    # mode ОБЯЗАТЕЛЕН и ВЫПРЯМЛЕН (ListOperation как строка «mode»)
    f = {"function": "minecraft:set_lore", "lore": lines}
    f.update(_list_op(rng, with_offset=True))
    return f


def _f_set_enchantments(rng, item, env):
    emap = gl._enchantments_map(rng, item)
    if not emap:  # предмет «не поддаётся» - принудительно дикая карта
        emap = {"minecraft:" + rng.choice(list(gl.ENCHANTS)): 1}
    f = {"function": "minecraft:set_enchantments",
         "enchantments": {k: float(v) for k, v in emap.items()}}
    if rng.random() < 0.3:
        f["add"] = rng.random() < 0.7
    return f


def _f_enchant_randomly(rng, item, env):
    f = {"function": "minecraft:enchant_randomly",
         "only_compatible": rng.random() < 0.7}
    if rng.random() < 0.5:
        opts = rng.sample(list(gl.ENCHANTS), rng.randint(2, 5))
        f["options"] = ["minecraft:" + e for e in opts]
    return f


def _f_enchant_with_levels(rng, item, env):
    f = {"function": "minecraft:enchant_with_levels",
         "levels": gl._num_provider(rng, 5, 30)}
    if rng.random() < 0.3:
        opts = rng.sample(list(gl.ENCHANTS), rng.randint(2, 4))
        f["options"] = ["minecraft:" + e for e in opts]
    return f


def _f_enchanted_count_increase(rng, item, env):
    f = {"function": "minecraft:enchanted_count_increase",
         "count": gl._num_provider(rng, 1, 3),
         "enchantment": "minecraft:" + rng.choice(list(gl.ENCHANTS))}
    if rng.random() < 0.6:
        f["limit"] = rng.randint(2, 16)
    return f


def _f_apply_bonus(rng, item, env):
    t = gl._weighted(rng, [("ore_drops", 30), ("uniform_bonus_count", 40),
                           ("binomial_with_bonus_count", 30)])
    if t == "ore_drops":
        params = {}
    elif t == "uniform_bonus_count":
        params = {"bonusMultiplier": round(rng.uniform(0.5, 2.0), 2)}
    else:
        params = {"extra": rng.randint(1, 5),
                  "probability": round(rng.uniform(0.2, 0.8), 3)}
    return {"function": "minecraft:apply_bonus",
            "enchantment": "minecraft:" + rng.choice(list(gl.ENCHANTS)),
            "formula": "minecraft:" + t,
            "parameters": params}


def _f_set_attributes(rng, item, env):
    # записи модификаторов: ключ «attribute» (НЕ «type» - это кодек
    # set_attributes-ФУНКЦИИ, он отличается от кодека компонента!)
    mods = []
    for m in gl._attribute_modifiers(rng, item, env["tag_prefix"]):
        m2 = {"attribute": m["type"], "id": m["id"],
              "amount": m["amount"], "operation": m["operation"]}
        if "slot" in m:
            m2["slot"] = m["slot"]
        mods.append(m2)
    return {"function": "minecraft:set_attributes",
            "modifiers": mods,
            "replace": rng.random() < 0.75}


def _f_set_damage(rng, item, env):
    f = {"function": "minecraft:set_damage",
         "damage": _frac_provider(rng)}
    if rng.random() < 0.4:
        f["add"] = rng.random() < 0.6
    return f


def _f_furnace_smelt(rng, item, env):
    return _maybe_conditions(rng,
                             {"function": "minecraft:furnace_smelt"})


def _f_set_potion(rng, item, env):
    return {"function": "minecraft:set_potion",
            "id": "minecraft:" + rng.choice(gl.POTIONS_IDS)}


def _f_set_stew_effect(rng, item, env):
    effects = [{"type": "minecraft:" + rng.choice(gl.MOB_EFFECTS),
                "duration": rng.randint(40, 400)}
               for _ in range(rng.randint(1, 2))]
    return {"function": "minecraft:set_stew_effect", "effects": effects}


def _f_set_custom_data(rng, item, env):
    tag = {"forged_by": rng.choice(gl._RU_AUTHORS),
           "serial": rng.randint(0, 9999)}
    if rng.random() < 0.3:
        tag["Tags"] = [rng.choice(["marked", "crafted", "blessed"])]
    return {"function": "minecraft:set_custom_data", "tag": tag}


def _f_set_components(rng, item, env):
    comps = {}
    if rng.random() < 0.5:
        comps["minecraft:rarity"] = gl._rarity(rng)
    if rng.random() < 0.35 and gl._leather(item):
        comps["minecraft:dyed_color"] = int(gl._hex_color(rng)[1:], 16)
    if rng.random() < 0.25:
        comps["minecraft:enchantment_glint_override"] = rng.random() < 0.8
    if rng.random() < 0.20:
        comps["minecraft:unbreakable"] = {}
    if rng.random() < 0.15:
        comps["minecraft:max_stack_size"] = rng.randint(1, 16)
    if rng.random() < 0.12:
        comps["minecraft:custom_model_data"] = {
            "floats": [round(rng.uniform(0.0, 9.9), 2)],
            "flags": [rng.random() < 0.5],
            "strings": [rng.choice(["a", "tier", "variant"])],
            "colors": [int(gl._hex_color(rng)[1:], 16)]}
    return {"function": "minecraft:set_components", "components": comps}


def _f_copy_state(rng, item, env):
    block, props = rng.choice(list(gl.BLOCK_STATE_PROPS.items()))
    return {"function": "minecraft:copy_state", "block": block,
            "properties": list(props)[:rng.randint(1, len(props))]}


def _f_copy_name(rng, item, env):
    return {"function": "minecraft:copy_name",
            # LootContextArg.ENTITY_OR_BLOCK (javap): все цели сущностей
            # + "block_entity"
            "source": rng.choice(["this", "block_entity", "this"])}


def _f_copy_components(rng, item, env):
    f = {"function": "minecraft:copy_components",
         "source": "block_entity"}
    if rng.random() < 0.6:
        f["include"] = rng.sample(_TOOLTIP_COMPONENTS,
                                  rng.randint(1, 2))
    else:
        f["exclude"] = rng.sample(_TOOLTIP_COMPONENTS,
                                  rng.randint(1, 2))
    return f


def _f_set_loot_table(rng, item, env):
    f = {"function": "minecraft:set_loot_table",
         "name": rng.choice(gl.VANILLA_TABLES),
         "type": "minecraft:chest"}
    if rng.random() < 0.3:
        f["seed"] = rng.randint(0, 2 ** 31 - 1)
    return f


def _f_set_contents(rng, item, env):
    entries = [{"type": "minecraft:item",
                "name": rng.choice(gl.ALL_ITEMS)}
               for _ in range(rng.randint(1, 3))]
    return {"function": "minecraft:set_contents",
            "component": "minecraft:container",
            "entries": entries}


def _f_modify_contents(rng, item, env):
    inner = gl._weighted(rng, [
        (lambda: {"function": "minecraft:set_count",
                  "count": gl._num_provider(rng, 1, 3), "add": True}, 50),
        (lambda: {"function": "minecraft:set_name",
                  "name": gl.rand_name(rng, item),
                  "target": "custom_name"}, 25),
        (lambda: {"function": "minecraft:limit_count",
                  "limit": {"min": 1, "max": rng.randint(4, 32)}}, 25)])
    return {"function": "minecraft:modify_contents",
            "component": rng.choice(_CONTAINER_COMPONENTS),
            "modifier": inner()}


def _f_filtered(rng, item, env):
    tag = rng.choice(["#minecraft:swords", "#minecraft:pickaxes",
                      "#minecraft:planks", "#minecraft:wool"])
    if_pass = {"function": "minecraft:set_name",
               "name": gl.rand_name(rng, item),
               "target": "custom_name"}
    if_fail = {"function": "minecraft:set_count",
               "count": float(rng.randint(2, 5)), "add": True}
    return {"function": "minecraft:filtered",
            "item_filter": {"items": tag},
            "on_pass": if_pass, "on_fail": if_fail}


def _f_limit_count(rng, item, env):
    lim = {}
    if rng.random() < 0.7:
        lim["min"] = rng.randint(1, 4)
    lim["max"] = rng.randint(4, 32)
    return {"function": "minecraft:limit_count", "limit": lim}


def _f_reference(rng, item, env):
    if not env["prior"]:
        # ссылаться не на что (первый модификатор) - fallback, чтобы
        # НЕ создать ссылку на самого себя (бесконечная рекурсия)
        return _f_set_custom_data(rng, item, env)
    return {"function": "minecraft:reference",
            "name": rng.choice(env["prior"])}


def _f_sequence(rng, item, env):
    return {"function": "minecraft:sequence",
            "functions": [_f_set_count(rng, item, env),
                          _f_set_custom_data(rng, item, env)]}


def _f_set_banner_pattern(rng, item, env):
    patterns = [{"pattern": "minecraft:" + rng.choice(_BANNER_PATTERNS),
                 "color": rng.choice(gl.DYE_COLORS)}
                for _ in range(rng.randint(1, 3))]
    # append ОБЯЗАТЕЛЕН (javap: fieldOf, не optionalFieldOf)
    return {"function": "minecraft:set_banner_pattern",
            "patterns": patterns,
            "append": rng.random() < 0.6}


def _f_set_random_dyes(rng, item, env):
    f = {"function": "minecraft:set_random_dyes",
         "number_of_dyes": rng.randint(1, 3)}
    return f


def _f_set_random_potion(rng, item, env):
    opts = rng.sample(gl.POTIONS_IDS, rng.randint(2, 5))
    return {"function": "minecraft:set_random_potion",
            "options": ["minecraft:" + p for p in opts]}


def _f_set_instrument(rng, item, env):
    return {"function": "minecraft:set_instrument",
            "options": rng.sample(_INSTRUMENTS, rng.randint(1, 3))}


def _f_set_fireworks(rng, item, env):
    # explosions = ListOperation$StandAlone: {"values":[...], "mode":...}
    # (javap) - НЕ голый массив! Элементы - FireworkExplosion-КОМПОНЕНТЫ
    # (без ключа «function»); flight_duration - unsigned byte (int 0-255)
    explosions = [{"shape": rng.choice(["small_ball", "large_ball",
                                        "star", "creeper", "burst"]),
                   "colors": [rng.randint(0, 0xFFFFFF)
                              for _ in range(rng.randint(1, 3))],
                   "has_trail": rng.random() < 0.4,
                   "has_twinkle": rng.random() < 0.4}
                  for _ in range(rng.randint(1, 3))]
    op = _list_op(rng, with_offset=True)
    op["values"] = explosions
    return {"function": "minecraft:set_fireworks",
            "flight_duration": rng.randint(1, 3),
            "explosions": op}


def _f_set_firework_explosion(rng, item, env):
    f = {"function": "minecraft:set_firework_explosion",
         "shape": rng.choice(["small_ball", "large_ball", "star",
                              "creeper", "burst"]),
         "colors": [rng.randint(0, 0xFFFFFF)
                    for _ in range(rng.randint(1, 3))]}
    if rng.random() < 0.4:
        f["fade_colors"] = [rng.randint(0, 0xFFFFFF)]
    if rng.random() < 0.4:
        f["has_trail"] = rng.random() < 0.5
    if rng.random() < 0.4:
        f["has_twinkle"] = rng.random() < 0.5
    return f


def _f_set_book_cover(rng, item, env):
    return {"function": "minecraft:set_book_cover",
            "title": rng.choice(gl._BOOK_TITLES),
            "author": rng.choice(gl._RU_AUTHORS),
            "generation": rng.randint(0, 3)}


def _f_set_written_book_pages(rng, item, env):
    # mode ОБЯЗАТЕЛЕН и ВЫПРЯМЛЕН (ListOperation-строка «mode»)
    f = {"function": "minecraft:set_written_book_pages",
         "pages": gl._book_pages(rng, rng.randint(2, 5), True)}
    f.update(_list_op(rng))
    return f


def _f_set_writable_book_pages(rng, item, env):
    f = {"function": "minecraft:set_writable_book_pages",
         "pages": gl._book_pages(rng, rng.randint(2, 5), False)}
    f.update(_list_op(rng))
    return f


def _f_toggle_tooltips(rng, item, env):
    keys = rng.sample(_TOOLTIP_COMPONENTS, rng.randint(1, 3))
    return {"function": "minecraft:toggle_tooltips",
            "toggles": {k: rng.random() < 0.5 for k in keys}}


def _f_set_custom_model_data(rng, item, env):
    # floats/flags/strings/colors - КАЖДЫЙ = ListOperation$StandAlone
    # {"values":[...], "mode":...} (javap) - НЕ голый массив;
    # значения floats - NumberProvider (обычные числа тоже можно)
    f = {"function": "minecraft:set_custom_model_data"}
    if rng.random() < 0.6:
        op = _list_op(rng)
        op["values"] = [round(rng.uniform(0.0, 9.9), 2)]
        f["floats"] = op
    if rng.random() < 0.5:
        op = _list_op(rng)
        op["values"] = [rng.random() < 0.5]
        f["flags"] = op
    if rng.random() < 0.5:
        op = _list_op(rng)
        op["values"] = [rng.choice(["a", "tier", "variant", "skin"])]
        f["strings"] = op
    if rng.random() < 0.4:
        op = _list_op(rng)
        op["values"] = [int(gl._hex_color(rng)[1:], 16)]
        f["colors"] = op
    return f


def _f_set_ominous(rng, item, env):
    return {"function": "minecraft:set_ominous_bottle_amplifier",
            "amplifier": rng.randint(0, 4)}


def _f_exploration_map(rng, item, env):
    f = {"function": "minecraft:exploration_map",
         "destination": rng.choice(_STRUCTURE_TAGS),
         "decoration": rng.choice(_MAP_DECORATIONS)}
    if rng.random() < 0.6:
        f["zoom"] = rng.randint(1, 4)
    if rng.random() < 0.5:
        f["search_radius"] = rng.randint(50, 256)
    if rng.random() < 0.3:
        f["skip_existing_chunks"] = rng.random() < 0.5
    return f


def _f_fill_player_head(rng, item, env):
    return {"function": "minecraft:fill_player_head",
            "entity": rng.choice(["this", "attacking_player"])}


def _f_discard(rng, item, env):
    return _maybe_conditions(rng, {"function": "minecraft:discard"})


# полный каталог строителей (для «дикого тира»)
_ALL_BUILDERS = [
    _f_set_count, _f_set_item, _f_set_name, _f_set_lore,
    _f_set_enchantments, _f_enchant_randomly, _f_enchant_with_levels,
    _f_enchanted_count_increase, _f_apply_bonus, _f_set_attributes,
    _f_set_damage, _f_furnace_smelt, _f_set_potion, _f_set_stew_effect,
    _f_set_custom_data, _f_set_components, _f_copy_state, _f_copy_name,
    _f_copy_components, _f_set_loot_table, _f_set_contents,
    _f_modify_contents, _f_filtered, _f_limit_count, _f_reference,
    _f_sequence, _f_set_banner_pattern, _f_set_random_dyes,
    _f_set_random_potion, _f_set_instrument, _f_set_fireworks,
    _f_set_firework_explosion, _f_set_book_cover,
    _f_set_written_book_pages, _f_set_writable_book_pages,
    _f_toggle_tooltips, _f_set_custom_model_data, _f_set_ominous,
    _f_exploration_map, _f_fill_player_head, _f_discard,
]


# ---------------------------------------------------------------------------
# «Персонажи»: тематические пулы (предметы x функции)
# ---------------------------------------------------------------------------

_CHARACTERS = {
    "weapon_smith": (  # Оружейник
        _WEAPONS,
        [(_f_set_name, 20), (_f_set_enchantments, 25),
         (_f_enchant_randomly, 15), (_f_enchant_with_levels, 10),
         (_f_set_attributes, 15), (_f_set_damage, 10),
         (_f_set_lore, 10), (_f_set_custom_data, 5),
         (_f_enchanted_count_increase, 5), (_f_apply_bonus, 5)]),
    "armorer": (  # Бронник
        _ARMOR,
        [(_f_set_attributes, 30), (_f_set_enchantments, 25),
         (_f_set_name, 15), (_f_set_lore, 10), (_f_set_components, 15),
         (_f_set_damage, 5)]),
    "alchemist": (  # Алхимик
        gl.POTIONS + ["minecraft:suspicious_stew",
                      "minecraft:honey_bottle", "minecraft:milk_bucket"],
        [(_f_set_potion, 30), (_f_set_stew_effect, 20),
         (_f_set_custom_data, 15), (_f_set_name, 10),
         (_f_set_lore, 10), (_f_set_random_potion, 10),
         (_f_set_count, 5)]),
    "enchanter": (  # Чародей
        gl.BOOKS + gl.ENCH_BOOKS + _WEAPONS + gl.PICKAXES,
        [(_f_enchant_randomly, 25), (_f_enchant_with_levels, 20),
         (_f_set_enchantments, 20), (_f_enchanted_count_increase, 10),
         (_f_apply_bonus, 10), (_f_toggle_tooltips, 10),
         (_f_set_name, 5)]),
    "curse_monger": (  # Проклинатель
        _WEAPONS + _ARMOR + gl.BOOKS,
        [(_f_set_enchantments, 30), (_f_set_name, 20),
         (_f_set_lore, 20), (_f_set_custom_data, 15),
         (_f_set_attributes, 10), (_f_toggle_tooltips, 5)]),
    "tailor": (  # Портной
        ["minecraft:leather_helmet", "minecraft:leather_chestplate",
         "minecraft:leather_leggings", "minecraft:leather_boots",
         "minecraft:white_banner", "minecraft:red_banner",
         "minecraft:blue_banner", "minecraft:wool", "minecraft:shears"],
        [(_f_set_random_dyes, 30), (_f_set_banner_pattern, 20),
         (_f_set_components, 20), (_f_set_lore, 15),
         (_f_set_name, 10), (_f_set_custom_data, 5)]),
    "scribe": (  # Писец
        gl.BOOKS + ["minecraft:written_book"],
        [(_f_set_book_cover, 25), (_f_set_written_book_pages, 25),
         (_f_set_writable_book_pages, 15), (_f_set_name, 15),
         (_f_set_lore, 10), (_f_set_custom_data, 10)]),
    "pyrotechnic": (  # Пиротехник
        ["minecraft:firework_rocket", "minecraft:firework_star"],
        [(_f_set_fireworks, 40), (_f_set_firework_explosion, 30),
         (_f_set_name, 15), (_f_set_lore, 15)]),
    "cartographer": (  # Картограф
        ["minecraft:map", "minecraft:filled_map", "minecraft:compass"],
        [(_f_exploration_map, 40), (_f_set_name, 20),
         (_f_set_lore, 20), (_f_set_custom_data, 20)]),
    "scavenger": (  # Падальщик
        ["minecraft:chest", "minecraft:barrel", "minecraft:shulker_box",
         "minecraft:bundle"] + gl.PICKAXES + gl.SHOVELS,
        [(_f_copy_state, 20), (_f_copy_name, 15),
         (_f_copy_components, 15), (_f_set_loot_table, 15),
         (_f_set_contents, 15), (_f_set_name, 10),
         (_f_modify_contents, 10)]),
    "showman": (  # Витринщик
        ["minecraft:diamond", "minecraft:emerald",
         "minecraft:netherite_ingot", "minecraft:golden_apple",
         "minecraft:totem_of_undying", "minecraft:nether_star",
         "minecraft:dragon_egg", "minecraft:beacon"],
        [(_f_set_name, 20), (_f_set_lore, 20),
         (_f_toggle_tooltips, 15), (_f_set_custom_model_data, 15),
         (_f_set_components, 15), (_f_set_custom_data, 15)]),
    "smith": (  # Кузнец
        _WEAPONS + gl.PICKAXES + gl.AXES + gl.SHOVELS + gl.HOES,
        [(_f_furnace_smelt, 25), (_f_set_damage, 20),
         (_f_set_count, 15), (_f_set_name, 15),
         (_f_set_attributes, 15), (_f_set_item, 10)]),
    "trickster": (  # Трюкач
        gl.ALL_ITEMS[:200],
        [(_f_filtered, 25), (_f_sequence, 15), (_f_limit_count, 15),
         (_f_set_count, 15), (_f_set_item, 15), (_f_discard, 5),
         (_f_modify_contents, 10)]),
    "mystic": (  # Мистик
        gl.BOOKS + gl.ENCH_BOOKS + ["minecraft:amethyst_shard",
                                    "minecraft:echo_shard"],
        [(_f_reference, 25), (_f_sequence, 15),
         (_f_set_custom_data, 20), (_f_set_name, 15),
         (_f_enchant_with_levels, 15), (_f_set_lore, 10)]),
    "gift_wrapper": (  # Даритель
        ["minecraft:chest", "minecraft:shulker_box", "minecraft:bundle",
         "minecraft:ominous_bottle", "minecraft:goat_horn",
         "minecraft:golden_apple", "minecraft:decorated_pot"],
        [(_f_set_contents, 25), (_f_modify_contents, 15),
         (_f_set_loot_table, 15), (_f_set_ominous, 10),
         (_f_set_instrument, 10), (_f_set_random_potion, 10),
         (_f_set_item, 10), (_f_set_count, 5)]),
    "headhunter": (  # Охотник за головами
        ["minecraft:player_head", "minecraft:skeleton_skull",
         "minecraft:zombie_head", "minecraft:creeper_head",
         "minecraft:wither_skeleton_skull"],
        [(_f_fill_player_head, 35), (_f_set_name, 25),
         (_f_set_lore, 20), (_f_set_custom_data, 20)]),
}

# у проклинателя зачарования - только проклятия
_CURSE_ENCHANTS = ["vanishing_curse", "binding_curse"]


# ---------------------------------------------------------------------------
# Публичная функция
# ---------------------------------------------------------------------------

def rand_item_modifiers(rng, ns, name, count=None):
    """Случайные item_modifiers измерения («персонажи» с 1-6 функциями).

    rng    - random.Random (весь рандом только через него);
    ns     - namespace;
    name   - имя измерения (id: <ns>:<name>_modN);
    count  - сколько модификаторов создать (None -> тяжёлый хвост,
             в среднем ~2, выбросы до 15).

    Возвращает {"item_modifiers": {"<ns>:<name>_modN": json, ...}},
    где json - массив функций (корень item_modifier-файла 26.2).
    Модуль ничего не пишет на диск."""
    if count is None:
        count = _modifier_count(rng)
    out = {}
    prior = []  # id уже созданных - для reference «назад»
    chars = rng.sample(list(_CHARACTERS),
                       min(len(_CHARACTERS), max(count, 1)))
    for i in range(count):
        mid = "%s:%s_mod%d" % (ns, name, i)
        # редкий пограничный случай: ПУСТОЙ модификатор (валидный
        # SequenceFunction из нуля функций)
        if rng.random() < 0.02:
            out[mid] = []
            prior.append(mid)
            continue
        key = chars[i % len(chars)]
        items, pool = _CHARACTERS[key]
        # базовый предмет: из пула характера, изредка «дикий»
        if rng.random() < 0.08:
            item = rng.choice(gl.ALL_ITEMS)
        else:
            item = rng.choice(items)
        env = {"prior": list(prior), "tag_prefix": "%s_m%d" % (name, i)}
        n = gl._weighted(rng, [(1, 20), (2, 30), (3, 25),
                               (4, 13), (5, 8), (6, 4)])
        funcs = []
        builders = []
        for _ in range(n):
            b = gl._weighted(rng, pool)
            if b not in builders or rng.random() < 0.3:
                builders.append(b)
                f = b(rng, item, env)
                if key == "curse_monger" and \
                        b is _f_set_enchantments:
                    f["enchantments"] = {
                        "minecraft:" + rng.choice(_CURSE_ENCHANTS): 1.0}
                funcs.append(f)
        # «дикий тир»: с малым шансом дополнительная случайная функция
        if rng.random() < 0.10:
            wild = rng.choice(_ALL_BUILDERS)
            try:
                wf = wild(rng, item, env)
                funcs.append(wf)
            except Exception:
                pass
        # корень: массив (обычно) или одиночный объект (тоже валиден)
        if len(funcs) == 1 and rng.random() < 0.35:
            out[mid] = funcs[0]
        else:
            out[mid] = funcs
        prior.append(mid)
    return {"item_modifiers": out}


# ---------------------------------------------------------------------------
# Самотест: воспроизводимость, 20+ seed, валидность id/структуры
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    import random

    seeds = list(range(1, 31))  # 30 seed
    total = 0
    per_seed = []
    empty_seen = 0
    for sd in seeds:
        r1 = random.Random(sd)
        r2 = random.Random(sd)
        res1 = rand_item_modifiers(r1, "rndim", "dim%d" % sd)
        res2 = rand_item_modifiers(r2, "rndim", "dim%d" % sd)
        assert json.dumps(res1, sort_keys=True) == \
            json.dumps(res2, sort_keys=True), "невоспроизводимо: seed %d" % sd
        tbl = res1["item_modifiers"]
        total += len(tbl)
        per_seed.append(len(tbl))
        for mid, js in tbl.items():
            ns_, rest = mid.split(":", 1)
            assert ns_ == "rndim" and rest.startswith("dim%d_mod" % sd), mid
            assert all(c in "abcdefghijklmnopqrstuvwxyz0123456789_/"
                       for c in rest), mid
            json.dumps(js)  # сериализуемость
            roots = js if isinstance(js, list) else [js]
            if not roots:
                empty_seen += 1
            for f in roots:
                assert "function" in f and f["function"].startswith(
                    "minecraft:"), (mid, f)
                if f.get("function") == "minecraft:reference":
                    ref = f["name"]
                    my_n = int(mid.rsplit("mod", 1)[1])
                    ref_n = int(ref.rsplit("mod", 1)[1])
                    assert ref_n < my_n, (mid, ref)
    print("OK: %d modifiers на %d seed (в среднем %.2f, min %d, max %d), "
          "пустых: %d" % (total, len(seeds), total / float(len(seeds)),
                          min(per_seed), max(per_seed), empty_seen))
    demo = rand_item_modifiers(random.Random(777), "rndim", "demo", 4)
    for mid, js in demo["item_modifiers"].items():
        print(" ", mid, "=", json.dumps(js, ensure_ascii=False)[:160])
