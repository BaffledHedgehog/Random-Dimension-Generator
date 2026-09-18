# -*- coding: utf-8 -*-
"""Генератор случайных зачарований и enchantment_provider для Minecraft 26.2.

Формат проверен по клиентскому jar 26.2 (data format 107):
  vanilla JSON `data/minecraft/enchantment/*.json` (43 шт.) и
  `data/minecraft/enchantment_provider/*.json`, плюс байткод классов
  net/minecraft/world/item/enchantment/* (javap, Java 25 epsilon).
  Всё ниже — либо скопировано из ванильных JSON, либо сверено с кодеками
  в байткоде; ничего не выдумано.

Реестры (БЕЗ префикса worldgen/):
  data/<ns>/enchantment/<id>.json
  data/<ns>/enchantment_provider/<id>.json

Зачарование (Enchantment$EnchantmentDefinition.CODEC):
  description        — текст-компонент (у нас: {"text": "...", "color": ...})
  supported_items    — HolderSet<Item>: "#tag" | id | список id
  primary_items      — необязательный HolderSet<Item>
  weight             — int 1..1024 (обратная редкость)
  max_level          — int 1..255
  min_cost/max_cost  — {"base": int, "per_level_above_first": int}
  anvil_cost         — int >= 0
  slots              — список групп слотов: any, mainhand, offhand, hand,
                       feet, legs, chest, head, armor, body, saddle
  exclusive_set      — необязательный HolderSet<Enchantment> (id | список)
  effects            — необязательная карта компонент (DataComponentMap)

Компоненты эффектов (EnchantmentEffectComponents, все 31, имена из байткода):
  списки {effect: ValueEffect, requirements?}:
    damage, damage_protection, smash_damage_per_fallen_block, knockback,
    armor_effectiveness, item_damage, ammo_use, projectile_piercing,
    projectile_spread, projectile_count, trident_return_acceleration,
    fishing_time_reduction, fishing_luck_bonus, block_experience,
    mob_experience, repair_with_xp
  список {effect: {}, requirements}:
    damage_immunity (DamageImmunity — unit-кодек, эффект всегда {})
  списки {enchanted, affected, effect, requirements?} (TargetedConditionalEffect):
    post_attack, equipment_drops (effect тут — ValueEffect, как у looting:
      add 0.01/0.01, enchanted=attacker, req entity_properties attacker player)
  списки {effect: EntityEffect, requirements?}:
    post_piercing_attack, hit_block, tick, projectile_spawned
  список {effect: LocationEffect, requirements?}:
    location_changed — реестр location-эффектов принимает ТЕ ЖЕ имена типов,
      что и entity-эффекты (проверено по bootstrap EnchantmentLocationBasedEffect:
      all_of, apply_mob_effect, attribute, change_item_damage, damage_entity,
      explode, ignite, apply_impulse, apply_exhaustion, play_sound,
      replace_block, replace_disk, run_function, set_block_properties,
      spawn_particles, summon_entity) — поэтому frost_walker кладёт
      replace_disk прямо в location_changed
  список {amount, attribute, id, operation} (НЕ conditional):
    attributes — operation: add_value | add_multiplied_base |
      add_multiplied_total; id — уникальный Identifier
  одиночный ValueEffect (НЕ список):
    crossbow_charge_time, trident_spin_attack_strength
  список {start, end} — crossbow_charging_sounds (id звуков)
  список id звуков     — trident_sound
  пустой объект {}     — prevent_equipment_drop, prevent_armor_change

ValueEffect (диспетч по "type" — все 6 типов реестра, сверено по
байткоду EnchantmentValueEffect):
  add {value: LBV}, multiply {factor: float}, set {value: float},
  remove_binomial {chance: LBV}, all_of {effects: [...]},
  exponential {base: LBV, exponent: LBV} — ScaleExponentially:
  итог = value * base^exponent (в ванили не используется; мы генерируем
  с знаком по компоненте: для «уменьшающих» (charge_time) base < 1;
  проверено загрузкой на реальном сервере 26.2)

LevelBasedValue ("type"):
  linear {base, per_level_above_first}, clamped {value, min, max},
  fraction {numerator, denominator}, levels_squared {added},
  exponent {base, power}, lookup {values: [float...], fallback},
  а также голое число-константа (vanilla: radius 3.5, height 1.0...).

EntityEffect-типы (поля по байткоду; Vec3/Vec3i сериализуются СПИСКАМИ
[x, y, z] — см. wind_burst/lunge/frost_walker):
  apply_mob_effect {to_apply: id|[id], min_duration, max_duration,
                    min_amplifier, max_amplifier}      — LBV
  change_item_damage {amount: LBV}
  damage_entity {min_damage, max_damage: LBV, damage_type}
  ignite {duration: LBV}                               — в тиках (flame: 100)
  apply_impulse {direction: [x,y,z], coordinate_scale: [x,y,z], magnitude: LBV}
  apply_exhaustion {amount: LBV}
  play_sound {sound: id|[id], volume: FloatProvider, pitch: FloatProvider}
  replace_block {offset: [x,y,z]int, predicate?, block_state: BlockStateProvider,
                 trigger_game_event?}                   — predicate = worldgen
                                                        BlockPredicate
  replace_disk {radius: LBV, height: LBV, offset: [x,y,z]int, predicate?,
                block_state: BlockStateProvider, trigger_game_event?}
  run_function {function: id}   — проверяется ТОЛЬКО в рантайме; мы ссылаемся
                                  на функцию "<ns>:<id зачарования>" — её
                                  должен создать основной скрипт (или тест-пак)
  set_block_properties {properties: {строка: строка}, offset?, trigger_game_event?}
  spawn_particles {particle: {"type": id} (ОБЪЕКТ, голая строка не
                    парсится!), horizontal_position: {type: entity_position|
                    in_bounding_box — БЕЗ префикса minecraft:, offset: float,
                    scale: float>0}, vertical_position: {...},
                   horizontal_velocity: {movement_scale: float,
                    base: FloatProvider}, vertical_velocity: {...},
                   speed: FloatProvider?}
  summon_entity {entity: id|[id], join_team: bool}
  explode {radius: LBV, block_interaction: none|block|mob|tnt|trigger,
           damage_type, small_particle, large_particle (объекты
           {"type": id}), sound — ЭТИ ПОЛЯ В 26.2 ОБЯЗАТЕЛЬНЫ; optional:
           attribute_to_user?, create_fire?, knockback_multiplier?,
           immune_blocks?: HolderSet<Block> ("#tag"), offset: [x,y,z],
           block_particles?}
  all_of {effects: [...]}

LocationEffect-типы: те же + attribute {id, attribute, amount: LBV, operation}.

requirements — LootContextPredicate, и 26.2 ВАЛИДИРУЕТ их на загрузке по
ContextKeySet компоненты ("Parameters [...] are not provided in this
context"). Пулы обязаны соответствовать контексту (реально проверено на
сервере; LootContextParamSets): enchanted_damage (damage,
damage_protection, smash..., knockback, armor_effectiveness, post_attack,
damage_immunity) — random_chance / damage_source_properties /
entity_properties(this|direct_attacker); enchanted_item (item_damage,
ammo_use) — match_tool; enchanted_location/enchanted_entity
(location_changed, tick, post_piercing_attack) — random_chance /
entity_properties(this: entity_type, flags, vehicle) / inverted;
hit_block — weather_check / entity_properties(this) / location_check;
projectile_* — только random_chance; equipment_drops — как у looting
(entity_properties attacker player); у остальных компонент требований
не генерируем (в ванили их нет). FloatProvider uniform использует ключи
min_inclusive/max_exclusive, IntProvider uniform — min_inclusive/
max_inclusive (НЕ min/max — проверено на сервере).

EnchantmentTarget (enchanted/affected): attacker | damaging_entity | victim.

EnchantmentProvider (проверено по ванильным enderman_loot_drop /
mob_spawn_equipment / pillager_spawn_crossbow):
  single {enchantment: id, level: IntProvider}
  by_cost {enchantments: HolderSet, cost: IntProvider}
  by_cost_with_difficulty {enchantments: HolderSet,
                           max_cost_span: int, min_cost: int}

ВАЖНО про лут (EnchantRandomlyFunction): провайдеры из loot-таблиц НЕ
ссылаются — поля функции это `options` (HolderSet<Enchantment>:
"#тег" | id | список id), `only_compatible` (bool, умолч. true) и
`include_additional_cost_component`. enchantment_provider потребляют только
спавнеры мобов (EnchantmentHelper.enchantItemFromProvider). Для лута
gen_loot.py должен перечислять НАШИ id в options (или завести тег
tags/enchantment/). Сет компонентов: "minecraft:enchantments" = плоская
карта {id: level}, set_enchantments = {id: float}.

Модуль НИЧЕГО не пишет на диск: rand_enchantments(rng, ns, name, count=None,
mod_ids=None, pred_ids=None) возвращает
  {"enchantments": {id: json}, "enchantment_providers": {id: json},
   "functions": {<fname>: текст mcfunction},      # run_function-эффекты
   "gate_predicates": {<id>: json}},               # random_chance-гейты
id вида "<ns>:<name>_enchN" / "<ns>:<name>_provN"; fname — id зачарования
без namespace. mod_ids/pred_ids — id item_modifier'ов/predicates ИЗМЕРЕНИЯ
(генерируются ДО зачарований и передаются сюда): открывают категорию
перекраски (item modify) в mcfunction. gate_predicates обязаны быть
записаны основным скриптом в predicate/ — на них ссылаются команды.

Связка с gen_loot (лут ↔ зачарования; фичи «предмет только с визуалом»
и lore-подсказки):
  passive_enchants(enchantments) — список id зачарований с ПАССИВНЫМ
    действием: компоненты attributes / tick / location_changed /
    damage_immunity / prevent_equipment_drop / prevent_armor_change
    работают при ношении или удержании предмета, без боевых событий —
    именно их gen_loot ставит предмету, которому «не хватает функционала»;
  summarize_enchantment(ejson) — краткое русское описание действия
    зачарования, ДО 8 СЛОВ, строится по фактическим компонентам effects:
    damage → «усиливает урон», knockback → «отбрасывает врагов»,
    post_attack → «мстит при ударе по тебе», apply_mob_effect →
    «накладывает яд», attributes → «усиливает броню»...; про run_function
    говорит «творит особый ритуал» (текст mcfunction живёт вне JSON
    зачарования — словари _name_seeds/_ee_word дают слово «Ритуал»);
  rand_enchantments дополнительно сохраняет свой результат в модульной
    переменной LAST_ENCHANTMENTS ({id: json зачарования}) — gen_loot
    в том же процессе (generate_dimension.py) находит по ней зачарования
    измерения сам, без правки основного скрипта, который передаёт в
    set_custom_enchants только id.

run_function-ЭФФЕКТЫ И mcfunction (всё сверено байткодом jar 26.2):
  RunFunction.applyEffect(level, lvl, item, entity, pos) исполняет функцию
  с source.withEntity(entity).withPosition(pos).withRotation(
  entity.getRotationVector()) — то есть @s/позиция/поворот = сущности,
  на которую применён эффект. Отсюда контексты (одна функция на
  зачарование, выбирается САМЫЙ частый/строгий):
    full  — post_attack: affected-сущность; для run_function мы
            маршрутизируем affected=enchanted (владелец предмета);
    event — hit_block (бьющий) / post_piercing_attack (атакующий) /
            projectile_spawned (@s = сам снаряд!);
    worn  — tick/location_changed: носитель, вызов КАЖДЫЙ ТИК — только
            дешёвые команды, КАЖДАЯ загейчена random_chance-предикатом.
  Категории команд (41 = 20 исходных + 21 новая; веса/дешевизна — _FN_CAT_W,
    строители _fn_*_cmd):
    particle — 10 форм геометрии (смещения считает генератор): пучок/
      сектор/вспышка перед глазами/кольцо 6-10/СПИРАЛЬ (радиус+высота
      растут)/КУПОЛ-полусфера/АРКА-полуокружность/СЛЕД вдоль взгляда
      (^ ^ ^N по питчу)/СТОЛБ/СТЕНА-ЗАНАВЕС 2-3×2-3 перпенд. взгляду;
      параметризованные частицы dust/dust_color_transition/entity_effect/
      flash/dragon_breath (цвета — палитра 30);
    sound — playsound (48 звуков, сверены по SoundEvents; vol 0.3-2.0,
      pitch 0.5-2.0);
    fangs — 7 форм: линия/веер/крест/ДУГА (rotated ~±90)/КОЛЬЦО 8-12
      вокруг игрока (посчитанные ~X ~ ~Z)/СПИРАЛЬ/СТЕНА перпенд.
      взгляду (rotated ~±90 + ^±2 вперёд);
    cloud — одно или СВЯЗКА 2-3 area_effect_cloud с разными
      Radius/Duration/WaitTime, custom_effects 1-3 (расширенный пул:
      +glowing/darkness/blindness/unluck) и custom_color;
    firework / fw2 — одиночная ракета и ДВОЙНОЙ залп с разными зарядами
      (shape/colors/fade_colors/has_trail/has_twinkle);
    selfbuff / duet — баф и ДУЭТ бафов effect give @s (НЕ в worn);
    aura / auraring — дебаф-аура и КОЛЬЦО 2-3 радиусов effect give @e
      (НЕ в worn);
    flavor — actionbar-фразы (80 русских);
    recolor / glow2 — перекраска item modify и ЖЕРТВЕННОЕ СВЕЧЕНИЕ
      (mainhand+offhand, нужны mod_ids);
    xp / harvest — мелкий XP и ЖАТВА (орбы + частицы; гейт 0.05-0.2);
    lightning — только full, гейт 0.04-0.12 (<=0.15);
    echo — 2-3 playsound с НАРАСТАЮЩИМ pitch; flash — ВСПЫШКА СВЕТА
      (end_rod/flash{color}/... + звук); totem — тотемный визуал
      (totem_of_undying + item.totem.use); thunder — ГРОЗОВОЕ ЭХО
      (только звук entity.lightning_bolt.thunder, без молнии);
    НОВЫЕ 21 категория: rain — ДОЖДЬ частиц сверху (6-12 капель,
      высоты 2.2-5.5); vortex — ВИХРЬ (спираль 8-14, радиус растёт
      0.3-0.8→1.6-2.6); dome — КУПОЛ (полусфера: экватор + верхнее
      кольцо + макушка); chord — АККОРД-АРПЕДЖИО (3-5 звуков, pitch
      растёт шагом 0.15-0.35); choir — ХОР (один звук с 3-4 сторон,
      positioned ~±3); gamma — ГАММА-ЯРУСЫ (2-3 area_effect_cloud на
      высотах 0.4/1.4/2.4); fangarc — ВЕЕР КЛЫКОВ ПОЛУКРУГОМ (5-9 клыков
      дугой 90-180°); fangwall — СТЕНА КЛЫКОВ на дистанции 2.5-4.5
      поперёк взгляда; shards — ОСКОЛКИ (4-8 частиц block{block_state:
      {Name:...}} — BlockParticleOption 26.2, сверено javap'ом; БЕЗ
      summon falling_block — сущности не спамим); glow — СВЕЧЕНИЕ
      (effect give @s glowing 10-30 с, гейт 0.15-0.5, НЕ в worn);
      secondwind — ВТОРОЕ ДЫХАНИЕ (2 самобаффа: короткий 4-10 с +
      длинный +6-18 с); whisper — ШЁПОТ (tellraw цветной флейвор в чат,
      редко); march — МАРШ (3-5 звуков, громкость 0.3→1.5); awakening —
      ПРОБУЖДЕНИЕ (вспышка + гром-эхо + залп частиц); oath — КЛЯТВА
      (item modify обеих рук + title; нужны mod_ids); xprain — ДОЖДЬ
      ОПЫТА (4-8 орбов россыпью, гейт 0.05-0.2); farewell — ПРОЩАЛЬНЫЙ
      САЛЮТ (фейерверк с обязательными fade_colors + частицы); rings —
      МНОГОСЛОЙНЫЕ КОЛЬЦА (2-3 радиуса); crosses — КРЕСТЫ (1-3, центр
      + 4 луча); stars — ЗВЁЗДЫ (1-2, 5-8 лучей из центра + ядро);
      downspiral — ВОРОНКА (спираль ВНИЗ: радиус сжимается, высота
      падает 2.0→0.5).
    Инварианты worn-контекста: только particle/playsound/title/item/
    tellraw (все гейчены), без summon и effect give @s; призывные и
    бафовые категории — только full/event.
  Архитектурно ЗАПРЕЩЕНЫ: kill/give/tp/gamemode/scoreboard/data/... —
  самотест проверяет белый список глаголов. Слова профиля функции
  («Клык», «Громовержец», «Переливы»...) идут в НАЗВАНИЕ зачарования —
  функция генерируется ДО имени и передаёт слово в
  _name_seeds/_effect_name.
  Скрытый маркер-armor_stand НЕ призываем: без kill/деспавна он
  накапливался бы в мире вечно (чистота мира важнее).

ВАЛИДНОСТЬ КОМПОНЕНТ ПО ПРЕДМЕТАМ (требование юзера: «зачарования
не должны быть на предметах где их нельзя использовать — не надо мечу
давать защиту»; касается и сгенерированных). Правила сверены с точками
срабатывания в байткоде jar 26.2 (EnchantmentHelper: методы без
слот-чека — читают предмет-триггер; runIterationOnEquipment — со
слот-чеком Enchantment.matchingSlot) и закодированы в _COMP_ITEM_RULES
(+ _comp_usable; генерация фильтрует кандидатов, самотест проверяет
каждое сгенерированное зачарование через side-канал LAST_PROFILES):
  damage_protection — только надеваемое (armor/elytra/#equippable) +
    слоты брони; щиту не даём (в руке он не экипировка);
  smash_damage_per_fallen_block — ТОЛЬКО булава (MaceItem.hurtEnemy);
  атрибуты — тематические пулы по профилю (_PROFILE_ATTR_IDS):
    attack_* / sweeping — оружию, block_break/mining_efficiency/
    submerged_mining — инструментам, armor/toughness — броне;
  projectile_count/spread/piercing/ammo_use — лук/арбалет;
  projectile_spawned — лук/арбалет/трезубец; crossbow_* — арбалет;
  trident_* — трезубец; fishing_* — удочка; block_experience —
    инструменты; mob_experience/equipment_drops — оружие в mainhand
    (лутинг-подобные «работают в руках»); post_piercing_attack —
    копья/трезубец (выпад — PiercingWeapon, 26.2 споры);
  item_damage/repair_with_xp — только предметы с прочностью;
  tick/location_changed/post_attack/damage_immunity/hit_block/
    prevent_equipment_drop/prevent_armor_change — ок везде (решение
    юзера; hit_block срабатывает ударом о блок ЛЮБЫМ предметом —
    ServerPlayerGameMode — и попаданием снаряда — AbstractArrow).
Профиль absurd («абсурд») — исключение: там любой набор (наш стиль).

ПОЛИТИКА БЕЗОПАСНОСТИ (требование юзера): зачарования НИКОГДА не наносят
прямой урон владельцу предмета (HP-урон: damage_entity, ignite,
instant_damage/poison/wither). Взрывы, импульсы, истощение, мобы, блоки —
можно. Реализация — три пула эффектов по контексту:
  FULL  — post_attack (цели задаются явно; повреждающие эффекты идут
          ТОЛЬКО противоположной стороне: enchanted=attacker → victim,
          enchanted=victim → attacker/damaging_entity);
  EVENT — post_piercing_attack/hit_block/projectile_spawned (this может
          оказаться владельцем) — без повреждающих эффектов;
  WORN  — tick/location_changed (эффект на носителе каждый тик/шаг) —
          только баффы и лёгкие эффекты (без урона, спам-призывов,
          взрывов и перезаписи блоков). Инвариант проверяет
  _owner_damage_violations() в самотесте.
"""

import json
import math
import random

# ---------------------------------------------------------------------------
# heavy_count — копия из generate_dimension.py (тяжёлый хвост количества)
# ---------------------------------------------------------------------------


def _heavy_count(rng, mean, big_min, big_max, big_p):
    if rng.random() < big_p:
        return int(round(math.exp(
            rng.uniform(math.log(big_min), math.log(big_max)))))
    n = 1 + int(rng.expovariate(1.0 / max(0.5, mean - 1)))
    return max(1, min(n, big_min - 1))


# ---------------------------------------------------------------------------
# Справочники (всё из jar 26.2)
# ---------------------------------------------------------------------------

# группы слотов (EquipmentSlotGroup, имена сериализации)
_SLOT_GROUPS = ["any", "mainhand", "offhand", "hand", "feet", "legs",
                "chest", "head", "armor", "body", "saddle"]

# теги items/enchantable/* (22 шт. из jar)
_ENCH_TAGS = ["melee_weapon", "sharp_weapon", "mace", "fire_aspect",
              "sweeping", "armor", "chest_armor", "foot_armor", "leg_armor",
              "head_armor", "bow", "crossbow", "trident", "fishing",
              "mining", "mining_loot", "durability", "equippable",
              "vanishing", "weapon"]

# прочие осмысленные теги предметов (для абсурдных сетов "копательный меч")
_OTHER_TAGS = ["swords", "pickaxes", "axes", "shovels", "hoes",
               "breaks_decorated_pots"]

# предметы для случайных списков supported_items (ванильные, проверенные)
_ITEMS = ["minecraft:diamond_sword", "minecraft:iron_sword",
          "minecraft:netherite_sword", "minecraft:wooden_sword",
          "minecraft:diamond_pickaxe", "minecraft:iron_shovel",
          "minecraft:bow", "minecraft:crossbow", "minecraft:trident",
          "minecraft:fishing_rod", "minecraft:shears",
          "minecraft:flint_and_steel", "minecraft:carrot_on_a_stick",
          "minecraft:warped_fungus_on_a_stick", "minecraft:elytra",
          "minecraft:shield", "minecraft:turtle_helmet",
          "minecraft:diamond_helmet", "minecraft:diamond_chestplate",
          "minecraft:diamond_leggings", "minecraft:diamond_boots",
          "minecraft:mace", "minecraft:brush", "minecraft:stick",
          "minecraft:bone", "minecraft:blaze_rod", "minecraft:ender_pearl",
          "minecraft:torch", "minecraft:ladder", "minecraft:tnt",
          "minecraft:golden_apple", "minecraft:book", "minecraft:name_tag",
          "minecraft:saddle", "minecraft:totem_of_undying",
          "minecraft:heart_of_the_sea", "minecraft:nautilus_shell",
          "minecraft:bread", "minecraft:cooked_beef", "minecraft:compass",
          "minecraft:clock", "minecraft:spyglass", "minecraft:bucket"]

# типы урона (data/minecraft/damage_type/, 51 шт. — выбраны безопасные)
_DAMAGE_TYPES = ["minecraft:generic", "minecraft:magic", "minecraft:arrow",
                 "minecraft:trident", "minecraft:spear", "minecraft:explosion",
                 "minecraft:player_explosion", "minecraft:fireball",
                 "minecraft:indirect_magic", "minecraft:mob_attack",
                 "minecraft:mob_projectile", "minecraft:player_attack",
                 "minecraft:thorns", "minecraft:sonic_boom", "minecraft:wither",
                 "minecraft:wither_skull", "minecraft:wind_charge",
                 "minecraft:falling_anvil", "minecraft:falling_block",
                 "minecraft:falling_stalactite", "minecraft:stalagmite",
                 "minecraft:mace_smash", "minecraft:freeze", "minecraft:cactus",
                 "minecraft:sweet_berry_bush", "minecraft:sting", "minecraft:spit"]

# теги типов урона для требований (ванильные требования protection-семейства)
_DAMAGE_TAGS = ["minecraft:is_fire", "minecraft:is_explosion",
                "minecraft:is_fall", "minecraft:is_projectile",
                "minecraft:is_freezing", "minecraft:is_lightning",
                "minecraft:is_drowning", "minecraft:burn_from_stepping"]

# мобы/теги для entity_properties -> minecraft:entity_type
_MOB_PREDS = ["minecraft:player", "minecraft:zombie", "minecraft:skeleton",
              "minecraft:creeper", "minecraft:spider", "minecraft:witch",
              "#minecraft:sensitive_to_smite",
              "#minecraft:sensitive_to_bane_of_arthropods",
              "#minecraft:sensitive_to_impaling", "#minecraft:undead",
              "#minecraft:arthropod", "#minecraft:aquatic",
              "#minecraft:arrows"]

# моб-эффекты (реестр mob_effect 26.2, сверено с MobEffects.class)
_MOB_EFFECTS = ["minecraft:speed", "minecraft:slowness", "minecraft:haste",
                "minecraft:mining_fatigue", "minecraft:strength",
                "minecraft:jump_boost", "minecraft:nausea",
                "minecraft:regeneration", "minecraft:resistance",
                "minecraft:fire_resistance", "minecraft:water_breathing",
                "minecraft:invisibility", "minecraft:blindness",
                "minecraft:night_vision", "minecraft:hunger",
                "minecraft:weakness", "minecraft:poison", "minecraft:wither",
                "minecraft:health_boost", "minecraft:absorption",
                "minecraft:saturation", "minecraft:glowing",
                "minecraft:levitation", "minecraft:luck", "minecraft:unluck",
                "minecraft:slow_falling", "minecraft:conduit_power",
                "minecraft:dolphins_grace", "minecraft:darkness",
                "minecraft:instant_health", "minecraft:instant_damage",
                "minecraft:bad_omen", "minecraft:hero_of_the_village",
                "minecraft:trial_omen", "minecraft:raid_omen",
                "minecraft:wind_charged", "minecraft:weaving",
                "minecraft:oozing", "minecraft:infested",
                "minecraft:breath_of_the_nautilus"]

# эффекты, наносящие ПРЯМОЙ урон носителю цели (HP сразу или тиком):
# их нельзя применять к владельцу зачарованного предмета (требование юзера:
# "урон владельцу нельзя, взрывы и прочее — можно")
_MOB_EFFECTS_HARMFUL = frozenset(["minecraft:instant_damage",
                                  "minecraft:poison", "minecraft:wither"])
_MOB_EFFECTS_SAFE = [e for e in _MOB_EFFECTS
                     if e not in _MOB_EFFECTS_HARMFUL]

# звуки (безопасное подмножество; часть прямо из ванильных зачарований)
_SOUNDS = ["minecraft:entity.lightning_bolt.impact",
           "minecraft:entity.lightning_bolt.thunder",
           "minecraft:item.trident.thunder",
           "minecraft:item.trident.riptide_1",
           "minecraft:item.trident.riptide_2",
           "minecraft:item.trident.riptide_3",
           "minecraft:item.trident.return",
           "minecraft:item.crossbow.quick_charge_1",
           "minecraft:item.crossbow.quick_charge_2",
           "minecraft:item.crossbow.quick_charge_3",
           "minecraft:item.crossbow.loading_end",
           "minecraft:entity.blaze.shoot", "minecraft:entity.wither.shoot",
           "minecraft:entity.enderman.teleport",
           "minecraft:entity.evoker.cast_spell",
           "minecraft:entity.generic.explode",
           "minecraft:entity.goat.screaming.ambient",
           "minecraft:entity.wind_charge.wind_burst",
           "minecraft:block.beacon.activate", "minecraft:block.anvil.use",
           "minecraft:block.amethyst_block.chime",
           "minecraft:block.fire.ambient", "minecraft:block.bell.use",
           "minecraft:block.glass.break", "minecraft:block.conduit.ambient",
           "minecraft:entity.player.attack.crit",
           "minecraft:entity.player.levelup"]

# частицы без параметров (голая строка в JSON)
_PARTICLES = ["minecraft:poof", "minecraft:crit", "minecraft:enchanted_hit",
              "minecraft:flame", "minecraft:soul_fire_flame",
              "minecraft:heart", "minecraft:cloud", "minecraft:smoke",
              "minecraft:splash", "minecraft:witch", "minecraft:lava",
              "minecraft:angry_villager", "minecraft:happy_villager",
              "minecraft:end_rod", "minecraft:sonic_boom", "minecraft:gust",
              "minecraft:sculk_soul", "minecraft:electric_spark",
              "minecraft:infested"]

# атрибуты: (id, min, max) — ванильный реестр attributes
_ATTRS = [
    ("minecraft:movement_speed", -0.02, 0.06),
    ("minecraft:movement_efficiency", 0.1, 1.0),
    ("minecraft:max_health", -2.0, 6.0),
    ("minecraft:max_absorption", 1.0, 4.0),
    ("minecraft:attack_damage", 0.5, 4.0),
    ("minecraft:attack_speed", -0.2, 0.5),
    ("minecraft:attack_knockback", 0.5, 2.0),
    ("minecraft:knockback_resistance", 0.05, 0.3),
    ("minecraft:explosion_knockback_resistance", 0.1, 0.5),
    ("minecraft:armor", 1.0, 4.0),
    ("minecraft:armor_toughness", 1.0, 3.0),
    ("minecraft:step_height", 0.2, 0.8),
    ("minecraft:jump_strength", 0.05, 0.3),
    ("minecraft:safe_fall_distance", 1.0, 5.0),
    ("minecraft:fall_damage_multiplier", -0.15, 0.1),
    ("minecraft:block_break_speed", 0.3, 2.0),
    ("minecraft:mining_efficiency", 0.5, 3.0),
    ("minecraft:submerged_mining_speed", 1.0, 4.0),
    ("minecraft:oxygen_bonus", 1.0, 5.0),
    ("minecraft:water_movement_efficiency", 0.2, 1.0),
    ("minecraft:sneaking_speed", 0.05, 0.3),
    ("minecraft:sweeping_damage_ratio", 0.1, 0.4),
    ("minecraft:scale", -0.05, 0.1),
    ("minecraft:gravity", -0.04, 0.02),
    ("minecraft:luck", 1.0, 3.0),
    ("minecraft:follow_range", 2.0, 8.0),
    ("minecraft:flying_speed", 0.01, 0.05),
]

# тематические пулы атрибутов по профилям (юзер: «attack-атрибуты — только
# weapon/melee; mining — только mining; броневые — только armor/equippable»;
# механически атрибут сработал бы из любого слота — EnchantmentHelper.
# forEachModifier не проверяет тип предмета, — но нечего вешать «урон в
# атаке» на шлем или «скорость добычи» на меч: компонента обязана иметь
# смысл на предметах профиля). _ATTRS хранит (id, lo, hi) — пул = подсеть
_ATTACK_ATTR_IDS = frozenset([
    "minecraft:attack_damage", "minecraft:attack_speed",
    "minecraft:attack_knockback", "minecraft:sweeping_damage_ratio"])
_MINING_ATTR_IDS = frozenset([
    "minecraft:block_break_speed", "minecraft:mining_efficiency",
    "minecraft:submerged_mining_speed"])
_ARMOR_ATTR_IDS = frozenset([
    "minecraft:armor", "minecraft:armor_toughness"])
# прочие (движение/здоровье/прыжок/удача/...) доступны всем профилям
_ALL_ATTR_IDS = frozenset(a[0] for a in _ATTRS)
_GENERAL_ATTR_IDS = (_ALL_ATTR_IDS - _ATTACK_ATTR_IDS - _MINING_ATTR_IDS
                      - _ARMOR_ATTR_IDS)

