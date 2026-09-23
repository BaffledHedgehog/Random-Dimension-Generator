#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_loot.py - генератор случайных лут-таблиц для Minecraft 26.2
(data format 107, каталог data/<ns>/loot_table/ - в 26.2 он в ЕДИНСТВЕННОМ
числе, не loot_tables!; в имени файла - ТОЛЬКО basename, без префикса
namespace: на Windows id с двоеточием молча превращается в NTFS
ADS-артефакт вместо файла).

Формат КАЖДОГО поля сверен с ванильным jar 26.2
(minecraft-26.2-client.jar, data/minecraft/loot_table/** - 1355 таблиц),
классами net/minecraft/world/item/component/*.class (javap) и реальным
сервером (loot spawn каждой таблицы):
  * верхний уровень: {"type", "pools", "random_sequence"};
  * типы таблиц, реально встречающиеся в ванильных данных:
    chest, entity, block, gift, archaeology, fishing, barter, equipment;
  * пул: {"rolls", "entries", "conditions", "functions"}; rolls - число
    (float) ИЛИ NumberProvider {"type": "minecraft:uniform",
    "min": 1.0, "max": 4.0} (в ванили именно min/max, не min_inclusive!);
  * записи: item / loot_table (value: строка-id или вложенный объект) /
    empty / tag {"name", "expand"} / group / alternatives (children);
  * функции: ключ "function" (не "name"!), set_count (count -
    NumberProvider: constant/uniform/binomial), set_damage (damage),
    set_potion (id), set_components (components), set_enchantments
    (enchantments: {id: float}), enchant_randomly (options, опционально),
    enchant_with_levels (levels), furnace_smelt (+conditions на функции),
    apply_bonus (enchantment + formula: ore_drops / uniform_bonus_count
    / binomial_with_bonus_count - параметры формулы лежат ВЛОЖЕННО
    в объекте "parameters": {"bonusMultiplier": int} либо
    {"probability": float, "extra": int}; сверено с ванильными
    таблицами и ApplyBonusCount.class),
    set_ominous_bottle_amplifier (amplifier), set_instrument (options);
  * условия: random_chance (chance), killed_by_player, any_of (terms),
    inverted (term), table_bonus (chances - длина = max_level+1);
  * компоненты - по классам net/minecraft/world/item/component/*.class и
    net/minecraft/core/component/DataComponents.class (всего 111 полей;
    сверен каждый кодек javap'ом + серверной пробой set_components):
      custom_name, item_name, lore [строка, ...] - ПЛОСКИЙ массив
      текстовых компонентов (обёртки "lines" в 26.2 НЕТ), rarity,
      enchantments / stored_enchantments - ПРЯМАЯ карта {id: уровень}
      (в 26.2 обёртки "levels" НЕТ - ItemEnchantments.CODEC это
      Codec.unboundedMap с intRange(1,255)),
      attribute_modifiers - ПЛОСКИЙ массив [{"type": атрибут, "id",
      "amount", "operation", "slot"}]: поля модификатора лежат РЯДОМ
      с type/slot, вложенного объекта "modifier" в 26.2 НЕТ
      ("slot" опционален, по умолчанию any). ВНИМАНИЕ: компонент
      ЗАМЕНЯЕТ ванильные дефолтные модификаторы предмета ЦЕЛИКОМ,
      поэтому при его генерации ванильные базовые характеристики
      (урон/скорость атаки оружия, броня/твёрдость брони) ВСЕГДА
      включаются В НАЧАЛО списка - см. _BASE_ATTRS, unbreakable {},
      enchantment_glint_override (bool), custom_data (произвольный NBT),
      max_damage, max_stack_size, damage, repair_cost (int),
      damage_resistant {"types": "#minecraft:is_fire"}
      (старого fire_resistant больше нет), dyed_color (int RGB),
      potion_contents {"potion": "..."}, potion_duration_scale,
      trim {"pattern", "material"};
      боевые: weapon {item_damage_per_attack, disable_blocking_for_
      seconds}, attack_range {min_reach, max_reach, hitbox_margin
      (ТОЛЬКО [0.0;1.0]!), mob_factor, min/max_creative_reach},
      piercing_weapon
      {deals_knockback, dismounts, hit_sound}, kinetic_weapon
      {damage_multiplier, forward_movement, delay_ticks,
      contact_cooldown_ticks, hit_sound, damage_conditions/
      knockback_conditions {min_speed, max_duration_ticks},
      dismount_conditions {min_relative_speed, max_duration_ticks}},
      minimum_attack_charge (float), swing_animation {type: none|stab|
      whack - БЕЗ namespace!, duration}, blocks_attacks
      {block_delay_seconds, disable_cooldown_scale, item_damage
      {threshold, base, factor}, damage_reductions [{type:
      HolderSet-типов-урона, factor, base, horizontal_blocking_angle}],
      bypassed_by, block_sound, disable_sound}, death_protection
      {death_effects: [consume-эффекты]};
      зачарования/ремонт: enchantable {value}, repairable {items:
      тег/id/список};
      использование: food {nutrition, saturation, can_always_eat},
      consumable {consume_seconds, animation, sound,
      has_consume_particles, on_consume_effects [...]} (типы
      consume-эффектов: apply_effects {effects: [{id, amplifier,
      duration}], probability}, remove_effects, clear_all_effects,
      teleport_randomly {diameter}, play_sound {sound}),
      use_remainder {id, count}, use_cooldown {seconds,
      cooldown_group}, use_effects {can_sprint, interact_vibrations,
      speed_multiplier<=1.0}, glider {}, intangible_projectile {},
      equippable {slot, asset_id (id EQUIPMENT-ассета
      assets/<ns>/equipment/<id>.json - в генерации НЕ задаётся НИКОГДА:
      без него игра берёт ассет по id предмета, т.е. родную текстуру
      брони; случайный asset_id ломал текстуру на игроке), equip_sound,
      dispensable, swappable, damage_on_hurt, equip_on_interact},
      tool {rules: [{blocks: «#тег» РЕШЁТКОЙ или список id, speed,
      correct_for_drops}],
      default_mining_speed, damage_per_block,
      can_destroy_blocks_in_creative};
      «предметные»: fireworks {flight_duration, explosions},
      firework_explosion {shape, colors, fade_colors, has_trail,
      has_twinkle}, charged_projectiles [стеки], bundle_contents
      [стеки], container [{slot, item: {id, count, components}}],
      container_loot {loot_table, seed}, lock - «ГОЛЫЙ» ItemPredicate
      {"items": "#minecraft:planks"} (LockCode.CODEC - xmap от
      ItemPredicate.CODEC, обёртки "lock" НЕТ), jukebox_playable
      (СТРОКА - id песни), instrument (СТРОКА - id инструмента
      рога из реестра instrument: прямая ссылка или «#тег»),
      map_color (int), map_decorations {имя: {type, x, z, rotation}},
      map_id (int), suspicious_stew_effects [{id, duration}],
      writable_book_content {pages: [{raw, filtered}]},
      written_book_content {title: {raw, filtered}, author,
      generation, resolved, pages: [{raw: компонент, filtered}]}
      (поля "book" у кодека НЕТ), banner_patterns - ПЛОСКИЙ массив
      [{pattern, color}], base_color,
      block_state {свойство: значение}, custom_model_data {floats,
      flags, strings, colors}, profile {name}, bees [{entity_data:
      {id, ...}, ticks_in_hive, min_ticks_in_hive}];
      предметно-специфичные с путевыми id (модель «сущность/поле»; сами
      id компонентов доказаны байткодом регистрации DataComponents):
      horse/variant ("white"|"creamy"|"chestnut"|"brown"|"black"|
      "gray"|"dark_brown" - БЕЗ namespace), sheep/color, wolf/collar,
      cat/collar, shulker/color, tropical_fish/base_color,
      tropical_fish/pattern, tropical_fish/pattern_color, dye (цвет
      DyeColor), sulfur_cube_content {id, count}, bucket_entity_data
      {entity: {id}}, ominous_bottle_amplifier (int 0-4),
      pot_decorations [4 предмета], note_block_sound (id звука),
      painting/variant (id из реестра painting_variant), axolotl/variant
      ("lucy"|"wild"|"gold"|"cyan"|"blue" - enum, БЕЗ namespace),
      salmon/size ("small"|"medium"|"large"), варианты спавн-яиц:
      chicken|cow|pig|frog/variant = "minecraft:temperate"|"warm"|"cold"
      (файловые реестры - С namespace), wolf/variant и cat/variant
      (id реестров jar), villager/variant ("minecraft:plains" и т.п.),
      llama|fox|rabbit|parrot|mooshroom/variant (enum),
      zombie_nautilus/variant, звуковые cat|wolf|cow|pig|chicken/
      sound_variant (id реестров <entity>_sound_variant);
      break_sound (id звука поломки), potion_contents {potion,
      custom_color, custom_effects [{id, amplifier, duration}]}.

Логика («не фул рандом»): у каждой таблицы есть характер
(weapons-heavy / treasure / junk / food / mixed / mob), под который
согласованно подбираются предметы; entity-таблицы строятся как дроп моба
(еда/мусор + редкая награда за killed_by_player), археология - черепки
и хлам, бартер - сокровища. Основные пулы - курируемые, плюс «дикий
тир»: с малым шансом может выпасть ЛЮБОЙ предмет полного каталога
(1523 id - весь реестр minecraft:item минус технические: air, barrier,
light, командные/структурные блоки, debug_stick, knowledge_book,
test_*). Специфичные компоненты ставятся только на «свои» предметы
(баннеры, книги, фейерверки, вёдра, спавн-яйца и т.д.) - 98 из 111
полей DataComponents (tooltip_display и tooltip_style убраны из
генерации: прятатьTooltip-трюки запутывали игроков); недостающие -
технические (recipes,
map_postprocessing, debug_stick_state и др.) либо не выдаваемые
намеренно, лутом не выдаются. Вложенность
ГЛУБОКАЯ - компоненты внутри компонентов: арбалет заряжен
зачарованными зельевыми стрелами (potion_contents с кастомными
комбинациями эффектов) и фейерверками С взрывами; мешок и сундук -
с книгой, рогом, пластинкой, арбалетом внутри (тематические заливки
«припасы/дары земли/коллекция»); еда превращается (use_remainder)
в другой предмет - с шансом 40-60% оставляя после себя посуду,
остаток из пула или КАСТОМНЫЙ именной остаток («Косточка от
похлёбки»); у предмета есть «истинное имя» (item_name - базовое имя,
его перекрывает custom_name).

Инварианты генерации (жалобы юзеров, сверяются самотестом):
  * БАЗОВЫЕ АТРИБУТЫ: attribute_modifiers на предмете с ванильными
    дефолтами всегда НАЧИНАЕТСЯ с них (броня: armor+armor_toughness
    своего слота, нэзерит + knockback_resistance; оружие/инструменты:
    attack_damage+attack_speed по ванильным значениям) - «не урезать,
    а ДОПОЛНИТЬ»;
  * СЛОТЫ атрибутов - только работающие: armor-слоты (head/chest/legs/
    feet/armor) - предметам, которые реально туда надеваются (броне
    или «дикой» диковине с equippable), hand-слоты - оружию/инструментам
    и «рукастым» предметам; слот any - где угодно;
  * equippable.asset_id НЕ рандомится (текстура брони на игроке
    соответствует предмету); у настоящей брони компонент equippable
    вообще не трогаем - ванильный уже на месте;
  * camera_overlay не генерируется; компонент stackable не ставится
    никогда; max_stack_size - только «бонусный» (65-99) и только
    недamageable предметам с >=2 другими кастомными компонентами;
  * tooltip_display / tooltip_style / hide_tooltip / hidden_components
    НЕ генерируются НИКОГДА (самотест грепает сгенерированный JSON);
  * имена и lore РАСКРЫВАЮТ фактическое содержимое (зелья - эффект,
    атрибуты - величина, чары, еда, планер...), а не полностью
    рандомные; упоминаний trim в именах/лоре нет (trim виден и так);
  * НЕ БЫВАЕТ предметов «только с визуалом»: если после генерации
    компонентов у предмета остались лишь косметические особенности
    (rarity, item_name, custom_name, lore, окраска, глинт, custom_data,
    орнаменты...), ему добавляется РАБОЧАЯ фича - приоритетно
    пассивное зачарование измерения (attributes/tick/location_changed/
    damage_immunity/prevent_* - действуют при ношении/удержании),
    фолбэк - функциональный компонент (attribute_modifiers с базовыми
    значениями, potion_contents, glider, consumable с эффектами);
  * КАЖДОЕ кастомное зачарование измерения (id не из minecraft:)
    получает lore-строку «Имя зачарования - описание действия»
    (описание - gen_enchantments.summarize_enchantment); ванильные
    зачарования в lore НЕ описываются (игроки их знают);
  * КАПЫ (жалоба: «слишком много rolls - контейнеры ПУСТЫЕ от передозировки,
    игра ВИСНЕТ после убийства моба») - жёсткие пределы, проверяются
    самотестом на КАЖДОЙ таблице:
      - пулов <= 8 (mob 1-2, chest 3-6, treasure 4-8, прочие 2-5);
      - rolls <= 6 (и min >= 1: роллы никогда не «съедают» пул),
        bonus_rolls <= 2 (только не-mob пула, редко);
      - вложенные loot_table-записи: <= 2 на таблицу, глубина ровно 1
        (таблица-цель сама ссылок не имеет; ссылки только «вперёд» или
        на ванильные id - план ссылок строится заранее в rand_loot);
      - mob-таблицы (entity): 1-2 пула, rolls 1-2, БЕЗ вложенных таблиц
        и group/alternatives (суммарно <= ~6 предметов с убийства),
        предметы «лёгкие» - <= 2 функциональных компонентов
        (имя/lore-подсказки не в счёт), без контейнеров/зарядов/NBT-мобов;
  * ПУСТЫЕ КОНТЕЙНЕРЫ невозможны: в КАЖДОЙ таблице есть «гарантийный»
    пул (первый) - rolls >= 1, БЕЗ условий пула, БЕЗ empty-записей, с
    хотя бы одной безусловной item-записью (plain item не вылетает и
    из контекстной чистки _strip_table). Пустые записи (empty) - только
    в НЕпервом пуле и с малым весом; unconditional-альтернативы
    (перехват выбора) не генерируются в принципе - не-последний ребёнок
    alternatives ВСЕГДА с условием;
  * ЗАЧАРОВАНИЯ ТОЛЬКО НА СОВМЕСТИМЫХ ПРЕДМЕТАХ (жалоба: «не надо мечу
    давать защиту - его нельзя экипировать»), проверяется самотестом
    по ВСЕМ таблицам:
      - ванильные: каждый id зачарования несёт точный список предметов
        из jar 26.2 (data/minecraft/enchantment/*.json - supported_items
        через теги #minecraft:enchantable/*, содержимое тегов захардкожено
        по data/minecraft/tags/item/enchantable/*.json): sharpness не
        попадёт на кирку, protection - на меч, knockback/looting - на
        топор; enchanted_book - исключение-носитель (любые, применяются
        наковальней только к совместимому);
      - кастомные (rndim:*): предмет обязан входить в supported_items
        зачарования (кэш _ENCH_INFO: тег|#id|список разрешается картой
        тегов из jar; неизвестный тег = не ставим). Действует и для
        «спасения» визуальных предметов, и для options у
        enchant_with_levels/enchant_randomly; enchant_randomly без
        явных опций валиден сам по себе;
  * ТЕМАТИЧЕСКИЕ ПУЛЫ: у каждой таблицы 2-4 темы (арсенал/провизия/
    сокровища/инструменты/алхимия/письмена/хлам/реликвии), каждая со
    своим весом; пул целиком одной темы - наборы записей согласованы
    по смыслу, а не полный рандом;
  * РАЗНООБРАЗИЕ ФУНКЦИЙ/УСЛОВИЙ: цепочки set_count+limit_count+
    set_damage+enchant_*, кривые количества constant/uniform/binomial,
    bonus_rolls, условия random_chance / random_chance_with_enchanted_
    bonus (только entity: нужен ATTACKING_ENTITY) / table_bonus (только
    fishing/archaeology/vault: нужен TOOL) / killed_by_player (entity) /
    any_of/all_of/inverted - контекст каждого условия сверен с
    LootContextParamSets 26.2 (javap), чистка _strip_cond снимает
    несовместимое при вложенности;
  * ПУЛЫ/РОЛЛЫ дифференцированы по типу таблицы: entity (дроп моба) -
    1-2 пула и rolls 1-2; chest - 3-6 пулов и rolls 1-6 (в среднем 2-4);
    таблицы сокровищ (характер treasure у chest-типа) - самые богатые
    (4-8 пулов, rolls 2-6); прочие - 2-5 пулов, rolls 1-6;
  * USE_REMAINDER: съедобный предмет (vanilla-еда или компонент food/
    consumable) с шансом 40-60% оставляет остаток: базовая посуда
    (миска у супов, бутылка у мёда), любой из пула остатков (bone,
    paper, candle, charcoal, feather, flint, string, leather,
    clay_ball, gold_nugget) или - с шансом 35% - КАСТОМНЫЙ именной
    остаток («Косточка от похлёбки», изредка с lore); count всегда 1
    (_STACK1; именной остаток в стае копий быть не может).

Публичные функции:

    rand_loot(rng, ns, name, count=None) -> {"loot_tables": {id: json, ...}}

    rng    - random.Random (весь рандом только через него);
    ns     - namespace ('rndim');
    name   - имя измерения (префикс id таблиц);
    count  - сколько таблиц создать (None -> 1-2).

    set_custom_enchants(ids)      - id кастомных зачарований измерения
                                     (подмешивает generate_dimension);
    set_ench_summaries(info)      - сведения о них: {id: описание} или
                                     {id: {"name", "desc", "passive",
                                     "supported_items"}}; без явного вызова
                                     модуль находит их сам - ленивым
                                     импортом gen_enchantments
                                     (LAST_ENCHANTMENTS в том же процессе).
                                     supported_items ("#тег"|id|[id,...]) -
                                     для проверки совместимости: предмет
                                     обязан входить в него, иначе зачарование
                                     ставится только на enchanted_book.

Вложенные loot_table-ссылки - только «вперёд» (на таблицы с бОльшим
номером) или на ванильные id: так рекурсия физически невозможна.
Файлы на диск модуль не пишет - возвращает dict.
"""

# (модуль math больше не нужен - «тяжёлый хвост» пулов убран вместе с
# жалобой на передоз роллов)

# ---------------------------------------------------------------------------
# Данные: предметы (все id подтверждены lang-файлом jar 26.2:
# assets/minecraft/lang/en_us.json, ключи item.minecraft.*)
# ---------------------------------------------------------------------------

_MATERIALS = ["wooden", "stone", "iron", "golden", "diamond", "netherite",
              "copper"]


def _tools(part, mats=_MATERIALS):
    return ["minecraft:%s_%s" % (m, part) for m in mats]


SWORDS = _tools("sword")
SPEARS = _tools("spear")
AXES = _tools("axe")
PICKAXES = _tools("pickaxe")
SHOVELS = _tools("shovel")
HOES = _tools("hoe")
BOWS = ["minecraft:bow"]
CROSSBOWS = ["minecraft:crossbow"]
TRIDENTS = ["minecraft:trident"]
MACES = ["minecraft:mace"]
SHIELDS = ["minecraft:shield"]
ELYTRA = ["minecraft:elytra"]

_HELMETS = _tools("helmet", ["leather", "chainmail", "iron", "golden",
                             "diamond", "netherite", "copper"]) + \
    ["minecraft:turtle_helmet"]
_CHESTPLATES = _tools("chestplate", ["leather", "chainmail", "iron",
                                     "golden", "diamond", "netherite",
                                     "copper"])
_LEGGINGS = _tools("leggings", ["leather", "chainmail", "iron", "golden",
                                "diamond", "netherite", "copper"])
_BOOTS = _tools("boots", ["leather", "chainmail", "iron", "golden",
                          "diamond", "netherite", "copper"])

# «конская броня» и прочие сокровища-без-экипировки (как в ванильных сундуках)
HORSE_ARMORS = ["minecraft:leather_horse_armor",
                "minecraft:iron_horse_armor",
                "minecraft:golden_horse_armor",
                "minecraft:diamond_horse_armor",
                "minecraft:copper_horse_armor",
                "minecraft:iron_nautilus_armor",
                "minecraft:golden_nautilus_armor",
                "minecraft:diamond_nautilus_armor",
                "minecraft:netherite_nautilus_armor",
                "minecraft:copper_nautilus_armor"]

WEAPONS = SWORDS + SPEARS + AXES + BOWS + CROSSBOWS + TRIDENTS + MACES
ARMOR = _HELMETS + _CHESTPLATES + _LEGGINGS + _BOOTS
TOOLS = PICKAXES + SHOVELS + HOES + ["minecraft:shears",
                                     "minecraft:flint_and_steel",
                                     "minecraft:fishing_rod",
                                     "minecraft:brush",
                                     "minecraft:carrot_on_a_stick"]

# Damageable-предметы: в дефолтных компонентах есть minecraft:max_damage.
# ВАЛИДАТОР 26.2 (ItemStack.validateComponents): max_stack_size > 1 у предмета
# с max_damage (дефолтным ИЛИ добавленным патчем) = «Item cannot be both
# damageable and stackable» - предмет вообще не создастся. Список получен
# ЭМПИРИЧЕСКИ: серверная проба 26.2 - все 1523 предмета реестра выданы
# через loot spawn с set_components {max_stack_size: 2, custom_data.probe};
# ровно эти 84 предмета упали с этой ошибкой (байткод Items ненадёжен -
# часть регистраций через лямбды). Обновлять при смене версии той же пробой.
_DAMAGEABLE = frozenset(
    WEAPONS + ARMOR + TOOLS + SHIELDS + ELYTRA + CROSSBOWS +
    ["minecraft:turtle_helmet", "minecraft:wolf_armor",
     "minecraft:warped_fungus_on_a_stick", "minecraft:trident"])

# еда (в т.ч. гнилая - для моб-столов)
FOOD = ["minecraft:bread", "minecraft:apple", "minecraft:golden_apple",
        "minecraft:enchanted_golden_apple", "minecraft:cooked_beef",
        "minecraft:cooked_porkchop", "minecraft:cooked_chicken",
        "minecraft:cooked_mutton", "minecraft:cooked_rabbit",
        "minecraft:cooked_cod", "minecraft:cooked_salmon",
        "minecraft:baked_potato", "minecraft:pumpkin_pie",
        "minecraft:cookie", "minecraft:melon_slice", "minecraft:carrot",
        "minecraft:beetroot", "minecraft:sweet_berries",
        "minecraft:glow_berries", "minecraft:dried_kelp",
        "minecraft:chorus_fruit", "minecraft:honey_bottle",
        "minecraft:mushroom_stew", "minecraft:beetroot_soup",
        "minecraft:rabbit_stew", "minecraft:suspicious_stew"]
RAW_FOOD = ["minecraft:beef", "minecraft:porkchop", "minecraft:chicken",
            "minecraft:mutton", "minecraft:rabbit", "minecraft:cod",
            "minecraft:salmon", "minecraft:pufferfish",
            "minecraft:tropical_fish", "minecraft:potato"]
BAD_FOOD = ["minecraft:rotten_flesh", "minecraft:spider_eye",
            "minecraft:poisonous_potato", "minecraft:fermented_spider_eye"]

# мусор
JUNK = ["minecraft:string", "minecraft:stick", "minecraft:bowl",
        "minecraft:glass_bottle", "minecraft:leather", "minecraft:paper",
        "minecraft:bone", "minecraft:bone_meal", "minecraft:feather",
        "minecraft:flint", "minecraft:egg", "minecraft:snowball",
        "minecraft:wheat_seeds", "minecraft:melon_seeds",
        "minecraft:pumpkin_seeds", "minecraft:beetroot_seeds",
        "minecraft:torchflower_seeds", "minecraft:pitcher_pod",
        "minecraft:sugar", "minecraft:wheat", "minecraft:clay_ball",
        "minecraft:brick", "minecraft:nether_brick", "minecraft:ink_sac",
        "minecraft:charcoal", "minecraft:disc_fragment_5",
        "minecraft:resin_clump", "minecraft:copper_nugget",
        "minecraft:gold_nugget", "minecraft:iron_nugget"]

# ресурсы (средняя ценность; tipped_arrow - ради potion_contents:
# зачарованные/зельевые стрелы - самостоятельный класс лута)
RESOURCES = ["minecraft:coal", "minecraft:iron_ingot", "minecraft:raw_iron",
             "minecraft:copper_ingot", "minecraft:raw_copper",
             "minecraft:gold_ingot", "minecraft:raw_gold",
             "minecraft:redstone", "minecraft:lapis_lazuli",
             "minecraft:quartz", "minecraft:amethyst_shard",
             "minecraft:glowstone_dust", "minecraft:gunpowder",
             "minecraft:slime_ball", "minecraft:blaze_powder",
             "minecraft:resin_brick", "minecraft:arrow",
             "minecraft:spectral_arrow", "minecraft:tipped_arrow",
             "minecraft:firework_rocket"]

# сокровища (включая ПУСТЫЕ КОНТЕЙНЕРЫ-сокровищницы: сундук/шалкер/
# медный сундук - им достанется container/container_loot/lock с нашими
# тематическими заливками; шалкеры - стек-1, см. _STACK1)
VALUABLES = ["minecraft:diamond", "minecraft:emerald",
             "minecraft:netherite_scrap", "minecraft:netherite_ingot",
             "minecraft:echo_shard", "minecraft:nether_star",
             "minecraft:heart_of_the_sea", "minecraft:nautilus_shell",
             "minecraft:shulker_shell", "minecraft:phantom_membrane",
             "minecraft:totem_of_undying", "minecraft:dragon_breath",
             "minecraft:ender_pearl", "minecraft:ender_eye",
             "minecraft:ghast_tear", "minecraft:breeze_rod",
             "minecraft:blaze_rod", "minecraft:experience_bottle",
             "minecraft:saddle", "minecraft:name_tag", "minecraft:lead",
             "minecraft:golden_carrot", "minecraft:glistering_melon_slice",
             "minecraft:magma_cream", "minecraft:rabbit_foot",
             "minecraft:trial_key", "minecraft:ominous_trial_key",
             "minecraft:ominous_bottle", "minecraft:blue_egg",
             "minecraft:shulker_box", "minecraft:chest",
             "minecraft:barrel", "minecraft:decorated_pot",
             "minecraft:copper_chest"] + HORSE_ARMORS

MUSIC_DISCS = ["minecraft:music_disc_13", "minecraft:music_disc_cat",
               "minecraft:music_disc_blocks", "minecraft:music_disc_chirp",
               "minecraft:music_disc_far", "minecraft:music_disc_mall",
               "minecraft:music_disc_mellohi", "minecraft:music_disc_stal",
               "minecraft:music_disc_strad", "minecraft:music_disc_ward",
               "minecraft:music_disc_11", "minecraft:music_disc_wait",
               "minecraft:music_disc_otherside",
               "minecraft:music_disc_pigstep", "minecraft:music_disc_relic",
               "minecraft:music_disc_5", "minecraft:music_disc_creator",
               "minecraft:music_disc_creator_music_box",
               "minecraft:music_disc_precipice", "minecraft:music_disc_tears",
               "minecraft:music_disc_bounce",
               "minecraft:music_disc_lava_chicken"]

POTIONS = ["minecraft:potion", "minecraft:splash_potion",
           "minecraft:lingering_potion"]
BOOKS = ["minecraft:book", "minecraft:writable_book"]
ENCH_BOOKS = ["minecraft:enchanted_book"]

# id зелий - реестр Potions.class 26.2 (strong_/long_ вариантов больше нет)
POTIONS_IDS = ["water", "mundane", "thick", "awkward", "night_vision",
               "invisibility", "leaping", "fire_resistance", "swiftness",
               "slowness", "turtle_master", "water_breathing", "healing",
               "harming", "poison", "regeneration", "strength", "weakness",
               "luck", "slow_falling", "wind_charged",
               "weaving", "oozing", "infested"]

SMITHING_TEMPLATES = [
    "minecraft:netherite_upgrade_smithing_template",
    "minecraft:sentry_armor_trim_smithing_template",
    "minecraft:dune_armor_trim_smithing_template",
    "minecraft:coast_armor_trim_smithing_template",
    "minecraft:wild_armor_trim_smithing_template",
    "minecraft:ward_armor_trim_smithing_template",
    "minecraft:eye_armor_trim_smithing_template",
    "minecraft:vex_armor_trim_smithing_template",
    "minecraft:tide_armor_trim_smithing_template",
    "minecraft:snout_armor_trim_smithing_template",
    "minecraft:rib_armor_trim_smithing_template",
    "minecraft:host_armor_trim_smithing_template",
    "minecraft:raiser_armor_trim_smithing_template",
    "minecraft:shaper_armor_trim_smithing_template",
    "minecraft:silence_armor_trim_smithing_template",
    "minecraft:spire_armor_trim_smithing_template",
    "minecraft:wayfinder_armor_trim_smithing_template",
    "minecraft:bolt_armor_trim_smithing_template",
    "minecraft:flow_armor_trim_smithing_template"]

POTTERY_SHERDS = ["minecraft:angler_pottery_sherd",
                  "minecraft:archer_pottery_sherd",
                  "minecraft:arms_up_pottery_sherd",
                  "minecraft:blade_pottery_sherd",
                  "minecraft:brewer_pottery_sherd",
                  "minecraft:burn_pottery_sherd",
                  "minecraft:danger_pottery_sherd",
                  "minecraft:explorer_pottery_sherd",
                  "minecraft:friend_pottery_sherd",
                  "minecraft:heart_pottery_sherd",
                  "minecraft:heartbreak_pottery_sherd",
                  "minecraft:howl_pottery_sherd",
                  "minecraft:miner_pottery_sherd",
                  "minecraft:mourner_pottery_sherd",
                  "minecraft:plenty_pottery_sherd",
                  "minecraft:prize_pottery_sherd",
                  "minecraft:scrape_pottery_sherd",
                  "minecraft:shelter_pottery_sherd",
                  "minecraft:skull_pottery_sherd"]

MISC = ["minecraft:compass", "minecraft:clock", "minecraft:spyglass",
        "minecraft:recovery_compass",
        "minecraft:bucket", "minecraft:water_bucket",
        "minecraft:powder_snow_bucket", "minecraft:lava_bucket",
        "minecraft:milk_bucket", "minecraft:bundle", "minecraft:goat_horn",
        "minecraft:wolf_armor", "minecraft:map",
        "minecraft:filled_map", "minecraft:painting",
        "minecraft:decorated_pot", "minecraft:firework_star",
        "minecraft:sulfur_cube_bucket"]
# голого minecraft:harness НЕТ в реестре item 26.2 (только цветные
# *_harness) - «Unknown registry key in minecraft:item» на загрузке пака

# ванильные таблицы для вложенных loot_table-записей (все id из jar)
VANILLA_TABLES = [
    "minecraft:chests/simple_dungeon",
    "minecraft:chests/abandoned_mineshaft",
    "minecraft:chests/desert_pyramid",
    "minecraft:chests/jungle_temple",
    "minecraft:chests/stronghold_library",
    "minecraft:chests/stronghold_crossing",
    "minecraft:chests/stronghold_corridor",
    "minecraft:chests/woodland_mansion",
    "minecraft:chests/nether_bridge",
    "minecraft:chests/buried_treasure",
    "minecraft:chests/end_city_treasure",
    "minecraft:chests/ancient_city",
    "minecraft:chests/ancient_city_ice_box",
    "minecraft:chests/bastion_bridge",
    "minecraft:chests/bastion_hoglin_stable",
    "minecraft:chests/bastion_other",
    "minecraft:chests/bastion_treasure",
    "minecraft:chests/ruined_portal",
    "minecraft:chests/pillager_outpost",
    "minecraft:chests/igloo_chest",
    "minecraft:chests/shipwreck_treasure",
    "minecraft:chests/shipwreck_supply",
    "minecraft:chests/underwater_ruin_big",
    "minecraft:chests/underwater_ruin_small",
    "minecraft:chests/spawn_bonus_chest",
    "minecraft:chests/village/village_weaponsmith",
    "minecraft:chests/village/village_armorer",
    "minecraft:chests/village/village_toolsmith",
    "minecraft:chests/village/village_fletcher",
    "minecraft:chests/village/village_temple",
    "minecraft:chests/village/village_desert_house",
    "minecraft:chests/village/village_plains_house",
    "minecraft:chests/village/village_snowy_house",
    "minecraft:chests/village/village_taiga_house",
    "minecraft:chests/village/village_savanna_house",
    "minecraft:chests/trial_chambers/reward",
    "minecraft:chests/trial_chambers/supply",
    "minecraft:chests/trial_chambers/corridor",
    "minecraft:chests/trial_chambers/entrance",
    "minecraft:gameplay/fishing",
    "minecraft:gameplay/fishing/fish",
    "minecraft:gameplay/fishing/junk",
    "minecraft:gameplay/fishing/treasure",
    "minecraft:gameplay/piglin_bartering",
    "minecraft:gameplay/sniffer_digging",
    "minecraft:gameplay/cat_morning_gift",
    "minecraft:gameplay/hero_of_the_village/weaponsmith_gift",
    "minecraft:gameplay/hero_of_the_village/farmer_gift",
    "minecraft:gameplay/hero_of_the_village/librarian_gift",
]

# теги предметов для tag-записей - все есть в data/minecraft/tags/item/ 26.2
ITEM_TAGS = [
    "minecraft:planks", "minecraft:logs", "minecraft:flowers",
    "minecraft:small_flowers", "minecraft:wool", "minecraft:wool_carpets",
    "minecraft:candles", "minecraft:arrows", "minecraft:dyes",
    "minecraft:coals", "minecraft:fishes", "minecraft:saplings",
    "minecraft:leaves", "minecraft:stone_bricks", "minecraft:terracotta",
    "minecraft:glazed_terracotta", "minecraft:concrete", "minecraft:fences",
    "minecraft:doors", "minecraft:trapdoors", "minecraft:buttons",
    "minecraft:rails", "minecraft:slabs", "minecraft:stairs",
    "minecraft:walls", "minecraft:boats", "minecraft:chest_boats",
    "minecraft:banners", "minecraft:signs", "minecraft:hanging_signs",
    "minecraft:lanterns", "minecraft:skulls", "minecraft:swords",
    "minecraft:pickaxes", "minecraft:axes", "minecraft:shovels",
    "minecraft:hoes", "minecraft:spears", "minecraft:trimmable_armor",
    "minecraft:copper_ores", "minecraft:iron_ores", "minecraft:gold_ores",
    "minecraft:diamond_ores", "minecraft:coal_ores",
    "minecraft:redstone_ores", "minecraft:lapis_ores",
    "minecraft:creeper_drop_music_discs", "minecraft:smelts_to_glass",
    "minecraft:dampens_vibrations", "minecraft:piglin_loved",
]

# ---------------------------------------------------------------------------
# Зачарования: id -> (max_level по jar, ТОЧНЫЙ набор предметов).
# Набор = содержимое supported_items зачарования из jar 26.2
# (data/minecraft/enchantment/*.json), развёрнутое через теги
# #minecraft:enchantable/* (карты тегов - см. ENCH_TAG_ITEMS ниже):
#   sharpness = sharp_weapon (мечи/копья/топоры), knockback/looting =
#   melee_weapon (ТОЛЬКО мечи/копья), fire_aspect = без топоров и т.д.
# Инвариант самотеста: ванильное зачарование ставится на предмет
# только если предмет ? набору (sharpness не на кирке, protection
# не на мече); enchanted_book - исключение-носитель.
# ---------------------------------------------------------------------------

# кастомные зачарования текущего измерения (id "ns:name_enchN") - их
# подмешивает generate_dimension.py перед вызовом rand_loot
CUSTOM_ENCHS = []

# ЯВНЫЕ сведения о кастомных зачарованиях: {id: {"name", "desc",
# "passive", "slots"}} - задаёт set_ench_summaries (образец -
# set_custom_enchants). Без явного вызова gen_loot строит их сам:
# ленивым импортом gen_enchantments (в одном процессе generate_dimension
# вызывает rand_enchantments ДО rand_loot, и последний результат лежит
# в gen_enchantments.LAST_ENCHANTMENTS).
ENCH_SUMMARIES = {}
# Atomic explicit snapshot from the dimension generator; None retains the
# standalone module's legacy LAST_* discovery, {} means explicitly no data.
ENCH_CONTEXT = None


def set_enchantment_context(enchantments, function_metadata):
    """Pass the exact world snapshot; metadata remains Python-side, never JSON."""
    global ENCH_CONTEXT
    ENCH_CONTEXT = (dict(enchantments or {}), dict(function_metadata or {}))


# рабочий кэш сведений (имя + описание + пассивность + слоты) - строится
# заново при каждом rand_loot слиянием явных ENCH_SUMMARIES и найденного
_ENCH_INFO = {}


def set_custom_enchants(ids):
    """Задать кастомные зачарования измерения для последующей генерации
    лута (связка лут ? зачарования). Вызывать до rand_loot."""
    global CUSTOM_ENCHS, ENCH_CONTEXT
    CUSTOM_ENCHS = [i for i in (ids or []) if i]
    ENCH_CONTEXT = None  # new ID set invalidates the old explicit snapshot


def set_ench_summaries(info):
    """Задать краткие сведения о кастомных зачарованиях измерения
    (по образцу set_custom_enchants; вызывать до rand_loot).

    info - {id: описание-строка} или {id: {"name": имя зачарования,
    "desc": описание действия (до 8 слов), "passive": bool (действует
    при ношении/удержании), "slots": [слоты], "supported_items":
    "#тег" | id | [id, ...] - те же формы, что в JSON зачарования
    (26.2 HolderSet<Item>); без supported_items зачарование ставится
    только на enchanted_book-носители - безопасный отказ)}. Служит для
    lore-подсказок «Имя - описание действия», фикса «предмет только с
    визуалом» и ПРОВЕРКИ СОВМЕСТИМОСТИ (предмет ? supported_items).
    Ключи name/desc/passive/slots/supported_items необязательны; явные
    сведения перекрывают автопоиск по gen_enchantments.LAST_ENCHANTMENTS,
    кроме desc для известных сгенерированных command families: достоверный
    COMMAND_FAMILIES / LAST_FUNCTION_METADATA имеет приоритет."""
    global ENCH_SUMMARIES
    ENCH_SUMMARIES = {}
    for k, v in (info or {}).items():
        if not k:
            continue
        if isinstance(v, dict):
            ENCH_SUMMARIES[k] = {
                "name": str(v.get("name") or ""),
                "desc": str(v.get("desc") or ""),
                "passive": bool(v.get("passive")),
                "slots": [s for s in (v.get("slots") or []) if s],
                "supported_items": v.get("supported_items")}
        else:
            ENCH_SUMMARIES[k] = {"name": "", "desc": str(v),
                                 "passive": False, "slots": [],
                                 "supported_items": None}


def _build_ench_info():
    """{id: {"name","desc","passive","slots","support"}} по CUSTOM_ENCHS:
    явные ENCH_SUMMARIES + автопоиск по gen_enchantments.
    LAST_ENCHANTMENTS (name = description.text, desc =
    summarize_enchantment, passive - passive_enchants, slots - поле slots
    зачарования, support - разобранный supported_items, см.
    _resolve_supported). Автопоиск молчит, если gen_enchantments
    недоступен или ничего не генерировал - тогда работают только явные
    set_ench_summaries."""
    info = {}
    try:
        import gen_enchantments as _ge
        if ENCH_CONTEXT is None:
            last = getattr(_ge, "LAST_ENCHANTMENTS", None) or {}
            command_meta = getattr(_ge, "LAST_FUNCTION_METADATA", {})
        else:
            last, command_meta = ENCH_CONTEXT
        passive = set(getattr(_ge, "passive_enchants", lambda d: [])(last))
        summ = getattr(_ge, "summarize_enchantment", None)
        command_lore = getattr(_ge, "command_family_lore", None)
        for eid in CUSTOM_ENCHS:
            ejson = last.get(eid)
            if not isinstance(ejson, dict):
                continue
            name = ""
            d = ejson.get("description")
            if isinstance(d, dict) and d.get("text"):
                name = str(d["text"])
            desc = ""
            if summ is not None:
                try:
                    desc = str(summ(ejson) or "")
                except Exception:
                    desc = ""
            # Authoritative structured metadata, not guesses from names or
            # mcfunction substring parsing. @s is the affected entity, not
            # necessarily the bearer/player. Native summary remains fallback.
            meta = command_meta.get(eid)
            if meta and command_lore:
                native = _ge.summarize_native_enchantment(ejson)
                desc = ". ".join(part for part in (native, command_lore(meta)) if part)
            info[eid] = {"name": name, "desc": desc,
                         "command_families": list(meta["families"]) if meta else [],
                         "passive": eid in passive,
                         "slots": [s for s in (ejson.get("slots") or [])
                                   if isinstance(s, str)],
                         "support": _resolve_supported(
                             ejson.get("supported_items"))}
    except ImportError:
        pass
    # явные сведения сильнее автопоиска (по ключам; только непустые
    # значения - строковый API {id: описание} не должен гасить
    # автонайденные passive/имя/support; поддержа из явного API
    # используется, только если автопоиск её не нашёл)
    for eid, v in ENCH_SUMMARIES.items():
        base = info.get(eid, {"name": "", "desc": "",
                              "passive": False, "slots": [],
                              "support": None})
        for k in ("name", "desc", "passive", "slots"):
            # Generated family metadata wins over stale generic "ritual"
            # descriptions; explicit summaries still work for external enchants.
            if k == "desc" and base.get("command_families"):
                continue
            if v.get(k):
                base[k] = v[k]
        if base.get("support") is None and v.get("supported_items") \
                is not None:
            base["support"] = _resolve_supported(v["supported_items"])
        info[eid] = base
    return info

# ---------------------------------------------------------------------------
# СОВМЕСТИМОСТЬ ЗАЧАРОВАНИЙ С ПРЕДМЕТАМИ (жалоба: «не надо мечу давать
# защиту - его нельзя экипировать»). Всё захардкожено из jar 26.2:
#   * data/minecraft/tags/item/enchantable/*.json - 22 тега (внутри -
#     вложенные #minecraft:swords/#minecraft:chest_armor/...);
#   * data/minecraft/tags/item/{swords,pickaxes,axes,shovels,hoes,
#     spears,chest_armor,leg_armor,head_armor,foot_armor,skulls,
#     breaks_decorated_pots}.json - простые теги;
#   * data/minecraft/enchantment/*.json - supported_items каждого
#     ванильного зачарования (см. ENCHANTS ниже).
# gen_enchantments использует в supported_items только "#minecraft:
# enchantable/*", "#minecraft:{swords,pickaxes,axes,shovels,hoes,
# breaks_decorated_pots}", одиночные id и списки id - всё покрыто.
# ---------------------------------------------------------------------------

_SKULL_ITEMS = frozenset([
    "minecraft:player_head", "minecraft:creeper_head",
    "minecraft:zombie_head", "minecraft:skeleton_skull",
    "minecraft:wither_skeleton_skull", "minecraft:dragon_head",
    "minecraft:piglin_head"])

# тег -> предметы (jar 26.2, посимвольно)
_TAG_SWORDS = frozenset(SWORDS)
_TAG_SPEARS = frozenset(SPEARS)
_TAG_AXES = frozenset(AXES)
_TAG_PICKAXES = frozenset(PICKAXES)
_TAG_SHOVELS = frozenset(SHOVELS)
_TAG_HOES = frozenset(HOES)
_TAG_MACES = frozenset(MACES)
_TAG_BOWS = frozenset(BOWS)
_TAG_CROSSBOWS = frozenset(CROSSBOWS)
_TAG_TRIDENTS = frozenset(TRIDENTS)
_TAG_FISHING = frozenset(["minecraft:fishing_rod"])
_TAG_HEAD = frozenset(_HELMETS)            # + turtle_helmet
_TAG_CHEST = frozenset(_CHESTPLATES)
_TAG_LEG = frozenset(_LEGGINGS)
_TAG_FOOT = frozenset(_BOOTS)
_TAG_ARMOR = _TAG_HEAD | _TAG_CHEST | _TAG_LEG | _TAG_FOOT
_TAG_MELEE = _TAG_SWORDS | _TAG_SPEARS            # enchantable/melee_weapon
_TAG_SHARP = _TAG_MELEE | _TAG_AXES               # enchantable/sharp_weapon
_TAG_WEAPON = _TAG_SHARP | _TAG_MACES             # enchantable/weapon
_TAG_FIRE = _TAG_MELEE | _TAG_MACES               # enchantable/fire_aspect
_TAG_DURABILITY = _TAG_ARMOR | frozenset(
    ELYTRA + SHIELDS + SWORDS + AXES + PICKAXES + SHOVELS + HOES + BOWS
    + CROSSBOWS + TRIDENTS + MACES + SPEARS + [
        "minecraft:flint_and_steel", "minecraft:shears",
        "minecraft:brush", "minecraft:fishing_rod",
        "minecraft:carrot_on_a_stick",
        "minecraft:warped_fungus_on_a_stick"])
_TAG_EQUIPPABLE = _TAG_ARMOR | frozenset(ELYTRA) | _SKULL_ITEMS | frozenset(
    ["minecraft:carved_pumpkin"])
_TAG_VANISHING = _TAG_DURABILITY | _SKULL_ITEMS | frozenset(
    ["minecraft:compass", "minecraft:carved_pumpkin"])
_TAG_MINING = _TAG_AXES | _TAG_PICKAXES | _TAG_SHOVELS | _TAG_HOES | \
    frozenset(["minecraft:shears"])
_TAG_MINING_LOOT = _TAG_AXES | _TAG_PICKAXES | _TAG_SHOVELS | _TAG_HOES

# карта ВСЕХ тегов, которые gen_enchantments может поставить в
# supported_items ("#...") - незнакомый тег = зачарование не ставим
ENCH_TAG_ITEMS = {
    "#minecraft:enchantable/melee_weapon": _TAG_MELEE,
    "#minecraft:enchantable/sharp_weapon": _TAG_SHARP,
    "#minecraft:enchantable/weapon": _TAG_WEAPON,
    "#minecraft:enchantable/mace": _TAG_MACES,
    "#minecraft:enchantable/fire_aspect": _TAG_FIRE,
    "#minecraft:enchantable/sweeping": _TAG_SWORDS,
    "#minecraft:enchantable/lunge": _TAG_SPEARS,
    "#minecraft:enchantable/armor": _TAG_ARMOR,
    "#minecraft:enchantable/head_armor": _TAG_HEAD,
    "#minecraft:enchantable/chest_armor": _TAG_CHEST,
    "#minecraft:enchantable/leg_armor": _TAG_LEG,
    "#minecraft:enchantable/foot_armor": _TAG_FOOT,
    "#minecraft:enchantable/bow": _TAG_BOWS,
    "#minecraft:enchantable/crossbow": _TAG_CROSSBOWS,
    "#minecraft:enchantable/trident": _TAG_TRIDENTS,
    "#minecraft:enchantable/fishing": _TAG_FISHING,
    "#minecraft:enchantable/mining": _TAG_MINING,
    "#minecraft:enchantable/mining_loot": _TAG_MINING_LOOT,
    "#minecraft:enchantable/durability": _TAG_DURABILITY,
    "#minecraft:enchantable/equippable": _TAG_EQUIPPABLE,
    "#minecraft:enchantable/vanishing": _TAG_VANISHING,
    "#minecraft:swords": _TAG_SWORDS,
    "#minecraft:spears": _TAG_SPEARS,
    "#minecraft:axes": _TAG_AXES,
    "#minecraft:pickaxes": _TAG_PICKAXES,
    "#minecraft:shovels": _TAG_SHOVELS,
    "#minecraft:hoes": _TAG_HOES,
    "#minecraft:skulls": _SKULL_ITEMS,
    "#minecraft:chest_armor": _TAG_CHEST,
    "#minecraft:leg_armor": _TAG_LEG,
    "#minecraft:head_armor": _TAG_HEAD,
    "#minecraft:foot_armor": _TAG_FOOT,
    "#minecraft:breaks_decorated_pots": (
        _TAG_SWORDS | _TAG_AXES | _TAG_PICKAXES | _TAG_SHOVELS | _TAG_HOES
        | _TAG_TRIDENTS | _TAG_MACES),
}


def _resolve_supported(sup):
    """supported_items зачарования -> frozenset предметов ИЛИ None
    (неразрешимо: незнакомый тег/мусор - тогда зачарование на предметы
    НЕ ставим: гарантия валидности важнее щедрости).
    Формат 26.2 (HolderSet<Item>): "#тег" | "id" | [id, ...] - внутри
    списка тегов НЕ бывает (проверено gen_enchantments'ом и сервером)."""
    if isinstance(sup, str):
        if sup.startswith("#"):
            return ENCH_TAG_ITEMS.get(sup)
        return frozenset([sup])
    if isinstance(sup, list) and sup:
        ids = frozenset(x for x in sup
                        if isinstance(x, str) and not x.startswith("#"))
        return ids or None
    return None


def _custom_ench_ok(eid, item):
    """Можно ли поставить кастомное зачарование измерения на предмет:
    предмет обязан входить в supported_items зачарования (кэш _ENCH_INFO,
    поле support). Книги-носители (enchanted_book) - всегда да: чары
    применятся наковальней лишь к совместимому. Нет сведений/тег не
    разрешён - НЕТ (безопасный отказ)."""
    if item in ENCH_BOOKS:
        return True
    info = _ENCH_INFO.get(eid)
    if not info:
        return False
    sup = info.get("support")
    return bool(sup) and item in sup

ENCHANTS = {
    # прочность (вся экипировка и инструменты; vanishing шире - черепа,
    # компас, тыква) - сверен с supported_items каждого зачарования
    # в jar 26.2 (data/minecraft/enchantment/*.json)
    "unbreaking":      (3, _TAG_DURABILITY),
    "mending":         (1, _TAG_DURABILITY),
    "vanishing_curse": (1, _TAG_VANISHING),
    # броня (binding_curse - equippable: и черепа/тыква/элитры)
    "protection":            (4, _TAG_ARMOR),
    "fire_protection":       (4, _TAG_ARMOR),
    "blast_protection":      (4, _TAG_ARMOR),
    "projectile_protection": (4, _TAG_ARMOR),
    "thorns":                (3, _TAG_ARMOR),
    "binding_curse":         (1, _TAG_EQUIPPABLE),
    "respiration":           (3, _TAG_HEAD),
    "aqua_affinity":         (1, _TAG_HEAD),
    "swift_sneak":           (3, _TAG_LEG),
    "feather_falling":       (4, _TAG_FOOT),
    "depth_strider":         (3, _TAG_FOOT),
    "frost_walker":          (2, _TAG_FOOT),
    "soul_speed":            (3, _TAG_FOOT),
    # ближний бой: sharpness - sharp_weapon (мечи/копья/ТОПОРЫ),
    # smite/bane - weapon (+ булава), knockback/looting - ТОЛЬКО
    # melee_weapon (мечи/копья, НЕ топоры), fire_aspect - без топоров,
    # sweeping - только мечи, lunge - только копья (всё по jar!)
    "sharpness":          (5, _TAG_SHARP),
    "smite":              (5, _TAG_WEAPON),
    "bane_of_arthropods": (5, _TAG_WEAPON),
    "knockback":          (2, _TAG_MELEE),
    "looting":            (3, _TAG_MELEE),
    "fire_aspect":        (2, _TAG_FIRE),
    "sweeping_edge":      (3, _TAG_SWORDS),
    "lunge":              (3, _TAG_SPEARS),
    # булава
    "density":    (5, _TAG_MACES),
    "breach":     (4, _TAG_MACES),
    "wind_burst": (3, _TAG_MACES),
    # добыча (efficiency - и ножницы; fortune/silk - без них)
    "efficiency": (5, _TAG_MINING),
    "fortune":    (3, _TAG_MINING_LOOT),
    "silk_touch": (1, _TAG_MINING_LOOT),
    # дальний бой
    "power":        (5, _TAG_BOWS),
    "punch":        (2, _TAG_BOWS),
    "flame":        (1, _TAG_BOWS),
    "infinity":     (1, _TAG_BOWS),
    "multishot":    (1, _TAG_CROSSBOWS),
    "quick_charge": (3, _TAG_CROSSBOWS),
    "piercing":     (4, _TAG_CROSSBOWS),
    # трезубец / удочка
    "impaling":       (5, _TAG_TRIDENTS),
    "loyalty":        (3, _TAG_TRIDENTS),
    "riptide":        (3, _TAG_TRIDENTS),
    "channeling":     (1, _TAG_TRIDENTS),
    "luck_of_the_sea": (3, _TAG_FISHING),
    "lure":            (3, _TAG_FISHING),
}

# ПРОВЕРКА СОВМЕСТИМОСТИ: id зачарования -> предмет поддерживается?
# (кники-носители - исключение, см. _enchantments_map: enchanted_book
# хранит любые зачарования, наковальня применит лишь совместимые)
def _ench_supports(ench, item):
    """Валидно ли ванильное зачарование `ench` (без префикса) для
    предмета - по точным supported_items из jar 26.2 (ENCHANTS)."""
    spec = ENCHANTS.get(str(ench).split(":")[-1])
    return spec is not None and item in spec[1]

# ---------------------------------------------------------------------------
# Атрибуты: id -> (мин, макс). Имена подтверждены Attributes.class 26.2
# (префикса generic. больше нет). Величины - с разумными пределами.
# ---------------------------------------------------------------------------

ATTRIBUTES = [
    # (id, lo, mid, peak, can_neg, neg_mid, neg_peak)
    # Здоровье и атака
    ("minecraft:max_health", 1.0, 4.0, 14.0, True, 2.0, 6.0),
    ("minecraft:max_absorption", 1.0, 3.0, 8.0, False, 0.0, 0.0),
    ("minecraft:attack_damage", 1.0, 3.0, 10.0, True, 1.5, 4.0),
    ("minecraft:attack_speed", 0.1, 0.4, 1.2, True, 0.2, 0.6),
    ("minecraft:attack_knockback", 0.3, 0.8, 2.2, False, 0.0, 0.0),
    ("minecraft:sweeping_damage_ratio", 0.1, 0.3, 0.8, False, 0.0, 0.0),

    # Защита и броня (не могут быть отрицательными - клампятся в 0)
    ("minecraft:armor", 1.0, 3.0, 8.0, False, 0.0, 0.0),
    ("minecraft:armor_toughness", 1.0, 2.0, 5.0, False, 0.0, 0.0),
    ("minecraft:knockback_resistance", 0.05, 0.12, 0.35, False, 0.0, 0.0),
    ("minecraft:explosion_knockback_resistance", 0.05, 0.15, 0.40, False, 0.0, 0.0),

    # Движение и мобильность
    ("minecraft:movement_speed", 0.005, 0.020, 0.065, True, 0.015, 0.035),
    ("minecraft:flying_speed", 0.005, 0.015, 0.045, False, 0.0, 0.0),
    ("minecraft:jump_strength", 0.02, 0.07, 0.22, False, 0.0, 0.0),
    ("minecraft:step_height", 0.2, 0.5, 1.2, False, 0.0, 0.0),
    ("minecraft:sneaking_speed", 0.03, 0.08, 0.25, False, 0.0, 0.0),
    ("minecraft:movement_efficiency", 0.1, 0.3, 0.8, False, 0.0, 0.0),
    ("minecraft:water_movement_efficiency", 0.1, 0.3, 0.8, False, 0.0, 0.0),
    ("minecraft:bounciness", 0.1, 0.3, 0.8, False, 0.0, 0.0),

    # Физика, размер и гравитация
    ("minecraft:scale", 0.1, 0.3, 0.8, True, 0.2, 0.5),
    ("minecraft:gravity", 0.01, 0.025, 0.06, True, 0.025, 0.06),
    ("minecraft:fall_damage_multiplier", 0.05, 0.20, 0.50, True, 0.15, 0.40),

    # Инструменты и добыча
    ("minecraft:block_break_speed", 0.1, 0.35, 1.2, False, 0.0, 0.0),
    ("minecraft:mining_efficiency", 0.5, 1.5, 4.0, False, 0.0, 0.0),
    ("minecraft:submerged_mining_speed", 0.1, 0.4, 1.0, False, 0.0, 0.0),
    ("minecraft:block_interaction_range", 0.5, 1.0, 2.5, True, 0.5, 1.2),
    ("minecraft:entity_interaction_range", 0.5, 0.8, 2.0, True, 0.5, 1.0),

    # Полезности и выживание
    ("minecraft:safe_fall_distance", 1.0, 3.0, 10.0, False, 0.0, 0.0),
    ("minecraft:oxygen_bonus", 1.0, 2.0, 6.0, False, 0.0, 0.0),
    ("minecraft:luck", 1.0, 2.0, 5.0, True, 1.0, 3.0),
    ("minecraft:burning_time", 0.1, 0.25, 0.6, True, 0.2, 0.5),
]

_KIND_SLOTS = {
    "sword": "mainhand", "spear": "mainhand", "axe": "mainhand",
    "mace": "mainhand", "pickaxe": "mainhand", "shovel": "mainhand",
    "hoe": "mainhand", "bow": "mainhand", "crossbow": "mainhand",
    "trident": "mainhand", "fishing_rod": "mainhand",
    "helmet": "head", "chestplate": "chest", "leggings": "legs",
    "boots": "feet", "elytra": "chest", "shield": "offhand",
    "book": "any",
}

# слоты для «диких» модификаторов на НЕоружии (EquipmentSlotGroup 26.2):
# offhand оставлен только «рукастым» диковинам - атакующие атрибуты
# оружия работают лишь в mainhand
_HAND_SLOTS_MAIN = ["mainhand", "hand", "any"]
_HAND_SLOTS_ANY = ["mainhand", "offhand", "hand", "any"]

# ---------------------------------------------------------------------------
# ВАНИЛЬНЫЕ БАЗОВЫЕ АТРИБУТЫ (жалоба: «получил поножи с бонусом к
# кислороду, но БЕЗ атрибутов брони вообще»). Механика 26.2: компонент
# attribute_modifiers ЗАМЕНЯЕТ дефолтные модификаторы предмета ЦЕЛИКОМ,
# поэтому при генерации собственных модификаторов ванильные дефолты
# ВСЕГДА включаются В НАЧАЛО списка - «не урезать, а ДОПОЛНИТЬ».
#
# ИСТОЧНИК ЗНАЧЕНИЙ: регистрации Items в jar 26.2
# (minecraft-26.2-client.jar, net/minecraft/world/item/Items.class -
# Item.Properties.attributes(...) / SwordItem.createAttributes(...) /
# AxeItem/HoeItem/PickaxeItem/ShovelItem/MaceItem; броня - ArmorItem
# ArmorMaterial: очки брони по (материал, слот), armor_toughness по
# материалу, нэзерит дополнительно knockback_resistance 0.1 на часть).
# amount = ИТОГОВОЕ значение ? база игрока: attack_damage база 1
# (алмазный меч 7 урона -> модификатор +6), attack_speed база 4.0
# (меч 1.6 -> ?2.4). Медь (Copper Age, 26.x) - промеждуточный тир между
# stone и iron (урон меча 5, броня 2/5/4/2); копьё (26.x) - копейное
# оружие: урон «меч + 1», скорость 1.0. Таблица захардкожена - при
# смене версии переписать по новому jar.
# ---------------------------------------------------------------------------

# оружие/инструменты: item -> (attack_damage, attack_speed);
# None = ванильного модификатора нет (мотыги бьют на базу игрока,
# алмазная/нэзеритовая мотыга имеет скорость 4.0 = базу)
_BASE_TOOL_ATTRS = {
    # мечи (итог 4/5/6/4/7/8 урона, медь 5; скорость 1.6)
    "minecraft:wooden_sword": (3, -2.4),
    "minecraft:stone_sword": (4, -2.4),
    "minecraft:iron_sword": (5, -2.4),
    "minecraft:golden_sword": (3, -2.4),
    "minecraft:diamond_sword": (6, -2.4),
    "minecraft:netherite_sword": (7, -2.4),
    "minecraft:copper_sword": (4, -2.4),
    # копья (итог 5/6/7/5/8/9, медь 6; скорость 1.0)
    "minecraft:wooden_spear": (4, -3.0),
    "minecraft:stone_spear": (5, -3.0),
    "minecraft:iron_spear": (6, -3.0),
    "minecraft:golden_spear": (4, -3.0),
    "minecraft:diamond_spear": (7, -3.0),
    "minecraft:netherite_spear": (8, -3.0),
    "minecraft:copper_spear": (5, -3.0),
    # топоры (итог 7/9/9/7/9/10, медь 8; скорость 0.8-1.0)
    "minecraft:wooden_axe": (6, -3.2),
    "minecraft:stone_axe": (8, -3.2),
    "minecraft:iron_axe": (8, -3.1),
    "minecraft:golden_axe": (6, -3.0),
    "minecraft:diamond_axe": (8, -3.0),
    "minecraft:netherite_axe": (9, -3.0),
    "minecraft:copper_axe": (7, -3.1),
    # кирки (итог 2/3/4/2/5/6, медь 3; скорость 1.2)
    "minecraft:wooden_pickaxe": (1, -2.8),
    "minecraft:stone_pickaxe": (2, -2.8),
    "minecraft:iron_pickaxe": (3, -2.8),
    "minecraft:golden_pickaxe": (1, -2.8),
    "minecraft:diamond_pickaxe": (4, -2.8),
    "minecraft:netherite_pickaxe": (5, -2.8),
    "minecraft:copper_pickaxe": (2, -2.8),
    # лопаты (итог 2.5/3.5/4.5/2.5/5.5/6.5, медь 3.5; скорость 1.0)
    "minecraft:wooden_shovel": (1.5, -3.0),
    "minecraft:stone_shovel": (2.5, -3.0),
    "minecraft:iron_shovel": (3.5, -3.0),
    "minecraft:golden_shovel": (1.5, -3.0),
    "minecraft:diamond_shovel": (4.5, -3.0),
    "minecraft:netherite_shovel": (5.5, -3.0),
    "minecraft:copper_shovel": (2.5, -3.0),
    # мотыги (урон = база игрока 1 - модификатора урона нет;
    # скорость растёт с тиром: 1/2/3/1/4/4, медь 2)
    "minecraft:wooden_hoe": (None, -3.0),
    "minecraft:stone_hoe": (None, -2.0),
    "minecraft:iron_hoe": (None, -1.0),
    "minecraft:golden_hoe": (None, -3.0),
    "minecraft:diamond_hoe": (None, None),
    "minecraft:netherite_hoe": (None, None),
    "minecraft:copper_hoe": (None, -2.0),
    # булава (итог 6 урона; скорость 0.6) и трезубец (итог 9; 1.1)
    "minecraft:mace": (5, -3.4),
    "minecraft:trident": (8, -2.9),
}

# броня: материал -> (очки head/chest/legs/feet, armor_toughness,
# knockback_resistance) - ArmorItem/ArmorMaterial из jar 26.2
_BASE_ARMOR_ATTRS = {
    "leather": ((1, 3, 2, 1), 0, 0.0),    # итог 7
    "chainmail": ((2, 5, 4, 1), 0, 0.0),  # итог 12
    "golden": ((2, 5, 3, 1), 0, 0.0),     # итог 11
    "copper": ((2, 5, 4, 2), 0, 0.0),     # итог 13 (Copper Age, 26.x)
    "iron": ((2, 6, 5, 2), 0, 0.0),       # итог 15
    "diamond": ((3, 8, 6, 3), 2, 0.0),    # итог 20, твёрдость 8
    "netherite": ((3, 8, 6, 3), 3, 0.1),  # итог 20, твёрдость 12, kb 0.4
}


def _build_base_attrs():
    """Собрать item -> [(атрибут, amount), ...] из таблиц выше.
    (черепаший шлем - 2 брони, без твёрдости; элитра/щит/лук и прочее -
    ванильных модификаторов не имеют, в таблицу не попадают)."""
    out = {}
    for it, (dmg, spd) in _BASE_TOOL_ATTRS.items():
        mods = []
        if dmg is not None:
            mods.append(("minecraft:attack_damage", dmg))
        if spd is not None:
            mods.append(("minecraft:attack_speed", spd))
        if mods:
            out[it] = mods
    for mat, (pts, tough, kbr) in _BASE_ARMOR_ATTRS.items():
        for part, p in (("helmet", 0), ("chestplate", 1),
                        ("leggings", 2), ("boots", 3)):
            mods = [("minecraft:armor", pts[p])]
            if tough:
                mods.append(("minecraft:armor_toughness", tough))
            if kbr:
                mods.append(("minecraft:knockback_resistance", kbr))
            out["minecraft:%s_%s" % (mat, part)] = mods
    out["minecraft:turtle_helmet"] = [("minecraft:armor", 2)]
    return out


_BASE_ATTRS = _build_base_attrs()

# слот ванильного equippable у «настоящей» носимой брони (генератор сам
# компонент не ставит - дефолтный уже на предмете; нужно аудиту слотов
# атрибутов и базовых модификаторов)
_VANILLA_EQUIP = {}
for _part, _slot in (("helmet", "head"), ("chestplate", "chest"),
                     ("leggings", "legs"), ("boots", "feet")):
    for _mat in _BASE_ARMOR_ATTRS:
        _VANILLA_EQUIP["minecraft:%s_%s" % (_mat, _part)] = _slot
_VANILLA_EQUIP["minecraft:turtle_helmet"] = "head"
_VANILLA_EQUIP["minecraft:elytra"] = "chest"
_VANILLA_EQUIP["minecraft:wolf_armor"] = "body"
for _h in ("minecraft:skeleton_skull", "minecraft:wither_skeleton_skull",
           "minecraft:zombie_head", "minecraft:creeper_head",
           "minecraft:dragon_head", "minecraft:piglin_head",
           "minecraft:player_head", "minecraft:carved_pumpkin"):
    _VANILLA_EQUIP[_h] = "head"
for _mat in ("leather", "copper", "iron", "golden", "diamond", "netherite"):
    _VANILLA_EQUIP["minecraft:%s_horse_armor" % _mat] = "body"


def _base_attr_slot(item):
    """Слот для ванильных базовых модификаторов: броня - свой слот,
    оружие/инструменты - mainhand (как в Items.class 26.2)."""
    return _KIND_SLOTS.get(_kind_of(item), "mainhand")


def _vanilla_base_mods(item, tag_prefix):
    """Ванильные дефолт-модификаторы предмета (см. _BASE_TOOL_ATTRS /
    _BASE_ARMOR_ATTRS) в формате компонента 26.2. id с суффиксом _base -
    по нему lore и имена отличают базу от собственных модификаторов."""
    specs = _BASE_ATTRS.get(item)
    if not specs:
        return []
    slot = _base_attr_slot(item)
    return [{"type": a, "id": "%s_base%d" % (tag_prefix, i),
             "amount": amt, "operation": "add_value", "slot": slot}
            for i, (a, amt) in enumerate(specs)]

# ---------------------------------------------------------------------------
# «Дикий тир»: ПОЛНЫЙ каталог предметов 26.2 - весь реестр minecraft:item
# (1523 id из reports/registries.json реального сервера; он посимвольно
# совпадает с assets/minecraft/items/*.json клиентского jar) минус
# технические предметы, которые нельзя выдавать лутом:
#   air - сервер ругается «Item must not be minecraft:air»;
#   barrier, light, командные/структурные блоки, jigsaw, debug_stick,
#   knowledge_book, test_block, test_instance_block - недоступны в обычной
#   игре. Спавн-яйца оставлены: это валидные предметы из креатива.
# ---------------------------------------------------------------------------

_TECH_ITEMS = frozenset([
    "air", "barrier", "light", "command_block", "chain_command_block",
    "repeating_command_block", "command_block_minecart", "structure_block",
    "structure_void", "jigsaw", "debug_stick", "knowledge_book",
    "test_block", "test_instance_block"])

# ФАНТОМНЫЕ предметы: есть в lang-файле (имя-подсказка), НЕТ в реестре
# item 26.2 - серверная проба всех 1523 id (лут-таблица на предмет +
# loot spawn -> «Unknown registry key»). Ловушка суперсета lang-файлов,
# как entity-killer_bunny. В 26.2 лодстоун-компас = компас с компонентом
# lodestone_tracker, отдельного предмета нет
_PHANTOM_ITEMS = frozenset(["lodestone_compass"])

ALL_ITEMS = []  # заполняется ниже из _ALL_ITEM_NAMES


# полный реестр предметов (дамп сервера 26.2), по 6 id в строке;
# фильтрация технических - ниже при сборке ALL_ITEMS
_ALL_ITEM_NAMES = [
    "acacia_boat", "acacia_button", "acacia_chest_boat", "acacia_door", "acacia_fence", "acacia_fence_gate",
    "acacia_hanging_sign", "acacia_leaves", "acacia_log", "acacia_planks", "acacia_pressure_plate", "acacia_sapling",
    "acacia_shelf", "acacia_sign", "acacia_slab", "acacia_stairs", "acacia_trapdoor", "acacia_wood",
    "activator_rail", "allay_spawn_egg", "allium", "amethyst_block", "amethyst_cluster", "amethyst_shard",
    "ancient_debris", "andesite", "andesite_slab", "andesite_stairs", "andesite_wall", "angler_pottery_sherd",
    "anvil", "apple", "archer_pottery_sherd", "armadillo_scute", "armadillo_spawn_egg", "armor_stand",
    "arms_up_pottery_sherd", "arrow", "axolotl_bucket", "axolotl_spawn_egg", "azalea", "azalea_leaves",
    "azure_bluet", "baked_potato", "bamboo", "bamboo_block", "bamboo_button", "bamboo_chest_raft",
    "bamboo_door", "bamboo_fence", "bamboo_fence_gate", "bamboo_hanging_sign", "bamboo_mosaic", "bamboo_mosaic_slab",
    "bamboo_mosaic_stairs", "bamboo_planks", "bamboo_pressure_plate", "bamboo_raft", "bamboo_shelf", "bamboo_sign",
    "bamboo_slab", "bamboo_stairs", "bamboo_trapdoor", "barrel", "basalt", "bat_spawn_egg",
    "beacon", "bedrock", "bee_nest", "bee_spawn_egg", "beef", "beehive",
    "beetroot", "beetroot_seeds", "beetroot_soup", "bell", "big_dripleaf", "birch_boat",
    "birch_button", "birch_chest_boat", "birch_door", "birch_fence", "birch_fence_gate", "birch_hanging_sign",
    "birch_leaves", "birch_log", "birch_planks", "birch_pressure_plate", "birch_sapling", "birch_shelf",
    "birch_sign", "birch_slab", "birch_stairs", "birch_trapdoor", "birch_wood", "black_banner",
    "black_bed", "black_bundle", "black_candle", "black_carpet", "black_concrete", "black_concrete_powder",
    "black_dye", "black_glazed_terracotta", "black_harness", "black_shulker_box", "black_stained_glass", "black_stained_glass_pane",
    "black_terracotta", "black_wool", "blackstone", "blackstone_slab", "blackstone_stairs", "blackstone_wall",
    "blade_pottery_sherd", "blast_furnace", "blaze_powder", "blaze_rod", "blaze_spawn_egg", "blue_banner",
    "blue_bed", "blue_bundle", "blue_candle", "blue_carpet", "blue_concrete", "blue_concrete_powder",
    "blue_dye", "blue_egg", "blue_glazed_terracotta", "blue_harness", "blue_ice", "blue_orchid",
    "blue_shulker_box", "blue_stained_glass", "blue_stained_glass_pane", "blue_terracotta", "blue_wool", "bogged_spawn_egg",
    "bolt_armor_trim_smithing_template", "bone", "bone_block", "bone_meal", "book", "bookshelf",
    "bordure_indented_banner_pattern", "bow", "bowl", "brain_coral", "brain_coral_block", "brain_coral_fan",
    "bread", "breeze_rod", "breeze_spawn_egg", "brewer_pottery_sherd", "brewing_stand", "brick",
    "brick_slab", "brick_stairs", "brick_wall", "bricks", "brown_banner", "brown_bed",
    "brown_bundle", "brown_candle", "brown_carpet", "brown_concrete", "brown_concrete_powder", "brown_dye",
    "brown_egg", "brown_glazed_terracotta", "brown_harness", "brown_mushroom", "brown_mushroom_block", "brown_shulker_box",
    "brown_stained_glass", "brown_stained_glass_pane", "brown_terracotta", "brown_wool", "brush", "bubble_coral",
    "bubble_coral_block", "bubble_coral_fan", "bucket", "budding_amethyst", "bundle", "burn_pottery_sherd",
    "bush", "cactus", "cactus_flower", "cake", "calcite", "calibrated_sculk_sensor",
    "camel_husk_spawn_egg", "camel_spawn_egg", "campfire", "candle", "carrot", "carrot_on_a_stick",
    "cartography_table", "carved_pumpkin", "cat_spawn_egg", "cauldron", "cave_spider_spawn_egg", "chainmail_boots",
    "chainmail_chestplate", "chainmail_helmet", "chainmail_leggings", "charcoal", "cherry_boat", "cherry_button",
    "cherry_chest_boat", "cherry_door", "cherry_fence", "cherry_fence_gate", "cherry_hanging_sign", "cherry_leaves",
    "cherry_log", "cherry_planks", "cherry_pressure_plate", "cherry_sapling", "cherry_shelf", "cherry_sign",
    "cherry_slab", "cherry_stairs", "cherry_trapdoor", "cherry_wood", "chest", "chest_minecart",
    "chicken", "chicken_spawn_egg", "chipped_anvil", "chiseled_bookshelf", "chiseled_cinnabar", "chiseled_copper",
    "chiseled_deepslate", "chiseled_nether_bricks", "chiseled_polished_blackstone", "chiseled_quartz_block", "chiseled_red_sandstone", "chiseled_resin_bricks",
    "chiseled_sandstone", "chiseled_stone_bricks", "chiseled_sulfur", "chiseled_tuff", "chiseled_tuff_bricks", "chorus_flower",
    "chorus_fruit", "chorus_plant", "cinnabar", "cinnabar_brick_slab", "cinnabar_brick_stairs", "cinnabar_brick_wall",
    "cinnabar_bricks", "cinnabar_slab", "cinnabar_stairs", "cinnabar_wall", "clay", "clay_ball",
    "clock", "closed_eyeblossom", "coal", "coal_block", "coal_ore", "coarse_dirt",
    "coast_armor_trim_smithing_template", "cobbled_deepslate", "cobbled_deepslate_slab", "cobbled_deepslate_stairs", "cobbled_deepslate_wall", "cobblestone",
    "cobblestone_slab", "cobblestone_stairs", "cobblestone_wall", "cobweb", "cocoa_beans", "cod",
    "cod_bucket", "cod_spawn_egg", "comparator", "compass", "composter", "conduit",
    "cooked_beef", "cooked_chicken", "cooked_cod", "cooked_mutton", "cooked_porkchop", "cooked_rabbit",
    "cooked_salmon", "cookie", "copper_axe", "copper_bars", "copper_block", "copper_boots",
    "copper_bulb", "copper_chain", "copper_chest", "copper_chestplate", "copper_door", "copper_golem_spawn_egg",
    "copper_golem_statue", "copper_grate", "copper_helmet", "copper_hoe", "copper_horse_armor", "copper_ingot",
    "copper_lantern", "copper_leggings", "copper_nautilus_armor", "copper_nugget", "copper_ore", "copper_pickaxe",
    "copper_shovel", "copper_spear", "copper_sword", "copper_torch", "copper_trapdoor", "cornflower",
    "cow_spawn_egg", "cracked_deepslate_bricks", "cracked_deepslate_tiles", "cracked_nether_bricks", "cracked_polished_blackstone_bricks", "cracked_stone_bricks",
    "crafter", "crafting_table", "creaking_heart", "creaking_spawn_egg", "creeper_banner_pattern", "creeper_head",
    "creeper_spawn_egg", "crimson_button", "crimson_door", "crimson_fence", "crimson_fence_gate", "crimson_fungus",
    "crimson_hanging_sign", "crimson_hyphae", "crimson_nylium", "crimson_planks", "crimson_pressure_plate", "crimson_roots",
    "crimson_shelf", "crimson_sign", "crimson_slab", "crimson_stairs", "crimson_stem", "crimson_trapdoor",
    "crossbow", "crying_obsidian", "cut_copper", "cut_copper_slab", "cut_copper_stairs", "cut_red_sandstone",
    "cut_red_sandstone_slab", "cut_sandstone", "cut_sandstone_slab", "cyan_banner", "cyan_bed", "cyan_bundle",
    "cyan_candle", "cyan_carpet", "cyan_concrete", "cyan_concrete_powder", "cyan_dye", "cyan_glazed_terracotta",
    "cyan_harness", "cyan_shulker_box", "cyan_stained_glass", "cyan_stained_glass_pane", "cyan_terracotta", "cyan_wool",
    "damaged_anvil", "dandelion", "danger_pottery_sherd", "dark_oak_boat", "dark_oak_button", "dark_oak_chest_boat",
    "dark_oak_door", "dark_oak_fence", "dark_oak_fence_gate", "dark_oak_hanging_sign", "dark_oak_leaves", "dark_oak_log",
    "dark_oak_planks", "dark_oak_pressure_plate", "dark_oak_sapling", "dark_oak_shelf", "dark_oak_sign", "dark_oak_slab",
    "dark_oak_stairs", "dark_oak_trapdoor", "dark_oak_wood", "dark_prismarine", "dark_prismarine_slab", "dark_prismarine_stairs",
    "daylight_detector", "dead_brain_coral", "dead_brain_coral_block", "dead_brain_coral_fan", "dead_bubble_coral", "dead_bubble_coral_block",
    "dead_bubble_coral_fan", "dead_bush", "dead_fire_coral", "dead_fire_coral_block", "dead_fire_coral_fan", "dead_horn_coral",
    "dead_horn_coral_block", "dead_horn_coral_fan", "dead_tube_coral", "dead_tube_coral_block", "dead_tube_coral_fan", "decorated_pot",
    "deepslate", "deepslate_brick_slab", "deepslate_brick_stairs", "deepslate_brick_wall", "deepslate_bricks", "deepslate_coal_ore",
    "deepslate_copper_ore", "deepslate_diamond_ore", "deepslate_emerald_ore", "deepslate_gold_ore", "deepslate_iron_ore", "deepslate_lapis_ore",
    "deepslate_redstone_ore", "deepslate_tile_slab", "deepslate_tile_stairs", "deepslate_tile_wall", "deepslate_tiles", "detector_rail",
    "diamond", "diamond_axe", "diamond_block", "diamond_boots", "diamond_chestplate", "diamond_helmet",
    "diamond_hoe", "diamond_horse_armor", "diamond_leggings", "diamond_nautilus_armor", "diamond_ore", "diamond_pickaxe",
    "diamond_shovel", "diamond_spear", "diamond_sword", "diorite", "diorite_slab", "diorite_stairs",
    "diorite_wall", "dirt", "dirt_path", "disc_fragment_5", "dispenser", "dolphin_spawn_egg",
    "donkey_spawn_egg", "dragon_breath", "dragon_egg", "dragon_head", "dried_ghast", "dried_kelp",
    "dried_kelp_block", "dripstone_block", "dropper", "drowned_spawn_egg", "dune_armor_trim_smithing_template", "echo_shard",
    "egg", "elder_guardian_spawn_egg", "elytra", "emerald", "emerald_block", "emerald_ore",
    "enchanted_book", "enchanted_golden_apple", "enchanting_table", "end_crystal", "end_portal_frame", "end_rod",
    "end_stone", "end_stone_brick_slab", "end_stone_brick_stairs", "end_stone_brick_wall", "end_stone_bricks", "ender_chest",
    "ender_dragon_spawn_egg", "ender_eye", "ender_pearl", "enderman_spawn_egg", "endermite_spawn_egg", "evoker_spawn_egg",
    "experience_bottle", "explorer_pottery_sherd", "exposed_chiseled_copper", "exposed_copper", "exposed_copper_bars", "exposed_copper_bulb",
    "exposed_copper_chain", "exposed_copper_chest", "exposed_copper_door", "exposed_copper_golem_statue", "exposed_copper_grate", "exposed_copper_lantern",
    "exposed_copper_trapdoor", "exposed_cut_copper", "exposed_cut_copper_slab", "exposed_cut_copper_stairs", "exposed_lightning_rod", "eye_armor_trim_smithing_template",
    "farmland", "feather", "fermented_spider_eye", "fern", "field_masoned_banner_pattern", "filled_map",
    "fire_charge", "fire_coral", "fire_coral_block", "fire_coral_fan", "firefly_bush", "firework_rocket",
    "firework_star", "fishing_rod", "fletching_table", "flint", "flint_and_steel", "flow_armor_trim_smithing_template",
    "flow_banner_pattern", "flow_pottery_sherd", "flower_banner_pattern", "flower_pot", "flowering_azalea", "flowering_azalea_leaves",
    "fox_spawn_egg", "friend_pottery_sherd", "frog_spawn_egg", "frogspawn", "furnace", "furnace_minecart",
    "ghast_spawn_egg", "ghast_tear", "gilded_blackstone", "glass", "glass_bottle", "glass_pane",
    "glistering_melon_slice", "globe_banner_pattern", "glow_berries", "glow_ink_sac", "glow_item_frame", "glow_lichen",
    "glow_squid_spawn_egg", "glowstone", "glowstone_dust", "goat_horn", "goat_spawn_egg", "gold_block",
    "gold_ingot", "gold_nugget", "gold_ore", "golden_apple", "golden_axe", "golden_boots",
    "golden_carrot", "golden_chestplate", "golden_dandelion", "golden_helmet", "golden_hoe", "golden_horse_armor",
    "golden_leggings", "golden_nautilus_armor", "golden_pickaxe", "golden_shovel", "golden_spear", "golden_sword",
    "granite", "granite_slab", "granite_stairs", "granite_wall", "grass_block", "gravel",
    "gray_banner", "gray_bed", "gray_bundle", "gray_candle", "gray_carpet", "gray_concrete",
    "gray_concrete_powder", "gray_dye", "gray_glazed_terracotta", "gray_harness", "gray_shulker_box", "gray_stained_glass",
    "gray_stained_glass_pane", "gray_terracotta", "gray_wool", "green_banner", "green_bed", "green_bundle",
    "green_candle", "green_carpet", "green_concrete", "green_concrete_powder", "green_dye", "green_glazed_terracotta",
    "green_harness", "green_shulker_box", "green_stained_glass", "green_stained_glass_pane", "green_terracotta", "green_wool",
    "grindstone", "guardian_spawn_egg", "gunpowder", "guster_banner_pattern", "guster_pottery_sherd", "hanging_roots",
    "happy_ghast_spawn_egg", "hay_block", "heart_of_the_sea", "heart_pottery_sherd", "heartbreak_pottery_sherd", "heavy_core",
    "heavy_weighted_pressure_plate", "hoglin_spawn_egg", "honey_block", "honey_bottle", "honeycomb", "honeycomb_block",
    "hopper", "hopper_minecart", "horn_coral", "horn_coral_block", "horn_coral_fan", "horse_spawn_egg",
    "host_armor_trim_smithing_template", "howl_pottery_sherd", "husk_spawn_egg", "ice", "infested_chiseled_stone_bricks", "infested_cobblestone",
    "infested_cracked_stone_bricks", "infested_deepslate", "infested_mossy_stone_bricks", "infested_stone", "infested_stone_bricks", "ink_sac",
    "iron_axe", "iron_bars", "iron_block", "iron_boots", "iron_chain", "iron_chestplate",
    "iron_door", "iron_golem_spawn_egg", "iron_helmet", "iron_hoe", "iron_horse_armor", "iron_ingot",
    "iron_leggings", "iron_nautilus_armor", "iron_nugget", "iron_ore", "iron_pickaxe", "iron_shovel",
    "iron_spear", "iron_sword", "iron_trapdoor", "item_frame", "jack_o_lantern", "jukebox",
    "jungle_boat", "jungle_button", "jungle_chest_boat", "jungle_door", "jungle_fence", "jungle_fence_gate",
    "jungle_hanging_sign", "jungle_leaves", "jungle_log", "jungle_planks", "jungle_pressure_plate", "jungle_sapling",
    "jungle_shelf", "jungle_sign", "jungle_slab", "jungle_stairs", "jungle_trapdoor", "jungle_wood",
    "kelp", "ladder", "lantern", "lapis_block", "lapis_lazuli", "lapis_ore",
    "large_amethyst_bud", "large_fern", "lava_bucket", "lead", "leaf_litter", "leather",
    "leather_boots", "leather_chestplate", "leather_helmet", "leather_horse_armor", "leather_leggings", "lectern",
    "lever", "light_blue_banner", "light_blue_bed", "light_blue_bundle", "light_blue_candle", "light_blue_carpet",
    "light_blue_concrete", "light_blue_concrete_powder", "light_blue_dye", "light_blue_glazed_terracotta", "light_blue_harness", "light_blue_shulker_box",
    "light_blue_stained_glass", "light_blue_stained_glass_pane", "light_blue_terracotta", "light_blue_wool", "light_gray_banner", "light_gray_bed",
    "light_gray_bundle", "light_gray_candle", "light_gray_carpet", "light_gray_concrete", "light_gray_concrete_powder", "light_gray_dye",
    "light_gray_glazed_terracotta", "light_gray_harness", "light_gray_shulker_box", "light_gray_stained_glass", "light_gray_stained_glass_pane", "light_gray_terracotta",
    "light_gray_wool", "light_weighted_pressure_plate", "lightning_rod", "lilac", "lily_of_the_valley", "lily_pad",
    "lime_banner", "lime_bed", "lime_bundle", "lime_candle", "lime_carpet", "lime_concrete",
    "lime_concrete_powder", "lime_dye", "lime_glazed_terracotta", "lime_harness", "lime_shulker_box", "lime_stained_glass",
    "lime_stained_glass_pane", "lime_terracotta", "lime_wool", "lingering_potion", "llama_spawn_egg", "lodestone",
    "loom", "mace", "magenta_banner", "magenta_bed", "magenta_bundle", "magenta_candle",
    "magenta_carpet", "magenta_concrete", "magenta_concrete_powder", "magenta_dye", "magenta_glazed_terracotta", "magenta_harness",
    "magenta_shulker_box", "magenta_stained_glass", "magenta_stained_glass_pane", "magenta_terracotta", "magenta_wool", "magma_block",
    "magma_cream", "magma_cube_spawn_egg", "mangrove_boat", "mangrove_button", "mangrove_chest_boat", "mangrove_door",
    "mangrove_fence", "mangrove_fence_gate", "mangrove_hanging_sign", "mangrove_leaves", "mangrove_log", "mangrove_planks",
    "mangrove_pressure_plate", "mangrove_propagule", "mangrove_roots", "mangrove_shelf", "mangrove_sign", "mangrove_slab",
    "mangrove_stairs", "mangrove_trapdoor", "mangrove_wood", "map", "medium_amethyst_bud", "melon",
    "melon_seeds", "melon_slice", "milk_bucket", "minecart", "miner_pottery_sherd", "mojang_banner_pattern",
    "mooshroom_spawn_egg", "moss_block", "moss_carpet", "mossy_cobblestone", "mossy_cobblestone_slab", "mossy_cobblestone_stairs",
    "mossy_cobblestone_wall", "mossy_stone_brick_slab", "mossy_stone_brick_stairs", "mossy_stone_brick_wall", "mossy_stone_bricks", "mourner_pottery_sherd",
    "mud", "mud_brick_slab", "mud_brick_stairs", "mud_brick_wall", "mud_bricks", "muddy_mangrove_roots",
    "mule_spawn_egg", "mushroom_stem", "mushroom_stew", "music_disc_11", "music_disc_13", "music_disc_5",
    "music_disc_blocks", "music_disc_bounce", "music_disc_cat", "music_disc_chirp", "music_disc_creator", "music_disc_creator_music_box",
    "music_disc_far", "music_disc_lava_chicken", "music_disc_mall", "music_disc_mellohi", "music_disc_otherside", "music_disc_pigstep",
    "music_disc_precipice", "music_disc_relic", "music_disc_stal", "music_disc_strad", "music_disc_tears", "music_disc_wait",
    "music_disc_ward", "mutton", "mycelium", "name_tag", "nautilus_shell", "nautilus_spawn_egg",
    "nether_brick", "nether_brick_fence", "nether_brick_slab", "nether_brick_stairs", "nether_brick_wall", "nether_bricks",
    "nether_gold_ore", "nether_quartz_ore", "nether_sprouts", "nether_star", "nether_wart", "nether_wart_block",
    "netherite_axe", "netherite_block", "netherite_boots", "netherite_chestplate", "netherite_helmet", "netherite_hoe",
    "netherite_horse_armor", "netherite_ingot", "netherite_leggings", "netherite_nautilus_armor", "netherite_pickaxe", "netherite_scrap",
    "netherite_shovel", "netherite_spear", "netherite_sword", "netherite_upgrade_smithing_template", "netherrack", "note_block",
    "oak_boat", "oak_button", "oak_chest_boat", "oak_door", "oak_fence", "oak_fence_gate",
    "oak_hanging_sign", "oak_leaves", "oak_log", "oak_planks", "oak_pressure_plate", "oak_sapling",
    "oak_shelf", "oak_sign", "oak_slab", "oak_stairs", "oak_trapdoor", "oak_wood",
    "observer", "obsidian", "ocelot_spawn_egg", "ochre_froglight", "ominous_bottle", "ominous_trial_key",
    "open_eyeblossom", "orange_banner", "orange_bed", "orange_bundle", "orange_candle", "orange_carpet",
    "orange_concrete", "orange_concrete_powder", "orange_dye", "orange_glazed_terracotta", "orange_harness", "orange_shulker_box",
    "orange_stained_glass", "orange_stained_glass_pane", "orange_terracotta", "orange_tulip", "orange_wool", "oxeye_daisy",
    "oxidized_chiseled_copper", "oxidized_copper", "oxidized_copper_bars", "oxidized_copper_bulb", "oxidized_copper_chain", "oxidized_copper_chest",
    "oxidized_copper_door", "oxidized_copper_golem_statue", "oxidized_copper_grate", "oxidized_copper_lantern", "oxidized_copper_trapdoor", "oxidized_cut_copper",
    "oxidized_cut_copper_slab", "oxidized_cut_copper_stairs", "oxidized_lightning_rod", "packed_ice", "packed_mud", "painting",
    "pale_hanging_moss", "pale_moss_block", "pale_moss_carpet", "pale_oak_boat", "pale_oak_button", "pale_oak_chest_boat",
    "pale_oak_door", "pale_oak_fence", "pale_oak_fence_gate", "pale_oak_hanging_sign", "pale_oak_leaves", "pale_oak_log",
    "pale_oak_planks", "pale_oak_pressure_plate", "pale_oak_sapling", "pale_oak_shelf", "pale_oak_sign", "pale_oak_slab",
    "pale_oak_stairs", "pale_oak_trapdoor", "pale_oak_wood", "panda_spawn_egg", "paper", "parched_spawn_egg",
    "parrot_spawn_egg", "pearlescent_froglight", "peony", "petrified_oak_slab", "phantom_membrane", "phantom_spawn_egg",
    "pig_spawn_egg", "piglin_banner_pattern", "piglin_brute_spawn_egg", "piglin_head", "piglin_spawn_egg", "pillager_spawn_egg",
    "pink_banner", "pink_bed", "pink_bundle", "pink_candle", "pink_carpet", "pink_concrete",
    "pink_concrete_powder", "pink_dye", "pink_glazed_terracotta", "pink_harness", "pink_petals", "pink_shulker_box",
    "pink_stained_glass", "pink_stained_glass_pane", "pink_terracotta", "pink_tulip", "pink_wool", "piston",
    "pitcher_plant", "pitcher_pod", "player_head", "plenty_pottery_sherd", "podzol", "pointed_dripstone",
    "poisonous_potato", "polar_bear_spawn_egg", "polished_andesite", "polished_andesite_slab", "polished_andesite_stairs", "polished_basalt",
    "polished_blackstone", "polished_blackstone_brick_slab", "polished_blackstone_brick_stairs", "polished_blackstone_brick_wall", "polished_blackstone_bricks", "polished_blackstone_button",
    "polished_blackstone_pressure_plate", "polished_blackstone_slab", "polished_blackstone_stairs", "polished_blackstone_wall", "polished_cinnabar", "polished_cinnabar_slab",
    "polished_cinnabar_stairs", "polished_cinnabar_wall", "polished_deepslate", "polished_deepslate_slab", "polished_deepslate_stairs", "polished_deepslate_wall",
    "polished_diorite", "polished_diorite_slab", "polished_diorite_stairs", "polished_granite", "polished_granite_slab", "polished_granite_stairs",
    "polished_sulfur", "polished_sulfur_slab", "polished_sulfur_stairs", "polished_sulfur_wall", "polished_tuff", "polished_tuff_slab",
    "polished_tuff_stairs", "polished_tuff_wall", "popped_chorus_fruit", "poppy", "porkchop", "potato",
    "potent_sulfur", "potion", "powder_snow_bucket", "powered_rail", "prismarine", "prismarine_brick_slab",
    "prismarine_brick_stairs", "prismarine_bricks", "prismarine_crystals", "prismarine_shard", "prismarine_slab", "prismarine_stairs",
    "prismarine_wall", "prize_pottery_sherd", "pufferfish", "pufferfish_bucket", "pufferfish_spawn_egg", "pumpkin",
    "pumpkin_pie", "pumpkin_seeds", "purple_banner", "purple_bed", "purple_bundle", "purple_candle",
    "purple_carpet", "purple_concrete", "purple_concrete_powder", "purple_dye", "purple_glazed_terracotta", "purple_harness",
    "purple_shulker_box", "purple_stained_glass", "purple_stained_glass_pane", "purple_terracotta", "purple_wool", "purpur_block",
    "purpur_pillar", "purpur_slab", "purpur_stairs", "quartz", "quartz_block", "quartz_bricks",
    "quartz_pillar", "quartz_slab", "quartz_stairs", "rabbit", "rabbit_foot", "rabbit_hide",
    "rabbit_spawn_egg", "rabbit_stew", "rail", "raiser_armor_trim_smithing_template", "ravager_spawn_egg", "raw_copper",
    "raw_copper_block", "raw_gold", "raw_gold_block", "raw_iron", "raw_iron_block", "recovery_compass",
    "red_banner", "red_bed", "red_bundle", "red_candle", "red_carpet", "red_concrete",
    "red_concrete_powder", "red_dye", "red_glazed_terracotta", "red_harness", "red_mushroom", "red_mushroom_block",
    "red_nether_brick_slab", "red_nether_brick_stairs", "red_nether_brick_wall", "red_nether_bricks", "red_sand", "red_sandstone",
    "red_sandstone_slab", "red_sandstone_stairs", "red_sandstone_wall", "red_shulker_box", "red_stained_glass", "red_stained_glass_pane",
    "red_terracotta", "red_tulip", "red_wool", "redstone", "redstone_block", "redstone_lamp",
    "redstone_ore", "redstone_torch", "reinforced_deepslate", "repeater", "resin_block", "resin_brick",
    "resin_brick_slab", "resin_brick_stairs", "resin_brick_wall", "resin_bricks", "resin_clump", "respawn_anchor",
    "rib_armor_trim_smithing_template", "rooted_dirt", "rose_bush", "rotten_flesh", "saddle", "salmon",
    "salmon_bucket", "salmon_spawn_egg", "sand", "sandstone", "sandstone_slab", "sandstone_stairs",
    "sandstone_wall", "scaffolding", "scrape_pottery_sherd", "sculk", "sculk_catalyst", "sculk_sensor",
    "sculk_shrieker", "sculk_vein", "sea_lantern", "sea_pickle", "seagrass", "sentry_armor_trim_smithing_template",
    "shaper_armor_trim_smithing_template", "sheaf_pottery_sherd", "shears", "sheep_spawn_egg", "shelter_pottery_sherd", "shield",
    "short_dry_grass", "short_grass", "shroomlight", "shulker_box", "shulker_shell", "shulker_spawn_egg",
    "silence_armor_trim_smithing_template", "silverfish_spawn_egg", "skeleton_horse_spawn_egg", "skeleton_skull", "skeleton_spawn_egg", "skull_banner_pattern",
    "skull_pottery_sherd", "slime_ball", "slime_block", "slime_spawn_egg", "small_amethyst_bud", "small_dripleaf",
    "smithing_table", "smoker", "smooth_basalt", "smooth_quartz", "smooth_quartz_slab", "smooth_quartz_stairs",
    "smooth_red_sandstone", "smooth_red_sandstone_slab", "smooth_red_sandstone_stairs", "smooth_sandstone", "smooth_sandstone_slab", "smooth_sandstone_stairs",
    "smooth_stone", "smooth_stone_slab", "sniffer_egg", "sniffer_spawn_egg", "snort_pottery_sherd", "snout_armor_trim_smithing_template",
    "snow", "snow_block", "snow_golem_spawn_egg", "snowball", "soul_campfire", "soul_lantern",
    "soul_sand", "soul_soil", "soul_torch", "spawner", "spectral_arrow", "spider_eye",
    "spider_spawn_egg", "spire_armor_trim_smithing_template", "splash_potion", "sponge", "spore_blossom", "spruce_boat",
    "spruce_button", "spruce_chest_boat", "spruce_door", "spruce_fence", "spruce_fence_gate", "spruce_hanging_sign",
    "spruce_leaves", "spruce_log", "spruce_planks", "spruce_pressure_plate", "spruce_sapling", "spruce_shelf",
    "spruce_sign", "spruce_slab", "spruce_stairs", "spruce_trapdoor", "spruce_wood", "spyglass",
    "squid_spawn_egg", "stick", "sticky_piston", "stone", "stone_axe", "stone_brick_slab",
    "stone_brick_stairs", "stone_brick_wall", "stone_bricks", "stone_button", "stone_hoe", "stone_pickaxe",
    "stone_pressure_plate", "stone_shovel", "stone_slab", "stone_spear", "stone_stairs", "stone_sword",
    "stonecutter", "stray_spawn_egg", "strider_spawn_egg", "string", "stripped_acacia_log", "stripped_acacia_wood",
    "stripped_bamboo_block", "stripped_birch_log", "stripped_birch_wood", "stripped_cherry_log", "stripped_cherry_wood", "stripped_crimson_hyphae",
    "stripped_crimson_stem", "stripped_dark_oak_log", "stripped_dark_oak_wood", "stripped_jungle_log", "stripped_jungle_wood", "stripped_mangrove_log",
    "stripped_mangrove_wood", "stripped_oak_log", "stripped_oak_wood", "stripped_pale_oak_log", "stripped_pale_oak_wood", "stripped_spruce_log",
    "stripped_spruce_wood", "stripped_warped_hyphae", "stripped_warped_stem", "sugar", "sugar_cane", "sulfur",
    "sulfur_brick_slab", "sulfur_brick_stairs", "sulfur_brick_wall", "sulfur_bricks", "sulfur_cube_bucket", "sulfur_cube_spawn_egg",
    "sulfur_slab", "sulfur_spike", "sulfur_stairs", "sulfur_wall", "sunflower", "suspicious_gravel",
    "suspicious_sand", "suspicious_stew", "sweet_berries", "tadpole_bucket", "tadpole_spawn_egg", "tall_dry_grass",
    "tall_grass", "target", "terracotta", "tide_armor_trim_smithing_template", "tinted_glass", "tipped_arrow",
    "tnt", "tnt_minecart", "torch", "torchflower", "torchflower_seeds", "totem_of_undying",
    "trader_llama_spawn_egg", "trapped_chest", "trial_key", "trial_spawner", "trident", "tripwire_hook",
    "tropical_fish", "tropical_fish_bucket", "tropical_fish_spawn_egg", "tube_coral", "tube_coral_block", "tube_coral_fan",
    "tuff", "tuff_brick_slab", "tuff_brick_stairs", "tuff_brick_wall", "tuff_bricks", "tuff_slab",
    "tuff_stairs", "tuff_wall", "turtle_egg", "turtle_helmet", "turtle_scute", "turtle_spawn_egg",
    "twisting_vines", "vault", "verdant_froglight", "vex_armor_trim_smithing_template", "vex_spawn_egg", "villager_spawn_egg",
    "vindicator_spawn_egg", "vine", "wandering_trader_spawn_egg", "ward_armor_trim_smithing_template", "warden_spawn_egg", "warped_button",
    "warped_door", "warped_fence", "warped_fence_gate", "warped_fungus", "warped_fungus_on_a_stick", "warped_hanging_sign",
    "warped_hyphae", "warped_nylium", "warped_planks", "warped_pressure_plate", "warped_roots", "warped_shelf",
    "warped_sign", "warped_slab", "warped_stairs", "warped_stem", "warped_trapdoor", "warped_wart_block",
    "water_bucket", "waxed_chiseled_copper", "waxed_copper_bars", "waxed_copper_block", "waxed_copper_bulb", "waxed_copper_chain",
    "waxed_copper_chest", "waxed_copper_door", "waxed_copper_golem_statue", "waxed_copper_grate", "waxed_copper_lantern", "waxed_copper_trapdoor",
    "waxed_cut_copper", "waxed_cut_copper_slab", "waxed_cut_copper_stairs", "waxed_exposed_chiseled_copper", "waxed_exposed_copper", "waxed_exposed_copper_bars",
    "waxed_exposed_copper_bulb", "waxed_exposed_copper_chain", "waxed_exposed_copper_chest", "waxed_exposed_copper_door", "waxed_exposed_copper_golem_statue", "waxed_exposed_copper_grate",
    "waxed_exposed_copper_lantern", "waxed_exposed_copper_trapdoor", "waxed_exposed_cut_copper", "waxed_exposed_cut_copper_slab", "waxed_exposed_cut_copper_stairs", "waxed_exposed_lightning_rod",
    "waxed_lightning_rod", "waxed_oxidized_chiseled_copper", "waxed_oxidized_copper", "waxed_oxidized_copper_bars", "waxed_oxidized_copper_bulb", "waxed_oxidized_copper_chain",
    "waxed_oxidized_copper_chest", "waxed_oxidized_copper_door", "waxed_oxidized_copper_golem_statue", "waxed_oxidized_copper_grate", "waxed_oxidized_copper_lantern", "waxed_oxidized_copper_trapdoor",
    "waxed_oxidized_cut_copper", "waxed_oxidized_cut_copper_slab", "waxed_oxidized_cut_copper_stairs", "waxed_oxidized_lightning_rod", "waxed_weathered_chiseled_copper", "waxed_weathered_copper",
    "waxed_weathered_copper_bars", "waxed_weathered_copper_bulb", "waxed_weathered_copper_chain", "waxed_weathered_copper_chest", "waxed_weathered_copper_door", "waxed_weathered_copper_golem_statue",
    "waxed_weathered_copper_grate", "waxed_weathered_copper_lantern", "waxed_weathered_copper_trapdoor", "waxed_weathered_cut_copper", "waxed_weathered_cut_copper_slab", "waxed_weathered_cut_copper_stairs",
    "waxed_weathered_lightning_rod", "wayfinder_armor_trim_smithing_template", "weathered_chiseled_copper", "weathered_copper", "weathered_copper_bars", "weathered_copper_bulb",
    "weathered_copper_chain", "weathered_copper_chest", "weathered_copper_door", "weathered_copper_golem_statue", "weathered_copper_grate", "weathered_copper_lantern",
    "weathered_copper_trapdoor", "weathered_cut_copper", "weathered_cut_copper_slab", "weathered_cut_copper_stairs", "weathered_lightning_rod", "weeping_vines",
    "wet_sponge", "wheat", "wheat_seeds", "white_banner", "white_bed", "white_bundle",
    "white_candle", "white_carpet", "white_concrete", "white_concrete_powder", "white_dye", "white_glazed_terracotta",
    "white_harness", "white_shulker_box", "white_stained_glass", "white_stained_glass_pane", "white_terracotta", "white_tulip",
    "white_wool", "wild_armor_trim_smithing_template", "wildflowers", "wind_charge", "witch_spawn_egg", "wither_rose",
    "wither_skeleton_skull", "wither_skeleton_spawn_egg", "wither_spawn_egg", "wolf_armor", "wolf_spawn_egg", "wooden_axe",
    "wooden_hoe", "wooden_pickaxe", "wooden_shovel", "wooden_spear", "wooden_sword", "writable_book",
    "written_book", "yellow_banner", "yellow_bed", "yellow_bundle", "yellow_candle", "yellow_carpet",
    "yellow_concrete", "yellow_concrete_powder", "yellow_dye", "yellow_glazed_terracotta", "yellow_harness", "yellow_shulker_box",
    "yellow_stained_glass", "yellow_stained_glass_pane", "yellow_terracotta", "yellow_wool", "zoglin_spawn_egg", "zombie_head",
    "zombie_horse_spawn_egg", "zombie_nautilus_spawn_egg", "zombie_spawn_egg", "zombie_villager_spawn_egg", "zombified_piglin_spawn_egg",
]

ALL_ITEMS = ["minecraft:" + n for n in _ALL_ITEM_NAMES
             if n not in _TECH_ITEMS and n not in _PHANTOM_ITEMS]

# Предметы со стеком 1 (внутренности container/bundle_contents не могут
# иметь count > 1 - validateContainedItemSizes: «Item stack with count of
# N was larger than maximum: 1», патч отвергается целиком). Список из
# серверной пробы 26.2: каждый предмет клали в container с count 2;
# ровно эти 240 предметов упали. = damageable-снаряжение + кровати,
# лодки, шалкеры, вёдра-с-сущностью, зелья, диски, супы, конские и
# наутилусовые брони, узоры знамён, книги, тотем, подзорная труба...
# (written_book здесь НЕТ - он стакается; writable_book - нет)
_STACK1 = frozenset("""minecraft:acacia_boat minecraft:acacia_chest_boat
minecraft:axolotl_bucket minecraft:bamboo_chest_raft minecraft:bamboo_raft
minecraft:beetroot_soup minecraft:birch_boat minecraft:birch_chest_boat
minecraft:black_bed minecraft:black_bundle minecraft:black_harness
minecraft:black_shulker_box minecraft:blue_bed minecraft:blue_bundle
minecraft:blue_harness minecraft:blue_shulker_box
minecraft:bordure_indented_banner_pattern minecraft:bow minecraft:brown_bed
minecraft:brown_bundle minecraft:brown_harness minecraft:brown_shulker_box
minecraft:brush minecraft:bundle minecraft:cake minecraft:carrot_on_a_stick
minecraft:chainmail_boots minecraft:chainmail_chestplate
minecraft:chainmail_helmet minecraft:chainmail_leggings minecraft:cherry_boat
minecraft:cherry_chest_boat minecraft:chest_minecart minecraft:cod_bucket
minecraft:copper_axe minecraft:copper_boots minecraft:copper_chestplate
minecraft:copper_helmet minecraft:copper_hoe minecraft:copper_horse_armor
minecraft:copper_leggings minecraft:copper_nautilus_armor
minecraft:copper_pickaxe minecraft:copper_shovel minecraft:copper_spear
minecraft:copper_sword minecraft:creeper_banner_pattern minecraft:crossbow
minecraft:cyan_bed minecraft:cyan_bundle minecraft:cyan_harness
minecraft:cyan_shulker_box minecraft:dark_oak_boat
minecraft:dark_oak_chest_boat minecraft:diamond_axe minecraft:diamond_boots
minecraft:diamond_chestplate minecraft:diamond_helmet minecraft:diamond_hoe
minecraft:diamond_horse_armor minecraft:diamond_leggings
minecraft:diamond_nautilus_armor minecraft:diamond_pickaxe
minecraft:diamond_shovel minecraft:diamond_spear minecraft:diamond_sword
minecraft:elytra minecraft:enchanted_book
minecraft:field_masoned_banner_pattern minecraft:fishing_rod
minecraft:flint_and_steel minecraft:flow_banner_pattern
minecraft:flower_banner_pattern minecraft:furnace_minecart
minecraft:globe_banner_pattern minecraft:goat_horn minecraft:golden_axe
minecraft:golden_boots minecraft:golden_chestplate minecraft:golden_helmet
minecraft:golden_hoe minecraft:golden_horse_armor minecraft:golden_leggings
minecraft:golden_nautilus_armor minecraft:golden_pickaxe
minecraft:golden_shovel minecraft:golden_spear minecraft:golden_sword
minecraft:gray_bed minecraft:gray_bundle minecraft:gray_harness
minecraft:gray_shulker_box minecraft:green_bed minecraft:green_bundle
minecraft:green_harness minecraft:green_shulker_box
minecraft:guster_banner_pattern minecraft:hopper_minecart minecraft:iron_axe
minecraft:iron_boots minecraft:iron_chestplate minecraft:iron_helmet
minecraft:iron_hoe minecraft:iron_horse_armor minecraft:iron_leggings
minecraft:iron_nautilus_armor minecraft:iron_pickaxe minecraft:iron_shovel
minecraft:iron_spear minecraft:iron_sword minecraft:jungle_boat
minecraft:jungle_chest_boat minecraft:lava_bucket minecraft:leather_boots
minecraft:leather_chestplate minecraft:leather_helmet
minecraft:leather_horse_armor minecraft:leather_leggings
minecraft:light_blue_bed minecraft:light_blue_bundle
minecraft:light_blue_harness minecraft:light_blue_shulker_box
minecraft:light_gray_bed minecraft:light_gray_bundle
minecraft:light_gray_harness minecraft:light_gray_shulker_box
minecraft:lime_bed minecraft:lime_bundle minecraft:lime_harness
minecraft:lime_shulker_box minecraft:lingering_potion minecraft:mace
minecraft:magenta_bed minecraft:magenta_bundle minecraft:magenta_harness
minecraft:magenta_shulker_box minecraft:mangrove_boat
minecraft:mangrove_chest_boat minecraft:milk_bucket minecraft:minecart
minecraft:mojang_banner_pattern minecraft:mushroom_stew
minecraft:music_disc_blocks minecraft:music_disc_bounce
minecraft:music_disc_cat minecraft:music_disc_chirp
minecraft:music_disc_creator minecraft:music_disc_creator_music_box
minecraft:music_disc_far minecraft:music_disc_lava_chicken
minecraft:music_disc_mall minecraft:music_disc_mellohi
minecraft:music_disc_otherside minecraft:music_disc_pigstep
minecraft:music_disc_precipice minecraft:music_disc_relic
minecraft:music_disc_stal minecraft:music_disc_strad
minecraft:music_disc_tears minecraft:music_disc_wait minecraft:music_disc_ward
minecraft:netherite_axe minecraft:netherite_boots
minecraft:netherite_chestplate minecraft:netherite_helmet
minecraft:netherite_hoe minecraft:netherite_horse_armor
minecraft:netherite_leggings minecraft:netherite_nautilus_armor
minecraft:netherite_pickaxe minecraft:netherite_shovel
minecraft:netherite_spear minecraft:netherite_sword minecraft:oak_boat
minecraft:oak_chest_boat minecraft:orange_bed minecraft:orange_bundle
minecraft:orange_harness minecraft:orange_shulker_box
minecraft:pale_oak_boat minecraft:pale_oak_chest_boat
minecraft:piglin_banner_pattern minecraft:pink_bed minecraft:pink_bundle
minecraft:pink_harness minecraft:pink_shulker_box minecraft:potion
minecraft:powder_snow_bucket minecraft:pufferfish_bucket
minecraft:purple_bed minecraft:purple_bundle minecraft:purple_harness
minecraft:purple_shulker_box minecraft:rabbit_stew minecraft:red_bed
minecraft:red_bundle minecraft:red_harness minecraft:red_shulker_box
minecraft:saddle minecraft:salmon_bucket minecraft:shears
minecraft:shield minecraft:shulker_box
minecraft:skull_banner_pattern minecraft:spyglass minecraft:stone_axe
minecraft:stone_hoe minecraft:stone_pickaxe minecraft:stone_shovel
minecraft:stone_spear minecraft:stone_sword minecraft:splash_potion
minecraft:spruce_boat minecraft:spruce_chest_boat
minecraft:sulfur_cube_bucket minecraft:suspicious_stew
minecraft:tadpole_bucket minecraft:tnt_minecart
minecraft:totem_of_undying minecraft:trident
minecraft:tropical_fish_bucket minecraft:turtle_helmet
minecraft:warped_fungus_on_a_stick minecraft:water_bucket
minecraft:white_bed minecraft:white_bundle minecraft:white_harness
minecraft:white_shulker_box minecraft:wolf_armor minecraft:wooden_axe
minecraft:wooden_hoe minecraft:wooden_pickaxe minecraft:wooden_shovel
minecraft:wooden_spear minecraft:wooden_sword minecraft:writable_book
minecraft:yellow_bed minecraft:yellow_bundle minecraft:yellow_harness
minecraft:yellow_shulker_box""".split())

ULTRA_RARE_VALUABLES = frozenset([
    "minecraft:nether_star", "minecraft:elytra", "minecraft:beacon",
    "minecraft:heavy_core", "minecraft:conduit", "minecraft:enchanted_golden_apple",
    "minecraft:dragon_egg", "minecraft:dragon_head", "minecraft:netherite_block",
    "minecraft:lodestone", "minecraft:recovery_compass", "minecraft:sponge",
    "minecraft:wet_sponge", "minecraft:totem_of_undying", "minecraft:trial_key",
    "minecraft:ominous_trial_key", "minecraft:mace", "minecraft:trident",
    "minecraft:shulker_box", "minecraft:white_shulker_box", "minecraft:orange_shulker_box",
    "minecraft:magenta_shulker_box", "minecraft:light_blue_shulker_box", "minecraft:yellow_shulker_box",
    "minecraft:lime_shulker_box", "minecraft:pink_shulker_box", "minecraft:gray_shulker_box",
    "minecraft:light_gray_shulker_box", "minecraft:cyan_shulker_box", "minecraft:purple_shulker_box",
    "minecraft:blue_shulker_box", "minecraft:brown_shulker_box", "minecraft:green_shulker_box",
    "minecraft:red_shulker_box", "minecraft:black_shulker_box"
])

RARE_VALUABLES = frozenset([
    "minecraft:netherite_ingot", "minecraft:netherite_scrap",
    "minecraft:netherite_upgrade_smithing_template", "minecraft:diamond_block",
    "minecraft:emerald_block", "minecraft:gold_block", "minecraft:heart_of_the_sea",
    "minecraft:nautilus_shell", "minecraft:echo_shard", "minecraft:disc_fragment_5",
    "minecraft:golden_apple", "minecraft:wither_skeleton_skull"
])


# спавн-яйца из полного каталога - для «сюрпризных» записей (варианты
# сущностей на яйцах: cat/variant, wolf/variant и т.д.)
SPAWN_EGGS = [i for i in ALL_ITEMS if i.endswith("_spawn_egg")]

# ---------------------------------------------------------------------------
# Данные реестров для компонентов (всё выверено по jar / дампу сервера):
#   jukebox_song - data/minecraft/jukebox_song/*.json (22 песни);
#   instrument - data/minecraft/instrument/*.json (8 рогов);
#   banner_pattern - data/minecraft/banner_pattern/*.json (43 узора);
#   mob_effect - реестр сервера (39 эффектов) - для stew/consumable;
#   map_decoration_type - реестр сервера (36 типов);
#   звуковые события - реестр сервера (1968, здесь кураторская подборка).
# ---------------------------------------------------------------------------

JUKEBOX_SONGS = ["13", "cat", "blocks", "chirp", "far", "mall", "mellohi",
                 "stal", "strad", "ward", "11", "wait", "otherside",
                 "pigstep", "relic", "5", "creator", "creator_music_box",
                 "precipice", "tears", "bounce", "lava_chicken"]

INSTRUMENTS = ["admire_goat_horn", "call_goat_horn", "dream_goat_horn",
               "feel_goat_horn", "ponder_goat_horn", "seek_goat_horn",
               "sing_goat_horn", "yearn_goat_horn"]

# рог -> слово в родительном для имени-раскрытия: «Рог Тоски»
INSTRUMENT_RU = {
    "admire_goat_horn": "Восхищения", "call_goat_horn": "Зова",
    "dream_goat_horn": "Мечты", "feel_goat_horn": "Чувства",
    "ponder_goat_horn": "Раздумья", "seek_goat_horn": "Поиска",
    "sing_goat_horn": "Пения", "yearn_goat_horn": "Тоски",
}

BANNER_PATTERNS = ["base", "border", "bricks", "circle", "creeper",
                   "cross", "curly_border", "diagonal_left",
                   "diagonal_right", "diagonal_up_left",
                   "diagonal_up_right", "flow", "flower", "globe",
                   "gradient", "gradient_up", "guster", "half_horizontal",
                   "half_horizontal_bottom", "half_vertical",
                   "half_vertical_right", "mojang", "piglin", "rhombus",
                   "skull", "small_stripes", "square_bottom_left",
                   "square_bottom_right", "square_top_left",
                   "square_top_right", "straight_cross", "stripe_bottom",
                   "stripe_center", "stripe_downleft", "stripe_downright",
                   "stripe_left", "stripe_middle", "stripe_right",
                   "stripe_top", "triangle_bottom", "triangle_top",
                   "triangles_bottom", "triangles_top"]

# эффекты для suspicious_stew / consumable (реестр mob_effect 26.2)
MOB_EFFECTS = ["absorption", "bad_omen", "blindness",
               "breath_of_the_nautilus", "conduit_power", "darkness",
               "dolphins_grace", "fire_resistance", "glowing", "haste",
               "health_boost", "hero_of_the_village", "hunger", "infested",
               "instant_damage", "instant_health", "invisibility",
               "jump_boost", "levitation", "luck", "mining_fatigue",
               "nausea", "night_vision", "oozing", "poison", "raid_omen",
               "regeneration", "resistance", "saturation", "slow_falling",
               "slowness", "speed", "strength", "trial_omen", "unluck",
               "water_breathing", "weakness", "weaving", "wind_charged",
               "wither"]

# полный реестр map_decoration_type 26.2 (34 типа: маркеры игроков/рамок,
# цели, 16 цветных знамён, структуры и деревни) - раньше брали 17
MAP_DECORATION_TYPES = ["player", "frame", "red_marker", "blue_marker",
                        "target_x", "target_point", "player_off_map",
                        "player_off_limits", "red_x", "mansion",
                        "monument", "swamp_hut", "trial_chambers",
                        "village_desert", "village_plains",
                        "village_savanna", "village_snowy", "village_taiga",
                        "banner_white", "banner_orange", "banner_magenta",
                        "banner_light_blue", "banner_yellow", "banner_lime",
                        "banner_pink", "banner_gray", "banner_light_gray",
                        "banner_cyan", "banner_purple", "banner_blue",
                        "banner_brown", "banner_green", "banner_red",
                        "banner_black"]

# звуки для consumable/play_sound/kinetic_weapon (реестр sound_event)
SOUNDS = ["minecraft:entity.generic.drink", "minecraft:entity.player.burp",
          "minecraft:item.armor.equip_diamond",
          "minecraft:item.armor.equip_iron",
          "minecraft:item.armor.equip_gold",
          "minecraft:item.armor.equip_leather",
          "minecraft:item.armor.equip_netherite",
          "minecraft:item.shield.block", "minecraft:item.shield.break",
          "minecraft:item.mace.smash_ground", "minecraft:item.trident.hit",
          "minecraft:item.trident.throw", "minecraft:item.trident.return",
          "minecraft:block.note_block.pling",
          "minecraft:entity.player.levelup",
          "minecraft:block.enchantment_table.use",
          "minecraft:item.totem.use", "minecraft:block.bell.use",
          "minecraft:entity.enderman.teleport", "minecraft:item.crossbow.hit",
          "minecraft:item.crossbow.shoot",
          "minecraft:entity.player.attack.strong",
          "minecraft:entity.player.attack.nodamage",
          "minecraft:entity.evoker.cast_spell"]

DYE_COLORS = ["white", "orange", "magenta", "light_blue", "yellow", "lime",
              "pink", "gray", "light_gray", "cyan", "purple", "blue",
              "brown", "green", "red", "black"]

TROPICAL_FISH_PATTERNS = ["kob", "sunstreak", "snooper", "dasher",
                          "brinely", "spotty", "flopper", "glitter",
                          "blockfish", "betty", "clayfish", "stripey"]

HORSE_VARIANTS = ["white", "creamy", "chestnut", "brown", "black", "gray",
                  "dark_brown"]

# валидные блоки-состояния для block_state (только кураторские
# безопасные комбинации: свойство обязано существовать у блока)
BLOCK_STATE_PROPS = {
    "minecraft:beehive": {"honey_level": ["1", "3", "5"]},
    "minecraft:bee_nest": {"honey_level": ["2", "5"]},
    "minecraft:redstone_lamp": {"lit": ["true"]},
    "minecraft:campfire": {"lit": ["true", "false"]},
    "minecraft:respawn_anchor": {"charges": ["1", "2", "3", "4"]},
    "minecraft:composter": {"level": ["3", "6", "8"]},
    "minecraft:cauldron": {"level": ["1", "2", "3"]},
    "minecraft:farmland": {"moisture": ["1", "7"]},
    "minecraft:candle": {"lit": ["true"]},
    "minecraft:lantern": {"hanging": ["true", "false"]},
}

# контейнеры для container/container_loot/lock (+ медные сундуки 26.2:
# RandomizableContainer, как обычный сундук - держат NBT LootTable)
_COPPER_CHESTS = [
    "minecraft:copper_chest", "minecraft:exposed_copper_chest",
    "minecraft:weathered_copper_chest", "minecraft:oxidized_copper_chest",
    "minecraft:waxed_copper_chest",
    "minecraft:waxed_exposed_copper_chest",
    "minecraft:waxed_weathered_copper_chest",
    "minecraft:waxed_oxidized_copper_chest"]
CONTAINER_ITEMS = set(
    ["minecraft:barrel", "minecraft:chest", "minecraft:trapped_chest",
     "minecraft:dispenser", "minecraft:dropper", "minecraft:hopper",
     "minecraft:furnace", "minecraft:blast_furnace", "minecraft:smoker",
     "minecraft:brewing_stand", "minecraft:chest_minecart",
     "minecraft:hopper_minecart", "minecraft:decorated_pot",
     "minecraft:shulker_box", "minecraft:blue_shulker_box",
     "minecraft:red_shulker_box", "minecraft:purple_shulker_box"] +
    _COPPER_CHESTS +
    ["minecraft:%s_shulker_box" % c for c in DYE_COLORS])

# рыбные вёдра (bucket_entity_data + tropical_fish/*)
FISH_BUCKETS = {
    "minecraft:cod_bucket": "minecraft:cod",
    "minecraft:salmon_bucket": "minecraft:salmon",
    "minecraft:pufferfish_bucket": "minecraft:pufferfish",
    "minecraft:tropical_fish_bucket": "minecraft:tropical_fish",
    "minecraft:axolotl_bucket": "minecraft:axolotl",
    "minecraft:tadpole_bucket": "minecraft:tadpole",
}

# теги для tool.rules / repairable (все есть в jar 26.2)
TOOL_BLOCK_TAGS = ["minecraft:mineable/pickaxe", "minecraft:mineable/axe",
                   "minecraft:mineable/shovel", "minecraft:mineable/hoe",
                   "minecraft:logs", "minecraft:planks",
                   "minecraft:stone_bricks", "minecraft:wool",
                   "minecraft:dirt", "minecraft:sand"]
# варианты для repairable {items} - теги предметные ИЛИ списки id
# (теги вида iron_ingots/diamonds в 26.2 НЕ существуют - проверено!)
REPAIR_VARIANTS = [
    "#minecraft:planks", "#minecraft:logs", "#minecraft:wool",
    ["minecraft:iron_ingot"], ["minecraft:gold_ingot"],
    ["minecraft:diamond", "minecraft:emerald"],
    ["minecraft:copper_ingot"], ["minecraft:leather"],
    ["minecraft:string", "minecraft:phantom_membrane"]]

# «диковины» - предметы-носители редких компонентов (головы -> profile,
# книги -> *_book_content, улей -> bees, блоки -> block_state/note_block_sound)
ODDITIES = ["minecraft:player_head", "minecraft:creeper_head",
            "minecraft:zombie_head", "minecraft:skeleton_skull",
            "minecraft:written_book", "minecraft:writable_book",
            "minecraft:note_block", "minecraft:beehive",
            "minecraft:bee_nest", "minecraft:dragon_egg", "minecraft:bell"]

# ---------------------------------------------------------------------------
# Генератор имён (русский). Согласование родов: прилагательные заданы
# кортежем (м, ж, ср, мн).
# ---------------------------------------------------------------------------

_ADJ = [
    ("Пепельный", "Пепельная", "Пепельное", "Пепельные"),
    ("Тлеющий", "Тлеющая", "Тлеющее", "Тлеющие"),
    ("Ржавый", "Ржавая", "Ржавое", "Ржавые"),
    ("Полированный", "Полированная", "Полированное", "Полированные"),
    ("Зазубренный", "Зазубренная", "Зазубренное", "Зазубренные"),
    ("Поющий", "Поющая", "Поющее", "Поющие"),
    ("Шепчущий", "Шепчущая", "Шепчущее", "Шепчущие"),
    ("Молчаливый", "Молчаливая", "Молчаливое", "Молчаливые"),
    ("Голодный", "Голодная", "Голодное", "Голодные"),
    ("Жующийся", "Жующаяся", "Жующееся", "Жующиеся"),
    ("Спящий", "Спящая", "Спящее", "Спящие"),
    ("Слепой", "Слепая", "Слепое", "Слепые"),
    ("Дикий", "Дикая", "Дикое", "Дикие"),
    ("Забытый", "Забытая", "Забытое", "Забытые"),
    ("Краденый", "Краденая", "Краденое", "Краденые"),
    ("Разбитый", "Разбитая", "Разбитое", "Разбитые"),
    ("Кривой", "Кривая", "Кривое", "Кривые"),
    ("Ледяной", "Ледяная", "Ледяное", "Ледяные"),
    ("Плачущий", "Плачущая", "Плачущее", "Плачущие"),
    ("Утонувший", "Утонувшая", "Утонувшее", "Утонувшие"),
    ("Солёный", "Солёная", "Солёное", "Солёные"),
    ("Святой", "Святая", "Святое", "Святые"),
    ("Проклятый", "Проклятая", "Проклятое", "Проклятые"),
    ("Царский", "Царская", "Царское", "Царские"),
    ("Драконий", "Драконья", "Драконье", "Драконьи"),
    ("Змеиный", "Змеиная", "Змеиное", "Змеиные"),
    ("Волчий", "Волчья", "Волчье", "Волчьи"),
    ("Вороний", "Воронья", "Воронье", "Вороньи"),
    ("Крысиный", "Крысиная", "Крысиное", "Крысиные"),
    ("Лунный", "Лунная", "Лунное", "Лунные"),
    ("Солнечный", "Солнечная", "Солнечное", "Солнечные"),
    ("Туманный", "Туманная", "Туманное", "Туманные"),
    ("Громовой", "Громовая", "Громовое", "Громовые"),
    ("Костяной", "Костяная", "Костяное", "Костяные"),
    ("Смоляной", "Смоляная", "Смоляное", "Смоляные"),
    ("Стеклянный", "Стеклянная", "Стеклянное", "Стеклянные"),
    ("Зеркальный", "Зеркальная", "Зеркальное", "Зеркальные"),
    ("Медный", "Медная", "Медное", "Медные"),
    ("Золотой", "Золотая", "Золотое", "Золотые"),
    ("Бумажный", "Бумажная", "Бумажное", "Бумажные"),
    ("Бархатный", "Бархатная", "Бархатное", "Бархатные"),
    ("Гнилой", "Гнилая", "Гнилое", "Гнилые"),
    ("Мёртвый", "Мёртвая", "Мёртвое", "Мёртвые"),
    ("Полый", "Полая", "Полое", "Полые"),
    ("Тяжёлый", "Тяжёлая", "Тяжёлое", "Тяжёлые"),
    ("Невесомый", "Невесомая", "Невесомое", "Невесомые"),
    ("Тихий", "Тихая", "Тихое", "Тихие"),
    ("Вечный", "Вечная", "Вечное", "Вечные"),
    ("Мимолётный", "Мимолётная", "Мимолётное", "Мимолётные"),
    ("Последний", "Последняя", "Последнее", "Последние"),
    ("Бессонный", "Бессонная", "Бессонное", "Бессонные"),
    ("Хромой", "Хромая", "Хромое", "Хромые"),
    ("Сытый", "Сытая", "Сытое", "Сытые"),
    ("Косой", "Косая", "Косое", "Косые"),
    ("Жареный", "Жареная", "Жареное", "Жареные"),
    ("Горький", "Горькая", "Горькое", "Горькие"),
    ("Благословенный", "Благословенная", "Благословенное", "Благословенные"),
    ("Воровской", "Воровская", "Воровское", "Воровские"),
    ("Лебединый", "Лебединая", "Лебединое", "Лебединые"),
    ("Жабий", "Жабья", "Жабье", "Жабьи"),
    ("Улиточный", "Улиточная", "Улиточное", "Улиточные"),
    # --- материалы и огранка ---
    ("Обсидиановый", "Обсидиановая", "Обсидиановое", "Обсидиановые"),
    ("Гранитный", "Гранитная", "Гранитное", "Гранитные"),
    ("Мраморный", "Мраморная", "Мраморное", "Мраморные"),
    ("Базальтовый", "Базальтовая", "Базальтовое", "Базальтовые"),
    ("Вулканический", "Вулканическая", "Вулканическое", "Вулканические"),
    ("Алмазный", "Алмазная", "Алмазное", "Алмазные"),
    ("Яшмовый", "Яшмовая", "Яшмовое", "Яшмовые"),
    ("Ониксовый", "Ониксовая", "Ониксовое", "Ониксовые"),
    ("Кварцевый", "Кварцевая", "Кварцевое", "Кварцевые"),
    ("Свинцовый", "Свинцовая", "Свинцовое", "Свинцовые"),
    ("Оловянный", "Оловянная", "Оловянное", "Оловянные"),
    ("Стальной", "Стальная", "Стальное", "Стальные"),
    ("Бронзовый", "Бронзовая", "Бронзовое", "Бронзовые"),
    ("Серебряный", "Серебряная", "Серебряное", "Серебряные"),
    ("Позолоченный", "Позолоченная", "Позолоченное", "Позолоченные"),
    ("Посеребрённый", "Посеребрённая", "Посеребрённое", "Посеребрённые"),
    ("Чернёный", "Чернёная", "Чернёное", "Чернёные"),
    ("Литой", "Литая", "Литое", "Литые"),
    ("Кованый", "Кованая", "Кованое", "Кованые"),
    ("Чеканный", "Чеканная", "Чеканное", "Чеканные"),
    ("Резной", "Резная", "Резное", "Резные"),
    ("Витой", "Витая", "Витое", "Витые"),
    ("Клёпаный", "Клёпаная", "Клёпаное", "Клёпаные"),
    ("Игольчатый", "Игольчатая", "Игольчатое", "Игольчатые"),
    ("Гранёный", "Гранёная", "Гранёное", "Гранёные"),
    # --- износ и сохранность ---
    ("Треснувший", "Треснувшая", "Треснувшее", "Треснувшие"),
    ("Потёртый", "Потёртая", "Потёртое", "Потёртые"),
    ("Обшарпанный", "Обшарпанная", "Обшарпанное", "Обшарпанные"),
    ("Изношенный", "Изношенная", "Изношенное", "Изношенные"),
    ("Обгорелый", "Обгорелая", "Обгорелое", "Обгорелые"),
    ("Обмёрзлый", "Обмёрзлая", "Обмёрзлое", "Обмёрзлые"),
    ("Заплесневелый", "Заплесневелая", "Заплесневелое", "Заплесневелые"),
    ("Окисленный", "Окисленная", "Окисленное", "Окисленные"),
    ("Закопчённый", "Закопчённая", "Закопчённое", "Закопчённые"),
    ("Истлевший", "Истлевшая", "Истлевшее", "Истлевшие"),
    ("Истрёпанный", "Истрёпанная", "Истрёпанное", "Истрёпанные"),
    ("Потрескавшийся", "Потрескавшаяся", "Потрескавшееся",
     "Потрескавшиеся"),
    ("Дырявый", "Дырявая", "Дырявое", "Дырявые"),
    ("Промокший", "Промокшая", "Промокшее", "Промокшие"),
    ("Замёрзший", "Замёрзшая", "Замёрзшее", "Замёрзшие"),
    ("Тусклый", "Тусклая", "Тусклое", "Тусклые"),
    ("Блёклый", "Блёклая", "Блёклое", "Блёклые"),
    # --- возраст и происхождение ---
    ("Старинный", "Старинная", "Старинное", "Старинные"),
    ("Вековой", "Вековая", "Вековое", "Вековые"),
    ("Ископаемый", "Ископаемая", "Ископаемое", "Ископаемые"),
    ("Легендарный", "Легендарная", "Легендарное", "Легендарные"),
    ("Сказочный", "Сказочная", "Сказочное", "Сказочные"),
    ("Былинный", "Былинная", "Былинное", "Былинные"),
    # --- чары и святость ---
    ("Зачарованный", "Зачарованная", "Зачарованное", "Зачарованные"),
    ("Заколдованный", "Заколдованная", "Заколдованное", "Заколдованные"),
    ("Заговорённый", "Заговорённая", "Заговорённое", "Заговорённые"),
    ("Наговорённый", "Наговорённая", "Наговорённое", "Наговорённые"),
    ("Приворотный", "Приворотная", "Приворотное", "Приворотные"),
    ("Призрачный", "Призрачная", "Призрачное", "Призрачные"),
    ("Освящённый", "Освящённая", "Освящённое", "Освящённые"),
    ("Осквернённый", "Осквернённая", "Осквернённое", "Осквернённые"),
    ("Погребальный", "Погребальная", "Погребальное", "Погребальные"),
    ("Адский", "Адская", "Адское", "Адские"),
    ("Райский", "Райская", "Райское", "Райские"),
    # --- звуки ---
    ("Звенящий", "Звенящая", "Звенящее", "Звенящие"),
    ("Гудящий", "Гудящая", "Гудящее", "Гудящие"),
    ("Трещащий", "Трещащая", "Трещащее", "Трещащие"),
    ("Скрипучий", "Скрипучая", "Скрипучее", "Скрипучие"),
    ("Стонущий", "Стонущая", "Стонущее", "Стонущие"),
    ("Ревущий", "Ревущая", "Ревущее", "Ревущие"),
    ("Грохочущий", "Грохочущая", "Грохочущее", "Грохочущие"),
    ("Жужжащий", "Жужжащая", "Жужжащее", "Жужжащие"),
    ("Сверлящий", "Сверлящая", "Сверлящее", "Сверлящие"),
    # --- свет ---
    ("Светящийся", "Светящаяся", "Светящееся", "Светящиеся"),
    ("Блестящий", "Блестящая", "Блестящее", "Блестящие"),
    ("Сияющий", "Сияющая", "Сияющее", "Сияющие"),
    ("Меркнущий", "Меркнущая", "Меркнущее", "Меркнущие"),
    ("Гаснущий", "Гаснущая", "Гаснущее", "Гаснущие"),
    # --- силы и повадки ---
    ("Неподъёмный", "Неподъёмная", "Неподъёмное", "Неподъёмные"),
    ("Неудержимый", "Неудержимая", "Неудержимое", "Неудержимые"),
    ("Неукротимый", "Неукротимая", "Неукротимое", "Неукротимые"),
    ("Неутомимый", "Неутомимая", "Неутомимое", "Неутомимые"),
    ("Неодолимый", "Неодолимая", "Неодолимое", "Неодолимые"),
    ("Летучий", "Летучая", "Летучее", "Летучие"),
    ("Парящий", "Парящая", "Парящее", "Парящие"),
    ("Быстрый", "Быстрая", "Быстрое", "Быстрые"),
    ("Проворный", "Проворная", "Проворное", "Проворные"),
    ("Ловкий", "Ловкая", "Ловкое", "Ловкие"),
    ("Скользкий", "Скользкая", "Скользкое", "Скользкие"),
    # --- нрав ---
    ("Суровый", "Суровая", "Суровое", "Суровые"),
    ("Строгий", "Строгая", "Строгое", "Строгие"),
    ("Угрюмый", "Угрюмая", "Угрюмое", "Угрюмые"),
    ("Хмурый", "Хмурая", "Хмурое", "Хмурые"),
    ("Ворчливый", "Ворчливая", "Ворчливое", "Ворчливые"),
    ("Надменный", "Надменная", "Надменное", "Надменные"),
    ("Высокомерный", "Высокомерная", "Высокомерное", "Высокомерные"),
    ("Спесивый", "Спесивая", "Спесивое", "Спесивые"),
    ("Скупой", "Скупая", "Скупое", "Скупые"),
    ("Щедрый", "Щедрая", "Щедрое", "Щедрые"),
    ("Роскошный", "Роскошная", "Роскошное", "Роскошные"),
    ("Убогий", "Убогая", "Убогое", "Убогие"),
    ("Великий", "Великая", "Великое", "Великие"),
    ("Крошечный", "Крошечная", "Крошечное", "Крошечные"),
    ("Громадный", "Громадная", "Громадное", "Громадные"),
    ("Исполинский", "Исполинская", "Исполинское", "Исполинские"),
    # --- места ---
    ("Заброшенный", "Заброшенная", "Заброшенное", "Заброшенные"),
    ("Опустевший", "Опустевшая", "Опустевшее", "Опустевшие"),
    ("Покинутый", "Покинутая", "Покинутое", "Покинутые"),
    ("Дальний", "Дальняя", "Дальнее", "Дальние"),
    ("Прибрежный", "Прибрежная", "Прибрежное", "Прибрежные"),
    ("Морской", "Морская", "Морское", "Морские"),
    ("Речной", "Речная", "Речное", "Речные"),
    ("Озёрный", "Озёрная", "Озёрное", "Озёрные"),
    ("Болотный", "Болотная", "Болотное", "Болотные"),
    # --- вкус и тепло ---
    ("Жгучий", "Жгучая", "Жгучее", "Жгучие"),
    ("Обжигающий", "Обжигающая", "Обжигающее", "Обжигающие"),
    ("Горячий", "Горячая", "Горячее", "Горячие"),
    ("Пряный", "Пряная", "Пряное", "Пряные"),
    ("Кислый", "Кислая", "Кислое", "Кислые"),
    ("Сладкий", "Сладкая", "Сладкое", "Сладкие"),
    ("Душистый", "Душистая", "Душистое", "Душистые"),
    ("Медовый", "Медовая", "Медовое", "Медовые"),
    ("Хмельной", "Хмельная", "Хмельное", "Хмельные"),
    ("Жёваный", "Жёваная", "Жёваное", "Жёваные"),
    ("Твёрдый", "Твёрдая", "Твёрдое", "Твёрдые"),
    ("Мягкий", "Мягкая", "Мягкое", "Мягкие"),
    # --- диковины и ценность ---
    ("Странный", "Странная", "Странное", "Странные"),
    ("Чуждый", "Чуждая", "Чуждое", "Чуждые"),
    ("Нездешний", "Нездешняя", "Нездешнее", "Нездешние"),
    ("Диковинный", "Диковинная", "Диковинное", "Диковинные"),
    ("Невиданный", "Невиданная", "Невиданное", "Невиданные"),
    ("Небывалый", "Небывалая", "Небывалое", "Небывалые"),
    ("Бесценный", "Бесценная", "Бесценное", "Бесценные"),
    ("Дешёвый", "Дешёвая", "Дешёвое", "Дешёвые"),
    ("Поддельный", "Поддельная", "Поддельное", "Поддельные"),
    ("Злобный", "Злобная", "Злобное", "Злобные"),
    ("Ядовитый", "Ядовитая", "Ядовитое", "Ядовитые"),
    ("Смертоносный", "Смертоносная", "Смертоносное", "Смертоносные"),
    ("Кровожадный", "Кровожадная", "Кровожадное", "Кровожадные"),
    ("Славный", "Славная", "Славное", "Славные"),
    ("Удалой", "Удалая", "Удалое", "Удалые"),
    ("Ратный", "Ратная", "Ратное", "Ратные"),
    ("Княжеский", "Княжеская", "Княжеское", "Княжеские"),
    ("Квасной", "Квасная", "Квасное", "Квасные"),
]

# существительные по типу предмета: (слово, род) - м/ж/ср/мн
_KIND_NOUNS = {
    "sword":     [("Клинок", "м"), ("Бритва", "ж"), ("Жало", "ср"),
                  ("Клык", "м"), ("Резак", "м"), ("Шип", "м"),
                  ("Осколок", "м"), ("Перо", "ср"),
                  ("Остриё", "ср"), ("Лезвие", "ср")],
    "spear":     [("Копьё", "ср"), ("Пика", "ж"), ("Шест", "м"),
                  ("Жало", "ср"), ("Игла", "ж"), ("Рогатина", "ж")],
    "axe":       [("Секира", "ж"), ("Топорище", "ср"), ("Раскол", "м"),
                  ("Громила", "м"), ("Тесак", "м"), ("Колун", "м")],
    "mace":      [("Булава", "ж"), ("Молот", "м"), ("Громобой", "м"),
                  ("Кулак", "м"), ("Шестопёр", "м")],
    "pickaxe":   [("Кирка", "ж"), ("Резец", "м"), ("Бур", "м"),
                  ("Кайло", "ср"), ("Заступ", "м")],
    "shovel":    [("Лопата", "ж"), ("Ковш", "м"), ("Совок", "м"),
                  ("Черпак", "м")],
    "hoe":       [("Мотыга", "ж"), ("Грабли", "мн"), ("Коса", "ж"),
                  ("Тяпка", "ж")],
    "bow":       [("Лук", "м"), ("Тетива", "ж"), ("Дуга", "ж"),
                  ("Лучок", "м")],
    "crossbow":  [("Самострел", "м"), ("Арбалет", "м"),
                  ("Пищаль", "ж")],
    "trident":   [("Трезубец", "м"), ("Вилка", "ж"), ("Острога", "ж")],
    "fishing_rod": [("Удочка", "ж"), ("Поплавок", "м"),
                     ("Закидушка", "ж")],
    "helmet":    [("Венец", "м"), ("Череп", "м"), ("Каска", "ж"),
                  ("Кокошник", "м"), ("Тара", "ж"), ("Шлем", "м"),
                  ("Ушанка", "ж")],
    "chestplate": [("Панцирь", "м"), ("Кираса", "ж"), ("Кожух", "м"),
                   ("Броня", "ж"), ("Раковина", "ж"), ("Кольчуга", "ж"),
                   ("Латы", "мн")],
    "leggings":  [("Поножи", "мн"), ("Гамаши", "мн"), ("Штаны", "мн"),
                  ("Портки", "мн")],
    "boots":     [("Сапоги", "мн"), ("Ботинки", "мн"), ("Лапти", "мн"),
                  ("Ступни", "мн"), ("Валенки", "мн")],
    "elytra":    [("Плащ", "м"), ("Крылья", "мн"), ("Крыло", "ср"),
                  ("Крылышки", "мн")],
    "shield":    [("Щит", "м"), ("Стена", "ж"), ("Крышка", "ж"),
                  ("Заслон", "м")],
    "book":      [("Том", "м"), ("Фолиант", "м"), ("Гримуар", "м"),
                  ("Хроника", "ж"), ("Тетрадь", "ж"), ("Свиток", "м"),
                  ("Кодекс", "м"), ("Рукопись", "ж"), ("Летопись", "ж"),
                  ("Скрижаль", "ж")],
    "potion":    [("Зелье", "ср"), ("Настой", "м"), ("Отвар", "м"),
                  ("Эликсир", "м"), ("Микстура", "ж"), ("Настойка", "ж"),
                  ("Брага", "ж"), ("Пойло", "ср")],
    "generic":   [("Осколок", "м"), ("Пыль", "ж"), ("Слеза", "ж"),
                  ("Артефакт", "м"), ("Реликвия", "ж"), ("Безделушка", "ж"),
                  ("Штука", "ж"), ("Подарок", "м"), ("Диковина", "ж"),
                  ("Утварь", "ж"), ("Оберег", "м"), ("Талисман", "м"),
                  ("Черепок", "м"), ("Цацка", "ж"), ("Штуковина", "ж")],
}

# родительный падеж: «<Существительное> <Родительный>»
_GENITIVE = [
    "Пепельного Рассвета", "Забытого Короля", "Утонувшей Луны",
    "Мёртвой Звезды", "Первого Снега", "Спящего Вулкана",
    "Гнилого Королевства", "Слепого Бога", "Трёх Лун", "Вечного Голода",
    "Тихой Ярости", "Последнего Дракона", "Жующейся Бездны",
    "Полуночного Солнца", "Ржавого Принца", "Потерянной Карты",
    "Каменного Сна", "Стеклянного Моря", "Костяного Сада",
    "Плачущей Скалы", "Одинокого Маяка", "Бумажного Тигра",
    "Медного Пророка", "Свечного Короля", "Заячьей Храбрости",
    "Волчьей Зимы", "Вишнёвого Сада", "Мешка Соли", "Голубой Пустоты",
    "Двух Бездомных Псов", "Тёплого Пепла", "Старого Штурмана",
    "Мокрого Пороха", "Сломанной Клятвы", "Немого Певца",
    "Пятнадцатой Зимы", "Украденной Короны", "Пустого Трона",
    "Гостя Из Глубин", "Торговца Погасших Свечей", "Двоюродного Демона",
    "Забытых Богов", "Голодного Ветра", "Спящего Портного",
    "Последнего Свидетеля", "Моста В Никуда", "Полынной Полночи",
    "Смолёной Лодки", "Треснувшего Колокола", "Рваной Карты",
    # --- пополнение: жнецы, мельницы, сказки ---
    "Багрового Жнеца", "Студёной Зари", "Сломанного Компаса",
    "Затонувшего Города", "Спящего Лешего", "Безымянного Коваля",
    "Тихой Гавани", "Голодной Стаи", "Слепого Часовщика",
    "Медного Быка", "Стеклянного Дождя", "Костяного Кита",
    "Пепельной Зари", "Потерянного Штопора", "Северного Ветра",
    "Полуночного Гонца", "Дальней Тропы", "Старой Крепости",
    "Забытой Шахты", "Кривого Зеркала", "Ржавого Якоря",
    "Мёртвой Реки", "Сплюснутой Луны", "Морской Тоски",
    "Висячего Моста", "Заброшенной Мельницы", "Последнего Дозора",
    "Ночной Вахты", "Вечного Скитальца", "Пустого Колодца",
    "Глубокого Снега", "Дикого Мёда", "Краденой Луны",
    "Украденной Весны", "Проданной Тени", "Обещанного Золота",
    "Невыплаченного Долга", "Последней Битвы", "Диких Троп",
    "Глухого Леса", "Дремучего Бора", "Тёмной Чащи",
    "Болотных Огней", "Полярной Ночи", "Затяжного Дождя",
    "Короткого Лета", "Долгой Зимы", "Горькой Полыни",
    "Мятного Чая", "Древней Клятвы", "Тайного Сговора",
    "Потайного Хода", "Запертой Двери", "Потерянного Ключа",
    "Собачьей Верности", "Заячьей Души", "Медвежьей Силы",
    "Рыбьей Памяти", "Слоновьей Кости", "Лебяжьего Пуха",
    "Соловьиной Ночи", "Жабьей Слизи", "Кислых Щей",
    "Пустых Обещаний", "Бабушкиных Сказок", "Ночных Кошмаров",
    "Дурных Примет", "Плохой Погоды", "Тридесятого Царства",
    "Кощеевой Смерти", "Курьих Ножек", "Жар-Птицы",
    "Серого Волка", "Золотой Рыбки", "Костяной Ноги",
    "Мёртвой Головы", "Стеклянных Бус", "Утонувшего Колокола",
    "Звериного Оскала", "Крокодильих Слёз", "Кошачьей Лени",
    "Собачьей Жары", "Старого Пня", "Иван-Чая",
    "Дальнего Берега", "Ближнего Болота", "Морского Царя",
    "Золотой Осени", "Древней Смуты", "Лихолетья",
    "Недоброго Часа", "Кривой Улыбки", "Косого Дождя",
    "Мокрого Снега", "Драной Кошки", "Первого Мороза",
    "Кровной Мести", "Одноногого Пирата", "Бабы-Яги",
]

# вторая половина для дефисных имён («Клинок-Птица»)
_HYPHEN_WORDS = ["Птица", "Гроза", "Мамонт", "Вихрь", "Комета", "Смерть",
                 "Заря", "Боль", "Ужин", "Тишина", "Ярость", "Скука",
                 "Печаль", "Молния", "Бабочка", "Кит", "Осы", "Полночь",
                 # --- пополнение ---
                 "Гром", "Ветер", "Звезда", "Луна", "Солнце", "Волк",
                 "Медведь", "Лис", "Ворон", "Сокол", "Змея", "Краб",
                 "Жаба", "Сова", "Филин", "Паук", "Ёж", "Пчела",
                 "Спрут", "Тоска", "Слеза", "Искра", "Зенит", "Курган",
                 "Маяк", "Костёр", "Свеча", "Буря", "Град", "Ливень",
                 "Стужа", "Зной", "Морок", "Дух", "Призрак", "Тень",
                 "Сон", "Грёза", "Рок", "Судьба", "Месть", "Кара",
                 "Гнев", "Хандра", "Наковальня"]

# слоги для «собственных имён» артефактов («Гхарзул»)
_NAME_SYLL = ["Гхар", "зул", "мор", "вен", "ак", "хольт", "дро", "вир",
              "эн", "тар", "шек", "уру", "кай", "лосс", "мей", "но", "ри",
              "тум", "бар", "грим", "ста", "вель", "орн", "иш", "пад",
              "вор", "гло", "дай", "жун", "зор", "крад", "лу", "мар",
              "нур", "окс", "раз", "трог", "уд", "фар", "хаз", "чур",
              "щур", "юр", "ам", "ем", "ир", "ом", "ун", "эр", "юс",
              "бек"]

# цвета текста имён (именованные - как в чате, или hex)
_NAME_COLORS = ["gold", "gold", "aqua", "aqua", "light_purple",
                "light_purple", "red", "yellow", "green", "dark_aqua",
                "dark_purple", "dark_red", "blue", "white"]

# строки лора (flavor)
_LORE_LINES = [
    "Пахнет дымом и старостью.", "Найдено в пыли забытых залов.",
    "Предыдущий владелец не выжил.", "Тёплое на ощупь.",
    "Шепчет по ночам.", "Не роняй.", "Сделано неизвестным мастером.",
    "Слишком острое для осторожных.", "Метка мастера стёрлась.",
    "Внутри что-то гремит.", "Проклято. Наверное.",
    "Кто-то очень старался.", "Помнит прошлое. Не спрашивай.",
    "Слегка дымится.", "Продано дважды. Оба раза - тайно.",
    "Держи крепче.", "Ему одиноко.", "Счёт гномов на внутренней стороне.",
    "Пахнет мокрым камнем.", "Тяжелее, чем кажется.",
    "Украдено у того, кто не заметил.", "Точить бесполезно.",
    # --- пополнение ---
    "Пахнет грозой.", "Хранит тепло чужих рук.",
    "Внутри гудит, как улей.", "Точильщик отказался его точить.",
    "Продавец плакал, отдавая его.", "Оно снится прежнему хозяину.",
    "Метка на рукояти затёрта.", "Отражает не то, что перед ним.",
    "Тяжелеет перед бедой.", "Его не берут ни воры, ни вороны.",
    "Помнит вкус первой крови.", "Шевелится, когда никто не смотрит.",
    "Найдено в желудке рыбы.", "Им заколачивали дверь. Изнутри.",
    "Умеет ждать.", "О нём молчат в тавернах.",
    "Старше города, в котором найдено.", "Пахнет полынью и дымом.",
    "Служило трём королям. Всем - плохо.", "Его боится огонь.",
    "От него шарахаются лошади.", "Роса на нём не высыхает.",
    "Оставлено на перекрёстке. Зря.", "Кто его потерял - тот рад.",
    "Найдётся само. Когда захочет.", "Говорят, оно из-под земли.",
    "Им нельзя бить по своему отражению.", "Теплеет перед рассветом.",
    "Считает дни до новолуния.", "Отпечаток ладони на лезвии.",
    "Его чистят, а оно темнеет.", "Пахнет снегом посреди лета.",
]

# страницы книг (written/writable_book_content): короткий русский
# флейвор - 1-2 предложения на страницу, из них собирается «дневник».
# В text-компонентах страниц 26.2 разрешены text/color/italic/bold
_BOOK_PAGE_SENTENCES = [
    "День третий. Дождь не прекращается.",
    "Слышал шаги за стеной. Проверять не стал.",
    "Мел истончился. Осталась половина.",
    "Съел последний сухарь. На вкус - бумага.",
    "Карта врёт: реки здесь нет.",
    "Факелы тают быстрее, чем я иду.",
    "Ночью стены дышали. Я не спал.",
    "Сосед по лагерю исчез вместе с сапогами.",
    "Ключ подошёл не с первого раза.",
    "Заблудился в собственных заметках.",
    "Оставил зарубку на третьем повороте.",
    "Кто-то дописал страницу за меня.",
    "Мост обрушился ещё до дождей.",
    "Здесь эхо отзывается на имя.",
    "Печь всё ещё тёплая. Значит, я не первый.",
    "Не считай звёзды - их тут больше, чем нужно.",
    "Соль кончилась. Суп теперь мстит.",
    "Дракон был стар. Старше этой записи.",
    "Спустился ниже - и забыл, зачем.",
    "Свет меркнет, когда я отворачиваюсь.",
    "Выменял компас на ужин. Не жалею.",
    "Сундук был пуст. Кроме письма.",
    "Письмо не буду переписывать сюда.",
    "Вернусь за киркой. Если вернусь.",
    "Считаю шаги, чтобы не сойти с ума.",
    "Сегодня ветер пах солью и медью.",
    "Оставил монету на удачу. Не помогло.",
    "Внизу кто-то поёт. Без слов.",
    "Записываю, пока горит свеча.",
    "Эта страница - последняя чистая.",
    # --- пополнение: странники, глубины, звёзды, долгие зимы ---
    "День седьмой. Ветер не меняет направления.",
    "Нашёл гвоздь. Прибил к столу - спокойнее.",
    "Компас показывает вниз.",
    "Сосед считает звёзды. Сбивается и злится.",
    "Мороз нарисовал на стекле чей-то профиль.",
    "Свеча коптит влево. Всегда влево.",
    "Здесь не поют петухи. Совсем.",
    "Видел свет между корнями. Не полез.",
    "Костёр разгорается только от щепок.",
    "Кролик смотрел на меня как на равного.",
    "Болото дышит. Я записываю ритм.",
    "Дождь идёт столбом в сотне шагов.",
    "Под мостом кто-то считает прохожих.",
    "Отражение в воде запаздывает.",
    "Собака скулит на север.",
    "Из старой шахты тянет тёплым.",
    "Записал три новых слова. Значит, был не один.",
    "Хлеб черствеет за ночь до камня.",
    "Указатель с двумя стрелками. Обе вниз.",
    "Луна висит ниже обычного.",
    "Тень от костра падает против огня.",
    "Мельница крутится без ветра.",
    "Стая кружит над одним местом.",
    "Ночью всё звучит на октаву ниже.",
    "Карта нарисовала вторую реку.",
    "Сыр не плесневеет. Это подозрительно.",
    "Кот уходит на охоту и возвращается с лилией.",
    "Следы обрываются на середине поля.",
    "Гвозди в стенах повернулись на восток.",
    "Соловей разучил чужую песню.",
    "Колодец отвечает раньше вопроса.",
    "Паутина серебрится в полночь.",
    "Смола на деревьях застыла свечами.",
    "Утром у входа подарок: мышь, травинка, ключ.",
    "Рыба в ручье плывёт вверх.",
    "Облако стоит над холмом третий день.",
    "Муравьи обходят лагерь по кругу.",
    "Лёд на реке трескается по буквам.",
    "Видел во сне эту страницу.",
    "У костра оставляю монету. Не воруют.",
    "Пахнет яблоками. Яблонь здесь нет.",
    "Стрекоза села на удочку и не улетает.",
    "Дым уходит в землю.",
    "Шёпот за спиной зовёт меня по имени. С ошибкой.",
    "Книга сама открывается на этой странице.",
    "Снег ложится квадратами.",
    "Лужи замерзают от середины.",
    "Волки воют на молчание.",
    "Ступени вниз шире, чем вверх.",
    "Фонарь на холме гаснет, когда смотрю.",
    "Ель у тропы шелестит без ветра.",
    "На рассвете весь мир секунду стоит.",
    "Печь гудит чужим голосом.",
    "Мел кончился. Пишу углём.",
    "Звёзды складываются в спираль.",
    "Тетрадь тяжелеет с каждой страницей.",
    "Часы соседа тикают в такт моему сердцу.",
    "Пыль в луче света падает вверх.",
    "Сухарь с царапиной. В царапине - соль.",
    "Мой дневник читают. Я не против.",
    "Коза смотрит с укором. Проверил: не моя.",
    "Печка благодарно гудит. За что - не спрашиваю.",
    "Зима длинная. Записей хватит.",
]

# чернила страниц (бумага светлая - тёмная палитра, как в ванильных книгах)
_BOOK_PAGE_COLORS = ["black", "dark_gray", "gray", "dark_blue",
                     "dark_green", "dark_aqua", "dark_red", "dark_purple",
                     "blue"]

# ---------------------------------------------------------------------------
# Вспомогательные распределения
# ---------------------------------------------------------------------------

_GENDER_IDX = {"м": 0, "ж": 1, "ср": 2, "мн": 3}


# ---------------------------------------------------------------------------
# ЖЁСТКИЕ КАПЫ (жалоба: «слишком много rolls - контейнеры ПУСТЫЕ от
# передозировки, игра ВИСНЕТ после убийства моба»). Проверяются
# самотестом на КАЖДОЙ таблице; генерация ниже никогда их не превышает
# (капы - не «подрезка после», а форма распределений)
# ---------------------------------------------------------------------------
CAP_MAX_POOLS = 8      # пулов в таблице - не больше
CAP_MAX_ROLLS = 6.0    # rolls любого пула (и min, и max провайдера)
CAP_MAX_BONUS = 2.0    # bonus_rolls (иногда 1-2, только не-mob пулы)
CAP_MAX_ITEMS_MOB = 6  # суммарный предел предметов с одного убийства
CAP_NESTED_PER_TABLE = 2  # loot_table-записей на таблицу (глубина <= 1)


def _clamped_rolls(rng, lo, hi):
    """Число ИЛИ uniform-провайдер в [lo; hi], зажатый в глобальный
    кап CAP_MAX_ROLLS (и min >= 1 - роллы никогда не обнуляют пул)."""
    hi = min(hi, CAP_MAX_ROLLS)
    lo = max(1.0, min(lo, hi))
    if rng.random() < 0.55:
        return float(rng.randint(int(lo), int(hi)))
    return {"type": "minecraft:uniform",
            "min": float(lo), "max": float(hi)}


def _rolls(rng, tier=None):
    """rolls пула - дифференцировано ПО ТИПУ ТАБЛИЦЫ (мобы не дропают
    горы вещей, сундуки щедрее мусорок, сокровища - самые богатые),
    ВСЕГДА в глобальном капе <= CAP_MAX_ROLLS и с min >= 1:
      tier="mob"      - дроп моба: 1-2;
      tier="chest"    - сундук: 1-4 (в среднем ~2-3);
      tier="treasure" - сокровище: 2-6 (самые богатые);
      tier=None       - прочие (gift/fishing/equipment/archaeology/
                        barter): 1-4, изредка до 6."""
    r = rng.random()
    if tier == "mob":
        if r < 0.70:
            return float(rng.randint(1, 2))
        return {"type": "minecraft:uniform", "min": 1.0, "max": 2.0}
    if tier == "chest":
        if r < 0.45:
            return float(rng.randint(1, 3))
        return _clamped_rolls(rng, 1.0, 4.0)
    if tier == "treasure":
        if r < 0.50:
            return float(rng.randint(2, 4))
        return _clamped_rolls(rng, 2.0, 6.0)
    if r < 0.60:
        return float(rng.randint(1, 3))
    if r < 0.90:
        return _clamped_rolls(rng, 1.0, 4.0)
    return _clamped_rolls(rng, 1.0, 6.0)


def _pool_count(rng, tier=None):
    """Сколько пулов у таблицы тира (жёстко <= CAP_MAX_POOLS):
      mob - 1-2; chest - 3-6; treasure - 4-8; None - 2-5.
    Прежний «тяжёлый хвост» до 100 пулов убран (жалоба на передоз
    rolls - богатство теперь в ТЕМАХ и разнообразии записей, а не в
    количестве роллов)."""
    if tier == "mob":
        return rng.randint(1, 2)
    if tier == "chest":
        return rng.randint(3, 6)
    if tier == "treasure":
        return rng.randint(4, CAP_MAX_POOLS)
    return rng.randint(2, 5)


def _num_provider(rng, lo, hi):
    """NumberProvider (uniform / binomial / константа) - формат как в
    ванильных set_count."""
    r = rng.random()
    if r < 0.55:
        a = float(rng.randint(lo, hi))
        return {"type": "minecraft:uniform",
                "min": a, "max": float(rng.randint(max(lo, int(a)), hi))}
    if r < 0.75:
        return {"type": "minecraft:binomial",
                "n": float(rng.randint(hi, max(hi, hi * 2))),
                "p": round(rng.uniform(0.2, 0.8), 3)}
    return float(rng.randint(lo, hi))


def _weighted(rng, pairs):
    """Взвешенный выбор: pairs = [(значение, вес), ...]."""
    vals = [p[0] for p in pairs]
    ws = [p[1] for p in pairs]
    return rng.choices(vals, weights=ws)[0]


def _decaying_int(rng, cap, p=0.45):
    """Уровень с убывающей вероятностью: 1-2 частые, дальше реже."""
    v = 1
    while v < cap and rng.random() < p:
        v += 1
    return v


def _decaying_frac(rng):
    """Дробь в [0,1] с плотностью у нуля (для величин модификаторов)."""
    return rng.random() ** 2.5


def _hex_color(rng):
    return "#%02X%02X%02X" % (rng.randint(40, 255), rng.randint(40, 255),
                              rng.randint(40, 255))


# ---------------------------------------------------------------------------
# Классификация предметов
# ---------------------------------------------------------------------------

_ITEM_KIND = {}


def _reg(items, kind):
    for it in items:
        _ITEM_KIND[it] = kind


_reg(SWORDS, "sword")
_reg(SPEARS, "spear")
_reg(AXES, "axe")
_reg(MACES, "mace")
_reg(PICKAXES, "pickaxe")
_reg(SHOVELS, "shovel")
_reg(HOES, "hoe")
_reg(BOWS, "bow")
_reg(CROSSBOWS, "crossbow")
_reg(TRIDENTS, "trident")
_reg(["minecraft:fishing_rod"], "fishing_rod")
_reg(_HELMETS, "helmet")
_reg(_CHESTPLATES, "chestplate")
_reg(_LEGGINGS, "leggings")
_reg(_BOOTS, "boots")
_reg(ELYTRA, "elytra")
_reg(SHIELDS, "shield")
_reg(BOOKS + ENCH_BOOKS, "book")
_reg(POTIONS, "potion")


def _kind_of(item):
    return _ITEM_KIND.get(item, "generic")


def _leather(item):
    return item.startswith("minecraft:leather_")


# ---------------------------------------------------------------------------
# Генератор имён
# ---------------------------------------------------------------------------

def _proper_name(rng):
    n = rng.randint(2, 4)
    s = "".join(rng.choice(_NAME_SYLL) for _ in range(n))
    # первый слог может быть строчным - имя обязано начинаться с заглавной
    return s[0].upper() + s[1:]


def rand_name(rng, item):
    """Крутое имя предмета (text component). Род согласован.
    Базовое существительное - через _base_noun: спец-предметы (лодки/
    попоны/черепки/стрелы/пластинки/яйца...) получают своё слово и здесь,
    а не только в раскрывающем _reveal_name."""
    kind = _kind_of(item)
    noun, gender = _base_noun(rng, item, kind)
    gi = _GENDER_IDX[gender]
    r = rng.random()
    if r < 0.34:  # «Пепельный Клинок»
        adj = rng.choice(_ADJ)[gi]
        title = "%s %s" % (adj, noun)
    elif r < 0.69:  # «Клинок Пепельного Рассвета»
        title = "%s %s" % (noun, rng.choice(_GENITIVE))
    elif r < 0.87:  # «Ржавая Бритва Спящего Вулкана»
        adj = rng.choice(_ADJ)[gi]
        title = "%s %s %s" % (adj, noun, rng.choice(_GENITIVE))
    elif r < 0.96:  # «Топор-Гроза»
        title = "%s-%s" % (noun, rng.choice(_HYPHEN_WORDS))
    else:  # собственное имя: «Гхарзул»
        title = _proper_name(rng)
    color = _hex_color(rng) if rng.random() < 0.2 else rng.choice(_NAME_COLORS)
    comp = {"text": title, "color": color, "italic": False}
    if rng.random() < 0.15:
        comp["bold"] = True
    if rng.random() < 0.04:
        comp["obfuscated"] = True
    return comp


# ---------------------------------------------------------------------------
# Компоненты предметов
# ---------------------------------------------------------------------------

SINGLE_LEVEL_ENCHANTS = frozenset({
    "silk_touch", "mending", "infinity", "flame", "channeling",
    "multishot", "aqua_affinity", "binding_curse", "vanishing_curse"
})

def _enchant_levels(rng, ench):
    """Уровень зачарования:
    - Зачарования, не дающие бонуса выше 1-го уровня (шёлковое касание и др.),
      всегда строго уровня 1.
    - Масштабируемые зачарования: обычно 1..max_level, редкий дроп (~5%)
      сверхвысокого уровня вплоть до 20 с убывающей вероятностью."""
    max_lvl = ENCHANTS.get(ench, (1,))[0]
    if max_lvl == 1 or ench in SINGLE_LEVEL_ENCHANTS:
        return 1
    if rng.random() < 0.05:
        u = min(1.0, abs(rng.gauss(0, 0.38)))
        bonus = int(u * (20 - max_lvl))
        return min(20, max_lvl + 1 + bonus)
    else:
        return _decaying_int(rng, max_lvl)


def _enchantments_map(rng, item):
    """Карта {id зачарования: уровень} под предмет. enchanted_book -
    носитель ЛЮБЫХ зачарований (применится наковальней лишь к
    совместимому); обычные предметы - ТОЛЬКО подходящие по точным
    supported_items из jar 26.2 (жалоба: «не надо мечу давать защиту"):
    sharpness не на кирке, knockback не на топоре, unbreaking не на
    хлебе. Предмет без единого совместимого зачарования (черепки,
    блоки, еда...) остаётся без чар - осмысленность важнее хаоса."""
    if item in ENCH_BOOKS:
        pool = list(ENCHANTS)
    else:
        pool = [e for e in ENCHANTS if item in ENCHANTS[e][1]]
        if not pool:
            return {}
    n = _weighted(rng, [(1, 35), (2, 30), (3, 20), (4, 10), (5, 5)])
    n = min(n, len(pool))
    picked = rng.sample(pool, n)
    # логика: не сочетаем взаимоисключающие семейства (85% случаев)
    exclusive = ({"protection", "fire_protection", "blast_protection",
                  "projectile_protection"},
                 {"sharpness", "smite", "bane_of_arthropods"})
    if rng.random() < 0.85:
        for ex in exclusive:
            clashing = [e for e in picked if e in ex]
            if len(clashing) > 1:
                keep = rng.choice(clashing)
                picked = [e for e in picked if e not in ex or e == keep]
    out = {}
    for e in picked:
        out["minecraft:" + e] = _enchant_levels(rng, e)
    # кастомные зачарования ИЗМЕРЕНИЯ (связка с gen_enchantments: главный
    # скрипт подмешивает их через set_custom_enchants перед rand_loot).
    # ТОЛЬКО совместимые с предметом: предмет обязан входить в
    # supported_items зачарования (жалоба: «не надо мечу давать защиту -
    # касается и сгенерированных зачарований»); книги - исключение-носитель.
    # Свой уровень 1-3 с убывающей вероятностью (max_level чужого модуля
    # мы не знаем, берём безопасный низкий)
    cpool = [e for e in CUSTOM_ENCHS if _custom_ench_ok(e, item)]
    if cpool and rng.random() < 0.80:
        k = rng.choice([1, 1, 2]) if len(cpool) >= 2 else 1
        for ce in rng.sample(cpool, min(k, len(cpool))):
            out[ce] = _decaying_int(rng, 3)
    return out


# тематические пулы атрибутов: атака считывается только с предметов В
# руках (mainhand/offhand), защита/жизнь - с предметов В слотах брони.
# Чтобы модификаторы РАБОТАЛИ, а не висели мёртвым грузом (жалоба:
# «attribute_modifiers со слотом chest - только на equippable»), пул
# атрибутов и допустимые слоты подбираются под класс предмета
_ATTR_POOL_WEAPON = ["minecraft:attack_damage", "minecraft:attack_speed",
                     "minecraft:attack_knockback", "minecraft:sweeping_damage_ratio",
                     "minecraft:entity_interaction_range", "minecraft:max_health",
                     "minecraft:movement_speed", "minecraft:knockback_resistance",
                     "minecraft:luck", "minecraft:scale"]
_ATTR_POOL_TOOL = ["minecraft:block_break_speed", "minecraft:mining_efficiency",
                   "minecraft:submerged_mining_speed", "minecraft:block_interaction_range",
                   "minecraft:entity_interaction_range", "minecraft:max_health",
                   "minecraft:movement_speed", "minecraft:luck",
                   "minecraft:movement_efficiency"]
_ATTR_POOL_RANGED = ["minecraft:max_health", "minecraft:movement_speed",
                     "minecraft:knockback_resistance", "minecraft:sneaking_speed",
                     "minecraft:entity_interaction_range", "minecraft:safe_fall_distance",
                     "minecraft:luck", "minecraft:scale", "minecraft:gravity"]
_ATTR_POOL_ARMOR = ["minecraft:armor", "minecraft:armor_toughness",
                    "minecraft:max_health", "minecraft:max_absorption",
                    "minecraft:knockback_resistance",
                    "minecraft:explosion_knockback_resistance",
                    "minecraft:movement_speed", "minecraft:jump_strength",
                    "minecraft:sneaking_speed", "minecraft:safe_fall_distance",
                    "minecraft:fall_damage_multiplier", "minecraft:oxygen_bonus",
                    "minecraft:step_height", "minecraft:flying_speed",
                    "minecraft:scale", "minecraft:gravity", "minecraft:bounciness",
                    "minecraft:movement_efficiency", "minecraft:water_movement_efficiency",
                    "minecraft:burning_time", "minecraft:luck"]
_ATTR_POOL_MATERIAL = ["minecraft:max_health", "minecraft:movement_speed",
                      "minecraft:attack_damage", "minecraft:armor", "minecraft:armor_toughness",
                      "minecraft:luck", "minecraft:jump_strength", "minecraft:knockback_resistance",
                      "minecraft:safe_fall_distance", "minecraft:mining_efficiency",
                      "minecraft:scale", "minecraft:gravity", "minecraft:step_height"]
_ATTR_POOL_GENERIC = ["minecraft:max_health", "minecraft:movement_speed", 
                      "minecraft:jump_strength", "minecraft:step_height",
                      "minecraft:knockback_resistance", "minecraft:scale",
                      "minecraft:gravity", "minecraft:luck", "minecraft:bounciness"]
_HAND_SLOTS = _HAND_SLOTS_ANY  # «рукастые» диковины (не оружие)
# id -> (id, lo, hi) - для распаковки attr, lo, hi
_ATTR_RANGE = {a[0]: a for a in ATTRIBUTES}


def _decaying_roll(rng, lo, mid, peak):
    """Убывающее (полунормальное) распределение для величины атрибута:
    - большинство (~70%) предметов получают малый сбалансированный прирост [lo, mid];
    - около 25% получают хороший прирост в диапазоне (mid, mid + (peak-mid)*0.5];
    - около 5% получают редкие высокие броски (god-roll), приближающиеся к peak."""
    z = min(abs(rng.gauss(0, 1.0)), 3.8)
    if z <= 1.0:
        return lo + (mid - lo) * z
    else:
        t = (z - 1.0) / 2.8
        return mid + (peak - mid) * (t ** 1.8)


def _gen_attribute_amount(rng, spec, op, strong=False):
    """Генерирует значение атрибута. Для сильных материалов (strong=True)
    значения берутся из верхней трети диапазона и положительны (кроме fall_damage)."""
    aid, lo, mid, peak, can_neg, neg_mid, neg_peak = spec
    digits = 3 if peak <= 1.0 else (1 if peak >= 10.0 else 2)
    
    is_neg = False
    if aid == "minecraft:fall_damage_multiplier":
        is_neg = (rng.random() < 0.85)
    elif not strong:
        if aid in ("minecraft:scale", "minecraft:gravity"):
            is_neg = (rng.random() < 0.40)
        elif can_neg:
            is_neg = (rng.random() < 0.07)
        
    if op != "add_value":
        if is_neg:
            return -round(rng.uniform(0.05, 0.25), 3)
        else:
            if strong:
                return round(_decaying_roll(rng, 0.20, 0.45, 0.85), 3)
            else:
                return round(_decaying_roll(rng, 0.05, 0.15, 0.40), 3)
    else:
        if is_neg:
            raw = _decaying_roll(rng, lo * 0.8 if lo < neg_mid else lo, neg_mid, neg_peak)
            return -round(raw, digits)
        else:
            if strong:
                strong_lo = mid if mid > lo else lo
                strong_mid = (mid + peak) * 0.55
                raw = _decaying_roll(rng, strong_lo, strong_mid, peak)
                return round(raw, digits)
            else:
                raw = _decaying_roll(rng, lo, mid, peak)
                return round(raw, digits)
def _armor_slot_for_item(item, kind):
    """Определяет канонический слот брони. Шлем никогда не получает слот legs/feet/chest."""
    if kind == "helmet" or item.endswith("_helmet") or item.endswith("_skull") or item.endswith("_head") or item == "minecraft:carved_pumpkin":
        return "head"
    elif kind == "chestplate" or item.endswith("_chestplate") or kind == "elytra" or item == "minecraft:elytra":
        return "chest"
    elif kind == "leggings" or item.endswith("_leggings"):
        return "legs"
    elif kind == "boots" or item.endswith("_boots"):
        return "feet"
    elif item.endswith("_horse_armor") or item == "minecraft:wolf_armor":
        return "body"
    return None


def _attribute_modifiers(rng, item, tag_prefix, equip_slot=None, strong=False):
    """Генерация модификаторов атрибутов 26.2."""
    kind = _kind_of(item)
    aslot = _armor_slot_for_item(item, kind)
    if aslot:
        pool, slots = _ATTR_POOL_ARMOR, [aslot, "armor", "any"]
    elif equip_slot:
        pool, slots = _ATTR_POOL_ARMOR, [equip_slot, "armor", "any"]
    elif kind in _MELEE_KINDS:
        pool, slots = _ATTR_POOL_WEAPON, _HAND_SLOTS_MAIN
    elif kind in ("bow", "crossbow", "fishing_rod"):
        pool, slots = _ATTR_POOL_RANGED, _HAND_SLOTS_MAIN
    elif kind in _TOOL_KINDS:
        pool, slots = _ATTR_POOL_TOOL, _HAND_SLOTS_MAIN
    elif kind in _ARMOR_KINDS:
        pool, slots = _ATTR_POOL_ARMOR, [_KIND_SLOTS[kind], "armor", "any"]
    elif kind == "shield":
        pool, slots = _ATTR_POOL_ARMOR, ["offhand", "any"]
    elif _is_material(item):
        pool, slots = _ATTR_POOL_MATERIAL, ["any", "mainhand", "offhand", "hand"]
    else:
        pool, slots = _ATTR_POOL_GENERIC, _HAND_SLOTS_ANY
    modifiers = _vanilla_base_mods(item, tag_prefix)
    if strong:
        n = _weighted(rng, [(1, 25), (2, 50), (3, 25)])
    else:
        n = _weighted(rng, [(1, 40), (2, 32), (3, 18), (4, 10)])
    for i in range(n):
        spec = _ATTR_RANGE[rng.choice(pool)]
        attr = spec[0]
        op = "add_value" if rng.random() < 0.75 else rng.choice(
            ["add_multiplied_base", "add_multiplied_total"])
        amount = _gen_attribute_amount(rng, spec, op, strong=strong)
        modifiers.append({
            "type": attr,
            "id": "%s_a%d%d" % (tag_prefix, i, rng.randint(0, 999)),
            "amount": amount, "operation": op,
            "slot": rng.choice(slots)})
    return modifiers
def _rarity(rng):
    return _weighted(rng, [("common", 45), ("uncommon", 30),
                           ("rare", 18), ("epic", 7)])


# ---------------------------------------------------------------------------
# Новые компоненты 26.2 (все форматы подтверждены серверной пробой)
# ---------------------------------------------------------------------------

def _consume_effect(rng):
    r = rng.random()
    if r < 0.70:  # apply_effects
        effects = []
        for eid in rng.sample(MOB_EFFECTS, rng.randint(2, 4)):
            is_god = rng.random() < 0.15
            amp = rng.randint(4, 7) if is_god else rng.randint(1, 4)
            dur = rng.randint(6000, 12000) if is_god else rng.randint(1200, 4800)
            effects.append({"id": "minecraft:" + eid, "amplifier": amp, "duration": dur})
        return {"type": "minecraft:apply_effects", "effects": effects, "probability": 1.0}
    if r < 0.80:  # remove_effects
        return {"type": "minecraft:remove_effects",
                "effects": ["minecraft:" + e for e in rng.sample(MOB_EFFECTS, rng.randint(1, 3))]}
    if r < 0.88:  # clear_all_effects
        return {"type": "minecraft:clear_all_effects"}
    if r < 0.95:  # teleport_randomly
        return {"type": "minecraft:teleport_randomly", "diameter": float(rng.randint(4, 32))}
    return {"type": "minecraft:play_sound", "sound": rng.choice(SOUNDS)}


def _consumable(rng):
    """Компонент consumable."""
    c = {"consume_seconds": round(rng.uniform(0.5, 3.2), 2),
         "animation": rng.choice(["eat", "drink", "bow", "spyglass",
                                  "crossbow", "spear", "brush"]),
         "sound": rng.choice(SOUNDS),
         "has_consume_particles": rng.random() < 0.8}
    if rng.random() < 0.5:
        c["on_consume_effects"] = [_consume_effect(rng)
                                   for _ in range(rng.randint(1, 2))]
    return c


def _tool_rules(rng, kind):
    """Компонент tool для инструмента (kind: pickaxe/shovel/hoe/axe).
    ВАЖНО: blocks - тег С РЕШЁТКОЙ («#minecraft:mineable/pickaxe») или
    СПИСОК id блоков; голая строка без # парсится как id блока."""
    tag = {"pickaxe": "minecraft:mineable/pickaxe",
           "axe": "minecraft:mineable/axe",
           "shovel": "minecraft:mineable/shovel",
           "hoe": "minecraft:mineable/hoe"}[kind]
    rules = [{"blocks": "#" + tag,
              "speed": round(rng.uniform(2.0, 12.0), 1),
              "correct_for_drops": rng.random() < 0.8}]
    if rng.random() < 0.4:
        rules.append({"blocks": "#" + rng.choice(TOOL_BLOCK_TAGS),
                      "speed": round(rng.uniform(1.0, 6.0), 1)})
    return {"rules": rules,
            "default_mining_speed": round(rng.uniform(1.0, 4.0), 1),
            "damage_per_block": rng.randint(1, 3),
            "can_destroy_blocks_in_creative": rng.random() < 0.9}


def _equippable(rng, slot):
    """Компонент equippable для «дикого» надеваемого предмета
    (не-брони): slot - слот экипировки (head/chest/legs/feet).

    asset_id НЕ задаём НИКОГДА (жалоба: «текстура брони на игроке
    должна соответствовать предмету»): без поля игра берёт
    equipment-ассет по id предмета - для настоящей брони это её родная
    текстура, для диковины - слоя просто нет, предмет носится «как
    есть». Случайный asset_id натягивал бы на игрока чужую текстуру.
    allowed_entities тоже не ставим - диковина должна надеваться кем
    угодно, иначе её атрибуты - мёртвый груз. camera_overlay из
    генерации удалён полностью."""
    return {
        "slot": slot,
        # звук надевания - любой из ванильных equip_* (не привязан к
        # материалу: предмет может звучать «не своим» звуком)
        "equip_sound": "minecraft:item.armor.equip_" + rng.choice(
            ["leather", "iron", "gold", "diamond", "netherite"]),
        "dispensable": rng.random() < 0.9,
        "swappable": rng.random() < 0.7,
        "damage_on_hurt": rng.random() < 0.8,
        "equip_on_interact": rng.random() < 0.3,
    }


def _blocks_attacks(rng):
    """Компонент blocks_attacks (щиты)."""
    reds = []
    n = rng.randint(1, 2)
    for _ in range(n):
        red = {"factor": round(rng.uniform(0.3, 0.9), 2),
               "base": round(rng.uniform(-2.0, 0.0), 2),
               "horizontal_blocking_angle": round(
                   rng.uniform(60.0, 100.0), 1)}
        if rng.random() < 0.5:
            red["type"] = rng.choice(
                ["#minecraft:is_projectile", "#minecraft:is_explosion",
                 "#minecraft:is_fire"])
        reds.append(red)
    out = {"block_delay_seconds": round(rng.uniform(0.1, 0.5), 2),
           "disable_cooldown_scale": round(rng.uniform(0.3, 1.0), 2),
           "item_damage": {"threshold": round(rng.uniform(0.5, 5.0), 1),
                           "base": float(rng.randint(0, 2)),
                           "factor": round(rng.uniform(0.5, 2.0), 2)},
           "damage_reductions": reds,
           "block_sound": rng.choice(
               ["minecraft:item.shield.block",
                "minecraft:item.mace.smash_ground",
                "minecraft:block.bell.use",
                "minecraft:item.trident.hit"])}
    if rng.random() < 0.3:
        # какой урон «пробивает» блок (теги damage_type из jar 26.2)
        out["bypassed_by"] = rng.choice(
            ["#minecraft:bypasses_shield", "#minecraft:bypasses_armor",
             "#minecraft:bypasses_resistance", "#minecraft:bypasses_effects",
             "#minecraft:bypasses_enchantments",
             "#minecraft:bypasses_invulnerability"])
    return out


def _kinetic_weapon(rng):
    """Компонент kinetic_weapon (булава). ВАЖНО: условия - одиночные
    объекты (не массивы), и max_duration_ticks обязателен."""
    out = {"damage_multiplier": round(rng.uniform(1.0, 4.0), 2),
           "forward_movement": round(rng.uniform(0.1, 1.0), 2),
           "delay_ticks": rng.randint(1, 10),
           "contact_cooldown_ticks": rng.randint(5, 40),
           "hit_sound": rng.choice(
               ["minecraft:item.mace.smash_ground",
                "minecraft:item.trident.hit",
                "minecraft:block.bell.use",
                "minecraft:entity.player.attack.strong"]),
           "damage_conditions": {
               "min_speed": round(rng.uniform(0.5, 2.0), 2),
               "max_duration_ticks": rng.randint(2, 6)},
           "knockback_conditions": {
               "min_speed": round(rng.uniform(0.5, 3.0), 2),
               "max_duration_ticks": rng.randint(2, 8)}}
    if rng.random() < 0.4:
        out["dismount_conditions"] = {
            "min_relative_speed": round(rng.uniform(0.2, 1.0), 2),
            "max_duration_ticks": rng.randint(2, 5)}
    return out


def _firework_explosion(rng):
    """Один взрыв для fireworks.explosions / firework_explosion."""
    e = {"shape": rng.choice(["small_ball", "large_ball", "star", "creeper",
                              "burst"]),
         "colors": [rng.randint(0, 0xFFFFFF)
                    for _ in range(rng.randint(1, 3))]}
    if rng.random() < 0.5:
        e["fade_colors"] = [rng.randint(0, 0xFFFFFF)
                            for _ in range(rng.randint(1, 2))]
    e["has_trail"] = rng.random() < 0.4
    e["has_twinkle"] = rng.random() < 0.4
    return e


def _potion_effects(rng, long_durations):
    """Генерирует эффекты для potion_contents.custom_effects.
    Длительность эффектов задаётся в тиках (20 тиков = 1 сек).
    long_durations=True - банки (базовая: 2400-9600 тиков = 2-8 мин).
    long_durations=False - стрелы (базовая: 2400-9600 тиков, с учётом того что
    Minecraft Arrow.class при попадании масштабирует длительность на 0.125f (в 8
    раз меньше), на цели эффект держится 15-60 секунд). Редкий дроп (~7%): супер
    высокий уровень (до X) или супер высокая длительность."""
    k = _weighted(rng, [(1, 45), (2, 35), (3, 20)])
    effects = []
    for eid in rng.sample(MOB_EFFECTS, k):
        is_god_roll = rng.random() < 0.07
        if long_durations:
            if is_god_roll:
                amp = rng.randint(3, 8) if rng.random() < 0.6 else rng.randint(1, 3)
                dur = rng.randint(18000, 72000) if rng.random() < 0.6 else rng.randint(4800, 14400)
            else:
                amp = rng.randint(0, 2)
                dur = rng.randint(2400, 9600)
        else:
            if is_god_roll:
                amp = rng.randint(3, 9) if rng.random() < 0.6 else rng.randint(1, 3)
                dur = rng.randint(16000, 48000) if rng.random() < 0.6 else rng.randint(4800, 12000)
            else:
                amp = rng.randint(0, 2)
                dur = rng.randint(2400, 9600)
        effects.append({"id": "minecraft:" + eid, "amplifier": amp, "duration": dur})
    return effects


def _potion_contents(rng, long_durations=True):
    """Компонент potion_contents «с характером»: стандартное зелье +
    кастомные комбинации эффектов (amplifier до 3) + иногда свой цвет.
    (имена полей - PotionContents.CODEC: potion, custom_color,
    custom_effects; сверено серверной пробой)."""
    pc = {"potion": "minecraft:" + rng.choice(POTIONS_IDS)}
    if rng.random() < 0.55:
        pc["custom_effects"] = _potion_effects(rng, long_durations)
    if rng.random() < 0.35:
        pc["custom_color"] = int(_hex_color(rng)[1:], 16)
    return pc


def _true_name(rng, item):
    """«Истинное имя» для item_name (базовое имя без курсива):
    custom_name перекрывает его в тултипе - «у предмета два имени»,
    базовое остаётся под ним."""
    noun, gender = _base_noun(rng, item, _kind_of(item))
    return "%s %s" % (noun, rng.choice(_GENITIVE))


def _fill_stack(rng, pool):
    """Стек для тематической заливки container (все слоты - одна тема:
    «припасы», «дары земли», «коллекция пластинок»...).
    Стек-1 предметам count>1 нельзя (validateContainedItemSizes)."""
    item = rng.choice(pool)
    s = {"id": item,
         "count": 1 if item in _STACK1 else rng.randint(1, 6)}
    if item == "minecraft:tipped_arrow" and rng.random() < 0.6:
        s["components"] = {"minecraft:potion_contents":
                           _potion_contents(rng, long_durations=False)}
    return s


def _stack(rng, lo=1, hi=3, comps=None):
    """Стек предметов (bundle_contents, charged_projectiles, container).
    Стек-1 предметам count>1 нельзя - validateContainedItemSizes
    («Item stack with count of N was larger than maximum: 1»)."""
    it = rng.choice(ALL_ITEMS)
    if it in ULTRA_RARE_VALUABLES:
        cnt = 1
    elif it in RARE_VALUABLES:
        cnt = 1 if rng.random() < 0.8 else 2
    else:
        cnt = 1 if it in _STACK1 else rng.randint(lo, hi)
    s = {"id": it, "count": cnt}
    if comps:
        s["components"] = comps
    return s


def _book_pages(rng, n, component_form):
    try:
        from gen_lore import generate_50_book_pages
        return generate_50_book_pages(rng, component_form=component_form)
    except ImportError:
        import sys, os
        sys.path.insert(0, os.path.dirname(__file__))
        from gen_lore import generate_50_book_pages
        return generate_50_book_pages(rng, component_form=component_form)


_RU_AUTHORS = ["Стив", "Алекс", "Безымянный монах", "Картограф Тимофей",
               "Ведьма Агата", "Старатель Голд", "Библиотекарь Эльдар",
               "Пчеловод Мирон", "Капитан Соль", "Ученик чародея"]

_BOOK_TITLES = ["Дневник выживальщика", "Записки смотрителя маяка",
                "Трактат о пчёлах", "Картография тумана", "Реестр находок",
                "Молитва Глубин", "Кухня подземелий", "Полевой журнал",
                "Список должников", "Песни Пустоты"]


# классы предметов для новых компонентов
_MELEE_KINDS = ("sword", "spear", "axe", "mace", "trident")
_TOOL_KINDS = ("pickaxe", "axe", "shovel", "hoe")
_ARMOR_KINDS = ("helmet", "chestplate", "leggings", "boots", "elytra")

_PROFILE_NAMES = ["Notch", "jeb_", "Dinnerbone", "Grumm"]

# ---------------------------------------------------------------------------
# Варианты сущностей 26.2 для спавн-яйц/вёдер/картин. Значения:
#   * файловые реестры jar (data/minecraft/<registry>/*.json) - id С
#     namespace ("minecraft:temperate", "minecraft:jellie");
#   * enum-кодеки (Axolotl$Variant.CODEC и т.п., подтверждено байткодом) -
#     plain lowercase БЕЗ namespace ("lucy", "evil", "red_blue").
# Сериализованные id самих компонентов («путевые»: chicken/variant,
# salmon/size, painting/variant, cat/sound_variant...) доказаны байткодом
# регистрации DataComponents (static init, // String константы).
# ---------------------------------------------------------------------------

# климатические варианты (chicken/cow/pig/frog_variant - реестры из jar)
_CLIMATE_VARIANTS = ["minecraft:temperate", "minecraft:warm",
                     "minecraft:cold"]
WOLF_VARIANTS = ["minecraft:ashen", "minecraft:black", "minecraft:chestnut",
                 "minecraft:pale", "minecraft:rusty", "minecraft:snowy",
                 "minecraft:spotted", "minecraft:striped", "minecraft:woods"]
CAT_VARIANTS = ["minecraft:all_black", "minecraft:black",
                "minecraft:british_shorthair", "minecraft:calico",
                "minecraft:jellie", "minecraft:persian",
                "minecraft:ragdoll", "minecraft:red", "minecraft:siamese",
                "minecraft:tabby", "minecraft:white"]
VILLAGER_VARIANTS = ["minecraft:desert", "minecraft:jungle",
                     "minecraft:plains", "minecraft:savanna",
                     "minecraft:snow", "minecraft:swamp", "minecraft:taiga"]
# реестр painting_variant jar (51 картины) - значение компонента
# painting/variant = id оттуда
PAINTING_VARIANTS = [
    "minecraft:alban", "minecraft:aztec", "minecraft:aztec2",
    "minecraft:backyard", "minecraft:baroque", "minecraft:bomb",
    "minecraft:bouquet", "minecraft:burning_skull", "minecraft:bust",
    "minecraft:cavebird", "minecraft:changing", "minecraft:cotan",
    "minecraft:courbet", "minecraft:creebet", "minecraft:dennis",
    "minecraft:donkey_kong", "minecraft:earth", "minecraft:endboss",
    "minecraft:fern", "minecraft:fighters", "minecraft:finding",
    "minecraft:fire", "minecraft:graham", "minecraft:humble",
    "minecraft:kebab", "minecraft:lowmist", "minecraft:match",
    "minecraft:meditative", "minecraft:orb", "minecraft:owlemons",
    "minecraft:passage", "minecraft:pigscene", "minecraft:plant",
    "minecraft:pointer", "minecraft:pond", "minecraft:pool",
    "minecraft:prairie_ride", "minecraft:sea", "minecraft:skeleton",
    "minecraft:skull_and_roses", "minecraft:stage", "minecraft:sunflowers",
    "minecraft:sunset", "minecraft:tides", "minecraft:unpacked",
    "minecraft:void", "minecraft:wanderer", "minecraft:wasteland",
    "minecraft:water", "minecraft:wind", "minecraft:wither"]

# enum-варианты (plain lowercase, без namespace)
AXOLOTL_VARIANTS = ["lucy", "wild", "gold", "cyan", "blue"]
SALMON_SIZES = ["small", "medium", "large"]
PARROT_VARIANTS = ["red_blue", "blue", "green", "yellow_blue", "gray"]
RABBIT_VARIANTS = ["brown", "white", "black", "white_splotched", "gold",
                   "salt", "evil"]
LLAMA_VARIANTS = ["creamy", "white", "brown", "gray"]
FOX_VARIANTS = ["red", "snow"]
MOOSHROOM_VARIANTS = ["red", "brown"]

# звуковые варианты (реестры <entity>_sound_variant из jar)
WOLF_SOUND_VARIANTS = ["minecraft:angry", "minecraft:big",
                       "minecraft:classic", "minecraft:cute",
                       "minecraft:grumpy", "minecraft:puglin",
                       "minecraft:sad"]
CAT_SOUND_VARIANTS = ["minecraft:classic", "minecraft:royal"]
COW_SOUND_VARIANTS = ["minecraft:classic", "minecraft:moody"]
PIG_SOUND_VARIANTS = ["minecraft:big", "minecraft:classic", "minecraft:mini"]
CHICKEN_SOUND_VARIANTS = ["minecraft:classic", "minecraft:picky"]


def _variant_gen(values):
    """Генератор значения варианта: lambda по переданному списку."""
    return lambda rng: rng.choice(values)


def _climate_variant(rng):
    return rng.choice(_CLIMATE_VARIANTS)


# спавн-яйца: список (компонент, генератор) - на яйцо берётся 1..все
_SPAWN_EGG_VARIANTS = {
    "minecraft:cat_spawn_egg": [
        ("minecraft:cat/collar", _variant_gen(DYE_COLORS)),
        ("minecraft:cat/variant", _variant_gen(CAT_VARIANTS)),
        ("minecraft:cat/sound_variant", _variant_gen(CAT_SOUND_VARIANTS))],
    "minecraft:wolf_spawn_egg": [
        ("minecraft:wolf/collar", _variant_gen(DYE_COLORS)),
        ("minecraft:wolf/variant", _variant_gen(WOLF_VARIANTS)),
        ("minecraft:wolf/sound_variant", _variant_gen(WOLF_SOUND_VARIANTS))],
    "minecraft:horse_spawn_egg": [
        ("minecraft:horse/variant", _variant_gen(HORSE_VARIANTS))],
    "minecraft:sheep_spawn_egg": [
        ("minecraft:sheep/color", _variant_gen(DYE_COLORS))],
    "minecraft:shulker_spawn_egg": [
        ("minecraft:shulker/color", _variant_gen(DYE_COLORS))],
    "minecraft:chicken_spawn_egg": [
        ("minecraft:chicken/variant", _climate_variant),
        ("minecraft:chicken/sound_variant",
         _variant_gen(CHICKEN_SOUND_VARIANTS))],
    "minecraft:cow_spawn_egg": [
        ("minecraft:cow/variant", _climate_variant),
        ("minecraft:cow/sound_variant", _variant_gen(COW_SOUND_VARIANTS))],
    "minecraft:pig_spawn_egg": [
        ("minecraft:pig/variant", _climate_variant),
        ("minecraft:pig/sound_variant", _variant_gen(PIG_SOUND_VARIANTS))],
    "minecraft:frog_spawn_egg": [
        ("minecraft:frog/variant", _climate_variant)],
    "minecraft:zombie_nautilus_spawn_egg": [
        ("minecraft:zombie_nautilus/variant",
         lambda rng: rng.choice(["minecraft:temperate",
                                 "minecraft:warm"]))],
    "minecraft:villager_spawn_egg": [
        ("minecraft:villager/variant", _variant_gen(VILLAGER_VARIANTS))],
    "minecraft:zombie_villager_spawn_egg": [
        ("minecraft:villager/variant", _variant_gen(VILLAGER_VARIANTS))],
    "minecraft:llama_spawn_egg": [
        ("minecraft:llama/variant", _variant_gen(LLAMA_VARIANTS))],
    "minecraft:trader_llama_spawn_egg": [
        ("minecraft:llama/variant", _variant_gen(LLAMA_VARIANTS))],
    "minecraft:fox_spawn_egg": [
        ("minecraft:fox/variant", _variant_gen(FOX_VARIANTS))],
    "minecraft:rabbit_spawn_egg": [
        ("minecraft:rabbit/variant", _variant_gen(RABBIT_VARIANTS))],
    "minecraft:parrot_spawn_egg": [
        ("minecraft:parrot/variant", _variant_gen(PARROT_VARIANTS))],
    "minecraft:mooshroom_spawn_egg": [
        ("minecraft:mooshroom/variant", _variant_gen(MOOSHROOM_VARIANTS))],
    "minecraft:axolotl_spawn_egg": [
        ("minecraft:axolotl/variant", _variant_gen(AXOLOTL_VARIANTS))],
    "minecraft:salmon_spawn_egg": [
        ("minecraft:salmon/size", _variant_gen(SALMON_SIZES))],
}


# ---------------------------------------------------------------------------
# Осмысленные кастомные предметы (жалобы: имена, РАСКРЫВАЮЩИЕ параметры,
# и «глубокий» NBT мобов у спавн-яиц). Приёмы зеркалят соседние
# серверно-проверенные генераторы: имена по фактическому содержимому -
# как gen_enchantments._effect_name («Громовое Пробитие» - по
# projectile_piercing), полный NBT моба - как gen_structures._rand_mob_nbt
# ---------------------------------------------------------------------------

# зелья -> слово в РОДИТЕЛЬНОМ падеже: «Настой Огнестойкости»
# (id - реестр Potions 26.2; вода/мутная/густая/неловкая - тоже со
# словом: имя-раскрытие должно покрывать ~100% зелий)
_POTION_RU = {
    "water": "Живой Воды", "mundane": "Осадка", "thick": "Густоты",
    "awkward": "Неловкости", "night_vision": "Ночного Зрения",
    "invisibility": "Невидимости",
    "leaping": "Прыгучести", "fire_resistance": "Огнестойкости",
    "swiftness": "Стремительности", "slowness": "Медлительности",
    "turtle_master": "Черепашьей Мощи",
    "water_breathing": "Подводного Дыхания", "healing": "Исцеления",
    "harming": "Вреда", "poison": "Яда", "regeneration": "Регенерации",
    "strength": "Силы", "weakness": "Слабости", "luck": "Удачи",
    "slow_falling": "Медленного Падения", "wind_charged": "Заряда Ветра",
    "weaving": "Плетения", "oozing": "Слизи", "infested": "Заражения",
}

# атрибуты -> (слово в родительном, приоритет «зрелищности» в имени):
# attribute_modifiers на attack_damage -> «Клинок Ярости»
_ATTR_RU = {
    "minecraft:attack_damage": ("Ярости", 9),
    "minecraft:attack_knockback": ("Отброса", 7),
    "minecraft:armor": ("Брони", 7),
    "minecraft:max_health": ("Живучести", 7),
    "minecraft:attack_speed": ("Темпа", 6),
    "minecraft:armor_toughness": ("Твёрдости", 6),
    "minecraft:knockback_resistance": ("Стойкости", 6),
    "minecraft:movement_speed": ("Скорости", 6),
    "minecraft:flying_speed": ("Полёта", 6),
    "minecraft:max_absorption": ("Запаса Жизни", 5),
    "minecraft:explosion_knockback_resistance": ("Взрывной Стойкости", 5),
    "minecraft:jump_strength": ("Прыжка", 5),
    "minecraft:block_break_speed": ("Дробления", 5),
    "minecraft:mining_efficiency": ("Рудокопа", 5),
    "minecraft:submerged_mining_speed": ("Водолаза", 4),
    "minecraft:block_interaction_range": ("Размаха", 4),
    "minecraft:entity_interaction_range": ("Долгих Рук", 4),
    "minecraft:fall_damage_multiplier": ("Кошачьей Лапы", 4),
    "minecraft:safe_fall_distance": ("Приземистости", 4),
    "minecraft:sneaking_speed": ("Скрытности", 4),
    "minecraft:oxygen_bonus": ("Жабр", 4),
    "minecraft:step_height": ("Широкого Шага", 3),
    "minecraft:scale": ("Величия", 5),
    "minecraft:gravity": ("Гравитации", 5),
    "minecraft:luck": ("Удачи", 5),
    "minecraft:bounciness": ("Прыгучести", 5),
    "minecraft:movement_efficiency": ("Проворства", 5),
    "minecraft:water_movement_efficiency": ("Пловца", 5),
    "minecraft:sweeping_damage_ratio": ("Вихря", 5),
    "minecraft:burning_time": ("Времени Горения", 4),
}

# зачарования -> слово в родительном: «Клинок Остроты»
_ENCH_RU = {
    "sharpness": "Остроты", "smite": "Небесной Кары",
    "bane_of_arthropods": "Бича Насекомых", "knockback": "Отброса",
    "looting": "Добычи", "fire_aspect": "Пламени",
    "sweeping_edge": "Размаха", "lunge": "Рывка",
    "unbreaking": "Прочности", "mending": "Починки",
    "vanishing_curse": "Проклятия Утраты", "protection": "Защиты",
    "fire_protection": "Огнеупорности",
    "blast_protection": "Взрывоупорности",
    "projectile_protection": "Щита от Стрел", "thorns": "Шипов",
    "binding_curse": "Проклятия Срастания", "respiration": "Дыхания",
    "aqua_affinity": "Родства с Водой", "swift_sneak": "Скрытности",
    "feather_falling": "Пёрышка", "depth_strider": "Подводной Ходьбы",
    "frost_walker": "Ледохода", "soul_speed": "Скорости Душ",
    "density": "Плотности", "breach": "Пробития",
    "wind_burst": "Порыва Ветра", "power": "Силы", "punch": "Отброса",
    "flame": "Пламени", "infinity": "Бесконечности",
    "multishot": "Залпа", "quick_charge": "Быстрого Взвода",
    "piercing": "Пробития", "impaling": "Пронзания",
    "loyalty": "Верности", "riptide": "Течения",
    "channeling": "Призыва Молний", "luck_of_the_sea": "Рыбацкой Удачи",
    "lure": "Приманки", "efficiency": "Эффективности",
    "fortune": "Удачи", "silk_touch": "Шёлкового Касания",
}

# эффекты -> слово в родительном (еда/похлёбка/consumable)
_EFF_RU = {
    "speed": "Скорости", "slowness": "Медлительности",
    "haste": "Спешки", "mining_fatigue": "Усталости",
    "strength": "Силы", "jump_boost": "Заячьего Прыжка",
    "nausea": "Дурноты", "regeneration": "Регенерации",
    "resistance": "Стойкости", "fire_resistance": "Огнестойкости",
    "water_breathing": "Жабр", "invisibility": "Невидимости",
    "blindness": "Слепоты", "night_vision": "Ночного Зрения",
    "hunger": "Голода", "weakness": "Слабости", "poison": "Яда",
    "wither": "Иссушения", "health_boost": "Здоровья",
    "absorption": "Поглощения", "saturation": "Сытости",
    "glowing": "Сияния", "levitation": "Левитации",
    "luck": "Удачи", "unluck": "Неудачи",
    "slow_falling": "Медленного Падения",
    "conduit_power": "Морской Силы",
    "dolphins_grace": "Благодати Дельфина", "darkness": "Тьмы",
    "instant_health": "Исцеления", "instant_damage": "Боли",
    "bad_omen": "Дурного Знамения",
    "hero_of_the_village": "Героя Деревни",
    "trial_omen": "Знамения Испытания", "raid_omen": "Знамения Рейда",
    "wind_charged": "Заряда Ветра", "weaving": "Плетения",
    "oozing": "Слизи", "infested": "Заражения",
    "breath_of_the_nautilus": "Дыхания Наутилуса",
}

# прилагательные в РОДИТЕЛЬНОМ падеже для имён спавн-яиц
# («Яйцо Древнего Скелета» - м/ср, «Яйцо Древней Ведьмы» - ж)
_GEN_ADJ = [
    ("Древнего", "Древней"), ("Забытого", "Забытой"),
    ("Проклятого", "Проклятой"), ("Мёртвого", "Мёртвой"),
    ("Спящего", "Спящей"), ("Голодного", "Голодной"),
    ("Бешеного", "Бешеной"), ("Тёмного", "Тёмной"),
    ("Лунного", "Лунной"), ("Костяного", "Костяной"),
    ("Ржавого", "Ржавой"), ("Медного", "Медной"),
    ("Соляного", "Соляной"), ("Жадного", "Жадной"),
    ("Тихого", "Тихой"), ("Пылающего", "Пылающей"),
    ("Мерцающего", "Мерцающей"), ("Кровавого", "Кровавой"),
    ("Громового", "Громовой"), ("Ледяного", "Ледяной"),
    # --- пополнение (м-форма = также ср-род) ---
    ("Студёного", "Студёной"), ("Полуночного", "Полуночной"),
    ("Сумрачного", "Сумрачной"), ("Кромешного", "Кромешной"),
    ("Слепого", "Слепой"), ("Немого", "Немой"),
    ("Хромого", "Хромой"), ("Косого", "Косой"),
    ("Задумчивого", "Задумчивой"), ("Свирепого", "Свирепой"),
    ("Яростного", "Яростной"), ("Гневного", "Гневной"),
    ("Лютого", "Лютой"), ("Злобного", "Злобной"),
    ("Хитрого", "Хитрой"), ("Лукавого", "Лукавой"),
    ("Коварного", "Коварной"), ("Гордого", "Гордой"),
    ("Мудрого", "Мудрой"), ("Строптивого", "Строптивой"),
    ("Упрямого", "Упрямой"), ("Дремучего", "Дремучей"),
    ("Лесного", "Лесной"), ("Болотного", "Болотной"),
    ("Пещерного", "Пещерной"), ("Подземного", "Подземной"),
    ("Глубинного", "Глубинной"), ("Небесного", "Небесной"),
    ("Звёздного", "Звёздной"), ("Утреннего", "Утренней"),
    ("Вечернего", "Вечерней"), ("Северного", "Северной"),
    ("Снежного", "Снежной"), ("Морозного", "Морозной"),
    ("Туманного", "Туманной"), ("Пепельного", "Пепельной"),
    ("Тлеющего", "Тлеющей"), ("Поющего", "Поющей"),
    ("Шепчущего", "Шепчущей"), ("Плачущего", "Плачущей"),
    ("Одинокого", "Одинокой"), ("Бродячего", "Бродячей"),
    ("Странного", "Странной"), ("Диковинного", "Диковинной"),
    ("Святого", "Святой"), ("Грешного", "Грешной"),
    ("Колдовского", "Колдовской"), ("Благословенного", "Благословенной"),
    ("Освящённого", "Освящённой"), ("Утопшего", "Утопшей"),
    ("Утонувшего", "Утонувшей"), ("Замёрзшего", "Замёрзшей"),
    ("Окаменелого", "Окаменелой"), ("Ветхого", "Ветхой"),
    ("Старого", "Старой"), ("Малого", "Малой"),
    ("Великого", "Великой"), ("Последнего", "Последней"),
    ("Первого", "Первой"), ("Тройного", "Тройной"),
    ("Дырявого", "Дырявой"),
]

# профили голов -> родительный: «Голова Нотча»
_PROFILE_RU = {"Notch": "Нотча", "jeb_": "Джеба",
               "Dinnerbone": "Диннерборна", "Grumm": "Грумма"}

# мобы спавн-яиц/вёдер: (именительный, родительный, род) - род None =
# фраза, прилагательное уже внутри («Древний Страж»); род (м/ж/ср)
# согласует прилагательные имени моба (механизм _inflect_adj из
# gen_enchantments - здесь через готовые формы _ADJ/_GEN_ADJ)
_MOB_RU = {
    "allay": ("Эллей", "Эллея", "м"),
    "armadillo": ("Броненосец", "Броненосца", "м"),
    "axolotl": ("Аксолотль", "Аксолотля", "м"),
    "bat": ("Летучая Мышь", "Летучей Мыши", "ж"),
    "bee": ("Пчела", "Пчелы", "ж"),
    "blaze": ("Блейз", "Блейза", "м"),
    "bogged": ("Боггед", "Боггеда", "м"),
    "breeze": ("Бриз", "Бриза", "м"),
    "camel": ("Верблюд", "Верблюда", "м"),
    "camel_husk": ("Мумия Верблюда", "Мумии Верблюда", None),
    "cat": ("Кошка", "Кошки", "ж"),
    "cave_spider": ("Пещерный Паук", "Пещерного Паука", None),
    "chicken": ("Курица", "Курицы", "ж"),
    "cod": ("Треска", "Трески", "ж"),
    "copper_golem": ("Медный Голем", "Медного Голема", None),
    "cow": ("Корова", "Коровы", "ж"),
    "creaking": ("Скрипун", "Скрипуна", "м"),
    "creeper": ("Крипер", "Крипера", "м"),
    "dolphin": ("Дельфин", "Дельфина", "м"),
    "donkey": ("Осёл", "Осла", "м"),
    "drowned": ("Утопленник", "Утопленника", "м"),
    "elder_guardian": ("Древний Страж", "Древнего Стража", None),
    "ender_dragon": ("Дракон Края", "Дракона Края", None),
    "enderman": ("Эндермен", "Эндермена", "м"),
    "endermite": ("Эндермит", "Эндермита", "м"),
    "evoker": ("Призыватель", "Призывателя", "м"),
    "fox": ("Лиса", "Лисы", "ж"),
    "frog": ("Жаба", "Жабы", "ж"),
    "ghast": ("Гаст", "Гаста", "м"),
    "glow_squid": ("Светящийся Спрут", "Светящегося Спрута", None),
    "goat": ("Коза", "Козы", "ж"),
    "guardian": ("Страж", "Стража", "м"),
    "happy_ghast": ("Счастливый Гаст", "Счастливого Гаста", None),
    "hoglin": ("Хоглин", "Хоглина", "м"),
    "horse": ("Лошадь", "Лошади", "ж"),
    "husk": ("Зомби-Оболочка", "Зомби-Оболочки", None),
    "iron_golem": ("Железный Голем", "Железного Голема", None),
    "llama": ("Лама", "Ламы", "ж"),
    "magma_cube": ("Магмовый Куб", "Магмового Куба", None),
    "mooshroom": ("Грибная Корова", "Грибной Коровы", None),
    "mule": ("Мул", "Мула", "м"),
    "nautilus": ("Наутилус", "Наутилуса", "м"),
    "ocelot": ("Оцелот", "Оцелота", "м"),
    "panda": ("Панда", "Панды", "ж"),
    "parched": ("Пересохший Зомби", "Пересохшего Зомби", None),
    "parrot": ("Попугай", "Попугая", "м"),
    "phantom": ("Фантом", "Фантома", "м"),
    "pig": ("Свинья", "Свиньи", "ж"),
    "piglin": ("Пиглин", "Пиглина", "м"),
    "piglin_brute": ("Пиглин-Громила", "Пиглина-Громилы", None),
    "pillager": ("Разбойник", "Разбойника", "м"),
    "polar_bear": ("Полярный Медведь", "Полярного Медведя", None),
    "pufferfish": ("Рыба-Ёж", "Рыбы-Ежа", None),
    "rabbit": ("Кролик", "Кролика", "м"),
    "ravager": ("Разоритель", "Разорителя", "м"),
    "salmon": ("Лосось", "Лосося", "м"),
    "sheep": ("Овца", "Овцы", "ж"),
    "shulker": ("Шалкер", "Шалкера", "м"),
    "silverfish": ("Чешуйница", "Чешуйницы", "ж"),
    "skeleton": ("Скелет", "Скелета", "м"),
    "skeleton_horse": ("Лошадь-Скелет", "Лошади-Скелета", None),
    "slime": ("Слизень", "Слизня", "м"),
    "sniffer": ("Нюхач", "Нюхача", "м"),
    "snow_golem": ("Снежный Голем", "Снежного Голема", None),
    "spider": ("Паук", "Паука", "м"),
    "squid": ("Спрут", "Спрута", "м"),
    "stray": ("Странник", "Странника", "м"),
    "strider": ("Страйдер", "Страйдера", "м"),
    "sulfur_cube": ("Серный Куб", "Серного Куба", None),
    "tadpole": ("Головастик", "Головастика", "м"),
    "trader_llama": ("Лама Торговца", "Ламы Торговца", None),
    "tropical_fish": ("Тропическая Рыба", "Тропической Рыбы", None),
    "turtle": ("Черепаха", "Черепахи", "ж"),
    "vex": ("Досаждатель", "Досаждателя", "м"),
    "villager": ("Житель", "Жителя", "м"),
    "vindicator": ("Поборник", "Поборника", "м"),
    "wandering_trader": ("Странствующий Торговец",
                          "Странствующего Торговца", None),
    "warden": ("Варден", "Вардена", "м"),
    "witch": ("Ведьма", "Ведьмы", "ж"),
    "wither": ("Иссушитель", "Иссушителя", "м"),
    "wither_skeleton": ("Скелет-Иссушитель", "Скелета-Иссушителя", None),
    "wolf": ("Волк", "Волка", "м"),
    "zoglin": ("Зоглин", "Зоглина", "м"),
    "zombie": ("Зомби", "Зомби", "м"),
    "zombie_horse": ("Лошадь-Зомби", "Лошади-Зомби", None),
    "zombie_nautilus": ("Зомби-Наутилус", "Зомби-Наутилуса", None),
    "zombie_villager": ("Зомби-Житель", "Зомби-Жителя", None),
    "zombified_piglin": ("Зомбированный Пиглин",
                          "Зомбированного Пиглина", None),
}

# атрибуты NBT мобов ({id, base} - формат AttributeInstance$Packed, тот
# же набор и диапазоны, что в gen_structures.ATTRIBUTE_RANGES; чужие
# мобу атрибуты при загрузке молча пропускаются)
_MOB_ATTRS = {
    "minecraft:max_health": (10.0, 60.0),
    "minecraft:attack_damage": (1.0, 12.0),
    "minecraft:movement_speed": (0.15, 0.35),
    "minecraft:follow_range": (16.0, 48.0),
    "minecraft:armor": (0.0, 10.0),
    "minecraft:armor_toughness": (0.0, 5.0),
    "minecraft:attack_speed": (0.5, 2.0),
    "minecraft:knockback_resistance": (0.0, 0.5),
    "minecraft:max_absorption": (0.0, 10.0),
    "minecraft:scale": (0.7, 1.5),
    "minecraft:jump_strength": (0.3, 0.7),
    "minecraft:safe_fall_distance": (3.0, 10.0),
    "minecraft:gravity": (0.04, 0.12),
}

# мобы с ванильной таблицей entities/<моб> (fallback DeathLootTable,
# тот же список, что gen_structures.MOB_LOOT_TABLES)
_MOB_LOOT_TABLES = frozenset("""
allay armadillo axolotl bat bee blaze bogged breeze camel camel_husk
chicken copper_golem cow creaking creeper cave_spider cat dolphin
donkey drowned elder_guardian enderman endermite evoker
fox frog ghast giant glow_squid goat guardian happy_ghast hoglin horse
husk illusioner iron_golem llama magma_cube mooshroom mule nautilus
ocelot panda parched parrot phantom pig piglin piglin_brute pillager
polar_bear pufferfish rabbit ravager salmon sheep shulker silverfish
skeleton skeleton_horse slime sniffer snow_golem spider squid stray
strider sulfur_cube tadpole trader_llama tropical_fish turtle vex
villager vindicator wandering_trader warden witch wither_skeleton
wolf zoglin zombie zombie_horse zombie_nautilus zombie_villager
zombified_piglin""".split())

# мобы для block_entity_data-спавнера (все - враждебные, с яйцами и
# таблицами entities/<моб>; формат сверен с ванильными .nbt-шаблонами)
_SPAWNER_MOBS = ["zombie", "skeleton", "husk", "stray", "bogged",
                 "spider", "cave_spider", "creeper", "silverfish",
                 "blaze", "magma_cube", "slime", "zombified_piglin",
                 "piglin", "wither_skeleton", "drowned", "witch",
                 "enderman", "breeze", "creaking"]

# блочные контейнеры, поддерживающие NBT-тег LootTable
# (RandomizableContainer: сундуки/бочки/шалкеры/диспенсеры/воронки/
# кувшины; печи и варочные стойки - НЕТ, вагонетки - не блоки)
_LOOT_BED = frozenset(
    ["minecraft:chest", "minecraft:trapped_chest", "minecraft:barrel",
     "minecraft:dispenser", "minecraft:dropper", "minecraft:hopper",
     "minecraft:decorated_pot"] + _COPPER_CHESTS +
    ["minecraft:%s_shulker_box" % c for c in DYE_COLORS])

# ванильные chest-таблицы для LootTable в block_entity_data (только
# chests/* - открытие сундука не даёт fishing-контекст)
_VANILLA_CHEST_TABLES = [v for v in VANILLA_TABLES
                         if v.startswith("minecraft:chests/")]


def _mob_title(rng, mob):
    """Русское имя моба для CustomName NBT: «Древний Скелет»,
    «Ведьма Мёртвой Звезды». Возвращает текстовый компонент."""
    entry = _MOB_RU.get(mob)
    if entry is None:  # неизвестный моб - собственное имя слогами
        return {"text": _proper_name(rng),
                "color": rng.choice(_NAME_COLORS), "italic": False}
    nom, _gen, g = entry
    r = rng.random()
    if g and r < 0.5:  # «Древний Скелет» / «Древняя Ведьма»
        adj = rng.choice(_ADJ)[_GENDER_IDX[g]]
        title = "%s %s" % (adj, nom)
    elif r < 0.75:  # «Скелет Мёртвой Звезды»
        title = "%s %s" % (nom, rng.choice(_GENITIVE))
    else:
        title = nom
    comp = {"text": title, "color": rng.choice(_NAME_COLORS),
            "italic": False}
    if rng.random() < 0.2:
        comp["bold"] = True
    return comp


_SLOT_PART = {"head": "helmet", "chest": "chestplate",
              "legs": "leggings", "feet": "boots"}


def _nbt_stack(rng, cls, slot=None):
    """ItemStack для equipment моба в NBT: {id, count, components}
    (формат EntityEquipment.CODEC; зачарования - тематические по типу
    предмета, как в gen_structures._rand_item_stack, но имена русские).
    Броня подбирается ПОД запрошенный слот (шлем - в head, сапоги - в
    feet, как в ванильных equipment-таблицах); в слоты рук броня не
    попадает. Атрибут-модификаторы здесь не генерируются - ванильные
    базовые характеристики предмета действуют как есть."""
    if cls == "armor":
        part = _SLOT_PART.get(slot)
        pool = ([i for i in ARMOR if i.endswith("_" + part)] if part
                else ARMOR)
    elif cls == "weapon":
        pool = SWORDS + SPEARS + AXES + MACES + TRIDENTS + BOWS + CROSSBOWS
    else:  # «любой» - слот руки: броню в руку не берём
        pool = (SWORDS + SPEARS + AXES + MACES
                + ["minecraft:shield", "minecraft:totem_of_undying"])
    item = rng.choice(pool)
    out = {"id": item, "count": 1}
    comps = {}
    emap = _enchantments_map(rng, item)
    if emap and rng.random() < 0.7:
        comps["minecraft:enchantments"] = emap
        # кастомные зачарования - с lore-подсказкой «Имя - описание»
        # (дропнув с моба, предмет расскажет, что умеет)
        hints = _ench_hint_lines(rng, comps, [])
        if hints:
            comps["minecraft:lore"] = hints
    # имя - только снаряжению с компонентами (есть что раскрывать)
    if comps and rng.random() < 0.3:
        comps["minecraft:item_name"] = _reveal_name(rng, item, comps, [])
    if rng.random() < 0.2:
        comps["minecraft:unbreakable"] = {}
    if comps:
        out["components"] = comps
    return out


def _mob_nbt(rng, mob, table_ids):
    """Полный NBT «особого» моба для entity_data спавн-яйца и SpawnData
    спавнера - зеркало gen_structures._rand_mob_nbt (кастомное имя с
    цветом, атрибуты, снаряжение с зачарованиями, эффекты,
    DeathLootTable на НАШИ таблицы, Glowing/PersistenceRequired/...).
    NoAI и Invulnerable НЕ ставятся НИКОГДА - моб должен жить и быть
    убиваемым. Булевы значения пишутся как JSON true/false - в NBT это
    байты (как HasNectar у пчёл в bees-компоненте, серверная проба
    26.2)."""
    nbt = {"id": "minecraft:" + mob}
    if rng.random() < 0.9:
        nbt["CustomName"] = _mob_title(rng, mob)
        if rng.random() < 0.7:
            nbt["CustomNameVisible"] = True
    # атрибуты (AttributeInstance$Packed; base - float с десятичной
    # точкой, JSON-дубль читается float-полем кодека)
    attrs = []
    max_health = None
    for aid in rng.sample(sorted(_MOB_ATTRS), rng.randint(1, 3)):
        lo, hi = _MOB_ATTRS[aid]
        base = round(rng.uniform(lo, hi), 2)
        if aid == "minecraft:max_health":
            max_health = base
        attrs.append({"id": aid, "base": base})
    if max_health is None and rng.random() < 0.6:
        max_health = round(rng.uniform(10.0, 60.0), 1)
        attrs.append({"id": "minecraft:max_health", "base": max_health})
    nbt["attributes"] = attrs
    if max_health is not None:
        nbt["Health"] = max_health  # не выше max_health (движок клампит)
    # снаряжение (EquipmentTable.CODEC: map слот -> ItemStack); броня -
    # строго по слоту (см. _nbt_stack)
    equip = {}
    if rng.random() < 0.55:
        equip["mainhand"] = _nbt_stack(rng, "weapon")
    if rng.random() < 0.15:
        equip["offhand"] = _nbt_stack(rng, "any")
    for slot in ("head", "chest", "legs", "feet"):
        if rng.random() < 0.35:
            equip[slot] = _nbt_stack(rng, "armor", slot)
    if equip:
        nbt["equipment"] = equip
        if rng.random() < 0.6:
            nbt["drop_chances"] = {
                slot: round(rng.uniform(0.0, 1.0), 3)
                for slot in rng.sample(sorted(equip),
                                       rng.randint(1, len(equip)))}
    # активные эффекты (формат сохранения 1.20.5+: active_effects)
    if rng.random() < 0.2:
        nbt["active_effects"] = [
            {"id": "minecraft:" + rng.choice(MOB_EFFECTS),
             "amplifier": rng.randint(0, 1),
             "duration": rng.randint(200, 1200)}
            for _ in range(rng.randint(1, 2))]
    # DeathLootTable: НАША таблица измерения или ванильная entities/<моб>
    if table_ids and rng.random() < 0.6:
        nbt["DeathLootTable"] = rng.choice(table_ids)
    elif mob in _MOB_LOOT_TABLES:
        nbt["DeathLootTable"] = "minecraft:entities/" + mob
    # флаги (каждый - со своим шансом, как у структурных боссов);
    # NoAI/Invulnerable запрещены: моб должен жить и быть убиваемым
    if rng.random() < 0.6:
        nbt["PersistenceRequired"] = True
    if rng.random() < 0.25:
        nbt["Glowing"] = True
    if rng.random() < 0.10:
        nbt["Fire"] = rng.choice([20, 60, 100])  # short (числ. коэрцция)
    if rng.random() < 0.15:
        nbt["CanPickUpLoot"] = True
    if rng.random() < 0.10:
        nbt["LeftHanded"] = True
    if rng.random() < 0.05:
        nbt["Silent"] = True
    return nbt


def _is_material(item):
    if item in ULTRA_RARE_VALUABLES or item in RARE_VALUABLES:
        return False
    """Возвращает True, если предмет является обычным материалом/ресурсом/блоком
    без активных боевых, защитных или интерактивных способностей."""
    kind = _kind_of(item)
    if kind in _MELEE_KINDS or kind in _TOOL_KINDS or kind in _ARMOR_KINDS:
        return False
    if kind in ("bow", "crossbow", "trident", "fishing_rod", "shield", "elytra"):
        return False
    if kind in ("book", "potion"):
        return False
    if item in FOOD or item in RAW_FOOD or item in BAD_FOOD:
        return False
    if item in POTIONS or item in ("minecraft:tipped_arrow", "minecraft:ominous_bottle",
                                  "minecraft:suspicious_stew"):
        return False
    if item in ENCH_BOOKS or item in ("minecraft:written_book", "minecraft:writable_book"):
        return False
    if item in ("minecraft:bundle",) or item.endswith("_bundle"):
        return False
    if item in CONTAINER_ITEMS or item == "minecraft:spawner":
        return False
    if item in MUSIC_DISCS or item in ("minecraft:goat_horn", "minecraft:compass",
                                      "minecraft:recovery_compass", "minecraft:filled_map",
                                      "minecraft:clock", "minecraft:spyglass"):
        return False
    if item in ("minecraft:painting", "minecraft:firework_rocket",
                "minecraft:firework_star") or item in ODDITIES or item.endswith("_head") or item.endswith("_skull"):
        return False
    if item in ("minecraft:beehive", "minecraft:bee_nest"):
        return False
    if item.endswith("_spawn_egg") or item.endswith("_banner"):
        return False
    if item in FISH_BUCKETS or item in ("minecraft:axolotl_bucket", "minecraft:salmon_bucket",
                                      "minecraft:tropical_fish_bucket", "minecraft:sulfur_cube_bucket"):
        return False
    if item in BLOCK_STATE_PROPS or item == "minecraft:note_block" or item == "minecraft:decorated_pot":
        return False
    if item in HORSE_ARMORS or item == "minecraft:wolf_armor":
        return False
    return True


def _nested_stack(rng):
    """Стек предметов ВНУТРИ компонента (container/bundle_contents/
    charged_projectiles): осмысленный класс предмета + мини-компоненты
    (зачарованная кирка, именное зелье с potion_contents...) +
    «ГЛУБОКАЯ» вложенность - компоненты внутри компонентов: фейерверк
    со взрывами, книга со страницами, рог с инструментом, пластинка с
    песней, арбалет с заряженными зельевыми стрелами.
    Стек-1 предметам count>1 нельзя (validateContainedItemSizes)."""
    pool, cls = _weighted(rng, [
        ((RESOURCES, "resource"), 24), ((FOOD, "food"), 14),
        ((VALUABLES, "valuable"), 12), ((JUNK, "junk"), 14),
        ((WEAPONS + ARMOR + TOOLS, "gear"), 12),
        ((ENCH_BOOKS + ["minecraft:written_book",
                        "minecraft:writable_book"], "book"), 8),
        ((POTIONS, "potion"), 6), ((MUSIC_DISCS, "disc"), 4),
        ((MISC, "misc"), 6)])
    item = rng.choice(pool)
    hi = {"resource": 12, "food": 6, "junk": 8, "valuable": 3}.get(cls, 1)
    if item in ULTRA_RARE_VALUABLES:
        s = {"id": item, "count": 1}
    elif item in RARE_VALUABLES:
        s = {"id": item, "count": 1 if rng.random() < 0.8 else 2}
    elif _is_material(item) or cls == "resource":
        lo = 4 if item not in _STACK1 else 1
        hi_mat = 32 if (cls == "resource" or _is_material(item)) else 12
        s = {"id": item, "count": 1 if item in _STACK1 else rng.randint(lo, hi_mat)}
    else:
        s = {"id": item, "count": 1 if item in _STACK1 else rng.randint(1, hi)}
    if _is_material(item):
        if rng.random() < 0.06:
            nprefix = "nested_%d" % rng.randint(0, 10 ** 6)
            ncomp = {
                "minecraft:attribute_modifiers": _attribute_modifiers(
                    rng, item, nprefix, None, strong=True),
                "minecraft:rarity": rng.choice(["rare", "epic"]),
                "minecraft:enchantment_glint_override": True,
            }
            ncomp["minecraft:item_name"] = _reveal_name(rng, item, ncomp, [])
            clines = _component_lore(rng, item, ncomp, [])
            if clines:
                ncomp["minecraft:lore"] = clines
            s["components"] = ncomp
        return s
    ncomp = {}
    if cls == "gear" and rng.random() < 0.5:
        emap = _enchantments_map(rng, item)
        if emap:
            ncomp["minecraft:enchantments"] = emap
    elif item in ENCH_BOOKS:
        emap = _enchantments_map(rng, item)
        if emap:
            ncomp["minecraft:stored_enchantments"] = emap
    elif item in POTIONS + ["minecraft:tipped_arrow"]:
        ncomp["minecraft:potion_contents"] = _potion_contents(
            rng, long_durations=item in POTIONS)
    if rng.random() < 0.45:
        # глубокая вложенность: предмет «живёт» даже внутри контейнера -
        # в т.ч. ПОВЕРХ зачарований (арбалет с зачарованиями И зарядом)
        if item == "minecraft:firework_rocket":
            ncomp["minecraft:fireworks"] = {
                "flight_duration": rng.randint(1, 3),
                "explosions": [_firework_explosion(rng)
                               for _ in range(rng.randint(1, 2))]}
        elif item == "minecraft:firework_star":
            ncomp["minecraft:firework_explosion"] = _firework_explosion(rng)
        elif item == "minecraft:written_book":
            ncomp["minecraft:written_book_content"] = {
                "title": {"raw": rng.choice(_BOOK_TITLES),
                          "filtered": "Записки"},
                "author": rng.choice(_RU_AUTHORS),
                "generation": rng.randint(0, 3),
                "resolved": rng.random() < 0.5,
                "pages": _book_pages(rng, rng.randint(2, 3), True)}
        elif item == "minecraft:writable_book":
            ncomp["minecraft:writable_book_content"] = {
                "pages": _book_pages(rng, rng.randint(2, 3), False)}
        elif item == "minecraft:goat_horn":
            ncomp["minecraft:instrument"] = \
                "minecraft:" + rng.choice(INSTRUMENTS)
        elif item in MUSIC_DISCS:
            ncomp["minecraft:jukebox_playable"] = \
                "minecraft:" + rng.choice(JUKEBOX_SONGS)
        elif item in CROSSBOWS:
            ps = {"id": rng.choice(["minecraft:arrow",
                                    "minecraft:tipped_arrow"]),
                  "count": rng.randint(1, 3)}
            if ps["id"] == "minecraft:tipped_arrow" \
                    or rng.random() < 0.4:
                ps["components"] = {
                    "minecraft:potion_contents": _potion_contents(
                        rng, long_durations=False)}
            ncomp["minecraft:charged_projectiles"] = [ps]
        elif item in CONTAINER_ITEMS and rng.random() < 0.35:
            # матрёшка: контейнер внутри контейнера (1-2 слота, без
            # дальнейшей рекурсии - наполнение простыми стеками)
            tpool = rng.choice([RESOURCES, FOOD, VALUABLES, JUNK])
            max_slot = rng.choice([5, 9])
            slots = rng.sample(range(max_slot),
                               rng.randint(1, min(2, max_slot)))
            ncomp["minecraft:container"] = [
                {"slot": sl, "item": _fill_stack(rng, tpool)}
                for sl in slots]
    # имя - только предмету с компонентами (есть что раскрывать)
    if ncomp and rng.random() < 0.12:
        ncomp["minecraft:item_name"] = _reveal_name(rng, item, ncomp, [])
    if rng.random() < 0.08:
        ncomp["minecraft:rarity"] = _rarity(rng)
    # «только визуал» невозможен и в глубине: вложенный предмет с одной
    # косметикой получает работающую фичу (пассивное зачарование /
    # функциональный компонент), а кастомные зачарования - lore-подсказку
    _fix_visual_only(rng, item, ncomp, [],
                     "nested_%d" % rng.randint(0, 10 ** 6), None)
    hints = _ench_hint_lines(rng, ncomp, [])
    if hints:
        lore = list(ncomp.get("minecraft:lore") or [])
        lore.extend(hints)
        ncomp["minecraft:lore"] = lore
    if ncomp:
        s["components"] = ncomp
    return s


# спец-базовые существительные имён (item -> (слово, род));
# спавн-яйца/пластинки/мешки/шалкеры/знамёна/вёдра - по членству,
# см. _base_noun
_ITEM_BASES = {
    "minecraft:arrow": ("Стрела", "ж"),
    "minecraft:spectral_arrow": ("Стрела", "ж"),
    "minecraft:tipped_arrow": ("Стрела", "ж"),
    "minecraft:firework_rocket": ("Ракета", "ж"),
    "minecraft:firework_star": ("Звезда", "ж"),
    "minecraft:goat_horn": ("Рог", "м"),
    "minecraft:player_head": ("Голова", "ж"),
    "minecraft:spawner": ("Клетка", "ж"),
    "minecraft:beehive": ("Улей", "м"),
    "minecraft:bee_nest": ("Улей", "м"),
    "minecraft:decorated_pot": ("Кувшин", "м"),
    "minecraft:filled_map": ("Карта", "ж"),
    "minecraft:map": ("Карта", "ж"),
    "minecraft:compass": ("Компас", "м"),
    "minecraft:recovery_compass": ("Компас", "м"),
    "minecraft:clock": ("Часы", "мн"),
    "minecraft:spyglass": ("Труба", "ж"),
    "minecraft:bucket": ("Ведро", "ср"),
    "minecraft:ominous_bottle": ("Флакон", "м"),
    "minecraft:suspicious_stew": ("Похлёбка", "ж"),
    "minecraft:enchanted_book": ("Гримуар", "м"),
    "minecraft:writable_book": ("Тетрадь", "ж"),
    "minecraft:written_book": ("Том", "м"),
    # --- пополнение ---
    "minecraft:dragon_breath": ("Дыхание", "ср"),
    "minecraft:heart_of_the_sea": ("Сердце Моря", "ср"),
    "minecraft:nautilus_shell": ("Раковина", "ж"),
    "minecraft:painting": ("Полотно", "ср"),
    "minecraft:armor_stand": ("Манекен", "м"),
    "minecraft:end_crystal": ("Кристалл", "м"),
    "minecraft:wind_charge": ("Заряд", "м"),
    "minecraft:saddle": ("Седло", "ср"),
    "minecraft:shears": ("Ножницы", "мн"),
    "minecraft:flint_and_steel": ("Огниво", "ср"),
    "minecraft:lead": ("Поводок", "м"),
    "minecraft:name_tag": ("Бирка", "ж"),
    "minecraft:totem_of_undying": ("Тотем", "м"),
    "minecraft:experience_bottle": ("Склянка", "ж"),
    "minecraft:echo_shard": ("Осколок Эха", "м"),
}


def _base_noun(rng, item, kind):
    """Базовое существительное имени: спец-предметы - своё слово
    (Стрела/Яйцо/Мешок/...), прочее - по kind (_KIND_NOUNS)."""
    if item.endswith("_spawn_egg"):
        return ("Яйцо", "ср")
    if item in MUSIC_DISCS:
        return ("Пластинка", "ж")
    if item == "minecraft:bundle" or item.endswith("_bundle"):
        return ("Мешок", "м")
    if item.endswith("_shulker_box"):
        return ("Шалкер", "м")
    if item in CONTAINER_ITEMS:
        return ("Ящик", "м")
    if item.endswith("_banner"):
        return ("Знамя", "ср")
    if item.endswith("_bucket"):
        return ("Ведро", "ср")
    if item.endswith("_horse_armor"):
        return ("Попона", "ж")
    if item.endswith("minecart"):
        return ("Вагонетка", "ж")
    if item.endswith("_boat") or item.endswith("_raft"):
        return ("Лодка", "ж")
    if item.endswith("_pottery_sherd"):
        return ("Черепок", "м")
    if item.endswith("_smithing_template"):
        return ("Шаблон", "м")
    if item in _ITEM_BASES:
        return _ITEM_BASES[item]
    nouns = _KIND_NOUNS.get(kind) or _KIND_NOUNS["generic"]
    return rng.choice(nouns)


# статистика раскрытия имён (для самотеста: покрытие = seeded/named;
# сбрасывается тестом перед генерацией)
_REVEAL_STATS = {"named": 0, "seeded": 0}


def _reveal_name(rng, item, comps, funcs):
    """Имя предмета, РАСКРЫВАЮЩЕЕ его кастомные параметры (приём
    gen_enchantments._effect_name): potion_contents с огнестойкостью
    -> «Настой Огнестойкости», attribute_modifiers на attack_damage
    -> «Клинок Ярости», спавн-яйцо с кастомным мобом -> «Яйцо Древнего
    Скелета». Прилагательные согласованы с родом базового слова
    (_ADJ-кортежи + _GENDER_IDX - механизм _inflect_adj).

    ПОКРЫТИЕ ~100%: слово-источник есть у КАЖДОГО кастомного компонента
    (жалоба: «названия должны как-то раскрывать качества, а не быть
    полностью рандомными»); фолбэк rand_name - только когда «говорящих»
    компонентов нет совсем. Базовые ванильные модификаторы (id *_base*)
    НЕ считаются: они есть у любого меча, «Клинок Ярости» должен
    означать собственный бонус. trim в именах не упоминается
    (жалоба: «trim и так видно»)."""
    global _REVEAL_STATS
    _REVEAL_STATS["named"] += 1
    kind = _kind_of(item)
    noun, gender = _base_noun(rng, item, kind)
    gi = _GENDER_IDX[gender]
    seeds = []
    seen = set()

    def add(prio, word):
        if word and word not in seen:
            seen.add(word)
            seeds.append((prio, word))

    # спавн-яйцо: моб в родительном («Яйцо Скелета»); с entity_data -
    # «особый» моб, приоритет выше
    egg_mob = None
    if item.endswith("_spawn_egg"):
        ed = comps.get("minecraft:entity_data")
        mid = ed.get("id", "") if isinstance(ed, dict) else ""
        egg_mob = (mid.split(":", 1)[-1] or
                   item[len("minecraft:"):-len("_spawn_egg")])
        entry = _MOB_RU.get(egg_mob)
        if entry:
            add(10 if isinstance(ed, dict) else 8, entry[1])
    # зелье: функция set_potion или компонент potion_contents;
    # кастомные комбинации эффектов «главнее» стандартного зелья
    pid = None
    for f in funcs:
        if isinstance(f, dict) and f.get("function") == "minecraft:set_potion":
            pid = f.get("id")
    pc = comps.get("minecraft:potion_contents")
    if isinstance(pc, dict):
        if pc.get("potion"):
            pid = pc["potion"]
        for e in pc.get("custom_effects") or []:
            if isinstance(e, dict):
                add(9, _EFF_RU.get(str(e.get("id", "")).split(":")[-1]))
                break
    if pid:
        add(8, _POTION_RU.get(pid.split(":")[-1]))
    # эффекты похлёбки / consumable
    stew = comps.get("minecraft:suspicious_stew_effects")
    if isinstance(stew, list) and stew and isinstance(stew[0], dict):
        add(7, _EFF_RU.get(
            str(stew[0].get("id", "")).split(":")[-1]))
    cons = comps.get("minecraft:consumable")
    if isinstance(cons, dict):
        for eff in cons.get("on_consume_effects", []):
            if not isinstance(eff, dict):
                continue
            if eff.get("type") == "minecraft:apply_effects":
                for e in eff.get("effects", []):
                    add(7, _EFF_RU.get(
                        str(e.get("id", "")).split(":")[-1]))
                break
            if eff.get("type") == "minecraft:teleport_randomly":
                add(6, "Скачков")
                break
        else:
            if item not in FOOD and item not in RAW_FOOD \
                    and item not in BAD_FOOD:
                add(6, "Ужина")  # съедобный не-еда предмет
    # атрибут-модификаторы: самый «зрелищный» СОБСТВЕННЫЙ атрибут
    # (ванильные базовые модификаторы - id вида *_baseN - пропускаем:
    # они есть у любого предмета этого типа, «не урезать, а дополнить»
    # не значит «хвастаться заводской прошивкой»)
    best = None
    for mod in comps.get("minecraft:attribute_modifiers") or []:
        if (isinstance(mod, dict) and mod.get("type") in _ATTR_RU
                and "_base" not in str(mod.get("id", ""))):
            w, p = _ATTR_RU[mod["type"]]
            if best is None or p > best[0]:
                best = (p, w)
    if best:
        add(best[0], best[1])
    # зачарования (первое известное)
    for ekey in ("minecraft:enchantments", "minecraft:stored_enchantments"):
        emap = comps.get(ekey)
        if isinstance(emap, dict):
            for eid in emap:
                add(6, _ENCH_RU.get(eid.split(":")[-1]))
                break
    # одиночные компоненты - свои слова
    if "minecraft:unbreakable" in comps:
        add(5, "Вечности")
    if "minecraft:death_protection" in comps:
        add(8, "Бессмертия")
    if "minecraft:glider" in comps:
        add(6, "Полёта")
    if "minecraft:kinetic_weapon" in comps:
        add(7, "Сокрушения")
    if "minecraft:piercing_weapon" in comps:
        add(6, "Пронзания")
    if "minecraft:weapon" in comps:
        add(5, "Натиска")
    if "minecraft:blocks_attacks" in comps:
        add(5, "Заслона")
    if "minecraft:tool" in comps:
        add(5, "Дробления")
    if "minecraft:ominous_bottle_amplifier" in comps:
        add(6, "Дурного Знамения")
    if "minecraft:jukebox_playable" in comps:
        add(5, "Чужой Песни")
    # рог с конкретным инструментом: «Рог Тоски»
    ins = comps.get("minecraft:instrument")
    if isinstance(ins, str):
        add(6, INSTRUMENT_RU.get(ins.split(":")[-1]))
    if "minecraft:charged_projectiles" in comps:
        add(4, "Взвода")
    if comps.get("minecraft:pot_decorations"):
        add(3, "Росписи")
    if "minecraft:fireworks" in comps or \
            "minecraft:firework_explosion" in comps:
        add(5, "Залпа")
    prof = comps.get("minecraft:profile")
    if isinstance(prof, dict) and prof.get("name"):
        add(6, _PROFILE_RU.get(prof["name"]))
    if "minecraft:lodestone_tracker" in comps:
        add(4, "Дальнего Пути")
    if comps.get("minecraft:bundle_contents"):
        add(4, "Сокровищ")
    if comps.get("minecraft:banner_patterns"):
        add(4, "Узоров")
    if comps.get("minecraft:container"):
        add(4, "Припасов")
    if isinstance(comps.get("minecraft:container_loot"), dict):
        add(5, "Неведомого")
    if isinstance(comps.get("minecraft:block_state"), dict):
        add(4, "Уюта")
    # --- полное покрытие: слово для КАЖДОГО прочего компонента ---------
    # (жалоба: имена должны раскрывать качества ~100% предметов с
    # кастомными компонентами; раньше покрывалось ~59%)
    if "minecraft:attack_range" in comps:
        add(5, "Дальнего Боя")
    if "minecraft:swing_animation" in comps:
        add(4, "Замаха")
    if "minecraft:minimum_attack_charge" in comps:
        add(4, "Разгона")
    if "minecraft:damage_resistant" in comps:
        add(5, "Неприступности")
    if any(k in comps for k in ("minecraft:dyed_color",
                                "minecraft:base_color",
                                "minecraft:dye",
                                "minecraft:map_color")):
        add(4, "Окраса")
    if "minecraft:food" in comps:
        add(5, "Трапезы")
    if "minecraft:use_remainder" in comps:
        add(4, "Превращения")
    if "minecraft:potion_duration_scale" in comps:
        add(4, "Долгого Действия")
    if "minecraft:intangible_projectile" in comps:
        add(4, "Тумана")
    if "minecraft:block_entity_data" in comps:
        add(5, "Недр")
    if "minecraft:lock" in comps:
        add(4, "Запора")
    if "minecraft:writable_book_content" in comps:
        add(5, "Записок")
    if "minecraft:written_book_content" in comps:
        add(5, "Хроник")
    if "minecraft:painting/variant" in comps:
        add(5, "Чужой Кисти")
    if "minecraft:map_id" in comps:
        add(4, "Дальних Земель")
    if "minecraft:note_block_sound" in comps:
        add(4, "Чужого Голоса")
    if "minecraft:bucket_entity_data" in comps:
        add(6, "Глубин")
    if comps.get("minecraft:sulfur_cube_content"):
        add(4, "Серы")
    # варианты сущностей на вёдрах/яйцах (path-id: axolotl/variant,
    # tropical_fish/pattern, cat/sound_variant...) - «чужая кровь»
    for ck in comps:
        if "/" in ck and ck != "minecraft:painting/variant":
            add(5, "Чужой Крови")
            break
    if "minecraft:max_damage" in comps:
        add(4, "Закалки")
    if "minecraft:enchantable" in comps:
        add(4, "Отзыва")
    if "minecraft:repairable" in comps:
        add(4, "Ремонта")
    if "minecraft:break_sound" in comps:
        add(3, "Грохота")
    if "minecraft:max_stack_size" in comps:
        add(3, "Щедрости")
    if "minecraft:damage" in comps:
        add(3, "Старых Битв")
    if "minecraft:repair_cost" in comps:
        add(3, "Наковальни")
    if "minecraft:enchantment_glint_override" in comps:
        add(3, "Блеска")
    if "minecraft:rarity" in comps:
        add(3, "Диковины")
    if "minecraft:custom_data" in comps:
        add(3, "Нажитого")
    if "minecraft:custom_model_data" in comps:
        add(3, "Чужой Формы")
    if "minecraft:use_effects" in comps:
        add(4, "Отзвука")
    if "minecraft:equippable" in comps and kind == "generic":
        add(5, "Наряда")  # «дикая» надеваемая диковина
    # суффиксы - то, что «у предмета ЕСТЬ», а не «чем он является»:
    # «Улей с Пчёлами», «Карта с Метками» (trim НЕ упоминаем - орнамент
    # виден в тултипе и так, жалоба «не надо подсказки»)
    suffixes = []
    if comps.get("minecraft:bees"):
        suffixes.append("с Пчёлами")
    if comps.get("minecraft:map_decorations"):
        suffixes.append("с Метками")
    if comps.get("minecraft:container"):
        suffixes.append("с Припасами")
    seeds.sort(key=lambda p: -p[0])
    if not seeds:
        return rand_name(rng, item)
    _REVEAL_STATS["seeded"] += 1
    lead = seeds[0][1]
    second = seeds[1][1] if len(seeds) > 1 else None
    # сборка: у яиц прилагательное может стоять при мобе в родительном
    if egg_mob is not None:
        entry = _MOB_RU.get(egg_mob)
        mg = entry[2] if entry else None
        r = rng.random()
        if r < 0.30:
            title = "%s %s" % (noun, lead)
        elif r < 0.60 and mg in ("м", "ср", "ж"):
            ga = rng.choice(_GEN_ADJ)
            title = "%s %s %s" % (noun, ga[1] if mg == "ж" else ga[0],
                                  lead)
        elif r < 0.80:
            title = "%s %s %s" % (rng.choice(_ADJ)[gi], noun, lead)
        else:
            title = "%s %s %s" % (noun, lead, rng.choice(_GENITIVE))
    else:
        adj = rng.choice(_ADJ)[gi]
        r = rng.random()
        if r < 0.14 or len(noun) + len(lead) > 22:
            title = "%s %s" % (noun, lead)
        elif r < 0.42:
            title = "%s %s %s" % (adj, noun, lead)
        elif second and r < 0.58 and len(lead) + len(second) <= 18:
            title = "%s %s и %s" % (noun, lead, second)
        elif r < 0.78:
            title = "%s %s %s" % (noun, lead, rng.choice(_GENITIVE))
        else:
            title = "%s %s %s" % (adj, noun, lead)
    if len(title) > 38:  # от длиннот - компактная форма
        title = "%s %s" % (noun, lead)
    # суффикс приклеиваем ПОСЛЕ укорачивания - он короткий и информативный
    if suffixes:
        sfx = suffixes[0] if len(suffixes) == 1 else rng.choice(suffixes)
        if len(title) + len(sfx) + 1 <= 46:
            title = "%s %s" % (title, sfx)
    color = _hex_color(rng) if rng.random() < 0.2 else rng.choice(_NAME_COLORS)
    comp = {"text": title, "color": color, "italic": False}
    if rng.random() < 0.15:
        comp["bold"] = True
    if rng.random() < 0.04:
        comp["obfuscated"] = True
    return comp


# эффекты -> имя в ИМЕНИТЕЛЬНОМ падеже - для lore-строк
# («внутри дремлет огнестойкость»; реестр mob_effect 26.2)
_EFF_NOM = {
    "absorption": "поглощение", "bad_omen": "дурное знамение",
    "blindness": "слепота",
    "breath_of_the_nautilus": "дыхание наутилуса",
    "conduit_power": "морская сила", "darkness": "тьма",
    "dolphins_grace": "благодать дельфина",
    "fire_resistance": "огнестойкость", "glowing": "сияние",
    "haste": "спешка", "health_boost": "прилив здоровья",
    "hero_of_the_village": "слава героя деревни", "hunger": "голод",
    "infested": "заражение", "instant_damage": "мгновенная боль",
    "instant_health": "мгновенное исцеление",
    "invisibility": "невидимость", "jump_boost": "заячий прыжок",
    "levitation": "левитация", "luck": "удача",
    "mining_fatigue": "усталость", "nausea": "дурнота",
    "night_vision": "ночное зрение", "oozing": "слизь",
    "poison": "яд", "raid_omen": "знамение рейда",
    "regeneration": "регенерация", "resistance": "стойкость",
    "saturation": "сытость", "slow_falling": "медленное падение",
    "slowness": "медлительность", "speed": "скорость",
    "strength": "сила", "trial_omen": "знамение испытания",
    "unluck": "неудача", "water_breathing": "подводное дыхание",
    "weakness": "слабость", "weaving": "плетение",
    "wind_charged": "заряд ветра", "wither": "иссушение",
}

_LORE_COLORS = ["gray", "dark_gray", "blue", "dark_aqua"]


def _fmt_num(v):
    """Число без лишних нулей: 3 -> «3», 2.5 -> «2.5»."""
    return "%g" % v


def _component_lore(rng, item, comps, funcs):
    """Lore-строки ИЗ ФАКТИЧЕСКОГО содержимого предмета (жалоба:
    «lore должен как-то раскрывать качества, а не быть полностью
    рандомным"): зелья - «внутри дремлет огнестойкость», атрибуты -
    «тяжесть даёт +2 брони», чары, еда, планер «планирует, как семя
    клёна», инструмент, пчёлы, книги... Возвращает 0-3 строки; 0 -
    раскрыть нечего, lore не ставится ВООБЩЕ (случайный флейвор
    добавляет только вызывающий блок, и редко). Базовые ванильные
    модификаторы (id *_base*) пропускаются - они и так видны в тултипе;
    trim не описываем (жалоба: «trim и так видно»)."""
    cand = []
    # зелье (функция set_potion или компонент potion_contents);
    # кастомные комбинации «главнее» стандартного зелья
    pid = None
    for f in funcs:
        if isinstance(f, dict) and f.get("function") == "minecraft:set_potion":
            pid = f.get("id")
    pc = comps.get("minecraft:potion_contents")
    if isinstance(pc, dict):
        effs = pc.get("custom_effects") or []
        if effs and isinstance(effs[0], dict):
            pid = str(effs[0].get("id", ""))
        elif pc.get("potion"):
            pid = pc["potion"]
    if pid:
        nom = _EFF_NOM.get(str(pid).split(":")[-1])
        if nom:
            cand.append("Внутри дремлет %s." % nom)
    stew = comps.get("minecraft:suspicious_stew_effects")
    if isinstance(stew, list) and stew and isinstance(stew[0], dict):
        nom = _EFF_NOM.get(str(stew[0].get("id", "")).split(":")[-1])
        if nom:
            cand.append("Внутри дремлет %s." % nom)
    cons = comps.get("minecraft:consumable")
    if isinstance(cons, dict):
        for eff in cons.get("on_consume_effects") or []:
            if not isinstance(eff, dict):
                continue
            if eff.get("type") == "minecraft:apply_effects":
                es = eff.get("effects") or []
                if es and isinstance(es[0], dict):
                    nom = _EFF_NOM.get(
                        str(es[0].get("id", "")).split(":")[-1])
                    if nom:
                        cand.append("После еды ждёт %s." % nom)
                break
            if eff.get("type") == "minecraft:teleport_randomly":
                cand.append("После еды переносит в случайное место.")
                break
    # attribute modifiers omitted from lore per requirement
    food = comps.get("minecraft:food")
    if isinstance(food, dict):
        cand.append("Утоляет голод (%s ед.)."
                    % _fmt_num(food.get("nutrition", 1)))
    if "minecraft:use_remainder" in comps:
        cand.append("После еды что-то останется.")
    # боевые и рабочие качества
    if "minecraft:glider" in comps:
        cand.append("Планирует, как семя клёна.")
    if "minecraft:unbreakable" in comps:
        cand.append("Не изнашивается совсем.")
    if "minecraft:death_protection" in comps:
        cand.append("Однажды спасёт от смерти.")
    if "minecraft:blocks_attacks" in comps:
        cand.append("Держит удар на замахе.")
    if "minecraft:kinetic_weapon" in comps:
        cand.append("Сила удара растёт в падении.")
    if "minecraft:piercing_weapon" in comps:
        cand.append("Пронзает и сбивает с седла.")
    wc = comps.get("minecraft:weapon")
    if isinstance(wc, dict) and wc.get("disable_blocking_for_seconds"):
        cand.append("Выбивает щит из рук.")
    tc = comps.get("minecraft:tool")
    if isinstance(tc, dict):
        rules = tc.get("rules") or []
        if rules and isinstance(rules[0], dict) and rules[0].get("speed"):
            cand.append("Заточено для работы (скорость %s)."
                        % _fmt_num(rules[0]["speed"]))
    if "minecraft:attack_range" in comps:
        cand.append("Бьёт дальше, чем кажется.")
    if "minecraft:minimum_attack_charge" in comps:
        cand.append("Бьёт только с разгона.")
    if "minecraft:enchantable" in comps:
        cand.append("Охотно берёт чары.")
    if "minecraft:repairable" in comps:
        cand.append("Чинится на наковальне.")
    if "minecraft:damage_resistant" in comps:
        cand.append("Не страшится стихий.")
    if "minecraft:max_damage" in comps:
        cand.append("Закалено прочнее обычного.")
    if "minecraft:intangible_projectile" in comps:
        cand.append("Не берётся руками.")
    # содержимое и «начинка»
    bees = comps.get("minecraft:bees")
    if isinstance(bees, list) and bees:
        cand.append("Внутри гудят пчёлы (%d шт.)." % len(bees))
    if comps.get("minecraft:container"):
        cand.append("Наполнено чужим добром.")
    if comps.get("minecraft:bundle_contents"):
        cand.append("Связка припасов.")
    if "minecraft:charged_projectiles" in comps:
        cand.append("Заряжен и готов.")
    fw = comps.get("minecraft:fireworks")
    if isinstance(fw, dict) and fw.get("explosions"):
        cand.append("Гремит в небе (%d огней)."
                    % len(fw["explosions"]))
    elif "minecraft:firework_explosion" in comps:
        cand.append("Оставит след в небе.")
    if "minecraft:jukebox_playable" in comps:
        cand.append("Поёт, если поставить.")
    ins = comps.get("minecraft:instrument")
    if isinstance(ins, str):
        w = INSTRUMENT_RU.get(ins.split(":")[-1])
        if w:
            cand.append("Играет мелодию %s." % w.lower())
    wbc = comps.get("minecraft:written_book_content")
    if isinstance(wbc, dict) and wbc.get("pages"):
        cand.append("Чей-то дневник (%d стр.)." % len(wbc["pages"]))
    wbk = comps.get("minecraft:writable_book_content")
    if isinstance(wbk, dict) and wbk.get("pages"):
        cand.append("Записки на %d страницах." % len(wbk["pages"]))
    prof = comps.get("minecraft:profile")
    if isinstance(prof, dict) and prof.get("name"):
        cand.append("Носит чужое лицо.")
    if comps.get("minecraft:map_decorations"):
        cand.append("Испещрено метками.")
    if "minecraft:lodestone_tracker" in comps:
        cand.append("Всегда смотрит в одну точку.")
    if "minecraft:ominous_bottle_amplifier" in comps:
        cand.append("Пахнет дурным знамением.")
    if any(k in comps for k in ("minecraft:dyed_color", "minecraft:dye",
                                "minecraft:base_color")):
        cand.append("Выкрашено вручную.")
    if "minecraft:max_stack_size" in comps:
        cand.append("Складывается щедрее прочих.")
    eq = comps.get("minecraft:equippable")
    if isinstance(eq, dict) and _kind_of(item) == "generic":
        cand.append("Можно надеть, как диковину.")
    if not cand:
        return []
    k = _weighted(rng, [(1, 30), (2, 40), (3, 30)])
    k = min(k, len(cand))
    return [{"text": s, "color": rng.choice(_LORE_COLORS), "italic": True}
            for s in rng.sample(cand, k)]


# «мобильная» экипировка: попоны/наутилусовые брони/упряжи/волчья броня -
# надеваются на животных, а не на игрока; «дикий» equippable на них
# не ставим (как и на оружие/инструменты - копьё обуть нельзя)
_MOB_GEAR_ITEMS = frozenset(
    HORSE_ARMORS + [i for i in ALL_ITEMS if i.endswith("_harness")]
    + ["minecraft:wolf_armor"])

# ---------------------------------------------------------------------------
# USE_REMAINDER: пул остатков после еды (все id существуют в реестре
# 26.2 и стакаются - но мы всегда выдаём count 1)
# ---------------------------------------------------------------------------
_REMAINDER_POOL = [
    "minecraft:bone", "minecraft:paper", "minecraft:candle",
    "minecraft:charcoal", "minecraft:feather", "minecraft:flint",
    "minecraft:string", "minecraft:leather", "minecraft:clay_ball",
    "minecraft:gold_nugget",
]

# «человеческое» имя остатка для КАСТОМНОГО именного варианта
# («Косточка от похлёбки»)
_REMAINDER_NOUNS = {
    "minecraft:bone": "Косточка",
    "minecraft:paper": "Бумажка",
    "minecraft:candle": "Огарок",
    "minecraft:charcoal": "Уголёк",
    "minecraft:feather": "Перышко",
    "minecraft:flint": "Кремешок",
    "minecraft:string": "Верёвочка",
    "minecraft:leather": "Лоскуток",
    "minecraft:clay_ball": "Комочек",
    "minecraft:gold_nugget": "Самородочек",
}

# «...от чего» - родительный падеж трапезы (согласование не нужно)
_REMAINDER_FROM = [
    "от похлёбки", "от ужина", "от обеда", "от трапезы",
    "от пиршества", "от перекуса", "от варева", "от стряпни",
    "от каши", "от хлеба",
]

# редкая lore-строка именного остатка
_REMAINDER_LORE = [
    "Помнит вкус чужого обеда.", "Пахнет стряпнёй.",
    "Отголосок трапезы.", "Кто-то хорошо поел.",
    "Давно остыло.", "Сувенир из чужого котла.",
]

# «косметические» компоненты: меняют только вид/звук/скрытые данные,
# НЕ игру - предмет, у которого кроме них ничего нет, «только с
# визуалом» (жалоба юзера: rarity + item_name = обычный предмет) и
# получает РАБОЧУЮ фичу через _fix_visual_only
_COSMETIC_KEYS = frozenset([
    # собственно визуал текста/имени/редкости (задание задачи)
    "minecraft:rarity", "minecraft:item_name", "minecraft:custom_name",
    "minecraft:lore",
    # блеск и данные без игрового эффекта
    "minecraft:enchantment_glint_override", "minecraft:custom_data",
    "minecraft:custom_model_data",
    # окраска
    "minecraft:dyed_color", "minecraft:base_color", "minecraft:dye",
    "minecraft:map_color",
    # видимые орнаменты и декор
    "minecraft:banner_patterns", "minecraft:block_state",
    "minecraft:profile", "minecraft:painting/variant",
    "minecraft:pot_decorations", "minecraft:map_decorations",
    "minecraft:trim", "minecraft:note_block_sound",
])


_BONUS_ONLY_KEYS = frozenset([
    "minecraft:repairable",
    "minecraft:swing_animation",
])

def _has_mechanical_uniqueness(comps, funcs=()):
    for k in comps:
        if k in _COSMETIC_KEYS or k in _BONUS_ONLY_KEYS:
            continue
        if k in ("minecraft:damage", "minecraft:repair_cost", "minecraft:break_sound"):
            continue
        return True
    if funcs:
        for f in funcs:
            if isinstance(f, dict):
                fn = f.get("function", "")
                if fn in ("minecraft:set_enchantments", "minecraft:set_potion", "minecraft:apply_bonus"):
                    return True
    return False

def _fix_visual_only(rng, item, comps, funcs, tag_prefix, equip_slot):
    """ФИКС «предмет только с визуалом» (жалоба юзера: предмет с rarity
    и item_name - по факту обычный). Если после генерации компонентов у
    предмета не осталось ФУНКЦИОНАЛЬНЫХ особенностей (только косметика
    из _COSMETIC_KEYS и нет функций лута), добавить работающую фичу:
      1) приоритет - ПАССИВНОЕ зачарование измерения (attributes/tick/
         location_changed/damage_immunity/prevent_* - действуют при
         ношении/удержании; через существующий механизм кастомных
         зачарований - карта minecraft:enchantments, как в
         _enchantments_map);
      2) фолбэк - функциональный компонент: potion_contents (зельям),
         glider (элитрам/нагрудным диковинам), consumable с эффектами
         (еде), attribute_modifiers с базовыми значениями (остальным).
    Возвращает True, если предмет был «только визуалом» и получил фичу."""
    if not comps or funcs:
        return False
    if any(k not in _COSMETIC_KEYS and k not in _BONUS_ONLY_KEYS for k in comps):
        return False
    if _is_material(item):
        return False
    kind = _kind_of(item)
    # ТОЛЬКО совместимые с предметом (предмет ? supported_items -
    # «спасение» не должно приклеивать зачарование брони к мечу);
    # книги - носитель, им можно любое
    pool = [e for e in CUSTOM_ENCHS
            if _ENCH_INFO.get(e, {}).get("passive")
            and _custom_ench_ok(e, item)]
    if pool:
        # предпочитаем зачарования, которые можно носить/держать (слоты
        # any либо «родной» слот предмета); неизвестные слоты - любое
        native = _KIND_SLOTS.get(kind)
        best = [e for e in pool
                if not _ENCH_INFO[e].get("slots")
                or "any" in _ENCH_INFO[e]["slots"]
                or (native and native in _ENCH_INFO[e]["slots"])]
        eid = rng.choice(best or pool)
        # книги хранят зачарования в stored_enchantments (сет компонент
        # enchanted_book), остальным - прямая карта enchantments
        if item in ENCH_BOOKS:
            comps["minecraft:stored_enchantments"] = {eid: _decaying_int(rng, 3)}
        else:
            comps["minecraft:enchantments"] = {eid: _decaying_int(rng, 3)}
        return True
    # фолбэк: функциональный компонент по классу предмета
    if item in POTIONS or item == "minecraft:tipped_arrow":
        comps["minecraft:potion_contents"] = _potion_contents(rng)
    elif kind == "elytra" or equip_slot == "chest":
        comps["minecraft:glider"] = {}
    elif item in FOOD or item in RAW_FOOD or item in BAD_FOOD:
        c = _consumable(rng)
        effs = c.get("on_consume_effects") or []
        if not any(isinstance(e, dict) and e.get("type") in (
                "minecraft:apply_effects", "minecraft:teleport_randomly")
                for e in effs):
            while True:
                eff = _consume_effect(rng)
                if eff.get("type") in ("minecraft:apply_effects",
                                        "minecraft:teleport_randomly"):
                    c.setdefault("on_consume_effects", []).append(eff)
                    break
        comps["minecraft:consumable"] = c
    else:
        comps["minecraft:attribute_modifiers"] = _attribute_modifiers(
            rng, item, tag_prefix, equip_slot)
    return True


def _ench_hint_lines(rng, comps, funcs):
    """Lore-подсказки к кастомным чарам предмета: только кастомные механики/чары."""
    ids = []
    for ekey in ("minecraft:enchantments", "minecraft:stored_enchantments"):
        emap = comps.get(ekey)
        if isinstance(emap, dict):
            ids.extend(e for e in emap if e in _ENCH_INFO and not str(e).startswith("minecraft:"))
    for f in funcs:
        if isinstance(f, dict) and f.get("function") == "minecraft:set_enchantments":
            emap = f.get("enchantments") or {}
            if isinstance(emap, dict):
                ids.extend(e for e in emap if e in _ENCH_INFO and not str(e).startswith("minecraft:"))
    out = []
    for e in list(dict.fromkeys(ids)):
        nm = _ENCH_INFO[e].get("name") or e
        desc = _ENCH_INFO[e].get("desc") or ""
        txt = "%s - %s" % (nm, desc) if desc else str(nm)
        out.append({"text": txt, "color": rng.choice(_LORE_COLORS),
                    "italic": True})
    return out


def _item_components(rng, item, char, tag_prefix, want_name, ns="minecraft",
                     table_ids=()):
    """Случайные компоненты для предмета. Возвращает (components, functions):
    часть вещей удобнее делать функциями (set_enchantments/set_potion).

    Все форматы сверены с jar 26.2 (javap + серверные пробы loot spawn):
    plоские массивы lore/attribute_modifiers/banner_patterns/pot_decorations,
    условия kinetic_weapon - одиночные объекты, swing_animation без
    namespace, lock - «голый» ItemPredicate, horse/variant - plain enum
    (без «minecraft:»), компоненты сущностей - path-id (cat/collar и т.п.).
    Шансы убывающие: «сильные» компоненты (death_protection, glider,
    container_loot...) выпадают редко.

    Имя (custom_name) ставится В КОНЦЕ, по фактическому содержимому -
    и ТОЛЬКО предмету, которому есть что раскрывать (компоненты,
    спавн-яйцо или функция set_potion/set_enchantments/set_instrument;
    чистому ванильному предмету полностью рандомное имя не нужно):
    имя РАСКРЫВАЕТ кастомные параметры (_reveal_name, как _effect_name
    у зачарований), lore - ИЗ компонентов (_component_lore), а
    item_name - только предмету с другими кастомными компонентами
    (предмет, у которого меняется лишь имя, - чистый ванильный, его
    не трогаем)."""
    comps = {}
    funcs = []
    if _is_material(item):
        if rng.random() < 0.06:
            comps["minecraft:attribute_modifiers"] = _attribute_modifiers(
                rng, item, tag_prefix, None, strong=True)
            comps["minecraft:rarity"] = rng.choice(["rare", "epic"])
            comps["minecraft:enchantment_glint_override"] = True
            comps["minecraft:item_name"] = _reveal_name(rng, item, comps, funcs)
            clines = _component_lore(rng, item, comps, funcs)
            if clines:
                if rng.random() < 0.40:
                    clines.append({"text": rng.choice(_LORE_LINES),
                                   "color": rng.choice(["gray", "dark_gray", "blue", "dark_aqua"]),
                                   "italic": True})
                comps["minecraft:lore"] = clines
            return comps, funcs
        else:
            return {}, []
    kind = _kind_of(item)
    gear = kind in _MELEE_KINDS or kind in _TOOL_KINDS or \
        kind in _ARMOR_KINDS or kind == "shield" or \
        kind in ("bow", "crossbow", "trident", "fishing_rod")
    foodish = item in FOOD or item in RAW_FOOD or item in BAD_FOOD
    # «дикий» equippable: ЛЮБУЮ диковину можно сделать надеваемой -
    # тогда же её атрибут-модификаторы получают СООТВЕТСТВУЮЩИЙ слот
    # (компонент работает, а не висит мёртвым грузом). ТОЛЬКО для
    # «рукастых» диковин (kind=generic, не damageable, не моб-экипировка):
    # оружие/инструменты обуть нельзя (жалоба: «копьё которое даёт бонусы
    # когда обуто - копьё нельзя обуть!»); на груди - изредка и планер
    # (glider работает только в chest-слоте)
    aslot = _armor_slot_for_item(item, kind)
    equip_slot = aslot
    if (not aslot and kind == "generic" and item not in _DAMAGEABLE
            and item not in _MOB_GEAR_ITEMS and not _is_material(item) and rng.random() < 0.015):
        if item.endswith("_skull") or item.endswith("_head") or item == "minecraft:carved_pumpkin":
            equip_slot = "head"
        else:
            equip_slot = rng.choice(["head", "chest", "legs", "feet"])
        comps["minecraft:equippable"] = _equippable(rng, equip_slot)
        if equip_slot == "chest" and rng.random() < 0.25:
            comps["minecraft:glider"] = {}
    # зачарования: компонентом (прямая карта) ИЛИ функцией set_enchantments
    if rng.random() < 0.75:
        emap = _enchantments_map(rng, item)
        if emap:
            if rng.random() < 0.6:
                comps["minecraft:enchantments"] = emap
            else:
                funcs.append({"function": "minecraft:set_enchantments",
                              "enchantments": {k: float(v)
                                               for k, v in emap.items()}})
    # enchanted_book хранит зачарования в stored_enchantments
    if item in ENCH_BOOKS:
        emap = _enchantments_map(rng, item)
        if emap:
            comps["minecraft:stored_enchantments"] = emap
    gearish = kind in _KIND_SLOTS and kind != "book"
    # Extra bonus roll for custom enchantments on gear / books (Requirement 10)
    cpool = [e for e in CUSTOM_ENCHS if _custom_ench_ok(e, item)]
    if cpool and (gearish or item in ENCH_BOOKS) and rng.random() < 0.55:
        ce = rng.choice(cpool)
        lvl = _decaying_int(rng, 3)
        ekey = "minecraft:stored_enchantments" if item in ENCH_BOOKS else "minecraft:enchantments"
        if ekey not in comps:
            comps[ekey] = {}
        if ce not in comps[ekey]:
            comps[ekey][ce] = lvl
    # атрибут-модификаторы (тематические пулы/слоты - см.
    # _attribute_modifiers; equip_slot - слот «дикого» equippable)
    attr_p = {"weapons": 0.5, "treasure": 0.30, "mixed": 0.35}.get(char, 0.10)
    if (gearish or equip_slot) and rng.random() < attr_p:
        comps["minecraft:attribute_modifiers"] = _attribute_modifiers(
            rng, item, tag_prefix, equip_slot)
    # ---------------- общие компоненты (любому предмету, редко) ----------
    if rng.random() < 0.10:
        comps["minecraft:enchantment_glint_override"] = rng.random() < 0.85
    if rng.random() < 0.25:
        comps["minecraft:rarity"] = _rarity(rng)
# custom_data removed as per specification
    # tooltip_display/tooltip_style НЕ генерируются: прятать компоненты
    # и рисовать рамки - запутывает игроков (жалоба; самотест грепает
    # сгенерированный JSON на эти ключи)
    if rng.random() < 0.04:  # эффекты при ВЗАИМОДЕЙСТВИИ (не еде)
        comps["minecraft:use_effects"] = {
            "can_sprint": rng.random() < 0.5,
            "interact_vibrations": rng.random() < 0.5,
            "speed_multiplier": round(rng.uniform(0.2, 1.0), 2)}  # <= 1.0!
    # ---------------- боевое снаряжение ----------------------------------
    if gearish and rng.random() < 0.10:
        base = rng.choice([80, 120, 250, 600, 1500])
        comps["minecraft:max_damage"] = int(base * rng.uniform(0.5, 2.0))
    # unbreakable - только предметам С прочностью (на не-damageable он
    # мёртвый: ломаться нечему)
    if (item in _DAMAGEABLE or "minecraft:max_damage" in comps) \
            and rng.random() < 0.10:
        comps["minecraft:unbreakable"] = {}
    if gear and rng.random() < 0.12:  # текущий износ (абсолютный int)
        comps["minecraft:damage"] = _decaying_int(rng, 40)
    if gear and rng.random() < 0.15:
        comps["minecraft:repair_cost"] = _decaying_int(rng, 8)
    has_any_ench = (
        bool(comps.get("minecraft:enchantments"))
        or bool(comps.get("minecraft:stored_enchantments"))
        or any(isinstance(f, dict) and f.get("function") == "minecraft:set_enchantments" for f in funcs)
    )
    if gear and not has_any_ench and rng.random() < 0.25:
        comps["minecraft:enchantable"] = {"value": rng.randint(15, 50)}
    if gear and _has_mechanical_uniqueness(comps, funcs) and rng.random() < 0.35:
        comps["minecraft:repairable"] = {
            "items": rng.choice(REPAIR_VARIANTS)}
    if gear and rng.random() < 0.06:
        # звук поломки предмета (Holder<SoundEvent> - id звука)
        comps["minecraft:break_sound"] = rng.choice(
            ["minecraft:entity.item.break", "minecraft:item.shield.break",
             "minecraft:block.bell.use",
             "minecraft:entity.zombie.break_wooden_door"])
    # размер стека - только «приятный бонус»: стакаться БОЛЬШЕ ванили
    # (65-99), и только недamageable предметам, у которых уже есть >=2
    # других кастомных компонента (в одиночку он бессмыслен). Значения
    # ниже 64 (наказание) и компонент stackable не генерируем ВООБЩЕ
    # НИКОГДА; damageable + max_stack_size>1 валидатор 26.2 отвергает
    # целиком - см. _DAMAGEABLE
    if (item not in _DAMAGEABLE
            and "minecraft:max_damage" not in comps
            and len(comps) >= 2 and rng.random() < 0.05):
        comps["minecraft:max_stack_size"] = rng.randint(65, 99)
    if kind in _TOOL_KINDS and rng.random() < 0.40:
        comps["minecraft:tool"] = _tool_rules(rng, kind)
    if kind in _MELEE_KINDS and rng.random() < 0.35:
        comps["minecraft:weapon"] = {
            "item_damage_per_attack": rng.randint(1, 3),
            "disable_blocking_for_seconds": round(rng.uniform(0.0, 8.0), 1)}
    if kind in _MELEE_KINDS and rng.random() < 0.20:
        mn = round(rng.uniform(0.5, 2.0), 2)
        comps["minecraft:attack_range"] = {
            "min_reach": mn,
            "max_reach": round(mn + rng.uniform(0.5, 2.5), 2),
            # hitbox_margin - ТОЛЬКО в [0.0; 1.0] (проверено сервером)
            "hitbox_margin": round(rng.uniform(0.0, 1.0), 2),
            "mob_factor": round(rng.uniform(0.5, 2.0), 2),
            "min_creative_reach": round(mn + 0.5, 2),
            "max_creative_reach": round(rng.uniform(4.0, 6.0), 2)}
    if kind in _MELEE_KINDS and _has_mechanical_uniqueness(comps, funcs) and rng.random() < 0.35:
        comps["minecraft:swing_animation"] = {
            "type": rng.choice(["stab", "whack", "none"]),
            "duration": rng.randint(3, 10)}
    if kind == "mace" and rng.random() < 0.50:
        comps["minecraft:kinetic_weapon"] = _kinetic_weapon(rng)
    if kind == "mace" and rng.random() < 0.30:
        comps["minecraft:minimum_attack_charge"] = round(
            rng.uniform(0.1, 0.9), 2)
    if kind == "spear" and rng.random() < 0.40:
        comps["minecraft:piercing_weapon"] = {
            "deals_knockback": rng.random() < 0.7,
            "dismounts": rng.random() < 0.5,
            "hit_sound": rng.choice(SOUNDS)}
    # ---------------- броня / щит / элитры -------------------------------
    # НАСТОЯЩЕЙ броне equippable НЕ генерируем: ванильный компонент уже
    # на предмете, и заменить его можно только испортив - случайный
    # asset_id ломал бы текстуру, allowed_entities запрещал бы ношение
    # (жалобы юзера). Кастомизируем только «дикие» диковины выше.
    # волчья броня: надевается на ВОЛКА (слот body; asset_id minecraft:wolf
    # - ВАНИЛЬНО-ВЕРНОЕ значение для wolf_armor из Items.class 26.2,
    # НЕ рандом: без него игра искала бы несуществующий ассет wolf_armor;
    # equip_on_interact - использование по волку, как в ванили)
    if item == "minecraft:wolf_armor" and rng.random() < 0.45:
        e = _equippable(rng, "body")
        e["asset_id"] = "minecraft:wolf"
        e["allowed_entities"] = ["minecraft:wolf"]
        e["equip_on_interact"] = True
        comps["minecraft:equippable"] = e
    if kind == "elytra" and rng.random() < 0.40:
        comps["minecraft:glider"] = {}
    if kind in _ARMOR_KINDS and rng.random() < 0.08:  # редкая «второй тотем»
        comps["minecraft:death_protection"] = {
            "death_effects": [_consume_effect(rng)]}
    if kind == "shield" and rng.random() < 0.50:
        comps["minecraft:blocks_attacks"] = _blocks_attacks(rng)
    if rng.random() < 0.06:
        comps["minecraft:damage_resistant"] = {
            "types": rng.choice(["#minecraft:is_fire",
                                 "#minecraft:is_explosion",
                                 "#minecraft:is_projectile"])}
    if _leather(item) and rng.random() < 0.5:
        comps["minecraft:dyed_color"] = int(_hex_color(rng)[1:], 16)
    # волчья броня тоже красится (dyed_color валиден на wolf_armor)
    if item == "minecraft:wolf_armor" and rng.random() < 0.4 \
            and "minecraft:dyed_color" not in comps:
        comps["minecraft:dyed_color"] = int(_hex_color(rng)[1:], 16)
    if item in ARMOR and item != "minecraft:turtle_helmet" \
            and rng.random() < 0.25:
        comps["minecraft:trim"] = {
            "pattern": "minecraft:" + rng.choice(
                ["bolt", "coast", "dune", "eye", "flow", "host", "raiser",
                 "rib", "sentry", "shaper", "silence", "snout", "spire",
                 "tide", "vex", "ward", "wayfinder", "wild"]),
            "material": "minecraft:" + rng.choice(
                ["amethyst", "copper", "diamond", "gold", "iron", "lapis",
                 "netherite", "quartz", "redstone", "resin", "emerald"])}
    # ---------------- еда / зелья ----------------------------------------
    if foodish and rng.random() < 0.40:
        comps["minecraft:food"] = {
            "nutrition": rng.randint(1, 8),
            "saturation": round(rng.uniform(0.1, 1.2), 2),
            "can_always_eat": rng.random() < 0.4}
        # В Minecraft 26.2 / 1.21.2+ еда ОБЯЗАНА иметь consumable, иначе
        # предмет не съедобен и food не функционирует
        c = _consumable(rng)
        c["animation"] = rng.choice(["eat", "drink"])
        c["sound"] = rng.choice(["minecraft:entity.generic.eat", "minecraft:entity.generic.drink"] + SOUNDS)
        comps["minecraft:consumable"] = c
    elif rng.random() < (0.35 if foodish else 0.02):
        comps["minecraft:consumable"] = _consumable(rng)
    # use_remainder: съедобный предмет (vanilla-еда ИЛИ компонент food/
    # consumable) с шансом 40-60% оставляет после себя предмет -
    # варианты: базовая посуда (миска у супов, бутылка у мёда), любой
    # остаток из пула (кость, бумага, свеча, уголёк...) или - с шансом
    # 35% - КАСТОМНЫЙ именной остаток («Косточка от похлёбки», изредка
    # с lore). count ВСЕГДА 1: стек-1 предметам больше нельзя
    # (validateContainedItemSizes), а именной остаток в стае безымянных
    # копий смотрелся бы ошибкой
    if (foodish or "minecraft:food" in comps
            or "minecraft:consumable" in comps) \
            and rng.random() < rng.uniform(0.40, 0.60):
        r2 = rng.random()
        if r2 < 0.35:  # КАСТОМНЫЙ именной остаток
            base = rng.choice(_REMAINDER_POOL)
            rcomps = {"minecraft:item_name": {
                "text": "%s %s" % (_REMAINDER_NOUNS[base],
                                   rng.choice(_REMAINDER_FROM)),
                "color": rng.choice(_NAME_COLORS),
                "italic": False}}
            if rng.random() < 0.4:  # иногда - со своей lore-строчкой
                rcomps["minecraft:lore"] = [
                    {"text": rng.choice(_REMAINDER_LORE),
                     "color": rng.choice(_LORE_COLORS),
                     "italic": True}]
            comps["minecraft:use_remainder"] = {
                "id": base, "count": 1, "components": rcomps}
        elif item in ("minecraft:mushroom_stew",
                      "minecraft:beetroot_soup", "minecraft:rabbit_stew"):
            comps["minecraft:use_remainder"] = {
                "id": "minecraft:bowl", "count": 1}
        elif item == "minecraft:honey_bottle":
            comps["minecraft:use_remainder"] = {
                "id": "minecraft:glass_bottle", "count": 1}
        else:
            comps["minecraft:use_remainder"] = {
                "id": rng.choice(_REMAINDER_POOL), "count": 1}
    # зелья: функцией set_potion (ванильный формат) ИЛИ компонентом
    # potion_contents с кастомными КОМБИНАЦИЯМИ эффектов (amplifier/
    # duration) и своим цветом - не только стандартные зелья
    if item in POTIONS:
        if rng.random() < 0.45:
            funcs.append({"function": "minecraft:set_potion",
                          "id": "minecraft:" + rng.choice(POTIONS_IDS)})
        else:
            comps["minecraft:potion_contents"] = _potion_contents(rng)
        if rng.random() < 0.20:
            comps["minecraft:potion_duration_scale"] = round(
                rng.uniform(0.5, 2.0), 2)
    if item == "minecraft:tipped_arrow":
        # potion_contents: potion + кастомные комбинации эффектов + свой
        # цвет (имена полей доказаны байткодом PotionContents.CODEC:
        # "potion", "custom_color", "custom_effects"; длительности -
        # стрельиные, короткие)
        comps["minecraft:potion_contents"] = _potion_contents(
            rng, long_durations=False)
    if item == "minecraft:ominous_bottle" and rng.random() < 0.5:
        comps["minecraft:ominous_bottle_amplifier"] = rng.randint(0, 4)
    if item == "minecraft:suspicious_stew" and rng.random() < 0.8:
        comps["minecraft:suspicious_stew_effects"] = [
            {"id": "minecraft:" + eid,
             "duration": rng.randint(40, 400)}
            for eid in rng.sample(MOB_EFFECTS, rng.randint(1, 2))]
    # ---------------- стрелы / фейерверки / арбалет ----------------------
    if item == "minecraft:arrow" and rng.random() < 0.30:
        comps["minecraft:intangible_projectile"] = {}
    if item == "minecraft:firework_rocket" and rng.random() < 0.70:
        comps["minecraft:fireworks"] = {
            "flight_duration": rng.randint(1, 3),
            "explosions": [_firework_explosion(rng)
                           for _ in range(rng.randint(1, 3))]}
    if item == "minecraft:firework_star" and rng.random() < 0.70:
        comps["minecraft:firework_explosion"] = _firework_explosion(rng)
    if kind == "crossbow" and rng.random() < 0.40:
        # заряженный арбалет - ГЛУБОКАЯ вложенность: зельевые стрелы
        # (potion_contents с кастомными эффектами прямо в заряде)
        # и фейерверки С НАСТОЯЩИМИ взрывами внутри (без fireworks-компонента
        # ракета в арбалете - холостая)
        projectiles = []
        for _ in range(rng.randint(1, 2)):
            proj = rng.choice(["minecraft:arrow", "minecraft:arrow",
                               "minecraft:spectral_arrow",
                               "minecraft:tipped_arrow",
                               "minecraft:firework_rocket"])
            ps = {"id": proj, "count": rng.randint(1, 3)}
            inner = {}
            if proj in ("minecraft:arrow", "minecraft:tipped_arrow"):
                if proj == "minecraft:tipped_arrow" or rng.random() < 0.45:
                    # стрела с зельем (кастомные комбинации прямо в заряде)
                    inner["minecraft:potion_contents"] = _potion_contents(
                        rng, long_durations=False)
                # зачарованных стрел больше нет: стрелы не входят НИ В
                # ОДИН тег enchantable/* (jar 26.2) - чары на них
                # несовместимы по определению (жалоба о совместимости)
            elif proj == "minecraft:firework_rocket":
                inner["minecraft:fireworks"] = {
                    "flight_duration": rng.randint(1, 3),
                    "explosions": [_firework_explosion(rng)
                                   for _ in range(rng.randint(1, 2))]}
            if inner:
                ps["components"] = inner
            projectiles.append(ps)
        comps["minecraft:charged_projectiles"] = projectiles
    # ---------------- контейнеры: свой лут! ------------------------------
    if item == "minecraft:bundle" or item.endswith("_bundle"):
        if rng.random() < 0.50:  # уже наполненный мешок (с мини-компонентами)
            comps["minecraft:bundle_contents"] = [
                _nested_stack(rng) for _ in range(rng.randint(1, 4))]
    if item == "minecraft:spawner" and rng.random() < 0.55:
        # блок-спавнер с NBT (формат ванильных .nbt-шаблонов, как
        # gen_structures._rand_spawner_nbt): иногда с ОСОБЫМ мобом
        mob = rng.choice(_SPAWNER_MOBS)
        sp = {"id": "minecraft:mob_spawner", "Delay": 0,
              "MinSpawnDelay": 400, "MaxSpawnDelay": 1200,
              "SpawnCount": 2, "MaxNearbyEntities": 4,
              "RequiredPlayerRange": 16, "SpawnRange": 4}
        if rng.random() < 0.5:
            sp["SpawnData"] = {"entity": _mob_nbt(rng, mob, table_ids)}
        else:
            sp["SpawnData"] = {"entity": {"id": "minecraft:" + mob}}
        comps["minecraft:block_entity_data"] = sp
    if item in CONTAINER_ITEMS:
        r = rng.random()
        if r < 0.36:  # наполненные слоты (вложенные предметы - с компонентами)
            if rng.random() < 0.35:
                # ТЕМАТИЧЕСКАЯ заливка: все слоты одной темы - «припасы»,
                # «дары земли», «коллекция пластинок», «арсенал стрел»...
                tpool = _weighted(rng, [
                    (RESOURCES, 14), (FOOD, 12), (VALUABLES, 8),
                    (["minecraft:arrow", "minecraft:spectral_arrow",
                      "minecraft:tipped_arrow",
                      "minecraft:firework_rocket"], 8),
                    (MUSIC_DISCS, 5), (JUNK, 8),
                    (POTTERY_SHERDS + ["minecraft:brick"], 5),
                    (SMITHING_TEMPLATES, 3)])
                max_slot = rng.choice([5, 9, 27])
                slots = rng.sample(range(max_slot),
                                   rng.randint(2, min(6, max_slot)))
                comps["minecraft:container"] = [
                    {"slot": s, "item": _fill_stack(rng, tpool)}
                    for s in slots]
            else:
                max_slot = rng.choice([5, 9, 27])
                slots = rng.sample(range(max_slot),
                                   rng.randint(1, min(3, max_slot)))
                comps["minecraft:container"] = [
                    {"slot": s, "item": _nested_stack(rng)} for s in slots]
        elif r < 0.54 and table_ids:  # ссылка на НАШУ таблицу
            comps["minecraft:container_loot"] = {
                "loot_table": rng.choice(table_ids),
                "seed": rng.randint(1, 2 ** 31 - 1)}
        elif r < 0.62 and item in _LOOT_BED:
            # сундук, который при УСТАНОВКЕ раздаёт лут (LootTable в
            # block_entity_data - RandomizableContainer). id в
            # block_entity_data - это BLOCK ENTITY TYPE, а НЕ блок/предмет
            # (реестр BlockEntityTypeIds 26.2: chest/trapped_chest/
            # shulker_box(один на все цвета)/barrel/...; медным сундукам
            # отдельного BE-типа НЕТ - они обычный chest; поймано на
            # реальном сервере: «Unknown ... minecraft:copper_chest»)
            _BE_TYPE = {"minecraft:chest": "minecraft:chest",
                        "minecraft:trapped_chest": "minecraft:trapped_chest",
                        "minecraft:barrel": "minecraft:barrel",
                        "minecraft:dispenser": "minecraft:dispenser",
                        "minecraft:dropper": "minecraft:dropper",
                        "minecraft:hopper": "minecraft:hopper",
                        "minecraft:decorated_pot": "minecraft:decorated_pot"}
            be_id = _BE_TYPE.get(item, "minecraft:chest")  # медные -> chest
            if item.endswith("_shulker_box"):
                be_id = "minecraft:shulker_box"  # один BE-тип на все цвета
            lt = (rng.choice(table_ids) if table_ids and rng.random() < 0.5
                  else rng.choice(_VANILLA_CHEST_TABLES))
            comps["minecraft:block_entity_data"] = {
                "id": be_id, "LootTable": lt}
        if rng.random() < 0.15:  # замок: голый ItemPredicate
            comps["minecraft:lock"] = {
                "items": rng.choice(["#minecraft:planks",
                                     "minecraft:diamond",
                                     "minecraft:gold_ingot"])}
    # ---------------- книги / карты / пластинки --------------------------
    if item == "minecraft:writable_book" and rng.random() < 0.8:
        comps["minecraft:writable_book_content"] = {
            "pages": _book_pages(rng, rng.randint(2, 5), False)}
    if item == "minecraft:written_book" and rng.random() < 0.8:
        comps["minecraft:written_book_content"] = {
            "title": {"raw": rng.choice(_BOOK_TITLES),
                      "filtered": rng.choice(["Дневник", "Заметки",
                                              "Записки"])},
            "author": rng.choice(_RU_AUTHORS),
            "generation": rng.randint(0, 3),
            "resolved": rng.random() < 0.5,
            "pages": _book_pages(rng, rng.randint(2, 5), True)}
    if item == "minecraft:painting" and rng.random() < 0.60:
        # картина конкретного реестрового варианта (51 штука в jar)
        comps["minecraft:painting/variant"] = rng.choice(PAINTING_VARIANTS)
    if item == "minecraft:filled_map":
        if rng.random() < 0.50:
            comps["minecraft:map_color"] = int(_hex_color(rng)[1:], 16)
        if rng.random() < 0.50:
            comps["minecraft:map_id"] = rng.randint(1, 1000)
        if rng.random() < 0.40:
            comps["minecraft:map_decorations"] = {
                "метка_%d" % i: {
                    "type": "minecraft:" + rng.choice(MAP_DECORATION_TYPES),
                    "x": round(rng.uniform(-50.0, 50.0), 1),
                    "z": round(rng.uniform(-50.0, 50.0), 1),
                    "rotation": round(rng.uniform(0.0, 360.0), 1)}
                for i in range(rng.randint(1, 3))}
    if item in MUSIC_DISCS and rng.random() < 0.30:
        # пластинка «не своей» песни - просто строка id
        comps["minecraft:jukebox_playable"] = \
            "minecraft:" + rng.choice(JUKEBOX_SONGS)
    # ---------------- предметы-сущности (path-id компоненты) -------------
    if item == "minecraft:player_head" and rng.random() < 0.50:
        comps["minecraft:profile"] = {"name": rng.choice(_PROFILE_NAMES)}
    if item in ("minecraft:beehive", "minecraft:bee_nest") \
            and rng.random() < 0.50:
        # пчёлы с настоящим NBT: нектар, изредка имя («Улей с Пчёлами» -
        # имя носителя) и злость (Anger - тики гнева, как у ванильных пчёл)
        bees = []
        for _ in range(rng.randint(1, 3)):
            ed = {"id": "minecraft:bee",
                  "HasNectar": rng.random() < 0.5}
            if rng.random() < 0.20:
                ed["CustomName"] = _mob_title(rng, "bee")
            if rng.random() < 0.15:
                ed["Anger"] = rng.choice([60, 120, 300])
            bees.append({"entity_data": ed,
                         "ticks_in_hive": rng.randint(0, 1200),
                         "min_ticks_in_hive": rng.randint(60, 600)})
        comps["minecraft:bees"] = bees
    if item in BLOCK_STATE_PROPS and rng.random() < 0.60:
        comps["minecraft:block_state"] = {
            prop: rng.choice(vals)
            for prop, vals in BLOCK_STATE_PROPS[item].items()}
    if item == "minecraft:note_block" and rng.random() < 0.60:
        comps["minecraft:note_block_sound"] = rng.choice(SOUNDS)
    if item == "minecraft:decorated_pot" and rng.random() < 0.60:
        # ПЛОСКИЙ массив из 4 id (черепки/кирпич), порядок: back..front
        sherds = [rng.choice(POTTERY_SHERDS + ["minecraft:brick"])
                  for _ in range(4)]
        comps["minecraft:pot_decorations"] = sherds
    if item.endswith("_banner") and item != "minecraft:banner_pattern":
        if rng.random() < 0.50:
            comps["minecraft:banner_patterns"] = [
                {"pattern": "minecraft:" + rng.choice(BANNER_PATTERNS),
                 "color": rng.choice(DYE_COLORS)}
                for _ in range(rng.randint(1, 3))]
        if rng.random() < 0.30:
            comps["minecraft:base_color"] = rng.choice(DYE_COLORS)
    if item.endswith("_dye") and rng.random() < 0.30:
        comps["minecraft:dye"] = rng.choice(DYE_COLORS)
    if item == "minecraft:compass" and rng.random() < 0.15:
        comps["minecraft:lodestone_tracker"] = {
            "tracked": True,
            "target": {"dimension": rng.choice(
                           ["minecraft:overworld", "minecraft:the_nether",
                            "minecraft:the_end"]),
                       "pos": [rng.randint(-1000, 1000),
                               rng.randint(-60, 200),
                               rng.randint(-1000, 1000)]}}
    # рыбные вёдра: bucket_entity_data {entity: {id}} - ведро своего моба,
    # иногда ИМЕННОГО (CustomName переносится при выпуске)
    if item in FISH_BUCKETS and rng.random() < 0.50:
        ent = {"id": FISH_BUCKETS[item]}
        mob = item[len("minecraft:"):-len("_bucket")]
        if rng.random() < 0.30 and mob in _MOB_RU:
            ent["CustomName"] = _mob_title(rng, mob)
        comps["minecraft:bucket_entity_data"] = {"entity": ent}
    if item == "minecraft:tropical_fish_bucket" and rng.random() < 0.50:
        comps["minecraft:tropical_fish/base_color"] = rng.choice(DYE_COLORS)
        comps["minecraft:tropical_fish/pattern"] = rng.choice(
            TROPICAL_FISH_PATTERNS)
        comps["minecraft:tropical_fish/pattern_color"] = rng.choice(DYE_COLORS)
    if item == "minecraft:sulfur_cube_bucket" and rng.random() < 0.60:
        comps["minecraft:sulfur_cube_content"] = {
            "id": "minecraft:sulfur", "count": rng.randint(1, 4)}
    # вёдра со своими вариантами (enum-кодеки, plain lowercase)
    if item == "minecraft:axolotl_bucket" and rng.random() < 0.50:
        comps["minecraft:axolotl/variant"] = rng.choice(AXOLOTL_VARIANTS)
    if item == "minecraft:salmon_bucket" and rng.random() < 0.50:
        comps["minecraft:salmon/size"] = rng.choice(SALMON_SIZES)
    # спавн-яйца с вариантами сущностей (path-id компоненты): на яйцо
    # берётся случайное подмножество подходящих (1..все)
    if item in _SPAWN_EGG_VARIANTS and rng.random() < 0.75:
        pairs = _SPAWN_EGG_VARIANTS[item]
        for ckey, gen in rng.sample(pairs, rng.randint(1, len(pairs))):
            comps[ckey] = gen(rng)
    # спавн-яйцо с ОСОБЫМ мобом - entity_data с полным NBT (зеркало
    # gen_structures._rand_mob_nbt): кастомное имя с цветом, снаряжение
    # с зачарованиями, атрибуты, эффекты, DeathLootTable на НАШИ
    # таблицы, Glowing/... - имя предмета это раскрывает
    # («Яйцо Древнего Скелета»)
    if item.endswith("_spawn_egg") and rng.random() < 0.30:
        mob = item[len("minecraft:"):-len("_spawn_egg")]
        comps["minecraft:entity_data"] = _mob_nbt(rng, mob, table_ids)
    if item == "minecraft:goat_horn":
        # инструмент рога: ФУНКЦИЕЙ set_instrument (тег опций, ванильный
        # формат) ИЛИ КОМПОНЕНТОМ instrument (конкретный id - имя-раскрытие
        # «Рог Тоски» знает, что внутри)
        r = rng.random()
        if r < 0.45:
            funcs.append({"function": "minecraft:set_instrument",
                          "options": rng.choice(
                              ["#minecraft:goat_horns",
                               "#minecraft:regular_goat_horns",
                               "#minecraft:screaming_goat_horns"])})
        elif r < 0.85:
            comps["minecraft:instrument"] = \
                "minecraft:" + rng.choice(INSTRUMENTS)
    # ---------------- имя - В КОНЦЕ, по факту содержимого ---------------
    # item_name - «истинное имя» (базовое, без курсива): custom_name
    # перекрывает его - «у предмета два имени». Только при других
    # компонентах (инвариант «только имя» - чистая косметика
    # не считается)
    if comps and rng.random() < 0.06:
        comps["minecraft:item_name"] = {"text": _true_name(rng, item),
                                        "italic": False}
    # custom_name - РАСКРЫВАЮЩИЙ: строится из реальных компонентов;
    # «сильные» компоненты сами просят имя даже в дешёвых таблицах
    # (trim сюда НЕ входит: орнамент виден в тултипе и так - жалобa
    # «trim и так видно, не надо подсказки»)
    strong = ("minecraft:entity_data" in comps
              or "minecraft:attribute_modifiers" in comps
              or "minecraft:enchantments" in comps
              or "minecraft:potion_contents" in comps
              or "minecraft:stored_enchantments" in comps
              or "minecraft:instrument" in comps
              or "minecraft:charged_projectiles" in comps
              or "minecraft:bees" in comps
              or "minecraft:written_book_content" in comps
              or any(isinstance(f, dict) and f.get("function") in (
                  "minecraft:set_potion", "minecraft:set_enchantments")
                  for f in funcs))
    name_bonus = 0.75 if "minecraft:entity_data" in comps else 0.5
    # имя ставим ТОЛЬКО предмету, которому ЕСТЬ что раскрывать: непустые
    # компоненты, спавн-яйцо (моб читается из самого предмета) или
    # зелье/чара/рог функцией (set_potion/set_enchantments/
    # set_instrument). Иначе предмет - чистый ванильный, и полностью
    # рандомное имя ему не нужно (жалоба: «имена должны раскрывать
    # качества, а не быть полностью рандомными»)
    can_reveal = bool(comps) or item.endswith("_spawn_egg") or any(
        isinstance(f, dict) and f.get("function") in (
            "minecraft:set_potion", "minecraft:set_enchantments",
            "minecraft:set_instrument") for f in funcs)
    if can_reveal and (want_name or (strong and rng.random() < name_bonus)):
        comps["minecraft:item_name"] = _reveal_name(rng, item, comps, funcs)
        # lore - ИЗ ФАКТИЧЕСКОГО содержимого предмета (зелья - эффект,
        # атрибуты - «тяжесть даёт +X к защите», чары, еда, планер
        # «планирует, как семя клёна», инструмент...): 1-3 строки +
        # редкая флейвор-строка; полностью рандомного лора больше нет
        clines = _component_lore(rng, item, comps, funcs)
        if clines and rng.random() < 0.65:
            if rng.random() < 0.22:  # редкая флейвор-строка - как приправа
                clines.append({"text": rng.choice(_LORE_LINES),
                               "color": rng.choice(
                                   ["gray", "dark_gray", "blue",
                                    "dark_aqua"]),
                               "italic": True})
            comps["minecraft:lore"] = clines
    # ФИКС «предмет только с визуалом»: если функциональных особенностей
    # не осталось (только косметика) - добавить работающую фичу:
    # приоритетно ПАССИВНОЕ зачарование измерения (действует при
    # ношении/удержании), фолбэк - функциональный компонент
    _fix_visual_only(rng, item, comps, funcs, tag_prefix, equip_slot)
    # lore-подсказки КАСТОМНЫХ зачарований измерения: «Имя зачарования -
    # описание действия» (ванильные не описываем - игроки их знают).
    # Добавляется ПОСЛЕ фикса - подсказка покрывает и «спасённый» предмет
    hints = _ench_hint_lines(rng, comps, funcs)
    if hints:
        lore = list(comps.get("minecraft:lore") or [])
        lore.extend(hints)
        comps["minecraft:lore"] = lore
    if "minecraft:food" in comps and "minecraft:consumable" not in comps:
        c = _consumable(rng)
        c["animation"] = rng.choice(["eat", "drink"])
        comps["minecraft:consumable"] = c
    return comps, funcs


# ---------------------------------------------------------------------------
# Фабрика таблиц
# ---------------------------------------------------------------------------

_CHARS = [
    ("weapons", 16), ("treasure", 18), ("junk", 14),
    ("food", 12), ("mixed", 28), ("mob", 12),
]

# самотест: структура пулов/роллов по тирам таблиц (mob/chest/treasure/
# None) - заполняется в _LootGen.table, на вывод НЕ влияет
_TIER_STATS = {}

_TABLE_TYPES = [
    ("minecraft:chest", 46), ("minecraft:entity", 22),
    ("minecraft:gift", 10), ("minecraft:equipment", 10),
    ("minecraft:fishing", 6), ("minecraft:archaeology", 4),
    ("minecraft:barter", 2),
]

# Контексты лут-таблиц (LootContextParamSets, 26.2, сверено байткодом
# javap: lambda$static$9 = entity и т.д.): биты потребностей -
# killed_by_player нужен LAST_DAMAGE_PLAYER (только entity),
# apply_bonus/table_bonus/match_tool - TOOL (fishing/archaeology/vault),
# entity_properties(this) - THIS_ENTITY и ORIGIN,
# random_chance_with_enchanted_bonus / enchanted_count_increase -
# ATTACKING_ENTITY (опциональный параметр ТОЛЬКО entity-контекста:
# ванильные entities/blaze.json и entities/drowned.json так и делают).
# Вложенные таблицы (loot_table-записи) валидируются в контексте
# РОДИТЕЛЯ, поэтому эффективный контекст считается по всей цепочке.
_NEED_LDP, _NEED_TOOL, _NEED_THIS, _NEED_ORIGIN, _NEED_ATK = 1, 2, 4, 8, 16
# Точные составы (javap -v LootContextParamSets 26.2, через BootstrapMethods):
#   entity       THIS,ORIGIN,DAMAGE_SOURCE + opt ATTACKING,DIRECT_ATTACKING,LAST_DAMAGE_PLAYER
#   fishing      ORIGIN,TOOL,THIS          | vault      ORIGIN,TOOL,THIS
#   archaeology  ORIGIN,TOOL,THIS          | equipment  ORIGIN,THIS (БЕЗ tool!)
#   chest/gift   ORIGIN,THIS               | barter     THIS
_TYPE_COVERAGE = {
    "minecraft:entity": 13 | _NEED_ATK, "minecraft:fishing": 14,
    "minecraft:equipment": 12, "minecraft:vault": 14,
    "minecraft:chest": 12, "minecraft:gift": 12,
    "minecraft:archaeology": 14, "minecraft:barter": 4,
}
_TOOL_TYPES = ("minecraft:fishing", "minecraft:vault",
               "minecraft:archaeology")
_ATK_TYPES = ("minecraft:entity",)   # только entity даёт ATTACKING_ENTITY
_THIS_TYPES = ("minecraft:entity", "minecraft:fishing", "minecraft:equipment",
               "minecraft:vault", "minecraft:chest", "minecraft:gift",
               "minecraft:archaeology")
_CTX_FULL = 15 | _NEED_ATK  # LDP|TOOL|THIS|ORIGIN|ATK - «неограниченный»


def _vanilla_mask(vid):
    """Маска потребностей контекста ванильной таблицы (её тип - из jar 26.2:
    chests/* -> chest, gameplay/fishing* -> fishing, piglin_bartering -> barter,
    подарки -> gift). Вложенная таблица валидируется в контексте РОДИТЕЛЯ,
    поэтому ссылка безопасна только если маска ? эффективному контексту."""
    if vid.startswith("minecraft:gameplay/fishing"):
        return _NEED_TOOL | _NEED_THIS | _NEED_ORIGIN
    if vid == "minecraft:gameplay/piglin_bartering":
        return _NEED_THIS
    if vid.startswith("minecraft:chests/") or vid in (
            "minecraft:gameplay/sniffer_digging",
            "minecraft:gameplay/cat_morning_gift",
            "minecraft:gameplay/hero_of_the_village/weaponsmith_gift",
            "minecraft:gameplay/hero_of_the_village/farmer_gift",
            "minecraft:gameplay/hero_of_the_village/librarian_gift"):
        return _NEED_THIS | _NEED_ORIGIN
    return _CTX_FULL  # неизвестная таблица - считаем самой требовательной

_NON_STACKABLE = set(ARMOR + WEAPONS + TOOLS + POTIONS + ENCH_BOOKS +
                     SHIELDS + ELYTRA + MISC)

# Страховка от фантомов: тематические списки захардкожены и могут отстать
# от реестра (пример: голого minecraft:harness в 26.2 НЕТ - только цветные
# *_harness; real-server: «Unknown registry key in minecraft:item» ломает
# таблицу целиком). Прогоняем их через проверенный _ALL_ITEM_NAMES.
_KNOWN_ITEMS = frozenset("minecraft:" + n for n in _ALL_ITEM_NAMES
                         if n not in _PHANTOM_ITEMS)
for _lname in ("WEAPONS", "ARMOR", "TOOLS", "BOWS", "CROSSBOWS",
               "TRIDENTS", "MACES", "SHIELDS", "ELYTRA", "HORSE_ARMORS",
               "FOOD", "RAW_FOOD", "BAD_FOOD", "JUNK", "RESOURCES",
               "VALUABLES", "MUSIC_DISCS", "POTIONS", "BOOKS",
               "ENCH_BOOKS", "SMITHING_TEMPLATES", "POTTERY_SHERDS",
               "MISC", "ODDITIES"):
    _lst = globals()[_lname]
    _kept = [x for x in _lst if x in _KNOWN_ITEMS]
    if len(_kept) != len(_lst):
        globals()[_lname] = _kept
        _NON_STACKABLE.difference_update(_lst)  # на случай выпавших имён


# ---------------------------------------------------------------------------
# ТЕМАТИЧЕСКИЕ ПУЛЫ (жалоба: «генератор скудный»): каждая таблица
# сэмплирует 2-4 ТЕМЫ с разными весами, каждый пул целиком одной
# темы - наборы записей согласованы по смыслу. Темы опираются на те
# же курируемые списки предметов (страховка от фантомов выше).
# ---------------------------------------------------------------------------

_THEMES = {
    "armory": [((WEAPONS + SHIELDS, "weapon"), 42),
               ((ARMOR, "armor"), 34),
               ((ENCH_BOOKS, "book"), 12),
               ((SMITHING_TEMPLATES, "template"), 6),
               ((HORSE_ARMORS, "valuable"), 6)],
    "provisions": [((FOOD, "food"), 46), ((RAW_FOOD, "raw_food"), 16),
                   ((POTIONS, "potion"), 14), ((JUNK, "junk"), 24)],
    "treasure": [((VALUABLES, "valuable"), 44),
                 ((RESOURCES, "resource"), 20),
                 ((ENCH_BOOKS, "book"), 12),
                 ((MUSIC_DISCS, "disc"), 10),
                 ((SMITHING_TEMPLATES, "template"), 8),
                 ((WEAPONS + ARMOR, "gear"), 6)],
    "tools": [((TOOLS, "tool"), 34), ((RESOURCES, "resource"), 32),
              ((["minecraft:arrow", "minecraft:spectral_arrow",
                 "minecraft:tipped_arrow", "minecraft:firework_rocket"],
                "resource"), 16),
              ((JUNK, "junk"), 18)],
    "alchemy": [((POTIONS, "potion"), 34),
                ((["minecraft:tipped_arrow", "minecraft:dragon_breath",
                   "minecraft:fermented_spider_eye", "minecraft:magma_cream",
                   "minecraft:blaze_powder", "minecraft:gunpowder",
                   "minecraft:slime_ball", "minecraft:glowstone_dust"],
                  "resource"), 22),
                ((RESOURCES, "resource"), 22), ((FOOD, "food"), 10),
                ((JUNK, "junk"), 12)],
    "writings": [((ENCH_BOOKS + BOOKS, "book"), 30),
                 ((MUSIC_DISCS, "disc"), 24),
                 ((POTTERY_SHERDS, "junk"), 24),
                 ((["minecraft:name_tag", "minecraft:compass",
                    "minecraft:recovery_compass", "minecraft:clock",
                    "minecraft:spyglass", "minecraft:map",
                    "minecraft:filled_map", "minecraft:goat_horn"],
                   "misc"), 22)],
    "junk": [((JUNK, "junk"), 58), ((BAD_FOOD, "bad_food"), 14),
             ((RAW_FOOD, "raw_food"), 10), ((ODDITIES, "oddity"), 10),
             ((RESOURCES, "resource"), 8)],
    "relics": [((VALUABLES, "valuable"), 30), ((ODDITIES, "oddity"), 26),
               ((SPAWN_EGGS, "egg"), 18), ((MISC, "misc"), 18),
               ((MUSIC_DISCS, "disc"), 8)],
}

# тема -> характер записей (вероятность имён/компонентов в _item_entry)
_THEME_CHAR = {"armory": "weapons", "provisions": "food",
               "treasure": "treasure", "tools": "mixed",
               "alchemy": "mixed", "writings": "mixed",
               "junk": "junk", "relics": "treasure"}

# характер таблицы -> распределение тем (таблица сэмплирует 2-4)
_THEME_MIX = {
    "weapons": [("armory", 46), ("tools", 14), ("treasure", 14),
                ("relics", 10), ("junk", 8), ("writings", 8)],
    "treasure": [("treasure", 34), ("relics", 20), ("armory", 14),
                 ("writings", 12), ("provisions", 10), ("tools", 10)],
    "junk": [("junk", 44), ("provisions", 18), ("tools", 14),
             ("relics", 12), ("writings", 12)],
    "food": [("provisions", 50), ("junk", 18), ("alchemy", 16),
             ("treasure", 16)],
    "mob": [("junk", 38), ("provisions", 30), ("tools", 16),
            ("relics", 16)],
    "mixed": [("armory", 16), ("treasure", 16), ("tools", 14),
              ("provisions", 14), ("junk", 12), ("alchemy", 10),
              ("writings", 10), ("relics", 8)],
}


def _themes_for(rng, char):
    """2-4 темы таблицы, каждая со своим весом (жалоба «генератор
    скудный»: пул выбирает тему по весу - таблица получается
    многогранной, но согласованной)."""
    dist = _THEME_MIX.get(char, _THEME_MIX["mixed"])
    k = rng.randint(2, min(4, len(dist)))
    picked = rng.sample(dist, k)
    # первая тема тяжелее остальных (пересев весов)
    return [(t, (w * 3 if i == 0 else w)) for i, (t, w) in enumerate(picked)]


# «тяжёлые» компоненты, запрещённые на моб-дропах (лаг после убийства:
# вложенные контейнеры с лутом, NBT-мобов, заряженные арбалеты...)
_MOB_HEAVY_COMPS = frozenset([
    "minecraft:container", "minecraft:container_loot",
    "minecraft:block_entity_data", "minecraft:charged_projectiles",
    "minecraft:bundle_contents", "minecraft:bees",
    "minecraft:written_book_content", "minecraft:writable_book_content",
    "minecraft:fireworks", "minecraft:firework_explosion",
    "minecraft:entity_data", "minecraft:profile",
    "minecraft:map_decorations", "minecraft:lodestone_tracker",
    "minecraft:jukebox_playable", "minecraft:painting/variant",
    "minecraft:pot_decorations", "minecraft:banner_patterns"])


# приоритет сохранения функциональных компонентов моб-дропа при
# обрезке до двух: зачарования (на них ссылаются lore-подсказки),
# зелья, экипировка (без неё armor-слоты attribute_modifiers - мёртвые),
# планер, еда...; attribute_modifiers - последний
_LIGHT_PRIORITY = (
    "minecraft:enchantments", "minecraft:stored_enchantments",
    "minecraft:potion_contents", "minecraft:equippable",
    "minecraft:glider", "minecraft:consumable",
    "minecraft:use_remainder", "minecraft:food",
    "minecraft:repairable", "minecraft:enchantable",
    "minecraft:max_damage", "minecraft:unbreakable",
    "minecraft:repair_cost", "minecraft:weapon",
    "minecraft:piercing_weapon", "minecraft:kinetic_weapon",
    "minecraft:attack_range", "minecraft:minimum_attack_charge",
    "minecraft:swing_animation", "minecraft:tool",
    "minecraft:damage_resistant", "minecraft:death_protection",
    "minecraft:use_cooldown", "minecraft:use_effects",
    "minecraft:attribute_modifiers")


def _lighten_components(comps):
    """Компоненты моб-дропа (жалоба: «игра ВИСНЕТ после убийства моба»):
    без тяжёлых контейнеров/NBT-мобов/зарядов и не более ДВУХ
    функциональных компонентов на предмет (косметика/имя/lore -
    «идентичность», не в счёт; зачарования приоритетны - на них
    ссылаются lore-подсказки). Приоритет обрезки - _LIGHT_PRIORITY
    (детерминированный): attribute_modifiers без equippable не
    остаётся (armor-слоты стали бы мёртвыми - инвариант слотов)."""
    out = {k: v for k, v in comps.items() if k not in _MOB_HEAVY_COMPS}
    identity = ("minecraft:custom_name", "minecraft:item_name",
                "minecraft:lore")
    func = [k for k in out
            if k not in identity and k not in _COSMETIC_KEYS]
    if len(func) > 2:
        order = {k: i for i, k in enumerate(_LIGHT_PRIORITY)}
        func.sort(key=lambda k: order.get(k, len(_LIGHT_PRIORITY)))
        keep = set(func[:2])
        out = {k: v for k, v in out.items()
               if k in keep or k in identity or k in _COSMETIC_KEYS}
    return out


class _LootGen(object):
    """Внутренняя фабрика лут-таблиц одного измерения."""

    def __init__(self, rng, ns, name, ids):
        self.rng = rng
        self.ns = ns
        self.name = name
        self.ids = ids  # все id по порядку создания (для ссылок «вперёд»)
        self.ttype = None  # тип строящейся таблицы (контекст лут-условий)
        # ПЛАН вложенных loot_table-ссылок (жалоба: лаги/пустоты от
        # передоза): <= CAP_NESTED_PER_TABLE ссылок на таблицу, глубина
        # РОВНО 1 (цель сама ссылок не имеет), только «вперёд» -
        # рекурсия физически невозможна, а цепочки не глубже 1 уровня
        self.nested_plan = {}
        _targeted = set()
        for i in range(len(ids)):
            if i in _targeted:
                continue  # цель не ссылается сама (глубина <= 1)
            if rng.random() < 0.30:
                forward = list(range(i + 1, len(ids)))
                if not forward:
                    continue
                k = 1 if rng.random() < 0.65 else 2
                tgts = rng.sample(forward, min(k, len(forward)))
                self.nested_plan[i] = tgts
                _targeted.update(tgts)
        self._refs_left = 0  # остаток ссылок текущей таблицы

    # ---------- выборки предметов по характеру ----------

    def _pick_item(self, char):
        """(пул предметов, класс записи) под характер таблицы."""
        rng = self.rng
        if char == "weapons":
            return _weighted(rng, [
                ((WEAPONS + SHIELDS, "weapon"), 45), ((ARMOR, "armor"), 25),
                ((TOOLS, "tool"), 12), ((JUNK, "junk"), 10),
                ((ENCH_BOOKS, "book"), 8)])
        if char == "treasure":
            return _weighted(rng, [
                ((VALUABLES, "valuable"), 42), ((RESOURCES, "resource"), 18),
                ((ENCH_BOOKS, "book"), 12), ((MUSIC_DISCS, "disc"), 8),
                ((SMITHING_TEMPLATES, "template"), 8),
                ((FOOD, "food"), 6), ((WEAPONS + ARMOR, "gear"), 6),
                ((MISC, "misc"), 5), ((SPAWN_EGGS, "egg"), 3)])
        if char == "junk":
            return _weighted(rng, [
                ((JUNK, "junk"), 62), ((BAD_FOOD, "bad_food"), 12),
                ((RAW_FOOD, "raw_food"), 8), ((RESOURCES, "resource"), 10),
                ((FOOD, "food"), 5), ((VALUABLES, "valuable"), 3),
                ((ODDITIES, "oddity"), 3)])
        if char == "food":
            return _weighted(rng, [
                ((FOOD, "food"), 55), ((RAW_FOOD, "raw_food"), 12),
                ((POTIONS, "potion"), 10), ((JUNK, "junk"), 15),
                ((BAD_FOOD, "bad_food"), 8)])
        if char == "mob":
            return _weighted(rng, [
                ((BAD_FOOD, "bad_food"), 30), ((RAW_FOOD, "raw_food"), 22),
                ((JUNK, "junk"), 25), ((RESOURCES, "resource"), 15),
                ((FOOD, "food"), 5), ((SPAWN_EGGS, "egg"), 4)])
        # mixed
        return _weighted(rng, [
            ((WEAPONS + ARMOR + TOOLS + SHIELDS, "gear"), 25),
            ((VALUABLES, "valuable"), 18), ((RESOURCES, "resource"), 18),
            ((FOOD + RAW_FOOD, "food"), 15), ((JUNK, "junk"), 14),
            ((ENCH_BOOKS, "book"), 5), ((MUSIC_DISCS, "disc"), 3),
            ((POTIONS, "potion"), 2), ((MISC, "misc"), 4),
            ((SPAWN_EGGS, "egg"), 3), ((ODDITIES, "oddity"), 3)])

    # ---------- записи ----------

    def _item_entry(self, char, theme=None, light=False):
        """Запись-предмет (с функциями/компонентами).
        theme - тематический пул предметов (тема пула таблицы);
        light - «лёгкий» моб-дроп: <=2 функциональных компонентов,
        без контейнеров/NBT-мобов, скромные стопки (жалоба: «игра
        ВИСНЕТ после убийства моба»)."""
        rng = self.rng
        # «дикий тир» в духе BLOCK_TIERS: курируемые пулы - основной вес,
        # полный каталог (1523 предмета реестра 26.2) - редкий шанс ~5%;
        # технические предметы (командные блоки, air...) отфильтрованы
        if rng.random() < 0.05:
            item = rng.choice(ALL_ITEMS)
            pclass = "wild"
        elif theme and theme in _THEMES:
            pool, pclass = _weighted(rng, _THEMES[theme])
            item = rng.choice(pool)
        else:
            pool, pclass = self._pick_item(char)
            item = rng.choice(pool)
        if item in ULTRA_RARE_VALUABLES:
            if rng.random() < 0.75:
                item = rng.choice(RESOURCES)
                pclass = "resource"
                entry = {"type": "minecraft:item", "name": item,
                         "weight": rng.randint(1, 20)}
            else:
                entry = {"type": "minecraft:item", "name": item,
                         "weight": 1}
        elif item in RARE_VALUABLES:
            entry = {"type": "minecraft:item", "name": item,
                     "weight": rng.randint(1, 3)}
        else:
            entry = {"type": "minecraft:item", "name": item,
                     "weight": rng.randint(1, 20)}
        funcs = []
        # вероятность «крутого» предмета зависит от характера таблицы
        echar = _THEME_CHAR.get(theme, char)
        name_p = {"weapons": 0.7, "treasure": 0.45, "mixed": 0.35,
                  "food": 0.08, "junk": 0.03, "mob": 0.15}.get(echar, 0.2)
        want_name = pclass in ("weapon", "armor", "tool", "gear", "book",
                               "valuable", "disc", "wild", "misc", "egg",
                               "oddity") and rng.random() < name_p
        tag_prefix = "%s_%d" % (self.name, rng.randint(0, 10 ** 6))
        comps, cfuncs = _item_components(self.rng, item, echar, tag_prefix,
                                         want_name, self.ns, self.ids)
        if light:
            comps = _lighten_components(comps)
            # лёгкая чистка не должна оставлять «только визуал» (все
            # функциональные компоненты могли быть тяжёлыми): прогоняем
            # фикс ещё раз ПОСЛЕ облегчения - внутри сам проверяет критерий
            # (косметика без функций) и добавляет работающую фичу
            _fix_visual_only(rng, item, comps, cfuncs, tag_prefix, None)
            hints = _ench_hint_lines(rng, comps, cfuncs)
            if hints:
                lore = list(comps.get("minecraft:lore") or [])
                lore.extend(hints)
                comps["minecraft:lore"] = lore
        if comps:
            funcs.append({"function": "minecraft:set_components",
                          "components": comps})
        funcs.extend(cfuncs)
        # количество: стекающимся предметам - set_count с РАЗНЫМИ кривыми
        # (uniform/binomial/константа), поверх изредка limit_count
        # (ванильный приём грибных блоков); мобам - скромные стопки
        stackable = item not in _NON_STACKABLE and item not in _STACK1
        is_mat = _is_material(item) or pclass == "resource"
        if item in ULTRA_RARE_VALUABLES:
            funcs.append({"function": "minecraft:set_count",
                          "count": {"type": "minecraft:constant", "value": 1.0}})
        elif item in RARE_VALUABLES:
            c = 1.0 if rng.random() < 0.80 else 2.0
            funcs.append({"function": "minecraft:set_count",
                          "count": {"type": "minecraft:constant", "value": c}})
        elif stackable:
            if is_mat:
                c_min = rng.randint(4, 8) if not light else rng.randint(2, 4)
                c_max = rng.randint(16, 48) if not light else rng.randint(8, 16)
                funcs.append({"function": "minecraft:set_count",
                              "count": _num_provider(rng, c_min, c_max)})
                if rng.random() < 0.25:
                    funcs.append({"function": "minecraft:limit_count",
                                  "limit": {"min": float(c_min),
                                            "max": float(c_max)}})
            elif rng.random() < (0.30 if light else 0.55):
                hi = {"valuable": 5, "junk": 24}.get(pclass, 8)
                if light:
                    hi = min(hi, 4)
                hi += rng.randint(0, max(1, hi // 2))
                funcs.append({"function": "minecraft:set_count",
                              "count": _num_provider(rng, 1, max(2, hi))})
                if rng.random() < 0.25:
                    funcs.append({"function": "minecraft:limit_count",
                                  "limit": {"min": 1.0,
                                            "max": float(max(2, hi))}})
        if (pclass == "resource" and self.ttype in _TOOL_TYPES
                    and rng.random() < 0.3 and not light):
                formula = rng.choice(["minecraft:ore_drops",
                                      "minecraft:uniform_bonus_count",
                                      "minecraft:binomial_with_bonus_count"])
                f = {"function": "minecraft:apply_bonus",
                     "enchantment": "minecraft:fortune", "formula": formula}
                if formula == "minecraft:uniform_bonus_count":
                    f["parameters"] = {"bonusMultiplier": rng.randint(1, 3)}
                elif formula == "minecraft:binomial_with_bonus_count":
                    f["parameters"] = {
                        "probability": round(rng.uniform(0.2, 0.9), 3),
                        "extra": rng.randint(2, 5)}
                funcs.append(f)
        # «добычливость» с Добычей (Looting): enchanted_count_increase
        # читает ATTACKING_ENTITY - параметр ТОЛЬКО entity-контекста
        # (как ванильные entities/blaze.json; чистка _strip_cond снимает
        # функцию, если таблица с дроном моба вкладывается в слабый контекст)
        if (self.ttype == "minecraft:entity" and stackable
                and rng.random() < 0.20):
            funcs.append({"function": "minecraft:enchanted_count_increase",
                          "enchantment": "minecraft:looting",
                          "count": {"type": "minecraft:uniform",
                                    "min": 0.0, "max": 1.0}})
        gear = item in WEAPONS or item in ARMOR or item in TOOLS
        # повреждённое снаряжение (как в бастионах). unbreakable исключаем:
        # isDamageableItem() = MAX_DAMAGE && !UNBREAKABLE, иначе на каждый
        # спавн WARN «Couldn't set damage of loot item»
        if gear and "minecraft:unbreakable" not in comps and rng.random() < 0.25:
            funcs.append({"function": "minecraft:set_damage",
                          "damage": {"type": "minecraft:uniform",
                                     "min": round(rng.uniform(0.05, 0.6), 2),
                                     "max": round(rng.uniform(0.6, 1.0), 2)}})
        # случайные зачарования поверх (как в ванильных сундуках);
        # КАСТОМНЫЕ - только совместимые с предметом (supported_items;
        # enchant_randomly без опций валиден сам - движок фильтрует)
        if gear and rng.random() < 0.15:
            copts = [e for e in CUSTOM_ENCHS if _custom_ench_ok(e, item)]
            if rng.random() < 0.5:
                f = {"function": "minecraft:enchant_with_levels",
                     "levels": float(rng.randint(5, 39))}
                if copts and rng.random() < 0.4:
                    # только наши зачарования измерения - уровни разыграет
                    # движок (валах: в #on_random_loot попадут лишь совместимые)
                    f["options"] = list(copts)
                elif rng.random() < 0.7:
                    f["options"] = "#minecraft:on_random_loot"
            else:
                f = {"function": "minecraft:enchant_randomly"}
                if copts and rng.random() < 0.4:
                    f["options"] = rng.sample(
                        copts, rng.randint(1, min(3, len(copts))))
                elif rng.random() < 0.7:
                    f["options"] = "#minecraft:on_random_loot"
            funcs.append(f)
        # похлёбка: эффекты ФУНКЦИЕЙ set_stew_effect (ванильный формат
        # археологии; «type» - id эффекта, duration - провайдер), если
        # компонент suspicious_stew_effects не назначил свои
        if (item == "minecraft:suspicious_stew"
                and "minecraft:suspicious_stew_effects" not in comps
                and rng.random() < 0.5):
            funcs.append({"function": "minecraft:set_stew_effect",
                          "effects": [
                              {"type": "minecraft:" + rng.choice(MOB_EFFECTS),
                               "duration": {
                                   "type": "minecraft:uniform",
                                   "min": float(rng.randint(4, 8)),
                                   "max": float(rng.randint(9, 18))}}
                              for _ in range(rng.randint(2, 4))]})
        # сырое мясо иногда «зажарено» (условие как у зомби-дропа).
        # entity_properties(this) требует THIS_ENTITY+ORIGIN - только типы
        # из _THIS_TYPES; в остальных контекстах оставляем чистый шанс
        if item in RAW_FOOD and rng.random() < 0.25:
            terms = [{"condition": "minecraft:random_chance",
                      "chance": round(rng.uniform(0.05, 0.35), 3)}]
            if self.ttype in _THIS_TYPES:
                terms.insert(0, {
                    "condition": "minecraft:entity_properties",
                    "entity": "this",
                    "predicate": {"minecraft:flags": {"is_on_fire": True}}})
            conds = ([{"condition": "minecraft:any_of", "terms": terms}]
                     if len(terms) > 1 else terms)
            funcs.append({"function": "minecraft:furnace_smelt",
                          "conditions": conds})
        if funcs:
            entry["functions"] = funcs
        return entry

    def _nested_entry(self, idx):
        """Запись-ссылка на вложенную таблицу - из ЗАРАНЕЕ ПОСТРОЕННОГО
        плана (только «вперёд», глубина <= 1, <= CAP_NESTED_PER_TABLE на
        таблицу) или ванильная, совместимая с контекстом текущей таблицы
        (маска её типа ? нашей) - иначе сервер WARN'ит при валидации."""
        rng = self.rng
        targets = [self.ids[t] for t in self.nested_plan.get(idx, ())
                   if t > idx]
        if targets and rng.random() < 0.55:
            value = rng.choice(targets)
        else:
            own = _TYPE_COVERAGE.get(self.ttype, 0)
            pool = [v for v in VANILLA_TABLES
                    if not (_vanilla_mask(v) & ~own)]
            value = rng.choice(pool or VANILLA_TABLES)
        return {"type": "minecraft:loot_table", "value": value,
                "weight": rng.randint(1, 6)}

    @staticmethod
    def _solid_entry(e):
        """Безусловная не-empty запись: item/tag/group без conditions
        (alternatives - если последний ребёнок безусловен: он всегда
        достижим). Именно такая запись гарантирует непустой пул."""
        if not isinstance(e, dict) or e.get("type") == "minecraft:empty":
            return False
        if e.get("conditions"):
            return False
        if e.get("type") == "minecraft:alternatives":
            ch = e.get("children") or []
            return bool(ch) and isinstance(ch[-1], dict) \
                and not ch[-1].get("conditions")
        return e.get("type") in ("minecraft:item", "minecraft:tag",
                                  "minecraft:group")

    def _entry(self, idx, char, theme, no_empty=False, no_struct=False,
               no_nested=False):
        """Запись пула: item / вложенная таблица (по плану) / empty /
        tag / group|alternatives. no_empty - гарантийный пул без
        пустых записей; no_struct - моб-таблица без group/alternatives
        и вложенных таблиц (лёгкий дроп, <= предела предметов с убийства).
        НЕДОСТИЖИМЫХ записей не генерируем В ПРИНЦИПЕ: не-последний
        ребёнок alternatives ВСЕГДА с условием."""
        rng = self.rng
        can_nested = not no_struct and not no_nested and self._refs_left > 0
        w = [("item", 60)]
        if can_nested:
            w.append(("nested", 8))
        if not no_empty:
            w.append(("empty", 5))
        if not no_struct:
            w.append(("tag", 7))
            w.append(("struct", 16))
        else:
            w.append(("tag", 12))
        kind = _weighted(rng, w)
        if kind == "item":
            return self._item_entry(char, theme)
        if kind == "nested":
            self._refs_left -= 1
            return self._nested_entry(idx)
        if kind == "empty":
            # маленький вес: пустая запись - «разрядка», а не правило
            return {"type": "minecraft:empty", "weight": rng.randint(1, 4)}
        if kind == "tag":
            return {"type": "minecraft:tag",
                    "name": rng.choice(ITEM_TAGS), "expand": True,
                    "weight": rng.randint(1, 8)}
        # группа/альтернативы: «комплект» из 2-3 предметов ОДНОЙ темы
        children = [self._item_entry(char, theme)
                    for _ in range(rng.randint(2, 3))]
        etype = "minecraft:group" if rng.random() < 0.70 else \
            "minecraft:alternatives"
        if etype == "minecraft:alternatives":
            # AlternativesEntry.validate: все дети, кроме последнего,
            # ОБЯЗАНЫ иметь conditions - иначе WARN «Unreachable entry!»
            # (первый безусловный ребёнок перехватывает выбор навсегда).
            # Условия - с РАЗНЫМИ шансами (богаче вариативность),
            # последнему ребёнку условия НЕ ставим НИКОГДА
            for ch in children[:-1]:
                conds = []
                if self.ttype in _TOOL_TYPES and rng.random() < 0.35:
                    conds.append(self._table_bonus_cond())
                conds.append({"condition": "minecraft:random_chance",
                              "chance": round(rng.uniform(0.15, 0.8), 3)})
                ch["conditions"] = conds
        return {"type": etype, "children": children,
                "weight": rng.randint(1, 5)}

    # ---------- условия ----------

    def _cf_cond(self):
        """Контекстно-свободное условие (random_chance и связки
        any_of/all_of/inverted) - валидно в ЛЮБОМ LootContextParamSet,
        в отличие от killed_by_player (нужен LAST_DAMAGE_PLAYER, только
        entity), table_bonus (TOOL) и random_chance_with_enchanted_bonus
        (ATTACKING_ENTITY, только entity)."""
        rng = self.rng
        r = rng.random()
        if r < 0.45:
            return {"condition": "minecraft:random_chance",
                    "chance": round(rng.uniform(0.05, 0.9), 3)}
        if r < 0.62:
            return {"condition": "minecraft:any_of", "terms": [
                {"condition": "minecraft:random_chance",
                 "chance": round(rng.uniform(0.05, 0.9), 3)}
                for _ in range(rng.randint(2, 3))]}
        if r < 0.78:
            return {"condition": "minecraft:all_of", "terms": [
                {"condition": "minecraft:random_chance",
                 "chance": round(rng.uniform(0.3, 0.9), 3)}
                for _ in range(2)]}
        if r < 0.92:
            return {"condition": "minecraft:inverted", "term": {
                "condition": "minecraft:random_chance",
                "chance": round(rng.uniform(0.1, 0.5), 3)}}
        return {"condition": "minecraft:any_of", "terms": [
            {"condition": "minecraft:inverted", "term": {
                "condition": "minecraft:random_chance",
                "chance": round(rng.uniform(0.1, 0.5), 3)}},
            {"condition": "minecraft:random_chance",
             "chance": round(rng.uniform(0.05, 0.6), 3)}]}

    def _table_bonus_cond(self):
        """table_bonus - шанс по уровню зачарования ИНСТРУМЕНТА
        (удочка на рыбалке, фортуна в vault/археологии); длины списка
        шансов = max_level+1. Вызывать только для типов с TOOL
        (fishing/archaeology/vault) - чистка _strip_cond снимает
        несовместимое при вложенности."""
        rng = self.rng
        ench = ("minecraft:luck_of_the_sea"
                if self.ttype == "minecraft:fishing"
                else "minecraft:fortune")
        return {"condition": "minecraft:table_bonus",
                "enchantment": ench,
                "chances": [round(rng.uniform(0.05, 0.5), 3)
                            for _ in range(4)]}

    # ---------- пулы и таблица ----------

    def _pool(self, idx, char, tier, themes, guarantee=False):
        """Пул таблицы. guarantee - «гарантийный» первый пул: rolls >= 1,
        БЕЗ условий пула, БЕЗ empty-записей, первая запись - безусловный
        предмет (инвариант «пустых контейнеров не бывает»; plain item
        не вылетает и из контекстной чистки _strip_table)."""
        rng = self.rng
        pool = {"rolls": _rolls(rng, tier)}
        # bonus_rolls - редкий «бонусный» ролл сверх основного: <= капа,
        # не в гарантийном пуле и не у мобов (жалоба на передоз роллов)
        if not guarantee and tier != "mob" and rng.random() < 0.12:
            pool["bonus_rolls"] = float(rng.randint(1, int(CAP_MAX_BONUS)))
        theme = _weighted(rng, themes) if themes else None
        if guarantee:
            n = rng.randint(2, 6)
            entries = [self._item_entry(char, theme)]
            entries += [self._entry(idx, char, theme, no_empty=True,
                                    no_nested=True)
                        for _ in range(n - 1)]
        else:
            n = _weighted(rng, [(2, 10), (3, 20), (4, 22), (5, 18),
                                (6, 12), (7, 8), (8, 6)])
            entries = [self._entry(idx, char, theme) for _ in range(n)]
        # страховка: >=1 безусловная не-empty запись в КАЖДОМ пуле
        if not any(self._solid_entry(e) for e in entries):
            entries.append(self._item_entry(char, theme))
        pool["entries"] = entries
        if not guarantee and rng.random() < 0.25:
            # условия пула: контекстно-свободные всегда; в TOOL-типах
            # (fishing/vault/archaeology) изредка table_bonus по уровню
            # зачарования инструмента
            if self.ttype in _TOOL_TYPES and rng.random() < 0.35:
                pool["conditions"] = [self._table_bonus_cond()]
            else:
                pool["conditions"] = [self._cf_cond()
                                      for _ in range(rng.randint(1, 2))]
        return pool

    def _mob_pool(self, rare=False):
        """Пул моб-таблицы: обычный дроп (все записи - предметы,
        лёгкие: <=2 компонентов, без контейнеров/NBT-мобов) или редкая
        награда за killed_by_player (шанс растёт с Добычей - как у
        ванильных drowned). rolls ВСЕГДА 1-2, никаких вложенных таблиц
        и group/alternatives - суммарно <= ~6 предметов с убийства."""
        rng = self.rng
        pool = {"rolls": _rolls(rng, "mob")}
        if rare:
            conds = [{"condition": "minecraft:killed_by_player"}]
            if rng.random() < 0.5:
                # шанс растёт с Добычей (Looting): ATTACKING_ENTITY есть
                # только в entity-контексте - как entities/drowned.json
                conds.append({
                    "condition": "minecraft:random_chance_with_enchanted_bonus",
                    "enchantment": "minecraft:looting",
                    "unenchanted_chance": round(rng.uniform(0.05, 0.3), 3),
                    "enchanted_chance": {
                        "type": "minecraft:linear",
                        "base": round(rng.uniform(0.1, 0.5), 3),
                        "per_level_above_first": round(
                            rng.uniform(0.02, 0.1), 3)}})
            else:
                conds.append({"condition": "minecraft:random_chance",
                              "chance": round(rng.uniform(0.05, 0.5), 3)})
            pool["conditions"] = conds
            entries = []
            for _ in range(rng.randint(1, 3)):
                theme = rng.choice(["treasure", "armory"])
                entries.append(self._item_entry(_THEME_CHAR[theme], theme,
                                                light=True))
            pool["entries"] = entries
        else:
            pool["entries"] = [self._item_entry("mob", None, light=True)
                               for _ in range(rng.randint(1, 4))]
        return pool

    def table(self, idx):
        """Одна таблица. idx - порядковый номер (для ссылок «вперёд»)."""
        rng = self.rng
        ttype = _weighted(rng, _TABLE_TYPES)
        self.ttype = ttype
        # характер: по типу таблицы или случайный
        if ttype == "minecraft:gift":
            char = _weighted(rng, [("food", 50), ("treasure", 50)])
        elif ttype == "minecraft:fishing":
            char = _weighted(rng, [("junk", 40), ("food", 35),
                                   ("treasure", 25)])
        elif ttype == "minecraft:archaeology":
            char = "junk"
        elif ttype == "minecraft:barter":
            char = "treasure"
        elif ttype == "minecraft:equipment":
            char = "weapons"
        elif ttype == "minecraft:entity":
            char = "mob"
        else:
            char = _weighted(rng, _CHARS)
        # темы таблицы: 2-4 с разными весами (мобам не нужны - их пулы
        # курируются отдельно: мусор/еда + редкая награда)
        themes = [] if ttype == "minecraft:entity" else _themes_for(rng, char)
        table = {"type": ttype}
        # тир богатства (жёсткие капы, см. _pool_count/_rolls): entity -
        # mob (1-2 пула, rolls 1-2, без вложенных таблиц, лёгкие
        # предметы); «сокровищный» тир - только у chest-типа с характером
        # treasure (бартер/подарки/рыбалка не раздуваются); char=="mob"
        # у chest-таблиц остаётся сундуком - сундук есть сундук
        tier = "mob" if ttype == "minecraft:entity" else (
            "treasure" if (char == "treasure"
                           and ttype == "minecraft:chest") else (
                "chest" if ttype == "minecraft:chest" else None))
        # лимит ссылок «вперёд» для ЭТОЙ таблицы (план построен в
        # __init__; entity-таблицы ссылок не имеют вовсе)
        self._refs_left = 0 if ttype == "minecraft:entity" else \
            len(self.nested_plan.get(idx, ()))
        if ttype == "minecraft:entity":
            # дроп моба: 1-2 пула, иногда второй - редкая награда
            # (суммарно <= 2 пулов: <= 4 роллов, ~<= 6 предметов)
            pools = [self._mob_pool() for _ in range(rng.randint(1, 2))]
            if len(pools) < 2 and rng.random() < 0.4:
                pools.append(self._mob_pool(rare=True))
        elif ttype == "minecraft:archaeology":
            # археология: черепки + редкие находки (как в ванили);
            # первый пул - гарантийный (безусловные предметы, rolls >= 1);
            # 2-3 пула - в общих капах тира None
            pools = []
            for _ in range(rng.randint(2, 3)):
                entries = []
                for _ in range(rng.randint(1, 4)):
                    if rng.random() < 0.5:
                        entries.append({"type": "minecraft:item",
                                        "name": rng.choice(POTTERY_SHERDS),
                                        "weight": rng.randint(5, 15)})
                    else:
                        entries.append(self._item_entry("junk"))
                pools.append({"rolls": _rolls(rng), "entries": entries})
        else:
            n = _pool_count(rng, tier)
            pools = [self._pool(idx, char, tier, themes, guarantee=(i == 0))
                     for i in range(n)]
        # страховка глобального капа пулов (структурно недостижимо,
        # но кап есть кап - самотест проверяет на каждой таблице)
        if len(pools) > CAP_MAX_POOLS:
            pools = pools[:CAP_MAX_POOLS]
        table["pools"] = pools
        # статистика по тирам - только для самотеста
        st = _TIER_STATS.setdefault(tier,
                                     {"tables": 0, "pools": [], "rolls": []})
        st["tables"] += 1
        st["pools"].append(len(pools))
        for p in pools:
            rv = p["rolls"]
            st["rolls"].append(rv if isinstance(rv, (int, float))
                                else (rv.get("min", 0.0)
                                      + rv.get("max", 0.0)) / 2.0)
        table["random_sequence"] = self.ids[idx]
        return table


# ---------------------------------------------------------------------------
# Публичная функция
# ---------------------------------------------------------------------------

def rand_loot(rng, ns, name, count=None):
    """Случайные лут-таблицы измерения.

    rng    - random.Random (весь рандом только через него);
    ns     - namespace;
    name   - имя измерения (id таблиц: <ns>:<name>_lootN);
    count  - сколько таблиц (None -> 1-2, «разумный минимум»).

    Возвращает {"loot_tables": {"<ns>:<name>_lootN": <json>, ...}}.
    Формат каждого JSON сверен с ванильными таблицами jar 26.2."""
    n = count if count is not None else rng.randint(1, 2)
    n = max(1, int(n))
    ids = ["%s:%s_loot%d" % (ns, name, i + 1) for i in range(n)]
    # рабочий кэш сведений о кастомных зачарованиях (имя/описание/
    # пассивность/слоты): явные set_ench_summaries + автопоиск по
    # gen_enchantments.LAST_ENCHANTMENTS (в одном процессе
    # generate_dimension генерирует зачарования ДО лута)
    global _ENCH_INFO
    _ENCH_INFO = _build_ench_info()
    gen = _LootGen(rng, ns, name, ids)
    tables = {}
    for i, tid in enumerate(ids):
        tables[tid] = gen.table(i)
    _fix_nesting_contexts(tables, ids)
    return {"loot_tables": tables}


# ---------------------------------------------------------------------------
# Контекстная чистка вложенных таблиц (real-server 26.2: WARN «Parameters
# [...] are not provided in this context»). loot_table-запись валидируется
# в контексте РОДИТЕЛЯ (и всех предков цепочки), поэтому таблица с
# killed_by_player/apply_bonus/entity_properties(this), вложенная в слабый
# контекст, портит лог. Наши ссылки всегда идут «вперёд» (родитель с
# меньшим номером), так что один проход по id убирает все нарушения.
# ---------------------------------------------------------------------------

def _strip_cond(cond, avail):
    """Условие после чистки; None - выбросить целиком."""
    if not isinstance(cond, dict):
        return cond
    t = cond.get("condition")
    if t == "minecraft:killed_by_player" and not (avail & _NEED_LDP):
        return None
    if (t == "minecraft:random_chance_with_enchanted_bonus"
            and not (avail & _NEED_ATK)):
        # ATTACKING_ENTITY есть только в entity-контексте (26.2)
        return None
    if (t == "minecraft:table_bonus" and not (avail & _NEED_TOOL)):
        return None
    if (t == "minecraft:entity_properties" and cond.get("entity") == "this"
            and (avail & (_NEED_THIS | _NEED_ORIGIN))
            != (_NEED_THIS | _NEED_ORIGIN)):
        return None
    if t in ("minecraft:any_of", "minecraft:all_of"):
        terms = [x for x in (_strip_cond(x, avail)
                             for x in cond.get("terms", []))
                 if x is not None]
        if not terms:
            return None
        if len(terms) == 1:
            return terms[0]
        cond["terms"] = terms
        return cond
    if t == "minecraft:inverted":
        inner = _strip_cond(cond.get("term"), avail)
        if inner is None:
            return None
        cond["term"] = inner
        return cond
    return cond


def _strip_ctx_list(lst, avail):
    out = [x for x in (_strip_cond(x, avail) for x in lst) if x is not None]
    return out or None


def _strip_entries(entries, avail):
    """Чистка записей под эффективный контекст; None - все записи вылетели."""
    out = []
    for e in entries:
        if not isinstance(e, dict):
            out.append(e)
            continue
        # ванильная таблица, чей тип не влезает в эффективный контекст
        if (e.get("type") == "minecraft:loot_table"
                and isinstance(e.get("value"), str)
                and e["value"].startswith("minecraft:")
                and _vanilla_mask(e["value"]) & ~avail):
            continue
        if "conditions" in e:
            kept = _strip_ctx_list(e["conditions"], avail)
            if kept is None:
                del e["conditions"]
            else:
                e["conditions"] = kept
        if "functions" in e:
            funcs = []
            for f in e["functions"]:
                if not isinstance(f, dict):
                    funcs.append(f)
                    continue
                fn = f.get("function")
                # apply_bonus/table_bonus-подобные функции с TOOL-контекстом
                if fn == "minecraft:apply_bonus" and not (avail & _NEED_TOOL):
                    continue
                # enchanted_count_increase читает ATTACKING_ENTITY (только entity)
                if (fn == "minecraft:enchanted_count_increase"
                        and not (avail & _NEED_ATK)):
                    continue
                if "conditions" in f:
                    kept = _strip_ctx_list(f["conditions"], avail)
                    if kept is None:
                        del f["conditions"]
                    else:
                        f["conditions"] = kept
                funcs.append(f)
            if funcs:
                e["functions"] = funcs
            else:
                del e["functions"]
        if "children" in e:
            kept = _strip_entries(e["children"], avail)
            if kept is None:
                del e["children"]
            else:
                e["children"] = kept
        # группа/альтернативы без детей - невалидны
        if (e.get("type") in ("minecraft:group", "minecraft:alternatives")
                and not e.get("children")):
            continue
        out.append(e)
    return out or None


def _strip_table(table, avail):
    pools = []
    for pool in table.get("pools", []):
        if "conditions" in pool:
            kept = _strip_ctx_list(pool["conditions"], avail)
            if kept is None:
                del pool["conditions"]
            else:
                pool["conditions"] = kept
        ents = _strip_entries(pool.get("entries", []), avail)
        if ents is None:
            continue  # пул опустел - выкидываем целиком
        pool["entries"] = ents
        pools.append(pool)
    table["pools"] = pools


# контексты «внешних» ссылок из компонентов предметов (НЕ из записей
# loot_table): открытие сундука и смерть моба имеют свой набор
# LootContextParamSet, НЕзависящий от того, в какой таблице лежит предмет
_CHEST_OPEN_CTX = _NEED_THIS | _NEED_ORIGIN        # как minecraft:chest
# смерть моба: entity-контекст (+ ATTACKING_ENTITY - убивший игрок/моб)
_ENTITY_DEATH_CTX = (_NEED_LDP | _NEED_THIS | _NEED_ORIGIN | _NEED_ATK)


def _external_ctx(tables, ids):
    """Ограничения контекста таблиц, на которые ссылаются КОМПОНЕНТЫ
    предметов: container_loot (открывается в chest-контексте), LootTable
    в block_entity_data (chest-контекст при открытии поставленного
    блока) и DeathLootTable в NBT мобов entity_data/SpawnData
    (entity-контекст при смерти). Этим ссылкам всё равно, в какой таблице
    они лежат, - а _nested_refs их не видит."""
    idset = set(ids)
    bound = {}

    def limit(tid, ctx):
        bound[tid] = bound.get(tid, _CTX_FULL) & ctx

    def walk(node):
        if isinstance(node, dict):
            cl = node.get("minecraft:container_loot")
            if isinstance(cl, dict) and cl.get("loot_table") in idset:
                limit(cl["loot_table"], _CHEST_OPEN_CTX)
            for key, ctx in (("DeathLootTable", _ENTITY_DEATH_CTX),
                             ("LootTable", _CHEST_OPEN_CTX)):
                v = node.get(key)
                if isinstance(v, str) and v in idset:
                    limit(v, ctx)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    for t in tables.values():
        walk(t)
    return bound


def _nested_refs(node, acc):
    if isinstance(node, dict):
        if node.get("type") == "minecraft:loot_table" \
                and isinstance(node.get("value"), str):
            acc.append(node["value"])
        for v in node.values():
            _nested_refs(v, acc)
    elif isinstance(node, list):
        for v in node:
            _nested_refs(v, acc)


def _fix_nesting_contexts(tables, ids):
    idset = set(ids)
    # стартовые границы - от «вНЕшних» ссылок из КОМПОНЕНТОВ предметов
    # (см. _external_ctx); дальше наслаиваются вложенные loot_table-записи
    bound = _external_ctx(tables, ids)
    for tid in ids:
        table = tables[tid]
        eff = _TYPE_COVERAGE.get(table.get("type"), 0) & bound.get(tid, _CTX_FULL)
        if eff != _CTX_FULL:
            _strip_table(table, eff)
        refs = []
        _nested_refs(table, refs)
        for ref in refs:
            if ref in idset:
                bound[ref] = eff & bound.get(ref, _CTX_FULL)


# ---------------------------------------------------------------------------
# САМОПРОВЕРКА И CLI (на диск ничего не пишет):
#   python -X utf8 gen_loot.py [N]          - самотест на N таблиц (умолч. 100)
#   python -X utf8 gen_loot.py 500          - самотест на 500 таблиц
#   python -X utf8 gen_loot.py --check      - батарея инвариантов на пачке сидов
#   python -X utf8 gen_loot.py --print --seed 777 [N]
#                                            - напечатать JSON таблиц сида 777
#   (флаги можно совмещать: --print --seed 3 N=12 и т.п.)
# ---------------------------------------------------------------------------

import random as _random


def _setup_custom_enchs(seed=777):
    """Кастомные зачарования измерения - как их подмешивает
    generate_dimension: генерируются ДО лута (rand_enchantments
    запоминает их в LAST_ENCHANTMENTS), id передаются
    set_custom_enchants, а сведения (имя/описание/пассивность/
    supported_items) rand_loot находит сам - автопоиском по
    LAST_ENCHANTMENTS. Возвращает (ids, passive_ids, результат)."""
    global ENCH_SUMMARIES
    import gen_enchantments as _ge
    ENCH_SUMMARIES = {}
    _er = _ge.rand_enchantments(_random.Random(seed), "rndim", "testdim",
                                count=12)
    ids = sorted(_er["enchantments"])
    passive = set(_ge.passive_enchants(_er["enchantments"]))
    set_custom_enchants(ids)
    return ids, passive, _er


# ---- симуляция лута (проверка «пустых контейнеров не бывает») -------------

def _sim_cond(c, rng):
    """Условие в симуляции: контекстные - по номиналу (killed_by_player
    считаем истинным: игрока убил игрок; entity_properties - 50/50)."""
    if not isinstance(c, dict):
        return True
    t = c.get("condition")
    if t == "minecraft:random_chance":
        return rng.random() < c.get("chance", 0.5)
    if t == "minecraft:any_of":
        return any(_sim_cond(x, rng) for x in c.get("terms", []))
    if t == "minecraft:all_of":
        return all(_sim_cond(x, rng) for x in c.get("terms", []))
    if t == "minecraft:inverted":
        return not _sim_cond(c.get("term", {}), rng)
    if t == "minecraft:table_bonus":
        ch = c.get("chances") or [0.5]
        return rng.random() < float(ch[0])
    if t == "minecraft:random_chance_with_enchanted_bonus":
        u = c.get("unenchanted_chance", 0.5)
        if isinstance(u, dict):
            u = u.get("base", 0.5)
        return rng.random() < float(u)
    if t == "minecraft:entity_properties":
        return rng.random() < 0.5  # is_on_fire и прочие флаги
    return True


def _sim_conds(conds, rng):
    return all(_sim_cond(c, rng) for c in (conds or []))


def _sim_entry(e, rng):
    """Сколько предметов даёт запись (предметы, а не размеры стаков)."""
    t = e.get("type")
    if t == "minecraft:empty":
        return 0
    if t == "minecraft:group":
        return sum(_sim_entry(ch, rng) for ch in e.get("children", []))
    if t == "minecraft:alternatives":
        for ch in e.get("children", []):
            if _sim_conds(ch.get("conditions"), rng):
                return _sim_entry(ch, rng)
        return 0
    return 1  # item / tag / loot_table (своя таблица непуста по инварианту)


def _simulate(table, rng):
    """Сколько предметов выдаёт таблица при одном «открытии» - честная
    к rolls/bonus_rolls/условиям/весам/пустым записям симуляция."""
    items = 0
    for pool in table.get("pools", []):
        if not _sim_conds(pool.get("conditions"), rng):
            continue
        rolls = pool.get("rolls", 1)
        if isinstance(rolls, dict):
            n = rng.randint(int(rolls.get("min", 1)), int(rolls.get("max", 1)))
        else:
            n = int(rolls)
        bonus = pool.get("bonus_rolls", 0)
        if isinstance(bonus, dict):
            bonus = rng.randint(int(bonus.get("min", 0)),
                                int(bonus.get("max", 0)))
        for _ in range(n + int(bonus)):
            ents = pool.get("entries") or []
            if not ents:
                continue
            ws = [max(1, e.get("weight", 1)) for e in ents]
            items += _sim_entry(rng.choices(ents, weights=ws)[0], rng)
    return items


def _rolls_bounds(rolls):
    """(min, max) роллов пула: константа или uniform-провайдер."""
    if isinstance(rolls, dict):
        return float(rolls.get("min", 0)), float(rolls.get("max", 0))
    return float(rolls), float(rolls)


def _run_selftest(n_tables, seed, verbose=True):
    """Полная батарея инвариантов на n_tables таблицах сида seed.
    Возвращает (violations, tables). Печатает статистику, если verbose."""
    import json as _json

    rng = _random.Random(seed)
    _REVEAL_STATS["named"] = _REVEAL_STATS["seeded"] = 0  # покрытие имён
    _ench_ids, _passive_ids, _er = _setup_custom_enchs()
    _TIER_STATS.clear()
    out = rand_loot(rng, "rndim", "testdim", count=n_tables)
    tabs = out["loot_tables"]

    def _walk_entries(table):
        for p in table["pools"]:
            stack = list(p["entries"])
            while stack:
                e = stack.pop(0)
                if "children" in e:
                    stack = list(e["children"]) + stack
                yield p, e

    viol = []

    # =====================================================================
    # КАПЫ (жалоба: «слишком много rolls - контейнеры ПУСТЫЕ от
    # передозировки, игра ВИСНЕТ после убийства моба») - на КАЖДОЙ таблице
    # =====================================================================
    cap_pools_max = 0
    cap_rolls_max = 0.0
    cap_rolls_min = 1.0
    bonus_seen = 0
    for tid, t in tabs.items():
        if len(t["pools"]) > CAP_MAX_POOLS:
            viol.append("кап пулов: %s -> %d (> %d)"
                        % (tid, len(t["pools"]), CAP_MAX_POOLS))
        cap_pools_max = max(cap_pools_max, len(t["pools"]))
        for p in t["pools"]:
            mn, mx = _rolls_bounds(p.get("rolls", 1))
            if mn < 1.0:
                viol.append("rolls min < 1 (пул «съедается»): %s" % tid)
            if mx > CAP_MAX_ROLLS:
                viol.append("кап роллов: %s -> %s (> %s)"
                            % (tid, p.get("rolls"), CAP_MAX_ROLLS))
            cap_rolls_max = max(cap_rolls_max, mx)
            cap_rolls_min = min(cap_rolls_min, mn)
            br = p.get("bonus_rolls")
            if br is not None:
                bmn, bmx = _rolls_bounds(br)
                if bmx > CAP_MAX_BONUS or bmn < 0:
                    viol.append("кап bonus_rolls: %s -> %r" % (tid, br))
                bonus_seen += 1

    # ---- вложенные loot_table-записи: <= CAP_NESTED_PER_TABLE, глубина 1 --
    ref_targets = set()
    ref_total = 0
    for tid, t in tabs.items():
        n_ref = 0
        for _pool, e in _walk_entries(t):
            if e.get("type") == "minecraft:loot_table":
                n_ref += 1
                if isinstance(e.get("value"), str) and e["value"] in tabs:
                    ref_targets.add(e["value"])
        ref_total += n_ref
        if n_ref > CAP_NESTED_PER_TABLE:
            viol.append("кап вложенных таблиц: %s -> %d (> %d)"
                        % (tid, n_ref, CAP_NESTED_PER_TABLE))
    for tgt in ref_targets:
        # цель не должна ссылаться на НАШИ таблицы (глубина <= 1)
        refs = []
        _nested_refs(tabs[tgt], refs)
        deep = [r for r in refs if r in tabs]
        if deep:
            viol.append("глубина вложенных ссылок > 1: %s -> %s"
                        % (tgt, ",".join(sorted(deep)[:3])))

    # ---- mob-таблицы: лёгкие, без вложенных таблиц и group ---------------
    mob_tables = 0
    mob_max_items = 0
    for tid, t in tabs.items():
        if t.get("type") != "minecraft:entity":
            continue
        mob_tables += 1
        if not 1 <= len(t["pools"]) <= 2:
            viol.append("mob: пулов %d (нужно 1-2): %s"
                        % (len(t["pools"]), tid))
        total_max = 0
        for p in t["pools"]:
            mn, mx = _rolls_bounds(p.get("rolls", 1))
            if mx > 2.0:
                viol.append("mob: rolls %s (> 2): %s" % (p.get("rolls"), tid))
            total_max += mx
            _stack = list(p.get("entries") or [])
            while _stack:
                e = _stack.pop(0)
                if isinstance(e, dict) and "children" in e:
                    _stack = list(e["children"]) + _stack
                if not isinstance(e, dict):
                    continue
                et = e.get("type")
                if et == "minecraft:loot_table":
                    viol.append("mob: вложенная таблица: %s" % tid)
                if et in ("minecraft:group", "minecraft:alternatives"):
                    viol.append("mob: %s (тяжёлый дроп): %s" % (et, tid))
                if et != "minecraft:item":
                    continue
                for f in e.get("functions") or []:
                    if not (isinstance(f, dict)
                            and f.get("function") == "minecraft:set_components"):
                        continue
                    cs = f.get("components") or {}
                    heavy = [k for k in cs if k in _MOB_HEAVY_COMPS]
                    if heavy:
                        viol.append("mob: тяжёлый компонент %s: %s"
                                    % (heavy[0], tid))
                    # функциональные = не идентичность и не косметика
                    # (rarity/custom_data - копеечные, не считаем)
                    nfun = len([k for k in cs if k not in (
                        "minecraft:custom_name", "minecraft:item_name",
                        "minecraft:lore") and k not in _COSMETIC_KEYS])
                    if nfun > 2:
                        viol.append("mob: функциональных компонентов %d "
                                    "(> 2): %s" % (nfun, tid))
        mob_max_items = max(mob_max_items, total_max)
        if total_max > CAP_MAX_ITEMS_MOB:
            viol.append("mob: предметов с убийства %d (> %d): %s"
                        % (total_max, CAP_MAX_ITEMS_MOB, tid))

    # ---- ПУСТЫЕ КОНТЕЙНЕРЫ: гарантийный пул + симуляция ------------------
    sim_rng = _random.Random(seed ^ 0x5EED)
    sim_fail = 0
    for tid, t in tabs.items():
        ok = False
        for p in t["pools"]:
            if p.get("conditions"):
                continue
            mn, _mx = _rolls_bounds(p.get("rolls", 1))
            if mn < 1.0:
                continue
            ents = p.get("entries") or []
            if any(e.get("type") == "minecraft:empty" for e in ents):
                continue
            if any(_LootGen._solid_entry(e) for e in ents):
                ok = True
                break
        if not ok:
            viol.append("нет гарантийного пула (риск пустого контейнера): %s"
                        % tid)
        for _ in range(8):  # 8 «открытий» на таблицу - все обязаны дать >=1
            if _simulate(t, sim_rng) < 1:
                sim_fail += 1
                viol.append("симуляция: таблица выдала 0 предметов: %s" % tid)
                break

    # ---- статистика (verbose) --------------------------------------------
    pools_n = [len(t["pools"]) for t in tabs.values()]
    rolls = []
    names = []
    ncomp = 0
    nench = 0
    comp_kinds = set()
    for t in tabs.values():
        for p in t["pools"]:
            _mn, mx = _rolls_bounds(p.get("rolls", 1))
            rolls.append(mx)
        for _pool, e in _walk_entries(t):
            for f in e.get("functions", []):
                if f.get("function") == "minecraft:set_components":
                    ncomp += 1
                    comp_kinds.update(f["components"])
                    cn = f["components"].get("minecraft:item_name") or f["components"].get("minecraft:custom_name")
                    if cn:
                        names.append(cn["text"])
                    if "minecraft:enchantments" in f["components"]:
                        nench += 1
    if verbose:
        print("таблиц: %d, всего пулов: %d (среднее %.2f, макс %d; кап %d)"
              % (len(tabs), sum(pools_n), sum(pools_n) / len(pools_n),
                 max(pools_n), CAP_MAX_POOLS))
        print("роллы: среднее-макс %.2f, максимум %s (кап %s); "
              "min роллов >= %s; bonus_rolls у %d пулов (кап %s)"
              % (sum(rolls) / len(rolls), _fmt_num(cap_rolls_max),
                 _fmt_num(CAP_MAX_ROLLS), _fmt_num(cap_rolls_min), bonus_seen,
                 _fmt_num(CAP_MAX_BONUS)))
        print("вложенных loot_table-записей: %d (макс %d на таблицу), "
              "таблиц-целей: %d (глубина <= 1)"
              % (ref_total, CAP_NESTED_PER_TABLE, len(ref_targets)))
        print("mob-таблиц: %d, предметов с убийства <= %d (кап %d)"
              % (mob_tables, mob_max_items, CAP_MAX_ITEMS_MOB))
    # ---- структура пулов/роллов ПО ТИРАМ таблиц ---------------------------
    _tier_snap = {k: {"tables": v["tables"], "pools": list(v["pools"]),
                      "rolls": list(v["rolls"])}
                  for k, v in _TIER_STATS.items()}
    if verbose:
        for key, label in (("mob", "mob-таблицы (entity)"),
                           ("chest", "сундуки (chest)"),
                           ("treasure", "сокровища (chest + treasure)"),
                           (None, "прочие (gift/fishing/equipment/archaeology/barter)")):
            st = _tier_snap.get(key)
            if not st or not st["tables"]:
                print("%s: таблиц нет" % label)
                continue
            pl, rl = st["pools"], st["rolls"]
            print("%s: %d таблиц, пулов %d-%d (среднее %.1f), "
                  "роллы %.1f-%.1f (среднее %.1f)"
                  % (label, st["tables"], min(pl), max(pl),
                     sum(pl) / len(pl), min(rl), max(rl), sum(rl) / len(rl)))
        print("set_components-записей: %d (с зачарованиями: %d)"
              % (ncomp, nench))
        print("разных компонентов в выпуске: %d" % len(comp_kinds))

    # ---- вложенные стеки: глубина, компоненты внутри компонентов ---------
    nested_keys = set()
    nested_deep = 0  # вложенный стек С компонентами
    nested_total = 0

    def _scan_nested(node):
        nonlocal nested_deep, nested_total
        if isinstance(node, dict):
            if "id" in node and isinstance(node.get("components"), dict):
                nested_total += 1
                nested_keys.update(node["components"])
                # «глубина-2+»: компонент внутри вложенного стека сам
                # содержит стеки (арбалет в сундуке с зельевыми стрелами)
                if any(k in node["components"] for k in (
                        "minecraft:charged_projectiles",
                        "minecraft:container",
                        "minecraft:bundle_contents")):
                    nested_deep += 1
            for v in node.values():
                _scan_nested(v)
        elif isinstance(node, list):
            for v in node:
                _scan_nested(v)

    for t in tabs.values():
        _scan_nested(t)
    if verbose:
        print("вложенных стеков с компонентами: %d (из них глубина-2+: %d), "
              "разных компонентов внутри: %d"
              % (nested_total, nested_deep, len(nested_keys)))
    # осмысленность: предметов, у которых компоненты исчерпываются
    # одним именем, быть НЕ ДОЛЖНО - это чистый ванильный предмет,
    # а не кастомный (item_name ставится только при других компонентах)
    only_look = 0
    examples = []
    for t in tabs.values():
        for _pool, e in _walk_entries(t):
            for f in e.get("functions", []):
                if not (isinstance(f, dict)
                        and f.get("function") == "minecraft:set_components"):
                    continue
                cs = f["components"]
                if "minecraft:item_name" in cs and set(cs) <= {
                        "minecraft:item_name", "minecraft:custom_name",
                        "minecraft:lore"}:
                    only_look += 1
                cn = cs.get("minecraft:item_name") or cs.get("minecraft:custom_name")
                if cn and len(examples) < 14:
                    def _am_s(m):
                        a = m.get("amount", 0)
                        return "%s%s%g@%s" % (
                            m.get("type", "?").split(":")[-1],
                            "+" if a >= 0 else "", a,
                            m.get("slot", "any"))
                    am = cs.get("minecraft:attribute_modifiers") or []
                    amtxt = ("| attrs: " + ", ".join(
                        _am_s(m) for m in am
                        if isinstance(m, dict))[:100]) if am else ""
                    loretxt = cs.get("minecraft:lore")
                    lrtxt = ("| lore: " + " / ".join(
                        l.get("text", "") for l in loretxt)
                        [:100]) if loretxt else ""
                    examples.append((
                        e.get("name"), cn["text"],
                        ", ".join(sorted(k.split(":", 1)[-1] for k in cs
                                         if k != "minecraft:custom_name")),
                        amtxt, lrtxt))
    if verbose:
        print("предметов «только имя»: %d (инвариант: 0)" % only_look)
        print("примеры кастомных предметов (имя + атрибуты + lore):")
        for it, nm, keys, amtxt, lrtxt in examples:
            print("  %s «%s» [%s] %s %s"
                  % ((it or "?")[10:], nm, keys, amtxt, lrtxt))
        print("имён: %d, примеры:" % len(names))
        for nm in names[:10]:
            print("  «%s»" % nm)

    # ---- инварианты контекста (независимая проверка _fix_nesting_contexts)
    def _needs_of(node):
        needs = 0
        if isinstance(node, dict):
            if node.get("condition") == "minecraft:killed_by_player":
                needs |= _NEED_LDP
            if node.get("condition") in (
                    "minecraft:table_bonus", "minecraft:match_tool"):
                needs |= _NEED_TOOL
            if node.get("condition") == \
                    "minecraft:random_chance_with_enchanted_bonus":
                needs |= _NEED_ATK
            if node.get("function") == "minecraft:apply_bonus":
                needs |= _NEED_TOOL
            if node.get("function") == "minecraft:enchanted_count_increase":
                needs |= _NEED_ATK
            if (node.get("condition") == "minecraft:entity_properties"
                    and node.get("entity") == "this"):
                needs |= _NEED_THIS | _NEED_ORIGIN
            if (node.get("type") == "minecraft:loot_table"
                    and isinstance(node.get("value"), str)
                    and node["value"].startswith("minecraft:")):
                needs |= _vanilla_mask(node["value"])
            for v in node.values():
                needs |= _needs_of(v)
        elif isinstance(node, list):
            for v in node:
                needs |= _needs_of(v)
        return needs

    # запрет удалённых из генерации ключей (grep по сгенерированному
    # JSON): can_place_on / can_break (разрешения adventure-режима -
    # бесполезны), item_model (только путает), NoAI / Invulnerable
    # (мобы должны жить и быть убиваемыми) - их не должно быть НИГДЕ;
    # tooltip_display / tooltip_style / hide_tooltip / hidden_components
    # - прятанье тултипов запутывает игроков (жалоба)
    for tid in tabs:
        blob = _json.dumps(tabs[tid], ensure_ascii=False)
        for bad in ("minecraft:can_place_on", "minecraft:can_break",
                    "minecraft:item_model", "NoAI", "Invulnerable",
                    "camera_overlay", "minecraft:stackable", "Кайм",
                    "minecraft:tooltip_display", "minecraft:tooltip_style",
                    "hide_tooltip", "hidden_components"):
            if bad in blob:
                viol.append("запрещённый ключ %s: %s" % (bad, tid))
    bound = {}
    for tid in tabs:  # порядок вставки = порядок генерации (ссылки «вперёд»)
        t = tabs[tid]
        eff = _TYPE_COVERAGE.get(t.get("type"), 0) & bound.get(tid, _CTX_FULL)
        if _needs_of(t) & ~eff:
            viol.append("контекст: %s (тип %s)" % (tid, t.get("type")))
        refs = []
        _nested_refs(t, refs)
        for r in refs:
            if r in tabs:
                bound[r] = eff & bound.get(r, _CTX_FULL)
    for tid, t in tabs.items():
        for e in [x for _p, x in _walk_entries(t)]:
            if e.get("type") == "minecraft:alternatives":
                for ch in e.get("children", [])[:-1]:
                    if not ch.get("conditions"):
                        viol.append("unreachable: %s" % tid)

    # ---- инварианты ВЛОЖЕННЫХ стеков (валидатор 26.2) ---------------------
    def _check_stacks(node, where):
        if isinstance(node, dict):
            if "id" in node and isinstance(node.get("count"), int):
                if node["id"] in _STACK1 and node["count"] > 1:
                    viol.append("stack1: %s -> %s x%d"
                                % (where, node["id"], node["count"]))
                cc = node.get("components") or {}
                if node["id"] in _DAMAGEABLE \
                        and isinstance(cc.get("minecraft:max_stack_size"), int) \
                        and cc["minecraft:max_stack_size"] > 1:
                    viol.append("dmg+stack: %s -> %s"
                                % (where, node["id"]))
            for k, v in node.items():
                _check_stacks(v, where)
        elif isinstance(node, list):
            for v in node:
                _check_stacks(v, where)

    for tid, t in tabs.items():
        _check_stacks(t, tid)

    # ---- тиры пулов/роллов (жёсткие границы генерации) -------------------
    # «проверка состоялась» - только на достаточно большой выборке
    # (при 6 таблицах моба может просто не быть - это не инвариант)
    _TIER_BOUNDS = {"mob": ((1, 2), (1.0, 2.0)),
                    "chest": ((3, 6), (1.0, 6.0)),
                    "treasure": ((4, 8), (2.0, 6.0)),
                    None: ((2, 5), (1.0, 6.0))}
    for key, ((plo, phi), (rlo, rhi)) in _TIER_BOUNDS.items():
        st = _tier_snap.get(key) or {"pools": [], "rolls": []}
        if not st["pools"]:
            if n_tables >= 30:
                viol.append("тир %s: ни одной таблицы (проверка не "
                            "состоялась)" % key)
        for v in st["pools"]:
            if not plo <= v <= phi:
                viol.append("тир %s: пулов %d (нужно %d-%d)"
                            % (key, v, plo, phi))
        for v in st["rolls"]:
            if not rlo <= v <= rhi:
                viol.append("тир %s: роллы %s (нужно %.0f-%.0f)"
                            % (key, v, rlo, rhi))

    # ---- СОВМЕСТИМОСТЬ ЗАЧАРОВАНИЙ (жалоба: «не надо мечу давать защиту») -
    # каждая пара (предмет, зачарование) проверяется по точным
    # supported_items из jar 26.2: ванильные - ENCHANTS, кастомные -
    # кэш _ENCH_INFO (теги разрешены картой ENCH_TAG_ITEMS)
    _ench_stat = {"items": 0, "hints": 0, "rescued": 0, "examples": [],
                  "pairs": 0, "custom_pairs": 0, "compat_viol": 0}
    _rem_stat = {"edible": 0, "with_rem": 0, "custom": 0, "examples": []}
    _visual_only = []

    def _custom_ench_ids(cs, fns):
        """id зачарований НЕ из minecraft:* у предмета (компоненты +
        функция set_enchantments)."""
        ids = []
        for ekey in ("minecraft:enchantments",
                     "minecraft:stored_enchantments"):
            em = cs.get(ekey)
            if isinstance(em, dict):
                ids.extend(e for e in em
                           if not str(e).startswith("minecraft:"))
        for f in fns:
            if isinstance(f, dict) \
                    and f.get("function") == "minecraft:set_enchantments":
                em = f.get("enchantments") or {}
                if isinstance(em, dict):
                    ids.extend(e for e in em
                               if not str(e).startswith("minecraft:"))
        return ids

    def _has_hint(lore, eid):
        nm = _ENCH_INFO.get(eid, {}).get("name") or eid
        return any(isinstance(l, dict)
                   and str(l.get("text", "")).startswith(nm + " -")
                   for l in (lore or []))

    def _check_ench_item(cs, fns, where, item):
        """Все зачарования предмета: (а) совместимость - ванильные по
        ENCHANTS (supported_items из jar), кастомные по _ENCH_INFO
        (enchanted_book - исключение-носитель); (б) у КАЖДОГО кастомного
        есть lore-строка «Имя - описание»; (в) options у функций
        enchant_with_levels/enchant_randomly - только совместимые."""
        # (в) опции функций
        for f in fns:
            if not isinstance(f, dict):
                continue
            if f.get("function") not in ("minecraft:enchant_with_levels",
                                         "minecraft:enchant_randomly"):
                continue
            opts = f.get("options")
            if isinstance(opts, list):
                for o in opts:
                    _ench_stat["pairs"] += 1
                    if str(o).startswith("minecraft:") or item is None:
                        continue
                    if not _custom_ench_ok(o, item):
                        _ench_stat["compat_viol"] += 1
                        viol.append("несовместимое зачарование (options): "
                                    "%s -> %s %s" % (where, item, o))
        cids = _custom_ench_ids(cs, fns)
        if not cids:
            return
        _ench_stat["items"] += 1
        lore = cs.get("minecraft:lore") or []
        for cid in set(cids):
            if cid not in _ENCH_INFO:
                viol.append("custom-ench без сведений: %s (%s)"
                            % (cid, where))
            elif not _has_hint(lore, cid):
                viol.append("custom-ench без lore-подсказки: %s (%s)"
                            % (cid, where))
            else:
                _ench_stat["hints"] += 1
        em = (cs.get("minecraft:enchantments")
              or cs.get("minecraft:stored_enchantments") or {})
        if em and all(not str(k).startswith("minecraft:") for k in em):
            _ench_stat["rescued"] += 1
            # для примеров предпочитаем ИМЕННЫЕ предметы (жалоба была
            # именно про «выглядит особым, а обычный»)
            if (cs.get("minecraft:custom_name")
                    and len(_ench_stat["examples"]) < 10) \
                    or len(_ench_stat["examples"]) < 4:
                _ench_stat["examples"].append(
                    (where, cs.get("minecraft:custom_name") or {},
                     list(em), [l.get("text", "")
                                for l in (cs.get("minecraft:lore") or [])]))
        # (а) совместимость ВСЕХ пар (предмет, зачарование)
        if item is not None:
            for ekey in ("minecraft:enchantments",
                         "minecraft:stored_enchantments"):
                emap = cs.get(ekey)
                if not isinstance(emap, dict):
                    continue
                for e in emap:
                    _ench_stat["pairs"] += 1
                    if str(e).startswith("minecraft:"):
                        if item in ENCH_BOOKS:
                            continue  # книга-носитель - валидно
                        if not _ench_supports(e, item):
                            _ench_stat["compat_viol"] += 1
                            viol.append("несовместимое ванильное зачарование: "
                                        "%s -> %s %s" % (where, item, e))
                    else:
                        _ench_stat["custom_pairs"] += 1
                        if not _custom_ench_ok(e, item):
                            _ench_stat["compat_viol"] += 1
                            viol.append("несовместимое кастомное зачарование: "
                                        "%s -> %s %s" % (where, item, e))
            for f in fns:
                if not (isinstance(f, dict)
                        and f.get("function") == "minecraft:set_enchantments"):
                    continue
                emap = f.get("enchantments") or {}
                for e in emap:
                    _ench_stat["pairs"] += 1
                    if str(e).startswith("minecraft:"):
                        if item in ENCH_BOOKS:
                            continue
                        if not _ench_supports(e, item):
                            _ench_stat["compat_viol"] += 1
                            viol.append("несовместимое зачарование (функция): "
                                        "%s -> %s %s" % (where, item, e))
                    else:
                        _ench_stat["custom_pairs"] += 1
                        if not _custom_ench_ok(e, item):
                            _ench_stat["compat_viol"] += 1
                            viol.append("несовместимое кастомное (функция): "
                                        "%s -> %s %s" % (where, item, e))

    # записи таблиц: компоненты + функции вместе (зачарования бывают
    # и в set_enchantments-функции); «только визуал» = компоненты есть,
    # все косметические, других функций нет
    for tid, t in tabs.items():
        for _pool, e in _walk_entries(t):
            if e.get("type") != "minecraft:item":
                continue
            fns = [f for f in (e.get("functions") or [])
                   if isinstance(f, dict)]
            cs = {}
            for f in fns:
                if f.get("function") == "minecraft:set_components":
                    cs.update(f.get("components") or {})
            others = [f for f in fns
                      if f.get("function") != "minecraft:set_components"]
            if cs and set(cs) <= _COSMETIC_KEYS and not others:
                _visual_only.append((tid, e.get("name")))
            _check_ench_item(cs, fns, tid, e.get("name"))
            if "minecraft:food" in cs and "minecraft:consumable" not in cs:
                viol.append("item with food but missing consumable: %s -> %s"
                            % (tid, e.get("name")))
            # use_remainder: только у съедобных, count всегда 1, id -
            # из пула остатков/базовой посуды; именной - с custom_name
            nm_it = e.get("name") or ""
            if (nm_it in FOOD or nm_it in RAW_FOOD or nm_it in BAD_FOOD
                    or "minecraft:food" in cs
                    or "minecraft:consumable" in cs):
                _rem_stat["edible"] += 1
                rem = cs.get("minecraft:use_remainder")
                if isinstance(rem, dict):
                    _rem_stat["with_rem"] += 1
                    if rem.get("count") != 1:
                        viol.append("use_remainder count != 1: %s -> %r"
                                    % (tid, rem))
                    rid = rem.get("id")
                    if rid not in _REMAINDER_POOL and rid not in (
                            "minecraft:bowl", "minecraft:glass_bottle"):
                        viol.append("use_remainder вне пула: %s -> %s"
                                    % (tid, rid))
                    rc = rem.get("components") or {}
                    cname = rc.get("minecraft:item_name") or rc.get("minecraft:custom_name")
                    if isinstance(cname, dict):
                        _rem_stat["custom"] += 1
                        if len(_rem_stat["examples"]) < 8:
                            _rem_stat["examples"].append(
                                (nm_it, rid,
                                 cname.get("text", ""),
                                 [l.get("text", "") for l in
                                  (rc.get("minecraft:lore") or [])]))

    # вложенные стеки (container/bundle/charged_projectiles/оборудование
    # мобов в NBT): косметика-без-функций быть не должна, зачарования -
    # совместимые и с подсказками; use_remainder-остатки - не предметы
    # для проверки «только визуал» (трофей после еды имеет право быть
    # просто вещью)
    def _walk_stacks(node, pkey, where):
        if isinstance(node, dict):
            if isinstance(node.get("id"), str) and "count" in node \
                    and pkey != "minecraft:use_remainder":
                cc = node.get("components") or {}
                if cc and set(cc) <= (_COSMETIC_KEYS | _BONUS_ONLY_KEYS):
                    _visual_only.append((where, node["id"]))
                _check_ench_item(cc, [], where, node["id"])
                if "minecraft:food" in cc and "minecraft:consumable" not in cc:
                    viol.append("nested stack with food but missing consumable: %s -> %s"
                                % (where, node.get("id")))
            for k, v in node.items():
                _walk_stacks(v, k, where)
        elif isinstance(node, list):
            for v in node:
                _walk_stacks(v, pkey, where)

    for tid, t in tabs.items():
        _walk_stacks(t, "", tid)

    if _visual_only:
        viol.extend("предмет «только с визуалом»: %s -> %s" % (w, it)
                    for w, it in _visual_only[:5])
    if _ench_stat["items"] == 0 and n_tables >= 30:
        viol.append("ни одного предмета с кастомным зачарованием "
                    "(проверка подсказок не состоялась)")
    if verbose:
        if _rem_stat["edible"]:
            share = _rem_stat["with_rem"] / float(_rem_stat["edible"])
            print("съедобных предметов: %d, с use_remainder: %d (%.0f%%; "
                  "инвариант 35-65%%), из них КАСТОМНЫХ именных: %d"
                  % (_rem_stat["edible"], _rem_stat["with_rem"],
                     100.0 * share, _rem_stat["custom"]))
            if n_tables >= 30 and not 0.35 <= share <= 0.65:
                viol.append("доля остатков %.2f вне [0.35; 0.65]" % share)
            if (_rem_stat["with_rem"] >= 20
                    and _rem_stat["custom"] == 0 and n_tables >= 30):
                viol.append("ни одного кастомного именного остатка "
                            "(шанс 35%% от остатков)")
        elif n_tables >= 30:
            viol.append("ни одного съедобного предмета (use_remainder "
                        "не проверен)")
        print("предметов с кастомными зачарованиями: %d (lore-подсказок: %d), "
              "«спасённых» пассивным зачарованием: %d, "
              "«только визуал»: %d (инвариант: 0)"
              % (_ench_stat["items"], _ench_stat["hints"],
                 _ench_stat["rescued"], len(_visual_only)))
        print("совместимость зачарований: пар проверено %d (из них "
              "кастомных %d), нарушений %d (инвариант: 0)"
              % (_ench_stat["pairs"], _ench_stat["custom_pairs"],
                 _ench_stat["compat_viol"]))
        if (_ench_stat["compat_viol"] == 0 and _ench_stat["pairs"] < 50
                and n_tables >= 30):
            viol.append("слишком мало пар зачарований для проверки (%d)"
                        % _ench_stat["pairs"])
        print("примеры «спасённых» (только визуал -> пассивное зачарование "
              "+ lore-подсказка):")
        _ex = [x for x in _ench_stat["examples"]
               if x[1].get("text")] + [x for x in _ench_stat["examples"]
               if not x[1].get("text")]
        for w, cn, em, lore in _ex[:4]:
            print("  %s «%s» чары=%s | lore: %s"
                  % (w, cn.get("text", ""), ",".join(em),
                     " / ".join(lore)[:120]))
        print("примеры КАСТОМНЫХ именных остатков (use_remainder):")
        for it, rid, nm, lore in _rem_stat["examples"][:4]:
            print("  %s -> %s «%s»%s"
                  % ((it or "?")[10:], (rid or "?")[10:], nm,
                     (" | lore: " + " / ".join(lore)[:60]) if lore else ""))
    else:
        # в тихом режиме инварианты-«состоятельности» тоже проверяем
        # (на достаточно большой выборке)
        if _rem_stat["edible"] and n_tables >= 30:
            share = _rem_stat["with_rem"] / float(_rem_stat["edible"])
            if not 0.35 <= share <= 0.65:
                viol.append("доля остатков %.2f вне [0.35; 0.65]" % share)

    # ---- инварианты ЖАЛОБ ЮЗЕРА (базовые атрибуты, слоты, стеки) ---------
    _LORE_FLAVOR = set(_LORE_LINES)
    _lstat = {"items": 0, "lines": 0, "flavor": 0}

    def _check_item(item, cc, where):
        if not isinstance(cc, dict):
            return
        item = item or "?"
        am = cc.get("minecraft:attribute_modifiers")
        if isinstance(am, list) and am:
            # (1) базовые модификаторы - ПРЕФИКС списка
            base = _BASE_ATTRS.get(item) or []
            bslot = _base_attr_slot(item)
            for i, (at, amt) in enumerate(base):
                m = am[i] if i < len(am) else None
                if not (isinstance(m, dict) and m.get("type") == at
                        and m.get("amount") == amt
                        and m.get("slot") == bslot
                        and m.get("operation") == "add_value"):
                    viol.append("базовые атрибуты: %s -> %s" % (where, item))
                    break
            # (2) слоты
            eq = cc.get("minecraft:equippable")
            eqs = eq.get("slot") if isinstance(eq, dict) else None
            van = _VANILLA_EQUIP.get(item)
            for m in am:
                if not isinstance(m, dict):
                    continue
                s = m.get("slot", "any")
                if s in ("any", "mainhand", "offhand", "hand"):
                    continue
                if not (eqs == s or van == s or
                        (s == "armor" and (eqs in ("head", "chest", "legs",
                                                   "feet", "body")
                                           or van in ("head", "chest",
                                                      "legs", "feet", "body")))):
                    viol.append("слот атрибута: %s -> %s %s"
                                % (where, item, s))
        # (7) max_stack_size: 65..99, не damageable, >=2 других компонента
        mss = cc.get("minecraft:max_stack_size")
        if mss is not None:
            others = len([k for k in cc if k not in (
                "minecraft:max_stack_size", "minecraft:custom_name",
                "minecraft:lore", "minecraft:item_name")])
            if not (isinstance(mss, int) and 65 <= mss <= 99
                    and item not in _DAMAGEABLE
                    and "minecraft:max_damage" not in cc
                    and others >= 2):
                viol.append("max_stack_size: %s -> %s %r"
                            % (where, item, mss))
        # (3/6) equippable: asset_id - только ванильный волчьи;
        # camera_overlay - нигде; компонент stackable - никогда
        eq = cc.get("minecraft:equippable")
        if isinstance(eq, dict) and "asset_id" in eq:
            if item != "minecraft:wolf_armor" \
                    or eq["asset_id"] != "minecraft:wolf":
                viol.append("asset_id: %s -> %s" % (where, item))
        if "minecraft:stackable" in cc:
            viol.append("компонент stackable: %s -> %s" % (where, item))
        if "camera_overlay" in cc:
            viol.append("camera_overlay: %s -> %s" % (where, item))
        # (3) упоминания trim в именах/lore запрещены
        for key in ("minecraft:custom_name", "minecraft:item_name"):
            tcomp = cc.get(key)
            if isinstance(tcomp, dict) \
                    and "кайм" in str(tcomp.get("text", "")).lower():
                viol.append("trim в имени: %s -> %s" % (where, item))
        # (5) lore: у предмета >=1 компонентная строка; считаем долю
        lore = cc.get("minecraft:lore")
        if isinstance(lore, list) and lore:
            _lstat["items"] += 1
            has_real = False
            for ln in lore:
                txt = ln.get("text", "") if isinstance(ln, dict) else ""
                _lstat["lines"] += 1
                if txt in _LORE_FLAVOR:
                    _lstat["flavor"] += 1
                else:
                    has_real = True
                if "кайм" in txt.lower():
                    viol.append("trim в lore: %s -> %s" % (where, item))
            if not has_real:
                viol.append("lore без компонентов: %s -> %s" % (where, item))

    def _check_node(node, item, where):
        """Обход ВСЕГО JSON с отслеживанием текущего предмета: записи
        (type=item, name), вложенные стеки ({id, count}), NBT мобов
        (equipment) - компоненты проверяются и в set_components-функциях
        записей, и в components стеков."""
        if isinstance(node, dict):
            if node.get("type") == "minecraft:item" \
                    and isinstance(node.get("name"), str):
                item = node["name"]
            if isinstance(node.get("id"), str) and "count" in node:
                item = node["id"]
            for f in node.get("functions") or []:
                if isinstance(f, dict) \
                        and f.get("function") == "minecraft:set_components":
                    _check_item(item, f.get("components"), where)
            _check_item(item, node.get("components"), where)
            if "camera_overlay" in node:
                viol.append("camera_overlay: %s" % where)
            for k, v in node.items():
                _check_node(v, item, where + "/" + k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                _check_node(v, item, "%s[%d]" % (where, i))

    for tid, t in tabs.items():
        _check_node(t, None, tid)

    # ---- явный API set_ench_summaries (по образцу set_custom_enchants):
    # передаём сведения явно (а не автопоиском по LAST_ENCHANTMENTS) и
    # проверяем, что lore-подсказки работают и на этом пути; отдельный
    # маленький прогон другим сидом
    import gen_enchantments as _ge
    set_ench_summaries({
        eid: {"name": _er["enchantments"][eid]["description"]["text"],
              "desc": _ge.summarize_enchantment(_er["enchantments"][eid]),
              "passive": eid in _passive_ids}
        for eid in _ench_ids})
    out2 = rand_loot(_random.Random(4242), "rndim", "testdim2", count=25)
    _api_items = _api_hints = 0
    for tid, t in out2["loot_tables"].items():
        for _pool, e in _walk_entries(t):
            if e.get("type") != "minecraft:item":
                continue
            fns = [f for f in (e.get("functions") or [])
                   if isinstance(f, dict)]
            cs = {}
            for f in fns:
                if f.get("function") == "minecraft:set_components":
                    cs.update(f.get("components") or {})
            cids = _custom_ench_ids(cs, fns)
            if cids:
                _api_items += 1
            for cid in set(cids):
                if not _has_hint(cs.get("minecraft:lore") or [], cid):
                    viol.append("API set_ench_summaries: нет подсказки "
                                "%s (%s)" % (cid, tid))
                else:
                    _api_hints += 1
    if verbose:
        print("явный API set_ench_summaries: %d таблиц, предметов с кастомными "
              "чарами %d, подсказок %d"
              % (len(out2["loot_tables"]), _api_items, _api_hints))

    # (5) покрытие имён-раскрытий (счётчик ведёт _reveal_name)
    if _REVEAL_STATS["named"]:
        cov = _REVEAL_STATS["seeded"] / _REVEAL_STATS["named"]
        if verbose:
            print("имён-раскрытий: %d/%d (%.0f%%; инвариант: >=95%%)"
                  % (_REVEAL_STATS["seeded"], _REVEAL_STATS["named"],
                     100.0 * cov))
        if cov < 0.95:
            viol.append("покрытие имён-раскрытий < 95%%: %.0f%%"
                        % (100.0 * cov))
    if _lstat["items"]:
        share = 1.0 - _lstat["flavor"] / max(1, _lstat["lines"])
        if verbose:
            print("lore: предметов %d, строк %d, компонентных %.0f%% "
                  "(инвариант: >=80%% и >=1 на предмет)"
                  % (_lstat["items"], _lstat["lines"], 100.0 * share))
        if share < 0.8:
            viol.append("lore: компонентных строк < 80%% (%.0f%%)"
                        % (100.0 * share))
    elif verbose:
        print("lore: не сгенерирован")

    if verbose:
        if viol:
            print("ОШИБКИ ИНВАРИАНТОВ (%d):" % len(viol))
            for v in viol[:10]:
                print("  " + v)
        else:
            print("OK: капы (пулы <= %d, rolls <= %s, bonus_rolls <= %s, "
                  "вложенные таблицы <= %d и глубина <= 1, mob: 1-2 пула / "
                  "rolls 1-2 / <= %d предметов / лёгкие компоненты), "
                  "пустых контейнеров нет (гарантийный пул + симуляция), "
                  "зачарования только на совместимых предметах, "
                  "контексты таблиц чисты, alternatives без недостижимых "
                  "детей, вложенные стеки валидны (стек-1/count, "
                  "damageable/stack), базовые атрибуты на месте, слоты "
                  "атрибутов валидны, запрещённые ключи отсутствуют, "
                  "asset_id не рандомится, max_stack_size только 65-99, "
                  "имена и lore раскрывают компоненты, «только визуал» = 0, "
                  "кастомные зачарования с подсказками, тиры пулов/роллов "
                  "по типам таблиц, use_remainder только count 1"
                  % (CAP_MAX_POOLS, _fmt_num(CAP_MAX_ROLLS),
                     _fmt_num(CAP_MAX_BONUS), CAP_NESTED_PER_TABLE,
                     CAP_MAX_ITEMS_MOB))
    return viol, tabs


if __name__ == "__main__":
    import io as _io
    import json as _json
    import sys as _sys
    from contextlib import redirect_stdout as _redirect_stdout

    _args = _sys.argv[1:]
    _do_check = "--check" in _args
    _do_print = "--print" in _args
    _seed = 20260911
    _n = None
    _i = 0
    while _i < len(_args):
        _a = _args[_i]
        if _a == "--seed":
            _i += 1
            if _i >= len(_args):
                print("--seed требует число")
                raise SystemExit(2)
            _seed = int(_args[_i])
        elif _a in ("--check", "--print"):
            pass
        elif _a.startswith("--"):
            print("неизвестный флаг: %s" % _a)
            print("использование: gen_loot.py [N] [--check] [--print] "
                  "[--seed S]")
            raise SystemExit(2)
        else:
            _n = int(_a)
        _i += 1

    if _do_print:
        # печать JSON таблиц ( сид по умолчанию 777) + тихая батарея
        if _seed == 20260911:
            _seed = 777
        _n = _n or 6
        _viol, _tabs = _run_selftest(_n, _seed, verbose=False)
        print("# %d лут-таблиц, сид %d (инварианты: %s)"
              % (len(_tabs), _seed,
                 "OK" if not _viol else "ОШИБКИ: %d" % len(_viol)))
        for _tid in _tabs:
            print("# ---- %s" % _tid)
            print(_json.dumps(_tabs[_tid], ensure_ascii=False, indent=1))
        if _viol:
            for _v in _viol[:10]:
                print("# ОШИБКА: %s" % _v, file=_sys.stderr)
            raise SystemExit(1)
        raise SystemExit(0)

    if _do_check:
        # мульти-сидовая батарея инвариантов (тихие прогоны + один большой)
        _seeds = [20260911, 1, 7, 42, 777, 1234, 31337]
        _bad = 0
        for _sd in _seeds:
            _sink = _io.StringIO()
            with _redirect_stdout(_sink):
                _viol, _tabs = _run_selftest(80, _sd, verbose=False)
            if _viol:
                _bad += 1
                print("сид %d: ОШИБКИ (%d):" % (_sd, len(_viol)))
                for _v in _viol[:5]:
                    print("  " + _v)
            else:
                print("сид %d: OK (80 таблиц, все инварианты)" % _sd)
        _sink = _io.StringIO()
        with _redirect_stdout(_sink):
            _viol, _tabs = _run_selftest(500, 20260911, verbose=False)
        if _viol:
            _bad += 1
            print("сид 20260911 x500: ОШИБКИ (%d):" % len(_viol))
            for _v in _viol[:5]:
                print("  " + _v)
        else:
            print("сид 20260911 x500: OK (500 таблиц, все инварианты)")
        if _bad:
            print("--check: ПРОВАЛ (%d прогонов с ошибками)" % _bad)
            raise SystemExit(1)
        print("--check: OK - %d сидов x 80 таблиц + 500 таблиц, все "
              "инварианты зелёные (капы, пустые контейнеры, совместимость "
              "зачарований, контексты, вложенные стеки, тиры, "
              "имена/lore/остатки)" % len(_seeds))
        raise SystemExit(0)

    # обычный запуск: подробный самотест на N таблиц (умолчание 100)
    _n = _n or 100
    _viol, _tabs = _run_selftest(_n, _seed, verbose=True)
    if _viol:
        raise SystemExit(1)
