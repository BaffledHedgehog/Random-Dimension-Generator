#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_time.py — генератор случайного ВРЕМЕНИ измерения для Minecraft 26.2.

Реестры 26.2 (пути подтверждены ванильным jar-файлом 26.2):
  * world_clock — data/<ns>/world_clock/<id>.json   (ванилла: overworld, the_end)
  * timeline    — data/<ns>/timeline/<id>.json      (ванилла: day, moon, early_game,
                                                     villager_schedule)
  * теги timeline — data/<ns>/tags/timeline/<tag>.json
                      (ванилла: in_overworld, in_nether, in_end, universal)

Формат world_clock (26.2): запись-пустышка "{}". Класс WorldClock — record без
полей (unit-codec), значение реестра несёт только ID: на него ссылаются
timeline.clock и dimension_type.default_clock.

Формат timeline (сверено с timeline/day.json, moon.json, early_game.json,
villager_schedule.json и Timeline.class):
  {
    "clock": "<id из world_clock>",        # ОБЯЗАТЕЛЬНО
    "period_ticks": <int > 0>,             # нет поля — «одноразовая» шкала
                                            # (как ванильный early_game)
    "time_markers": {                      # именованные моменты времени
      "<id>": <int>,                       # либо просто тики,
      "<id>": {"ticks": <int>, "show_in_commands": true}
    },
    "tracks": {                            # дорожки значений по времени
      "minecraft:visual/sky_color": {
        "keyframes": [{"ticks": <int>, "value": <значение>}, ...],
        "ease": "constant" | ... | {"cubic_bezier": [x1, y1, x2, y2]},
        "modifier": "or" | "and" | "maximum" | "multiply"
      }
    }
  }
Ключи tracks — ID environment-атрибутов (реестр 26.2); используем только
атрибуты, реально встречающиеся в ванильных timeline-файлах.

Ограничения движка (Timeline.class / KeyframeTrack.class):
  * period_ticks — строго положительный (POSITIVE_INT);
  * keyframes не пустые, отсортированы по ticks (нестрого); при периоде
    0 <= ticks <= period_ticks;
  * ticks маркеров: 0 <= ticks < period_ticks (NON_NEGATIVE_INT);
  * ключи маркеров уникальны в рамках одного world_clock — все timeline'ы
    измерения делят ОДИН world_clock, поэтому имена маркеров делаем
    уникальными (суффикс номера шкалы).