# профиль -> множество допустимых атрибутов (absurd = все)
_PROFILE_ATTR_IDS = {
    "weapon": _GENERAL_ATTR_IDS | _ATTACK_ATTR_IDS,
    "armor": _GENERAL_ATTR_IDS | _ARMOR_ATTR_IDS,
    "bow": _GENERAL_ATTR_IDS,
    "crossbow": _GENERAL_ATTR_IDS,
    "trident": _GENERAL_ATTR_IDS,
    "fishing": _GENERAL_ATTR_IDS,
    "mining": _GENERAL_ATTR_IDS | _MINING_ATTR_IDS,
    "elytra": _GENERAL_ATTR_IDS | _ARMOR_ATTR_IDS,   # носится в chest
    "shield": _GENERAL_ATTR_IDS | _ARMOR_ATTR_IDS,   # защитный предмет
    "saddle": _GENERAL_ATTR_IDS,                     # скакун: скорость/прыжок
    "book": _GENERAL_ATTR_IDS,
    "durability": _GENERAL_ATTR_IDS,                 # предметы смешанные
    "curse": _GENERAL_ATTR_IDS,
}


def _attr_pool(profile):
    """(id, lo, hi) из _ATTRS, допустимые для профиля (None/absurd = все)."""
    allowed = _PROFILE_ATTR_IDS.get(profile)
    if allowed is None:
        return list(_ATTRS)
    return [a for a in _ATTRS if a[0] in allowed]

# блоки для replace_*: (Name, Properties|None)
_BLOCKS = [
    ("minecraft:cobweb", None), ("minecraft:ice", None),
    ("minecraft:packed_ice", None), ("minecraft:magma_block", None),
    ("minecraft:obsidian", None), ("minecraft:glowstone", None),
    ("minecraft:sea_lantern", None), ("minecraft:sculk", None),
    ("minecraft:amethyst_block", None), ("minecraft:cobblestone", None),
    ("minecraft:stone", None), ("minecraft:dirt", None),
    ("minecraft:mud", None), ("minecraft:soul_sand", None),
    ("minecraft:slime_block", None), ("minecraft:honey_block", None),
    ("minecraft:lantern", {"hanging": "false"}),
    ("minecraft:frosted_ice", {"age": "0"}),
    ("minecraft:frosted_ice", {"age": "3"}),
    ("minecraft:crying_obsidian", None),
]

# свойства для set_block_properties (карта строка->строка, любой блок-цель)
_BLOCK_PROPS = [{"age": "3"}, {"age": "0"}, {"lit": "true"},
                {"lit": "false"}, {"waterlogged": "true"},
                {"waterlogged": "false"}, {"open": "true"},
                {"power": "15"}, {"hanging": "true"}, {"snowy": "true"}]

# кого призываем (summon_entity)
_ENTITIES = ["minecraft:lightning_bolt", "minecraft:evoker_fangs",
             "minecraft:area_effect_cloud", "minecraft:firework_rocket",
             "minecraft:tnt", "minecraft:wind_charge", "minecraft:armor_stand",
             "minecraft:creeper", "minecraft:silverfish", "minecraft:vex",
             "minecraft:endermite", "minecraft:experience_orb"]

# игровые события (реестр game_event, для trigger_game_event)
_GAME_EVENTS = ["minecraft:block_place", "minecraft:block_change",
                "minecraft:block_destroy"]

# взаимодействие взрыва с блоками (Level$ExplosionInteraction)
_EXPLODE_INTER = ["none", "trigger", "mob", "tnt", "block"]

# цвета текста описаний (как _NAME_COLORS в gen_loot)
_COLORS = (["gold"] * 3 + ["aqua"] * 3 + ["light_purple"] * 3 +
           ["red", "yellow", "green", "dark_aqua", "dark_purple",
            "dark_red", "blue", "white"])

# слова для русских названий. Прилагательные — ТОЛЬКО на ый/ой/ий:
# согласование родов делает _inflect_adj (притяжательные -ий после
# шипящих — Медвежий/Волчий/... — склоняются через _POSSESSIVE_ADJ).
# Существительные _NOUN — любой род; род определяет _noun_gender
# (эвристика _word_gender + _GENDER_EXC + мн.ч. _PLURAL_NOUNS).
_ADJ = [
    # --- исходные ---
    "Громовой", "Раскалённый", "Ледяной", "Проклятый", "Древний",
    "Забытый", "Пылающий", "Мерцающий", "Шепчущий", "Кровавый",
    "Соляной", "Жадный", "Вечный", "Голодный", "Бешеный", "Тихий",
    "Тёмный", "Светлый", "Зловонный", "Железный", "Хрупкий",
    "Глубинный", "Небесный", "Пустотный", "Ржавый", "Смоляной",
    "Кристальный", "Лунный", "Солнечный", "Слепящий", "Вонючий",
    "Хитрый", "Мудрый", "Гордый", "Злой", "Дикий", "Святой", "Гнилой",
    "Каменный", "Стеклянный",
    # --- времена суток и года ---
    "Рассветный", "Закатный", "Утренний", "Вечерний", "Ночной",
    "Полуденный", "Полуночный", "Осенний", "Зимний", "Весенний",
    "Летний", "Северный",
    # --- свет и цвет ---
    "Багряный", "Пурпурный", "Лазурный", "Изумрудный", "Аметистовый",
    "Янтарный", "Жемчужный", "Перламутровый", "Бирюзовый",
    "Сапфировый", "Рубиновый", "Малахитовый", "Радужный",
    "Переливчатый", "Сверкающий", "Лучезарный", "Светозарный",
    "Звёздный", "Солярный", "Чёрный", "Седой", "Ясный",
    # --- стихии и непогода ---
    "Знойный", "Снежный", "Морозный", "Студёный", "Ветряной",
    "Штормовой", "Приливный", "Грозный", "Туманный", "Мглистый",
    "Дымчатый", "Дымный", "Смрадный", "Угольный", "Огненный",
    "Пламенный", "Сумрачный", "Мрачный", "Кромешный", "Пекельный",
    "Бездонный", "Непроглядный", "Подземный", "Поднебесный",
    # --- лес и земля ---
    "Лесной", "Дремучий", "Хвойный", "Смолистый", "Дубовый",
    "Кедровый", "Ивовый", "Ясеневый", "Клёновый", "Терновый",
    "Корневой", "Вязкий", "Колкий", "Ключевой", "Родниковый",
    "Горный", "Скалистый", "Песчаный", "Пыльный",
    # --- звери и птицы (притяжательные — через _POSSESSIVE_ADJ) ---
    "Пернатый", "Соколиный", "Орлиный", "Совиный", "Пчелиный",
    "Журавлиный", "Крылатый", "Косматый", "Клыкастый", "Зубастый",
    "Рогатый", "Чешуйчатый", "Панцирный", "Хищный",
    "Медвежий", "Волчий", "Лисий", "Рыбий", "Паучий", "Кабаний",
    "Олений", "Пастуший", "Верблюжий", "Заячий", "Барсучий", "Бычий",
    # --- нрав и судьба ---
    "Свирепый", "Яростный", "Гневный", "Неистовый", "Лютый",
    "Стойкий", "Упрямый", "Дерзкий", "Буйный", "Мстительный",
    "Кощунный", "Скорбный", "Тоскливый", "Задумчивый", "Бродячий",
    "Одинокий", "Безмолвный", "Немой", "Ветхий", "Стремительный",
    "Молниеносный", "Непреклонный", "Несгибаемый", "Хитроумный",
    "Лукавый", "Коварный", "Жестокий", "Милосердный", "Смертный",
    "Заветный", "Потайной", "Заповедный", "Первозданный", "Незримый",
    # --- смерть и оккультное ---
    "Гробовой", "Могильный", "Курганный", "Окаменелый", "Трухлявый",
    "Колдовской", "Ведовской", "Заговорный", "Бесовский",
    "Дьявольский",
    # --- ремесло и звук ---
    "Кузнечный", "Кремнёвый", "Гулкий", "Звонкий", "Соловьиный",
]

_NOUN = [
    # --- исходные ---
    "Раскол", "Удар", "Гром", "Клык", "Глаз", "Вихрь", "Шёпот", "Рёв",
    "Скрежет", "Пляска", "Танец", "Хор", "Позыв", "Зов", "Предел",
    "Обет", "Зарок", "Нрав", "Пыл", "Гнёт", "Дар", "Суд", "Клинок",
    "Обломок", "Осколок", "Отголосок", "Приговор", "Переворот",
    "Сглаз", "Позор", "Гимн", "Прыжок", "Полёт", "Коварство",
    # --- погода и небо ---
    "Гроза", "Буря", "Метель", "Вьюга", "Пурга", "Ливень", "Стужа",
    "Зной", "Град", "Шторм", "Смерч", "Ураган", "Заря", "Рассвет",
    "Закат", "Восход", "Полночь", "Зарево", "Молния", "Зарница",
    "Искра", "Звезда",
    # --- тьма, свет и пламя ---
    "Морок", "Тьма", "Свет", "Мрак", "Тень", "Сумрак", "Мгла",
    "Туман", "Дым", "Смрад", "Пламя", "Пепел", "Пекло", "Тлен",
    "Прах",
    # --- вода и земля ---
    "Волна", "Прибой", "Прилив", "Водоворот", "Разлом", "Провал",
    "Столп", "Курган", "Порог", "Чертог", "Костёр",
    # --- материя и ремесло ---
    "Сплав", "Кристалл", "Наковальня", "Молот", "Клеймо", "Цепь",
    "Шрам", "Иней", "Корень", "Крыло", "Ветвь", "Лоза", "Слеза",
    "Узы",
    # --- звуки и голоса ---
    "Гул", "Раскат", "Грохот", "Треск", "Звон", "Скрип", "Шорох",
    "Свист", "Стон", "Смех", "Хохот", "Рык", "Вопль", "Молва",
    "Весть", "Голос", "Эхо", "Песнь", "Колокол", "Набат",
    # --- духи и сновидения ---
    "Дух", "Призрак", "Мираж", "Кошмар", "Сон", "Дрёма", "Грёза",
    "Забвение", "Исход", "Жребий", "Судьба", "Рок", "Бремя",
    "Кладезь",
    # --- клятвы и кары ---
    "Заговор", "Клятва", "Порыв", "Печать", "Венец", "Оберег",
    "Амулет", "Талисман", "Хоровод", "Игрище", "Тризна", "Грех",
    "Кара", "Расплата", "Возмездие", "Месть", "Гнев", "Ярость",
    "Ужас", "Тоска", "Печаль", "Скорбь", "Надежда", "Час", "Миг",
    "Круг",
]

_GEN = [
    # --- исходные ---
    "Бездны", "Пустоты", "Соли", "Мешка Соли", "Глубин", "Вечности",
    "Грозы", "Обсидиана", "Пепла", "Искр", "Тьмы", "Зари", "Пекла",
    "Скалы", "Костей", "Долга", "Утра", "Полуночи", "Медузы",
    "Тритона", "Копателя", "Кузнеца", "Гробовщика", "Пустельги",
    "Хребта", "Пучины", "Пустоши", "Луны", "Гнили", "Углей", "Мороза",
    "Вихря", "Отражения", "Сумерек", "Ясеня", "Чеснока",
    # --- места ---
    "Пепелища", "Корней", "Подземья", "Вершины", "Утёса", "Провала",
    "Теснины", "Кургана", "Рудника", "Долины", "Оврага", "Обрыва",
    "Пещеры", "Топи", "Болота", "Омута", "Перекрёстка", "Тропы",
    "Океана", "Моря", "Небес",
    # --- времена и непогода ---
    "Метели", "Стужи", "Пурги", "Вьюги", "Града", "Зимы", "Затмения",
    "Рассвета", "Заката", "Восхода", "Полудня", "Ночи", "Вечера",
    "Шторма", "Прибоя", "Водоворота", "Смерча", "Урагана", "Бури",
    "Лавины", "Ветра", "Тумана", "Костра",
    # --- материя и стихии ---
    "Слёз", "Крови", "Праха", "Тлена", "Морока", "Мглы", "Тени",
    "Дыма", "Смрада", "Молний", "Зарниц", "Звёзд", "Светил",
    "Когтей", "Чешуи", "Крыльев", "Перьев", "Свечи",
    # --- люд фольклорный ---
    "Охотника", "Мельника", "Волхва", "Вещуна", "Колдуна", "Ведьмы",
    "Упыря", "Русалки", "Лешего", "Кикиморы", "Витязя", "Богатыря",
    "Палача", "Изгоя", "Странника", "Плута", "Стаи", "Логова",
    # --- судьба и быт ---
    "Тишины", "Судьбы", "Жатвы", "Потока", "Водопада", "Вереска",
    "Осины", "Вербы", "Терновника", "Волчьей Ягоды", "Мёртвой Воды",
    "Третьего Рассвета", "Кваса", "Киселя",
]


# ---------------------------------------------------------------------------
# Мелкие помощники
# ---------------------------------------------------------------------------


def _f(rng, lo, hi):
    """Равномерный float, округлённый до 3 знаков (чистый JSON)."""
    return round(rng.uniform(lo, hi), 3)


def _chance(rng, p):
    return rng.random() < p


def _pick_w(rng, pairs):
    """Взвешенный выбор из [(значение, вес), ...]."""
    vals, weights = zip(*pairs)
    return rng.choices(vals, weights=weights, k=1)[0]


# ---------------------------------------------------------------------------
# LevelBasedValue / ValueEffect / требования
# ---------------------------------------------------------------------------


def _lbv(rng, lo, hi, per_lo=0.0, per_hi=0.0):
    """Случайный LevelBasedValue (все 6 форм + константа)."""
    r = rng.random()
    if r < 0.48:  # ванильная классика
        return {"type": "minecraft:linear",
                "base": _f(rng, lo, hi),
                "per_level_above_first": _f(rng, per_lo, per_hi)}
    if r < 0.66:  # голая константа (как radius 3.5 у wind_burst)
        return _f(rng, lo, hi)
    if r < 0.74:
        val = {"type": "minecraft:linear", "base": _f(rng, lo, hi),
               "per_level_above_first": _f(rng, per_lo, per_hi)}
        return {"type": "minecraft:clamped", "value": val,
                "min": _f(rng, min(lo, 0.0), lo), "max": _f(rng, hi, hi * 2.5)}
    if r < 0.82:
        return {"type": "minecraft:levels_squared",
                "added": _f(rng, lo / 4.0 if lo > 0 else lo / 8.0, hi / 4.0)}
    if r < 0.89:
        num = _f(rng, lo, hi)
        return {"type": "minecraft:fraction",
                "numerator": num if _chance(rng, 0.5)
                else {"type": "minecraft:linear", "base": num,
                      "per_level_above_first": _f(rng, per_lo, per_hi)},
                "denominator": _f(rng, 1.0, 3.0)}
    if r < 0.96:
        n = rng.randint(2, 4)
        return {"type": "minecraft:lookup",
                "values": [_f(rng, lo, hi) for _ in range(n)],
                "fallback": {"type": "minecraft:linear",
                             "base": _f(rng, lo, hi),
                             "per_level_above_first": _f(rng, per_lo, per_hi)}}
    # exponent — редко (в ванили нет, но кодек есть)
    return {"type": "minecraft:exponent",
            "base": _f(rng, max(lo, 0.1), max(hi, 0.2)),
            "power": _f(rng, 0.5, 2.0)}


def _value_effect(rng, lo, hi, per_lo=0.0, per_hi=0.0,
                  allow_set=False, allow_binom=False):
    """Случайный ValueEffect с разумным масштабом."""
    r = rng.random()
    if r < 0.60:
        return {"type": "minecraft:add", "value": _lbv(rng, lo, hi, per_lo, per_hi)}
    if r < 0.74:
        # множитель около 1.0, знак берём из диапазона
        span = max(abs(lo), abs(hi), 0.05)
        factor = 1.0 + rng.uniform(-span, span) * 0.4
        return {"type": "minecraft:multiply", "factor": round(factor, 3)}
    if r < 0.74 + (0.14 if allow_set else 0.0):
        return {"type": "minecraft:set", "value": _f(rng, min(lo, 0.0), hi)}
    if allow_binom and _chance(rng, 0.5):
        return {"type": "minecraft:remove_binomial", "chance": _lbv(rng, 0.1, 0.9)}
    if r > 0.96:
        # exponential (ScaleExponentially 26.2, поля base/exponent, оба LBV):
        # итог = value * base^exponent. Знакосообразно: для «уменьшающих»
        # компонент (charge_time и др., hi <= 0) base < 1 — множитель < 1
        span = max(abs(lo), abs(hi), 0.05)
        if hi <= 0:
            base = _lbv(rng, max(0.5, 1.0 - span), 1.0)
        else:
            base = _lbv(rng, 1.0, min(2.0, 1.0 + span))
        return {"type": "minecraft:exponential",
                "base": base, "exponent": _lbv(rng, 0.5, 1.6)}
    if r > 0.93:  # all_of из двух
        return {"type": "minecraft:all_of", "effects": [
            {"type": "minecraft:add", "value": _lbv(rng, lo, hi, per_lo, per_hi)},
            {"type": "minecraft:multiply", "factor": round(
                1.0 + rng.uniform(-0.1, 0.25), 3)}]}
    return {"type": "minecraft:add", "value": _lbv(rng, lo, hi, per_lo, per_hi)}


def _rq_chance(rng):
    """random_chance — параметров контекста не требует, безопасен везде."""
    if _chance(rng, 0.5):
        return {"condition": "minecraft:random_chance",
                "chance": round(rng.uniform(0.05, 0.8), 2)}
    amt = _f(rng, 0.04, 0.2)
    if _chance(rng, 0.5):
        amt = {"type": "minecraft:linear", "base": amt,
               "per_level_above_first": _f(rng, 0.05, 0.2)}
    return {"condition": "minecraft:random_chance",
            "chance": {"type": "minecraft:enchantment_level", "amount": amt}}


def _rq_dmg_source(rng):
    """damage_source_properties — контекст enchanted_damage (protection и др.)."""
    if _chance(rng, 0.4):
        return {"condition": "minecraft:damage_source_properties",
                "predicate": {"is_direct": True}}
    return {"condition": "minecraft:damage_source_properties",
            "predicate": {"tags": [
                {"expected": True, "id": rng.choice(_DAMAGE_TAGS)},
                {"expected": False, "id": "minecraft:bypasses_invulnerability"}]}}


def _rq_this_type(rng):
    return {"condition": "minecraft:entity_properties", "entity": "this",
            "predicate": {"minecraft:entity_type": rng.choice(_MOB_PREDS)}}


def _rq_direct_type(rng):
    """direct_attacker — только в контексте enchanted_damage (power.json)."""
    return {"condition": "minecraft:entity_properties",
            "entity": "direct_attacker",
            "predicate": {"minecraft:entity_type": rng.choice(_MOB_PREDS)}}


def _rq_match_tool(rng):
    """match_tool — только enchanted_item (unbreaking, infinity)."""
    return {"condition": "minecraft:match_tool",
            "predicate": {"items": rng.choice(
                ["minecraft:arrow", "#minecraft:enchantable/armor",
                 "#minecraft:enchantable/weapon", "#minecraft:swords"])}}


def _rq_no_match_tool(rng):
    return {"condition": "minecraft:inverted", "term": _rq_match_tool(rng)}


def _rq_this_flags(rng):
    flags = {}
    for key, val in (("is_on_ground", True), ("is_flying", False),
                     ("is_in_water", False), ("is_fall_flying", False)):
        if _chance(rng, 0.4):
            flags[key] = val
    if not flags:
        flags = {"is_on_ground": True}
    return {"condition": "minecraft:entity_properties", "entity": "this",
            "predicate": {"minecraft:flags": flags}}


def _rq_no_vehicle(rng):
    return {"condition": "minecraft:inverted",
            "term": {"condition": "minecraft:entity_properties",
                     "entity": "this",
                     "predicate": {"minecraft:vehicle": {}}}}


def _rq_weather(rng):
    if _chance(rng, 0.5):
        return {"condition": "minecraft:weather_check", "thundering": True}
    return {"condition": "minecraft:weather_check", "raining": True}


def _rq_location_check(rng):
    """location_check — только hit_block (channeling)."""
    if _chance(rng, 0.5):
        return {"condition": "minecraft:location_check",
                "predicate": {"can_see_sky": True}}
    return {"condition": "minecraft:location_check",
            "predicate": {"block": {"blocks": "#minecraft:lightning_rods"},
                          "can_see_sky": True}}


# Контексты (LootContextParamSets, 26.2): требования каждой компоненты
# валидируются на ЗАГРУЗКЕ по её ContextKeySet — пул условий обязан
# соответствовать контексту (проверено на реальном сервере):
#   enchanted_damage: this_entity+origin+damage_source(+optional direct/attacker)
#   enchanted_item:   tool+enchantment_level
#   enchanted_location/enchanted_entity: this_entity+origin
#   hit_block:        this_entity+origin+block_state
#   projectile_*:     параметров почти нет — только random_chance
_REQ_DAMAGE_POOL = [_rq_chance, _rq_dmg_source, _rq_this_type, _rq_direct_type]
_REQ_ITEM_POOL = [_rq_match_tool, _rq_no_match_tool, _rq_chance]
_REQ_ENTITY_POOL = [_rq_chance, _rq_this_flags, _rq_this_type, _rq_no_vehicle]
_REQ_HIT_POOL = [_rq_weather, _rq_this_type, _rq_location_check]
_REQ_PROJECTILE_POOL = [_rq_chance]

_REQ_POOLS = {
    "damage": _REQ_DAMAGE_POOL,
    "damage_protection": _REQ_DAMAGE_POOL,
    "smash_damage_per_fallen_block": _REQ_DAMAGE_POOL,
    "knockback": _REQ_DAMAGE_POOL,
    "armor_effectiveness": _REQ_DAMAGE_POOL,
    "item_damage": _REQ_ITEM_POOL,
    "ammo_use": _REQ_ITEM_POOL,
    "post_attack": _REQ_DAMAGE_POOL,
    "post_piercing_attack": _REQ_ENTITY_POOL,
    "hit_block": _REQ_HIT_POOL,
    "tick": _REQ_ENTITY_POOL,
    "location_changed": _REQ_ENTITY_POOL,
    "projectile_spawned": _REQ_PROJECTILE_POOL,
    "projectile_piercing": _REQ_PROJECTILE_POOL,
    "projectile_spread": _REQ_PROJECTILE_POOL,
    "projectile_count": _REQ_PROJECTILE_POOL,
    # fishing_*, block/mob_experience, repair_with_xp, trident_*,
    # crossbow_*, attributes, prevent_* — требований не генерируем
    # (в ванили их тоже нет; equipment_drops/damage_immunity — свои шаблоны)
}


def _req(rng, pool):
    """Условие из пула контекста, иногда связка all_of/any_of."""
    if _chance(rng, 0.3):
        op = rng.choice(["minecraft:all_of", "minecraft:any_of"])
        return {"condition": op, "terms": [rng.choice(pool)(rng),
                                           rng.choice(pool)(rng)]}
    return rng.choice(pool)(rng)


def _req_damage(rng):
    """Требование в стиле protection-семейства (по тегу урона)."""
    return _rq_dmg_source(rng)


# ---------------------------------------------------------------------------
# Сущностные / локационные эффекты
# ---------------------------------------------------------------------------


def _state_provider(rng):
    name, props = rng.choice(_BLOCKS)
    state = {"Name": name}
    if props:
        state["Properties"] = props
    return {"type": "minecraft:simple_state_provider", "state": state}


def _block_predicate(rng):
    """Worldgen BlockPredicate (как у frost_walker)."""
    k = rng.randint(0, 2)
    if k == 0:
        return {"type": "minecraft:matching_blocks",
                "blocks": rng.choice(["minecraft:water", "minecraft:stone",
                                      "minecraft:dirt", "minecraft:grass_block"])}
    if k == 1:
        return {"type": "minecraft:replaceable"}
    return {"type": "minecraft:all_of", "predicates": [
        {"type": "minecraft:matching_block_tag", "offset": [0, 1, 0],
         "tag": "minecraft:air"},
        {"type": "minecraft:matching_fluids", "fluids": "minecraft:water"}]}


def _float_provider(rng, lo, hi):
    # FloatProvider: голое число ИЛИ uniform с min_inclusive/max_exclusive
    if _chance(rng, 0.6):
        return _f(rng, lo, hi)
    a, b = sorted([_f(rng, lo, hi), _f(rng, lo, hi)])
    return {"type": "minecraft:uniform", "min_inclusive": a,
            "max_exclusive": max(b, a + 0.01)}


def _particle(rng):
    # ParticleTypes.CODEC в 26.2 требует ОБЪЕКТ {"type": ...}, голая строка
    # не парсится ("Not a JSON object") — проверено на сервере
    return {"type": rng.choice(_PARTICLES)}


def _pos_source(rng):
    # PositionSourceType — StringRepresentable enum: имена БЕЗ префикса
    # minecraft: ("entity_position", "in_bounding_box"). entity_position
    # НЕЛЬЗЯ масштабировать — поле scale только у in_bounding_box
    # ("Cannot scale an entity position coordinate source")
    if _chance(rng, 0.7):
        d = {"type": "entity_position"}
        if _chance(rng, 0.6):
            d["offset"] = _f(rng, 0.0, 1.0)
        return d
    d = {"type": "in_bounding_box"}
    if _chance(rng, 0.4):
        d["scale"] = _f(rng, 0.5, 1.5)
    return d


def _vel_source(rng):
    d = {}
    if _chance(rng, 0.6):
        d["movement_scale"] = _f(rng, 0.0, 1.0)
    if _chance(rng, 0.7):
        d["base"] = _float_provider(rng, 0.0, 0.4)
    return d


def _mk_apply_mob_effect(pool):
    """apply_mob_effect над заданным пулом эффектов (полный или safe)."""
    def _mk(rng, _fid=None):
        n = rng.randint(1, 3)
        effs = rng.sample(pool, n)
        # длительности КРУПНЕЕ (юзер: «накладывают на очень короткое
        # время»): было 20-400 тиков (1-20 с) — стало 100-1200 (5-60 с,
        # в среднем ~30 с — как зелья ванили)
        mn_d, mx_d = sorted([_f(rng, 100, 600), _f(rng, 300, 1200)])
        mn_a, mx_a = sorted([_f(rng, 0, 2), _f(rng, 0, 2)])
        if _chance(rng, 0.3):  # иногда длительность/усиление растут с уровнем
            mn_d = _lbv(rng, 100, 400, 50, 300)
            mx_d = _lbv(rng, 400, 900, 100, 600)
        if _chance(rng, 0.2):
            mn_a, mx_a = _lbv(rng, 0, 1, 0, 1), _lbv(rng, 0, 2, 0, 1)
        return {"type": "minecraft:apply_mob_effect",
                "to_apply": effs[0] if n == 1 else effs,
                "min_duration": mn_d, "max_duration": mx_d,
                "min_amplifier": mn_a, "max_amplifier": mx_a}
    return _mk


_ee_apply_mob_effect = _mk_apply_mob_effect(_MOB_EFFECTS)
_ee_apply_mob_effect_safe = _mk_apply_mob_effect(_MOB_EFFECTS_SAFE)


def _ee_change_item_damage(rng, _fid=None):
    return {"type": "minecraft:change_item_damage",
            "amount": _chance(rng, 0.6) and _f(rng, 1, 6) or
            _lbv(rng, 1, 4, 0.5, 3)}


def _ee_damage_entity(rng, _fid=None):
    mn, mx = sorted([_f(rng, 1, 8), _f(rng, 1, 8)])
    return {"type": "minecraft:damage_entity", "min_damage": mn,
            "max_damage": mx, "damage_type": rng.choice(_DAMAGE_TYPES)}


def _ee_ignite(rng, _fid=None):
    return {"type": "minecraft:ignite",
            "duration": _chance(rng, 0.5) and _f(rng, 20, 200) or
            _lbv(rng, 20, 100, 10, 50)}


def _ee_apply_impulse(rng, _fid=None):
    direction = [rng.choice([0, 0, 1, -1]), rng.choice([0, 0, 1, -1]),
                 rng.choice([0, 1, -1])]
    if not any(direction):
        direction = [0, 0, 1]
    cs = [1, 1, 1]
    if _chance(rng, 0.4):
        cs = [rng.choice([0, 1]), rng.choice([0, 1]), rng.choice([0, 1])]
        if not any(cs):
            cs = [1, 1, 1]
    return {"type": "minecraft:apply_impulse", "direction": direction,
            "coordinate_scale": cs,
            "magnitude": _lbv(rng, 0.2, 1.2, 0.1, 0.5)}


def _ee_apply_exhaustion(rng, _fid=None):
    return {"type": "minecraft:apply_exhaustion",
            "amount": _lbv(rng, 0.5, 4.0, 0.5, 3.0)}


def _ee_play_sound(rng, _fid=None):
    n = rng.randint(1, 3)
    snds = rng.sample(_SOUNDS, n)
    return {"type": "minecraft:play_sound",
            "sound": snds[0] if n == 1 else snds,
            "volume": _f(rng, 0.5, 5.0), "pitch": _f(rng, 0.6, 1.6)}


def _ee_replace_block(rng, _fid=None):
    d = {"type": "minecraft:replace_block",
         "offset": [rng.randint(-3, 3), rng.randint(-3, 3), rng.randint(-3, 3)],
         "block_state": _state_provider(rng)}
    if _chance(rng, 0.4):
        d["predicate"] = _block_predicate(rng)
    if _chance(rng, 0.3):
        d["trigger_game_event"] = rng.choice(_GAME_EVENTS)
    return d


def _ee_replace_disk(rng, _fid=None):
    d = {"type": "minecraft:replace_disk",
         "radius": _lbv(rng, 1, 5, 0.5, 2),
         "height": _f(rng, 0.5, 2.0),
         "offset": [0, -1, 0] if _chance(rng, 0.7)
         else [0, rng.randint(-1, 1), 0],
         "block_state": _state_provider(rng)}
    if _chance(rng, 0.35):
        d["predicate"] = _block_predicate(rng)
    if _chance(rng, 0.3):
        d["trigger_game_event"] = rng.choice(_GAME_EVENTS)
    return d


def _ee_set_block_properties(rng, _fid=None):
    d = {"type": "minecraft:set_block_properties",
         "properties": dict(rng.choice(_BLOCK_PROPS))}
    if _chance(rng, 0.5):
        d["offset"] = [rng.randint(-1, 1), rng.randint(-1, 1), rng.randint(-1, 1)]
    if _chance(rng, 0.25):
        d["trigger_game_event"] = rng.choice(_GAME_EVENTS)
    return d


def _ee_spawn_particles(rng, _fid=None):
    d = {"type": "minecraft:spawn_particles",
         "particle": _particle(rng),
         "horizontal_position": _pos_source(rng),
         "vertical_position": _pos_source(rng),
         "horizontal_velocity": _vel_source(rng),
         "vertical_velocity": _vel_source(rng)}
    if _chance(rng, 0.6):
        d["speed"] = _f(rng, 0.01, 0.2)
    return d


def _ee_summon_entity(rng, _fid=None):
    n = rng.randint(1, 2)
    ents = rng.sample(_ENTITIES, n)
    return {"type": "minecraft:summon_entity",
            "entity": ents[0] if n == 1 else ents,
            "join_team": _chance(rng, 0.2)}


def _ee_explode(rng, _fid=None):
    # в 26.2 у explode ОБЯЗАТЕЛЬНЫ small_particle, large_particle и sound
    # (проверено на сервере: "No key sound/large_particle/small_particle")
    d = {"type": "minecraft:explode",
         "radius": _chance(rng, 0.5) and _f(rng, 1, 4) or _lbv(rng, 1, 3, 0.5, 1.5),
         "block_interaction": _pick_w(rng, [("none", 4), ("trigger", 3),
                                            ("mob", 2), ("tnt", 1), ("block", 1)]),
         "damage_type": rng.choice(_DAMAGE_TYPES),
         "small_particle": _particle(rng),
         "large_particle": _particle(rng),
         "sound": rng.choice(_SOUNDS)}
    if _chance(rng, 0.3):
        d["offset"] = [0.0, _f(rng, 0.1, 0.5), 0.0]
    if _chance(rng, 0.3):
        d["create_fire"] = True
    if _chance(rng, 0.3):
        d["knockback_multiplier"] = _lbv(rng, 1.0, 2.5, 0.2, 0.8)
    if _chance(rng, 0.2):
        d["immune_blocks"] = "#minecraft:dragon_immune"
    return d


def _ee_run_function(rng, func_id):
    # функция с id зачарования; проверка существования — только в рантайме
    return {"type": "minecraft:run_function", "function": func_id}


_EE_BUILDERS = [
    (_ee_apply_mob_effect, 14), (_ee_change_item_damage, 9),
    (_ee_damage_entity, 10), (_ee_ignite, 7), (_ee_apply_impulse, 7),
    (_ee_apply_exhaustion, 5), (_ee_play_sound, 11),
    (_ee_replace_block, 6), (_ee_replace_disk, 4),
    (_ee_set_block_properties, 5), (_ee_spawn_particles, 9),
    (_ee_summon_entity, 7), (_ee_explode, 4), (_ee_run_function, 48),
]


def _is_damaging_effect(d):
    """True, если эффект наносит ПРЯМОЙ урон цели (HP-урон сразу или тиком).

    Такими эффектами нельзя бить владельца зачарованного предмета (требование
    юзера). Взрывы/импульсы/истощение — НЕ прямой урон, разрешены где угодно.
    """
    t = d.get("type")
    if t in ("minecraft:damage_entity", "minecraft:ignite"):
        return True
    if t == "minecraft:apply_mob_effect":
        ta = d.get("to_apply")
        ta = [ta] if isinstance(ta, str) else (ta or [])
        return any(e in _MOB_EFFECTS_HARMFUL for e in ta)
    if t == "minecraft:all_of":
        return any(_is_damaging_effect(e) for e in d.get("effects", []))
    return False


# Пулы эффектов по контексту применения:
#   FULL  — только post_attack: цели задаются явно (attacker/victim/
#           damaging_entity), повреждающие эффекты маршрутизируются на врага;
#   EVENT — post_piercing_attack/hit_block/projectile_spawned: событие
#           попадания, сущность this может оказаться владельцем → прямой
#           урон запрещён, но взрывы/призывы/блоки — можно;
#   WORN  — tick/location_changed: эффект применяется к НОСИТЕЛЮ каждый
#           тик/шаг → без прямого урона И без тяжёлого спама (summon/explode/
#           replace_* каждый тик разорвали бы мир), только баффы/лёгкое.
_EE_BUILDERS_EVENT = [
    (_ee_apply_mob_effect_safe, 14), (_ee_change_item_damage, 9),
    (_ee_apply_impulse, 7), (_ee_apply_exhaustion, 5),
    (_ee_play_sound, 11), (_ee_replace_block, 6), (_ee_replace_disk, 4),
    (_ee_set_block_properties, 5), (_ee_spawn_particles, 9),
    (_ee_summon_entity, 7), (_ee_explode, 4), (_ee_run_function, 48),
]
_EE_BUILDERS_WORN = [
    (_ee_apply_mob_effect_safe, 14), (_ee_apply_impulse, 6),
    (_ee_apply_exhaustion, 4), (_ee_play_sound, 11),
    (_ee_spawn_particles, 9), (_ee_run_function, 30),
]


def _entity_effect(rng, func_id, pool=None):
    """Случайный EntityEffect из пула контекста (в all_of — вложенность)."""
    if pool is None:
        pool = _EE_BUILDERS
    if _chance(rng, 0.07):
        inner = [_pick_w(rng, pool)(rng, func_id) for _ in range(2)]
        return {"type": "minecraft:all_of", "effects": inner}
    return _pick_w(rng, pool)(rng, func_id)


def _location_effect(rng, attr_id, func_id, profile=None):
    """Эффект для location_changed (те же типы + attribute).

    location_changed применяется к носителю при движении (frost_walker) —
    только WORN-пул: никакого урона владельцу и спама каждый шаг.
    Атрибуты — из тематического пула профиля (как у компоненты attributes)."""
    if _chance(rng, 0.45):
        aid, lo, hi = rng.choice(_attr_pool(profile))
        return {"type": "minecraft:attribute", "id": attr_id,
                "attribute": aid, "amount": _lbv(rng, lo, hi, lo, hi),
                "operation": _pick_w(rng, [("add_value", 7),
                                           ("add_multiplied_base", 2),
                                           ("add_multiplied_total", 2)])}
    return _entity_effect(rng, func_id, _EE_BUILDERS_WORN)


# ---------------------------------------------------------------------------
# Построители компонент эффектов (ключ -> значение в "effects")
# ---------------------------------------------------------------------------

# масштабы ValueEffect для "числовых" компонент: (lo, hi, per_lo, per_hi)
_VE_SCALES = {
    "damage": (0.5, 5.0, 0.3, 2.5),
    "damage_protection": (0.5, 2.0, 0.3, 1.2),
    "smash_damage_per_fallen_block": (0.05, 0.6, 0.05, 0.4),
    "knockback": (0.5, 3.0, 0.5, 2.0),
    "armor_effectiveness": (0.05, 0.3, 0.03, 0.2),
    "item_damage": (1.0, 5.0, 0.5, 3.0),
    "ammo_use": (-1.0, 1.0, -0.5, 0.5),
    "projectile_piercing": (1.0, 4.0, 0.5, 2.0),
    "projectile_spread": (1.0, 10.0, 1.0, 6.0),
    "projectile_count": (1.0, 4.0, 1.0, 3.0),
    "trident_return_acceleration": (0.5, 3.0, 0.5, 2.0),
    "fishing_time_reduction": (1.0, 10.0, 1.0, 6.0),
    "fishing_luck_bonus": (1.0, 5.0, 0.5, 3.0),
    "block_experience": (0.5, 2.0, 0.3, 1.5),
    "mob_experience": (1.0, 5.0, 0.5, 3.0),
    "repair_with_xp": (1.5, 4.0, 0.5, 2.0),
    "crossbow_charge_time": (-0.4, -0.1, -0.3, -0.05),
    "trident_spin_attack_strength": (0.5, 3.0, 0.3, 2.0),
    "equipment_drops": (0.01, 0.05, 0.01, 0.03),
}


def _cond_list(rng, effect, req_prob, func_id, pool=None):
    """Список ConditionalEffect: 1 (80%) или 2 (20%) записи.

    Требования берутся ТОЛЬКО из пула контекста этой компоненты — иначе
    сервер 26.2 отвергает зачарование на загрузке ("Parameters ... are not
    provided in this context").
    """
    out = []
    for _ in range(1 if _chance(rng, 0.8) else 2):
        entry = {"effect": effect(rng, func_id)}
        if pool and _chance(rng, req_prob):
            entry["requirements"] = _req(rng, pool)
        out.append(entry)
    return out


def _build_ve_component(key):
    lo, hi, plo, phi = _VE_SCALES[key]
    # у ammo_use бывает "set 0" (infinity), у charge_time знак важен
    allow_set = key in ("ammo_use", "crossbow_charge_time")
    allow_binom = key in ("item_damage", "ammo_use")
    pool = _REQ_POOLS.get(key)

    def build(rng, func_id, _profile=None):
        return _cond_list(
            rng,
            lambda r, fid: _value_effect(r, lo, hi, plo, phi,
                                         allow_set=allow_set,
                                         allow_binom=allow_binom),
            0.45, func_id, pool)
    return build


def _build_single_ve(key):
    lo, hi, plo, phi = _VE_SCALES[key]

    def build(rng, _func_id, _profile=None):
        return _value_effect(rng, lo, hi, plo, phi, allow_set=True)
    return build


def _build_ee_component(key, pool):
    ctx_pool = pool

    def build(rng, func_id, _profile=None):
        return _cond_list(rng, lambda r, fid: _entity_effect(r, fid, ctx_pool),
                          0.55, func_id, _REQ_POOLS.get(key))
    return build


def _build_damage_immunity(rng, _func_id, _profile=None):
    # DamageImmunity — unit-кодек, эффект строго {}; требования по тегу урона
    out = []
    for _ in range(1 if _chance(rng, 0.85) else 2):
        entry = {"effect": {}}
        if _chance(rng, 0.9):
            entry["requirements"] = _req_damage(rng)
        out.append(entry)
    return out


def _build_post_attack(rng, _func_id, _profile=None):
    # TargetedConditionalEffect: enchanted — у кого зачарованный предмет,
    # affected — на кого действует (ванильный thorns: enchanted=victim,
    # affected=attacker).
    #
    # ПРАВИЛО БЕЗОПАСНОСТИ: прямой урон (damage_entity/ignite/instant_damage/
    # poison/wither) — только ПРОТИВОПОЛОЖНОЙ стороне. enchanted=attacker →
    # владельцем является attacker (и damaging_entity при прямом ударе —
    # это он же), урон идёт только на victim; enchanted=victim → владелец
    # victim, урон идёт на attacker/damaging_entity (как шипы/огонь).
    # НЕ-урон (импульс, звук, частицы, баффы, взрыв...) — на кого угодно.
    #
    # ИСКЛЮЧЕНИЕ для run_function: команда исполняется ОТ ЛИЦА affected
    # (байткод RunFunction: withEntity(affected), позиция/поворот — его же)
    # — маршрутизируем на enchanted (= владелец предмета), чтобы @s
    # внутри mcfunction всегда был владельцем (самобаффы, «клыки»
    # по взгляду и т.д. — см. _gen_ench_function, контекст full).
    out = []
    for _ in range(1 if _chance(rng, 0.75) else 2):
        enchanted = rng.choice(["attacker", "victim"])
        effect = _entity_effect(rng, _func_id, _EE_BUILDERS)
        if _is_damaging_effect(effect):
            affected = ("victim" if enchanted == "attacker"
                        else rng.choice(["attacker", "damaging_entity"]))
        elif _has_run_function(effect):
            affected = enchanted
        else:
            affected = rng.choice(["attacker", "victim", "damaging_entity"])
        entry = {"enchanted": enchanted, "affected": affected,
                 "effect": effect}
        if _chance(rng, 0.6):
            entry["requirements"] = _req(rng, _REQ_DAMAGE_POOL)
        out.append(entry)
    return out


def _build_equipment_drops(rng, _func_id, _profile=None):
    # как у looting: effect — ValueEffect, enchanted=attacker
    lo, hi, plo, phi = _VE_SCALES["equipment_drops"]
    entry = {"enchanted": "attacker", "affected": rng.choice(
        ["attacker", "victim"]),
        "effect": _value_effect(rng, lo, hi, plo, phi)}
    if _chance(rng, 0.5):
        entry["requirements"] = {"condition": "minecraft:entity_properties",
                                 "entity": "attacker",
                                 "predicate": {"minecraft:entity_type":
                                               "minecraft:player"}}
    return [entry]


def _build_location_changed(rng, func_id, profile=None):
    out = []
    for _ in range(1 if _chance(rng, 0.8) else 2):
        entry = {"effect": _location_effect(rng, func_id + "_loc", func_id,
                                            profile)}
        if _chance(rng, 0.65):
            entry["requirements"] = _req(rng, _REQ_ENTITY_POOL)
        out.append(entry)
    return out


def _build_attributes(rng, attr_id, profile=None):
    # НЕ conditional: список {amount, attribute, id, operation}; атрибуты —
    # из тематического пула профиля (attack — оружию, mining — инструментам,
    # броня — броне; см. _PROFILE_ATTR_IDS)
    pool = _attr_pool(profile)
    out = []
    for i in range(rng.randint(1, 3)):
        aid, lo, hi = rng.choice(pool)
        out.append({
            "amount": _lbv(rng, lo, hi, lo, hi),
            "attribute": aid,
            "id": "%s_a%d" % (attr_id, i),
            "operation": _pick_w(rng, [("add_value", 7),
                                       ("add_multiplied_base", 2),
                                       ("add_multiplied_total", 2)])})
    return out


def _build_charging_sounds(rng, _attr_id, _profile=None):
    n = rng.randint(1, 3)
    starts = ["minecraft:item.crossbow.quick_charge_1",
              "minecraft:item.crossbow.quick_charge_2",
              "minecraft:item.crossbow.quick_charge_3"]
    return [{"start": s, "end": "minecraft:item.crossbow.loading_end"}
            for s in rng.sample(starts, n)]


def _build_trident_sound(rng, _attr_id, _profile=None):
    n = rng.randint(1, 3)
    snds = ["minecraft:item.trident.riptide_1", "minecraft:item.trident.riptide_2",
            "minecraft:item.trident.riptide_3", "minecraft:item.trident.return"]
    return rng.sample(snds, n)


_COMPONENTS = {}
for _k in ("damage", "damage_protection", "smash_damage_per_fallen_block",
           "knockback", "armor_effectiveness", "item_damage", "ammo_use",
           "projectile_piercing", "projectile_spread", "projectile_count",
           "trident_return_acceleration", "fishing_time_reduction",
           "fishing_luck_bonus", "block_experience", "mob_experience",
           "repair_with_xp"):
    _COMPONENTS[_k] = _build_ve_component(_k)
for _k in ("crossbow_charge_time", "trident_spin_attack_strength"):
    _COMPONENTS[_k] = _build_single_ve(_k)
for _k in ("post_piercing_attack", "hit_block", "projectile_spawned"):
    _COMPONENTS[_k] = _build_ee_component(_k, _EE_BUILDERS_EVENT)
_COMPONENTS["tick"] = _build_ee_component("tick", _EE_BUILDERS_WORN)
_COMPONENTS["damage_immunity"] = _build_damage_immunity
_COMPONENTS["post_attack"] = _build_post_attack
_COMPONENTS["equipment_drops"] = _build_equipment_drops
_COMPONENTS["location_changed"] = _build_location_changed
_COMPONENTS["attributes"] = _build_attributes
_COMPONENTS["crossbow_charging_sounds"] = _build_charging_sounds
_COMPONENTS["trident_sound"] = _build_trident_sound
_COMPONENTS["prevent_equipment_drop"] = lambda rng, _a, _p=None: {}
_COMPONENTS["prevent_armor_change"] = lambda rng, _a, _p=None: {}
del _k


# ---------------------------------------------------------------------------
# Профили: осмысленные наборы (предметы + слоты + компоненты), плюс абсурд
# ---------------------------------------------------------------------------

# компоненты-«сцены» (post_attack/tick/location_changed — там живут
# run_function-функции): вес 3 — чтобы кастомные mcfunction-эффекты
# встречались у ~2/3 измерений (подобрано эмпирически)
_UNIVERSAL_COMPS = [("tick", 3), ("attributes", 5), ("location_changed", 3),
                    ("damage_immunity", 2), ("post_attack", 3),
                    ("item_damage", 1), ("repair_with_xp", 1)]


def _items_tag(tag):
    return "#minecraft:enchantable/" + tag


# ---------------------------------------------------------------------------
# ВАЛИДНОСТЬ КОМПОНЕНТ ПО ПРЕДМЕТАМ (юзер: «зачарования не должны быть на
# предметах где их нельзя использовать — не надо мечу давать защиту»).
# Таблица правил слотов/типов — по фактическим точкам срабатывания в байткоде
# jar 26.2 (EnchantmentHelper: runIterationOnItem БЕЗ слот-чека = компонента
# привязана к типу предмета-триггера; runIterationOnEquipment — со слот-чеком
# Enchantment.matchingSlot):
#   damage/knockback/armor_effectiveness/smash_* — оружие атаки
#     (stabAttack/getKnockback/getWeaponItem; smash — ТОЛЬКО MaceItem);
#   damage_protection/damage_immunity — экипировка жертвы по слотам;
#   projectile_*/ammo_use — ProjectileWeaponItem (лук/арбалет);
#   crossbow_*/trident_*/fishing_*/block_experience — соответствующий предмет;
#   mob_experience/equipment_drops/post_piercing_attack — экипировка убийцы
#     со слот-чеком (оружие в mainhand; piercing-атака — копья/трезубец);
#   hit_block — удар о блок ЛЮБЫМ удерживаемым предметом + снаряды
#     (ServerPlayerGameMode/AbstractArrow/ThrownTrident);
#   tick/location_changed/post_attack/prevent_* — ок везде (решение юзера).
# Классификация supported_items по видам (теги раскрыты по jar 26.2):
#   melee = мечи/копья/топоры (enchantable/melee_weapon|sharp_weapon|weapon
#     = swords+spears(+axes)); mace отдельно (smash только булаве);
#   durability = смешанный тег (броня+щит+лук+мечи — все с прочностью,
#     годен для item_damage/repair_with_xp, НЕ годен для урона);
#   vanishing = durability + компас/тыквы/черепа (без прочности — мимо);
#   worn = enchantable/equippable (броня+элитры+черепа/тыквы — годен для
#     защиты, не для прочности).
# ---------------------------------------------------------------------------

# тег -> вид предмета (теги из jar 26.2; melee = мечи/топоры, spear —
# копья отдельно: piercing-атака (lunge) доступна только им и трезубцу)
_ENTRY_KINDS = {
    "#minecraft:enchantable/melee_weapon": "melee",
    "#minecraft:enchantable/sharp_weapon": "melee",
    "#minecraft:enchantable/fire_aspect": "melee",
    "#minecraft:enchantable/sweeping": "melee",
    "#minecraft:enchantable/weapon": "melee",
    "#minecraft:swords": "melee",
    "#minecraft:spears": "spear",
    "#minecraft:enchantable/lunge": "spear",
    "#minecraft:enchantable/mace": "mace",
    "#minecraft:enchantable/bow": "bow",
    "#minecraft:enchantable/crossbow": "crossbow",
    "#minecraft:enchantable/trident": "trident",
    "#minecraft:enchantable/fishing": "fishing",
    "#minecraft:enchantable/mining": "mining",
    "#minecraft:enchantable/mining_loot": "mining",
    "#minecraft:axes": "mining", "#minecraft:pickaxes": "mining",
    "#minecraft:shovels": "mining", "#minecraft:hoes": "mining",
    "#minecraft:enchantable/armor": "armor",
    "#minecraft:enchantable/chest_armor": "armor",
    "#minecraft:enchantable/leg_armor": "armor",
    "#minecraft:enchantable/foot_armor": "armor",
    "#minecraft:enchantable/head_armor": "armor",
    "#minecraft:chest_armor": "armor", "#minecraft:leg_armor": "armor",
    "#minecraft:foot_armor": "armor", "#minecraft:head_armor": "armor",
    "#minecraft:enchantable/equippable": "worn",
    "#minecraft:skulls": "worn",
    "#minecraft:enchantable/durability": "durability",
    "#minecraft:enchantable/vanishing": "vanishing",
    "#minecraft:breaks_decorated_pots": "misc",
}


def _entry_kind(entry):
    """Вид предмета для элемента supported_items (тег или id)."""
    if entry in _ENTRY_KINDS:
        return _ENTRY_KINDS[entry]
    iid = entry.rsplit(":", 1)[-1]
    if iid == "mace":
        return "mace"
    if iid.endswith("_spear"):
        return "spear"
    if iid.endswith("_sword"):
        return "melee"
    if iid == "bow":
        return "bow"
    if iid == "crossbow":
        return "crossbow"
    if iid == "trident":
        return "trident"
    if iid == "fishing_rod":
        return "fishing"
    if (iid in ("shears", "brush", "flint_and_steel",
                "carrot_on_a_stick", "warped_fungus_on_a_stick")
            or iid.endswith(("_pickaxe", "_shovel", "_hoe", "_axe"))):
        return "mining"
    if iid.endswith(("_helmet", "_chestplate", "_leggings", "_boots")):
        return "armor"
    if iid == "elytra":
        return "elytra"
    if iid == "shield":
        return "shield"
    if iid == "saddle":
        return "saddle"
    if iid in ("book", "enchanted_book"):
        return "book"
    return "misc"


# компонента -> (допустимые виды предметов, требование к слотам|None).
# Слоты: "wear" = {any,armor,head,chest,legs,feet,body} (предмет реально
# надет), "mainhand" = {any,mainhand,hand} (предмет в руке при событии).
# Компоненты вне таблицы работают на любом предмете — tick/location_changed/
# post_attack/damage_immunity/prevent_* (решение юзера: «ок везде»).
_DURABILITY_KINDS = frozenset(
    "melee spear mace bow crossbow trident fishing mining armor elytra "
    "shield durability".split())
_ATTACK_KINDS = frozenset(
    "melee spear mace bow crossbow trident fishing mining shield".split())
_COMP_ITEM_RULES = {
    # оружие атаки: компонента читается с предмета-триггера без слот-чека
    "damage": (_ATTACK_KINDS, None),
    "knockback": (_ATTACK_KINDS, None),
    "armor_effectiveness": (frozenset("melee spear mace mining".split()), None),
    # smash-атака живёт в MaceItem.hurtEnemy — ТОЛЬКО булава
    "smash_damage_per_fallen_block": (frozenset(["mace"]), None),
    # защита — только то, что можно надеть (юзер: броня + equippable)
    "damage_protection": (frozenset("armor elytra worn".split()), "wear"),
    # прочность
    "item_damage": (_DURABILITY_KINDS, None),
    "repair_with_xp": (_DURABILITY_KINDS, None),
    # снаряды: ProjectileWeaponItem = лук/арбалет (трезубец — только spawn)
    "ammo_use": (frozenset("bow crossbow".split()), None),
    "projectile_piercing": (frozenset("bow crossbow".split()), None),
    "projectile_spread": (frozenset("bow crossbow".split()), None),
    "projectile_count": (frozenset("bow crossbow".split()), None),
    "projectile_spawned": (frozenset("bow crossbow trident".split()), None),
    # предметные механики
    "trident_return_acceleration": (frozenset(["trident"]), None),
    "trident_spin_attack_strength": (frozenset(["trident"]), None),
    "trident_sound": (frozenset(["trident"]), None),
    "fishing_time_reduction": (frozenset(["fishing"]), None),
    "fishing_luck_bonus": (frozenset(["fishing"]), None),
    "crossbow_charge_time": (frozenset(["crossbow"]), None),
    "crossbow_charging_sounds": (frozenset(["crossbow"]), None),
    "block_experience": (frozenset(["mining"]), None),
    # лутинг-подобные: оружие убийцы в mainhand (юзер: «работают в руках»)
    "mob_experience": (frozenset("melee spear mace".split()), "mainhand"),
    "equipment_drops": (frozenset("melee spear mace".split()), "mainhand"),
    # piercing-атака (выпад/lunge) — копья и трезубец в mainhand
    "post_piercing_attack": (frozenset("spear trident".split()), "mainhand"),
}

# piercing-атака (PiercingWeapon.attack -> postPiercingAttack) доступна
# только копьям/трезубцу: тег melee_weapon СМЕШАННЫЙ (мечи+копья), поэтому
# для post_piercing_attack допустимы только однозначно-копейные записи —
# #spears/#lunge/#trident и id копий/трезубца
_PIERCING_ENTRIES = frozenset([
    "#minecraft:spears", "#minecraft:enchantable/lunge",
    "#minecraft:enchantable/trident", "minecraft:trident"])

# слот-группы, в которых предмет реально находится в момент события
_WEAR_SLOTS = frozenset(["any", "armor", "head", "chest", "legs", "feet",
                         "body"])
_HAND_SLOTS = frozenset(["any", "mainhand", "hand"])


def _comp_usable(comp, supported, slots):
    """Юзабельна ли компонента для supported_items (+slots) по таблице
    правил (см. _COMP_ITEM_RULES). Проверяется КАЖДЫЙ элемент supported
    («не надо мечу давать защиту» — смешанный набор бракуется целиком).
    Пустые slots — дежурный краевой случай (валидность остаётся серверу)."""
    rule = _COMP_ITEM_RULES.get(comp)
    if rule is None:
        return True
    kinds, slot_req = rule
    entries = supported if isinstance(supported, list) else [supported]
    if comp == "post_piercing_attack":
        if not all(e in _PIERCING_ENTRIES
                   or (not e.startswith("#")
                       and _entry_kind(e) in ("spear", "trident"))
                   for e in entries):
            return False
    elif not all(_entry_kind(e) in kinds for e in entries):
        return False
    if slot_req and slots:
        need = _WEAR_SLOTS if slot_req == "wear" else _HAND_SLOTS
        if not any(s in need for s in slots):
            return False
    return True


_PROFILES = [
    ("weapon", 22,
     [(_items_tag("melee_weapon"), 3), (_items_tag("sharp_weapon"), 2),
      (_items_tag("mace"), 1), (_items_tag("fire_aspect"), 1),
      (_items_tag("sweeping"), 1), ("#minecraft:swords", 2),
      ("#minecraft:spears", 2),
      (["minecraft:diamond_sword", "minecraft:iron_sword",
        "minecraft:netherite_sword", "minecraft:mace"], 1)],
     [("mainhand", 6), ("hand", 2), ("offhand", 1), ("any", 1)],
     [("damage", 6), ("knockback", 3), ("equipment_drops", 2),
      ("mob_experience", 2), ("hit_block", 1), ("smash_damage_per_fallen_block", 1),
      ("post_piercing_attack", 1), ("armor_effectiveness", 1)]),
    ("armor", 20,
     [(_items_tag("armor"), 3), (_items_tag("equippable"), 1),
      (_items_tag("chest_armor"), 1), (_items_tag("foot_armor"), 1),
      (_items_tag("leg_armor"), 1), (_items_tag("head_armor"), 1),
      (["minecraft:diamond_helmet", "minecraft:diamond_chestplate",
        "minecraft:diamond_leggings", "minecraft:diamond_boots",
        "minecraft:elytra", "minecraft:turtle_helmet"], 1)],
     [("armor", 3), ("feet", 2), ("legs", 2), ("chest", 2), ("head", 2),
      ("body", 1), ("any", 1)],
     [("damage_protection", 6), ("prevent_armor_change", 1),
      ("prevent_equipment_drop", 1)]),
    ("bow", 8,
     [(_items_tag("bow"), 4), (["minecraft:bow"], 2)],
     [("mainhand", 5), ("hand", 2), ("any", 1)],
     [("damage", 3), ("projectile_count", 1), ("projectile_spread", 2),
      ("projectile_piercing", 2), ("ammo_use", 2), ("projectile_spawned", 2),
      ("hit_block", 1), ("knockback", 2)]),
    ("crossbow", 7,
     [(_items_tag("crossbow"), 4), (["minecraft:crossbow"], 2)],
     [("mainhand", 5), ("hand", 2), ("any", 1)],
     [("crossbow_charge_time", 2), ("crossbow_charging_sounds", 4),
      ("projectile_piercing", 3), ("projectile_count", 1),
      ("projectile_spawned", 2), ("ammo_use", 1), ("hit_block", 1)]),
    ("trident", 7,
     [(_items_tag("trident"), 4), (["minecraft:trident"], 2)],
     [("mainhand", 5), ("hand", 2), ("any", 1)],
     [("trident_return_acceleration", 2), ("trident_sound", 4),
      ("trident_spin_attack_strength", 2), ("damage", 3),
      ("projectile_spawned", 1), ("knockback", 1)]),
    ("mining", 14,
     [(_items_tag("mining"), 3), (_items_tag("mining_loot"), 2),
      ("#minecraft:pickaxes", 2), ("#minecraft:shovels", 1),
      (["minecraft:diamond_pickaxe", "minecraft:iron_shovel",
        "minecraft:shears", "minecraft:brush"], 1)],
     [("mainhand", 6), ("hand", 2), ("any", 1)],
     [("block_experience", 3), ("hit_block", 4), ("damage", 1)]),
    ("fishing", 4,
     [(_items_tag("fishing"), 4), (["minecraft:fishing_rod"], 2)],
     [("mainhand", 6), ("hand", 2)],
     [("fishing_time_reduction", 3), ("fishing_luck_bonus", 3),
      ("damage", 1), ("knockback", 1)]),
    ("elytra", 4,
     [(["minecraft:elytra"], 5), (_items_tag("equippable"), 1)],
     [("chest", 6), ("any", 2)],
     [("attributes", 4), ("location_changed", 3), ("tick", 2),
      ("damage_protection", 2), ("prevent_equipment_drop", 1)]),
    ("shield", 4,
     [(["minecraft:shield"], 6)],
     [("offhand", 5), ("hand", 2), ("any", 1)],
     # damage_protection убран: щит не надевается как броня (юзер:
     # «защита — только слоты брони»); hit_block — удар о блок щитом
     [("post_attack", 3), ("hit_block", 2), ("knockback", 2),
      ("attributes", 2), ("prevent_equipment_drop", 1)]),
    ("saddle", 2,
     [(["minecraft:saddle"], 6)],
     [("saddle", 6), ("any", 1)],
     # damage/knockback/equipment_drops убраны: скакун не атакует предметом
     # и не «убивает» (лутинг-подобные — только оружие в руках юзера)
     [("attributes", 5), ("post_attack", 3), ("tick", 2)]),
    ("book", 3,
     [(["minecraft:book"], 4), (["minecraft:enchanted_book"], 2)],
     [("any", 4), ("mainhand", 1), ("armor", 1)],
     # equipment_drops убран: лутинг-подобные — только оружие (юзер)
     [("attributes", 4), ("post_attack", 2), ("location_changed", 2),
      ("tick", 2), ("damage_immunity", 2)]),
    ("durability", 8,
     [(_items_tag("durability"), 3), (_items_tag("equippable"), 1),
      ("#minecraft:axes", 1),
      (["minecraft:elytra", "minecraft:shield", "minecraft:bow",
        "minecraft:flint_and_steel"], 1)],
     [("any", 3), ("mainhand", 2), ("armor", 2), ("hand", 1)],
     [("repair_with_xp", 2), ("prevent_equipment_drop", 1)]),
    ("curse", 6,
     [(_items_tag("vanishing"), 2), (_items_tag("equippable"), 2),
      (_items_tag("armor"), 1), (_items_tag("weapon"), 1),
      (["minecraft:book", "minecraft:name_tag", "minecraft:compass"], 1)],
     [("any", 2), ("armor", 2), ("mainhand", 2), ("hand", 1)],
     [("prevent_equipment_drop", 2), ("prevent_armor_change", 2)]),
    ("absurd", 12,
     None,  # предметы выбираются отдельно (см. _absurd_items)
     None,
     None),
]

_PROFILE_KEYS = [p[0] for p in _PROFILES]
_PROFILE_W = [p[1] for p in _PROFILES]


def _absurd_items(rng):
    """Абсурдные supported_items: 'копательный меч', зачарование хлеба...

    ВНИМАНИЕ: "#тег" допустим только ЦЕЛИКОМ (верхний уровень HolderSet),
    внутри списка — только чистые id (проверено: "Not a valid resource
    location: #minecraft:...").
    """
    k = rng.randint(0, 3)
    if k == 0:
        n = rng.randint(2, 5)
        return rng.sample(_ITEMS, n)
    if k == 1:
        return "#minecraft:" + rng.choice(_OTHER_TAGS)
    if k == 2:  # просто случайный список предметов (без тегов внутри!)
        n = rng.randint(2, 4)
        return rng.sample(_ITEMS, n)
    return rng.choice(["#minecraft:breaks_decorated_pots", "#minecraft:swords",
                       "#minecraft:pickaxes", "minecraft:stick",
                       "minecraft:bone", "minecraft:blaze_rod"])