Модуль НЕ пишет файлы: rand_time() и rand_infiniburn_tag() только возвращают
dict'ы. Весь рандом — через переданный rng (random.Random).
"""

# ---------------------------------------------------------------------------
# Данные, подтверждённые jar 26.2
# ---------------------------------------------------------------------------

# Фазы луны из timeline/moon.json
MOON_PHASES = [
    "full_moon", "waning_gibbous", "third_quarter", "waning_crescent",
    "new_moon", "waxing_crescent", "first_quarter", "waxing_gibbous",
]

# Активности жителей из timeline/villager_schedule.json
VILLAGER_ACTIVITIES = [
    "minecraft:idle", "minecraft:work", "minecraft:meet",
    "minecraft:rest", "minecraft:play",
]

# Метки для собственных time_markers (ID маркеров — свой namespace)
MARKER_LABELS = [
    "dawn", "morning", "noon", "afternoon", "dusk", "nightfall",
    "midnight", "eve",
]

# Именованные ease из реестра EasingType (EasingType.class; дефолт — linear)
EASE_NAMES = [
    "constant",
    "in_sine", "out_sine", "in_out_sine",
    "in_quad", "out_quad", "in_out_quad",
    "in_cubic", "out_cubic", "in_out_cubic",
    "in_quart", "out_quart", "in_out_quart",
    "in_quint", "out_quint", "in_out_quint",
    "in_expo", "out_expo", "in_out_expo",
    "in_circ", "out_circ", "in_out_circ",
    "in_bounce", "out_bounce", "in_out_bounce",
    "in_back", "out_back", "in_out_back",
    "in_elastic", "out_elastic", "in_out_elastic",
]

# Спецификации треков: (ID атрибута, тип значения, допустимые модификаторы).
# Модификаторы ТОЧНО по ванильным timeline-файлам 26.2 — они зависят от
# конкретного атрибута (напр. eyeblossom_open идёт БЕЗ модификатора, а
# bees_stay_in_hive — с "or"; пустой список = поле не писать вовсе).
# Цвета: sky_color/fog_color/sky_light_color — 6-значный hex "#rrggbb",
# cloud_color — 8-значный ARGB "#rrggbbaa" (ванилла пишет и интами),
# sunrise_sunset_color — 8-значный "#rrggbbaa".
TRACK_SPECS = [
    # цвета "#rrggbb" + multiply (day.json)
    ("minecraft:visual/sky_color", "rgb", ["multiply"]),
    ("minecraft:visual/fog_color", "rgb", ["multiply"]),
    ("minecraft:visual/sky_light_color", "rgb", ["multiply"]),
    # cloud_color — ARGB-цвет "#rrggbbaa" + multiply (day.json, интами)
    ("minecraft:visual/cloud_color", "rgba", ["multiply"]),
    # цвет рассвета/заката "#rrggbbaa" — БЕЗ модификатора (day.json)
    ("minecraft:visual/sunrise_sunset_color", "rgba", []),
    # дробные 0..1
    ("minecraft:visual/sky_light_factor", "factor", ["multiply"]),
    ("minecraft:visual/star_brightness", "star", ["maximum"]),
    ("minecraft:gameplay/sky_light_level", "factor", ["multiply"]),
    ("minecraft:gameplay/cat_waking_up_gift_chance", "chance", ["maximum"]),
    ("minecraft:gameplay/turtle_egg_hatch_chance", "chance", ["maximum"]),
    ("minecraft:gameplay/surface_slime_spawn_chance", "chance", ["maximum"]),
    # углы светил в градусах — без модификатора, ease cubic_bezier (day.json)
    ("minecraft:visual/sun_angle", "angle", []),
    ("minecraft:visual/moon_angle", "angle", []),
    ("minecraft:visual/star_angle", "angle", []),
    # строковые перечисления — без modifier/ease (moon.json, villager_schedule)
    ("minecraft:visual/moon_phase", "moon_phase", []),
    ("minecraft:gameplay/villager_activity", "activity", []),
    ("minecraft:gameplay/baby_villager_activity", "activity", []),
    # булевы флаги: у одних "or" (day.json), у patrol — "and" (early_game),
    # у eyeblossom_open — БЕЗ модификатора (day.json)
    ("minecraft:gameplay/monsters_burn", "bool", ["or"]),
    ("minecraft:gameplay/bees_stay_in_hive", "bool", ["or"]),
    ("minecraft:gameplay/creaking_active", "bool", ["or"]),
    ("minecraft:gameplay/eyeblossom_open", "bool", []),
    ("minecraft:gameplay/can_pillager_patrol_spawn", "bool", ["and"]),
    ("minecraft:audio/firefly_bush_sounds", "bool", ["or"]),
]

# Допустимость ease по типам (сверено с ванилью: строки и углы — constant/
# cubic_bezier; числовые — constant; цвета — без ease, кроме rare случаев)
_EASE_OK = {
    "rgb": False, "rgba": False, "factor": True, "chance": True,
    "star": True, "bool": False, "angle": True, "moon_phase": False,
    "activity": False,
}

# Запасной список блоков, если generate_dimension.py недоступен для импорта
_FALLBACK_BLOCKS = [
    "minecraft:stone", "minecraft:deepslate", "minecraft:granite",
    "minecraft:diorite", "minecraft:andesite", "minecraft:tuff",
    "minecraft:calcite", "minecraft:cobblestone", "minecraft:dirt",
    "minecraft:coarse_dirt", "minecraft:gravel", "minecraft:sand",
    "minecraft:red_sand", "minecraft:sandstone", "minecraft:netherrack",
    "minecraft:basalt", "minecraft:smooth_basalt", "minecraft:blackstone",
    "minecraft:obsidian", "minecraft:end_stone", "minecraft:quartz_block",
    "minecraft:prismarine", "minecraft:terracotta", "minecraft:bricks",
    "minecraft:nether_bricks", "minecraft:magma_block", "minecraft:glowstone",
    "minecraft:packed_ice", "minecraft:snow_block", "minecraft:amethyst_block",
]

# Блоки «вне» SOLID_BLOCKS: горючие/прочие известные (ванильный
# infiniburn_overworld = netherrack + magma_block)
EXTRA_BURNABLE = [
    "minecraft:soul_sand", "minecraft:soul_soil", "minecraft:bedrock",
    "minecraft:crimson_nylium", "minecraft:warped_nylium",
    "minecraft:netherrack", "minecraft:magma_block",
]


# ---------------------------------------------------------------------------
# Вспомогательные
# ---------------------------------------------------------------------------

def _rnd_f(rng, a, b, digits=3):
    return round(rng.uniform(a, b), digits)


def _rand_color24(rng):
    """Цвет "#rrggbb" — как в ванильных timeline/day.json."""
    return "#%06x" % rng.getrandbits(24)


def _rand_color32(rng):
    """Цвет с альфой "#rrggbbaa" — как sunrise_sunset_color в day.json."""
    return "#%02x%06x" % (rng.randint(8, 200), rng.getrandbits(24))


def _rand_value(rng, kind):
    """Случайное значение кейфрейма для данного типа дорожки."""
    if kind == "rgb":
        return _rand_color24(rng)
    if kind == "rgba":
        return _rand_color32(rng)
    if kind == "factor":
        return _rnd_f(rng, 0.0, 1.0)
    if kind == "chance":
        return _rnd_f(rng, 0.0, 1.0)
    if kind == "star":
        # яркость звёзд в ванилле 0..0.5
        return _rnd_f(rng, 0.0, 0.5)
    if kind == "moon_phase":
        return rng.choice(MOON_PHASES)
    if kind == "activity":
        return rng.choice(VILLAGER_ACTIVITIES)
    if kind == "bool":
        return rng.random() < 0.5
    if kind == "angle":
        return _rnd_f(rng, 0.0, 360.0, 1)
    raise ValueError("неизвестный тип дорожки: %s" % kind)


def _rand_keyframes(rng, kind, period):
    """Кейфреймы дорожки. period=None — одноразовая шкала (без периода).
    Возвращает НЕПУСТОЙ список, отсортированный по ticks (нестрого),
    при периоде 0 <= ticks <= period — как требует KeyframeTrack."""
    if kind == "angle" and period:
        # полный оборот светила: значение ровно +360 за период (плавная
        # обёртка угла, по мотивам sun_angle из day.json)
        start = _rnd_f(rng, 0.0, 360.0, 1)
        kfs = [{"ticks": 0, "value": start},
               {"ticks": period, "value": round(start + 360.0, 1)}]
        # иногда вставим промежуточную точку (ускорение/замедление хода)
        if period >= 4 and rng.random() < 0.4:
            mid = rng.randrange(1, period)
            kfs.insert(1, {"ticks": mid,
                           "value": _rnd_f(rng, 0.0, 720.0, 1)})
        return kfs

    # диапазон тиков: у периодической шкалы — [0, period], у одноразовой —
    # протяжённый «прогресс» до 200000 тиков (как early_game: 0..120000)
    span = period if period else rng.randint(1000, 200000)

    n = 2
    if kind == "bool":
        n = rng.randint(2, 4)
    elif kind == "moon_phase":
        n = rng.randint(2, 8)
    else:
        n = rng.randint(2, 9)
    n = max(2, min(n, span + 1))

    ticks = sorted(rng.sample(range(0, span + 1), n))
    kfs = [{"ticks": t, "value": _rand_value(rng, kind)} for t in ticks]

    if kind == "bool":
        # флаг «включается/выключается» — чередуем значения
        v = rng.random() < 0.5
        for kf in kfs:
            kf["value"] = v
            v = not v
    elif period and kind in ("rgb", "factor", "star", "chance") \
            and rng.random() < 0.5:
        # замкнуть цикл: в конце периода то же значение, что в начале
        kfs[-1]["value"] = kfs[0]["value"]
    return kfs


def _rand_track(rng, kind, period, mods):
    """Одна дорожка: keyframes (+ иногда ease и modifier).
    mods — ТОЧНЫЙ список допустимых модификаторов атрибута (может быть
    пустым — тогда поле не пишем вовсе, как eyeblossom_open в ванилле)."""
    track = {"keyframes": _rand_keyframes(rng, kind, period)}

    r = rng.random()
    if kind == "angle":
        # ванилла использует cubic_bezier для углов светил
        if r < 0.7:
            track["ease"] = {"cubic_bezier": [
                _rnd_f(rng, 0.0, 1.0), _rnd_f(rng, 0.0, 1.0),
                _rnd_f(rng, 0.0, 1.0), _rnd_f(rng, 0.0, 1.0)]}
        elif r < 0.85:
            track["ease"] = "constant"
    elif _EASE_OK.get(kind) and r < 0.30:
        track["ease"] = "constant"     # как turtle_egg_hatch_chance / moon.json
    elif _EASE_OK.get(kind) and r < 0.45:
        track["ease"] = rng.choice(EASE_NAMES)
    # цвета, строки, bool — в ванилле без ease

    if mods and rng.random() < 0.9:
        track["modifier"] = rng.choice(mods)
    return track


def _solid_block_ids():
    """ID блоков из SOLID_BLOCKS генератора измерений (ленивый импорт —
    избежать циклического импорта, т.к. generate_dimension импортирует нас)."""
    try:
        from generate_dimension import SOLID_BLOCKS
        return [bid for bid, _props in SOLID_BLOCKS]
    except ImportError:
        return list(_FALLBACK_BLOCKS)


# ---------------------------------------------------------------------------
# Публичные генераторы
# ---------------------------------------------------------------------------

def rand_time(rng, ns, name):
    """Своё время измерения. Возвращает:
    {"world_clock": {id: json},           # 1 world_clock (пустышка "{}")
     "timeline": {id: json},              # 1–3 timeline
     "timeline_tags": {tag_name: json},   # 1 тег, values = ID этих timeline
     "tag_paths": {tag_name: "tags/timeline/xxx.json"},  # путь файла тега
                                                           # внутри data/<ns>/
     "file_paths": {"world_clock": "world_clock/",       # фактические папки
                    "timeline": "timeline/"}}             # записи, по jar 26.2
    Все числовые поля случайны в разумных пределах; rng — random.Random."""
    clock_id = "%s:%s" % (ns, name)

    timelines = {}
    tag_values = []
    n_timelines = rng.randint(1, 3)
    for i in range(n_timelines):
        tl_id = clock_id if i == 0 else "%s:%s_tl%d" % (ns, name, i + 1)

        # период: 85% — циклическая шкала, 15% — одноразовая (early_game)
        periodic = rng.random() < 0.85
        period = None
        if periodic:
            if rng.random() < 0.25:
                # долгий «лунный» цикл — кратен суткам (ваниль: 192000)
                period = 24000 * rng.randint(2, 8)
            else:
                # обычная длина цикла, 600..96000 тиков
                period = rng.randint(600, 96000)

        tl = {"clock": clock_id}
        if periodic:
            tl["period_ticks"] = period

        # дорожки: 1..8 случайных атрибутов без повторов
        k = rng.randint(1, min(8, len(TRACK_SPECS)))
        tl["tracks"] = {tid: _rand_track(rng, kind, period if periodic else None,
                                         mods)
                        for tid, kind, mods in rng.sample(TRACK_SPECS, k)}

        # маркеры времени — только у циклических шкал (early_game без них);
        # имена уникальны: суффикс номера шкалы (общий world_clock!)
        if periodic:
            labels = rng.sample(MARKER_LABELS,
                                rng.randint(1, min(4, len(MARKER_LABELS))))
            markers = {}
            for label in labels:
                mid = "%s:%s_%d_%s" % (ns, name, i + 1, label)
                t = rng.randrange(0, period)      # строго < period_ticks
                if rng.random() < 0.5:
                    markers[mid] = t              # короткая форма: просто тики
                else:
                    markers[mid] = {"ticks": t, "show_in_commands": True}
            if markers:
                tl["time_markers"] = markers

        timelines[tl_id] = tl
        tag_values.append(tl_id)

    # один тег timeline: #<ns>:<name> со всеми нашими шкалами
    timeline_tags = {name: {"values": tag_values}}
    tag_paths = {name: "tags/timeline/%s.json" % name}

    return {
        "world_clock": {clock_id: {}},   # world_clock в 26.2 — всегда "{}"
        "timeline": timelines,
        "timeline_tags": timeline_tags,
        "tag_paths": tag_paths,
        # фактические папки записи (реестры БЕЗ префикса worldgen/,
        # как dimension_type: подтверждено jar и ключами реестров)
        "file_paths": {"world_clock": "world_clock/", "timeline": "timeline/"},
    }


def rand_infiniburn_tag(rng, ns, name, count=None):
    """Свой тег infiniburn для dimension_type.infiniburn (#<ns>:<name>).
    Возвращает json {"values": [...]}.

    count — сколько блоков в теге (по умолчанию 3-30 — старое поведение;
    вызывается с числом из тяжело-хвостового распределения: почти всегда
    1-2, редкие выбросы до сотни)."""
    pool = list(dict.fromkeys(_solid_block_ids() + EXTRA_BURNABLE))
    k = rng.randint(3, min(30, len(pool))) if count is None \
        else max(1, min(count, len(pool)))
    return {"values": sorted(rng.sample(pool, k))}