def _absurd_comps(rng):
    """Абсурд = любой набор компонент."""
    keys = list(_COMPONENTS.keys())
    weights = []
    for key in keys:
        if key in ("damage", "attributes", "post_attack", "tick"):
            weights.append(4)
        elif key in ("crossbow_charge_time", "crossbow_charging_sounds",
                     "trident_sound", "trident_return_acceleration",
                     "trident_spin_attack_strength", "fishing_time_reduction",
                     "fishing_luck_bonus"):
            weights.append(1)  # редкие, но возможные на мечах — наш стиль
        else:
            weights.append(2)
    return keys, weights


# ---------------------------------------------------------------------------
# Названия
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Названия: описательные (по РЕАЛЬНЫМ эффектам зачарования)
# ---------------------------------------------------------------------------
# _effect_name строит название из фактического содержимого effects:
#   «Громовое Пробитие»   — projectile_piercing
#   «Яд и Отброс»         — post_attack(apply_mob_effect poison) + knockback
#   «Кошачья Лапа»         — damage_immunity [minecraft:is_fall]
#   «Проклятие Хрупкости» — item_damage с положительным знаком
#   «Магическая Отплата»  — post_attack(damage_entity magic)
#   «Заряд Ветра Полуночи» — apply_mob_effect wind_charged + родительный
# Прилагательное согласуется с родом слова (_word_gender/_inflect_adj);
# фразы и мн.ч. идут без прилагательного. Знак учтён для ammo_use /
# crossbow_charge_time / item_damage (_VE_FLIP): «Бережливость» против
# «Проклятие Расточительства», «Быстрый Взвод» против «Затяжной Взвод».
# Фолбэк при пустых эффектах (крайний случай 3%) — вкусовое _rand_name.
# Существующие паки мигрируются скриптом migrate_ench_names.py.
# Слова для value-компонент (знак значения учитывается через _VE_FLIP)
_VE_WORDS = {
    "damage": ["Удар", "Клык", "Разруб", "Жало", "Острота"],
    "damage_protection": ["Оберег", "Щит", "Панцирь", "Заслон"],
    "smash_damage_per_fallen_block": ["Сокрушение", "Тяжёлая Пята", "Приземление"],
    "knockback": ["Отброс", "Таран", "Натиск"],
    "armor_effectiveness": ["Пробой", "Игла", "Вскрытие"],
    "item_damage": ["Износ", "Ломота"],
    "ammo_use": ["Расход"],
    "projectile_piercing": ["Пробитие", "Сквозной Полёт"],
    "projectile_spread": ["Разброс", "Веер"],
    "projectile_count": ["Залп", "Рой"],
    "trident_return_acceleration": ["Возврат", "Бумеранг"],
    "fishing_time_reduction": ["Терпение", "Клёв"],
    "fishing_luck_bonus": ["Удача Рыбака", "Клёвое Место"],
    "block_experience": ["Опыт Жил", "Знание Руд"],
    "mob_experience": ["Жатва Опыта", "Добытчик"],
    "repair_with_xp": ["Починка", "Самозалатка"],
    "crossbow_charge_time": ["Взвод"],
    "trident_spin_attack_strength": ["Вихрь", "Вертушка"],
    "equipment_drops": ["Трофеи", "Оброн", "Добыча"],
}

# знак меняет смысл: (отрицательное, ноль, положительное) -> слова
_VE_FLIP = {
    "ammo_use": (["Бережливость", "Экономия"], ["Бесконечность", "Неиссякаемость"],
                 ["Проклятие Расточительства", "Прожорливость"]),
    "crossbow_charge_time": (["Быстрый Взвод", "Скорая Стрельба"],
                             ["Взвод"], ["Затяжной Взвод", "Проклятие Медлительности"]),
    "item_damage": (["Закалка", "Долгий Век"], ["Износ"],
                    ["Проклятие Хрупкости", "Проклятие Ломоты"]),
}

# приоритет «зрелищности» value-компонент в названии
_VE_PRIO = {"damage": 9, "damage_protection": 7, "knockback": 7,
            "armor_effectiveness": 6, "smash_damage_per_fallen_block": 6,
            "projectile_count": 6, "projectile_piercing": 6,
            "projectile_spread": 4, "ammo_use": 5, "item_damage": 5,
            "trident_return_acceleration": 5, "trident_spin_attack_strength": 6,
            "crossbow_charge_time": 6, "fishing_time_reduction": 6,
            "fishing_luck_bonus": 5, "block_experience": 5,
            "mob_experience": 5, "repair_with_xp": 6, "equipment_drops": 5}

# атрибуты -> слово (реестр attributes 26.2)
_ATTR_WORDS = {
    "minecraft:movement_speed": "Скорость", "minecraft:movement_efficiency": "Проворство",
    "minecraft:max_health": "Живучесть", "minecraft:max_absorption": "Запас Жизни",
    "minecraft:attack_damage": "Ярость", "minecraft:attack_speed": "Темп",
    "minecraft:attack_knockback": "Замах", "minecraft:knockback_resistance": "Стойкость",
    "minecraft:explosion_knockback_resistance": "Взрывная Стойкость",
    "minecraft:armor": "Броня", "minecraft:armor_toughness": "Твёрдость",
    "minecraft:step_height": "Широкий Шаг", "minecraft:jump_strength": "Прыжок",
    "minecraft:safe_fall_distance": "Приземистость", "minecraft:fall_damage_multiplier": "Перо",
    "minecraft:block_break_speed": "Дробление", "minecraft:mining_efficiency": "Рудокоп",
    "minecraft:submerged_mining_speed": "Водолаз", "minecraft:oxygen_bonus": "Жабры",
    "minecraft:water_movement_efficiency": "Плавник", "minecraft:sneaking_speed": "Скрытность",
    "minecraft:sweeping_damage_ratio": "Размах", "minecraft:scale": "Великан",
    "minecraft:gravity": "Легкость", "minecraft:luck": "Удача",
    "minecraft:follow_range": "Взор", "minecraft:flying_speed": "Полёт",
}

# моб-эффекты -> слово (реестр mob_effect 26.2)
_EFF_WORDS = {
    "minecraft:speed": "Скорость", "minecraft:slowness": "Немощь",
    "minecraft:haste": "Спешка", "minecraft:mining_fatigue": "Усталость",
    "minecraft:strength": "Сила", "minecraft:jump_boost": "Заячий Прыжок",
    "minecraft:nausea": "Дурнота", "minecraft:regeneration": "Регенерация",
    "minecraft:resistance": "Стойкость", "minecraft:fire_resistance": "Огнеупорность",
    "minecraft:water_breathing": "Жабры", "minecraft:invisibility": "Невидимость",
    "minecraft:blindness": "Слепота", "minecraft:night_vision": "Ночное Зрение",
    "minecraft:hunger": "Голод", "minecraft:weakness": "Слабость",
    "minecraft:poison": "Яд", "minecraft:wither": "Иссушение",
    "minecraft:health_boost": "Здоровье", "minecraft:absorption": "Поглощение",
    "minecraft:saturation": "Сытость", "minecraft:glowing": "Сияние",
    "minecraft:levitation": "Левитация", "minecraft:luck": "Удача",
    "minecraft:unluck": "Неудача", "minecraft:slow_falling": "Перо",
    "minecraft:conduit_power": "Морская Сила", "minecraft:dolphins_grace": "Благодать Дельфина",
    "minecraft:darkness": "Тьма", "minecraft:instant_health": "Исцеление",
    "minecraft:instant_damage": "Боль",
    "minecraft:bad_omen": "Дурное Знамение", "minecraft:hero_of_the_village": "Герой Деревни",
    "minecraft:trial_omen": "Знамение Испытания", "minecraft:raid_omen": "Знамение Рейда",
    "minecraft:wind_charged": "Заряд Ветра", "minecraft:weaving": "Плетение",
    "minecraft:oozing": "Слизь", "minecraft:infested": "Заражение",
    "minecraft:breath_of_the_nautilus": "Дыхание Наутилуса",
}

# призываемые сущности -> слово
_ENT_WORDS = {
    "minecraft:lightning_bolt": "Громовержец", "minecraft:evoker_fangs": "Клыки Заклинателя",
    "minecraft:area_effect_cloud": "Облако", "minecraft:firework_rocket": "Фейерверк",
    "minecraft:tnt": "Подрывник", "minecraft:wind_charge": "Порыв",
    "minecraft:armor_stand": "Манекен", "minecraft:creeper": "Крипер",
    "minecraft:silverfish": "Чешуйница", "minecraft:vex": "Досаждатель",
    "minecraft:endermite": "Эндермит", "minecraft:experience_orb": "Опыт",
}

# блоки replace_* -> слово
_BLK_WORDS = {
    "minecraft:cobweb": "Паутина", "minecraft:ice": "Лёд", "minecraft:packed_ice": "Лёд",
    "minecraft:magma_block": "Магма", "minecraft:obsidian": "Обсидиан",
    "minecraft:glowstone": "Светокамень", "minecraft:sea_lantern": "Морской Фонарь",
    "minecraft:sculk": "Скулк", "minecraft:amethyst_block": "Аметист",
    "minecraft:cobblestone": "Булыжник", "minecraft:stone": "Камень",
    "minecraft:dirt": "Земля", "minecraft:mud": "Грязь",
    "minecraft:soul_sand": "Песок Душ", "minecraft:slime_block": "Слизь",
    "minecraft:honey_block": "Мёд", "minecraft:lantern": "Фонарь",
    "minecraft:frosted_ice": "Иней", "minecraft:crying_obsidian": "Плачущий Обсидиан",
}

# частицы -> слово (реестр particles 26.2; используется и генератором
# mcfunction-функций — см. _fn_particle_cmd)
_PART_WORDS = {
    "minecraft:flame": "Искры", "minecraft:soul_fire_flame": "Искры Душ",
    "minecraft:heart": "Сердца", "minecraft:crit": "Крит",
    "minecraft:enchanted_hit": "Блеск", "minecraft:end_rod": "Сияние",
    "minecraft:sonic_boom": "Звуковой Удар", "minecraft:gust": "Порыв",
    "minecraft:small_gust": "Порыв", "minecraft:sculk_soul": "Души",
    "minecraft:electric_spark": "Искры", "minecraft:poof": "Дымка",
    "minecraft:cloud": "Облако", "minecraft:smoke": "Дым",
    "minecraft:white_smoke": "Дымка", "minecraft:splash": "Брызги",
    "minecraft:witch": "Ведьмин Дым", "minecraft:lava": "Лава",
    "minecraft:angry_villager": "Гнев", "minecraft:happy_villager": "Радость",
    "minecraft:infested": "Заражение", "minecraft:enchant": "Чары",
    "minecraft:glow": "Сияние", "minecraft:portal": "Портал",
    "minecraft:dragon_breath": "Дыхание Дракона",
    "minecraft:totem_of_undying": "Тотем", "minecraft:firefly": "Светлячки",
    "minecraft:snowflake": "Снежинки", "minecraft:soul": "Души",
    "minecraft:dust": "Пыль",
    # --- расширение для mcfunction-генератора (все id — SimpleParticleType
    # --- jar 26.2, см. _FN_PARTICLES) ---
    "minecraft:sweep_attack": "Взмах", "minecraft:reverse_portal": "Изнанка",
    "minecraft:small_flame": "Огонёк", "minecraft:note": "Нота",
    "minecraft:explosion": "Взрыв", "minecraft:explosion_emitter": "Взрыв",
    "minecraft:firework": "Искры", "minecraft:dust_plume": "Шлейф",
    "minecraft:ominous_spawning": "Знамение",
    "minecraft:vault_connection": "Жила", "minecraft:trial_omen": "Знамение",
    "minecraft:raid_omen": "Набег", "minecraft:spit": "Плевок",
    "minecraft:sneeze": "Чих", "minecraft:squid_ink": "Чернила",
    "minecraft:glow_squid_ink": "Чернила", "minecraft:elder_guardian": "Страж",
    "minecraft:nautilus": "Наутилус", "minecraft:spore_blossom_air": "Споры",
    "minecraft:crimson_spore": "Споры", "minecraft:warped_spore": "Споры",
    "minecraft:campfire_cosy_smoke": "Дымок",
    "minecraft:campfire_signal_smoke": "Дымок", "minecraft:wax_on": "Воск",
    "minecraft:cherry_leaves": "Лепестки",
    "minecraft:pale_oak_leaves": "Лепестки",
    "minecraft:copper_fire_flame": "Медный Огонь",
    "minecraft:noxious_gas": "Миазмы", "minecraft:noxious_gas_cloud": "Миазмы",
    "minecraft:sulfur_bubbles": "Пузыри",
    "minecraft:sulfur_cube_goo": "Серная Слизь",
    "minecraft:dust_color_transition": "Хамелеон",
    "minecraft:entity_effect": "Ореол", "minecraft:flash": "Всполох",
}

# типы урона damage_entity -> слово
_DMGTYPE_WORDS = {
    "minecraft:magic": "Магическая", "minecraft:indirect_magic": "Магическая",
    "minecraft:arrow": "Стрелковая", "minecraft:trident": "Трезубцем",
    "minecraft:spear": "Копейная", "minecraft:explosion": "Взрывная",
    "minecraft:player_explosion": "Взрывная", "minecraft:fireball": "Огненная",
    "minecraft:mob_attack": "Звериная", "minecraft:mob_projectile": "Жало",
    "minecraft:player_attack": "Стальная", "minecraft:thorns": "Колючая",
    "minecraft:sonic_boom": "Звуковая", "minecraft:wither": "Иссушающая",
    "minecraft:wither_skull": "Иссушающая", "minecraft:wind_charge": "Ветряная",
    "minecraft:falling_anvil": "Наковальня", "minecraft:falling_block": "Тяжёлая",
    "minecraft:falling_stalactite": "Сталактит", "minecraft:stalagmite": "Шип",
    "minecraft:mace_smash": "Булавная", "minecraft:freeze": "Морозная",
    "minecraft:cactus": "Колючая", "minecraft:sweet_berry_bush": "Терновая",
    "minecraft:sting": "Жалящая", "minecraft:spit": "Плевок",
    "minecraft:generic": "Простая",
}

# теги урона в требованиях damage_immunity -> слово
_DTAG_WORDS = {
    "minecraft:is_fire": "Огнеупорность", "minecraft:is_explosion": "Взрывоупорность",
    "minecraft:is_fall": "Кошачья Лапа", "minecraft:is_projectile": "Щит от Стрел",
    "minecraft:is_freezing": "Стойкость к Стуже", "minecraft:is_lightning": "Грозостойкость",
    "minecraft:is_drowning": "Жабры", "minecraft:burn_from_stepping": "Огнеупорность",
}

# ---------------------------------------------------------------------------
# Словари для summarize_enchantment (краткие описания действий):
# винительные падежи — «накладывает <ЧТО>», «усиливает <ЧТО>»
# ---------------------------------------------------------------------------

# моб-эффекты -> винительный падеж («накладывает яд», «накладывает слепоту»;
# все id — реестр mob_effect 26.2, зеркало _EFF_WORDS)
_EFF_ACC = {
    "minecraft:speed": "скорость", "minecraft:slowness": "немощь",
    "minecraft:haste": "спешку", "minecraft:mining_fatigue": "усталость",
    "minecraft:strength": "силу", "minecraft:jump_boost": "заячий прыжок",
    "minecraft:nausea": "дурноту", "minecraft:regeneration": "регенерацию",
    "minecraft:resistance": "стойкость", "minecraft:fire_resistance": "огнеупорность",
    "minecraft:water_breathing": "водное дыхание", "minecraft:invisibility": "невидимость",
    "minecraft:blindness": "слепоту", "minecraft:night_vision": "ночное зрение",
    "minecraft:hunger": "голод", "minecraft:weakness": "слабость",
    "minecraft:poison": "яд", "minecraft:wither": "иссушение",
    "minecraft:health_boost": "прилив здоровья", "minecraft:absorption": "поглощение",
    "minecraft:saturation": "сытость", "minecraft:glowing": "сияние",
    "minecraft:levitation": "левитацию", "minecraft:luck": "удачу",
    "minecraft:unluck": "неудачу", "minecraft:slow_falling": "медленное падение",
    "minecraft:conduit_power": "силу моря", "minecraft:dolphins_grace": "благодать дельфина",
    "minecraft:darkness": "тьму", "minecraft:instant_health": "мгновенное исцеление",
    "minecraft:instant_damage": "мгновенную боль",
    "minecraft:bad_omen": "дурное знамение", "minecraft:hero_of_the_village": "славу героя деревни",
    "minecraft:trial_omen": "знамение испытания", "minecraft:raid_omen": "знамение рейда",
    "minecraft:wind_charged": "заряд ветра", "minecraft:weaving": "плетение",
    "minecraft:oozing": "слизь", "minecraft:infested": "заражение",
    "minecraft:breath_of_the_nautilus": "дыхание наутилуса",
}

# атрибуты -> винительный падеж («усиливает броню», «усиливает скорость атаки»;
# реестр attributes 26.2 — покрывает весь пул _ATTRS)
_ATTR_ACC = {
    "minecraft:movement_speed": "скорость", "minecraft:movement_efficiency": "проворство",
    "minecraft:max_health": "здоровье", "minecraft:max_absorption": "запас здоровья",
    "minecraft:attack_damage": "урон", "minecraft:attack_speed": "скорость атаки",
    "minecraft:attack_knockback": "отброс", "minecraft:knockback_resistance": "стойкость к отбросу",
    "minecraft:explosion_knockback_resistance": "стойкость к взрывам",
    "minecraft:armor": "броню", "minecraft:armor_toughness": "твёрдость брони",
    "minecraft:step_height": "высоту шага", "minecraft:jump_strength": "силу прыжка",
    "minecraft:safe_fall_distance": "безопасное падение",
    "minecraft:fall_damage_multiplier": "устойчивость к падению",
    "minecraft:block_break_speed": "скорость добычи", "minecraft:mining_efficiency": "эффективность добычи",
    "minecraft:submerged_mining_speed": "добычу под водой", "minecraft:oxygen_bonus": "запас воздуха",
    "minecraft:water_movement_efficiency": "плавучесть", "minecraft:sneaking_speed": "скрытность",
    "minecraft:sweeping_damage_ratio": "размах", "minecraft:scale": "размер",
    "minecraft:gravity": "вес", "minecraft:luck": "удачу",
    "minecraft:follow_range": "взор", "minecraft:flying_speed": "полёт",
}

# теги урона из требований damage_immunity -> дательный падеж
# («иммунитет к огню», «иммунитет к падению»)
_DTAG_DAT = {
    "minecraft:is_fire": "огню", "minecraft:is_explosion": "взрывам",
    "minecraft:is_fall": "падению", "minecraft:is_projectile": "снарядам",
    "minecraft:is_freezing": "стуже", "minecraft:is_lightning": "молниям",
    "minecraft:is_drowning": "утоплению", "minecraft:burn_from_stepping": "горячим полам",
}

# множественное число / фразы — прилагательное не согласуется, пропускаем
# (переливы/снежинки/светлячки/осколки — слова профилей mcfunction-функций)
_PLURAL_WORDS = {"Трофеи", "Сердца", "Искры", "Жабры", "Брызги", "Души",
                 "Переливы", "Снежинки", "Светлячки", "Осколки"}

# род отдельных слов, где эвристика по суффиксу ошибается (мягкий знак,
# средние на -я; пополнения идут вместе с новыми словами _NOUN)
_GENDER_EXC = {"Немощь": "f", "Боль": "f", "Слизь": "f",
               "Пламя": "n", "Бремя": "n",
               "Печать": "f", "Метель": "f", "Тень": "f", "Полночь": "f",
               "Весть": "f", "Песнь": "f", "Цепь": "f", "Ветвь": "f",
               "Кладезь": "f", "Месть": "f", "Печаль": "f", "Скорбь": "f"}


def _word_gender(w):
    """Род слова для согласования прилагательного: 'm'/'f'/'n' или None
    (фраза/мн.ч. — шаблоны с прилагательным пропускаются)."""
    if " " in w or "-" in w or w in _PLURAL_WORDS:
        return None
    if w in _GENDER_EXC:
        return _GENDER_EXC[w]
    if w.endswith(("ость", "ота", "ация", "ия", "есть", "шь")):
        return "f"
    if w.endswith(("а", "я")):
        return "f"
    if w.endswith(("о", "е")):
        return "n"
    return "m"


# притяжательные прилагательные — неправильное склонение
# (Медвежий -> Медвежья/Медвежье/Медвежьи, Лисий -> Лисья/...)
_POSSESSIVE_ADJ = {"Медвежий", "Волчий", "Лисий", "Рыбий", "Паучий",
                   "Кабаний", "Олений", "Пастуший", "Верблюжий", "Заячий",
                   "Барсучий", "Бычий", "Драконий", "Кошачий", "Собачий",
                   "Козий", "Коровий"}


def _inflect_adj(adj, gender):
    """Дикий -> Дикая/Дикое, Шепчущий -> Шепчущая/Шепчущее (согласование
    с родом; после ж/ч/ш/щ — «ее», после к/г/х — «ое"). Множественное
    (gender='p'): Громовой -> Громовые, Большой -> Большие, Горький ->
    Горькие. Притяжательные (_POSSESSIVE_ADJ): Медвежий -> Медвежья/
    Медвежье/Медвежьи."""
    if gender == "m" or not adj.endswith(("ый", "ой", "ий")):
        return adj
    stem = adj[:-2]
    last = stem[-1:]
    if adj in _POSSESSIVE_ADJ:
        return stem + {"f": "ья", "n": "ье", "p": "ьи"}.get(gender, "")
    if gender == "p":
        if adj.endswith("ий") or last in "жчшщ":
            return stem + "ие"
        return stem + "ые"
    if adj.endswith("ий") and last in "кгх":
        return stem + ("ая" if gender == "f" else "ое")
    if adj.endswith("ий") and last in "жчшщ":
        return stem + ("ая" if gender == "f" else "ее")
    if adj.endswith("ий"):
        return stem + ("яя" if gender == "f" else "ее")
    return stem + ("ая" if gender == "f" else "ое")


def _lbv_value(v):
    """Примерная величина LevelBasedValue (для выбора слова по знаку)."""
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, dict):
        t = v.get("type")
        if t == "minecraft:linear":
            return float(v.get("base", 0.0))
        if t == "minecraft:clamped":
            return _lbv_value(v.get("value"))
        if t == "minecraft:lookup":
            vals = v.get("values", [])
            return float(vals[0]) if vals else 0.0
        if t in ("minecraft:fraction", "minecraft:levels_squared",
                 "minecraft:exponent"):
            return _lbv_value(v.get("numerator", v.get("added", v.get("base", 0.0))))
    return 0.0


def _ve_sign(eff):
    """Знак действия ValueEffect: <0 уменьшает, 0 нейтрален/сет, >0 увеличивает."""
    if not isinstance(eff, dict):
        return 0.0
    t = eff.get("type")
    if t == "minecraft:add":
        return _lbv_value(eff.get("value"))
    if t == "minecraft:multiply":
        return float(eff.get("factor", 1.0)) - 1.0
    if t == "minecraft:set":
        return _lbv_value(eff.get("value"))
    if t == "minecraft:remove_binomial":
        return -0.5
    if t == "minecraft:exponential":
        try:
            return (_lbv_value(eff.get("base", 1.0))
                    ** _lbv_value(eff.get("exponent", 1.0))) - 1.0
        except (OverflowError, ValueError, ZeroDivisionError):
            return 0.0
    return 0.0


def _ee_word(d, run_function_word=None):
    """Слово по EntityEffect (реальный JSON зачарования).

    run_function_word — слово профиля СГЕНЕРИРОВАННОЙ mcfunction-функции
    («Клык», «Громовержец»...): без него run_function даёт фолбэк
    «Ритуал» (старые данные, миграция имён)."""
    if not isinstance(d, dict):
        return None
    t = d.get("type")
    if t == "minecraft:all_of":
        for inner in d.get("effects", []):
            w = _ee_word(inner)
            if w:
                return w
        return None
    if t == "minecraft:apply_mob_effect":
        ta = d.get("to_apply", [])
        ta = [ta] if isinstance(ta, str) else list(ta or [])
        return _EFF_WORDS.get(ta[0], "Сглаз") if ta else None
    if t == "minecraft:summon_entity":
        ents = d.get("entity", [])
        ents = [ents] if isinstance(ents, str) else list(ents or [])
        return _ENT_WORDS.get(ents[0], "Призыв") if ents else "Призыв"
    if t in ("minecraft:replace_block", "minecraft:replace_disk"):
        sp = d.get("block_state", {})
        nm = sp.get("Name", "") if isinstance(sp, dict) else ""
        return _BLK_WORDS.get(nm, "Окаменение")
    if t == "minecraft:ignite":
        return "Поджог"
    if t == "minecraft:damage_entity":
        dtw = _DMGTYPE_WORDS.get(d.get("damage_type"))
        return "%s Отплата" % dtw if dtw else "Отплата"
    if t == "minecraft:explode":
        return "Взрыв"
    if t == "minecraft:change_item_damage":
        return "Закалка" if _lbv_value(d.get("amount", 1)) < 0 else "Износ"
    if t == "minecraft:spawn_particles":
        p = d.get("particle", "")
        return _PART_WORDS.get(p, "Блеск") if isinstance(p, str) else "Блеск"
    if t == "minecraft:play_sound":
        return "Голос"
    if t == "minecraft:apply_impulse":
        return "Толчок"
    if t == "minecraft:apply_exhaustion":
        return "Утомление"
    if t == "minecraft:run_function":
        return run_function_word or "Ритуал"
    if t == "minecraft:set_block_properties":
        return "Порча"
    if t == "minecraft:attribute":
        return _ATTR_WORDS.get(d.get("attribute"), "Дар")
    return None


def _name_seeds(effects, rng=None, run_function_word=None):
    """[(приоритет, слово)] по РЕАЛЬНЫМ эффектам; порядок — по зрелищности.

    run_function_word — слово профиля mcfunction-функции зачарования:
    ставится с МАКСИМАЛЬНЫМ приоритетом (кастомная функция — самая
    характерная фича), эффекты run_function в компонентах дают то же
    слово (без дубля — dedup по seen)."""
    seeds = []
    seen = set()

    def pick(pool):
        if rng is not None and len(pool) > 1:
            return rng.choice(pool)
        return pool[0]

    def add(prio, word):
        if word and word not in seen:
            seen.add(word)
            seeds.append((prio, word))

    if run_function_word:
        add(9, run_function_word)

    for ckey, cval in effects.items():
        key = ckey.split(":", 1)[1] if ":" in ckey else ckey
        if key in _VE_WORDS or key in _VE_FLIP:
            eff = None
            if isinstance(cval, list) and cval and isinstance(cval[0], dict):
                eff = cval[0].get("effect", {})
            elif isinstance(cval, dict):
                eff = cval.get("effect", {})
            if key in _VE_FLIP:
                s = _ve_sign(eff)
                neg, zero, pos = _VE_FLIP[key]
                pool = neg if s < -1e-9 else (pos if s > 1e-9 else zero)
                add(_VE_PRIO.get(key, 5), pick(pool))
            else:
                add(_VE_PRIO.get(key, 5), pick(_VE_WORDS[key]))
        elif key in ("post_attack", "hit_block", "post_piercing_attack",
                     "projectile_spawned", "tick", "location_changed"):
            entries = cval if isinstance(cval, list) else [cval]
            prio = {"post_attack": 8, "hit_block": 8, "post_piercing_attack": 8,
                    "projectile_spawned": 8, "tick": 5, "location_changed": 7}[key]
            for ent in entries:
                if not isinstance(ent, dict):
                    continue
                w = _ee_word(ent.get("effect", {}), run_function_word)
                if w:
                    add(prio, w)
                    break
        elif key == "damage_immunity":
            word = "Неприступность"
            for ent in (cval if isinstance(cval, list) else [cval]):
                if not isinstance(ent, dict):
                    continue
                for rq in ent.get("requirements", []):
                    if not isinstance(rq, dict):
                        continue
                    tags = (rq.get("predicate") or {}).get("tags", [])
                    for tg in tags:
                        if tg in _DTAG_WORDS:
                            word = _DTAG_WORDS[tg]
                            break
            add(7, word)
        elif key == "attributes":
            for ent in (cval if isinstance(cval, list) else [cval]):
                if isinstance(ent, dict) and ent.get("attribute") in _ATTR_WORDS:
                    add(6, _ATTR_WORDS[ent["attribute"]])
                    break
        elif key == "crossbow_charging_sounds":
            add(3, "Скрип Взвода")
        elif key == "trident_sound":
            add(3, "Голос Трезубца")
        elif key == "prevent_equipment_drop":
            add(5, "Проклятие Верности")
        elif key == "prevent_armor_change":
            add(5, "Проклятие Срастания")
    seeds.sort(key=lambda p: -p[0])
    return seeds


# множественные существительные из _NOUN («Узы») — прилагательное
# во множественном числе («Громовые Узы»)
_PLURAL_NOUNS = {"Узы"}


def _noun_gender(w):
    """Род существительного из _NOUN: 'm'/'f'/'n' или 'p' (мн.ч.).
    В отличие от _word_gender (слова эффектов, мн.ч. там = None и
    прилагательные пропускаются), здесь множественное склоняется."""
    if w in _PLURAL_NOUNS:
        return "p"
    return _word_gender(w)


def _rand_name(rng):
    """Русское название в стиле генератора: «Раскол Мешка Соли».
    Прилагательное согласуется с родом существительного
    (_noun_gender + _inflect_adj): «Громовая Буря», «Раскалённое Пламя
    Морока», «Медвежьи Узы Долга»."""
    r = rng.random()
    if r < 0.45:
        return "%s %s" % (rng.choice(_NOUN), rng.choice(_GEN))
    adj = rng.choice(_ADJ)
    noun = rng.choice(_NOUN)
    g = _noun_gender(noun)
    if g is not None:
        adj = _inflect_adj(adj, g)
    if r < 0.80:
        return "%s %s" % (adj, noun)
    return "%s %s %s" % (adj, noun, rng.choice(_GEN))


def _effect_name(rng, effects, profile=None, run_function_word=None):
    """Название из РЕАЛЬНЫХ эффектов: «Громовое Пробитие», «Яд и Отброс»,
    «Проклятие Хрупкости Бездны». Прилагательное согласуется с родом слова.
    run_function_word — слово профиля функции («Клык», «Скорость»...).
    Фолбэк — вкусовое _rand_name."""
    seeds = _name_seeds(effects, rng, run_function_word)
    if not seeds:
        return _rand_name(rng)
    lead = seeds[0][1]
    second = seeds[1][1] if len(seeds) > 1 else None
    g = _word_gender(lead)
    r = rng.random()
    if r < 0.10 or len(lead) > 16:
        return lead
    if g is not None and r < 0.40:
        return "%s %s" % (_inflect_adj(rng.choice(_ADJ), g), lead)
    if r < 0.60:
        return "%s %s" % (lead, rng.choice(_GEN))
    if second and r < 0.72:
        return "%s и %s" % (lead, second)
    if second and r < 0.84 and len(lead) + len(second) <= 20:
        return "%s-%s" % (lead, second)
    if g is not None:
        return "%s %s %s" % (_inflect_adj(rng.choice(_ADJ), g), lead,
                              rng.choice(_GEN))
    return "%s %s" % (lead, rng.choice(_GEN))


# ---------------------------------------------------------------------------
# Генератор mcfunction для run_function-эффектов (контракты — докстринг
# модуля). Каждая категория = отдельная функция-строитель, возвращает
# (строки, слово_для_названия); диспетчер _gen_ench_function собирает
# 1-10 команд (worn: 1-3) без повторов категорий и считает бюджет строк.
# ---------------------------------------------------------------------------

# частицы без аргументов (реестр particles jar 26.2 — сверено javap'ом
# ParticleTypes: все перечисленные ниже объявлены как SimpleParticleType,
# т.е. работают голой строкой minecraft:<id> в /particle)
_FN_PARTICLES = [
    "minecraft:flame", "minecraft:soul_fire_flame",
    "minecraft:end_rod", "minecraft:electric_spark",
    "minecraft:enchant", "minecraft:enchanted_hit",
    "minecraft:crit", "minecraft:glow", "minecraft:portal",
    "minecraft:witch", "minecraft:smoke", "minecraft:white_smoke",
    "minecraft:large_smoke", "minecraft:poof", "minecraft:dragon_breath",
    "minecraft:totem_of_undying", "minecraft:sonic_boom",
    "minecraft:gust", "minecraft:small_gust",
    "minecraft:sculk_soul", "minecraft:soul",
    "minecraft:firefly", "minecraft:snowflake",
    "minecraft:lava", "minecraft:heart", "minecraft:splash",
    "minecraft:angry_villager", "minecraft:happy_villager",
    "minecraft:infested", "minecraft:sweep_attack",
    "minecraft:reverse_portal", "minecraft:small_flame",
    "minecraft:note", "minecraft:explosion",
    "minecraft:explosion_emitter", "minecraft:firework",
    "minecraft:dust_plume", "minecraft:ominous_spawning",
    "minecraft:vault_connection", "minecraft:trial_omen",
    "minecraft:raid_omen", "minecraft:spit", "minecraft:sneeze",
    "minecraft:squid_ink", "minecraft:glow_squid_ink",
    "minecraft:elder_guardian", "minecraft:nautilus",
    "minecraft:spore_blossom_air", "minecraft:crimson_spore",
    "minecraft:warped_spore", "minecraft:campfire_cosy_smoke",
    "minecraft:campfire_signal_smoke", "minecraft:wax_on",
    "minecraft:cherry_leaves", "minecraft:pale_oak_leaves",
    "minecraft:copper_fire_flame", "minecraft:noxious_gas",
    "minecraft:noxious_gas_cloud", "minecraft:sulfur_bubbles",
    "minecraft:sulfur_cube_goo"]

# параметризованные частицы (сверено байткодом jar 26.2):
#   dust{color,scale}                     DustParticleOptions: color (RGB int)
#     и scale — ОБА обязательные fieldOf
#   dust_color_transition{from_color,to_color,scale}
#                                         DustColorTransitionOptions: все
#     три обязательные
#   entity_effect{color} / flash{color}   ColorParticleOption: color
#   dragon_breath{power}                  PowerParticleOption: power
#     (optionalFieldOf с default 1.0, но пишем всегда)
# использует _fn_pick_particle

# цвета dust-частиц: палитра ~30 (DustParticleOptions.CODEC — color: int RGB
# 0..0xFFFFFF + scale: float)
_FN_DUST_COLORS = [0xFFD700, 0x00E5FF, 0xFF55FF, 0x7CFC00, 0xFF4500,
                   0x40E0D0, 0xFF69B4, 0x9370DB, 0xF5DEB3, 0x00FF7F,
                   0x1E90FF, 0xFFDAB9, 0xDC143C, 0x87CEEB, 0xDA70D6,
                   0x00FF00, 0xFF1493, 0x00CED1, 0x7FFF00, 0xFF8C00,
                   0xB22222, 0x9932CC, 0x20B2AA, 0xADFF2F, 0x4B0082,
                   0xF08080, 0xE0FFFF, 0xFF00FF, 0x00BFFF, 0xC71585]

# звуки для playsound: _SOUNDS (пул модуля, сверенный по jar) + атмосферные
# из полного реестра SoundEvents jar 26.2 (1874 id; каждый сверен грепом)
_FN_SOUNDS = _SOUNDS + [
    "minecraft:block.enchantment_table.use", "minecraft:item.totem.use",
    "minecraft:block.end_portal.spawn", "minecraft:block.respawn_anchor.charge",
    "minecraft:entity.elder_guardian.curse", "minecraft:entity.evoker.prepare_attack",
    "minecraft:block.note_block.pling", "minecraft:entity.ender_dragon.growl",
    "minecraft:entity.wither.spawn", "minecraft:item.shield.block",
    "minecraft:entity.warden.roar", "minecraft:entity.ravager.roar",
    "minecraft:block.portal.travel", "minecraft:entity.evoker.prepare_summon",
    "minecraft:entity.evoker.prepare_wololo", "minecraft:entity.phantom.flap",
    "minecraft:block.beacon.power_select", "minecraft:item.trident.throw",
    "minecraft:entity.ghast.scream", "minecraft:entity.experience_orb.pickup",
    "minecraft:entity.zombie.ambient", "minecraft:entity.enderman.stare"]

# самобаффы (только full/event): 3-10 с, усилитель 0-1, частицы скрыты
# (реестр MobEffects 26.2: все id существуют; только безопасные позитивные)
_FN_SELF_EFFECTS = ["minecraft:speed", "minecraft:haste",
                    "minecraft:strength", "minecraft:jump_boost",
                    "minecraft:regeneration", "minecraft:resistance",
                    "minecraft:fire_resistance", "minecraft:water_breathing",
                    "minecraft:night_vision", "minecraft:absorption",
                    "minecraft:slow_falling", "minecraft:saturation",
                    "minecraft:luck", "minecraft:dolphins_grace",
                    "minecraft:instant_health", "minecraft:invisibility",
                    "minecraft:health_boost", "minecraft:conduit_power",
                    "minecraft:hero_of_the_village",
                    "minecraft:breath_of_the_nautilus"]

# дебафы врагам (аура/облако): 2-5 с, усилитель 0-1 — только безопасные
# для баланса (без wither/Instant-урона/hunger/levitation)
_FN_AURA_EFFECTS = ["minecraft:slowness", "minecraft:weakness",
                    "minecraft:poison", "minecraft:mining_fatigue",
                    "minecraft:nausea", "minecraft:glowing",
                    "minecraft:darkness", "minecraft:blindness",
                    "minecraft:unluck"]

# флейвор-фразы для actionbar (короткие, атмосферные; без кавычек внутри —
# JSON-экранирует json.dumps в любом случае)
_FN_FLAVOR = ["Ты слышишь шёпот глубин...", "Клинок поёт...",
              "Мир дрожит...", "Древняя сила пробуждается",
              "Звёзды наблюдают за тобой", "Металл звенит от напряжения",
              "Тень сгущается...", "Что-то смотрит в ответ",
              "Воздух звенит от магии", "Ты чувствуешь холод вечности",
              "Земля едва слышно гудит", "Кровь кипит от азарта",
              "Пустота шепчет твоё имя", "Час пробил",
              "Меч жаждет боя", "Древний клинок голоден",
              "Магия звенит в воздухе", "Тьма отступает",
              "Судьба благосклонна", "Сталь помнит былые битвы",
              "Хватка судьбы крепка", "Ветер приносит вести",
              "Время течёт иначе здесь", "Ты чувствуешь взгляд из-за грани",
              "Пламя узнаёт тебя", "Рунный шёпот усиливается",
              "Звенит невидимый колокол", "Мир затаил дыхание",
              "Сила древних в твоих руках", "Свет собирается в фокус",
              # --- пополнение: рассветы, глубины, приметы ---
              "Рассвет близко. Или это пожар?",
              "Слышишь? И тишина услышала тебя",
              "Кто-то считает твои шаги",
              "Соль на губах — к дальней дороге",
              "Небо тяжелеет на глазах",
              "Старые боги ворочаются во сне",
              "Ветер несёт чужую песню",
              "Дым помнит каждый огонь",
              "Луна сегодня не та, что вчера",
              "Звёзды выстроились в ряд",
              "Твоя тень дышит тебе в затылок",
              "Где-то далеко скрипит колодец",
              "Земля слушает твои шаги",
              "Пыль оседает нехотя",
              "Молчание громче любого крика",
              "Мороз рисует на стекле знаки",
              "Костёр догорает до углей",
              "Колокол звонит сам собой",
              "Вода потемнела и затихла",
              "Ночь пробирается под кольчугу",
              "Дальние горы стали ближе",
              "Что-то щекочет край сознания",
              "Сердце бьётся вразнобой",
              "Птицы умолкли разом",
              "Туман пробует тебя на вкус",
              "Гром перекатывается за холмами",
              "Кто-то оставил дверь открытой",
              "Снег идёт против ветра",
              "Эхо вернулось без вопроса",
              "Уголёк в груди не гаснет",
              "Маяк мигает в чужом ритме",
              "Путь назад уже не узнать",
              "Ты здесь уже был. Или будешь",
              "Лёд на реке поёт на рассвете",
              "Паутина дрожит без ветра",
              "Заря тронула край мира",
              "Мешок с солью стал легче",
              "Волчий вой катится по долине",
              "Свеча гаснет и вспыхивает снова",
              "Твоё имя знают все ветра",
              "Глубины переворачиваются во сне",
              "Звон стоит в ушах",
              "Мир качнулся и выровнялся",
              "Огонь в очаге склонился к тебе",
              "Холодок пробегает между лопаток",
              "Пепел на ветру складывается в слова",
              "Чужой смех в дальнем лесу",
              "Ключ в кармане теплее руки",
              "Огни болот манят и ждут",
              "Медведь спит, но видит тебя"]

# формы фейерверка (FireworkExplosion$Shape: small_ball/large_ball/star/
# creeper/burst — snake_case БЕЗ префикса; сверено байткодом jar 26.2;
# биты — has_trail и has_twinkle)
_FN_FW_SHAPES = ["small_ball", "large_ball", "star", "creeper", "burst"]

# вспышечные частицы для категории «вспышка света» (все SimpleParticleType
# или ColorParticleOption — сверено по jar)
_FN_FLASH_PARTICLES = ["minecraft:end_rod", "minecraft:flash",
                       "minecraft:entity_effect", "minecraft:electric_spark",
                       "minecraft:glow", "minecraft:firework",
                       "minecraft:explosion"]

# звуки-компаньоны вспышки/тотема (сверены по реестру SoundEvents)
_FN_FLASH_SOUNDS = ["minecraft:block.beacon.activate",
                    "minecraft:block.bell.use", "minecraft:block.glass.break",
                    "minecraft:block.end_portal.spawn",
                    "minecraft:block.respawn_anchor.charge",
                    "minecraft:block.amethyst_block.chime"]

# частицы «жатвы» (сопровождение опыта)
_FN_HARVEST_PARTICLES = ["minecraft:happy_villager", "minecraft:glow",
                         "minecraft:firefly", "minecraft:enchant",
                         "minecraft:end_rod", "minecraft:electric_spark"]

# категории: (ключ, вес_full, вес_event, вес_worn) — 41 (20 исходных + 21
# новых: дождь/вихрь/купол/аккорд/хор/гамма/веер-полукруг/стена клыков/
# осколки/свечение/второе дыхание/шёпот/марш/пробуждение/клятва/дождь опыта/
# прощальный салют/кольца/кресты/звёзды/спираль вниз). В worn доступны
# только дешёвые гейченые (частицы/звук/фразы/перекраска/шёпот/клятва/
# эхо/вспышка/тотем/гром-звук); молния — только full; призывы (клыки/
# облака/фейерверки/XP) и effect give — не в worn.
_FN_CAT_W = [
    ("particle", 16, 14, 26),
    ("sound", 13, 13, 22),
    ("fangs", 11, 9, 0),
    ("cloud", 8, 7, 0),
    ("firework", 4, 4, 0),
    ("selfbuff", 10, 6, 0),
    ("aura", 8, 7, 0),
    ("flavor", 6, 6, 9),
    ("recolor", 7, 7, 8),    # только при mod_ids (перекрасить нечем)
    ("xp", 3, 3, 0),
    ("lightning", 2, 0, 0),  # редкий тяжёлый тир, только full
    ("echo", 6, 6, 8),       # 2-3 playsound с нарастающим pitch
    ("flash", 7, 7, 8),      # вспышка света: частицы + звук
    ("totem", 5, 5, 6),      # тотемный визуал: частица + item.totem.use
    ("thunder", 4, 4, 5),    # грозовое эхо: только звук грома, без молнии
    ("glow2", 5, 5, 6),      # жертвенное свечение: mainhand + offhand modify
    ("fw2", 3, 3, 0),        # двойной фейерверк с разными зарядами
    ("auraring", 5, 5, 0),   # 2-3 кольца дебафа разных радиусов
    ("duet", 6, 4, 0),       # самобафф-дуэт: 2 эффекта сразу
    ("harvest", 3, 3, 0),    # жатва: 2-4 орба опыта + частицы
    # --- НОВЫЕ (21) ---
    ("rain", 7, 7, 10),      # дождь частиц сверху
    ("vortex", 7, 6, 8),     # вихрь: спираль с растущим радиусом
    ("dome", 6, 6, 8),       # купол-полусфера над игроком
    ("chord", 7, 6, 8),      # аккорд-арпеджио 3-5 звуков
    ("choir", 6, 5, 6),      # хор: звук с нескольких сторон
    ("gamma", 5, 5, 0),      # 2-3 облака эффекта ярусами по высоте
    ("fangarc", 7, 6, 0),    # веер клыков полукругом 90-180°
    ("fangwall", 6, 6, 0),   # стена клыков поперёк взгляда
    ("shards", 7, 6, 8),     # осколки: частицы block{block_state}
    ("glow", 4, 4, 0),       # свечение: glowing 10-30 c (гейт)
    ("secondwind", 5, 4, 0), # второе дыхание: 2 баффа разных длительностей
    ("whisper", 3, 3, 4),    # шёпот: tellraw цветной флейвор в чат (редко)
    ("march", 5, 5, 5),      # марш: звуки с нарастающей громкостью
    ("awakening", 5, 5, 5),  # пробуждение: вспышка + гром + частицы
    ("oath", 4, 4, 4),       # клятва: modify обеих рук + title (mod_ids)
    ("xprain", 3, 3, 0),     # дождь опыта: 4-8 орбов (гейт)
    ("farewell", 4, 4, 0),   # прощальный салют: firework с fade_colors
    ("rings", 7, 6, 8),      # многослойные кольца 2-3 радиусов
    ("crosses", 6, 5, 7),    # кресты из частиц
    ("stars", 6, 6, 7),      # звёзды: лучи из центра
    ("downspiral", 6, 5, 7), # спираль вниз (воронка)
]

# приоритет «зрелищности» категории → её слово идёт в название
_FN_CAT_PRIO = {"lightning": 10, "fangs": 9, "cloud": 8, "firework": 7,
                "fw2": 7, "selfbuff": 6, "aura": 6, "auraring": 6,
                "duet": 6, "recolor": 5, "glow2": 5, "totem": 5,
                "xp": 4, "harvest": 4, "particle": 3, "flash": 3,
                "thunder": 3, "sound": 2, "echo": 2, "flavor": 1,
                "rain": 4, "vortex": 5, "dome": 4, "chord": 4,
                "choir": 4, "gamma": 5, "fangarc": 6, "fangwall": 6,
                "shards": 4, "glow": 4, "secondwind": 5, "whisper": 2,
                "march": 3, "awakening": 5, "oath": 5, "xprain": 4,
                "farewell": 6, "rings": 4, "crosses": 4, "stars": 4,
                "downspiral": 4}

_FN_CTX_DESC = {
    "full": "post_attack — вызывается после удара; @s = владелец предмета",
    "event": "hit_block / post_piercing_attack / projectile_spawned",
    "worn": "tick / location_changed — каждый тик, все команды гейчены",
}


def _has_run_function(node):
    """Есть ли run_function в дереве эффекта (в т.ч. внутри all_of)."""
    if isinstance(node, dict):
        if node.get("type") == "minecraft:run_function":
            return True
        return any(_has_run_function(v) for v in node.values())
    if isinstance(node, list):
        return any(_has_run_function(v) for v in node)
    return False


def _ench_rf_context(effects):
    """Контекст вызова функции зачарования: worn (tick/location_changed —
    самый частый и строгий, приоритетен), full (post_attack), event
    (hit_block/post_piercing_attack/projectile_spawned). Одна функция на
    зачарование обязана быть безопасной в ЛЮБОМ контексте, куда попал
    run_function, поэтому выбираем строжайший."""
    for comp in ("minecraft:tick", "minecraft:location_changed"):
        if _has_run_function(effects.get(comp)):
            return "worn"
    if _has_run_function(effects.get("minecraft:post_attack")):
        return "full"
    for comp in ("minecraft:hit_block", "minecraft:post_piercing_attack",
                 "minecraft:projectile_spawned"):
        if _has_run_function(effects.get(comp)):
            return "event"
    return None


def _fn_gate(rng, cfg, chance):
    """Гейт-предикат random_chance → префикс 'execute if predicate ... run '.

    Предикат пишется в gate_predicates (его обязан сохранить основной
    скрипт в predicate/); id = <ench>_p<N> — уникален в рамках функции."""
    cfg["gi"][0] += 1
    pid = "%s:%s_p%d" % (cfg["ns"], cfg["fname"], cfg["gi"][0])
    cfg["gates"][pid] = {"condition": "minecraft:random_chance",
                         "chance": chance}
    return "execute if predicate %s run " % pid


def _fn_gated(gate, line):
    """Гейтит команду; если та уже начинается с execute — вливает гейт
    ВНУТРЬ цепочки (без уродливого вложенного 'execute ... run execute')."""
    if line.startswith("execute "):
        return ("execute " + gate[len("execute "):-4]
                + line[len("execute "):])
    return gate + line


def _fn_num(v, nd=2):
    """Число с фикс. знаками без '-0.00' и экспоненты (для смещений
    ~X/^X в командах)."""
    if v == 0:  # заодно убирает -0.0
        v = 0.0
    s = "%.*f" % (nd, v)
    if s.startswith("-") and float(s) == 0.0:
        s = s[1:]
    return s


def _fn_pick_particle(rng):
    """(строка particle, id-для-слова): простые из пула + параметризованные
    dust / dust_color_transition / entity_effect / flash / dragon_breath
    (обязательность полей — см. комментарий над _FN_DUST_COLORS)."""
    r = rng.random()
    if r < 0.17:
        return ("minecraft:dust{color:%d,scale:%s}"
                % (rng.choice(_FN_DUST_COLORS), _f(rng, 0.8, 2.2)),
                "minecraft:dust")
    if r < 0.25:
        return ("minecraft:dust_color_transition{from_color:%d,to_color:%d,"
                "scale:%s}"
                % (rng.choice(_FN_DUST_COLORS), rng.choice(_FN_DUST_COLORS),
                   _f(rng, 0.8, 2.0)),
                "minecraft:dust_color_transition")
    if r < 0.31:
        return ("minecraft:entity_effect{color:%d}"
                % rng.choice(_FN_DUST_COLORS), "minecraft:entity_effect")
    if r < 0.36:
        return ("minecraft:flash{color:%d}"
                % rng.choice(_FN_DUST_COLORS), "minecraft:flash")
    if r < 0.40:
        return ("minecraft:dragon_breath{power:%s}"
                % _f(rng, 0.5, 2.0), "minecraft:dragon_breath")
    p = rng.choice(_FN_PARTICLES)
    return p, p


def _fn_pt_at(p, x, y, z, d=0.04):
    """Одиночная частица-точка геометрии: execute at @s positioned
    ~X ~Y ~Z (смещения уже посчитаны генератором)."""
    return ("execute at @s positioned ~%s ~%s ~%s run particle %s "
            "~ ~ ~ %s %s %s 0 1 force" % (x, y, z, p, d, d, d))


def _fn_particle_cmd(rng, cfg, ctx, budget):
    """Частицы — 10 форм геометрии (смещения считает генератор, команды
    получают готовые координаты):
      eyes    — вспышка перед глазами смотрящего (anchored eyes + локальные)
      beam    — простой пучок над головой
      sector  — сектор перед исполнителем (горизонталь через rotated ~ 0)
      ring    — кольцо 6-10 точек вокруг (positioned ~dx ~h ~dz)
      spiral  — вертикальная спираль: угол и радиус растут с высотой
      dome    — купол-полусфера 6-10 точек над головой (сферическая спираль)
      arc     — арка-полуокружность над головой вдоль случайного азимута
      trail   — «след» вдоль взгляда 5-8 точек (^ ^ ^N, в т.ч. по питчу)
      pillar  — вертикальный столб 3-6 точек (positioned ~ ~N ~)
      curtain — стена-занавес 2-3 ряда × 2-3 колонки, перпендикулярно взгляду
    Плюс параметризованные частицы (dust/dust_color_transition/entity_effect/
    flash/dragon_breath — см. _fn_pick_particle)."""
    p, word_p = _fn_pick_particle(rng)
    count = rng.randint(3, 14)
    dx, dy, dz = _f(rng, 0.1, 0.6), _f(rng, 0.1, 0.5), _f(rng, 0.1, 0.6)
    speed = _f(rng, 0.0, 0.05)
    form = rng.choices(
        ["eyes", "beam", "sector", "ring", "spiral", "dome", "arc",
         "trail", "pillar", "curtain"],
        weights=[14, 8, 8, 12, 12, 11, 9, 11, 7, 8], k=1)[0]
    if form == "eyes":
        # перед глазами смотрящего
        dist = _f(rng, 0.4, 1.0)
        lines = ["execute at @s anchored eyes positioned ^ ^ ^%s run "
                 "particle %s ~ ~ ~ %s %s %s %s %d"
                 % (dist, p, dx, dy, dz, speed, count)]
    elif form == "beam":
        # простой пучок над головой
        lines = ["particle %s ~ ~%s ~ %s %s %s %s %d"
                 % (p, _f(rng, 1.0, 1.6), dx, dy, dz, speed, count)]
    elif form == "sector":
        # сектор перед исполнителем (горизонталь — rotated ~ 0)
        lines = ["execute at @s rotated ~%d 0 run particle %s ^ ^1.2 ^1.0 "
                 "%s 0.1 %s %s %d"
                 % (rng.randint(-25, 25), p, dx, dz, speed, count)]
    elif form == "ring":
        # кольцо: n точек по кругу через positioned (смещения ~dx/~dz)
        n = max(3, min(rng.randint(6, 10), budget))
        rad, h = _f(rng, 0.8, 1.8), _f(rng, 1.0, 1.4)
        a0 = rng.uniform(0, 2.0 * math.pi)
        lines = [_fn_pt_at(
            p, _fn_num(rad * math.cos(a0 + 2.0 * math.pi * k / n)),
            _fn_num(h),
            _fn_num(rad * math.sin(a0 + 2.0 * math.pi * k / n)))
            for k in range(n)]
    elif form == "spiral":
        # спираль: радиус r0→r1, высота растёт, 1-2 оборота
        n = max(3, min(rng.randint(6, 10), budget))
        r0, r1 = _f(rng, 0.5, 1.0), _f(rng, 1.6, 3.0)
        h0, dh = _f(rng, 0.2, 0.6), _f(rng, 0.25, 0.5)
        turns = rng.choice([1, 1, 2])
        a0 = rng.uniform(0, 2.0 * math.pi)
        lines = []
        for k in range(n):
            t = k / max(1, n - 1)
            a = a0 + turns * 2.0 * math.pi * t
            rk = r0 + (r1 - r0) * t
            lines.append(_fn_pt_at(
                p, _fn_num(rk * math.cos(a)), _fn_num(h0 + dh * k),
                _fn_num(rk * math.sin(a))))
    elif form == "dome":
        # купол-полусфера: высота растёт с углом места, азимут 5-кратный
        n = max(3, min(rng.randint(6, 10), budget))
        rad = _f(rng, 1.4, 2.6)
        a0 = rng.uniform(0, 2.0 * math.pi)
        lines = []
        for k in range(n):
            t = k / max(1, n - 1)
            phi = (math.pi / 2.0) * t
            a = a0 + k * (2.0 * math.pi / 5.0)
            rr = rad * math.cos(phi)
            lines.append(_fn_pt_at(
                p, _fn_num(rr * math.cos(a)),
                _fn_num(0.3 + rad * math.sin(phi)),
                _fn_num(rr * math.sin(a))))
    elif form == "arc":
        # арка: полуокружность над головой вдоль азимута a0
        n = max(3, min(rng.randint(6, 10), budget))
        rad = _f(rng, 1.5, 2.8)
        a0 = rng.uniform(0, 2.0 * math.pi)
        lines = []
        for k in range(n):
            th = math.pi * k / max(1, n - 1)
            rr = rad * math.cos(th)
            lines.append(_fn_pt_at(
                p, _fn_num(rr * math.cos(a0)),
                _fn_num(0.2 + rad * math.sin(th)),
                _fn_num(rr * math.sin(a0))))
    elif form == "trail":
        # «след» вдоль взгляда: локальные координаты следуют и питчу
        n = max(2, min(rng.randint(5, 8), budget))
        step = _f(rng, 0.7, 1.2)
        lines = ["execute at @s run particle %s ^ ^ ^%s 0.02 0.02 0.02 0 1 "
                 "force" % (p, _fn_num(step * (k + 1))) for k in range(n)]
    elif form == "pillar":
        # вертикальный столб точек
        n = max(2, min(rng.randint(3, 6), budget))
        step = _f(rng, 0.5, 0.8)
        sx = _fn_num(_f(rng, -0.3, 0.3))
        sz = _fn_num(_f(rng, -0.3, 0.3))
        lines = [_fn_pt_at(p, sx, _fn_num(0.3 + step * k), sz)
                 for k in range(n)]
    else:  # curtain — стена-занавес перпендикулярно взгляду
        cols, rows = rng.randint(2, 3), rng.randint(2, 3)
        while cols * rows > budget and rows > 2:
            rows -= 1
        while cols * rows > budget and cols > 2:
            cols -= 1
        w = _f(rng, 0.6, 1.1)
        fwd = _fn_num(_f(rng, 1.6, 2.6))
        ys = [_f(rng, 0.6 + 0.7 * j, 1.0 + 0.7 * j) for j in range(rows)]
        xs = [[-w, w], [-w, 0.0, w], [0.0]][cols - 1] if cols <= 3 else [0.0]
        lines = ["execute at @s rotated ~ 0 positioned ^%s ^%s ^%s run "
                 "particle %s ~ ~ ~ 0.02 0.02 0.02 0 1 force"
                 % (_fn_num(x), _fn_num(y), fwd, p)
                 for y in ys for x in xs]
    if ctx == "worn":
        # каждый тик — только изредка (иначе спам)
        gate = _fn_gate(rng, cfg, _f(rng, 0.02, 0.08))
        lines = [_fn_gated(gate, l) for l in lines]
    elif _chance(rng, 0.15):
        gate = _fn_gate(rng, cfg, _f(rng, 0.3, 0.7))
        lines = [_fn_gated(gate, l) for l in lines]
    return lines, _PART_WORDS.get(word_p, "Блеск")


def _fn_sound_cmd(rng, cfg, ctx):
    """Звук: playsound @s master с рандомным звуком (48 ванильных —
    _FN_SOUNDS, каждый сверен по реестру SoundEvents 26.2), громкость
    0.3-2.0, тон 0.5-2.0, иногда источник «над головой» (positioned)."""
    snd = rng.choice(_FN_SOUNDS)
    vol, pitch = _f(rng, 0.3, 2.0), _f(rng, 0.5, 2.0)
    if _chance(rng, 0.35):
        line = ("execute positioned ~ ~%s ~ run playsound %s master @s "
                "~ ~ ~ %s %s" % (_f(rng, 1.0, 2.0), snd, vol, pitch))
    else:
        line = "playsound %s master @s ~ ~ ~ %s %s" % (snd, vol, pitch)
    if ctx == "worn":
        gate = _fn_gate(rng, cfg, _f(rng, 0.005, 0.02))
        line = _fn_gated(gate, line)
    elif _chance(rng, 0.2):
        line = _fn_gated(_fn_gate(rng, cfg, _f(rng, 0.3, 0.7)), line)
    return [line], rng.choice(["Голос", "Гимн", "Эхо"])


def _fn_fangs_cmd(rng, cfg, budget):
    """Клыки заклинателя — 7 форм геометрии:
      line   — линия 3-6 по взгляду (^ ^ ^N, горизонталь через rotated ~ 0)
      fan    — веер 3-4 направления (rotated ~±15..45)
      cross  — крест из 4 (rotated ~0/90/180/270)
      arc    — дуга 5-8: полукруг по rotам (rotated ~-90..90)
      ring   — кольцо 8-12 вокруг игрока (посчитанные смещения ~X ~ ~Z,
               радиус 2.3-3.4 — владелец вне зоны укуса)
      spiral — спираль: угол и радиус растут (1.2→4.0)
      wall   — стена перпендикулярно взгляду (rotated ~±90: ось «влево»
               после поворота совпадает со старым взглядом — ^±2 смещает
               стену вперёд, ^k расставляет клыки поперёк)"""
    form = rng.choices(
        ["line", "fan", "cross", "arc", "ring", "spiral", "wall"],
        weights=[10, 10, 7, 12, 14, 12, 12], k=1)[0]
    if form == "cross":
        dist = rng.randint(2, 4)
        lines = ["execute at @s rotated ~%d 0 run summon "
                 "minecraft:evoker_fangs ^ ^ ^%d" % (d, dist)
                 for d in (0, 90, 180, 270)]
    elif form == "fan":
        k = min(rng.randint(3, 4), budget)
        dirs = sorted(rng.sample([-45, -30, -15, 15, 30, 45], k))
        dist = rng.randint(2, 4)
        lines = ["execute at @s rotated ~%d 0 run summon "
                 "minecraft:evoker_fangs ^ ^ ^%d" % (d, dist) for d in dirs]
    elif form == "arc":
        # дуга: n клыков по дуге ±span/2 градусов перед исполнителем
        n = max(2, min(rng.randint(5, 8), budget))
        span = rng.choice([120, 150, 180])
        dist = rng.randint(2, 3)
        dirs = [(-span // 2 + span * k // max(1, n - 1)) for k in range(n)]
        lines = ["execute at @s rotated ~%d 0 run summon "
                 "minecraft:evoker_fangs ^ ^ ^%d" % (d, dist) for d in dirs]
    elif form == "ring":
        # кольцо вокруг владельца: смещения посчитаны, один summon на клык
        n = max(4, min(rng.randint(8, 12), budget))
        rad = _f(rng, 2.3, 3.4)
        a0 = rng.uniform(0, 2.0 * math.pi)
        lines = ["summon minecraft:evoker_fangs ~%s ~ ~%s"
                 % (_fn_num(rad * math.cos(a0 + 2.0 * math.pi * k / n)),
                    _fn_num(rad * math.sin(a0 + 2.0 * math.pi * k / n)))
                 for k in range(n)]
    elif form == "spiral":
        n = max(3, min(rng.randint(6, 9), budget))
        r0, r1 = _f(rng, 1.2, 1.8), _f(rng, 2.8, 4.0)
        da = math.radians(rng.randint(40, 70))
        a0 = rng.uniform(0, 2.0 * math.pi)
        lines = []
        for k in range(n):
            t = k / max(1, n - 1)
            rk = r0 + (r1 - r0) * t
            a = a0 + da * k
            lines.append("summon minecraft:evoker_fangs ~%s ~ ~%s"
                         % (_fn_num(rk * math.cos(a)),
                            _fn_num(rk * math.sin(a))))
    elif form == "wall":
        rot = rng.choice([90, -90])
        ahead = 2.0 if rot == 90 else -2.0
        half = 1 if budget < 5 else rng.randint(1, 2)
        lines = ["execute at @s rotated ~%d 0 run summon "
                 "minecraft:evoker_fangs ^%s ^ ^%s"
                 % (rot, _fn_num(ahead), _fn_num(k))
                 for k in range(-half, half + 1)]
    else:  # line
        start = rng.randint(1, 2)
        n = max(2, min(rng.randint(3, 6), budget, 6 - start + 1))
        lines = ["execute at @s rotated ~ 0 run summon "
                 "minecraft:evoker_fangs ^ ^ ^%d" % k
                 for k in range(start, start + n)]
    return lines, "Клык"


def _fn_cloud_cmd(rng, cfg, budget):
    """Облака эффектов: одно ВПЕРЁДИ по взгляду или связка 2-3 на разных
    смещениях (влево/вправо/вверх с джиттером). NBT 26.2 — Radius:Xf
    (float!), Duration 60-200, WaitTime, potion_contents.custom_effects
    (1-3 эффекта; id/amplifier/duration/ambient/visible — кодек
    MobEffectInstance) и с шансом 35% custom_color (окраска облака,
    PotionContents); 20% — облачко медленно всплывает (Motion)."""
    n_clouds = min(rng.choices([1, 2, 3], weights=[5, 3, 2], k=1)[0], budget)
    lines = []
    for i in range(n_clouds):
        n_eff = 1 if _chance(rng, 0.65) else rng.randint(2, 3)
        effs = rng.sample(_FN_AURA_EFFECTS, n_eff)
        dur_eff = rng.randint(40, 100)
        custom = ",".join(
            '{id:"%s",amplifier:%d,duration:%d,ambient:1b,visible:0b}'
            % (e, rng.randint(0, 1), dur_eff) for e in effs)
        nbt = ("{Radius:%sf,Duration:%d,WaitTime:%d,"
               "potion_contents:{custom_effects:[%s]%s}}"
               % (_f(rng, 2.0, 5.0) if n_clouds == 1 else _f(rng, 1.2, 3.0),
                  rng.randint(60, 200),
                  0 if _chance(rng, 0.6) else rng.randint(0, 20), custom,
                  (",custom_color:%d" % rng.choice(_FN_DUST_COLORS))
                  if _chance(rng, 0.35) else ""))
        if _chance(rng, 0.2):  # медленно всплывающее облачко
            nbt = nbt[:-1] + ",Motion:[0.0,%s,0.0]}" % _f(rng, 0.02, 0.08)
        if n_clouds == 1:
            dist = _f(rng, 2.0, 3.5)
            lines.append("execute at @s rotated ~ 0 run summon "
                         "minecraft:area_effect_cloud ^ ^ ^%s %s"
                         % (dist, nbt))
        else:
            # связка: разные смещения от взгляда (джиттер поверх базовых)
            lx, ly, lz = [(-1.4, 0.3, 2.2), (1.4, 0.9, 1.8),
                          (0.0, 1.4, 1.4)][i]
            lines.append("execute at @s rotated ~ 0 run summon "
                         "minecraft:area_effect_cloud ^%s ^%s ^%s %s"
                         % (_fn_num(lx + _f(rng, -0.3, 0.3)),
                            _fn_num(ly + _f(rng, -0.2, 0.4)),
                            _fn_num(lz + _f(rng, -0.4, 0.4)), nbt))
    return lines, "Облако"


def _fn_fw_explosion(rng):
    """SNBT одного заряда фейерверка (FireworkExplosion 26.2 — поля shape/
    colors/fade_colors/has_trail/has_twinkle, имена сверены байткодом)."""
    shape = rng.choice(_FN_FW_SHAPES)
    colors = [rng.choice(_FN_DUST_COLORS) for _ in range(rng.randint(1, 3))]
    return '{shape:"%s",colors:[%s]%s%s%s}' % (
        shape, ",".join(str(c) for c in colors),
        (",fade_colors:[%s]" % ",".join(
            str(rng.choice(_FN_DUST_COLORS))
            for _ in range(rng.randint(1, 2))))
        if _chance(rng, 0.45) else "",
        ",has_trail:1b" if _chance(rng, 0.3) else "",
        ",has_twinkle:1b" if _chance(rng, 0.25) else "")


def _fn_firework_cmd(rng, cfg):
    """Фейерверк-визуал: ракета с компонентом fireworks (FireworksItem —
    item stack SNBT: id/count/components{"minecraft:fireworks":...}),
    взрыв далеко впереди (3.5-5 блока — владелец вне радиуса), короткий
    LifeTime 10-25 тиков."""
    item = ('{id:"minecraft:firework_rocket",count:1,'
            'components:{"minecraft:fireworks":{flight_duration:1,'
            'explosions:[%s]}}}' % _fn_fw_explosion(rng))
    nbt = "{LifeTime:%d,FireworksItem:%s%s}" % (
        rng.randint(10, 25), item,
        ",Motion:[0.0,0.35,0.0]" if _chance(rng, 0.5) else "")
    return ["execute at @s rotated ~ 0 run summon minecraft:firework_rocket "
            "^ ^ ^%s %s" % (_f(rng, 3.5, 5.0), nbt)], "Фейерверк"


def _fn_fw2_cmd(rng, cfg):
    """Двойной фейерверк: две ракеты с РАЗНЫМИ зарядами (форма/палитра/
    fade_colors/биты has_trail/has_twinkle), с разных смещений от
    взгляда (слева/справа) — залп."""
    lines = []
    for lx, ly, lz in [(-1.2, 0.5, 3.2), (1.2, 1.0, 3.6)]:
        item = ('{id:"minecraft:firework_rocket",count:1,'
                'components:{"minecraft:fireworks":{flight_duration:%d,'
                'explosions:[%s]}}}'
                % (rng.randint(0, 2), _fn_fw_explosion(rng)))
        nbt = "{LifeTime:%d,FireworksItem:%s}" % (rng.randint(10, 30), item)
        lines.append("execute at @s rotated ~ 0 run summon "
                     "minecraft:firework_rocket ^%s ^%s ^%s %s"
                     % (_fn_num(lx + _f(rng, -0.3, 0.3)),
                        _fn_num(ly + _f(rng, -0.2, 0.3)),
                        _fn_num(lz + _f(rng, -0.5, 0.5)), nbt))
    return lines, "Салют"


def _fn_selfbuff_cmd(rng, cfg, ctx):
    """Самобафф владельцу: 15-45 с (было 3-10 — юзер: слишком коротко),
    усилитель 0-1, частицы скрыты (true).
    В worn запрещён (каждый тик обновлял бы таймер = перманентный баф)."""
    eff = rng.choice(_FN_SELF_EFFECTS)
    cmd = "effect give @s %s %d %d true" % (
        eff, rng.randint(15, 45), rng.randint(0, 1))
    if _chance(rng, 0.35):
        return [_fn_gate(rng, cfg, _f(rng, 0.25, 0.6)) + cmd], \
            _EFF_WORDS.get(eff, "Дар")
    return [cmd], _EFF_WORDS.get(eff, "Дар")


def _fn_aura_cmd(rng, cfg):
    """Дебаф-аура вокруг владельца: только мобам в радиусе 6-8 (type=!player
    исключает и владельца-игрока), 2-5 с, усилитель 0-1."""
    eff = rng.choice(_FN_AURA_EFFECTS)
    sel = "@e[distance=..%d,type=!player,type=!item,type=!experience_orb]" % (
        rng.choice([6, 7, 8]))
    return ["execute at @s run effect give %s %s %d 0 true"
            % (sel, eff, rng.randint(2, 5))], _EFF_WORDS.get(eff, "Сглаз")


def _fn_flavor_cmd(rng, cfg, ctx):
    """Флейвор-фраза в actionbar (русские фразы, JSON-валидно через
    json.dumps). В worn — гейт ~0.05 (требование юзера)."""
    msg = {"text": rng.choice(_FN_FLAVOR)}
    if _chance(rng, 0.5):
        msg["color"] = rng.choice(
            ["gold", "aqua", "light_purple", "yellow", "green"])
    if _chance(rng, 0.6):
        msg["italic"] = False
    cmd = "title @s actionbar %s" % json.dumps(
        msg, ensure_ascii=False, separators=(",", ":"))
    if ctx == "worn":
        return [_fn_gate(rng, cfg, _f(rng, 0.03, 0.06)) + cmd], "Шёпот"
    if _chance(rng, 0.3):
        return [_fn_gate(rng, cfg, _f(rng, 0.3, 0.7)) + cmd], "Шёпот"
    return [cmd], "Шёпот"


def _fn_recolor_cmd(rng, cfg, ctx):
    """Перекраска предмета item modify (существующее поведение как один из
    вариантов): нужен mod_ids; гейт — предикат измерения или наш
    random_chance (в worn — ОБЯЗАТЕЛЬНО гейчен)."""
    if not cfg["mod_ids"]:
        return None, None
    cmd = "item modify entity @s %s %s" % (
        rng.choice(["weapon.mainhand", "weapon.mainhand", "weapon.offhand"]),
        rng.choice(cfg["mod_ids"]))
    if ctx == "worn":
        return [_fn_gate(rng, cfg, _f(rng, 0.02, 0.06)) + cmd], "Переливы"
    if cfg["pred_ids"] and _chance(rng, 0.4):
        return ["execute if predicate %s run %s"
                % (rng.choice(cfg["pred_ids"]), cmd)], "Переливы"
    if _chance(rng, 0.5):
        return [_fn_gate(rng, cfg, _f(rng, 0.3, 0.7)) + cmd], "Переливы"
    return [cmd], "Переливы"


def _fn_xp_cmd(rng, cfg, budget):
    """Мелкая награда опытом: 1-3 орба {Value:1..3} (NBT 26.2: Value —
    int, байткод ExperienceOrb) либо xp add @s <=5 points. Редко — гейт
    0.05-0.2; только full/event (в worn = бесплатная ферма XP)."""
    gate = _fn_gate(rng, cfg, _f(rng, 0.05, 0.2))
    if _chance(rng, 0.5):
        n = min(rng.randint(1, 3), budget)
        return [_fn_gated(gate, "summon minecraft:experience_orb ~ ~1.2 ~ "
                         "{Value:%d}" % rng.randint(1, 3))
                for _ in range(n)], "Жатва"
    return [_fn_gated(gate, "xp add @s %d points" % rng.randint(1, 5))], \
        "Жатва"


def _fn_lightning_cmd(rng, cfg):
    """Молния — редкий тяжёлый тир: только full, гейт 0.04-0.12 (требование
    юзера: if predicate random_chance <=0.1..0.15), разряд 3-5 блоков
    вперёд по взгляду (владелец вне радиуса)."""
    gate = _fn_gate(rng, cfg, _f(rng, 0.04, 0.12))
    return [_fn_gated(gate, "execute at @s rotated ~ 0 run summon "
                      "minecraft:lightning_bolt ^ ^ ^%d" % rng.randint(3, 5))], \
        "Громовержец"


def _fn_echo_cmd(rng, cfg, ctx):
    """Эхо-звук: 2-3 playsound одного и того же звука с нарастающим pitch
    (0.5-0.9 с шагом 0.2-0.4 — эффект нарастания). В worn — плотный
    гейт (иначе звуковой спам каждый тик)."""
    snd = rng.choice(_FN_SOUNDS)
    n = 2 if ctx == "worn" else rng.randint(2, 3)
    p0, step, vol = _f(rng, 0.5, 0.9), _f(rng, 0.2, 0.4), _f(rng, 0.4, 1.0)
    lines = ["playsound %s master @s ~ ~ ~ %s %s"
             % (snd, vol, round(p0 + step * k, 3)) for k in range(n)]
    if ctx == "worn":
        gate = _fn_gate(rng, cfg, _f(rng, 0.005, 0.02))
        lines = [_fn_gated(gate, l) for l in lines]
    elif _chance(rng, 0.2):
        gate = _fn_gate(rng, cfg, _f(rng, 0.3, 0.7))
        lines = [_fn_gated(gate, l) for l in lines]
    return lines, "Резонанс"


def _fn_flash_cmd(rng, cfg, ctx):
    """Вспышка света: пучок end_rod/flash{color}/entity_effect{color}/
    electric_spark/glow/firework/explosion + короткий звук (все частицы
    и звуки существуют в 26.2 — flash это ColorParticleOption, сверено
    javap'ом по ParticleTypes)."""
    fp = rng.choice(_FN_FLASH_PARTICLES)
    if fp in ("minecraft:flash", "minecraft:entity_effect"):
        fp = "%s{color:%d}" % (fp, rng.choice(_FN_DUST_COLORS))
    lines = ["particle %s ~ ~1.2 ~ 0.4 0.5 0.4 %s %d force"
             % (fp, _f(rng, 0.05, 0.35), rng.randint(12, 30)),
             "playsound %s master @s ~ ~ ~ %s %s"
             % (rng.choice(_FN_FLASH_SOUNDS), _f(rng, 0.4, 1.2),
                _f(rng, 0.7, 1.6))]
    if ctx == "worn":
        gate = _fn_gate(rng, cfg, _f(rng, 0.02, 0.08))
        lines = [_fn_gated(gate, l) for l in lines]
    elif _chance(rng, 0.15):
        gate = _fn_gate(rng, cfg, _f(rng, 0.3, 0.7))
        lines = [_fn_gated(gate, l) for l in lines]
    return lines, "Вспышка"


def _fn_totem_cmd(rng, cfg, ctx):
    """Тотемный эффект: particle totem_of_undying + звук item.totem.use —
    только визуал (предмет-тотем не выдаётся, воскрешения не происходит)."""
    lines = ["particle minecraft:totem_of_undying ~ ~1 ~ 0.5 0.7 0.5 %s %d "
             "force" % (_f(rng, 0.1, 0.4), rng.randint(20, 45)),
             "playsound minecraft:item.totem.use master @s ~ ~ ~ %s %s"
             % (_f(rng, 0.5, 1.0), _f(rng, 0.9, 1.3))]
    if ctx == "worn":
        gate = _fn_gate(rng, cfg, _f(rng, 0.02, 0.08))
        lines = [_fn_gated(gate, l) for l in lines]
    elif _chance(rng, 0.2):
        gate = _fn_gate(rng, cfg, _f(rng, 0.3, 0.7))
        lines = [_fn_gated(gate, l) for l in lines]
    return lines, "Тотем"


def _fn_thunder_cmd(rng, cfg, ctx):
    """Грозовое эхо: только ЗВУК entity.lightning_bolt.thunder (саму молнию
    НЕ призываем — она поджигает/уронит), источник высоко над головой
    (positioned ~ ~8..24 ~ — звук «с неба»)."""
    line = ("execute positioned ~ ~%s ~ run playsound "
            "minecraft:entity.lightning_bolt.thunder master @s ~ ~ ~ %s %s"
            % (_f(rng, 8.0, 24.0), _f(rng, 0.8, 1.5), _f(rng, 0.5, 0.9)))
    if ctx == "worn":
        return [_fn_gated(_fn_gate(rng, cfg, _f(rng, 0.005, 0.02)), line)], \
            "Грохот"
    if _chance(rng, 0.3):
        return [_fn_gated(_fn_gate(rng, cfg, _f(rng, 0.3, 0.7)), line)], "Грохот"
    return [line], "Грохот"


def _fn_glow2_cmd(rng, cfg, ctx):
    """Жертвенное свечение: item modify поочерёдно в mainhand И offhand
    (обе руки «приносятся» зачарованию). Нужен mod_ids; гейты как у
    перекраски (в worn — ОБЯЗАТЕЛЬНО гейчен)."""
    if not cfg["mod_ids"]:
        return None, None
    lines = ["item modify entity @s weapon.%s %s"
             % (slot, rng.choice(cfg["mod_ids"]))
             for slot in ("mainhand", "offhand")]
    if ctx == "worn":
        gate = _fn_gate(rng, cfg, _f(rng, 0.02, 0.06))
        lines = [_fn_gated(gate, l) for l in lines]
    elif cfg["pred_ids"] and _chance(rng, 0.4):
        gate = "execute if predicate %s run " % rng.choice(cfg["pred_ids"])
        lines = [gate + l for l in lines]
    elif _chance(rng, 0.5):
        gate = _fn_gate(rng, cfg, _f(rng, 0.3, 0.7))
        lines = [_fn_gated(gate, l) for l in lines]
    return lines, "Жертва"


def _fn_auraring_cmd(rng, cfg, budget):
    """Кольцо дебафа: 2-3 волны разных радиусов (3-10) с разными
    эффектами вокруг владельца (type=!player исключает и владельца);
    2-5 с, усилитель 0."""
    n = min(rng.choices([2, 3], weights=[3, 2], k=1)[0], budget)
    effs = rng.sample(_FN_AURA_EFFECTS, n)
    radii = sorted(rng.sample([3, 4, 5, 6, 8, 10], n))
    lines = []
    for eff, rad in zip(effs, radii):
        sel = ("@e[distance=..%d,type=!player,type=!item,"
               "type=!experience_orb]" % rad)
        lines.append("execute at @s run effect give %s %s %d 0 true"
                     % (sel, eff, rng.randint(5, 15)))
    return lines, "Кольцо"


def _fn_duet_cmd(rng, cfg, ctx):
    """Самобафф-дуэт: два РАЗНЫХ эффекта сразу (короткие, 3-8 с — сила не
    копится). В worn запрещён (каждый тик обновлял бы таймеры)."""
    effs = rng.sample(_FN_SELF_EFFECTS, 2)
    lines = ["effect give @s %s %d %d true"
             % (e, rng.randint(3, 8), rng.randint(0, 1)) for e in effs]
    if _chance(rng, 0.4):
        gate = _fn_gate(rng, cfg, _f(rng, 0.25, 0.6))
        lines = [_fn_gated(gate, l) for l in lines]
    return lines, "Дуэт"


def _fn_harvest_cmd(rng, cfg, budget):
    """Жатва: 2-4 орба опыта {Value:1..3} с разбросом смещений + частица-
    фейерверк. Только full/event (в worn = бесплатная ферма XP),
    плотный гейт 0.05-0.2."""
    gate = _fn_gate(rng, cfg, _f(rng, 0.05, 0.2))
    n = min(rng.randint(2, 4), budget - 1) if budget > 1 else 1
    lines = [_fn_gated(gate, "summon minecraft:experience_orb ~%s ~1.2 ~%s "
                     "{Value:%d}"
                     % (_fn_num(_f(rng, -0.8, 0.8)),
                        _fn_num(_f(rng, -0.8, 0.8)), rng.randint(1, 3)))
             for _ in range(n)]
    lines.append(_fn_gated(
        gate, "particle %s ~ ~1.4 ~ 0.5 0.4 0.5 0.05 8"
        % rng.choice(_FN_HARVEST_PARTICLES)))
    return lines, "Жатва"


# ===========================================================================
# НОВЫЕ КАТЕГОРИИ (требование юзера: «функции зачарований — кратно
# расширить»): все — только разрешённые глаголы (particle/playsound/
# effect give/summon безопасные/title/tellraw/execute/xp add/item modify),
# worn-контекст — только дешёвые геометрии/звуки/фразы с гейтами
# ===========================================================================

def _fn_gate_lines(rng, cfg, ctx, lines, worn_lo=0.02, worn_hi=0.08,
                   full_p=0.15, full_lo=0.3, full_hi=0.7):
    """Гейтинг набора строк: worn — ВСЕГДА (вызов каждый тик), full/event —
    иногда; единая схема для новых категорий (как у particle/sound/echo)."""
    if ctx == "worn":
        gate = _fn_gate(rng, cfg, _f(rng, worn_lo, worn_hi))
        return [_fn_gated(gate, l) for l in lines]
    if _chance(rng, full_p):
        gate = _fn_gate(rng, cfg, _f(rng, full_lo, full_hi))
        return [_fn_gated(gate, l) for l in lines]
    return lines


def _fn_rain_cmd(rng, cfg, ctx, budget):
    """«Дождь» — частицы зоной СВЕРХУ игрока: 6-12 капель на нисходящих
    высотах 2.2-5.5, xz-разброс радиусом 0.6-3.0."""
    p, _wp = _fn_pick_particle(rng)
    n = max(3, min(rng.randint(6, 12), budget))
    rad, top = _f(rng, 0.6, 3.0), _f(rng, 3.0, 5.5)
    a0 = rng.uniform(0, 2.0 * math.pi)
    lines = []
    for k in range(n):
        t = k / max(1, n - 1)
        a = a0 + k * (2.0 * math.pi / 7.0)
        rk = rad * (0.55 + 0.45 * rng.random())
        lines.append(_fn_pt_at(
            p, _fn_num(rk * math.cos(a)), _fn_num(top * (1.0 - 0.55 * t)),
            _fn_num(rk * math.sin(a))))
    return _fn_gate_lines(rng, cfg, ctx, lines), "Ливень"


def _fn_vortex_cmd(rng, cfg, ctx, budget):
    """«Вихрь» — спираль 8-14 частиц по возрастающему радиусу 0.3-0.8 →
    1.6-2.6, высота ползёт вверх (шаг угла 35-65°, 1-2 витка)."""
    p, _wp = _fn_pick_particle(rng)
    n = max(4, min(rng.randint(8, 14), budget))
    r0, r1 = _f(rng, 0.3, 0.8), _f(rng, 1.6, 2.6)
    h0, dh = _f(rng, 0.1, 0.4), _f(rng, 0.12, 0.22)
    da = math.radians(rng.randint(35, 65))
    a0 = rng.uniform(0, 2.0 * math.pi)
    lines = []
    for k in range(n):
        t = k / max(1, n - 1)
        rk = r0 + (r1 - r0) * t
        a = a0 + da * k
        lines.append(_fn_pt_at(p, _fn_num(rk * math.cos(a)),
                               _fn_num(h0 + dh * k),
                               _fn_num(rk * math.sin(a))))
    return _fn_gate_lines(rng, cfg, ctx, lines), "Вихрь"


def _fn_dome_cmd(rng, cfg, ctx, budget):
    """«Купол» — полусфера над игроком: кольцо по экватору + малое кольцо
    выше + макушка (радиус 1.3-2.4)."""
    p, _wp = _fn_pick_particle(rng)
    rad = _f(rng, 1.3, 2.4)
    n1 = max(4, min(rng.randint(6, 8), budget))
    a0 = rng.uniform(0, 2.0 * math.pi)
    lines = [_fn_pt_at(p, _fn_num(rad * math.cos(a0 + 2.0 * math.pi * k / n1)),
                       _fn_num(rad * 0.35),
                       _fn_num(rad * math.sin(a0 + 2.0 * math.pi * k / n1)))
             for k in range(n1)]
    n2 = max(3, min(n1 - 2, budget - len(lines)))
    if n2 >= 3:
        rr, hh = rad * 0.6, rad * 0.72
        lines += [_fn_pt_at(p, _fn_num(rr * math.cos(a0 + 2.0 * math.pi * k / n2)),
                            _fn_num(hh),
                            _fn_num(rr * math.sin(a0 + 2.0 * math.pi * k / n2)))
                  for k in range(n2)]
    if len(lines) < budget:
        lines.append(_fn_pt_at(p, "0", _fn_num(rad * 1.02), "0"))
    return _fn_gate_lines(rng, cfg, ctx, lines), "Купол"


def _fn_chord_cmd(rng, cfg, ctx):
    """«Аккорд» — арпеджио: 3-5 звуков подряд с нарастающим pitch
    (шаг 0.15-0.35); один звук (чистое арпеджио) или 2-3 разных."""
    n = 3 if ctx == "worn" else rng.randint(3, 5)
    # один звук (чистое арпеджио) или 2-3 разных (перебор)
    snds = ([rng.choice(_FN_SOUNDS)] if _chance(rng, 0.4)
            else rng.sample(_FN_SOUNDS, min(rng.randint(2, 3), n)))
    p0, step, vol = _f(rng, 0.6, 1.0), _f(rng, 0.15, 0.35), _f(rng, 0.5, 1.0)
    lines = ["playsound %s master @s ~ ~ ~ %s %s"
             % (snds[0] if len(snds) == 1 else snds[k % len(snds)], vol,
                round(p0 + step * k, 3))
             for k in range(n)]
    return _fn_gate_lines(rng, cfg, ctx, lines,
                          worn_lo=0.005, worn_hi=0.02), "Аккорд"


def _fn_choir_cmd(rng, cfg, ctx):
    """«Хор» — один и тот же звук с нескольких сторон (positioned ~±3,
    3-4 источника вокруг игрока, громкость/тон общие — «хорал»)."""
    snd = rng.choice(_FN_SOUNDS)
    n = 2 if ctx == "worn" else rng.randint(3, 4)
    offs = [(-3.0, 1.5, 0.0), (3.0, 1.2, 0.0), (0.0, 2.0, -3.0),
            (0.0, 2.4, 3.0), (-2.2, 0.8, 2.2), (2.2, 1.0, -2.2)]
    pts = rng.sample(offs, n)
    vol, pitch = _f(rng, 0.4, 1.0), _f(rng, 0.7, 1.4)
    lines = ["execute positioned ~%s ~%s ~%s run playsound %s master @s "
             "~ ~ ~ %s %s"
             % (_fn_num(x + _f(rng, -0.3, 0.3)), _fn_num(y),
                _fn_num(z + _f(rng, -0.3, 0.3)), snd, vol, pitch)
             for (x, y, z) in pts]
    return _fn_gate_lines(rng, cfg, ctx, lines,
                          worn_lo=0.005, worn_hi=0.02), "Хор"


def _fn_gamma_cmd(rng, cfg, budget):
    """«Гамма» — связка 2-3 area_effect_cloud на РАЗНОЙ ВЫСОТЕ (ярусы
    0.4/1.4/2.4): облака маленькие (Radius 1.0-2.2), короткие, 1-2 эффекта.
    Не в worn (summon каждый тик = спам)."""
    n = min(rng.choices([2, 3], weights=[3, 2], k=1)[0], budget)
    lines = []
    for i in range(n):
        n_eff = 1 if _chance(rng, 0.7) else 2
        effs = rng.sample(_FN_AURA_EFFECTS, n_eff)
        custom = ",".join(
            '{id:"%s",amplifier:%d,duration:%d,ambient:1b,visible:0b}'
            % (e, rng.randint(0, 1), rng.randint(40, 90)) for e in effs)
        nbt = ("{Radius:%sf,Duration:%d,WaitTime:0,"
               "potion_contents:{custom_effects:[%s]%s}}"
               % (_f(rng, 1.0, 2.2), rng.randint(50, 150), custom,
                  (",custom_color:%d" % rng.choice(_FN_DUST_COLORS))
                  if _chance(rng, 0.3) else ""))
        lines.append("execute at @s run summon minecraft:area_effect_cloud "
                     "~%s ~%s ~%s %s"
                     % (_fn_num(_f(rng, -1.2, 1.2)),
                        _fn_num([0.4, 1.4, 2.4][i] + _f(rng, -0.2, 0.2)),
                        _fn_num(_f(rng, -1.2, 1.2)), nbt))
    return lines, "Ярус"


def _fn_fangarc_cmd(rng, cfg, budget):
    """«Веер клыков полукругом» — 5-9 клыков дугой 90-180° перед
    исполнителем (дистанция 2-4); старый веер — узкий ±45°, этот — размах.
    Не в worn (summon)."""
    n = max(3, min(rng.randint(5, 9), budget))
    span = rng.choice([90, 120, 150, 180])
    dist = rng.randint(2, 4)
    dirs = [(-span // 2 + span * k // max(1, n - 1)) for k in range(n)]
    lines = ["execute at @s rotated ~%d 0 run summon "
             "minecraft:evoker_fangs ^ ^ ^%d" % (d, dist) for d in dirs]
    return lines, "Полумесяц"


def _fn_fangwall_cmd(rng, cfg, budget):
    """«Стена клыков» — поперёк взгляда на ДИСТАНЦИИ 2.5-4.5 (rotated ~±90:
    поперечная ось совпадает со взглядом; 3-5 клыков через 1 блок).
    Не в worn (summon)."""
    rot = rng.choice([90, -90])
    ahead = rng.choice([2.5, 3.0, 3.5, 4.0, 4.5])
    half = 2 if budget >= 5 else 1
    lines = ["execute at @s rotated ~%d 0 run summon "
             "minecraft:evoker_fangs ^%s ^ ^%s"
             % (rot, _fn_num(ahead), _fn_num(k))
             for k in range(-half, half + 1)]
    return lines, "Заслон"


# блоки для «осколков» (BlockState в частице block; все есть в 26.2)
_FN_SHARD_BLOCKS = ["minecraft:stone", "minecraft:amethyst_block",
                    "minecraft:copper_block", "minecraft:glass",
                    "minecraft:packed_ice", "minecraft:glowstone",
                    "minecraft:obsidian", "minecraft:crying_obsidian",
                    "minecraft:quartz_block", "minecraft:calcite"]


def _fn_shards_cmd(rng, cfg, ctx, budget):
    """«Осколки» — 4-8 ЧАСТИЦ block{block_state:{Name:...}} (замена идеи
    summon falling_block — сущности не спамим); формат BlockParticleOption
    26.2: поле block_state с BlockState.CODEC — сверено javap'ом; типы
    block/block_marker/falling_dust — все BlockParticleOption."""
    ptype = rng.choice(["minecraft:block", "minecraft:block",
                        "minecraft:block_marker", "minecraft:falling_dust"])
    p = "%s{block_state:{Name:\"%s\"}}" % (ptype, rng.choice(_FN_SHARD_BLOCKS))
    n = max(3, min(rng.randint(4, 8), budget))
    lines = [_fn_pt_at(p, _fn_num(_f(rng, -1.6, 1.6)),
                       _fn_num(_f(rng, 0.2, 2.0)),
                       _fn_num(_f(rng, -1.6, 1.6))) for _ in range(n)]
    return _fn_gate_lines(rng, cfg, ctx, lines), "Осколки"


def _fn_glow_cmd(rng, cfg, ctx):
    """«Свечение» — effect give @s glowing 10-30 с, частицы скрыты;
    гейт ОБЯЗАТЕЛЕН (0.15-0.5). Не в worn (там effect give @s запрещён
    инвариантом — каждый тик = перманентное свечение)."""
    cmd = "effect give @s minecraft:glowing %d 0 true" % rng.randint(10, 30)
    gate = _fn_gate(rng, cfg, _f(rng, 0.15, 0.5))
    return [_fn_gated(gate, cmd)], "Сияние"


def _fn_secondwind_cmd(rng, cfg, ctx):
    """«Второе дыхание» — 2 самобаффа подряд с РАЗНЫМИ длительностями:
    короткий всплеск (4-10 с) + долгое послевкусие (+6-18 с, усилитель 1).
    Не в worn (каждый тик обновлял бы таймеры)."""
    effs = rng.sample(_FN_SELF_EFFECTS, 2)
    short = rng.randint(4, 10)
    lines = ["effect give @s %s %d 0 true" % (effs[0], short),
             "effect give @s %s %d 1 true" % (effs[1],
                                              short + rng.randint(6, 18))]
    if _chance(rng, 0.45):
        gate = _fn_gate(rng, cfg, _f(rng, 0.2, 0.55))
        lines = [_fn_gated(gate, l) for l in lines]
    return lines, "Второе Дыхание"


def _fn_whisper_cmd(rng, cfg, ctx):
    """«Пронзающий шёпот» — tellraw цветной флейвор в ЧАТ (не actionbar;
    редкая категория — вес мал). В worn — плотный гейт."""
    msg = {"text": rng.choice(_FN_FLAVOR)}
    if _chance(rng, 0.7):
        msg["color"] = rng.choice(["dark_gray", "gray", "dark_purple",
                                   "dark_aqua", "blue", "dark_blue"])
    if _chance(rng, 0.6):
        msg["italic"] = True
    cmd = "tellraw @s %s" % json.dumps(msg, ensure_ascii=False,
                                       separators=(",", ":"))
    if ctx == "worn":
        return [_fn_gate(rng, cfg, _f(rng, 0.01, 0.04)) + cmd], "Весть"
    if _chance(rng, 0.5):
        return [_fn_gate(rng, cfg, _f(rng, 0.3, 0.6)) + cmd], "Весть"
    return [cmd], "Весть"


def _fn_march_cmd(rng, cfg, ctx):
    """«Марш» — последовательность 3-5 звуков с НАРАСТАЮЩЕЙ громкостью
    0.3 → 1.5 (шаг 0.25-0.4), тон общий."""
    snd = rng.choice(_FN_SOUNDS)
    n = 3 if ctx == "worn" else rng.randint(3, 5)
    v0, vstep, pitch = _f(rng, 0.3, 0.45), _f(rng, 0.25, 0.4), _f(rng, 0.8, 1.3)
    lines = ["playsound %s master @s ~ ~ ~ %s %s"
             % (snd, round(min(1.5, v0 + vstep * k), 3), pitch)
             for k in range(n)]
    return _fn_gate_lines(rng, cfg, ctx, lines, full_p=0.25,
                          worn_lo=0.005, worn_hi=0.02), "Марш"


def _fn_awakening_cmd(rng, cfg, ctx):
    """«Пробуждение» — комбо: вспышка света + громовое эхо (только звук
    entity.lightning_bolt.thunder с высоты, без молнии) + залп частиц.
    Дёшево (particle+playsound) — доступно и в worn с гейтом."""
    fp = rng.choice(_FN_FLASH_PARTICLES)
    if fp in ("minecraft:flash", "minecraft:entity_effect"):
        fp = "%s{color:%d}" % (fp, rng.choice(_FN_DUST_COLORS))
    lines = [
        "particle %s ~ ~1.2 ~ 0.4 0.5 0.4 %s %d force"
        % (fp, _f(rng, 0.05, 0.3), rng.randint(12, 25)),
        "execute positioned ~ ~%s ~ run playsound "
        "minecraft:entity.lightning_bolt.thunder master @s ~ ~ ~ %s %s"
        % (_f(rng, 6.0, 16.0), _f(rng, 0.6, 1.2), _f(rng, 0.5, 0.8)),
        "particle %s ~ ~1.6 ~ 0.6 0.3 0.6 0.06 %d force"
        % (_fn_pick_particle(rng)[0], rng.randint(10, 20)),
    ]
    return _fn_gate_lines(rng, cfg, ctx, lines, worn_lo=0.01,
                          worn_hi=0.05), "Пробуждение"


_FN_OATH_TITLES = ["Клятва скреплена", "Союз заключён", "Слово сказано",
                   "Обет произнесён", "Договор в силе", "Узы затянуты"]


def _fn_oath_cmd(rng, cfg, ctx):
    """«Клятва» — item modify ОБЕИХ рук (один модификатор — обет единый)
    + title-заголовок. Нужен mod_ids; в worn — гейт обязательный
    (команды дешёвые: item + title)."""
    if not cfg["mod_ids"]:
        return None, None
    mod = rng.choice(cfg["mod_ids"])
    title = {"text": rng.choice(_FN_OATH_TITLES)}
    if _chance(rng, 0.7):
        title["color"] = rng.choice(["gold", "aqua", "light_purple",
                                     "green"])
    lines = ["item modify entity @s weapon.mainhand %s" % mod,
             "item modify entity @s weapon.offhand %s" % mod,
             "title @s title %s" % json.dumps(title, ensure_ascii=False,
                                              separators=(",", ":"))]
    if ctx == "worn":
        gate = _fn_gate(rng, cfg, _f(rng, 0.02, 0.06))
        lines = [_fn_gated(gate, l) for l in lines]
    elif cfg["pred_ids"] and _chance(rng, 0.4):
        gate = "execute if predicate %s run " % rng.choice(cfg["pred_ids"])
        lines = [gate + l for l in lines]
    elif _chance(rng, 0.5):
        gate = _fn_gate(rng, cfg, _f(rng, 0.3, 0.7))
        lines = [_fn_gated(gate, l) for l in lines]
    return lines, "Клятва"


def _fn_xprain_cmd(rng, cfg, budget):
    """«Дождь опыта» — 4-8 орбов опыта россыпью вокруг (±2 по xz,
    высоты 0.5-2.5); только full/event + гейт 0.05-0.2 (в worn = ферма)."""
    gate = _fn_gate(rng, cfg, _f(rng, 0.05, 0.2))
    n = max(3, min(rng.randint(4, 8), budget))
    lines = [_fn_gated(gate, "summon minecraft:experience_orb ~%s ~%s ~%s "
                     "{Value:%d}"
                     % (_fn_num(_f(rng, -2.0, 2.0)),
                        _fn_num(_f(rng, 0.5, 2.5)),
                        _fn_num(_f(rng, -2.0, 2.0)), rng.randint(1, 3)))
             for _ in range(n)]
    return lines, "Щедрость"


def _fn_farewell_cmd(rng, cfg):
    """«Прощальный салют» — фейерверк с fade_colors (обязательны — «угасание»)
    + прощальный залп частиц; LifeTime короткий (8-20). Не в worn (summon)."""
    shape = rng.choice(_FN_FW_SHAPES)
    colors = [rng.choice(_FN_DUST_COLORS) for _ in range(rng.randint(1, 3))]
    fades = [rng.choice(_FN_DUST_COLORS) for _ in range(rng.randint(1, 3))]
    expl = ('{shape:"%s",colors:[%s],fade_colors:[%s]%s%s}' % (
        shape, ",".join(str(c) for c in colors),
        ",".join(str(c) for c in fades),
        ",has_trail:1b" if _chance(rng, 0.5) else "",
        ",has_twinkle:1b" if _chance(rng, 0.4) else ""))
    item = ('{id:"minecraft:firework_rocket",count:1,components:'
            '{"minecraft:fireworks":{flight_duration:1,explosions:[%s]}}}'
            % expl)
    lines = ["execute at @s rotated ~ 0 run summon minecraft:firework_rocket "
             "^ ^ ^%s {LifeTime:%d,FireworksItem:%s}"
             % (_f(rng, 3.5, 5.0), rng.randint(8, 20), item),
             "particle %s ~ ~2 ~ 0.8 0.4 0.8 0.05 %d force"
             % (_fn_pick_particle(rng)[0], rng.randint(8, 16))]
    if _chance(rng, 0.3):
        lines.append("playsound minecraft:entity.firework_rocket.launch "
                     "master @s ~ ~ ~ %s %s" % (_f(rng, 0.5, 1.0),
                                                 _f(rng, 0.8, 1.4)))
    return lines, "Финал"


def _fn_rings_cmd(rng, cfg, ctx, budget):
    """«Многослойные кольца» — 2-3 концентрических кольца (радиусы шагом
    ×0.7, каждое чуть выше), 6-8 точек на кольцо."""
    p, _wp = _fn_pick_particle(rng)
    n_layers = rng.choices([2, 3], weights=[3, 2], k=1)[0]
    r0, h = _f(rng, 0.7, 1.1), _f(rng, 0.8, 1.2)
    a0 = rng.uniform(0, 2.0 * math.pi)
    lines = []
    for i in range(n_layers):
        rad = r0 * (1.0 + 0.7 * i)
        n = max(4, min(rng.randint(6, 8), budget - len(lines)))
        lines += [_fn_pt_at(p, _fn_num(rad * math.cos(a0 + 2.0 * math.pi * k / n)),
                            _fn_num(h + 0.15 * i),
                            _fn_num(rad * math.sin(a0 + 2.0 * math.pi * k / n)))
                  for k in range(n)]
        if len(lines) >= budget:
            break
    return _fn_gate_lines(rng, cfg, ctx, lines[:budget]), "Венец"


def _fn_crosses_cmd(rng, cfg, ctx, budget):
    """«Кресты» — 1-3 креста частиц (центр + 4 луча, плечо 0.25-0.5) в
    случайных точках вокруг; в маленький бюджет — урезанный крест."""
    p, _wp = _fn_pick_particle(rng)
    n_cross = 1 if budget < 6 else rng.randint(2, 3)
    arm = _f(rng, 0.25, 0.5)
    lines = []
    for _ in range(n_cross):
        cx, cy, cz = (_f(rng, -1.5, 1.5), _f(rng, 0.8, 2.0),
                      _f(rng, -1.5, 1.5))
        beam = [(arm, 0.0), (0.0, 0.0), (-arm, 0.0),
                (0.0, arm), (0.0, -arm)]
        for dx, dy in beam:
            if len(lines) >= budget:
                break
            lines.append(_fn_pt_at(p, _fn_num(cx + dx), _fn_num(cy + dy),
                                   _fn_num(cz)))
    return _fn_gate_lines(rng, cfg, ctx, lines), "Крест"


def _fn_stars_cmd(rng, cfg, ctx, budget):
    """«Звёзды» — 1-2 звезды: 5-8 лучей из центра (радиус 0.9-2.0, лёгкий
    вертикальный разброс) + точка-ядро."""
    p, _wp = _fn_pick_particle(rng)
    n_star = 1 if budget < 8 else rng.randint(1, 2)
    lines = []
    for i in range(n_star):
        cx, cy, cz = (_f(rng, -1.2, 1.2), _f(rng, 1.0, 2.2), _f(rng, -1.2, 1.2))
        rays = max(4, min(rng.randint(5, 8), budget - len(lines) - 1))
        rr = _f(rng, 0.9, 2.0)
        a0 = rng.uniform(0, 2.0 * math.pi)
        lines += [_fn_pt_at(p, _fn_num(cx + rr * math.cos(a0 + 2.0 * math.pi * k / rays)),
                            _fn_num(cy + 0.3 * math.sin(a0 + 2.0 * math.pi * k / rays)),
                            _fn_num(cz + rr * math.sin(a0 + 2.0 * math.pi * k / rays)))
                  for k in range(rays)]
        if len(lines) < budget:
            lines.append(_fn_pt_at(p, _fn_num(cx), _fn_num(cy), _fn_num(cz)))
        if len(lines) >= budget:
            break
    return _fn_gate_lines(rng, cfg, ctx, lines[:budget]), "Звезда"


def _fn_downspiral_cmd(rng, cfg, ctx, budget):
    """«Спираль вниз» — воронка: 6-10 частиц, радиус СЖИМАЕТСЯ 1.8-2.6 →
    0.3-0.8, высота падает 2.0-2.6 → ~0.5 (шаг угла 40-70°)."""
    p, _wp = _fn_pick_particle(rng)
    n = max(4, min(rng.randint(6, 10), budget))
    r0, r1 = _f(rng, 1.8, 2.6), _f(rng, 0.3, 0.8)
    h0, dh = _f(rng, 2.0, 2.6), -_f(rng, 0.16, 0.24)
    da = math.radians(rng.randint(40, 70))
    a0 = rng.uniform(0, 2.0 * math.pi)
    lines = []
    for k in range(n):
        t = k / max(1, n - 1)
        rk = r0 + (r1 - r0) * t
        a = a0 + da * k
        lines.append(_fn_pt_at(p, _fn_num(rk * math.cos(a)),
                               _fn_num(h0 + dh * k),
                               _fn_num(rk * math.sin(a))))
    return _fn_gate_lines(rng, cfg, ctx, lines), "Воронка"


def _gen_ench_function(rng, eid, ctx, mod_ids=None, pred_ids=None, gates=None,
                       report=None):
    """Текст mcfunction для run_function-эффекта зачарования.

    Контракт: id функции = id зачарования; вызывается при срабатывании
    эффекта; @s = affected-сущность (для post_attack мы маршрутизируем
    affected=enchanted — см. _build_post_attack). Возвращает
    (текст, слово_профиля): слово доминантной категории идёт в название
    зачарования («Клык», «Громовержец», «Скорость»...). gates пополняется
    random_chance-предикатами (id <ench>_p<N>). report — если передан
    set, в него добавляются ключи ИСПОЛЬЗОВАННЫХ категорий (для
    самотеста разнообразия; на генерацию не влияет)."""
    ns = eid.split(":", 1)[0]
    fname = eid.split(":", 1)[1]
    if gates is None:
        gates = {}
    cfg = {"ns": ns, "fname": fname, "gates": gates,
           "mod_ids": list(mod_ids or []), "pred_ids": list(pred_ids or []),
           "gi": [0]}
    # worn: только дешёвые категории, всё гейчено, бюджет 3 строки;
    # full/event: 1-10 команд (геометрия до 10 точек), бюджет 10 строк
    budget = 3 if ctx == "worn" else 10
    n_cats = rng.choices(
        [1, 2, 3, 4, 5],
        weights=([34, 44, 22, 0, 0] if ctx == "worn"
                 else [22, 30, 24, 14, 10]), k=1)[0]
    wmap = {c: (wf if ctx == "full" else we if ctx == "event" else ww)
            for c, wf, we, ww in _FN_CAT_W}
    cats = [c for c, _wf, _we, _ww in _FN_CAT_W
            if wmap[c] > 0
            and (c not in ("recolor", "glow2", "oath") or cfg["mod_ids"])]
    used, lines, words = set(), [], []
    while len(used) < n_cats and budget > 0 and cats:
        avail = [c for c in cats if c not in used]
        if not avail:
            break
        cat = rng.choices(avail, weights=[wmap[c] for c in avail], k=1)[0]
        used.add(cat)
        if cat == "particle":
            got, w = _fn_particle_cmd(rng, cfg, ctx, budget)
        elif cat == "sound":
            got, w = _fn_sound_cmd(rng, cfg, ctx)
        elif cat == "fangs":
            got, w = _fn_fangs_cmd(rng, cfg, budget)
        elif cat == "cloud":
            got, w = _fn_cloud_cmd(rng, cfg, budget)
        elif cat == "firework":
            got, w = _fn_firework_cmd(rng, cfg)
        elif cat == "selfbuff":
            got, w = _fn_selfbuff_cmd(rng, cfg, ctx)
        elif cat == "aura":
            got, w = _fn_aura_cmd(rng, cfg)
        elif cat == "flavor":
            got, w = _fn_flavor_cmd(rng, cfg, ctx)
        elif cat == "recolor":
            got, w = _fn_recolor_cmd(rng, cfg, ctx)
        elif cat == "xp":
            got, w = _fn_xp_cmd(rng, cfg, budget)
        elif cat == "lightning":
            got, w = _fn_lightning_cmd(rng, cfg)
        elif cat == "echo":
            got, w = _fn_echo_cmd(rng, cfg, ctx)
        elif cat == "flash":
            got, w = _fn_flash_cmd(rng, cfg, ctx)
        elif cat == "totem":
            got, w = _fn_totem_cmd(rng, cfg, ctx)
        elif cat == "thunder":
            got, w = _fn_thunder_cmd(rng, cfg, ctx)
        elif cat == "glow2":
            got, w = _fn_glow2_cmd(rng, cfg, ctx)
        elif cat == "fw2":
            got, w = _fn_fw2_cmd(rng, cfg)
        elif cat == "auraring":
            got, w = _fn_auraring_cmd(rng, cfg, budget)
        elif cat == "duet":
            got, w = _fn_duet_cmd(rng, cfg, ctx)
        elif cat == "harvest":
            got, w = _fn_harvest_cmd(rng, cfg, budget)
        elif cat == "rain":
            got, w = _fn_rain_cmd(rng, cfg, ctx, budget)
        elif cat == "vortex":
            got, w = _fn_vortex_cmd(rng, cfg, ctx, budget)
        elif cat == "dome":
            got, w = _fn_dome_cmd(rng, cfg, ctx, budget)
        elif cat == "chord":
            got, w = _fn_chord_cmd(rng, cfg, ctx)
        elif cat == "choir":
            got, w = _fn_choir_cmd(rng, cfg, ctx)
        elif cat == "gamma":
            got, w = _fn_gamma_cmd(rng, cfg, budget)
        elif cat == "fangarc":
            got, w = _fn_fangarc_cmd(rng, cfg, budget)
        elif cat == "fangwall":
            got, w = _fn_fangwall_cmd(rng, cfg, budget)
        elif cat == "shards":
            got, w = _fn_shards_cmd(rng, cfg, ctx, budget)
        elif cat == "glow":
            got, w = _fn_glow_cmd(rng, cfg, ctx)
        elif cat == "secondwind":
            got, w = _fn_secondwind_cmd(rng, cfg, ctx)
        elif cat == "whisper":
            got, w = _fn_whisper_cmd(rng, cfg, ctx)
        elif cat == "march":
            got, w = _fn_march_cmd(rng, cfg, ctx)
        elif cat == "awakening":
            got, w = _fn_awakening_cmd(rng, cfg, ctx)
        elif cat == "oath":
            got, w = _fn_oath_cmd(rng, cfg, ctx)
        elif cat == "xprain":
            got, w = _fn_xprain_cmd(rng, cfg, budget)
        elif cat == "farewell":
            got, w = _fn_farewell_cmd(rng, cfg)
        elif cat == "rings":
            got, w = _fn_rings_cmd(rng, cfg, ctx, budget)
        elif cat == "crosses":
            got, w = _fn_crosses_cmd(rng, cfg, ctx, budget)
        elif cat == "stars":
            got, w = _fn_stars_cmd(rng, cfg, ctx, budget)
        else:  # downspiral
            got, w = _fn_downspiral_cmd(rng, cfg, ctx, budget)
        if got:
            got = got[:budget]
            lines.extend(got)
            budget -= len(got)
            words.append((_FN_CAT_PRIO[cat], w))
            if report is not None:
                report.add(cat)
    if not lines:  # крайний случай — дежурная вспышка
        lines = ["particle minecraft:enchanted_hit ~ ~1 ~ 0.4 0.6 0.4 0 6"]
        words.append((3, "Блеск"))
    head = "# %s — вызывается run_function-эффектом зачарования (%s)\n" % (
        eid, _FN_CTX_DESC[ctx])
    # слово профиля = доминантная (самая зрелищная) категория функции
    word = max(words, key=lambda p: p[0])[1]
    return head + "\n".join(lines) + "\n", word


# ---------------------------------------------------------------------------
# Публичная функция
# ---------------------------------------------------------------------------


# ванильные зачарования (data/minecraft/enchantment/, 42 шт. из jar) —
# иногда попадают в exclusive_set («не сочетается с Остротой»)
_VANILLA_ENCHS = [
    "minecraft:sharpness", "minecraft:smite", "minecraft:bane_of_arthropods",
    "minecraft:knockback", "minecraft:fire_aspect", "minecraft:looting",
    "minecraft:sweeping_edge", "minecraft:efficiency", "minecraft:silk_touch",
    "minecraft:fortune", "minecraft:power", "minecraft:punch", "minecraft:flame",
    "minecraft:infinity", "minecraft:protection", "minecraft:fire_protection",
    "minecraft:blast_protection", "minecraft:projectile_protection",
    "minecraft:thorns", "minecraft:respiration", "minecraft:aqua_affinity",
    "minecraft:depth_strider", "minecraft:frost_walker", "minecraft:soul_speed",
    "minecraft:swift_sneak", "minecraft:feather_falling", "minecraft:mending",
    "minecraft:unbreaking", "minecraft:density", "minecraft:breach",
    "minecraft:wind_burst", "minecraft:lunge", "minecraft:multishot",
    "minecraft:quick_charge", "minecraft:piercing", "minecraft:impaling",
    "minecraft:riptide", "minecraft:loyalty", "minecraft:channeling",
    "minecraft:luck_of_the_sea", "minecraft:lure"]


def _rand_enchantment(rng, ns, eid, used_names, mod_ids=None, pred_ids=None,
                      gates=None):
    profile = _pick_w(rng, list(zip(_PROFILE_KEYS, _PROFILE_W)))
    # профиль текущего зачарования — для самотеста юзабельности компонент
    # (в JSON зачарования его не пишем: сервер отверг бы лишнее поле)
    _LAST_ENCH_PROFILE[0] = profile
    if profile == "absurd":
        supported = _absurd_items(rng)
        slot_pairs = [(s, 1) for s in rng.sample(
            _SLOT_GROUPS, rng.randint(1, 3))]
        comp_keys, comp_w = _absurd_comps(rng)
    else:
        for key, _w, items, slots, comps in _PROFILES:
            if key == profile:
                break
        supported = _pick_w(rng, items)
        slot_pairs = slots
        comp_keys = [c for c, _w in comps + _UNIVERSAL_COMPS]
        comp_w = [w for _c, w in comps + _UNIVERSAL_COMPS]

    # слоты: из профиля, иногда несколько; редко пустой список (проверка края)
    if profile == "absurd":
        slot_names = [s for s, _w in slot_pairs]
    else:
        first = _pick_w(rng, slot_pairs)
        slot_names = [first]
        if _chance(rng, 0.25):
            extra = rng.choice(_SLOT_GROUPS)
            if extra not in slot_names:
                slot_names.append(extra)
    if _chance(rng, 0.03):
        slot_names = []  # крайний случай: пустые slots (валидность — сервер)

    # динамический фильтр юзабельности: компоненты, которые на выбранных
    # предметах/слотах не срабатывают, не попадают в кандидаты (таблица
    # правил _COMP_ITEM_RULES; профиль absurd — исключение, там всё можно).
    # Пустые slots — дежурный краевой случай: слот-требования пропускаются
    # (см. _comp_usable), но проверка видов предметов остаётся
    if profile != "absurd":
        pairs = [(c, w) for c, w in zip(comp_keys, comp_w)
                 if _comp_usable(c, supported, slot_names)]
        if pairs:
            comp_keys = [c for c, _w in pairs]
            comp_w = [w for _c, w in pairs]

    # 1-5 разных компонент (разнообразнее: раньше максимум был 4)
    n_eff = rng.choices([1, 2, 3, 4, 5],
                         weights=[18, 30, 26, 18, 8], k=1)[0]
    n_eff = min(n_eff, len(comp_keys))
    chosen = set()
    for _ in range(n_eff):
        chosen.add(rng.choices(comp_keys, weights=comp_w, k=1)[0])
    # rng вызовы должны быть стабильны: добираем ровно n_eff попытками
    effects = {}
    for comp in sorted(chosen):
        # func_id = id зачарования: run_function ссылается на функцию с тем
        # же id, attributes добавляют суффиксы _a<N>/_loc; профиль — для
        # тематических пулов атрибутов и прочих правил
        effects["minecraft:" + comp] = _COMPONENTS[comp](rng, eid, profile)

    # mcfunction для run_function-эффектов генерируем ДО имени: доминантная
    # фича функции даёт слову названия («Клык», «Громовержец»...) —
    # функция СНАЧАЛА, потом _effect_name(run_function_word=...)
    fn_text, rf_word = None, None
    rf_ctx = _ench_rf_context(effects)
    if rf_ctx is not None:
        fn_text, rf_word = _gen_ench_function(
            rng, eid, rf_ctx, mod_ids=mod_ids, pred_ids=pred_ids, gates=gates)

    # имя описания (уникальное в пределах измерения) — по РЕАЛЬНЫМ
    # эффектам: «Громовое Пробитие», «Яд и Отброс», «Проклятие Хрупкости»
    for _ in range(8):
        nm = _effect_name(rng, effects, profile, rf_word)
        if nm not in used_names:
            break
    used_names.add(nm)

    # max_level 1..10 с падающей вероятностью
    max_level = rng.choices(range(1, 11),
                            weights=[28, 20, 13, 9, 6, 5, 4, 3, 2, 1],
                            k=1)[0]
    min_base = rng.randint(1, 25)
    min_per = rng.randint(1, 15)
    max_base = min_base + rng.randint(0, 30)
    max_per = min_per + rng.randint(0, 10)
    ench = {
        "description": {"text": nm, "color": rng.choice(_COLORS)},
        "supported_items": supported,
        "weight": int(round(math.exp(rng.uniform(0, math.log(40))))),
        "max_level": max_level,
        "min_cost": {"base": min_base, "per_level_above_first": min_per},
        "max_cost": {"base": max_base, "per_level_above_first": max_per},
        "anvil_cost": rng.choices([0, 1, 2, 3, 4, 5, 6, 8, 10, 12],
                                  weights=[4, 6, 6, 5, 4, 3, 2, 2, 1, 1],
                                  k=1)[0],
        "slots": slot_names,
    }
    # primary_items — иногда (подмножество supported для веса в столе)
    if _chance(rng, 0.4):
        if isinstance(supported, str) and supported.startswith("#minecraft:"):
            ench["primary_items"] = supported
        elif isinstance(supported, list) and len(supported) > 1:
            ench["primary_items"] = rng.sample(
                supported, rng.randint(1, len(supported) - 1))
    if effects:
        ench["effects"] = effects
    return ench, fn_text


def rand_enchantments(rng, ns, name, count=None, mod_ids=None, pred_ids=None):
    """Случайные зачарования + enchantment_provider для одного измерения.

    Возвращает {"enchantments": {id: json}, "enchantment_providers": {id: json},
    "functions": {fname: текст mcfunction}, "gate_predicates": {id: json}},
    id вида "<ns>:<name>_enchN" и "<ns>:<name>_provN"; fname — часть id
    зачарования после ':' (файл function/<fname>.mcfunction). На диск
    ничего не пишет.

    run_function-эффекты ссылаются на функцию с id зачарования
    ("<ns>:<name>_enchN") — её текст генерируется здесь же (см.
    _gen_ench_function) и кладётся в "functions"; гейт-предикаты команд —
    в "gate_predicates" (основной скрипт обязан записать их в predicate/,
    иначе команды с 'execute if predicate' молча не сработают).
    mod_ids/pred_ids — id item_modifier'ов/predicates измерения: без
    mod_ids категория перекраски (item modify) недоступна."""
    if count is None:
        # в среднем ~4-6, редкие выбросы до ~30 (heavy_count)
        count = _heavy_count(rng, 5.0, 15, 30, 0.08)
    count = max(1, int(count))

    used_names = set()
    enchantments = {}
    functions = {}
    gates = {}
    ench_ids = []
    profiles = {}
    for i in range(count):
        eid = "%s:%s_ench%d" % (ns, name, i)
        ench, fn_text = _rand_enchantment(
            rng, ns, eid, used_names, mod_ids=mod_ids, pred_ids=pred_ids,
            gates=gates)
        enchantments[eid] = ench
        profiles[eid] = _LAST_ENCH_PROFILE[0]
        if fn_text is not None:
            functions[eid.split(":", 1)[1]] = fn_text
        ench_ids.append(eid)

    # exclusive_set: иногда 2-3 взаимоисключающих зачарования одного профиля
    by_items = {}
    for eid in ench_ids:
        by_items.setdefault(
            json.dumps(enchantments[eid]["supported_items"],
                       sort_keys=True), []).append(eid)
    for _ in range(2):
        if _chance(rng, 0.45):
            groups = [g for g in by_items.values() if len(g) >= 2]
            if not groups:
                break
            group = rng.choice(groups)
            if len(group) >= 3 and _chance(rng, 0.5):
                group = rng.sample(group, 3)
            else:
                group = rng.sample(group, 2)
            for eid in group:
                others = [e for e in group if e != eid]
                if _chance(rng, 0.25):
                    # иногда исключаем ванильное зачарование вместо соседа
                    n_v = rng.randint(1, 2)
                    excl = rng.sample(_VANILLA_ENCHS, n_v)
                else:
                    excl = (others[0] if len(others) == 1 else others)
                enchantments[eid]["exclusive_set"] = (
                    excl[0] if len(excl) == 1 else excl)

    # enchantment_provider: несколько случайных подмножеств
    providers = {}
    n_prov = rng.choices([2, 3, 4, 5], weights=[4, 3, 2, 1], k=1)[0]
    n_prov = min(n_prov, max(1, len(ench_ids)))
    for i in range(n_prov):
        pid = "%s:%s_prov%d" % (ns, name, i)
        k = rng.randint(1, min(6, len(ench_ids)))
        subset = rng.sample(ench_ids, k)
        ptype = rng.choices(["single", "by_cost", "by_cost_with_difficulty"],
                            weights=[4, 3, 3], k=1)[0]
        if ptype == "single":
            eid = rng.choice(subset)
            lvl_max = enchantments[eid]["max_level"]
            providers[pid] = {
                "type": "minecraft:single", "enchantment": eid,
                "level": (rng.randint(1, min(3, lvl_max)) if _chance(rng, 0.5)
                          else {"type": "minecraft:uniform", "min_inclusive": 1,
                                "max_inclusive": max(1, lvl_max)})}
        elif ptype == "by_cost":
            providers[pid] = {
                "type": "minecraft:by_cost", "enchantments": subset,
                "cost": ({"type": "minecraft:uniform",
                          "min_inclusive": rng.randint(1, 10),
                          "max_inclusive": rng.randint(15, 40)})}
        else:
            providers[pid] = {
                "type": "minecraft:by_cost_with_difficulty",
                "enchantments": subset,
                "max_cost_span": rng.randint(5, 25),
                "min_cost": rng.randint(1, 15)}
    # кэш для gen_loot (см. LAST_ENCHANTMENTS) — до возврата
    global LAST_ENCHANTMENTS, LAST_PROFILES
    LAST_ENCHANTMENTS = enchantments
    LAST_PROFILES = profiles
    return {"enchantments": enchantments,
            "enchantment_providers": providers,
            "functions": functions,
            "gate_predicates": gates}


# последний результат rand_enchantments: {id зачарования: json}. Основной
# скрипт (generate_dimension.py) передаёт в gen_loot только id
# (set_custom_enchants), а полный JSON зачарований живёт здесь — gen_loot
# читает его ленивым импортом и сам строит сведения (имя/описание/
# пассивность) для lore-подсказок и фикса «предмет только с визуалом».
# Зачарования следующего измерения просто затирают прошлые (связка идёт
# по id из set_custom_enchants, так что устаревшие записи не мешают).
LAST_ENCHANTMENTS = {}

# профиль последнего сгенерированного зачарования (для самотеста
# юзабельности компонент — absurd exempt; JSON зачарования профиль не
# хранит, сервер отверг бы лишнее поле)
_LAST_ENCH_PROFILE = [None]

# {id зачарования: профиль} последнего rand_enchantments (side-канал для
# самотеста, как LAST_ENCHANTMENTS; на диск не пишется)
LAST_PROFILES = {}


# ---------------------------------------------------------------------------
# Пассивные зачарования и краткие описания (связка с gen_loot)
# ---------------------------------------------------------------------------

# компоненты эффектов, работающие ПРИ НОШЕНИИ/УДЕРЖАНИИ предмета без
# боевых событий: attributes (постоянные модификаторы), tick (каждый тик),
# location_changed (при движении, как frost_walker), damage_immunity
# (когда по вам бьют), prevent_equipment_drop / prevent_armor_change
# (просто носятся) — их ставят предметам «только с визуалом» в gen_loot
PASSIVE_EFFECT_COMPONENTS = ("minecraft:attributes", "minecraft:tick",
                              "minecraft:location_changed",
                              "minecraft:damage_immunity",
                              "minecraft:prevent_equipment_drop",
                              "minecraft:prevent_armor_change")


def passive_enchants(enchantments):
    """Id зачарований с ПАССИВНЫМ действием (см. PASSIVE_EFFECT_
    COMPONENTS) — работают при ношении/удержании, без событий. Аргумент —
    карта {id: json зачарования} (поле "enchantments" результата
    rand_enchantments); возвращает ОТСОРТИРОВАННЫЙ список id."""
    out = []
    for eid, ejson in (enchantments or {}).items():
        eff = ejson.get("effects") if isinstance(ejson, dict) else None
        if isinstance(eff, dict) and any(c in eff
                                         for c in PASSIVE_EFFECT_COMPONENTS):
            out.append(eid)
    return sorted(out)


# «числовые» компоненты -> фраза действия (знак значения — _SUMMARY_FLIP)
_SUMMARY_VE = {
    "damage": "усиливает урон",
    "damage_protection": "снижает получаемый урон",
    "smash_damage_per_fallen_block": "бьёт сильнее в падении",
    "knockback": "отбрасывает врагов",
    "armor_effectiveness": "сильнее пробивает броню",
    "projectile_piercing": "пробивает врагов насквозь",
    "projectile_spread": "пускает снаряды веером",
    "projectile_count": "пускает больше снарядов",
    "trident_return_acceleration": "быстрее возвращается в руку",
    "fishing_time_reduction": "ускоряет поклёвку",
    "fishing_luck_bonus": "улучшает улов",
    "block_experience": "даёт больше опыта за блоки",
    "mob_experience": "даёт больше опыта с мобов",
    "repair_with_xp": "чинится за опыт",
    "trident_spin_attack_strength": "усиливает вихревую атаку",
    "equipment_drops": "увеличивает дроп с мобов",
}

# знак значения меняет смысл: (отрицательное, ноль, положительное)
_SUMMARY_FLIP = {
    "item_damage": ("изнашивается медленнее", "меняет скорость износа",
                    "изнашивается быстрее"),
    "ammo_use": ("экономит боеприпасы", "не тратит боеприпасы",
                 "тратит больше боеприпасов"),
    "crossbow_charge_time": ("взводится быстрее", "меняет скорость взвода",
                             "взводится дольше"),
}

# приоритет «зрелищности» компоненты в описании (больше = раньше)
_SUMMARY_PRIO = {
    "damage": 9, "post_attack": 8, "damage_immunity": 7, "knockback": 7,
    "damage_protection": 6, "attributes": 6, "location_changed": 5,
    "tick": 5, "hit_block": 5, "post_piercing_attack": 5,
    "projectile_spawned": 5, "prevent_equipment_drop": 3,
    "prevent_armor_change": 3, "crossbow_charging_sounds": 2,
    "trident_sound": 2,
}


def _summ_ee_phrase(d):
    """Фраза по EntityEffect (внутри post_attack/tick/...)."""
    if not isinstance(d, dict):
        return None
    t = d.get("type")
    if t == "minecraft:all_of":
        for inner in d.get("effects", []):
            w = _summ_ee_phrase(inner)
            if w:
                return w
        return None
    if t == "minecraft:apply_mob_effect":
        ta = d.get("to_apply")
        ta = [ta] if isinstance(ta, str) else list(ta or [])
        acc = _EFF_ACC.get(ta[0]) if ta else None
        return "накладывает %s" % acc if acc else "накладывает эффекты"
    if t == "minecraft:damage_entity":
        return "бьёт врага"
    if t == "minecraft:ignite":
        return "поджигает врага"
    if t == "minecraft:summon_entity":
        return "призывает сущность"
    if t == "minecraft:explode":
        return "устраивает взрыв"
    if t == "minecraft:change_item_damage":
        return ("бережёт предмет" if _lbv_value(d.get("amount", 1)) < 0
                else "портит предмет")
    if t == "minecraft:apply_impulse":
        return "толкает цель"
    if t == "minecraft:apply_exhaustion":
        return "изматывает цель"
    if t in ("minecraft:replace_block", "minecraft:replace_disk",
             "minecraft:set_block_properties"):
        return "меняет блоки вокруг"
    if t == "minecraft:spawn_particles":
        return "рассыпает частицы"
    if t == "minecraft:play_sound":
        return "подаёт голос"
    if t == "minecraft:run_function":
        # текст mcfunction живёт вне JSON зачарования — _ee_word без слова
        # профиля даёт «Ритуал» (см. _name_seeds): описываем ритуалом
        return "творит особый ритуал"
    if t == "minecraft:attribute":
        acc = _ATTR_ACC.get(d.get("attribute"))
        return "усиливает %s" % acc if acc else None
    return None


def _summ_first_effect(cval):
    """Первый эффект из списка ConditionalEffect-компоненты."""
    if isinstance(cval, list):
        for ent in cval:
            if isinstance(ent, dict):
                eff = ent.get("effect")
                if isinstance(eff, (dict, list)):
                    return eff
                if eff is not None:
                    return eff
    return None


def summarize_enchantment(ejson):
    """Краткое русское описание действия зачарования — ДО 8 СЛОВ, без
    точки, по фактическим компонентам effects: damage → «усиливает урон»,
    knockback → «отбрасывает врагов», post_attack → «мстит ядом при
    ударе по тебе», apply_mob_effect → «накладывает слепоту», attributes
    → «усиливает броню», damage_immunity → «даёт иммунитет к огню»,
    tick/location_changed → «... при ношении/движении», run_function →
    «творит особый ритуал» (доминанта функции — слово «Ритуал» из
    _ee_word/_name_seeds: текст mcfunction вне JSON зачарования).
    Берётся самая «зрелищная» компонента (приоритеты _SUMMARY_PRIO +
    _VE_PRIO), при запасе слов — вторая через «и». Фолбэк при пустых
    эффектах — «даёт скрытую силу»."""
    effects = (ejson or {}).get("effects") if isinstance(ejson, dict) else None
    phrases = []  # (приоритет, фраза)

    def add(prio, txt):
        if txt:
            phrases.append((prio, txt))

    for ckey, cval in (effects or {}).items():
        key = ckey.split(":", 1)[1] if ":" in ckey else ckey
        if key in _SUMMARY_VE:
            add(_VE_PRIO.get(key, 4), _SUMMARY_VE[key])
        elif key in _SUMMARY_FLIP:
            eff = None
            if isinstance(cval, list) and cval and isinstance(cval[0], dict):
                eff = cval[0].get("effect", {})
            elif isinstance(cval, dict):
                eff = cval.get("effect", {})
            s = _ve_sign(eff)
            neg, zero, pos = _SUMMARY_FLIP[key]
            add(_VE_PRIO.get(key, 5), neg if s < -1e-9
                else (pos if s > 1e-9 else zero))
        elif key == "attributes":
            for ent in (cval if isinstance(cval, list) else [cval]):
                if isinstance(ent, dict):
                    acc = _ATTR_ACC.get(ent.get("attribute"))
                    if acc:
                        add(6, "усиливает %s" % acc)
                    else:
                        add(6, "усиливает носителя")
                    break
        elif key == "damage_immunity":
            word = None
            for ent in (cval if isinstance(cval, list) else [cval]):
                if not isinstance(ent, dict):
                    continue
                for rq in ent.get("requirements", []):
                    if not isinstance(rq, dict):
                        continue
                    tags = (rq.get("predicate") or {}).get("tags", [])
                    for tg in tags:
                        if isinstance(tg, dict) and tg.get("id") in _DTAG_DAT:
                            word = _DTAG_DAT[tg["id"]]
                            break
                    if word:
                        break
                if word:
                    break
            add(7, "даёт иммунитет к %s" % word if word
                else "даёт иммунитет к урону")
        elif key == "post_attack":
            # формулировка задачи: «мстит при ударе по тебе» — без
            # падежных вывертов с внутренним эффектом (мстить + творительный
            # не выводится из винительного «накладывает X»)
            add(8, "мстит при ударе по тебе")
        elif key in ("tick", "location_changed", "hit_block",
                     "post_piercing_attack", "projectile_spawned"):
            inner = _summ_first_effect(cval)
            ph = _summ_ee_phrase(inner) if inner else None
            ctx = {"tick": "при ношении", "location_changed": "при движении",
                   "hit_block": "при ударе о блок",
                   "post_piercing_attack": "при пронзающем ударе",
                   "projectile_spawned": "на лету"}[key]
            if ph:
                add(_SUMMARY_PRIO.get(key, 5), "%s %s" % (ph, ctx))
            else:
                add(_SUMMARY_PRIO.get(key, 5), "работает %s" % ctx)
        elif key == "prevent_equipment_drop":
            add(3, "не даёт предмету выпасть")
        elif key == "prevent_armor_change":
            add(3, "запрещает снимать предмет")
        elif key == "crossbow_charging_sounds":
            add(2, "скрипит при взводе")
        elif key == "trident_sound":
            add(2, "поёт как трезубец")
    if not phrases:
        return "даёт скрытую силу"
    phrases.sort(key=lambda p: -p[0])
    lead = phrases[0][1]
    if len(phrases) > 1:
        second = phrases[1][1]
        if len(lead.split()) + len(second.split()) + 1 <= 8:
            return "%s и %s" % (lead, second)
    return lead


# ---------------------------------------------------------------------------
# Инвариант «никакого прямого урона владельцу» (для самотеста)
# ---------------------------------------------------------------------------

# контексты, где эффект применяется к носителю предмета (this = владелец)
_OWNER_CONTEXTS = frozenset(["tick", "location_changed", "post_piercing_attack",
                             "hit_block", "projectile_spawned"])


def _find_damaging(node):
    """Список повреждающих эффектов, найденных в дереве эффекта."""
    found = []
    if isinstance(node, dict):
        if _is_damaging_effect(node):
            # all_of обрабатываем через рекурсию, чтобы найти все части
            if node.get("type") == "minecraft:all_of":
                for e in node.get("effects", []):
                    found.extend(_find_damaging(e))
            else:
                found.append(node)
        else:
            for v in node.values():
                found.extend(_find_damaging(v))
    elif isinstance(node, list):
        for v in node:
            found.extend(_find_damaging(v))
    return found


def _owner_damage_violations(ench):
    """Проверка зачарования на прямой урон владельцу. Возвращает список строк."""
    viol = []
    for comp, val in ench.get("effects", {}).items():
        k = comp.split(":", 1)[1]
        if k in _OWNER_CONTEXTS:
            for entry in val:
                for d in _find_damaging(entry.get("effect")):
                    viol.append("%s: %s с повреждающим эффектом %s"
                                % (comp, k, d.get("type")))
        elif k == "post_attack":
            for entry in val:
                if _is_damaging_effect(entry.get("effect", {})):
                    owner = entry["enchanted"]
                    if entry["affected"] == owner or (
                            owner == "attacker"
                            and entry["affected"] == "damaging_entity"):
                        viol.append("%s: урон владельцу (enchanted=%s, "
                                    "affected=%s)"
                                    % (comp, owner, entry["affected"]))
    return viol


# ---------------------------------------------------------------------------
# Самотест: python gen_enchantments.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import re

    NS = "tstns"
    seeds = list(range(25))
    all_counts = []
    comp_seen = set()
    prov_types = set()
    lbv_types = set()
    name_samples = []
    fn_cats_seen = set()
    fn_samples = []
    fn_count = gate_count = 0
    ctx_counts = {}
    cov_ctx = {}
    _FN_TEST_WORDS_SEEN = set()  # слова профилей функций (связь с названием)
    total = 0
    passive_total = 0
    summ_samples = []
    errors = []

    # краевые случаи новых экспортов (связка с gen_loot)
    if passive_enchants({}) != [] or passive_enchants(None) != []:
        errors.append("passive_enchants: краевые случаи")
    if passive_enchants({"a:b": {}, "a:c": {"effects": {}}}) != []:
        errors.append("passive_enchants: без эффектов не пассивно")
    if not summarize_enchantment({}).strip() \
            or not summarize_enchantment({"effects": {}}).strip():
        errors.append("summarize_enchantment: пустые эффекты")

    # глаголы mcfunction, разрешённые политикой (белый список)
    _FN_TEST_VERBS = {"particle", "playsound", "effect", "summon",
                      "title", "tellraw", "execute", "item", "xp"}
    # запрещённые подстроки (после замены легального "effect give ");
    # "teleport" НЕ ищем подстрокой — это слово в id звука
    # entity.enderman.teleport, а сам глагол уже отсечён белым списком
    _FN_TEST_BAN = ("kill", "gamemode", "gamerule", "scoreboard",
                    "setblock", "weather", "ban", "kick", "deop",
                    "stopsound", "fillbiome", "loot ",
                    "give ", "tp ", "time ", "data ", "fill ")
    # id для проверки категории перекраски (половина сидов — с ними)
    half_mods = ["%s:m%d" % (NS, i) for i in range(3)]
    half_preds = ["%s:p%d" % (NS, i) for i in range(4)]

    def _check_fn_body(tag, ctx, body, known_refs, gates_map=None):
        """Проверки строк mcfunction: белый список глаголов, запреты,
        worn-инварианты, JSON actionbar, известные ссылки <ns>:...,
        гейт молнии <= 0.15 (gates_map: id предиката → json)."""
        for l in body:
            # реальная команда — после последнего " run " у execute
            cmd = l
            if cmd.startswith("execute"):
                i = cmd.rfind(" run ")
                if i < 0:
                    errors.append("%s: execute без run: %r" % (tag, l[:60]))
                    continue
                cmd = cmd[i + 5:]
                # одна команда = одна строка: после ' run ' не может быть
                # нового execute (вложенные цепочки запрещены)
                if cmd.startswith("execute "):
                    errors.append("%s: вложенный execute: %r" % (tag, l[:60]))
                    continue
            verb = cmd.split(None, 1)[0].lower()
            if verb not in _FN_TEST_VERBS:
                errors.append("%s: глагол %r не в белом списке: %r"
                              % (tag, verb, l[:60]))
            if verb == "effect" and not cmd.startswith("effect give "):
                errors.append("%s: effect не give: %r" % (tag, l[:60]))
            m = re.match(r"xp add @s (\d+) points$", cmd)
            if verb == "xp" and (not m or int(m.group(1)) > 5):
                errors.append("%s: xp не 'add @s <=5 points': %r"
                              % (tag, l[:60]))
            # запрещённые подстроки ("effect give " — легален)
            probe = cmd.replace("effect give ", "EFFGIVE ")
            for bad in _FN_TEST_BAN:
                if bad in probe:
                    errors.append("%s: запрещённое %r: %r" % (tag, bad, l[:60]))
            if "actionbar" in l:
                try:
                    j = json.loads(l.split("actionbar ", 1)[1])
                    if not isinstance(j.get("text"), str) or not j["text"]:
                        raise ValueError("нет text")
                except Exception as ex:
                    errors.append("%s: битый JSON actionbar (%s): %r"
                                  % (tag, ex, l[:60]))
            # JSON title-заголовка и tellraw (клятва/шёпот) — валиден и с text
            if " title @s title " in l or l.startswith("title @s title "):
                try:
                    j = json.loads(l.split("title @s title ", 1)[1])
                    if not isinstance(j.get("text"), str) or not j["text"]:
                        raise ValueError("нет text")
                except Exception as ex:
                    errors.append("%s: битый JSON title (%s): %r"
                                  % (tag, ex, l[:60]))
            if cmd.startswith("tellraw "):
                try:
                    j = json.loads(cmd.split("tellraw @s ", 1)[1])
                    if not isinstance(j.get("text"), str) or not j["text"]:
                        raise ValueError("нет text")
                except Exception as ex:
                    errors.append("%s: битый JSON tellraw (%s): %r"
                                  % (tag, ex, l[:60]))
            if ctx == "worn":
                # WORN: только дешёвые гейченые команды — частицы/звук/
                # флейвор/перекраска/шёпот; никаких призывов (клыки/облака/
                # молнии/XP — не "summon ..." в тексте звука!) и никаких
                # эффектов
                if verb not in ("particle", "playsound", "title", "item",
                                "tellraw"):
                    errors.append("%s: недешёвая worn-команда (%s): %r"
                                  % (tag, verb, l[:60]))
                if cmd.startswith("summon "):
                    errors.append("%s: призыв в worn: %r" % (tag, l[:60]))
                if "effect give @s" in cmd:
                    errors.append("%s: effect give @s в worn: %r"
                                  % (tag, l[:60]))
                if not l.startswith("execute if predicate "):
                    errors.append("%s: worn-команда без гейта: %r"
                                  % (tag, l[:60]))
            elif "summon minecraft:lightning_bolt" in cmd:
                if not l.startswith("execute if predicate "):
                    errors.append("%s: молния без гейта: %r" % (tag, l[:60]))
                elif gates_map is not None:
                    # гейт молнии обязан быть random_chance <= 0.15
                    mg = re.match(
                        r"execute if predicate (%s:[a-z0-9_./\-]+) " % NS, l)
                    if mg:
                        ch = (gates_map.get(mg.group(1))
                              or {}).get("chance")
                        if not (isinstance(ch, (int, float))
                                and 0 < ch <= 0.15):
                            errors.append(
                                "%s: гейт молнии %r вне (0;0.15]" % (tag, ch))
            # все ссылки <ns>:... известны (гейты/mods/preds/зачарования)
            for m2 in re.finditer(r"%s:[a-z0-9_./\-]+" % NS, l):
                if m2.group(0) not in known_refs:
                    errors.append("%s: ссылка на неизвестное %s"
                                  % (tag, m2.group(0)))

    def _fn_cats(text):
        """Какие категории видны в тексте функции (для отчёта покрытия)."""
        found = set()
        for cat, needle in (("fangs", "evoker_fangs"),
                            ("cloud", "area_effect_cloud"),
                            ("lightning", "lightning_bolt"),
                            ("flavor", "actionbar"),
                            ("recolor", "item modify"),
                            ("xp", "experience_orb"),
                            ("xp", "xp add"),
                            ("firework", "firework_rocket"),
                            ("selfbuff", "effect give @s"),
                            ("aura", "effect give @e"),
                            ("sound", "playsound"),
                            ("particle", "particle "),
                            # новые категории с узнаваемыми маркерами
                            ("shards", "block_state:{Name"),
                            ("whisper", "tellraw"),
                            ("oath", "title @s title")):
            if needle in text:
                found.add(cat)
        return found

    id_re = re.compile(r"^[a-z0-9_/.-]+$")
    for seed in seeds:
        mods = half_mods if seed % 2 == 0 else None
        preds = half_preds if seed % 3 == 0 else None
        r1 = random.Random(seed)
        res = rand_enchantments(r1, NS, "dim%d" % seed,
                                mod_ids=mods, pred_ids=preds)
        # воспроизводимость (с теми же аргументами)
        r2 = random.Random(seed)
        res2 = rand_enchantments(r2, NS, "dim%d" % seed,
                                 mod_ids=mods, pred_ids=preds)
        if json.dumps(res, sort_keys=True) != json.dumps(res2, sort_keys=True):
            errors.append("seed %d: невоспроизводимо" % seed)

        # LAST_ENCHANTMENTS — кэш для gen_loot: равен последнему результату
        if LAST_ENCHANTMENTS != res2["enchantments"]:
            errors.append("seed %d: LAST_ENCHANTMENTS != результату" % seed)
        # passive_enchants: сортировка и взаимная полнота
        pass_ids = passive_enchants(res["enchantments"])
        if pass_ids != sorted(pass_ids):
            errors.append("seed %d: passive_enchants не отсортирован" % seed)
        for eid, e in res["enchantments"].items():
            is_pass = any(c in (e.get("effects") or {})
                          for c in PASSIVE_EFFECT_COMPONENTS)
            if (eid in pass_ids) != is_pass:
                errors.append("seed %d: passive_enchants ошибочен: %s"
                              % (seed, eid))
        passive_total += len(pass_ids)
        # summarize_enchantment: непусто, без точки, ДО 8 СЛОВ
        for eid, e in res["enchantments"].items():
            s = summarize_enchantment(e)
            if not s.strip():
                errors.append("%s: пустое описание" % eid)
            if s.endswith(".") or s.endswith(" "):
                errors.append("%s: описание с точкой/хвостом: %r" % (eid, s))
            if len(s.split()) > 8:
                errors.append("%s: описание длиннее 8 слов: %r" % (eid, s))
            if len(summ_samples) < 40:
                summ_samples.append((e["description"]["text"], s))

        enchs = res["enchantments"]
        provs = res["enchantment_providers"]
        all_counts.append(len(enchs))
        total += len(enchs)

        for eid, e in enchs.items():
            short = eid.split(":", 1)[1]
            if not id_re.match(short):
                errors.append("%s: плохое имя файла (двоеточие?)" % eid)
            for key in ("description", "supported_items", "weight",
                        "max_level", "min_cost", "max_cost", "anvil_cost",
                        "slots"):
                if key not in e:
                    errors.append("%s: нет ключа %s" % (eid, key))
            if not (1 <= e["weight"] <= 1024):
                errors.append("%s: weight вне 1..1024" % eid)
            if not (1 <= e["max_level"] <= 255):
                errors.append("%s: max_level вне 1..255" % eid)
            if e["anvil_cost"] < 0:
                errors.append("%s: anvil_cost < 0" % eid)
            for s in e["slots"]:
                if s not in _SLOT_GROUPS:
                    errors.append("%s: неизвестный слот %r" % (eid, s))
            for c in ("min_cost", "max_cost"):
                if set(e[c].keys()) != {"base", "per_level_above_first"}:
                    errors.append("%s: %s не {{base, per_level_above_first}}" % (eid, c))
            neff = len(e.get("effects", {}))
            if not (1 <= neff <= 5):
                errors.append("%s: эффектов %d (нужно 1-5)" % (eid, neff))
            ex = e.get("exclusive_set")
            if ex:
                exl = ex if isinstance(ex, list) else [ex]
                for x in exl:
                    if x not in enchs and x not in _VANILLA_ENCHS:
                        errors.append("%s: exclusive_set ссылается на %s" % (eid, x))
            for v in _owner_damage_violations(e):
                errors.append("%s: %s" % (eid, v))
            # юзабельность компонент (юзер: «зачарования не должны быть на
            # предметах где их нельзя использовать»): каждая компонента
            # работает на supported_items (+slots) по таблице правил
            # (_COMP_ITEM_RULES); профиль absurd — исключение (там всё
            # можно); профиль — из side-канала LAST_PROFILES
            prof = LAST_PROFILES.get(eid)
            if prof is not None and prof != "absurd":
                for comp in e.get("effects", {}):
                    k = comp.split(":", 1)[1]
                    if not _comp_usable(k, e["supported_items"],
                                        e["slots"]):
                        errors.append(
                            "%s: компонента %s неюзабельна для %s"
                            % (eid, k,
                               json.dumps(e["supported_items"])[:70]))
                # тематические пулы атрибутов: attack — оружию, mining —
                # инструментам, броневые — броне (и внутри location_changed)
                allowed_attr = _PROFILE_ATTR_IDS.get(prof, _ALL_ATTR_IDS)
                eff = e.get("effects", {})
                attr_nodes = list(eff.get("minecraft:attributes") or [])
                for ent in eff.get("minecraft:location_changed") or []:
                    if isinstance(ent, dict):
                        d = ent.get("effect", {})
                        if isinstance(d, dict) \
                                and d.get("type") == "minecraft:attribute":
                            attr_nodes.append(d)
                for ent in attr_nodes:
                    if isinstance(ent, dict) and ent.get("attribute") \
                            not in allowed_attr:
                        errors.append("%s: атрибут %s вне пула профиля %s"
                                      % (eid, ent.get("attribute"), prof))
            for comp, val in e.get("effects", {}).items():
                comp_seen.add(comp)
                txt = json.dumps(val)
                for t in ("linear", "clamped", "fraction", "levels_squared",
                          "lookup", "exponent"):
                    if '"minecraft:%s"' % t in txt:
                        lbv_types.add(t)

        for pid, p in provs.items():
            short = pid.split(":", 1)[1]
            if not id_re.match(short):
                errors.append("%s: плохое имя файла" % pid)
            prov_types.add(p["type"])
            refs = p["enchantments"] if p["type"] != "minecraft:single" \
                else [p["enchantment"]]
            if isinstance(refs, str):
                refs = [refs]
            for x in refs:
                if x not in enchs:
                    errors.append("%s: ссылка на несуществующее %s" % (pid, x))

        # ---- mcfunction-функции run_function-эффектов ----
        funcs = res.get("functions", {})
        gates = res.get("gate_predicates", {})
        fn_count += len(funcs)
        gate_count += len(gates)
        # каждой функции соответствует зачарование с run_function — и наоборот
        rf_expected = set()
        for eid, e in enchs.items():
            if "run_function" in json.dumps(e):
                rf_expected.add(eid.split(":", 1)[1])
                ctx = _ench_rf_context(e.get("effects", {}))
                if ctx not in ("full", "event", "worn"):
                    errors.append("%s: run_function вне известных компонент" % eid)
        if set(funcs) != rf_expected:
            errors.append("seed %d: functions %s != run_function-зачарованиям %s"
                          % (seed, sorted(funcs), sorted(rf_expected)))
        known_refs = (set(gates) | set(enchs) | set(mods or [])
                      | set(preds or []))
        for fname, text in funcs.items():
            tag = "seed %d/%s" % (seed, fname)
            if not text or not text.endswith("\n"):
                errors.append("%s: пустой/незакрытый текст" % tag)
            body = [l.strip() for l in text.splitlines()
                    if l.strip() and not l.strip().startswith("#")]
            if not body:
                errors.append("%s: нет команд" % tag)
                continue
            e = enchs.get("%s:%s" % (NS, fname), {})
            ctx = _ench_rf_context(e.get("effects", {})) or "full"
            ctx_counts[ctx] = ctx_counts.get(ctx, 0) + 1
            mx = 3 if ctx == "worn" else 10
            if not 1 <= len(body) <= mx:
                errors.append("%s: команд %d (нужно 1-%d)"
                              % (tag, len(body), mx))
            _check_fn_body(tag, ctx, body, known_refs, gates_map=gates)
            fn_cats_seen |= _fn_cats(text)
            if len(fn_samples) < 10:
                fn_samples.append((seed, fname, ctx, text))

        for pid, pj in gates.items():
            if not id_re.match(pid.split(":", 1)[1]):
                errors.append("%s: плохое имя файла гейта" % pid)
            if pj.get("condition") != "minecraft:random_chance":
                errors.append("%s: гейт не random_chance" % pid)
            ch = pj.get("chance")
            if not (isinstance(ch, (int, float)) and 0.0 < ch <= 1.0):
                errors.append("%s: шанс %r вне (0;1]" % (pid, ch))

        # примеры названий
        for eid in list(enchs)[:2]:
            name_samples.append((eid, enchs[eid]["description"]["text"]))

    # ---- покрытие категорий: прямая генерация по всем контекстам ----
    # (run_function в зачарованиях редок — проверяем разнообразие функций
    # напрямую: все контексты, с mods/preds и без; заодно МЕТРИКА
    # РАЗНООБРАЗИЯ — уникальные комбинации категорий по report; 120 сидов ×
    # 3 контекста × 2 варианта = 720 функций (метрика «на 500 функций»))
    profiles = set()
    for with_ids in (True, False):
        for ctx in ("full", "event", "worn"):
            for s in range(120):
                cov_gates = {}
                rep = set()
                rc = random.Random(97000 + s)
                eid = "%s:cov_%s_%d" % (NS, ctx, s)
                text, word = _gen_ench_function(
                    rc, eid, ctx,
                    mod_ids=half_mods if with_ids else None,
                    pred_ids=half_preds if with_ids else None,
                    gates=cov_gates, report=rep)
                body = [l.strip() for l in text.splitlines()
                        if l.strip() and not l.strip().startswith("#")]
                tag = "cov/%s/%d" % (ctx, s)
                mx = 3 if ctx == "worn" else 10
                if not 1 <= len(body) <= mx:
                    errors.append("%s: команд %d (нужно 1-%d)"
                                  % (tag, len(body), mx))
                known = (set(cov_gates) | set(half_mods if with_ids else [])
                         | set(half_preds if with_ids else []))
                _check_fn_body(tag, ctx, body, known, gates_map=cov_gates)
                fn_cats_seen |= rep | _fn_cats(text)
                cov_ctx[ctx] = cov_ctx.get(ctx, 0) + 1
                if rep:
                    profiles.add(frozenset(rep))
                if word not in _FN_TEST_WORDS_SEEN:
                    _FN_TEST_WORDS_SEEN.add(word)
    cov_words = _FN_TEST_WORDS_SEEN
    n_cov = sum(cov_ctx.values())
    # требования юзера: >=35 категорий; >=150 уникальных профилей;
    # плотность разнообразия: >=150 профилей на 500 функций
    if len(_FN_CAT_W) < 35:
        errors.append("категорий команд %d (нужно >= 35)" % len(_FN_CAT_W))
    if len(profiles) < 150:
        errors.append("разнообразие: всего %d уникальных профилей категорий "
                      "(нужно >= 150)" % len(profiles))
    if len(profiles) * 500.0 / max(1, n_cov) < 150:
        errors.append("разнообразие: %.0f профилей на 500 функций "
                      "(нужно >= 150)"
                      % (len(profiles) * 500.0 / max(1, n_cov)))

    print("=== gen_enchantments self-test (%d seeds, %d зачарований) ==="
          % (len(seeds), total))
    print("пассивных зачарований (attributes/tick/location_changed/"
          "damage_immunity/prevent_*): %d из %d (%.0f%%)"
          % (passive_total, total, 100.0 * passive_total / max(1, total)))
    if passive_total == 0:
        errors.append("пассивных зачарований нет ни одного (нужно > 0)")
    print("примеры описаний summarize_enchantment (до 8 слов):")
    for nm, s in summ_samples[:8]:
        print("  «%s» — %s" % (nm, s))
    print("количество зачарований на измерение: min %d, max %d, среднее %.1f"
          % (min(all_counts), max(all_counts), sum(all_counts) / len(all_counts)))
    print("распределение: %s" % sorted(all_counts))
    print("типы провайдеров: %s" % sorted(prov_types))
    print("виды LBV: %s" % sorted(lbv_types))
    print("покрытые компоненты: %d/%d" % (len(comp_seen), len(_COMPONENTS)))
    missing = sorted(set(_COMPONENTS) - {c.split(":", 1)[1] for c in comp_seen})
    if missing:
        print("  НЕ покрыты: %s" % missing)
    print("run_function-функций: %d (гейт-предикатов: %d), контексты: %s"
          % (fn_count, gate_count,
             ", ".join("%s=%d" % kv for kv in sorted(ctx_counts.items()))))
    print("прямое покрытие: %s функций по контекстам (с mods/preds и без)"
          % ", ".join("%s=%d" % kv for kv in sorted(cov_ctx.items())))
    print("разнообразие: %d функций → %d уникальных профилей категорий "
          "(>= 150; на 500 функций: %.0f)"
          % (n_cov, len(profiles), len(profiles) * 500.0 / max(1, n_cov)))
    print("покрытые категории команд: %d/%d: %s"
          % (len(fn_cats_seen), len(_FN_CAT_PRIO), sorted(fn_cats_seen)))
    not_cov = sorted(set(_FN_CAT_PRIO) - fn_cats_seen)
    if not_cov:
        print("  НЕ покрыты категории: %s" % not_cov)
    print("слова профилей (связь с названиями): %s"
          % sorted(_FN_TEST_WORDS_SEEN))
    print("примеры функций:")
    for seed, fname, ctx, text in fn_samples[:4]:
        print("--- seed %d: %s (контекст %s) ---" % (seed, fname, ctx))
        print(text.rstrip("\n"))
    print("примеры названий:")
    for eid, nm in name_samples[:8]:
        print("  %s — «%s»" % (eid, nm))
    if errors:
        print("ОШИБКИ (%d):" % len(errors))
        for e in errors[:20]:
            print("  " + e)
        raise SystemExit(1)
    print("OK: инварианты соблюдены, воспроизводимость подтверждена")
