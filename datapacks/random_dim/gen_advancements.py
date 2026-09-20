#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_advancements.py - генератор ДОСТИЖЕНИЙ-ТЕЛЕПОРТОВ для Minecraft 26.2
(pack_format 107). Формат каждого JSON сверен с ванильным jar 26.2
(minecraft-26.2-client.jar: data/minecraft/advancement/*.json) и байткодом
классов net/minecraft/advancements/triggers/* и .../predicates/*.

Модуль импортируется главным скриптом (generate_dimension.py) и сам ничего
не пишет на диск - только ВОЗВРАЩАЕТ dict'ы:

    rand_advancements(rng, ns, name, default_block, tp_y, data_root,
                      loot_ids=None, prev_dim=None, prev_ctx=None)
        -> {
            "advancements": {id: json},   # data/<ns>/advancement/<путь>.json
            "functions":   {fname: text}, # data/<ns>/function/<fname>.mcfunction
            "trigger":     "<id> + ...", # триггеры групп (= шагов) через « + »
            "hint":        "<текст>",   # подсказка (= description видимой)
            "parent":      "<id>",      # родитель видимой ачивки (цепочка)
            "n_steps":     <int>,        # число шагов пути
            "step_titles": ["Шаг 1 из N: ...", ...],
            "expansions":  ["пул", ...], # пулы, расширенные до ванильных
           }

    prev_dim - имя ПРЕДЫДУЩЕГО измерения ЦЕПОЧКИ (None = первое; родитель
               видимой ачивки = ачивка prev-измерения, а пулы критериев
               фильтруются по доступности его мира). generate_dimension
               пишет измерения на диск последовательно и знает порядок.
    prev_ctx - ГОТОВЫЙ контекст доступности prev-мира (см. read_prev_
               context); если не передан - читается с диска по prev_dim.
    Оба параметра опциональны: старые вызовы работают (prev_dim=None -
    первое измерение цепочки / хвост дерева с диска, без фильтров пулов).

Система на КАЖДОЕ измерение (вкладка достижений; ДЕРЕВО = ЦЕПОЧКА:
новая ачивка - ребёнок ПРЕДЫДУЩЕГО сгенерированного измерения, первое -
ребёнок root; ПРОГРЕСС = ШАГИ: у каждой ачивки измерения видны дети-шаги,
выполненные светятся - сколько условий из всех выполнено):
  <ns>:adv/root      корневая ачивка вкладки - одна на весь датапак, без
                     parent, с display + background; создаётся при первом
                     измерении и не пересоздаётся
  <ns>:adv/<name>    ВИДИМАЯ ачивка измерения: trigger minecraft:impossible
                     (никогда не срабатывает сама - выдаётся только
                     reward-функцией телепорта). Иконка - default_block
                     измерения, title содержит имя измерения, frame
                     случайный, description - загадка-присказка всех
                     условий + «- путь из N шагов». Parent - ачивка
                     ПРЕДЫДУЩЕГО измерения цепочки (prev_dim; None -
                     цепочка с диска либо root). Дети: шаги (прогресс),
                     заглушка _show и - у не-последнего измерения -
                     ачивка следующего измерения цепочки
  <ns>:adv/<name>_tp СКРЫТАЯ ачивка (без display): критерии c0..cN-1 -
                     DUMMY (trigger minecraft:impossible, БЕЗ условий) -
                     выдаются ТОЛЬКО командой `advancement grant @s only
                     <ns>:adv/<name>_tp c<i>` из reward-функций ШАГОВ;
                     requirements_matrix прежняя (2-4 группы, OR внутри
                     группы - все члены группы грантуются вместе). Когда
                     ВСЕ шаги выполнены -> все c<i> грантованы -> скрытая
                     завершается -> срабатывает rewards.function (телепорт)
  <ns>:adv/<name>_step<i>  ВИДИМЫЙ ШАГ (по одному на группу критериев):
                     parent = видимая ачивка измерения; criteria =
                     РЕАЛЬНЫЙ триггер + условия (перенесены сюда из
                     скрытой - dummy-критерий условий не проверяет),
                     включая «не в этом измерении»; display: icon -
                     предмет/блок из условий (мгновенно читается) либо
                     случайный из ROOT_ICONS/PLACEABLE_BLOCKS, title
                     «Шаг <i+1> из <N>: <слово-намёк>» (_STEP_WORDS),
                     description - ЗАГАДКА этого условия (та же
                     _hint_for), show_toast=True - тост объявляет номер;
                     rewards.function = <ns>:<name>_step<i>, которая
                     грантит все c<idx> своей группы + actionbar «<ИмяМира>:
                     шаг <i+1> из <N> открыт» + звук. Выполненные шаги
                     светятся под ачивкой измерения = ПРОГРЕСС (ваниль
                     не умеет прогресс-бар в одной ачивке - это компромисс
                     юзера); после телепорта шаги НЕ отзываются -
                     визуальный рекорд пройденного пути
  <ns>:<name>_tp     mcfunction (каталог function в единственном числе):
                     снять скрытую (advancement revoke only сбрасывает
                     прогресс ВСЕХ критериев - мульти-триггер возможен),
                     выдать видимую, телепорт на tp_y, сопротивление 5 ур.
                     на 30 сек, случайный звук (шаги при этом остаются)
  <ns>:<name>_step<i> mcfunction шага: grant критериев группы скрытой +
                     actionbar с номером шага + случайный звук
  <ns>:adv/<name>_show ЗАГЛУШКА ВИДИМОСТИ (без display - в меню не видна):
                     единственный критерий minecraft:tick, parent = id
                     видимой ачивки этого измерения. По декомпиляции 26.2
                     (net.minecraft.server.advancements.
                     AdvancementVisibilityEvaluator) видимость узла =
                     «есть прогресс» ИЛИ «кто-то из детей виден» (правило
                     SHOW всплывает вверх по цепочке), причём выполненный
                     ребёнок делает родителя видимым ДАЖЕ если у ребёнка
                     нет display. Корень вкладки (adv/root) имеет trigger
                     minecraft:impossible и сам никогда не выполняется,
                     дети до первой заработанной ачивки тоже - без
                     заглушки вся вкладка невидима. Заглушка выполняется
                     сама в первый же тик и «подсвечивает» цепочку
                     _show -> видимая -> ... -> adv/root. Осознанный
                     выбор триггера tick (а не advancement grant в
                     load-функции): load срабатывает один раз на
                     перезагрузку пака и НЕ покрывает игроков, зашедших
                     на сервер позже, а tick самовыполняется для КАЖДОГО
                     игрока (в т.ч. поздних). rewards/display/requirements
                     отсутствуют: одного критерия requirements не нужны,
                     узел ни на что не влияет, кроме видимости вкладки.
                     Имя файла <name>_show.json совместимо с
                     cleanup_dimension (удаляется по префиксу <name>_).

Дерево вкладки = ЦЕПОЧКА достижимости (фидбек юзера: «условия попадания
в каждое СЛЕДУЮЩЕЕ измерение должны быть 100% достижимы из ПРЕДЫДУЩЕГО»):
новая видимая ачивка - ребёнок ПРЕДЫДУЩЕГО сгенерированного измерения
(prev_dim от generate_dimension, пишущего миры на диск последовательно;
первое измерение - ребёнок root). При prev_dim=None хвост цепочки
читается с диска (chain_tail: самый глубокий лист дерева видимых ачивок
- перегенерация середины оставляет осиротевшие ветки, они корректно
игнорируются). Инвариант «у узла <= 2 видимых детей» сохраняется - НО
ачивки-ШАГИ (суффикс _step<i>) из подсчёта ИСКЛЮЧЕНЫ: они - прогресс-узлы
своего измерения, а не узлы цепочки (read_adv_tree их не возвращает).

НЕЗАВИСИМОСТЬ условий (фидбек юзера: «сделать 2-3 вещи не одновременно,
а в любое время»): доп. player-предикаты (эффект / предмет в руке /
верхом), требовавшие ОДНОВРЕМЕННОСТИ с событием триггера, УДАЛЕНЫ
полностью (_extra_player_cond больше нет). Каждый критерий - отдельная
самостоятельная задача, выполняемая когда угодно; внутренние условия
триггера (например fall_after_explosion: взрыв + падение) - ОДНО
действие и остаются.

ЦЕПОЧКА ДОСТИЖИМОСТИ: если prev_dim задан, rand_advancements читает
с диска данные prev-мира (read_prev_context) и строит множества
доступности - TERRAIN (блоки surface_rule/default_block/фич/процессоров:
все Name-строки worldgen JSON prev), MOBS (сущности спавнеров биомов +
trial_spawner'ов), ITEMS (предмети лут-таблиц: name/id в entries и
вложенных), EGGS (спавн-яйца из ITEMS - яйцо даёт моба!), POTIONS /
POTION_EFFECTS (potion_contents.potion / custom_effects). Пулы критериев
фильтруются (_avail_from_ctx): блоки ? TERRAIN ? ITEMS, сущности ?
MOBS ? EGGS, предметы ? ITEMS ? TERRAIN(блочные), зелья/эффекты - из
potion_contents prev, сундучные таблицы - ТОЛЬКО таблицы prev-измерения
(его структуры). Пул, опустевший после фильтра, расширяется до
полного ванильного и ЖУРНАЛИРУЕТСЯ (result["expansions"], самотест
печатает) - условие обязано существовать, а факт расширения виден.
prev_dim=None (первое измерение) - без фильтров: текущие пулы и так
ванильно-оверворлдные.

Формат 26.2 (сверено по jar и сгенерированным reports сервера):
  * icon: {"id": "minecraft:stone"} - НОВЫЙ формат (старого "item" больше нет)
  * predicate типа сущности: {"minecraft:entity_type": "minecraft:creeper"} -
    ключи с namespace (старое "type" не работает)
  * условие «не в измерении»: conditions.player += [{"condition":
    "minecraft:inverted", "term": {"condition": "minecraft:location_check",
    "predicate": {"dimension": "<ns>:<dim>"}}}] - LocationPredicate имеет
    поле dimension (байткод), vanilla nether/distract_piglin.json
    использует exactly такой inverted+term
  * rewards: {"function": "<ns>:<fname>"} (поле function - AdvancementRewards)
  * frame: task | goal | challenge; фон вкладки - текстура
    minecraft:gui/advancements/backgrounds/{adventure,end,husbandry,
    nether,stone} (в jar 26.2 ровно эти 5)
  * триггеры - сверены с CriteriaTriggers.class КЛИЕНТСКОГО и СЕРВЕРНОГО
    jar (совпадают); у каждого SimpleInstance есть Optional player
  * звуки: sounds.json в jar 26.2 больше НЕТ - реестр sound_event кодовый;
    пул _SOUND_POOL извлечён из SoundEvents.class клиентского jar (все
    события есть и в реестре сервера - проверено по generated/reports)
"""

import glob
import gzip
import json
import os
import random
import re
import struct

# ---------------------------------------------------------------------------
# Проверенные пулы данных (всё сверено с реестрами сервера 26.2 из
# generated/reports/registries.json: entity_type / item / mob_effect / potion)
# ---------------------------------------------------------------------------

# Мобы для player_killed_entity (безопасное подмножество
# entity_type; killer_bunny и прочие «lang-only» варианты не включаем)
MOBS = [
    "minecraft:zombie", "minecraft:skeleton", "minecraft:creeper",
    "minecraft:spider", "minecraft:zombie_villager", "minecraft:husk",
    "minecraft:stray", "minecraft:drowned", "minecraft:slime",
    "minecraft:enderman", "minecraft:cave_spider", "minecraft:witch",
    "minecraft:zombified_piglin", "minecraft:magma_cube",
    "minecraft:silverfish", "minecraft:endermite", "minecraft:blaze",
    "minecraft:ghast", "minecraft:piglin", "minecraft:hoglin",
    "minecraft:bogged", "minecraft:phantom", "minecraft:guardian",
    "minecraft:wither_skeleton", "minecraft:piglin_brute",
    "minecraft:shulker", "minecraft:creaking", "minecraft:parched",
    "minecraft:sulfur_cube", "minecraft:breeze", "minecraft:ravager",
    "minecraft:evoker", "minecraft:vindicator", "minecraft:pillager",
    "minecraft:vex", "minecraft:zoglin", "minecraft:cow", "minecraft:pig",
    "minecraft:sheep", "minecraft:chicken", "minecraft:horse",
    "minecraft:rabbit", "minecraft:fox", "minecraft:wolf", "minecraft:goat",
    "minecraft:llama", "minecraft:mooshroom", "minecraft:cat", "minecraft:panda",
    "minecraft:polar_bear", "minecraft:turtle", "minecraft:bee",
    "minecraft:armadillo", "minecraft:camel", "minecraft:frog",
    "minecraft:strider", "minecraft:villager", "minecraft:sniffer",
    "minecraft:allay", "minecraft:bat", "minecraft:squid",
    "minecraft:glow_squid", "minecraft:axolotl", "minecraft:dolphin",
]

# Приручаемые (tame_animal): только те, кого реально можно приручить
TAMEABLE = ["minecraft:cat", "minecraft:wolf", "minecraft:parrot",
            "minecraft:horse", "minecraft:donkey", "minecraft:mule",
            "minecraft:llama"]

# Верховые для started_riding (minecraft:vehicle в player-predicate).
# minecraft:zombie_horse УДАЛЁН по аудиту достижимости 26.2: зомби-лошади
# не спавнятся естественно и недоступны в выживании (только команды/
# креатив) - критерий «прокатись на зомби-лошади» был бы недостижим.
# skeleton_horse ОСТАВЛЕН: в изолированном наборе миров гроз нет
# (lightning_strike в REMOVED_TRIGGERS), но SKELETON_HORSE_SPAWN_EGG
# существует в реестре предметов 26.2 (проверено по Items.class) -
# дикий тир лута выдаёт все предметы, лошадь-скелет добывается яйцом.
VEHICLES = ["minecraft:horse", "minecraft:pig", "minecraft:strider",
            "minecraft:camel", "minecraft:donkey", "minecraft:mule",
            "minecraft:skeleton_horse", "#minecraft:boat"]

# Еда для consume_item (можно съесть/выпить)
FOODS = [
    "minecraft:bread", "minecraft:apple", "minecraft:golden_apple",
    "minecraft:enchanted_golden_apple", "minecraft:cooked_beef",
    "minecraft:cooked_porkchop", "minecraft:cooked_chicken",
    "minecraft:cooked_mutton", "minecraft:cooked_rabbit",
    "minecraft:cooked_cod", "minecraft:cooked_salmon",
    "minecraft:baked_potato", "minecraft:carrot", "minecraft:potato",
    "minecraft:beetroot", "minecraft:melon_slice",
    "minecraft:sweet_berries", "minecraft:glow_berries", "minecraft:cookie",
    # minecraft:cake УДАЛЁН: consume_item срабатывает только на предмет,
    # съедобный «из руки», а торт ставится блоком и откусывается уже
    # установленным (ванильный balanced_diet его тоже не содержит)
    "minecraft:pumpkin_pie", "minecraft:honey_bottle",
    "minecraft:milk_bucket", "minecraft:mushroom_stew",
    "minecraft:rabbit_stew", "minecraft:beetroot_soup",
    "minecraft:suspicious_stew", "minecraft:dried_kelp",
    "minecraft:rotten_flesh", "minecraft:spider_eye",
    "minecraft:chorus_fruit", "minecraft:poisonous_potato",
    "minecraft:pufferfish", "minecraft:tropical_fish",
    "minecraft:golden_carrot",
]

# Предметы для inventory_changed («заполучи что-то особенное»)
NOTABLE_ITEMS = [
    "minecraft:diamond", "minecraft:emerald", "minecraft:gold_ingot",
    "minecraft:iron_ingot", "minecraft:copper_ingot",
    "minecraft:netherite_ingot", "minecraft:coal", "minecraft:redstone",
    "minecraft:lapis_lazuli", "minecraft:quartz", "minecraft:amethyst_shard",
    "minecraft:echo_shard", "minecraft:ender_pearl", "minecraft:ender_eye",
    "minecraft:blaze_rod", "minecraft:ghast_tear", "minecraft:nether_star",
    "minecraft:heart_of_the_sea", "minecraft:totem_of_undying",
    "minecraft:elytra", "minecraft:dragon_egg",
    "minecraft:experience_bottle", "minecraft:saddle", "minecraft:name_tag",
    "minecraft:bone", "minecraft:string", "minecraft:gunpowder",
    "minecraft:slime_ball", "minecraft:leather", "minecraft:feather",
    "minecraft:paper", "minecraft:book", "minecraft:brick",
    "minecraft:nether_brick", "minecraft:clay_ball", "minecraft:wheat",
    "minecraft:sugar", "minecraft:egg", "minecraft:flint", "minecraft:stick",
    "minecraft:torch", "minecraft:lantern", "minecraft:compass",
    "minecraft:clock", "minecraft:map", "minecraft:shears",
    "minecraft:flint_and_steel", "minecraft:fishing_rod", "minecraft:bow",
    "minecraft:arrow", "minecraft:shield", "minecraft:bucket",
    "minecraft:glass_bottle", "minecraft:snowball",
] + FOODS

# Эффекты для effects_changed (реестр mob_effect). Аудит 26.2 (jar): luck,
# unluck и health_boost упоминаются ТОЛЬКО в MobEffects (реестре) - ни один
# предмет/еда/маяк/зелье их не выдаёт (luck-зелье добывается только
# командами, см. POTIONS) - для выживания эти эффекты недостижимы и
# отравили бы И effects_changed, И _extra_player_cond.
EFFECTS = [
    "minecraft:absorption", "minecraft:bad_omen", "minecraft:blindness",
    "minecraft:conduit_power", "minecraft:darkness",
    "minecraft:dolphins_grace", "minecraft:fire_resistance",
    "minecraft:glowing", "minecraft:haste",
    # minecraft:hero_of_the_village УДАЛЁН (фидбек юзера): эффект даётся
    # только за победу над рейдом, а рейды бывают лишь в деревнях
    # обычного мира - в изолированном наборе кастомных миров недостижим
    "minecraft:hunger",
    "minecraft:invisibility", "minecraft:jump_boost",
    "minecraft:levitation", "minecraft:mining_fatigue",
    "minecraft:nausea", "minecraft:night_vision", "minecraft:poison",
    "minecraft:regeneration", "minecraft:resistance",
    "minecraft:saturation", "minecraft:slow_falling", "minecraft:slowness",
    "minecraft:speed", "minecraft:strength",
    "minecraft:water_breathing", "minecraft:weakness", "minecraft:wither",
    "minecraft:infested", "minecraft:oozing", "minecraft:weaving",
    "minecraft:wind_charged",
]

# Зелья для brewed_potion (реестр potion, базовые варианты без strong_/long_).
# minecraft:luck УДАЛЁН по аудиту jar 26.2: PotionBrewing не содержит ни
# одного микса на Potions.LUCK, лут/торговля его не выдают - зелье удачи
# добывается только командами, критерий с ним никогда бы не сработал.
# water/mundane/thick/awkward остаются: их достают из варочной стойки
# (в т.ч. как splash-варианты через порох).
POTIONS = [
    "minecraft:awkward", "minecraft:fire_resistance", "minecraft:harming",
    "minecraft:healing", "minecraft:infested", "minecraft:invisibility",
    "minecraft:leaping", "minecraft:mundane",
    "minecraft:night_vision", "minecraft:oozing", "minecraft:poison",
    "minecraft:regeneration", "minecraft:slow_falling", "minecraft:slowness",
    "minecraft:strength", "minecraft:swiftness", "minecraft:thick",
    "minecraft:turtle_master", "minecraft:water",
    "minecraft:water_breathing", "minecraft:weakness", "minecraft:weaving",
    "minecraft:wind_charged",
]

# Ведра для filled_bucket
BUCKETS = [
    "minecraft:water_bucket", "minecraft:lava_bucket", "minecraft:milk_bucket",
    "minecraft:powder_snow_bucket", "minecraft:axolotl_bucket",
    "minecraft:cod_bucket", "minecraft:salmon_bucket",
    "minecraft:pufferfish_bucket", "minecraft:tropical_fish_bucket",
    "minecraft:tadpole_bucket",
]

# Предметы для зачарования (enchanted_item)
ENCHANTABLES = [
    "minecraft:book", "minecraft:diamond_sword", "minecraft:diamond_pickaxe",
    "minecraft:iron_sword", "minecraft:iron_pickaxe", "minecraft:bow",
    "minecraft:crossbow", "minecraft:fishing_rod", "minecraft:trident",
    "minecraft:diamond_helmet", "minecraft:diamond_chestplate",
    "minecraft:diamond_leggings", "minecraft:diamond_boots",
    "minecraft:netherite_sword", "minecraft:golden_axe",
]

# Блоки для placed_block / allay_drop_item_on_block - только имеющие форму
# предмета (иначе игрок не сможет их взять в руку и поставить)
PLACEABLE_BLOCKS = [
    "minecraft:stone", "minecraft:cobblestone", "minecraft:granite",
    "minecraft:diorite", "minecraft:andesite", "minecraft:deepslate",
    "minecraft:tuff", "minecraft:calcite", "minecraft:dirt",
    "minecraft:coarse_dirt", "minecraft:rooted_dirt", "minecraft:mud",
    "minecraft:packed_mud", "minecraft:mud_bricks", "minecraft:sand",
    "minecraft:red_sand", "minecraft:gravel", "minecraft:clay",
    "minecraft:sandstone", "minecraft:red_sandstone", "minecraft:bricks",
    "minecraft:nether_bricks", "minecraft:red_nether_bricks",
    "minecraft:stone_bricks", "minecraft:mossy_stone_bricks",
    "minecraft:deepslate_bricks", "minecraft:deepslate_tiles",
    "minecraft:tuff_bricks", "minecraft:polished_deepslate",
    "minecraft:polished_blackstone", "minecraft:polished_granite",
    "minecraft:polished_diorite", "minecraft:polished_andesite",
    "minecraft:polished_tuff", "minecraft:smooth_stone",
    "minecraft:obsidian", "minecraft:crying_obsidian", "minecraft:netherrack",
    "minecraft:end_stone", "minecraft:end_stone_bricks", "minecraft:basalt",
    "minecraft:blackstone", "minecraft:quartz_block", "minecraft:purpur_block",
    "minecraft:prismarine", "minecraft:prismarine_bricks",
    "minecraft:dark_prismarine", "minecraft:terracotta",
    "minecraft:quartz_bricks", "minecraft:amethyst_block",
    "minecraft:copper_block", "minecraft:iron_block", "minecraft:gold_block",
    "minecraft:diamond_block", "minecraft:emerald_block",
    "minecraft:lapis_block", "minecraft:redstone_block",
    "minecraft:coal_block", "minecraft:netherite_block",
    "minecraft:glowstone", "minecraft:shroomlight", "minecraft:sea_lantern",
    "minecraft:magma_block", "minecraft:melon", "minecraft:pumpkin",
    "minecraft:carved_pumpkin", "minecraft:jack_o_lantern",
    "minecraft:hay_block", "minecraft:bone_block", "minecraft:slime_block",
    "minecraft:honey_block", "minecraft:honeycomb_block",
    "minecraft:dried_kelp_block", "minecraft:sponge", "minecraft:wet_sponge",
    "minecraft:moss_block", "minecraft:sculk", "minecraft:dripstone_block",
    "minecraft:ice", "minecraft:packed_ice", "minecraft:blue_ice",
    "minecraft:snow_block", "minecraft:soul_sand", "minecraft:soul_soil",
    "minecraft:mycelium", "minecraft:podzol", "minecraft:grass_block",
    "minecraft:oak_planks", "minecraft:spruce_planks",
    "minecraft:birch_planks", "minecraft:jungle_planks",
    "minecraft:acacia_planks", "minecraft:dark_oak_planks",
    "minecraft:mangrove_planks", "minecraft:cherry_planks",
    "minecraft:pale_oak_planks", "minecraft:bamboo_planks",
    "minecraft:bamboo_mosaic", "minecraft:crimson_planks",
    "minecraft:warped_planks", "minecraft:oak_log", "minecraft:spruce_log",
    "minecraft:birch_log", "minecraft:glass", "minecraft:tinted_glass",
    "minecraft:crafting_table", "minecraft:furnace", "minecraft:chest",
    "minecraft:barrel", "minecraft:bookshelf", "minecraft:composter",
    "minecraft:note_block", "minecraft:jukebox", "minecraft:beacon",
    "minecraft:lodestone", "minecraft:respawn_anchor",
]

# Блоки генератора БЕЗ формы предмета (реестр item, см. mc-26-2 память):
# у noise_settings default_block может быть таким - тогда fallback-иконка
ITEMLESS_BLOCKS = {"minecraft:frosted_ice", "minecraft:powder_snow"}

# Блоки, в которые можно «войти» головой (enter_block). Ванильный формат:
# {"block": "<id>"}. Порталы Нижнего мира и шлюзы Края УДАЛЕНЫ (аудит
# достижимости 26.2 по фидбеку юзера): в изолированном наборе кастомных
# миров нет ни одного портала в другие миры - критерий с ними невыполним.
# Вода/пузырьковый столб/паутина/куст ягод/порошковый снег достижимы везде.
ENTERABLE_BLOCKS = [
    "minecraft:water", "minecraft:bubble_column", "minecraft:cobweb",
    "minecraft:sweet_berry_bush", "minecraft:powder_snow",
]

# Предметы с длительным использованием (using_item; vanilla spyglass_at_dragon)
USABLE_ITEMS = [
    "minecraft:spyglass", "minecraft:bow", "minecraft:crossbow",
    "minecraft:shield", "minecraft:trident", "minecraft:goat_horn",
    # копьё 26.2 бывает ТОЛЬКО с материалом (minecraft:spear не существует -
    # real-server: "Failed to get element minecraft:spear"); см. тег item/spears
    "minecraft:iron_spear",
]

# Что можно выудить удочкой (fishing_rod_hooked; vanilla fishy_business)
FISH_LOOT = [
    "minecraft:cod", "minecraft:salmon", "minecraft:tropical_fish",
    "minecraft:pufferfish", "minecraft:enchanted_book", "minecraft:name_tag",
    "minecraft:saddle", "minecraft:nautilus_shell", "minecraft:fishing_rod",
    "minecraft:bowl", "minecraft:stick", "minecraft:string",
    "minecraft:leather_boots", "minecraft:rotten_flesh",
]

# Скрещиваемые (bred_animals; vanilla bred_all_animals - условие «child»).
# ПОЛНЫЙ РАЦИОН РАЗВЕДЕНИЯ (аудит 26.2, фидбек юзера: еда для разведения
# должна быть ДОБЫВАЕМОЙ в изолированном наборе миров - яйца спавна из
# лута дают самих мобов, а корм берётся фермой/крафтом/лутом):
#   корова/овца/грибная корова/козёл - пшеница (ферма, лут)
#   свинья - морковь/картофель/свёкла (ферма, лут, зомби)
#   курица - семена (трава/ферма)
#   лошадь/осёл - золотая морковь/золотое яблоко (крафт из золота)
#   волк - любое мясо (гнилая плоть с зомби)
#   кошка - сырая треска/лосось (ловля/лут)
#   лама - сноп сена (крафт из пшеницы)
#   кролик - морковь/одуванчик/золотая морковь
#   лиса - сладкие/светящиеся ягоды (кусты, лут)
#   черепаха - водоросли (ножницы в воде)
#   панда - бамбук (лут/ особенности мира)
#   жаба - слизь (слизни)
#   верблюд - кактус (лут)
#   нюхач - семена факела (выкапывают сами нюхачи из земли - есть
#           яйца спавна нюхача; также дикий тир лута)
#   пчела - любой цветок (фичи-поля, лут)
#   броненосец - паучий глаз (пауки)
#   хоглин - багровый гриб (лут/фичи незер-биомов)
#   страйдер - искажённый гриб (лут/фичи)
#   аксолотль - ведро тропической рыбки (яйцо спавна + вода)
# Все корма достижимы - состав не менялся.
BREEDABLE = [
    "minecraft:cow", "minecraft:pig", "minecraft:sheep", "minecraft:chicken",
    "minecraft:horse", "minecraft:donkey", "minecraft:wolf", "minecraft:cat",
    "minecraft:llama", "minecraft:rabbit", "minecraft:fox", "minecraft:turtle",
    "minecraft:panda", "minecraft:goat", "minecraft:frog", "minecraft:camel",
    "minecraft:sniffer", "minecraft:bee", "minecraft:armadillo",
    "minecraft:hoglin", "minecraft:strider", "minecraft:mooshroom",
    "minecraft:axolotl",
]

# С кем можно взаимодействовать с предметом в руке (player_interacted_with_
# entity; vanilla brush_armadillo - entity + item)
INTERACTABLE = [
    "minecraft:villager", "minecraft:wandering_trader", "minecraft:allay",
    "minecraft:armadillo", "minecraft:wolf", "minecraft:cat", "minecraft:horse",
    "minecraft:cow", "minecraft:sheep", "minecraft:pig", "minecraft:chicken",
    "minecraft:parrot", "minecraft:fox", "minecraft:sniffer", "minecraft:goat",
    "minecraft:creeper", "minecraft:skeleton", "minecraft:zombie",
]

# Предметы с НИЗКИМ запасом прочности для item_durability_changed: условие
# «доточи до остатка <= N» должно достигаться разумным числом использований,
# поэтому алмазку/незерит (1500+) сюда не берём
WEARABLE_ITEMS = [
    "minecraft:carrot_on_a_stick", "minecraft:warped_fungus_on_a_stick",
    "minecraft:flint_and_steel", "minecraft:fishing_rod",
    "minecraft:golden_sword", "minecraft:golden_pickaxe",
    "minecraft:golden_axe", "minecraft:golden_shovel",
    "minecraft:golden_hoe", "minecraft:wooden_sword",
    "minecraft:wooden_pickaxe", "minecraft:wooden_axe",
    "minecraft:wooden_shovel", "minecraft:wooden_hoe",
]

# Источники взрыва для fall_after_explosion (vanilla who_needs_rockets -
# cause: [ent_pred wind_charge], distance.y.min)
EXPLOSION_SOURCES = ["minecraft:creeper", "minecraft:tnt",
                     "minecraft:wind_charge"]

# Сущности, которых игрок может «построить» (summoned_entity; vanilla
# summon_iron_golem). С яйцом призыва триггер тоже срабатывает.
SUMMONABLE = [
    "minecraft:iron_golem", "minecraft:snow_golem", "minecraft:wither",
    "minecraft:end_crystal",
]

# Ванильные сундучные лут-таблицы (jar 26.2, data/minecraft/loot_table/
# chests/) - ТОЛЬКО для rewards.loot скрытой ачивки (награда генерирует
# предметы напрямую, ей всё равно где находиться). Для триггера
# player_generates_container_loot они НЕ годятся: сундуки ванильных
# структур в изолированном наборе кастомных миров не встречаются -
# триггер использует НАШИ таблицы других измерений (см.
# _foreign_chest_tables).
CHEST_LOOT = [
    "chests/abandoned_mineshaft", "chests/ancient_city",
    "chests/ancient_city_ice_box", "chests/bastion_bridge",
    "chests/bastion_hoglin_stable", "chests/bastion_other",
    "chests/bastion_treasure", "chests/buried_treasure",
    "chests/desert_pyramid", "chests/end_city_treasure", "chests/igloo_chest",
    "chests/jungle_temple", "chests/nether_bridge", "chests/pillager_outpost",
    "chests/ruined_portal", "chests/shipwreck_map", "chests/shipwreck_supply",
    "chests/shipwreck_treasure", "chests/simple_dungeon",
    "chests/stronghold_corridor", "chests/stronghold_crossing",
    "chests/stronghold_library", "chests/trial_chambers/corridor",
    "chests/trial_chambers/entrance", "chests/trial_chambers/intersection",
    "chests/trial_chambers/reward", "chests/trial_chambers/reward_rare",
    "chests/trial_chambers/reward_ominous", "chests/trial_chambers/supply",
    "chests/underwater_ruin_big", "chests/underwater_ruin_small",
    "chests/village/village_armorer", "chests/village/village_butcher",
    "chests/village/village_cartographer", "chests/village/village_desert_house",
    "chests/village/village_fisher", "chests/village/village_fletcher",
    "chests/village/village_mason", "chests/village/village_plains_house",
    "chests/village/village_savanna_house", "chests/village/village_shepherd",
    "chests/village/village_snowy_house", "chests/village/village_taiga_house",
    "chests/village/village_tannery", "chests/village/village_temple",
    "chests/village/village_toolsmith", "chests/village/village_weaponsmith",
    "chests/woodland_mansion",
]

# Ванильные рецепты (отобраны вручную из 1585 jar 26.2; без камнерезных
# дублей/окраски/вощения) - для rewards.recipes
RECIPE_POOL = [
    "amethyst_block", "anvil", "armor_stand", "barrel", "beacon",
    "blast_furnace", "bookshelf", "bow", "brewing_stand", "brush", "bundle",
    "cake", "candle", "cauldron", "chest", "chest_minecart", "clock",
    "compass", "conduit", "cookie", "crossbow", "crafting_table",
    "dried_kelp_block", "enchanting_table", "ender_chest", "fishing_rod",
    "flint_and_steel", "furnace", "golden_apple", "hay_block", "hopper",
    "hopper_minecart", "jack_o_lantern", "jukebox", "lantern",
    "lightning_rod", "lodestone", "mace", "map", "minecart", "music_disc_5",
    "name_tag", "note_block", "observer", "piston", "powered_rail",
    "pumpkin_pie", "rail", "recovery_compass", "respawn_anchor", "saddle",
    "sea_lantern", "shears", "shield", "soul_lantern", "soul_torch",
    "sponge", "spyglass", "sticky_piston", "tinted_glass", "tnt",
    "tnt_minecart", "torch", "trapped_chest",
]

# Инструменты для item_used_on_block (vanilla lighten_up - location:
# [location_check block + match_tool]). Список и ПАРЫ «инструмент ->
# валидные блоки» (аудит достижимости 26.2) - см. TOOL_TARGETS ниже,
# после словарей русских имён. minecraft:brush УДАЛЁН: расчёсывание
# срабатывает только на блоках с расчёсываемой лут-таблицей, для
# поставленных блоков item_used_on_block с кистью не выполняется.

# Фолбэк-иконки для таких случаев + иконки корня («портальные» предметы)
ROOT_ICONS = [
    "minecraft:ender_eye", "minecraft:ender_pearl", "minecraft:nether_star",
    "minecraft:echo_shard", "minecraft:recovery_compass",
    "minecraft:compass", "minecraft:crying_obsidian", "minecraft:obsidian",
    "minecraft:amethyst_shard", "minecraft:chorus_fruit",
    "minecraft:lodestone", "minecraft:heart_of_the_sea",
]

# Фоны вкладки достижений (textures/gui/advancements/backgrounds/, jar 26.2)
BACKGROUNDS = [
    "minecraft:gui/advancements/backgrounds/adventure",
    "minecraft:gui/advancements/backgrounds/end",
    "minecraft:gui/advancements/backgrounds/husbandry",
    "minecraft:gui/advancements/backgrounds/nether",
    "minecraft:gui/advancements/backgrounds/stone",
]

# Красивые цвета текста заголовков (ChatFormatting)
TITLE_COLORS = ["gold", "aqua", "light_purple", "green", "yellow", "blue",
                "dark_purple", "dark_aqua", "red", "white"]

# Шаблоны названий видимых ачивок: {N} = имя измерения с заглавной буквы.
# Словарь расширен по фидбеку юзера («покажи всё величие русского языка»,
# 20 -> 66): прямые имена, дороги и пороги, зов и голоса, тень и свет,
# судьба и чудо, стихии - всё поэтично, без канцелярита
TITLE_PATTERNS = [
    # прямые имена
    "Измерение {N}", "Таинственное измерение {N}", "Древнее измерение {N}",
    "Забытое измерение {N}", "Незнакомое измерение {N}", "Чужое измерение {N}",
    # дороги, двери и пороги
    "Тропа в {N}", "Забытая тропа в {N}", "Врата в {N}", "Тёмные врата в {N}",
    "Дверь в {N}", "Калитка в {N}", "Путь в {N}", "Дорога в {N}",
    "Мост в {N}", "Лестница в {N}", "Ступень в {N}", "Шаг в {N}",
    "Окно в {N}", "Порог {N}", "Сверкающий порог {N}",
    # зов, вести и предания
    "Зов {N}", "Древний зов {N}", "Глас {N}", "Шёпот {N}", "Отголосок {N}",
    "Весть из {N}", "Гость из {N}", "Песнь о {N}", "Сказ о {N}",
    "Быль о {N}", "Легенда о {N}", "Предание о {N}", "Притча о {N}",
    "Баллада о {N}", "Небылица о {N}", "Сага о {N}", "Присказка о {N}",
    # тень, свет и времена суток
    "Тень {N}", "Сон о {N}", "Эхо {N}", "Осколок {N}", "Заря {N}",
    "Закат {N}", "Сумерки {N}", "Рассвет {N}", "Полдень {N}", "Полночь {N}",
    "Свет {N}", "Мгла {N}", "Туман {N}", "Мираж {N}", "Отражение {N}",
    "Рябь {N}", "Иней {N}", "Зола {N}",
    # судьба, тайна и чудо
    "Тайна {N}", "Загадка {N}", "Знамение {N}", "Пророчество о {N}",
    "Судьба {N}", "Доля {N}", "Удел {N}", "Наследие {N}", "Память о {N}",
    "Заклинание {N}", "Оберег {N}", "Талисман {N}", "Печать {N}",
    # стихии
    "Гроза {N}", "Ветер {N}", "Пламя {N}", "Волна {N}",
]

# Слово-намёк для ЗАГОЛОВКА ачивки-шага: «Шаг 1 из 3: Охота» -
# короткое имя задачи по её триггеру (полный список = самотест сверяет
# с TRIGGER_POOL). Описания шагов - ЗАГАДКИ условий (_hint_for),
# слово лишь намекает на ХАРАКТЕР задачи, не раскрывая её
_STEP_WORDS = {
    "minecraft:player_killed_entity": "Охота",
    "minecraft:placed_block": "Строительство",
    "minecraft:consume_item": "Трапеза",
    "minecraft:inventory_changed": "Находка",
    "minecraft:effects_changed": "Колдовство",
    "minecraft:brewed_potion": "Алхимия",
    "minecraft:slept_in_bed": "Сон",
    "minecraft:tame_animal": "Приручение",
    "minecraft:villager_trade": "Торговля",
    "minecraft:fall_from_height": "Падение",
    "minecraft:ride_entity_in_lava": "Пламя",
    "minecraft:allay_drop_item_on_block": "Поручение",
    "minecraft:entity_hurt_player": "Стойкость",
    "minecraft:levitation": "Левитация",
    "minecraft:started_riding": "Езда",
    "minecraft:used_totem": "Спасение",
    "minecraft:enchanted_item": "Зачарование",
    "minecraft:filled_bucket": "Ведро",
    "minecraft:shot_crossbow": "Выстрел",
    "minecraft:fishing_rod_hooked": "Рыбалка",
    "minecraft:target_hit": "Меткость",
    "minecraft:enter_block": "Погружение",
    "minecraft:item_durability_changed": "Износ",
    "minecraft:using_item": "Применение",
    "minecraft:item_used_on_block": "Ремесло",
    "minecraft:player_generates_container_loot": "Тайник",
    "minecraft:fall_after_explosion": "Взлёт",
    "minecraft:cured_zombie_villager": "Исцеление",
    "minecraft:summoned_entity": "Призыв",
    "minecraft:bred_animals": "Потомство",
    "minecraft:player_interacted_with_entity": "Забота",
    "minecraft:bee_nest_destroyed": "Мёд",
}

# Название/описание корневой ачивки (случайные, в стиле генератора;
# расширено по фидбеку юзера: 10 -> 34 названий, 6 -> 18 описаний)
ROOT_TITLES = [
    "Разломы мироздания",
    "Двери в неизвестность",
    "Случайные измерения",
    "За гранью мира",
    "Бесконечность миров",
    "Атлас невозможного",
    "Хроники чужих небес",
    "Колода миров",
    "Каталог случайных дверей",
    "Осколки вселенной",
    "Калейдоскоп миров",
    "Сундук с мирами",
    "Ключи от всех дверей",
    "Хоровод измерений",
    "Узоры мироздания",
    "Кружева параллелей",
    "Мельница миров",
    "Небесная мастерская",
    "Чужие поднебесья",
    "Перекрёсток вселенной",
    "Врата без замков",
    "Компас без сторон света",
    "Карта без берегов",
    "Мосты через пустоту",
    "Тропы наугад",
    "Дороги, каких нет на карте",
    "Миры нарасхват",
    "Чужие зори",
    "Незнакомые рассветы",
    "Семь дорог в никуда",
    "Тетрадь странника",
    "Верста чужих дорог",
    "Ларец чудес",
    "Лествица в невозможное",
]
ROOT_DESCS = [
    "Каждый мир открывается своим ключом. Найди его.",
    "Случайные двери в случайные миры.",
    "Миры, которых не должно было быть.",
    "Собери их все... если сможешь вернуться.",
    "Здесь живут миры, придуманные никем.",
    "Шагни - и увидишь, что выпало.",
    "Все дороги тут ведут вникуда - и обратно.",
    "Каждая дверь заперта загадкой. Отгадай.",
    "Миры рождаются из ничего и ждут гостей.",
    "Ступай - за каждым порогом новое небо.",
    "Тут водятся места, каких не найти на карте.",
    "Собери ключи от всех чужих небес.",
    "Двери открываются лишь терпеливым.",
    "Не всякая дверь ведёт домой.",
    "Мир за миром - вся вселенная в котомке.",
    "Пусть каждая тропа приведёт к новому небу.",
    "Чужие миры приветствуют смельчаков.",
    "Звёзды здесь складываются в новые дороги.",
]

# ---------------------------------------------------------------------------
# Русские имена для подсказок: имена существ/эффектов/зелий идут в
# подсказки напрямую (юзер: «существо называй как сейчас»), а конкретные
# БЛОКИ и ПРЕДМЕТЫ из условий скрыты за ЗАГАДКАМИ (RIDDLE_BLOCKS /
# RIDDLE_ITEMS ниже - по фидбеку юзера загадка должна быть ОПОЗНАВАЕМОЙ).
# Единый источник правды - conditions JSON критерия (см. _hint_for).
#   RU_ENT      id -> (именительный, винительный, родительный, творительный)
#   RU_VEHICLES id -> предложная фраза («на лошади», «в лодке»)
#   RU_ITEM     id -> {"n": именительный, "a": винительный (если != n),
#                     "i": творительный (только где нужен)}
#   RU_BLOCK    id -> {"n": именительный, "a": винительный (если != n)}
#   RU_EFFECT   id -> родительный («под эффектом скорости»)
#   RU_POTION   id -> винительная фраза («зелье огнестойкости»)
# Имена сверены с локализацией ru_ru 26.2; где официального имени ещё
# нет (новые сущности 26.2) - использованы понятные эквиваленты.
# Самотест проверяет, что КАЖДЫЙ id каждого пула имеет русское имя
# (и загадку - для блоков и предметов).
# ---------------------------------------------------------------------------

RU_ENT = {
    # id: (именительный, винительный, родительный, творительный)
    # --- враждебные ---
    "minecraft:zombie": ("зомби", "зомби", "зомби", "зомби"),
    "minecraft:skeleton": ("скелет", "скелета", "скелета", "скелетом"),
    "minecraft:creeper": ("крипер", "крипера", "крипера", "крипером"),
    "minecraft:spider": ("паук", "паука", "паука", "пауком"),
    "minecraft:zombie_villager": ("зомби-житель", "зомби-жителя",
                                   "зомби-жителя", "зомби-жителем"),
    "minecraft:husk": ("злобный зомби", "злобного зомби",
                       "злобного зомби", "злобным зомби"),
    "minecraft:stray": ("зимогор", "зимогора", "зимогора", "зимогором"),
    "minecraft:drowned": ("утопленник", "утопленника", "утопленника",
                          "утопленником"),
    "minecraft:slime": ("слизень", "слизня", "слизня", "слизнем"),
    "minecraft:enderman": ("эндермен", "эндермена", "эндермена",
                           "эндерменом"),
    "minecraft:cave_spider": ("пещерный паук", "пещерного паука",
                              "пещерного паука", "пещерным пауком"),
    "minecraft:witch": ("ведьма", "ведьму", "ведьмы", "ведьмой"),
    "minecraft:zombified_piglin": ("зомбифицированный пиглин",
                                   "зомбифицированного пиглина",
                                   "зомбифицированного пиглина",
                                   "зомбифицированным пиглином"),
    "minecraft:magma_cube": ("лавовый куб", "лавовый куб",
                             "лавового куба", "лавовым кубом"),
    "minecraft:silverfish": ("чешуйница", "чешуйницу", "чешуйницы",
                             "чешуйницей"),
    "minecraft:endermite": ("эндермит", "эндермита", "эндермита",
                            "эндермитом"),
    "minecraft:blaze": ("воспламенитель", "воспламенителя",
                        "воспламенителя", "воспламенителем"),
    "minecraft:ghast": ("гаст", "гаста", "гаста", "гастом"),
    "minecraft:piglin": ("пиглин", "пиглина", "пиглина", "пиглином"),
    "minecraft:hoglin": ("хоглин", "хоглина", "хоглина", "хоглином"),
    "minecraft:bogged": ("топляк", "топляка", "топляка", "топляком"),
    "minecraft:phantom": ("фантом", "фантома", "фантома", "фантомом"),
    "minecraft:guardian": ("страж", "стража", "стража", "стражем"),
    "minecraft:wither_skeleton": ("скелет-иссушитель",
                                  "скелета-иссушителя",
                                  "скелета-иссушителя",
                                  "скелетом-иссушителем"),
    "minecraft:piglin_brute": ("пиглин-громила", "пиглина-громилу",
                               "пиглина-громилы", "пиглином-громилой"),
    "minecraft:shulker": ("шалкер", "шалкера", "шалкера", "шалкером"),
    "minecraft:creaking": ("скрипун", "скрипуна", "скрипуна", "скрипуном"),
    "minecraft:parched": ("иссохший", "иссохшего", "иссохшего",
                          "иссохшим"),
    "minecraft:sulfur_cube": ("серный куб", "серный куб",
                              "серного куба", "серным кубом"),
    "minecraft:breeze": ("бриз", "бриза", "бриза", "бризом"),
    "minecraft:ravager": ("разоритель", "разорителя", "разорителя",
                          "разорителем"),
    "minecraft:evoker": ("призыватель", "призывателя", "призывателя",
                         "призывателем"),
    "minecraft:vindicator": ("защитник", "защитника", "защитника",
                             "защитником"),
    "minecraft:pillager": ("разбойник", "разбойника", "разбойника",
                           "разбойником"),
    "minecraft:vex": ("досаждатель", "досаждателя", "досаждателя",
                      "досаждателем"),
    "minecraft:zoglin": ("зоглин", "зоглина", "зоглина", "зоглином"),
    # --- мирные ---
    "minecraft:cow": ("корова", "корову", "коровы", "коровой"),
    "minecraft:pig": ("свинья", "свинью", "свиньи", "свиньёй"),
    "minecraft:sheep": ("овца", "овцу", "овцы", "овцой"),
    "minecraft:chicken": ("курица", "курицу", "курицы", "курицей"),
    "minecraft:horse": ("лошадь", "лошадь", "лошади", "лошадью"),
    "minecraft:donkey": ("осёл", "осла", "осла", "ослом"),
    "minecraft:mule": ("мул", "мула", "мула", "мулом"),
    "minecraft:rabbit": ("кролик", "кролика", "кролика", "кроликом"),
    "minecraft:fox": ("лиса", "лису", "лисы", "лисой"),
    "minecraft:wolf": ("волк", "волка", "волка", "волком"),
    "minecraft:goat": ("козёл", "козла", "козла", "козлом"),
    "minecraft:llama": ("лама", "ламу", "ламы", "ламой"),
    "minecraft:mooshroom": ("грибная корова", "грибную корову",
                            "грибной коровы", "грибной коровой"),
    "minecraft:cat": ("кошка", "кошку", "кошки", "кошкой"),
    "minecraft:panda": ("панда", "панду", "панды", "пандой"),
    "minecraft:polar_bear": ("полярный медведь", "полярного медведя",
                             "полярного медведя", "полярным медведем"),
    "minecraft:turtle": ("черепаха", "черепаху", "черепахи", "черепахой"),
    "minecraft:bee": ("пчела", "пчелу", "пчелы", "пчелой"),
    "minecraft:armadillo": ("броненосец", "броненосца", "броненосца",
                           "броненосцем"),
    "minecraft:camel": ("верблюд", "верблюда", "верблюда", "верблюдом"),
    "minecraft:frog": ("жаба", "жабу", "жабы", "жабой"),
    "minecraft:strider": ("страйдер", "страйдера", "страйдера",
                          "страйдером"),
    "minecraft:villager": ("житель", "жителя", "жителя", "жителем"),
    "minecraft:wandering_trader": ("странствующий торговец",
                                   "странствующего торговца",
                                   "странствующего торговца",
                                   "странствующим торговцем"),
    "minecraft:sniffer": ("нюхач", "нюхача", "нюхача", "нюхачом"),
    "minecraft:allay": ("алай", "алая", "алая", "алаем"),
    "minecraft:bat": ("летучая мышь", "летучую мышь", "летучей мыши",
                      "летучей мышью"),
    "minecraft:squid": ("спрут", "спрута", "спрута", "спрутом"),
    "minecraft:glow_squid": ("светящийся спрут", "светящегося спрута",
                             "светящегося спрута", "светящимся спрутом"),
    "minecraft:axolotl": ("аксолотль", "аксолотля", "аксолотля",
                          "аксолотлем"),
    "minecraft:dolphin": ("дельфин", "дельфина", "дельфина", "дельфином"),
    "minecraft:parrot": ("попугай", "попугая", "попугая", "попугаем"),
    "minecraft:skeleton_horse": ("лошадь-скелет", "лошадь-скелет",
                                 "лошади-скелета", "лошадью-скелетом"),
    # --- создаваемые / особые (SUMMONABLE, EXPLOSION_SOURCES) ---
    "minecraft:iron_golem": ("железный голем", "железного голема",
                             "железного голема", "железным големом"),
    "minecraft:snow_golem": ("снежный голем", "снежного голема",
                             "снежного голема", "снежным големом"),
    "minecraft:wither": ("иссушитель", "иссушителя", "иссушителя",
                         "иссушителем"),
    "minecraft:end_crystal": ("кристалл Края", "кристалл Края",
                              "кристалла Края", "кристаллом Края"),
    "minecraft:tnt": ("динамит", "динамит", "динамита", "динамитом"),
    "minecraft:wind_charge": ("заряд ветра", "заряд ветра",
                              "заряда ветра", "зарядом ветра"),
    # тег лодок (entity_type принимает теги; в VEHICLES именно тег)
    "#minecraft:boat": ("лодка", "лодку", "лодки", "лодкой"),
}

# «Верхом на X» (предложный падеж с предлогом; лодка - «в»)
RU_VEHICLES = {
    "minecraft:horse": "на лошади",
    "minecraft:pig": "на свинье",
    "minecraft:strider": "на страйдере",
    "minecraft:camel": "на верблюде",
    "minecraft:donkey": "на осле",
    "minecraft:mule": "на муле",
    "minecraft:skeleton_horse": "на лошади-скелете",
    "#minecraft:boat": "в лодке",
}

RU_ITEM = {
    # id: {"n": именительный, "a": винительный (если отличен), "i": творительный}
    # --- еда (для consume_item: «Съешь X» / «Полакомься Y» / «Выпей X») ---
    "minecraft:bread": {"n": "хлеб", "i": "хлебом"},
    "minecraft:apple": {"n": "яблоко", "i": "яблоком"},
    "minecraft:golden_apple": {"n": "золотое яблоко",
                              "i": "золотым яблоком"},
    "minecraft:enchanted_golden_apple": {"n": "зачарованное золотое яблоко",
                                        "i": "зачарованным золотым яблоком"},
    "minecraft:cooked_beef": {"n": "жареная говядина", "a": "жареную говядину",
                              "i": "жареной говядиной"},
    "minecraft:cooked_porkchop": {"n": "жареная свинина",
                                  "a": "жареную свинину",
                                  "i": "жареной свининой"},
    "minecraft:cooked_chicken": {"n": "жареная курица", "a": "жареную курицу",
                                 "i": "жареной курицей"},
    "minecraft:cooked_mutton": {"n": "жареная баранина",
                                "a": "жареную баранину",
                                "i": "жареной бараниной"},
    "minecraft:cooked_rabbit": {"n": "жареная крольчатина",
                                "a": "жареную крольчатину",
                                "i": "жареной крольчатиной"},
    "minecraft:cooked_cod": {"n": "жареная треска", "a": "жареную треску",
                             "i": "жареной треской"},
    "minecraft:cooked_salmon": {"n": "жареный лосось",
                                "i": "жареным лососем"},
    "minecraft:baked_potato": {"n": "печёный картофель",
                               "i": "печёным картофелем"},
    "minecraft:carrot": {"n": "морковь", "i": "морковью"},
    "minecraft:potato": {"n": "картофель", "i": "картофелем"},
    "minecraft:beetroot": {"n": "свёкла", "a": "свёклу", "i": "свёклой"},
    "minecraft:melon_slice": {"n": "ломтик арбуза", "i": "ломтиком арбуза"},
    "minecraft:sweet_berries": {"n": "сладкие ягоды", "i": "сладкими ягодами"},
    "minecraft:glow_berries": {"n": "светящиеся ягоды",
                               "i": "светящимися ягодами"},
    "minecraft:cookie": {"n": "печенье", "i": "печеньем"},
    "minecraft:pumpkin_pie": {"n": "тыквенный пирог",
                             "i": "тыквенным пирогом"},
    "minecraft:honey_bottle": {"n": "бутылочка мёда", "a": "бутылочку мёда",
                               "i": "бутылочкой мёда"},
    "minecraft:milk_bucket": {"n": "ведро молока", "i": "ведром молока"},
    "minecraft:mushroom_stew": {"n": "грибное рагу", "i": "грибным рагу"},
    "minecraft:rabbit_stew": {"n": "кроличье рагу", "i": "кроличьим рагу"},
    "minecraft:beetroot_soup": {"n": "свекольный суп",
                               "i": "свекольным супом"},
    "minecraft:suspicious_stew": {"n": "подозрительное рагу",
                                  "i": "подозрительным рагу"},
    "minecraft:dried_kelp": {"n": "сушёная ламинария",
                             "a": "сушёную ламинарию",
                             "i": "сушёной ламинарией"},
    "minecraft:rotten_flesh": {"n": "гнилая плоть", "a": "гнилую плоть",
                               "i": "гнилой плотью"},
    "minecraft:spider_eye": {"n": "паучий глаз", "i": "паучьим глазом"},
    "minecraft:chorus_fruit": {"n": "плод хоруса", "i": "плодом хоруса"},
    "minecraft:poisonous_potato": {"n": "ядовитый картофель",
                                   "i": "ядовитым картофелем"},
    "minecraft:pufferfish": {"n": "рыба-фугу", "a": "рыбу-фугу",
                             "i": "рыбой-фугу"},
    "minecraft:tropical_fish": {"n": "тропическая рыба",
                                "a": "тропическую рыбу",
                                "i": "тропической рыбой"},
    "minecraft:golden_carrot": {"n": "золотая морковь",
                                "a": "золотую морковь",
                                "i": "золотой морковью"},
    # --- заметные предметы (inventory_changed: «Заполучи X») ---
    "minecraft:diamond": {"n": "алмаз"},
    "minecraft:emerald": {"n": "изумруд"},
    "minecraft:gold_ingot": {"n": "золотой слиток"},
    "minecraft:iron_ingot": {"n": "железный слиток"},
    "minecraft:copper_ingot": {"n": "медный слиток"},
    "minecraft:netherite_ingot": {"n": "незеритовый слиток"},
    "minecraft:coal": {"n": "уголь"},
    "minecraft:redstone": {"n": "красная пыль", "a": "красную пыль"},
    "minecraft:lapis_lazuli": {"n": "лазурит"},
    "minecraft:quartz": {"n": "кварц"},
    "minecraft:amethyst_shard": {"n": "осколок аметиста"},
    "minecraft:echo_shard": {"n": "эхо-осколок"},
    "minecraft:ender_pearl": {"n": "эндер-жемчуг"},
    "minecraft:ender_eye": {"n": "око Края"},
    "minecraft:blaze_rod": {"n": "огненный стержень"},
    "minecraft:ghast_tear": {"n": "слеза гаста", "a": "слезу гаста"},
    "minecraft:nether_star": {"n": "звезда Нижнего мира",
                             "a": "звезду Нижнего мира"},
    "minecraft:heart_of_the_sea": {"n": "сердце моря"},
    "minecraft:totem_of_undying": {"n": "тотем бессмертия"},
    "minecraft:elytra": {"n": "элитры"},
    "minecraft:dragon_egg": {"n": "яйцо дракона"},
    "minecraft:experience_bottle": {"n": "пузырёк опыта"},
    "minecraft:saddle": {"n": "седло", "i": "седлом"},
    "minecraft:name_tag": {"n": "бирка имени", "a": "бирку имени",
                          "i": "биркой имени"},
    "minecraft:bone": {"n": "кость", "i": "костью"},
    "minecraft:string": {"n": "нить"},
    "minecraft:gunpowder": {"n": "порох"},
    "minecraft:slime_ball": {"n": "слизь"},
    "minecraft:leather": {"n": "кожа", "a": "кожу"},
    "minecraft:feather": {"n": "перо"},
    "minecraft:paper": {"n": "бумага", "a": "бумагу"},
    "minecraft:book": {"n": "книга", "a": "книгу"},
    "minecraft:brick": {"n": "кирпич"},
    "minecraft:nether_brick": {"n": "незер-кирпич"},
    "minecraft:clay_ball": {"n": "глина", "a": "глину"},
    "minecraft:wheat": {"n": "пшеница", "a": "пшеницу", "i": "пшеницей"},
    "minecraft:sugar": {"n": "сахар"},
    "minecraft:egg": {"n": "яйцо"},
    "minecraft:flint": {"n": "кремень"},
    "minecraft:stick": {"n": "палка", "a": "палку"},
    "minecraft:torch": {"n": "факел"},
    "minecraft:lantern": {"n": "фонарь"},
    "minecraft:compass": {"n": "компас"},
    "minecraft:clock": {"n": "часы"},
    "minecraft:map": {"n": "карта", "a": "карту"},
    "minecraft:shears": {"n": "ножницы", "i": "ножницами"},
    "minecraft:flint_and_steel": {"n": "огниво", "i": "огнивом"},
    "minecraft:fishing_rod": {"n": "удочка", "a": "удочку"},
    "minecraft:bow": {"n": "лук"},
    "minecraft:arrow": {"n": "стрела", "a": "стрелу"},
    "minecraft:shield": {"n": "щит"},
    "minecraft:bucket": {"n": "ведро", "i": "ведром"},
    "minecraft:glass_bottle": {"n": "стеклянная бутылочка",
                              "a": "стеклянную бутылочку"},
    "minecraft:snowball": {"n": "снежок"},
    # --- зачаровываемое (enchanted_item: «Зачаруй X») ---
    "minecraft:diamond_sword": {"n": "алмазный меч"},
    "minecraft:diamond_pickaxe": {"n": "алмазная кирка",
                                 "a": "алмазную кирку"},
    "minecraft:iron_sword": {"n": "железный меч"},
    "minecraft:iron_pickaxe": {"n": "железная кирка",
                              "a": "железную кирку"},
    "minecraft:crossbow": {"n": "арбалет"},
    "minecraft:trident": {"n": "трезубец"},
    "minecraft:diamond_helmet": {"n": "алмазный шлем"},
    "minecraft:diamond_chestplate": {"n": "алмазный нагрудник"},
    "minecraft:diamond_leggings": {"n": "алмазные штаны"},
    "minecraft:diamond_boots": {"n": "алмазные ботинки"},
    "minecraft:netherite_sword": {"n": "незеритовый меч"},
    "minecraft:golden_axe": {"n": "золотой топор",
                            "a": "золотой топор", "i": "золотым топором"},
    # --- длительное использование (using_item) ---
    "minecraft:spyglass": {"n": "подзорная труба", "a": "подзорную трубу"},
    "minecraft:goat_horn": {"n": "козий рог"},
    "minecraft:iron_spear": {"n": "железное копьё"},
    # --- вёдра (filled_bucket: «Набери X») ---
    "minecraft:water_bucket": {"n": "ведро воды"},
    "minecraft:lava_bucket": {"n": "ведро лавы"},
    "minecraft:powder_snow_bucket": {"n": "ведро порошкового снега"},
    "minecraft:axolotl_bucket": {"n": "ведро с аксолотлем"},
    "minecraft:cod_bucket": {"n": "ведро с треской"},
    "minecraft:salmon_bucket": {"n": "ведро с лососем"},
    "minecraft:pufferfish_bucket": {"n": "ведро с рыбой-фугу"},
    "minecraft:tropical_fish_bucket": {"n": "ведро с тропической рыбой"},
    "minecraft:tadpole_bucket": {"n": "ведро с головастиком"},
    # --- рыболовный лут (fishing_rod_hooked: «Выуди X удочкой») ---
    "minecraft:cod": {"n": "треска", "a": "треску"},
    "minecraft:salmon": {"n": "лосось", "a": "лосося"},
    "minecraft:enchanted_book": {"n": "зачарованная книга",
                                "a": "зачарованную книгу"},
    "minecraft:nautilus_shell": {"n": "раковина наутилуса",
                                "a": "раковину наутилуса"},
    "minecraft:bowl": {"n": "миска", "a": "миску"},
    "minecraft:leather_boots": {"n": "кожаные ботинки"},
    # --- изнашиваемое (item_durability_changed) ---
    "minecraft:golden_sword": {"n": "золотой меч"},
    "minecraft:carrot_on_a_stick": {"n": "морковь на удочке"},
    "minecraft:warped_fungus_on_a_stick": {"n": "искажённый гриб на удочке"},
    "minecraft:golden_pickaxe": {"n": "золотая кирка", "a": "золотую кирку"},
    "minecraft:golden_shovel": {"n": "золотая лопата",
                               "a": "золотую лопату"},
    "minecraft:golden_hoe": {"n": "золотая мотыга",
                            "a": "золотую мотыгу",
                            "i": "золотой мотыгой"},
    "minecraft:wooden_sword": {"n": "деревянный меч"},
    "minecraft:wooden_pickaxe": {"n": "деревянная кирка",
                                "a": "деревянную кирку"},
    "minecraft:wooden_axe": {"n": "деревянный топор",
                            "i": "деревянным топором"},
    "minecraft:wooden_shovel": {"n": "деревянная лопата",
                               "a": "деревянную лопату"},
    "minecraft:wooden_hoe": {"n": "деревянная мотыга",
                            "a": "деревянную мотыгу",
                            "i": "деревянной мотыгой"},
    # --- инструменты для item_used_on_block ---
    "minecraft:stone_axe": {"n": "каменный топор", "i": "каменным топором"},
    "minecraft:iron_axe": {"n": "железный топор", "i": "железным топором"},
    "minecraft:diamond_axe": {"n": "алмазный топор", "i": "алмазным топором"},
    "minecraft:netherite_axe": {"n": "незеритовый топор",
                               "i": "незеритовым топором"},
    "minecraft:iron_hoe": {"n": "железная мотыга", "a": "железную мотыгу",
                          "i": "железной мотыгой"},
    "minecraft:diamond_hoe": {"n": "алмазная мотыга", "a": "алмазную мотыгу",
                             "i": "алмазной мотыгой"},
    "minecraft:iron_shovel": {"n": "железная лопата", "a": "железную лопату",
                             "i": "железной лопатой"},
    "minecraft:honeycomb": {"n": "соты", "i": "сотами"},
}

# Питьё (глагол «Выпей» вместо «Съешь» в подсказках consume_item)
DRINKS = frozenset(("minecraft:milk_bucket", "minecraft:honey_bottle"))

RU_BLOCK = {
    # id: {"n": именительный, "a": винительный (если отличен)}
    "minecraft:stone": {"n": "камень"},
    "minecraft:cobblestone": {"n": "булыжник"},
    "minecraft:granite": {"n": "гранит"},
    "minecraft:diorite": {"n": "диорит"},
    "minecraft:andesite": {"n": "андезит"},
    "minecraft:deepslate": {"n": "глубинный сланец"},
    "minecraft:tuff": {"n": "туф"},
    "minecraft:calcite": {"n": "кальцит"},
    "minecraft:dirt": {"n": "земля", "a": "землю"},
    "minecraft:coarse_dirt": {"n": "каменистая земля",
                             "a": "каменистую землю"},
    "minecraft:rooted_dirt": {"n": "корневая земля",
                             "a": "корневую землю"},
    "minecraft:mud": {"n": "грязь"},
    "minecraft:packed_mud": {"n": "уплотнённая грязь",
                            "a": "уплотнённую грязь"},
    "minecraft:mud_bricks": {"n": "кирпичи из грязи"},
    "minecraft:sand": {"n": "песок"},
    "minecraft:red_sand": {"n": "красный песок"},
    "minecraft:gravel": {"n": "гравий"},
    "minecraft:clay": {"n": "глина", "a": "глину"},
    "minecraft:sandstone": {"n": "песчаник"},
    "minecraft:red_sandstone": {"n": "красный песчаник"},
    "minecraft:bricks": {"n": "кирпичи"},
    "minecraft:nether_bricks": {"n": "незерские кирпичи"},
    "minecraft:red_nether_bricks": {"n": "красные незерские кирпичи"},
    "minecraft:stone_bricks": {"n": "каменные кирпичи"},
    "minecraft:mossy_stone_bricks": {"n": "замшелые каменные кирпичи"},
    "minecraft:deepslate_bricks": {"n": "кирпичи из глубинного сланца"},
    "minecraft:deepslate_tiles": {"n": "плитка из глубинного сланца",
                                "a": "плитку из глубинного сланца"},
    "minecraft:tuff_bricks": {"n": "туфовые кирпичи"},
    "minecraft:polished_deepslate": {"n": "полированный глубинный сланец"},
    "minecraft:polished_blackstone": {"n": "полированный чернит"},
    "minecraft:polished_granite": {"n": "полированный гранит"},
    "minecraft:polished_diorite": {"n": "полированный диорит"},
    "minecraft:polished_andesite": {"n": "полированный андезит"},
    "minecraft:polished_tuff": {"n": "полированный туф"},
    "minecraft:smooth_stone": {"n": "гладкий камень"},
    "minecraft:obsidian": {"n": "обсидиан"},
    "minecraft:crying_obsidian": {"n": "плачущий обсидиан"},
    "minecraft:netherrack": {"n": "незеррак"},
    "minecraft:end_stone": {"n": "камень Края"},
    "minecraft:end_stone_bricks": {"n": "кирпичи Края"},
    "minecraft:basalt": {"n": "базальт"},
    "minecraft:blackstone": {"n": "чернит"},
    "minecraft:quartz_block": {"n": "кварцевый блок"},
    "minecraft:purpur_block": {"n": "пурпуровый блок"},
    "minecraft:prismarine": {"n": "призмарин"},
    "minecraft:prismarine_bricks": {"n": "призмариновые кирпичи"},
    "minecraft:dark_prismarine": {"n": "тёмный призмарин"},
    "minecraft:terracotta": {"n": "терракота", "a": "терракоту"},
    "minecraft:quartz_bricks": {"n": "кварцевые кирпичи"},
    "minecraft:amethyst_block": {"n": "блок аметиста"},
    "minecraft:copper_block": {"n": "медный блок"},
    "minecraft:iron_block": {"n": "железный блок"},
    "minecraft:gold_block": {"n": "золотой блок"},
    "minecraft:diamond_block": {"n": "алмазный блок"},
    "minecraft:emerald_block": {"n": "изумрудный блок"},
    "minecraft:lapis_block": {"n": "блок лазурита"},
    "minecraft:redstone_block": {"n": "блок красной пыли"},
    "minecraft:coal_block": {"n": "угольный блок"},
    "minecraft:netherite_block": {"n": "незеритовый блок"},
    "minecraft:glowstone": {"n": "светокамень"},
    "minecraft:shroomlight": {"n": "грибной свет"},
    "minecraft:sea_lantern": {"n": "морской фонарь"},
    "minecraft:magma_block": {"n": "блок магмы"},
    "minecraft:melon": {"n": "арбуз"},
    "minecraft:pumpkin": {"n": "тыква", "a": "тыкву"},
    "minecraft:carved_pumpkin": {"n": "вырезанная тыква",
                                "a": "вырезанную тыкву"},
    "minecraft:jack_o_lantern": {"n": "светильник Джека"},
    "minecraft:hay_block": {"n": "сноп сена"},
    "minecraft:bone_block": {"n": "костяной блок"},
    "minecraft:slime_block": {"n": "блок слизи"},
    "minecraft:honey_block": {"n": "медовый блок"},
    "minecraft:honeycomb_block": {"n": "блок медовых сот"},
    "minecraft:dried_kelp_block": {"n": "блок сушёной ламинарии"},
    "minecraft:sponge": {"n": "губка", "a": "губку"},
    "minecraft:wet_sponge": {"n": "мокрая губка", "a": "мокрую губку"},
    "minecraft:moss_block": {"n": "блок мха"},
    "minecraft:sculk": {"n": "скалк"},
    "minecraft:dripstone_block": {"n": "блок натёчного камня"},
    "minecraft:ice": {"n": "лёд"},
    "minecraft:packed_ice": {"n": "плотный лёд"},
    "minecraft:blue_ice": {"n": "синий лёд"},
    "minecraft:snow_block": {"n": "снежный блок"},
    "minecraft:soul_sand": {"n": "песок душ"},
    "minecraft:soul_soil": {"n": "земля душ", "a": "землю душ"},
    "minecraft:mycelium": {"n": "мицелий"},
    "minecraft:podzol": {"n": "подзол"},
    "minecraft:grass_block": {"n": "дёрн"},
    "minecraft:oak_planks": {"n": "дубовые доски"},
    "minecraft:spruce_planks": {"n": "еловые доски"},
    "minecraft:birch_planks": {"n": "берёзовые доски"},
    "minecraft:jungle_planks": {"n": "доски из тропического дерева"},
    "minecraft:acacia_planks": {"n": "доски из акации"},
    "minecraft:dark_oak_planks": {"n": "доски из тёмного дуба"},
    "minecraft:mangrove_planks": {"n": "доски из мангрового дерева"},
    "minecraft:cherry_planks": {"n": "вишнёвые доски"},
    "minecraft:pale_oak_planks": {"n": "доски из бледного дуба"},
    "minecraft:bamboo_planks": {"n": "бамбуковые доски"},
    "minecraft:bamboo_mosaic": {"n": "бамбуковая мозаика",
                               "a": "бамбуковую мозаику"},
    "minecraft:crimson_planks": {"n": "малиновые доски"},
    "minecraft:warped_planks": {"n": "искажённые доски"},
    "minecraft:oak_log": {"n": "дубовое бревно"},
    "minecraft:spruce_log": {"n": "еловое бревно"},
    "minecraft:birch_log": {"n": "берёзовое бревно"},
    "minecraft:glass": {"n": "стекло"},
    "minecraft:tinted_glass": {"n": "тонированное стекло"},
    "minecraft:crafting_table": {"n": "верстак"},
    "minecraft:furnace": {"n": "печь"},
    "minecraft:chest": {"n": "сундук"},
    "minecraft:barrel": {"n": "бочка", "a": "бочку"},
    "minecraft:bookshelf": {"n": "книжный шкаф"},
    "minecraft:composter": {"n": "компостер"},
    "minecraft:note_block": {"n": "нотный блок"},
    "minecraft:jukebox": {"n": "проигрыватель"},
    "minecraft:beacon": {"n": "маяк"},
    "minecraft:lodestone": {"n": "магнетит"},
    "minecraft:respawn_anchor": {"n": "якорь возрождения"},
    # брёвна для обтёсывания топором (item_used_on_block; сверх
    # PLACEABLE_BLOCKS - цель пары «топор -> бревно»)
    "minecraft:jungle_log": {"n": "бревно из тропического дерева"},
    "minecraft:acacia_log": {"n": "бревно акации"},
    "minecraft:dark_oak_log": {"n": "бревно из тёмного дуба"},
    "minecraft:mangrove_log": {"n": "бревно из мангрового дерева"},
    "minecraft:cherry_log": {"n": "вишнёвое бревно"},
    "minecraft:pale_oak_log": {"n": "бревно из бледного дуба"},
    # enter_block + bee_nest_destroyed
    "minecraft:nether_portal": {"n": "портал Нижнего мира"},
    "minecraft:end_gateway": {"n": "шлюз Края"},
    "minecraft:water": {"n": "вода", "a": "воду"},
    "minecraft:bubble_column": {"n": "пузырьковый столб"},
    "minecraft:cobweb": {"n": "паутина", "a": "паутину"},
    "minecraft:sweet_berry_bush": {"n": "куст сладких ягод"},
    "minecraft:powder_snow": {"n": "порошковый снег"},
    "minecraft:bee_nest": {"n": "пчелиное гнездо"},
    "minecraft:beehive": {"n": "улей"},
}

# Эффекты, родительный падеж: «под эффектом X», «Подвергнись эффекту X»
RU_EFFECT = {
    "minecraft:absorption": "поглощения",
    "minecraft:bad_omen": "дурного знамения",
    "minecraft:blindness": "слепоты",
    "minecraft:conduit_power": "силы проводника",
    "minecraft:darkness": "тьмы",
    "minecraft:dolphins_grace": "грации дельфина",
    "minecraft:fire_resistance": "огнестойкости",
    "minecraft:glowing": "свечения",
    "minecraft:haste": "спешки",
    "minecraft:hunger": "голода",
    "minecraft:infested": "заражения",
    "minecraft:invisibility": "невидимости",
    "minecraft:jump_boost": "прыгучести",
    "minecraft:levitation": "левитации",
    "minecraft:mining_fatigue": "усталости",
    "minecraft:nausea": "тошноты",
    "minecraft:night_vision": "ночного зрения",
    "minecraft:oozing": "истечения",
    "minecraft:poison": "отравления",
    "minecraft:regeneration": "регенерации",
    "minecraft:resistance": "сопротивления",
    "minecraft:saturation": "насыщения",
    "minecraft:slow_falling": "медленного падения",
    "minecraft:slowness": "медлительности",
    "minecraft:speed": "скорости",
    "minecraft:strength": "силы",
    "minecraft:water_breathing": "подводного дыхания",
    "minecraft:weakness": "слабости",
    "minecraft:weaving": "плетения",
    "minecraft:wind_charged": "заряда ветра",
    "minecraft:wither": "иссушения",
}

# Зелья, винительная фраза: «Свари X»
RU_POTION = {
    "minecraft:awkward": "неуклюжее зелье",
    "minecraft:fire_resistance": "зелье огнестойкости",
    "minecraft:harming": "зелье вреда",
    "minecraft:healing": "зелье лечения",
    "minecraft:infested": "зелье заражения",
    "minecraft:invisibility": "зелье невидимости",
    "minecraft:leaping": "зелье прыгучести",
    "minecraft:mundane": "мутное зелье",
    "minecraft:night_vision": "зелье ночного зрения",
    "minecraft:oozing": "зелье истечения",
    "minecraft:poison": "зелье отравления",
    "minecraft:regeneration": "зелье регенерации",
    "minecraft:slow_falling": "зелье медленного падения",
    "minecraft:slowness": "зелье медлительности",
    "minecraft:strength": "зелье силы",
    "minecraft:swiftness": "зелье скорости",
    "minecraft:thick": "густое зелье",
    "minecraft:turtle_master": "зелье черепахи",
    "minecraft:water": "флакон воды",
    "minecraft:water_breathing": "зелье подводного дыхания",
    "minecraft:weakness": "зелье слабости",
    "minecraft:weaving": "зелье плетения",
    "minecraft:wind_charged": "зелье заряда ветра",
}

# ---------------------------------------------------------------------------
# ЗАГАДКИ в духе русского фольклора (фидбек юзера: прежние описания были
# «бездушными» - теперь каждый блок/предмет скрыт НАСТОЯЩЕЙ загадкой, над
# которой надо подумать; но 1-2 характерных признака - свойство,
# происхождение, функция, цвет, форма, число - всегда оставлены, чтобы
# предмет УГАДЫВАЛСЯ). Приёмы - как в народных загадках, тег у каждой:
#   neg       ОТРИЦАНИЕ очевидного - «не лает, не кусает, а в дом не
#             не пускает» (замок), «без окон, без дверей» (огурец)
#   contrast  КОНТРАСТ/НЕИЗМЕННОСТЬ - «зимой и летом одним цветом» (ёлка)
#   person    ПЕРСОНИФИКАЦИЯ - «сидит дед, во сто шуб одет» (лук),
#             «красная девица сидит в темнице» (морковь)
#   metaphor  МЕТАФОРА ДОМА/ТЕЛА/ЖИЗНИ - «кто на себе свой дом носит»
#             (улитка), «висит груша - нельзя скушать» (лампочка)
#   number    ЧИСЛОВАЯ ЗАГАДКА - «два конца, два кольца, посередине
#             гвоздик» (ножницы); железный блок = «девять слитков»
#   notab     «НЕ А, НЕ Б, А В» - перечисление и отрицание признаков
#   action    ЗАГАДКА-ДЕЙСТВИЕ - «кто в году четыре раза
#             переодевается?» (земля)
# Формат (источник правды - conditions JSON критерия, см. _hint_for):
#   RIDDLE_BLOCKS  id -> ((тег, текст), (тег, текст)) - ДВА варианта:
#                  первый КОРОТКИЙ (<= 7 слов: его берут двойные
#                  подсказки «предмет + блок» - алай, item_used_on_block),
#                  второй - «два колена» подлиннее (4-12 слов)
#   RIDDLE_ITEMS   id -> {"a": ((тег, винительный), (тег, винительный)),
#                  "i": ((тег, творительный), (тег, творительный))} -
#                  "i" только предметам, что в подсказках «держат в
#                  руке» (инструменты item_used_on_block + предметы
#                  интеракт-пар)
# Все фразы - именные группы в нужном падеже: они ставятся ПОСЛЕ глагола
# («Воздвигни ...», «Заполучи ...», «Вкуси ...», «Обтёси ... ...ом»);
# творительный всегда согласован («обтёси ... каменным топором дикаря»).
# Доступ с бюджетом слов (_riddle_block(rng, id, max_words=N)) берёт
# короткое колено, когда загадка встаёт в двойную подсказку.
#   POETIC_ENT  id -> (именительный, винительный) - образные прозвища
#               колоритных врагов для подсказок убийства («страж
#               песков» = хаск); используются ИЗРЕДКА - фидбек юзера:
#               «местами образно, но понятнее, чем блоки»
# Самотест проверяет: полноту (каждый id каждого пула), длину 4-14 слов,
# короткое первое колено <= 7 слов, запрещённые канцеляризмы («который»,
# «является»...) и разнообразие приёмов (>= 3 разных тега в каждом окне
# из 20 загадок подряд, >= 6 приёмов по всем таблицам).
# ---------------------------------------------------------------------------

# легенда приёмов (теги загадок; см. самотест - разнообразие проверяется)
_RIDDLE_TAGS = ("neg", "contrast", "person", "metaphor", "number",
                "notab", "action")

RIDDLE_BLOCKS = {
    # --- камень и породы ---
    "minecraft:stone": (
        ("contrast", "кость земли, что не старится"),
        ("metaphor", "первую плоть, что держит на себе все горы"),
    ),
    "minecraft:cobblestone": (
        ("action", "то, что остаётся, когда кирка права"),
        ("notab", "каменное крошево, а не гальку и не плиту"),
    ),
    "minecraft:granite": (
        ("metaphor", "камень в розовых веснушках"),
        ("person", "румяный барин каменных палат"),
    ),
    "minecraft:diorite": (
        ("metaphor", "окаменевшее молоко в чёрных крапинках"),
        ("notab", "молоко с чёрными точками, а не мел и не золу"),
    ),
    "minecraft:andesite": (
        ("contrast", "серого середняка из каменного троебратства"),
        ("notab", "серого работягу, а не белого и не рыжего"),
    ),
    "minecraft:deepslate": (
        ("metaphor", "кость нижних этажей мира"),
        ("contrast", "камень, почерневший от вечной ночи"),
    ),
    "minecraft:tuff": (
        ("metaphor", "слоёный пирог из вулканического пепла"),
        ("person", "золу, что спит уже тысячу лет"),
    ),
    "minecraft:calcite": (
        ("metaphor", "меловую белизну древних морей"),
        ("number", "раковины миллиона моллюсков, спрессованные в камень"),
    ),
    "minecraft:dirt": (
        ("metaphor", "колыбель всего, что растёт"),
        ("action", "то, что пачкает лопату и кормит колос"),
    ),
    "minecraft:coarse_dirt": (
        ("neg", "землю, что не держит травы"),
        ("person", "упрямую землю, отказывающуюся зеленеть"),
    ),
    "minecraft:rooted_dirt": (
        ("metaphor", "землю, сотканную из корней"),
        ("action", "живую кладовую, где спят корни"),
    ),
    "minecraft:mud": (
        ("metaphor", "глубокую чавкающую постель болот"),
        ("person", "трясину, что тянет за сапоги"),
    ),
    "minecraft:packed_mud": (
        ("action", "грязь, высушенную до каменной твёрдости"),
        ("notab", "затвердевшую топь - не грязь и не кирпич"),
    ),
    "minecraft:mud_bricks": (
        ("metaphor", "кладку из болотного теста"),
        ("number", "кирпичи из грязи и солнца"),
    ),
    "minecraft:sand": (
        ("metaphor", "сухое море без капли воды"),
        ("action", "то, что утекает сквозь пальцы"),
    ),
    "minecraft:red_sand": (
        ("metaphor", "ржавое море без воды"),
        ("contrast", "песок, выгоревший до цвета меди"),
    ),
    "minecraft:gravel": (
        ("action", "то, что хрустит под сапогами"),
        ("metaphor", "речной пирог с кремниевой начинкой"),
    ),
    "minecraft:clay": (
        ("metaphor", "мягкое серое тесто гончара"),
        ("action", "то, из чего родится кирпич"),
    ),
    "minecraft:sandstone": (
        ("number", "песок, сжатый тысячью ветров в камень"),
        ("metaphor", "дюну, что спеклась в камень"),
    ),
    "minecraft:red_sandstone": (
        ("metaphor", "ржавую дюну, что спеклась в камень"),
        ("contrast", "близнеца песчаника в медной шкуре"),
    ),
    "minecraft:bricks": (
        ("metaphor", "красную кладку людских очагов"),
        ("action", "глину, что закалили в огне"),
    ),
    "minecraft:nether_bricks": (
        ("metaphor", "кладку цвета запёкшейся крови"),
        ("neg", "кирпич, что обжигали не в печи"),
    ),
    "minecraft:red_nether_bricks": (
        ("number", "адскую кладку, обожжённую дважды"),
        ("contrast", "кирпич, что даже в аду рыжее всех"),
    ),
    "minecraft:stone_bricks": (
        ("metaphor", "старую кладку крепостей и руин"),
        ("person", "ветеранов, что держат древние стены"),
    ),
    "minecraft:mossy_stone_bricks": (
        ("contrast", "кладку, что обнял мох"),
        ("action", "камни, пережившие свои стены"),
    ),
    "minecraft:deepslate_bricks": (
        ("metaphor", "тёмную кладку чернильных подземелий"),
        ("neg", "кирпичи, что не видели солнца"),
    ),
    "minecraft:deepslate_tiles": (
        ("metaphor", "тёмную чешую подземных чертогов"),
        ("number", "тысячу тёмных плиток в одном кубе"),
    ),
    "minecraft:tuff_bricks": (
        ("metaphor", "кладку из вулканического слоёного пирога"),
        ("person", "пепел, что выучился строиться"),
    ),
    "minecraft:polished_deepslate": (
        ("metaphor", "глянцевую тьму нижних этажей"),
        ("contrast", "вечную тьму, что заблестела"),
    ),
    "minecraft:polished_blackstone": (
        ("metaphor", "смоляное зеркало каменных низин"),
        ("contrast", "уголь, что научился блестеть"),
    ),
    "minecraft:polished_granite": (
        ("metaphor", "веснушки, отшлифованные до шёлка"),
        ("person", "румяного барина, приодевшегося в глянец"),
    ),
    "minecraft:polished_diorite": (
        ("metaphor", "глянцевое молоко в чёрных крапинках"),
        ("contrast", "молоко, что блестит, как река"),
    ),
    "minecraft:polished_andesite": (
        ("metaphor", "глянцевый пепел остывших вулканов"),
        ("contrast", "серого середняка, надевшего глянец"),
    ),
    "minecraft:polished_tuff": (
        ("metaphor", "глянцевый слоёный пирог вулкана"),
        ("contrast", "пепел, что надел парадный блеск"),
    ),
    "minecraft:smooth_stone": (
        ("action", "камень, отшлифованный до нежности"),
        ("contrast", "булыжник, что забыл шершавость"),
    ),
    "minecraft:obsidian": (
        ("metaphor", "слёзы огня, застывшие стеклом"),
        ("neg", "чёрное стекло, что не бьётся"),
    ),
    "minecraft:crying_obsidian": (
        ("person", "обсидиан, что горько плачет светом"),
        ("metaphor", "камень со слезами на щеках"),
    ),
    "minecraft:netherrack": (
        ("metaphor", "розовое мясо нижнего мира"),
        ("action", "камень, что вечно тлеет и не сгорает"),
    ),
    "minecraft:end_stone": (
        ("metaphor", "бледную кость чужого неба"),
        ("neg", "камень, что не помнит солнца"),
    ),
    "minecraft:end_stone_bricks": (
        ("metaphor", "кладку из кости чужого мира"),
        ("number", "кость чужих островов, распиленную на кирпичи"),
    ),
    "minecraft:basalt": (
        ("metaphor", "застывшие колонны огненных фонтанов"),
        ("contrast", "камень, рождённый лавой, но холодный"),
    ),
    "minecraft:blackstone": (
        ("metaphor", "смоляную кость каменных низин"),
        ("neg", "чёрный, как полночь, но не ночь"),
    ),
    "minecraft:quartz_block": (
        ("metaphor", "слоновую кость из недр"),
        ("contrast", "снег, что не тает и в аду"),
    ),
    "minecraft:purpur_block": (
        ("metaphor", "пурпурную чешую чужого мира"),
        ("contrast", "фиолетовый камень чужих дворцов"),
    ),
    "minecraft:prismarine": (
        ("metaphor", "зелёную чешую океанского дна"),
        ("action", "камень, что вылизан морем"),
    ),
    "minecraft:prismarine_bricks": (
        ("metaphor", "морскую кладку русалочьих чертогов"),
        ("number", "тысячу рыбьих чешуек, сложенных в камень"),
    ),
    "minecraft:dark_prismarine": (
        ("metaphor", "тёмную чешую морской бездны"),
        ("contrast", "морской камень с чёрной водой в сердце"),
    ),
    "minecraft:terracotta": (
        ("metaphor", "обожжённую глину цветных каньонов"),
        ("action", "посуду гончара, ставшую камнем"),
    ),
    "minecraft:quartz_bricks": (
        ("metaphor", "кладку из слоновой кости"),
        ("contrast", "белые кирпичи, что не боятся огня"),
    ),
    # --- самоцветы и металлы ---
    "minecraft:amethyst_block": (
        ("metaphor", "спевший хор фиолетовых кристаллов"),
        ("action", "камень, что звенит, если задеть"),
    ),
    "minecraft:copper_block": (
        ("contrast", "рыжий металл, что зеленеет с возрастом"),
        ("metaphor", "застывший закат в металле"),
    ),
    "minecraft:iron_block": (
        ("number", "девять слитков, сжатых в одно"),
        ("metaphor", "всю серую казну кузнецов"),
    ),
    "minecraft:gold_block": (
        ("number", "девять капель солнца в одном кубе"),
        ("contrast", "самый тяжёлый кошель королей"),
    ),
    "minecraft:diamond_block": (
        ("number", "девять слёз земли, сжатых в куб"),
        ("contrast", "куб, что твёрже стали и дороже короны"),
    ),
    "minecraft:emerald_block": (
        ("number", "девять зелёных монет, сжатых в куб"),
        ("metaphor", "казну торговцев, застывшую камнем"),
    ),
    "minecraft:lapis_block": (
        ("metaphor", "сгущённую синеву вечернего неба"),
        ("number", "краску художников, спрессованную в камень"),
    ),
    "minecraft:redstone_block": (
        ("metaphor", "сжатую искру всех механизмов"),
        ("action", "пыль, что дышит, если её сжать"),
    ),
    "minecraft:coal_block": (
        ("metaphor", "спрессованный чёрный хлеб печей"),
        ("number", "древний лес, спрессованный в чёрный куб"),
    ),
    "minecraft:netherite_block": (
        ("contrast", "куб, что пережил адскую плавку"),
        ("neg", "металл, что не берут ни огонь, ни время"),
    ),
    # --- свет ---
    "minecraft:glowstone": (
        ("metaphor", "пойманный свет чужого потолка"),
        ("contrast", "солнце, что остыло, но светит"),
    ),
    "minecraft:shroomlight": (
        ("metaphor", "фонарь, что зреет в шляпке гриба"),
        ("person", "гриб, что носит собственное солнце"),
    ),
    "minecraft:sea_lantern": (
        ("metaphor", "сияющую жемчужину океанского дна"),
        ("contrast", "свет, что не боится воды"),
    ),
    "minecraft:magma_block": (
        ("metaphor", "лаву, что притворилась камнем"),
        ("action", "камень, что жжёт подошвы"),
    ),
    # --- флора и дары природы ---
    "minecraft:melon": (
        ("metaphor", "огромную полосатую ягоду с красной мякотью"),
        ("notab", "полосатую гору, а не тыкву и не яблоко"),
    ),
    "minecraft:pumpkin": (
        ("metaphor", "рыжий шар осенних страшилищ"),
        ("person", "круглого рыжего барина с грядки"),
    ),
    "minecraft:carved_pumpkin": (
        ("person", "тыкву с вырезанной усмешкой"),
        ("action", "рыжий шар, что получил лицо от ножа"),
    ),
    "minecraft:jack_o_lantern": (
        ("metaphor", "фонарь с тыквенной душой"),
        ("contrast", "голова, что светится в темноте"),
    ),
    "minecraft:hay_block": (
        ("metaphor", "спрессованное золото летних полей"),
        ("number", "стог, сжатый до одного куба"),
    ),
    "minecraft:bone_block": (
        ("metaphor", "памятник из чужих скелетов"),
        ("person", "кость великана, что не успел истлеть"),
    ),
    "minecraft:slime_block": (
        ("action", "куб, что прыгает, если стукнуть"),
        ("contrast", "мягкое, как подушка, да живое"),
    ),
    "minecraft:honey_block": (
        ("metaphor", "тягучий капкан из золотистой сладости"),
        ("action", "сладость, что не отпускает ногу"),
    ),
    "minecraft:honeycomb_block": (
        ("number", "кладовую из тысячи пчелиных шестиугольников"),
        ("metaphor", "соты, что стали стеной"),
    ),
    "minecraft:dried_kelp_block": (
        ("metaphor", "брикет из морской травы"),
        ("contrast", "траву, что высушили до хруста"),
    ),
    "minecraft:sponge": (
        ("person", "жадного до воды старика"),
        ("neg", "камень, что не тонет, а пьёт"),
    ),
    "minecraft:wet_sponge": (
        ("contrast", "губку, что уже напилась"),
        ("person", "старика, что хватил лишку океана"),
    ),
    "minecraft:moss_block": (
        ("metaphor", "мягкую бархатную подушку леса"),
        ("contrast", "ковёр, что стелется без ткача"),
    ),
    "minecraft:sculk": (
        ("person", "тьму, что дышит и растёт"),
        ("action", "мох, что помнит чужие крики"),
    ),
    "minecraft:dripstone_block": (
        ("action", "камень, что точат капли"),
        ("metaphor", "сердце всех пещерных сталактитов"),
    ),
    # --- лёд и снег ---
    "minecraft:ice": (
        ("contrast", "воду, что забыла, как течь"),
        ("notab", "хрупкий холод, а не снег и не стекло"),
    ),
    "minecraft:packed_ice": (
        ("number", "лёд, укатанный в сто слоёв"),
        ("contrast", "холод, что уже не тает"),
    ),
    "minecraft:blue_ice": (
        ("metaphor", "плотную синеву вечной зимы"),
        ("neg", "лёд, что не тает даже у огня"),
    ),
    "minecraft:snow_block": (
        ("metaphor", "куб, слепленный из целой метели"),
        ("contrast", "зиму, что держит форму"),
    ),
    # --- земля душ и почвы ---
    "minecraft:soul_sand": (
        ("person", "песок, где стонут чужие души"),
        ("action", "топь, что тянет вниз каждый шаг"),
    ),
    "minecraft:soul_soil": (
        ("metaphor", "землю, напитанную чужими голосами"),
        ("person", "тихое кладбище чужих голосов"),
    ),
    "minecraft:mycelium": (
        ("metaphor", "грибную паутину, притворившуюся землёй"),
        ("contrast", "пурпурную кожу со спящими под ней грибами"),
    ),
    "minecraft:podzol": (
        ("metaphor", "подстилку старого хвойного леса"),
        ("action", "землю, что хвоя укрыла от солнца"),
    ),
    "minecraft:grass_block": (
        ("contrast", "живой ковёр на мёртвом кубе"),
        ("metaphor", "зелёные волосы самой земли"),
    ),
    # --- дерево: доски ---
    "minecraft:oak_planks": (
        ("metaphor", "пилёную плоть столетнего дуба"),
        ("person", "доски, что помнят шум листвы"),
    ),
    "minecraft:spruce_planks": (
        ("metaphor", "смолистые доски северной ели"),
        ("contrast", "дерево, что выбрало мороз"),
    ),
    "minecraft:birch_planks": (
        ("contrast", "белокорые доски с чёрными чёрточками"),
        ("metaphor", "стройную берёзку, распиленную на доски"),
    ),
    "minecraft:jungle_planks": (
        ("metaphor", "пилёные стволы тропических великанов"),
        ("action", "древесину, увитую когда-то лианами"),
    ),
    "minecraft:acacia_planks": (
        ("metaphor", "тёплые доски дерева саванн"),
        ("contrast", "доски цвета чужого заката"),
    ),
    "minecraft:dark_oak_planks": (
        ("metaphor", "тёмное дерево глухих чащ"),
        ("neg", "доски, что не любят света"),
    ),
    "minecraft:mangrove_planks": (
        ("metaphor", "рыжие доски болотного странника"),
        ("action", "дерево, что ходит по болотам корнями"),
    ),
    "minecraft:cherry_planks": (
        ("metaphor", "доски цвета лепесткового снега"),
        ("contrast", "весну, распиленную на доски"),
    ),
    "minecraft:pale_oak_planks": (
        ("neg", "седые доски жутких рощ"),
        ("person", "доски, что старше самого леса"),
    ),
    "minecraft:bamboo_planks": (
        ("metaphor", "доски из полого тростника-исполина"),
        ("contrast", "траву, что доросла до дерева"),
    ),
    "minecraft:bamboo_mosaic": (
        ("number", "узор из сотни бамбуковых коленцев"),
        ("metaphor", "плетёный ковёр из бамбука"),
    ),
    "minecraft:crimson_planks": (
        ("metaphor", "малиновое дерево огненных пещер"),
        ("contrast", "грибы, что притворились деревом"),
    ),
    "minecraft:warped_planks": (
        ("metaphor", "бирюзовое дерево чужих пещер"),
        ("person", "дерево, что вывернуло душу наизнанку"),
    ),
    # --- дерево: брёвна ---
    "minecraft:oak_log": (
        ("metaphor", "ствол, что триста лет держал небо"),
        ("person", "патриарха леса, положенного на бок"),
    ),
    "minecraft:spruce_log": (
        ("metaphor", "колючий ствол северных лесов"),
        ("contrast", "бревно, что пахнет морозом"),
    ),
    "minecraft:birch_log": (
        ("contrast", "белокорый ствол в чёрных крапинках"),
        ("metaphor", "белую свечку северного леса"),
    ),
    "minecraft:jungle_log": (
        ("metaphor", "ствол, увитый когда-то лианами"),
        ("number", "бревно толще человечьей талии втрое"),
    ),
    "minecraft:acacia_log": (
        ("metaphor", "шиповатый ствол дерева саванн"),
        ("action", "бревно, что выросло среди сухой травы"),
    ),
    "minecraft:dark_oak_log": (
        ("metaphor", "тёмный ствол глухих чащ"),
        ("neg", "бревно, что выросло в вечной тени"),
    ),
    "minecraft:mangrove_log": (
        ("metaphor", "болотное бревно с корнями-бородой"),
        ("action", "ствол, что стоит по колено в трясине"),
    ),
    "minecraft:cherry_log": (
        ("metaphor", "ствол из вишнёвого сада"),
        ("contrast", "дерево, что розовеет раньше всех"),
    ),
    "minecraft:pale_oak_log": (
        ("metaphor", "седой ствол жутких рощ"),
        ("person", "ствол, где спит скрипун"),
    ),
    # --- стекло ---
    "minecraft:glass": (
        ("neg", "стену, что не задержит взгляда"),
        ("metaphor", "застывший воздух, что боится камней"),
    ),
    "minecraft:tinted_glass": (
        ("neg", "стекло, что не пускает свет"),
        ("contrast", "прозрачное снаружи, тёмное внутри"),
    ),
    # --- функциональные блоки ---
    "minecraft:crafting_table": (
        ("metaphor", "сердце всякой людской мастерской"),
        ("action", "стол, где вещи рождаются заново"),
    ),
    "minecraft:furnace": (
        ("person", "каменную пасть, что всегда голодна"),
        ("action", "печь, что ест руду и выдаёт слитки"),
    ),
    "minecraft:chest": (
        ("metaphor", "скрипучего хранителя чужого скарба"),
        ("neg", "дом без окон, полный чужих тайн"),
    ),
    "minecraft:barrel": (
        ("metaphor", "бочку, что любит погреба"),
        ("person", "толстяка, что стоит в погребе"),
    ),
    "minecraft:bookshelf": (
        ("metaphor", "стену из чужих историй"),
        ("person", "мудреца, распиленного на доски"),
    ),
    "minecraft:composter": (
        ("action", "бочку, что ест объедки"),
        ("metaphor", "утробу, что превращает мусор в землю"),
    ),
    "minecraft:note_block": (
        ("person", "куб, что поёт, если тронуть"),
        ("number", "двадцать пять голосов в одном кубе"),
    ),
    "minecraft:jukebox": (
        ("person", "ящик, что поёт за пластинку"),
        ("action", "голос, что просыпается от пластинки"),
    ),
    "minecraft:beacon": (
        ("metaphor", "сияющую корону на пирамиде"),
        ("action", "свет, что требует жертвы"),
    ),
    "minecraft:lodestone": (
        ("action", "камень, что приковывает стрелку компаса"),
        ("metaphor", "вечный якорь для заблудившихся стрелок"),
    ),
    "minecraft:respawn_anchor": (
        ("metaphor", "якорь, что держит душу"),
        ("contrast", "постель для тех, кому кровать опасна"),
    ),
    # --- enter_block (порталы в другие миры убраны - их тут нет) ---
    "minecraft:water": (
        ("neg", "то, без чего никто не живёт"),
        ("metaphor", "живую кровь рек и морей"),
    ),
    "minecraft:bubble_column": (
        ("action", "лифт, что поднимает без канатов"),
        ("metaphor", "столб воздуха посреди воды"),
    ),
    "minecraft:cobweb": (
        ("metaphor", "ловушку из шёлка пауков"),
        ("person", "сеть, что сплёл голодный ткач"),
    ),
    "minecraft:sweet_berry_bush": (
        ("contrast", "куст, что кусает за сладость"),
        ("notab", "ягоды с характером, а не ежа и не крапиву"),
    ),
    "minecraft:powder_snow": (
        ("neg", "снег, что притворяется твердью"),
        ("contrast", "белую трясину без капли воды"),
    ),
    # --- bee_nest_destroyed ---
    "minecraft:bee_nest": (
        ("person", "гулкий домик диких тружениц"),
        ("action", "дом, что жужжит и жалит"),
    ),
    "minecraft:beehive": (
        ("metaphor", "домик для пчёл, сколоченный людьми"),
        ("contrast", "гнездо, но ручной работы"),
    ),
}

RIDDLE_ITEMS = {
    # --- заметные предметы ---
    "minecraft:diamond": {"a": (
        ("contrast", "слезу земли, что твёрже стали"),
        ("action", "то, за чем спускаются на самое дно"),
    )},
    "minecraft:emerald": {"a": (
        ("metaphor", "зелёную монету чужих торговцев"),
        ("action", "камень, за что продают целые деревни"),
    )},
    "minecraft:gold_ingot": {"a": (
        ("metaphor", "застывший луч солнца в металле"),
        ("person", "мягкое золото, что любят короли"),
    )},
    "minecraft:iron_ingot": {"a": (
        ("metaphor", "всю рабочую валюту мастеровых"),
        ("action", "слиток, что устал от молота"),
    )},
    "minecraft:copper_ingot": {"a": (
        ("contrast", "рыжий слиток, что зеленеет с годами"),
        ("metaphor", "отломанный кусочек медного заката"),
    )},
    "minecraft:netherite_ingot": {"a": (
        ("contrast", "слиток, что пережил адское пламя"),
        ("person", "упрямца, что плавится лишь в аду"),
    )},
    "minecraft:coal": {"a": (
        ("metaphor", "чёрный хлеб для печей"),
        ("contrast", "лес, что сгорел миллионы лет назад"),
    )},
    "minecraft:redstone": {"a": (
        ("action", "пыль, что оживляет механизмы"),
        ("metaphor", "огненную кровь каменных жил"),
    )},
    "minecraft:lapis_lazuli": {"a": (
        ("metaphor", "синий осколок ночного неба"),
        ("action", "камень, что красит в царскую синь"),
    )},
    "minecraft:quartz": {"a": (
        ("metaphor", "белый кристалл из адских недр"),
        ("contrast", "снежинку, что не тает и в аду"),
    )},
    "minecraft:amethyst_shard": {"a": (
        ("action", "звенящий осколок поющей горы"),
        ("contrast", "осколок, что поёт под молотком"),
    )},
    "minecraft:echo_shard": {"a": (
        ("person", "осколок, что помнит чужие голоса"),
        ("contrast", "эхо, застывшее в камне"),
    )},
    "minecraft:ender_pearl": {"a": (
        ("action", "шар, что швыряет хозяина сквозь мир"),
        ("metaphor", "слезу чужого безмолвного народа"),
    )},
    "minecraft:ender_eye": {"a": (
        ("action", "око, что ищет незримое"),
        ("contrast", "глаз, что летает и возвращается"),
    )},
    "minecraft:blaze_rod": {"a": (
        ("person", "полено, что не гаснет"),
        ("metaphor", "пылающий посох огненного духа"),
    )},
    "minecraft:ghast_tear": {"a": (
        ("person", "слезу плачущего белого призрака"),
        ("contrast", "горькую каплю, что лечит раны"),
    )},
    "minecraft:nether_star": {"a": (
        ("number", "звёздный трофей трёхглавого кошмара"),
        ("contrast", "звезду, что светит в руке, но не в небе"),
    )},
    "minecraft:heart_of_the_sea": {"a": (
        ("metaphor", "сердце, что спит в раковине"),
        ("action", "то, что будит подводные силы"),
    )},
    "minecraft:totem_of_undying": {"a": (
        ("person", "деревянного обманщика самой смерти"),
        ("contrast", "фигурку, что спасает лишь единожды"),
    )},
    "minecraft:elytra": {"a": (
        ("metaphor", "крылья, оставшиеся от чужого полёта"),
        ("action", "то, что дарит небо смертному"),
    )},
    "minecraft:dragon_egg": {"a": (
        ("contrast", "яйцо, из него уже вылупилась легенда"),
        ("number", "последнее яйцо последнего дракона"),
    )},
    "minecraft:experience_bottle": {"a": (
        ("metaphor", "пузырёк чужой накопленной мудрости"),
        ("action", "зелье, что шепчет, если разбить"),
    )},
    "minecraft:saddle": {
        "a": (
            ("metaphor", "пропуск на чужой хребет"),
            ("metaphor", "кожаный трон для наездника"),
        ),
        "i": (
            ("metaphor", "пропуском на чужой хребет"),
            ("metaphor", "кожаным троном для наездника"),
        ),
    },
    "minecraft:name_tag": {
        "a": (
            ("person", "бирку, что безмолвна, а имя всякому даст"),
            ("action", "ярлык, что дарит имена"),
        ),
        "i": (
            ("person", "биркой, что безмолвна, а имя даст"),
            ("action", "ярлыком, что дарит имена"),
        ),
    },
    "minecraft:bone": {
        "a": (
            ("metaphor", "белый мосл чужого скелета"),
            ("action", "то, что пёс закапывает на чёрный день"),
        ),
        "i": (
            ("metaphor", "белым мослом чужого скелета"),
            ("action", "костью, что пёс припрятал на чёрный день"),
        ),
    },
    "minecraft:string": {"a": (
        ("metaphor", "тонкую песню голодного паука"),
        ("action", "нить, что спрядена на погиболь мухам"),
    )},
    "minecraft:gunpowder": {"a": (
        ("metaphor", "чёрное сердце любого взрыва"),
        ("action", "серую пыль, что говорит языком грома"),
    )},
    "minecraft:slime_ball": {"a": (
        ("contrast", "зелёную каплю, что пружинит"),
        ("person", "отрыжку самого скромного слизня"),
    )},
    "minecraft:leather": {"a": (
        ("metaphor", "шкуру, что носила кого-то живого"),
        ("action", "то, что стало бронёй бедняка"),
    )},
    "minecraft:feather": {"a": (
        ("metaphor", "письмо, что обронила курица"),
        ("contrast", "лёгкий сувенир от птицы"),
    )},
    "minecraft:paper": {"a": (
        ("action", "тростник, что стал страницей"),
        ("contrast", "белый лист, что боится огня"),
    )},
    "minecraft:book": {"a": (
        ("metaphor", "переплёт, полный пустых страниц"),
        ("neg", "мудрость, что ещё ничего не знает"),
    )},
    "minecraft:brick": {"a": (
        ("action", "глину, что закалил огонь"),
        ("metaphor", "красный брусик из печных недр"),
    )},
    "minecraft:nether_brick": {"a": (
        ("metaphor", "кирпич из адской кладки"),
        ("contrast", "брусик, что закалялся в преисподней"),
    )},
    "minecraft:clay_ball": {"a": (
        ("metaphor", "комок, ждущий гончарного круга"),
        ("contrast", "мягкий шар, что станет твёрдым в огне"),
    )},
    "minecraft:wheat": {
        "a": (
            ("contrast", "хлеб, что ещё не хлеб"),
            ("metaphor", "златые колосья, что станут хлебом"),
        ),
        "i": (
            ("contrast", "хлебом, что ещё не хлеб"),
            ("metaphor", "златыми колосьями грядущего хлеба"),
        ),
    },
    "minecraft:sugar": {"a": (
        ("action", "сладость, выжатую из стеблей"),
        ("contrast", "белый песок, что не с моря"),
    )},
    "minecraft:egg": {"a": (
        ("metaphor", "загадку в хрупкой скорлупе"),
        ("contrast", "курятник, спрятанный в одном шарике"),
    )},
    "minecraft:flint": {"a": (
        ("action", "камешек, что рождает искру"),
        ("contrast", "осколок, что не боится стали"),
    )},
    "minecraft:stick": {"a": (
        ("metaphor", "начало всех копий и лопат"),
        ("notab", "простую палку, а не дубину и не тростинку"),
    )},
    "minecraft:torch": {"a": (
        ("metaphor", "первого друга всякого заблудившегося"),
        ("contrast", "огонёк, что не боится дождя"),
    )},
    "minecraft:lantern": {"a": (
        ("metaphor", "железный домик для огонька"),
        ("neg", "свет, что не задует никакой ветер"),
    )},
    "minecraft:compass": {"a": (
        ("person", "стрелку, что помнит дом"),
        ("action", "иглу, что всегда смотрит на место рождения"),
    )},
    "minecraft:clock": {"a": (
        ("metaphor", "время, спрятанное в золотой корпус"),
        ("action", "циферблат, что тикает в кармане"),
    )},
    "minecraft:map": {"a": (
        ("action", "бумагу, что запоминает землю"),
        ("contrast", "лист, где весь мир уместился в кармане"),
    )},
    "minecraft:shears": {
        "a": (
            ("number", "два конца, два кольца, гвоздик посередине"),
            ("action", "инструмент, что стрижёт овец и листву"),
        ),
        "i": (
            ("number", "двумя концами, двумя кольцами, гвоздиком посередине"),
            ("action", "инструментом, что стрижёт овец"),
        ),
    },
    "minecraft:flint_and_steel": {
        "a": (
            ("action", "железку, что рождает первый огонь"),
            ("contrast", "искру, что живёт в кармане"),
        ),
        "i": (
            ("action", "железкой, что рождает первый огонь"),
            ("contrast", "искрой, что живёт в кулаке"),
        ),
    },
    "minecraft:fishing_rod": {"a": (
        ("neg", "гибкий прут, что ловит не птиц"),
        ("person", "удочку для самых терпеливых"),
    )},
    "minecraft:bow": {"a": (
        ("metaphor", "деревянную дугу с песней тетивы"),
        ("action", "дугу, что плюётся стрелами"),
    )},
    "minecraft:arrow": {"a": (
        ("number", "перо, палка и жало в одном"),
        ("action", "жало, что летит по ветру"),
    )},
    "minecraft:shield": {"a": (
        ("metaphor", "верного деревянного телохранителя в левой руке"),
        ("action", "доску, что принимает удары на себя"),
    )},
    "minecraft:bucket": {
        "a": (
            ("metaphor", "железную утробу для жидкого"),
            ("action", "пустую тару, что ждёт наполнения"),
        ),
        "i": (
            ("metaphor", "железной утробой для жидкого"),
            ("action", "пустой тарой, что ждёт наполнения"),
        ),
    },
    "minecraft:glass_bottle": {"a": (
        ("metaphor", "пузатую стеклянную капсулу алхимика"),
        ("contrast", "хрупкий сосуд для зелий и бед"),
    )},
    "minecraft:snowball": {"a": (
        ("contrast", "зимний снаряд, что тает в полёте"),
        ("action", "комок, что просится в цель"),
    )},
    # --- еда ---
    "minecraft:bread": {"a": (
        ("metaphor", "колос, что стал ломтем"),
        ("action", "хлеб, что гонит прочь голод"),
    )},
    "minecraft:apple": {
        "a": (
            ("metaphor", "наливное солнце из кроны"),
            ("action", "плод, что падает, когда созреет"),
        ),
        "i": (
            ("metaphor", "наливным солнцем из кроны"),
            ("action", "плодом, что падает, когда созреет"),
        ),
    },
    "minecraft:golden_apple": {"a": (
        ("metaphor", "яблоко, отлитое из солнца"),
        ("number", "восемь слитков золота в одном яблоке"),
    )},
    "minecraft:enchanted_golden_apple": {"a": (
        ("contrast", "плод, что светится чужими чарами"),
        ("contrast", "редкий плод, что дороже короны"),
    )},
    "minecraft:cooked_beef": {"a": (
        ("action", "мясо, что побывало на углях"),
        ("metaphor", "стейк, что шипел на огне"),
    )},
    "minecraft:cooked_porkchop": {"a": (
        ("action", "свинину, что побывала на огне"),
        ("contrast", "отбивную, чей повар - костёр"),
    )},
    "minecraft:cooked_chicken": {"a": (
        ("action", "птицу, что просилась на угли"),
        ("metaphor", "курицу в золотистой корке"),
    )},
    "minecraft:cooked_mutton": {"a": (
        ("action", "бараний бок с углей"),
        ("contrast", "мясо, что огонь сделал мягче"),
    )},
    "minecraft:cooked_rabbit": {"a": (
        ("action", "нежную крольчатину с углей"),
        ("metaphor", "маленький пир из одного зверька"),
    )},
    "minecraft:cooked_cod": {"a": (
        ("action", "белую рыбу с решётки"),
        ("contrast", "рыбу, что уже не уплывёт"),
    )},
    "minecraft:cooked_salmon": {"a": (
        ("action", "розовую рыбу с углей"),
        ("metaphor", "лосося в персиковой шкуре"),
    )},
    "minecraft:baked_potato": {"a": (
        ("action", "клубень, запечённый в углях"),
        ("metaphor", "овощ, что парился в собственной шкуре"),
    )},
    "minecraft:carrot": {
        "a": (
            ("person", "красную девицу из темницы, коса наружу"),
            ("notab", "рыжий корень, а не фрукт и не ягоду"),
        ),
        "i": (
            ("person", "красной девицей из темницы"),
            ("notab", "рыжим корнем, а не фруктом и не ягодой"),
        ),
    },
    "minecraft:potato": {"a": (
        ("metaphor", "земляное яблоко бедного мужика"),
        ("contrast", "хлеб бедняка, что растёт в грязи"),
    )},
    "minecraft:beetroot": {"a": (
        ("metaphor", "бордовое сердце горячего борща"),
        ("action", "корень, что красит руки и суп"),
    )},
    "minecraft:melon_slice": {"a": (
        ("number", "красную дольку полосатого исполина"),
        ("metaphor", "сладкий ломоть полосатой горы"),
    )},
    "minecraft:sweet_berries": {"a": (
        ("contrast", "сладость с колючим характером"),
        ("action", "ягоды с куста, что кусается"),
    )},
    "minecraft:glow_berries": {"a": (
        ("contrast", "ягоды, что светятся в темноте"),
        ("metaphor", "живые фонарики пещерных лиан"),
    )},
    "minecraft:cookie": {"a": (
        ("number", "кругляш с тёмными крапинками"),
        ("contrast", "сладкий блинчик, что хрустит"),
    )},
    "minecraft:pumpkin_pie": {"a": (
        ("metaphor", "осень, запечённую в пирог"),
        ("action", "тыкву, что пустили на праздник"),
    )},
    "minecraft:honey_bottle": {"a": (
        ("metaphor", "стеклянную бутылочку пойманного лета"),
        ("contrast", "сладость, что течёт медленнее времени"),
    )},
    "minecraft:milk_bucket": {"a": (
        ("metaphor", "белую реку в железных берегах"),
        ("action", "то, что корова даёт за терпение"),
    )},
    "minecraft:mushroom_stew": {"a": (
        ("metaphor", "миску тёмного лесного варева"),
        ("action", "суп из того, что растёт под дождём"),
    )},
    "minecraft:rabbit_stew": {"a": (
        ("metaphor", "миску настоящей охотничьей удачи"),
        ("contrast", "рагу, где кролик - главный гость"),
    )},
    "minecraft:beetroot_soup": {"a": (
        ("metaphor", "миску густого бордового зелья"),
        ("contrast", "суп цвета заката, но из грядки"),
    )},
    "minecraft:suspicious_stew": {"a": (
        ("neg", "рагу, после него чудится всякое"),
        ("person", "угощение с двойным дном"),
    )},
    "minecraft:dried_kelp": {"a": (
        ("contrast", "морскую траву, высушенную до хруста"),
        ("notab", "перекус морехода, а не рыбу и не траву"),
    )},
    "minecraft:rotten_flesh": {"a": (
        ("person", "ужин, что начал жить своей жизнью"),
        ("contrast", "обед, что пережил своего едока"),
    )},
    "minecraft:spider_eye": {"a": (
        ("neg", "глаз, что смотрел из паутины"),
        ("contrast", "сладость, что глядит вслед"),
    )},
    "minecraft:chorus_fruit": {"a": (
        ("action", "плод, что путает ноги едока"),
        ("neg", "фрукт - съел и очутился невесть где"),
    )},
    "minecraft:poisonous_potato": {"a": (
        ("contrast", "картофелину с дурным глазом"),
        ("neg", "клубень, что сыт, да коварен"),
    )},
    "minecraft:pufferfish": {"a": (
        ("contrast", "рыбу, что раздувается от злости"),
        ("neg", "колючий шар, что не для робких желудков"),
    )},
    "minecraft:tropical_fish": {"a": (
        ("metaphor", "рыбку в тропических красках"),
        ("contrast", "пёструю малютку коралловых садов"),
    )},
    "minecraft:golden_carrot": {"a": (
        ("number", "восемь самородков в одном корнеплоде"),
        ("contrast", "морковь, что дороже серебра"),
    )},
    # --- зачаровываемое (enchanted_item) ---
    "minecraft:diamond_sword": {"a": (
        ("contrast", "клинок, что бреет камень"),
        ("metaphor", "грозу глубин в твоей руке"),
    )},
    "minecraft:diamond_pickaxe": {"a": (
        ("action", "зубило, что грызёт недра"),
        ("neg", "единственную кирку для чёрного стекла"),
    )},
    "minecraft:iron_sword": {"a": (
        ("metaphor", "простой честный клинок мастерового"),
        ("contrast", "железную правду любого спора"),
    )},
    "minecraft:iron_pickaxe": {"a": (
        ("metaphor", "верную подругу всякого шахтёра"),
        ("action", "кирку, что открывает глубины"),
    )},
    "minecraft:crossbow": {"a": (
        ("metaphor", "механическую дугу с железным сердцем"),
        ("action", "мастеровую, что плюётся болтами"),
    )},
    "minecraft:trident": {"a": (
        ("number", "три жала на одном древке"),
        ("metaphor", "громовые вилы морских владык"),
    )},
    "minecraft:diamond_helmet": {"a": (
        ("metaphor", "алмазную скорлупу для головы"),
        ("contrast", "шапку, что дороже всей головы"),
    )},
    "minecraft:diamond_chestplate": {"a": (
        ("metaphor", "сияющую броню для груди"),
        ("number", "восемь слёз земли, ставшие панцирем"),
    )},
    "minecraft:diamond_leggings": {"a": (
        ("metaphor", "алмазную защиту для ног"),
        ("neg", "штаны, что не промокнут и не порвутся"),
    )},
    "minecraft:diamond_boots": {"a": (
        ("metaphor", "алмазные башмаки отчаянного храбреца"),
        ("action", "обувь, что топчет любые шипы"),
    )},
    "minecraft:netherite_sword": {"a": (
        ("contrast", "клинок, что ковали в аду"),
        ("neg", "меч, что не ржавеет и не горит"),
    )},
    "minecraft:golden_axe": {
        "a": (
            ("metaphor", "золотое рубило суетного богача"),
            ("contrast", "парадное рубило богатого мота"),
        ),
        "i": (
            ("metaphor", "золотым рубилом суетного богача"),
            ("contrast", "парадным рубилом богатого мота"),
        ),
    },
    # --- длительное использование (using_item) ---
    "minecraft:spyglass": {"a": (
        ("action", "трубу, что приближает горизонт"),
        ("neg", "глаз, что видит дальше любого глаза"),
    )},
    "minecraft:goat_horn": {"a": (
        ("person", "рог, что кричит эхом гор"),
        ("person", "рог, что перекликается с горами"),
    )},
    "minecraft:iron_spear": {"a": (
        ("metaphor", "железное жало на длинной рукояти"),
        ("contrast", "копьё, что бьёт дальше меча"),
    )},
    # --- рыболовный лут (fishing_rod_hooked) ---
    "minecraft:cod": {"a": (
        ("metaphor", "простую рыбу холодных вод"),
        ("action", "усатую скромную добычу рыбака"),
    )},
    "minecraft:salmon": {"a": (
        ("metaphor", "серебристую рыбу с розовой душой"),
        ("action", "рыбу, что плывёт против течения"),
    )},
    "minecraft:enchanted_book": {"a": (
        ("contrast", "книгу, что уже тронули чары"),
        ("metaphor", "страницы с вплетённым заклятием"),
    )},
    "minecraft:nautilus_shell": {"a": (
        ("metaphor", "спиральный домик древнего моллюска"),
        ("number", "раковину, что помнит миллион лет"),
    )},
    "minecraft:bowl": {"a": (
        ("metaphor", "пустую посуду для варева"),
        ("contrast", "миску, что ждёт горячего"),
    )},
    "minecraft:leather_boots": {"a": (
        ("metaphor", "обувь странника из чужой кожи"),
        ("neg", "башмаки, что не спасут от зубов"),
    )},
    # --- инструменты item_used_on_block (творительный - «обтёси ... топором») ---
    "minecraft:wooden_axe": {
        "a": (
            ("metaphor", "самое первое рубило человечества"),
            ("action", "топор, с него всё началось"),
        ),
        "i": (
            ("metaphor", "самым первым рубилом человечества"),
            ("action", "топором, с него всё началось"),
        ),
    },
    "minecraft:stone_axe": {
        "a": (
            ("number", "рубило с каменным зубом"),
            ("action", "топор, что помнит первую искру"),
        ),
        "i": (
            ("number", "рубилом с каменным зубом"),
            ("action", "топором, что помнит первую искру"),
        ),
    },
    "minecraft:iron_axe": {
        "a": (
            ("metaphor", "надёжное железное рубило кузнеца"),
            ("action", "топор, что валит за один замах"),
        ),
        "i": (
            ("metaphor", "надёжным железным рубилом кузнеца"),
            ("action", "топором, что валит за один замах"),
        ),
    },
    "minecraft:diamond_axe": {
        "a": (
            ("contrast", "алмазное рубило ловкого мастера"),
            ("neg", "топор, что не щадит лесов"),
        ),
        "i": (
            ("contrast", "алмазным рубилом ловкого мастера"),
            ("neg", "топором, что не щадит лесов"),
        ),
    },
    "minecraft:netherite_axe": {
        "a": (
            ("contrast", "тёмное рубило из адских глубин"),
            ("neg", "топор, что не боится ни пламени, ни лет"),
        ),
        "i": (
            ("contrast", "тёмным рубилом из адских глубин"),
            ("neg", "топором, что не боится пламени"),
        ),
    },
    "minecraft:wooden_hoe": {
        "a": (
            ("metaphor", "простую мотыгу первого хлебороба"),
            ("action", "палку, что научилась копать"),
        ),
        "i": (
            ("metaphor", "простой мотыгой первого хлебороба"),
            ("action", "палкой, что научилась копать"),
        ),
    },
    "minecraft:iron_hoe": {
        "a": (
            ("metaphor", "верную железную мотыгу пахаря"),
            ("action", "мотыгу, что будит спящую землю"),
        ),
        "i": (
            ("metaphor", "верной железной мотыгой пахаря"),
            ("action", "мотыгой, что будит землю"),
        ),
    },
    "minecraft:diamond_hoe": {
        "a": (
            ("contrast", "алмазную мотыгу праздного богача"),
            ("action", "мотыгу, что пашет как по маслу"),
        ),
        "i": (
            ("contrast", "алмазной мотыгой праздного богача"),
            ("action", "мотыгой, что пашет как по маслу"),
        ),
    },
    "minecraft:iron_shovel": {
        "a": (
            ("metaphor", "верную железную лопату землекопа"),
            ("action", "лопату, что копает глубже слов"),
        ),
        "i": (
            ("metaphor", "верной железной лопатой землекопа"),
            ("action", "лопатой, что копает глубже слов"),
        ),
    },
    "minecraft:honeycomb": {
        "a": (
            ("number", "шестиугольники из пчелиной кладовой"),
            ("action", "воск, что запечатывает медовые тайны"),
        ),
        "i": (
            ("number", "сотами из пчелиной кладовой"),
            ("action", "воском, что запечатывает тайны"),
        ),
    },
    # --- изнашиваемое (item_durability_changed) ---
    "minecraft:carrot_on_a_stick": {"a": (
        ("action", "приманку для борзой свиньи"),
        ("contrast", "лакомство на удочке для скакуна"),
    )},
    "minecraft:warped_fungus_on_a_stick": {"a": (
        ("contrast", "синюю поганку на удочке"),
        ("action", "приманку для лавового ходока"),
    )},
    "minecraft:golden_sword": {"a": (
        ("contrast", "парадный клинок ленивых королей"),
        ("neg", "меч красивый, но недолговечный"),
    )},
    "minecraft:golden_pickaxe": {"a": (
        ("contrast", "золотое зубило богатого мота"),
        ("action", "кирку, что тупится быстрее, чем блестит"),
    )},
    "minecraft:golden_shovel": {"a": (
        ("contrast", "золотую лопату богатого мота"),
        ("action", "лопату, что блистает, да быстро гнётся"),
    )},
    "minecraft:golden_hoe": {"a": (
        ("contrast", "золотую мотыгу праздного богача"),
        ("action", "мотыгу, что пашет лишь для вида"),
    )},
    "minecraft:wooden_sword": {"a": (
        ("neg", "меч, что скорее ветка"),
        ("number", "первый клинок каждого новичка"),
    )},
    "minecraft:wooden_pickaxe": {"a": (
        ("metaphor", "первое зубило всякого копателя"),
        ("contrast", "кирку, что боится глубокого камня"),
    )},
    "minecraft:wooden_shovel": {"a": (
        ("metaphor", "лопату самых первых землекопов"),
        ("action", "совок, что умрёт на первом камне"),
    )},
    # --- вёдра (filled_bucket) ---
    "minecraft:water_bucket": {"a": (
        ("metaphor", "железную утробу, полную реки"),
        ("action", "то, чем зачерпывают жизнь"),
    )},
    "minecraft:lava_bucket": {"a": (
        ("metaphor", "утробу с жидким огнём"),
        ("contrast", "ведро, что горячее любой печи"),
    )},
    "minecraft:powder_snow_bucket": {"a": (
        ("neg", "ведро снега, что притворяется пустым"),
        ("contrast", "хрупкую белизну, что глотает путников"),
    )},
    "minecraft:axolotl_bucket": {"a": (
        ("person", "аквариум с улыбчивой розовой нежностью"),
        ("action", "воду, где живёт улыбка"),
    )},
    "minecraft:cod_bucket": {"a": (
        ("metaphor", "аквариум с усатым жильцом"),
        ("number", "одну рыбу в железной квартире"),
    )},
    "minecraft:salmon_bucket": {"a": (
        ("metaphor", "аквариум с упрямой речной рыбой"),
        ("contrast", "упрямую пловчиху в железной реке"),
    )},
    "minecraft:pufferfish_bucket": {"a": (
        ("person", "аквариум с колючим характером"),
        ("contrast", "ведро, где плавает обида"),
    )},
    "minecraft:tropical_fish_bucket": {"a": (
        ("metaphor", "аквариум с тропическими красками"),
        ("number", "пёструю малютку в железном море"),
    )},
    "minecraft:tadpole_bucket": {"a": (
        ("contrast", "аквариум с будущей жабой"),
        ("action", "хвост, что ещё не стал жабой"),
    )},
}

# Образные прозвища колоритных врагов для подсказок player_killed_entity
# (фидбек юзера: «можно местами образно, но понятнее, чем блоки; не
# переусердствуй» - потому прозвище держит 1-2 узнаваемых признака и
# выпадает лишь с шансом, остальное время существо названо прямо).
# Расширено по фидбеку юзера «покажи всё величие русского языка»:
# 15 -> 60 - и врагов, и мирного зверья; самотест требует прозвища
# только для мобов из пула MOBS
POETIC_ENT = {
    # id: (именительный, винительный)
    # --- враждебные ---
    "minecraft:husk": ("страж песков", "стража песков"),
    "minecraft:stray": ("зимний стрелок", "зимнего стрелка"),
    "minecraft:bogged": ("стрелок трясин", "стрелка трясин"),
    "minecraft:drowned": ("гость со дна", "гостя со дна"),
    "minecraft:creeper": ("тихий гром в зелёной шкуре",
                          "тихий гром в зелёной шкуре"),
    "minecraft:ghast": ("белый плачущий призрак", "белого плачущего призрака"),
    "minecraft:blaze": ("огненный дух", "огненного духа"),
    "minecraft:witch": ("злая знахарка", "злую знахарку"),
    "minecraft:enderman": ("тень с фиолетовыми глазами",
                           "тень с фиолетовыми глазами"),
    "minecraft:phantom": ("крылатый кошмар ночи", "крылатого кошмара ночи"),
    "minecraft:guardian": ("колючий глаз глубин", "колючий глаз глубин"),
    "minecraft:wither_skeleton": ("чёрный рыцарь углей",
                                  "чёрного рыцаря углей"),
    "minecraft:evoker": ("злой чародей", "злого чародея"),
    "minecraft:breeze": ("ветреный проказник", "ветреного проказника"),
    "minecraft:creaking": ("скрипучая тень леса", "скрипучую тень леса"),
    "minecraft:zombie": ("бездушный ходок", "бездушного ходока"),
    "minecraft:skeleton": ("костяной стрелок", "костяного стрелка"),
    "minecraft:spider": ("ткач теней", "ткача теней"),
    "minecraft:cave_spider": ("малый ядовитый ткач", "малого ядовитого ткача"),
    "minecraft:slime": ("зелёное желе", "зелёное желе"),
    "minecraft:magma_cube": ("прыгучий уголёк преисподней",
                             "прыгучего уголька преисподней"),
    "minecraft:silverfish": ("книжный червь из камня",
                             "книжного червя из камня"),
    "minecraft:endermite": ("крадущийся огонёк", "крадущегося огонька"),
    "minecraft:zombified_piglin": ("гнилой свинопас", "гнилого свинопаса"),
    "minecraft:piglin": ("золотоискатель с клыками",
                         "золотоискателя с клыками"),
    "minecraft:piglin_brute": ("громила с золотым топором",
                               "громилу с золотым топором"),
    "minecraft:hoglin": ("кабан железных чащ", "кабана железных чащ"),
    "minecraft:shulker": ("живой ларец", "живой ларец"),
    "minecraft:ravager": ("рогатая осада", "рогатую осаду"),
    "minecraft:vindicator": ("мрачный палач", "мрачного палача"),
    "minecraft:pillager": ("грабитель с арбалетом", "грабителя с арбалетом"),
    "minecraft:vex": ("злая искра", "злую искру"),
    "minecraft:zoglin": ("гниющий кабан", "гниющего кабана"),
    "minecraft:parched": ("иссохшая мумия", "иссохшую мумию"),
    "minecraft:sulfur_cube": ("кислый куб", "кислый куб"),
    "minecraft:zombie_villager": ("мёртвый сосед", "мёртвого соседа"),
    # --- мирные (колоритные) ---
    "minecraft:mooshroom": ("корова в грибном платке",
                            "корову в грибном платке"),
    "minecraft:squid": ("восьмирукий мореход", "восьмирукого морехода"),
    "minecraft:glow_squid": ("глубинный фонарь", "глубинный фонарь"),
    "minecraft:dolphin": ("морской забавник", "морского забавника"),
    "minecraft:polar_bear": ("хозяин льдов", "хозяина льдов"),
    "minecraft:panda": ("бамбуковый лежебока", "бамбукового лежебоку"),
    "minecraft:llama": ("шерстяной странник", "шерстяного странника"),
    "minecraft:wolf": ("серый брат ночи", "серого брата ночи"),
    "minecraft:fox": ("рыжая плутовка", "рыжую плутовку"),
    "minecraft:bee": ("полосатая труженица", "полосатую труженицу"),
    "minecraft:goat": ("бодливый горец", "бодливого горца"),
    "minecraft:rabbit": ("трусишка под кустом", "трусишку под кустом"),
    "minecraft:sheep": ("облачное руно", "облачное руно"),
    "minecraft:cow": ("мычащая кормилица", "мычащую кормилицу"),
    "minecraft:pig": ("розовый пухляк", "розового пухляка"),
    "minecraft:chicken": ("квохчущая хозяйка двора",
                         "квохчущую хозяйку двора"),
    "minecraft:turtle": ("панцирный странник", "панцирного странника"),
    "minecraft:armadillo": ("свернувшийся клубок", "свернувшийся клубок"),
    "minecraft:axolotl": ("розовая улыбочка", "розовую улыбочку"),
    "minecraft:allay": ("крылатый помощник", "крылатого помощника"),
    "minecraft:sniffer": ("древний садовник", "древнего садовника"),
    "minecraft:bat": ("кожистый летун", "кожистого летуна"),
    "minecraft:camel": ("корабль сухих морей", "корабль сухих морей"),
}


def _with(ins):
    """Предлог «с» с алломорфом «со»: «скелетом» -> «со скелетом",
    «крипером» -> «с крипером» (со - перед с/з + согласная в начале
    первого слова: со скелетом, со страйдером, со злобным, со снежным)."""
    head = ins.split(" ", 1)[0]
    if head[0] in "сз" and len(head) > 1 and head[1] not in "аеёиоуыэюя":
        return "со " + ins
    return "с " + ins


def _item_acc(iid):
    e = RU_ITEM[iid]
    return e.get("a", e["n"])


def _block_acc(bid):
    e = RU_BLOCK[bid]
    return e.get("a", e["n"])


def _riddle_pick(rng, variants, max_words):
    """Случайная загадка из (тег, текст)-вариантов с бюджетом слов.
    Двойные подсказки («предмет + блок»: алай, item_used_on_block,
    интеракции, суффиксы «(держа X)») просят КОРОТКОЕ «колено» <=
    max_words; одиночные подсказки берут любое. Если бюджет не
    выдерживает ни один вариант (не должно случаться - самотест
    требует первое колено <= 7 слов), берётся самый короткий."""
    ok = [text for _tag, text in variants if len(text.split()) <= max_words]
    if ok:
        return rng.choice(ok)
    return min((text for _tag, text in variants),
               key=lambda t: len(t.split()))


def _riddle_block(rng, bid, max_words=99):
    """Случайная загадка-описание блока (винительный падеж); max_words -
    бюджет для двойных подсказок (см. _riddle_pick)."""
    return _riddle_pick(rng, RIDDLE_BLOCKS[bid], max_words)


def _riddle_item(rng, iid, max_words=99):
    """Случайная загадка-описание предмета (винительный падеж)."""
    return _riddle_pick(rng, RIDDLE_ITEMS[iid]["a"], max_words)


def _riddle_item_i(rng, iid, max_words=99):
    """Загадка-описание предмета в творительном («обтёси ... топором»)."""
    return _riddle_pick(rng, RIDDLE_ITEMS[iid]["i"], max_words)


# ---------------------------------------------------------------------------
# Достижимость item_used_on_block: пары «инструмент -> валидные блоки»
# (аудит 26.2). Блок выбирается ТОЛЬКО из списка валидных для инструмента -
# иначе условие невыполнимо (например, мотыга ничего не делает с камнем).
# ---------------------------------------------------------------------------

AXE_LOGS = [
    "minecraft:oak_log", "minecraft:spruce_log", "minecraft:birch_log",
    "minecraft:jungle_log", "minecraft:acacia_log",
    "minecraft:dark_oak_log", "minecraft:mangrove_log",
    "minecraft:cherry_log", "minecraft:pale_oak_log",
]
HOE_SOILS = ["minecraft:dirt", "minecraft:grass_block",
             "minecraft:rooted_dirt", "minecraft:coarse_dirt"]
SHOVEL_SOILS = ["minecraft:grass_block", "minecraft:dirt",
                "minecraft:coarse_dirt"]

TOOL_TARGETS = {}
for _mat in ("wooden", "stone", "iron", "golden", "diamond", "netherite"):
    TOOL_TARGETS["minecraft:%s_axe" % _mat] = AXE_LOGS       # обтёсывание
for _mat in ("wooden", "iron", "diamond"):
    TOOL_TARGETS["minecraft:%s_hoe" % _mat] = HOE_SOILS       # вспашка
TOOL_TARGETS["minecraft:iron_shovel"] = SHOVEL_SOILS          # тропа
TOOL_TARGETS["minecraft:shears"] = ["minecraft:pumpkin"]      # вырезание
TOOL_TARGETS["minecraft:flint_and_steel"] = list(PLACEABLE_BLOCKS)  # огонь
TOOL_TARGETS["minecraft:honeycomb"] = ["minecraft:copper_block"]     # воск

# (порядок = оси -> мотыги -> лопата -> ножницы -> огниво -> соты)
TOOL_ITEMS = list(TOOL_TARGETS)


# ---------------------------------------------------------------------------
# Достижимость player_interacted_with_entity: пары «сущность -> предмет»
# (аудит 26.2). Предмет выбирается ТОЛЬКО валидный для сущности -
# «поменять местами» (например, пшеница на крипера) нельзя.
# ПОЛНЫЙ РАЦИОН пар (аудит 26.2 по фидбеку «козёл ест подсолнух?»):
#   бирка  -> любой моб из INTERACTABLE, но ТОЛЬКО с ЗАДАННЫМ именем -
#             см. _name_tag_custom_name: безымянная бирка в 26.2 НЕ
#             работает (NameTagItem без custom_name возвращает PASS, а
#             триггер вызывается лишь на InteractionResult$Success -
#             сверено по байткоду ServerGamePacketListenerImpl);
#   ведро  -> корова (доение пустым ведром - молоко);
#   пшеница-> корова / овца / козёл (кормление: все три едят пшеницу -
#             она же еда разведения; добывается фермой и лежит в луте);
#   морковь-> свинья (кормление и приманивание);
#   яблоко -> лошадь (кормление: лечит и растит норов; яблоко - с дуба
#             или из лута);
#   кость  -> волк (приручение);
#   ножницы-> овца (стрижка);
#   седло  -> лошадь (осёдлка прирученной; седло - из лута).
# ---------------------------------------------------------------------------

_INTERACT_ITEMS = {
    "minecraft:name_tag": list(INTERACTABLE),   # бирка работает на всех
    "minecraft:bucket": ["minecraft:cow"],      # доение
    "minecraft:wheat": ["minecraft:cow", "minecraft:sheep",
                        "minecraft:goat"],       # кормление
    "minecraft:carrot": ["minecraft:pig"],
    "minecraft:apple": ["minecraft:horse"],
    "minecraft:bone": ["minecraft:wolf"],
    "minecraft:shears": ["minecraft:sheep"],    # стрижка
    "minecraft:saddle": ["minecraft:horse"],    # седловка
}
_INTERACT_PAIRS = [(ent, it) for it, ents in _INTERACT_ITEMS.items()
                   for ent in ents]


def _pretty(s):
    """Имя с заглавной буквы (как {N} в заголовках ачивек)."""
    return s[0].upper() + s[1:] if s else s


def _name_tag_custom_name(conds, dim_name):
    """ФИКС достижимости (фидбек: «нареки моба биркой, что безмолвна» -
    в ванили НЕВОЗМОЖНО применить бирку с ПУСТЫМ именем). Клик
    безымянной биркой по мобу ничего не делает: NameTagItem проверяет
    custom_name и без него возвращает PASS, а триггер
    player_interacted_with_entity вызывается из ServerGamePacket
    ListenerImpl только на InteractionResult$Success (байткод 26.2:
    instanceof Success -> ifeq мимо вызова trigger) - критерий без
    имени на бирке никогда бы не сработал.

    Решение: item-условие получает компонент custom_name с КОНКРЕТНЫМ
    текстом - именем измерения (rand_advancements уже знает его).
    Формат сверен по байткоду 26.2: ItemPredicate имеет ровно три поля
    (items / count / components:DataComponentMatchers); components -
    ТОЧНОЕ сравнение значения компонента (карта «id -> значение»,
    Objects.equals), частичного типа для custom_name в реестре
    DataComponentPredicates НЕТ (там damage/enchantments/potions/...).
    Наковальня пишет custom_name как Component.literal(строка)
    (байткод AnvilMenu), поэтому {"text": ...} с пустым стилем совпадает
    ТОЧНО: игрок переименовывает бирку на наковальне в <ИмяМира> (оно же
    стоит в заголовке видимой ачивки) и кликает по мобу - достижимо."""
    if not dim_name:
        return
    it = conds.get("item")
    if isinstance(it, dict) and it.get("items") == "minecraft:name_tag":
        it["components"] = {"minecraft:custom_name": {
            "text": _pretty(dim_name)}}


def _custom_name_text(conds):
    """Текст custom_name из item-условия (наш генератор пишет плоский
    {"text": ...}; bare-строку тоже понимаем)."""
    it = conds.get("item")
    if not isinstance(it, dict):
        return None
    comp = (it.get("components") or {}).get("minecraft:custom_name")
    if isinstance(comp, str):
        return comp
    if isinstance(comp, dict) and isinstance(comp.get("text"), str):
        return comp["text"]
    return None

# ---------------------------------------------------------------------------
# Пул триггеров скрытой ачивки: (trigger, генератор условий) - 2-tuple;
# подсказки БОЛЬШЕ не хранятся в пуле, а строятся из РЕАЛЬНЫХ conditions
# JSON критерия (см. _hint_for / _HINT_BUILDERS выше по вызову). Генератор
# возвращает conditions БЕЗ ключа player; если ему нужен дополнительный
# player-predicate (например, vehicle у started_riding), он кладёт его в
# conditions["player"] - модуль объединит его с условием «не в этом
# измерении». Все имена триггеров сверены с CriteriaTriggers.class
# клиентского И серверного jar 26.2.
# ---------------------------------------------------------------------------

def _ent_pred(etype):
    """ContextAwarePredicate: сущность указанного типа (26.2: minecraft:entity_type)."""
    return {"condition": "minecraft:entity_properties", "entity": "this",
            "predicate": {"minecraft:entity_type": etype}}


def _loc_block_pred(block):
    """location_check с предикатом блока (для placed_block / allay)."""
    return {"condition": "minecraft:location_check",
            "predicate": {"block": {"blocks": block}}}


# Фидбек юзера «условия пусть будут не зависимы - сделать 2-3 вещи не
# одновременно, а в любое время»: доп. player-условия (эффект /
# предмет в руке / верховая езда), требовавшие ОДНОВРЕМЕННОСТИ с
# событием триггера, УДАЛЕНЫ ПОЛНОСТЬЮ (прежде - _extra_player_cond с
# шансом 15%). Внутренние условия самого триггера (взрыв + падение у
# fall_after_explosion, флаги is_on_ground у placed_block/using_item,
# vehicle у started_riding) - ЧАСТЬ ОДНОГО действия и остаются.

# Соединители подсказок нескольких критериев в одну фразу: подсказка
# скрытой ачивки должна читаться как ЗАКЛИНАНИЕ/ПРИСКАЗКА (фидбек
# юзера). Расширено по фидбеку «покажи всё величие русского языка»:
# 10 -> 30 - пора и присказки, и полуночный шёпот, и уговоры дорог
HINT_JOINERS = [
    " и ", " и вдобавок ", ", затем ", ", а ещё ",
    " - и только после этого ", " ... и ... ",
    " ... и лишь тогда ... ",
    " - как велит древний уговор - ",
    " - так заведено в чужих мирах - ",
    " - покуда не сбудется - ",
    " и, не мешкая, ",
    " и следом ",
    ", вслед за тем, ",
    ", а после - ",
    " - и лишь затем - ",
    " ... затем ... ",
    " ... а после ... ",
    " - по уговору трёх дорог - ",
    " - как водится у странников - ",
    " - как велит старая примета - ",
    " - как шепчет полночь - ",
    " - покуда звёзды не сложатся - ",
    " - и мир услышит - ",
    " - и небо отзовётся - ",
    " - там, где кончается карта, - ",
    " - за краем тропы - ",
    " - по велению рассвета - ",
    " - под чужими звёздами - ",
    ", а как стемнеет, ",
    " - не оглядываясь - ",
    " - по следам ветра - ",
]


# ---------------------------------------------------------------------------
# ПОДСКАЗКИ: текст строится ИЗ РЕАЛЬНЫХ conditions JSON критерия (единый
# источник правды - подсказка не может разойтись с условием). Стиль -
# народные ЗАГАДКИ (фидбек юзера): блоки/предметы скрыты загадками из
# RIDDLE_BLOCKS/RIDDLE_ITEMS с приёмами фольклора (отрицание,
# персонификация, число, «не А, не Б, а В»...); действия - поэтичные,
# но С ЯСНЫМ глаголом («Пусть земля примет...», «Воздвигни...»,
# «Вкуси...» - что делать, считывается сразу); существа - по имени,
# изредка с образным прозвищем из POETIC_ENT. Двойные подсказки
# (алай, item_used_on_block) берут КОРОТКОЕ колено загадки с бюджетом
# слов. Один критерий ~12-15 слов; склейка нескольких критериев
# соединителями HINT_JOINERS читается как заклинание-присказка
# (см. rand_advancements).
# ---------------------------------------------------------------------------

def _entity_predicates(conds, key):
    """predicate-словари из conditions[key] (entity/victims/cause/child/
    projectile): список ContextAwarePredicate (или список списков)."""
    out = []
    val = conds.get(key)
    if not isinstance(val, list):
        return out
    for grp in val:
        for p in (grp if isinstance(grp, list) else [grp]):
            if isinstance(p, dict):
                pr = p.get("predicate")
                if isinstance(pr, dict):
                    out.append(pr)
    return out


def _entity_ids(conds, key):
    """Типы сущностей из conditions[key] (entity/victims/cause/bystander/
    child): список ContextAwarePredicate (или список списков у victims)."""
    return [pr["minecraft:entity_type"]
            for pr in _entity_predicates(conds, key)
            if pr.get("minecraft:entity_type")]


def _player_flags(conds):
    """minecraft:flags из player-предикатов САМОГО триггера (используют
    placed_block/using_item - внутренние условия одного действия)."""
    val = conds.get("player")
    out = {}
    for p in (val if isinstance(val, list) else
              [val] if isinstance(val, dict) else ()):
        if isinstance(p, dict):
            fl = p.get("predicate", {}).get("minecraft:flags")
            if isinstance(fl, dict):
                out.update(fl)
    return out


def _cond_item(conds):
    """Предмет из conditions["item"]["items"] (consume_item/using_item/
    filled_bucket/enchanted_item/item_durability_changed/...) или None."""
    it = conds.get("item")
    return it.get("items") if isinstance(it, dict) else None


def _loc_blocks(conds):
    """Блоки из location[] - location_check с predicate.block.blocks."""
    out = []
    loc = conds.get("location")
    if not isinstance(loc, list):
        return out
    for p in loc:
        if isinstance(p, dict) and "block" in p.get("predicate", {}):
            b = p["predicate"]["block"].get("blocks")
            if b:
                out.append(b)
    return out


def _loc_tool_pred(conds):
    """Полный ItemPredicate из match_tool внутри location[]
    (allay_drop_item_on_block): {"items": ..., "predicates": ...}? или None."""
    loc = conds.get("location")
    if not isinstance(loc, list):
        return None
    for p in loc:
        if isinstance(p, dict) and p.get("condition") == "minecraft:match_tool":
            pr = p.get("predicate")
            if isinstance(pr, dict):
                return pr
    return None


def _hint_killed(conds, rng):
    """Существо - ПРЯМО по имени (юзер: «со страйдером» ок), но флаг
    is_baby и дистанция из условий дают вариации «с детёнышем» /
    «лицом к лицу» / «издалека» (Formats - vanilla sniper_duel:
    minecraft:distance). С шансом ~40% колоритный враг получает образное
    прозвище из POETIC_ENT («страж песков» = хаск) - фидбек: «местами
    образно, но в меру»; глагол убийства остаётся считываемым."""
    mobs = _entity_ids(conds, "entity")
    if not mobs:
        return ""
    n, a, g, i = RU_ENT[mobs[0]]
    prs = _entity_predicates(conds, "entity")
    pr = prs[0] if prs else {}
    flags = pr.get("minecraft:flags") or {}
    dist = pr.get("minecraft:distance") or {}
    if flags.get("is_baby"):
        return rng.choice((
            "Сразись с детёнышем %s" % g,
            "Одолей детёныша %s" % g,
            "Прими бой с детёнышем %s" % g,
            "Не дай вырасти детёнышу %s" % g))
    if dist.get("absolute", {}).get("max") is not None:
        return rng.choice((
            "Порази %s вплотную" % a,
            "Сойдись %s лицом к лицу" % _with(i),
            "Срази %s на расстоянии вздоха" % a,
            "Сойдись %s грудь в грудь" % _with(i)))
    if dist.get("horizontal", {}).get("min") is not None:
        return rng.choice((
            "Порази %s издалека" % a,
            "Срази %s метким выстрелом издали" % a,
            "Срази %s с почтительного расстояния" % a,
            "Покажи дальнюю руку - срази %s" % a))
    if mobs[0] in POETIC_ENT and rng.random() < 0.4:
        pn, pa = POETIC_ENT[mobs[0]]
        return rng.choice((
            "Пусть %s узнает свою последнюю грозу" % pn,
            "Докажи себя - одолей %s" % pa,
            "Пусть %s встретит достойного" % pn,
            "Одолей %s - так велит приговор" % pa,
            "Пусть %s сложит свою песню" % pn,
            "Ступай смело - одолей %s" % pa))
    return rng.choice((
        "Пусть %s падёт" % n,
        "Сразись %s" % _with(i),
        "Пусть %s узнает свою последнюю грозу" % n,
        "Найдётся смельчак, что одолеет %s" % a,
        "Одержи верх над %s" % i,
        "Отведай боя %s" % g,
        "Отправь %s в последний путь" % a,
        "Сведи счёты %s" % _with(i),
        "Пусть %s более не встанет" % n,
        "Сотри %s с лица этого мира" % a,
        "Не на того напал %s - сразись" % n,
        "Пусть по %s затянется песня" % g))


def _hint_placed(conds, rng):
    blocks = _loc_blocks(conds)
    if not blocks:
        return ""
    r = _riddle_block(rng, blocks[0], max_words=10)
    if _player_flags(conds).get("is_on_ground"):
        return rng.choice((
            "Воздвигни %s, твёрдо стоя на земле" % r,
            "Пусть земля примет %s из твоих рук" % r,
            "Поставь %s, ощутив под ногами землю" % r,
            "Не отрываясь от земли, воздвигни %s" % r))
    return rng.choice((
        "Воздвигни %s" % r,
        "Пусть земля примет %s" % r,
        "Вручи миру %s" % r,
        "Поставь %s, и мир станет богаче" % r,
        "Впиши %s в полотно мира" % r,
        "Дай миру %s" % r,
        "Пусть %s обоснуется здесь" % r,
        "Оставь след - поставь %s" % r))


def _hint_consume(conds, rng):
    it = _cond_item(conds)
    if not it:
        return ""
    r = _riddle_item(rng, it, max_words=10)
    if it in DRINKS:
        return rng.choice((
            "Осуши %s" % r,
            "Выпей до дна %s" % r,
            "Пусть горло запомнит %s" % r,
            "Выпей %s без остатка" % r,
            "Подними %s и осуши" % r,
            "Не оставь ни капли - выпей %s" % r))
    return rng.choice((
        "Вкуси %s" % r,
        "Съешь %s" % r,
        "Попробуй на зуб %s" % r,
        "Пусть тело узнает %s" % r,
        "Сполна отведай %s" % r,
        "Утоли голод %s" % r,
        "Не отказывай себе - съешь %s" % r,
        "Пусть трапеза запомнится - съешь %s" % r))


def _hint_inventory(conds, rng):
    items = conds.get("items")
    iid = items[0].get("items") if items and isinstance(items[0], dict) \
        else None
    if not iid:
        return ""
    r = _riddle_item(rng, iid, max_words=10)
    return rng.choice((
        "Заполучи %s" % r,
        "Раздобудь %s" % r,
        "Добудь и сбереги %s" % r,
        "Схорони в котомке %s" % r,
        "Пусть в котомке заведётся %s" % r,
        "Вырви у судьбы %s" % r,
        "Заведи у себя %s" % r,
        "Пусть руки помнят тяжесть %s" % r))


def _hint_effects(conds, rng):
    effs = conds.get("effects")
    eff = next(iter(effs)) if isinstance(effs, dict) and effs else None
    if not eff:
        return ""
    g = RU_EFFECT[eff]
    return rng.choice((
        "Подвергнись эффекту %s" % g,
        "Тебе не избежать %s" % g,
        "Сдайся власти %s" % g,
        "Испытай на себе действие %s" % g,
        "Прими на себя бремя %s" % g,
        "Дай %s овладеть собой" % g,
        "Пусть %s течёт в твоих жилах" % g,
        "Познай на себе %s" % g))


def _hint_brewed(conds, rng):
    p = conds.get("potion")
    if not p:
        return ""
    name = RU_POTION[p]
    return rng.choice((
        "Свари %s" % name,
        "Вскипяти в варочной стойке %s" % name,
        "Пусть варочная стойка выдаст %s" % name,
        "Приготовь в варочной стойке %s" % name,
        "Вари, покуда не выйдет %s" % name,
        "Алхимия терпения - свари %s" % name))


def _hint_tame(conds, rng):
    mobs = _entity_ids(conds, "entity")
    if not mobs:
        return ""
    a = RU_ENT[mobs[0]][1]
    return rng.choice((
        "Приручи %s" % a,
        "Заведи друга - приручи %s" % a,
        "Пусть дикое сердце станет ручным - приручи %s" % a,
        "Приручи %s терпением и лаской" % a,
        "Пусть дикое сердце смирится - приручи %s" % a,
        "Завоюй доверие - приручи %s" % a))


def _hint_fall_from_height(conds, rng):
    d = conds.get("distance", {}).get("y", {}).get("min")
    if d is None:
        return ""
    n = int(d)
    return rng.choice((
        "Бросься вниз с высоты %d+ блоков" % n,
        "Пусть земля окажется на %d+ блоков ниже" % n,
        "Упади с высоты %d+ блоков" % n))


def _hint_lava_ride(conds, rng):
    d = conds.get("distance", {}).get("horizontal", {}).get("min")
    if d is None:
        return ""
    n = int(d)
    return rng.choice((
        "Прокатись по лаве верхом - %d+ блоков пути" % n,
        "Оседлай кого-нибудь в лаве и проедь %d+ блоков" % n,
        "Верхом по огненной реке - %d+ блоков пути" % n))


def _hint_allay(conds, rng):
    blocks = _loc_blocks(conds)
    tool = _loc_tool_pred(conds)
    if not blocks or not tool or not tool.get("items"):
        return ""
    # двойная подсказка - короткие колена загадок (бюджет 7 слов)
    br = _riddle_block(rng, blocks[0], max_words=7)
    ir = _riddle_item(rng, tool["items"], max_words=7)
    if tool.get("predicates"):
        # зачарованный инструмент (match_tool с компонентом enchantments)
        return rng.choice((
            "Отдай алаю зачарованное - %s на %s" % (ir, br),
            "Вручи алаю зачарованное - %s на %s" % (ir, br)))
    return rng.choice((
        "Отдай алаю %s на %s" % (ir, br),
        "Поручи алаю отнести %s на %s" % (ir, br)))


def _hint_hurt(conds, rng):
    """entity_hurt_player: урон / блок щитом (vanilla deflect_arrow:
    damage.blocked) / прямой удар (damage.type.is_direct)."""
    dmg = conds.get("damage")
    if not isinstance(dmg, dict):
        return ""
    if dmg.get("blocked"):
        return rng.choice((
            "Прими удар на щит",
            "Пусть щит услышит чужой удар",
            "Спрячься за щитом в самый миг"))
    typ = dmg.get("type")
    if isinstance(typ, dict) and typ.get("is_direct"):
        return rng.choice((
            "Прими удар лицом к лицу",
            "Подставься под прямой удар"))
    d = dmg.get("taken", {}).get("min")
    if d is None:
        return ""
    n = int(d)
    return rng.choice((
        "Прими %d+ урона разом" % n,
        "Пусть тебе прилетит на %d+ урона" % n))


def _hint_levitation(conds, rng):
    d = conds.get("distance", {}).get("y", {}).get("min")
    if d is None:
        return ""
    n = int(d)
    return rng.choice((
        "Отдайся левитации и взмой на %d+ блоков" % n,
        "Левитируя, поднимись на %d+ блоков" % n,
        "Взлети на %d+ блоков чужой волей" % n))


def _hint_started_riding(conds, rng):
    veh = None
    players = conds.get("player")
    for p in (players if isinstance(players, list) else
              [players] if isinstance(players, dict) else ()):
        if isinstance(p, dict):
            v = p.get("predicate", {}).get("minecraft:vehicle", {}) \
                .get("minecraft:entity_type")
            if v:
                veh = v
                break
    on = RU_VEHICLES.get(veh)
    if not on:
        return ""
    return rng.choice((
        "Прокатись %s" % on,
        "Устройся %s" % on,
        "Прокатись вдоволь %s" % on))


def _hint_totem(conds, rng):
    r = _riddle_item(rng, "minecraft:totem_of_undying", max_words=10)
    return rng.choice((
        "Смерть отступит - %s в помощь" % r,
        "Держи %s крепче - смерть отступит" % r,
        "Пусть смерть ошибётся - %s в помощь" % r))


def _hint_enchanted(conds, rng):
    lv = conds.get("levels", {}).get("min")
    it = _cond_item(conds)
    if it and lv is not None:
        r = _riddle_item(rng, it, max_words=10)
        return rng.choice((
            "Зачаруй %s (уровень %d+)" % (r, lv),
            "Влей магию в %s - уровень %d+" % (r, lv)))
    if lv is None:
        return ""
    return rng.choice((
        "Зачаруй что-нибудь на уровне %d+" % lv,
        "Стол зачарований, уровень %d+" % lv))


def _hint_bucket(conds, rng):
    it = _cond_item(conds)
    if not it:
        return ""
    r = _riddle_item(rng, it, max_words=10)
    return rng.choice((
        "Набери %s" % r,
        "Зачерпни %s" % r,
        "Ведро в руки - и зачерпни %s" % r))


def _hint_fishing(conds, rng):
    it = _cond_item(conds)
    if not it:
        return ""
    r = _riddle_item(rng, it, max_words=10)
    return rng.choice((
        "Выуди %s удочкой" % r,
        "Поймай %s на крючок" % r,
        "Пусть рыбалка подарит %s" % r))


def _hint_enter_block(conds, rng):
    b = conds.get("block")
    if not b:
        return ""
    r = _riddle_block(rng, b)
    return rng.choice((
        "Окунись в %s" % r,
        "Сунься в %s" % r,
        "Провались в %s" % r,
        "Войди в %s" % r))


def _hint_durability(conds, rng):
    it = _cond_item(conds)
    d = conds.get("durability", {}).get("max")
    if not it or d is None:
        return ""
    r = _riddle_item(rng, it, max_words=8)
    return rng.choice((
        "Износи %s до остатка прочности не более %d" % (r, d),
        "Доточи %s почти до конца (останется не более %d)" % (r, d),
        "Доведи %s до последних капель прочности (не более %d)" % (r, d)))


def _hint_using(conds, rng):
    it = _cond_item(conds)
    if not it:
        return ""
    r = _riddle_item(rng, it, max_words=10)
    if _player_flags(conds).get("is_on_ground") is False:
        return rng.choice((
            "Используй %s, не касаясь земли" % r,
            "Приладь %s в полёте" % r))
    return rng.choice((
        "Долго используй %s" % r,
        "Не отрываясь, используй %s" % r,
        "Не спеши - используй %s" % r))


def _hint_item_used_on_block(conds, rng):
    it = _cond_item(conds)
    blocks = _loc_blocks(conds)
    if not it or not blocks:
        return ""
    # двойная подсказка - короткие колена загадок (бюджет 7 слов)
    br = _riddle_block(rng, blocks[0], max_words=7)
    ti = _riddle_item_i(rng, it, max_words=7)
    if it.endswith("_axe"):  # обтёсывание брёвен
        return rng.choice((
            "Обтёси %s %s" % (br, ti),
            "Очисти от коры %s %s" % (br, ti)))
    if it.endswith("_hoe"):  # вспашка в грядки
        return rng.choice((
            "Вспахай %s %s" % (br, ti),
            "Преврати %s в грядку %s" % (br, ti)))
    if it.endswith("_shovel"):  # тропа
        return rng.choice((
            "Преврати %s в тропинку %s" % (br, ti),
            "Утрамбуй %s в тропу %s" % (br, ti)))
    if it == "minecraft:shears":  # вырезание тыквы
        return rng.choice((
            "Вырежи %s %s" % (br, ti),
            "Вырежи лицо осени %s" % ti))
    if it == "minecraft:flint_and_steel":  # огонь
        return rng.choice((
            "Подожги %s %s" % (br, ti),
            "Пусть %s займётся от %s" % (br, ti)))
    if it == "minecraft:honeycomb":  # вощение меди
        return rng.choice((
            "Покрой %s %s" % (br, ti),
            "Запечатай %s %s" % (br, ti)))
    return "Примени %s к %s" % (_riddle_item(rng, it, max_words=7), br)


# id лут-таблицы имеет вид <ns>:<имя_измерения>_loot<N> - суффикс
# срезаем, чтобы назвать ИЗМЕРЕНИЕ в подсказке контейнерного триггера
_DIM_OF_LOOT_RX = re.compile(r"_loot\d+$")


def _dim_of_loot_table(lt):
    """Имя измерения из id его сундучной таблицы: rndim:myxaeloon_loot3
    -> myxaeloon (срезается ПОСЛЕДНИЙ суффикс _lootN - имя мира само
    по случайности может кончаться на _loot<цифры>)."""
    path = lt.split(":", 1)[1] if ":" in lt else lt
    return _DIM_OF_LOOT_RX.sub("", path)


def _hint_container_loot(conds, rng):
    """player_generates_container_loot: вскрыть НАШ сундук с лут-таблицей
    ДРУГОГО измерения (условие строится в _rand_criteria; текст - в духе
    присказки). Фидбек юзера: «там надо именно определенное измерение?» -
    ДА, таблицы лежат в структурах конкретных чужих миров, поэтому
    подсказка называет ИМЯ(А) этих миров (та же pretty-форма, что в
    заголовках ачивек: rndim:myxaeloon -> Myxaeloon). conds["loot_table"]
    - ОДНА таблица или СПИСОК всех таблиц OR-группы (список передаёт
    _rand_criteria): миры перечисляются без повторов, максимум два -
    «вскрой тайник мира Myxaeloon» / «...миров Myxaeloon или Zyprat»."""
    lt = conds.get("loot_table")
    tables = lt if isinstance(lt, list) else (
        [lt] if isinstance(lt, str) else [])
    dims = []
    for t in tables:
        d = _dim_of_loot_table(t)
        if d and d not in dims:
            dims.append(d)
    names = [_pretty(d) for d in dims[:2]]
    if not names:
        # мусорный id без _lootN (в генерации не встречается) - общая
        # фраза без имени мира
        return rng.choice((
            "Вскрой заветный тайник одного из этих миров",
            "Пусть чужой спрятанный сундук откроется тебе"))
    if len(names) == 1:
        where = "мира %s" % names[0]
    elif len(dims) > 2:
        where = "миров %s, %s и прочих" % (names[0], names[1])
    else:
        where = "миров %s или %s" % (names[0], names[1])
    return rng.choice((
        "Вскрой заветный тайник %s" % where,
        "Разграбь нетронутый тайник %s" % where,
        "Загляни в запертый сундук %s" % where,
        "Сорви печать с тайника %s" % where,
        "Обчисти ларец %s до последней блёстки" % where,
        "Пусть чужие сокровища %s станут твоими" % where,
        "Замок сундука %s ждёт лишь твоей руки" % where,
        "Найди и вскрой тайник %s" % where))


def _hint_fall_after_explosion(conds, rng):
    causes = _entity_ids(conds, "cause")
    d = conds.get("distance", {}).get("y", {}).get("min")
    if not causes or d is None:
        return ""
    g = RU_ENT[causes[0]][2]
    n = int(d)
    return rng.choice((
        "Пусть взрыв %s подбросит тебя - падение с %d+ блоков" % (g, n),
        "Взлети от взрыва %s и упади с высоты %d+ блоков" % (g, n),
        "Взрывная волна %s - полёт и падение с %d+ блоков" % (g, n)))


def _hint_summoned(conds, rng):
    mobs = _entity_ids(conds, "entity")
    if not mobs:
        return ""
    a = RU_ENT[mobs[0]][1]
    return rng.choice((
        "Построй %s" % a,
        "Создай %s своими руками" % a,
        "Призови в мир %s" % a,
        "Собери по своим чертежам %s" % a))


def _hint_bred(conds, rng):
    mobs = _entity_ids(conds, "child")
    if not mobs:
        return ""
    g = RU_ENT[mobs[0]][2]
    return rng.choice((
        "Вырасти детёныша %s" % g,
        "Пусть у %s родится потомство" % g,
        "Пусть двое зверей подарят тебе малыша %s" % g))


# Действия для player_interacted_with_entity (фидбек юзера: поэтично,
# но глагол считывается): %(e)s = винительный существа («Нареки
# жителя...»), %(g)s = родительный («Сними шубу с овцы...»), %(i)s =
# загадка предмета в творительном, %(a)s = в винительном, %(nm)s =
# ЗАДАННОЕ имя бирки (читается из custom_name условия - единый
# источник правды; безымянная бирка не работает, см.
# _name_tag_custom_name). Загадки - из RIDDLE_ITEMS с бюджетом 8 слов
# (двойная подсказка)
_INTERACT_HINTS = {
    "minecraft:name_tag": (
        "Нареки %(e)s биркой с именем %(nm)s",
        "Пометь %(e)s - имя %(nm)s на бирке",
        "Впиши имя %(nm)s в бирку и нареки %(e)s",
        "Дай %(e)s имя %(nm)s - бирка наготове",
    ),
    "minecraft:bucket": (
        "Подои %(e)s - %(a)s в помощь",
        "Белая струя %(g)s ждёт %(a)s",
        "Подои %(e)s, не пролив ни капли",
        "Не жалей %(g)s - %(a)s в помощь",
    ),
    "minecraft:wheat": (
        "Угости %(e)s %(i)s",
        "Покорми %(e)s %(i)s",
        "Протяни %(e)s %(i)s",
        "Смягчи сердце %(g)s %(i)s",
    ),
    "minecraft:carrot": (
        "Примани %(e)s %(i)s",
        "Угости %(e)s %(i)s",
        "Соблазни %(e)s %(i)s",
    ),
    "minecraft:apple": (
        "Угости %(e)s %(a)s",
        "Пусть %(e)s получит %(a)s",
        "Протяни %(e)s %(a)s",
        "Отщедрись - подари %(e)s %(a)s",
    ),
    "minecraft:bone": (
        "Подкупи %(e)s %(i)s",
        "Угости %(e)s %(i)s",
        "Завоюй сердце %(g)s %(i)s",
    ),
    "minecraft:shears": (
        "Стриги %(e)s %(i)s",
        "Сними шубу с %(g)s %(i)s",
        "Пусть %(e)s сбросит шубу - %(i)s в помощь",
    ),
    "minecraft:saddle": (
        "Осёдлай %(e)s - %(a)s в помощь",
        "Пусть %(e)s получит %(a)s",
        "Вручи %(e)s %(a)s - и в путь",
    ),
}


def _hint_interact(conds, rng):
    mobs = _entity_ids(conds, "entity")
    it = _cond_item(conds)
    if not mobs or not it or it not in _INTERACT_HINTS:
        return ""
    n, a, g, _i = RU_ENT[mobs[0]]
    nm = _custom_name_text(conds)
    ir = _riddle_item_i(rng, it, max_words=8)
    ar = _riddle_item(rng, it, max_words=8)
    if it == "minecraft:name_tag" and not nm:
        # страховка для путей без внедрённого имени (генерация ставит
        # имя всегда - см. _rand_criteria / _name_tag_custom_name)
        return rng.choice((
            "Нареки %s %s" % (a, ir),
            "Пометь %s %s" % (a, ir)))
    return rng.choice(_INTERACT_HINTS[it]) % {"e": a, "g": g, "n": n,
                                              "i": ir, "a": ar,
                                              "nm": nm or ""}


def _hint_bee_nest(conds, rng):
    b = conds.get("block")
    if not b:
        return ""
    r = _riddle_block(rng, b, max_words=8)
    if conds.get("num_bees_inside"):
        return rng.choice((
            "Сними шёлковым касанием %s - внутри гул" % r,
            "Добудь шёлковым касанием %s, где спят пчёлы" % r))
    return "Сними шёлковым касанием %s" % r


def _hint_target_hit(conds, rng):
    """target_hit: в яблочко; вариант с дистанцией - vanilla bullseye
    (projectile + minecraft:distance)."""
    prs = _entity_predicates(conds, "projectile")
    dist = (prs[0].get("minecraft:distance") or {}) if prs else {}
    dmin = dist.get("horizontal", {}).get("min")
    if dmin is not None:
        n = int(dmin)
        return rng.choice((
            "Порази сердце мишени с %d+ блоков" % n,
            "Пусть стрела найдёт яблочко с %d+ блоков" % n))
    return rng.choice((
        "Попади стрелой в центр мишени",
        "Точный выстрел в яблочко мишени",
        "Мишень, стрела и верный глаз"))


# Реестр построителей: триггер -> ф(conditions, rng) -> текст подсказки.
# Триггеры без генератора условий (slept_in_bed и др.) дают статичные
# подсказки - им нечего называть конкретно. Удалённым триггерам
# (changed_dimension, nether_travel, hero_of_the_village,
# channeled_lightning, lightning_strike) построителей нет.
_HINT_BUILDERS = {
    "minecraft:player_killed_entity": _hint_killed,
    "minecraft:placed_block": _hint_placed,
    "minecraft:consume_item": _hint_consume,
    "minecraft:inventory_changed": _hint_inventory,
    "minecraft:effects_changed": _hint_effects,
    "minecraft:brewed_potion": _hint_brewed,
    "minecraft:slept_in_bed": lambda conds, rng: rng.choice((
        "Поспи в кровати",
        "Вздремни в тёплой постели",
        "Усни под чужими звёздами")),
    "minecraft:tame_animal": _hint_tame,
    "minecraft:villager_trade": lambda conds, rng: rng.choice((
        "Поторгуй с жителем",
        "Обменяйся с местным торговцем",
        "Поторгуйся с жителем до последнего изумруда")),
    "minecraft:fall_from_height": _hint_fall_from_height,
    "minecraft:ride_entity_in_lava": _hint_lava_ride,
    "minecraft:allay_drop_item_on_block": _hint_allay,
    "minecraft:entity_hurt_player": _hint_hurt,
    "minecraft:levitation": _hint_levitation,
    "minecraft:started_riding": _hint_started_riding,
    "minecraft:used_totem": _hint_totem,
    "minecraft:enchanted_item": _hint_enchanted,
    "minecraft:filled_bucket": _hint_bucket,
    "minecraft:shot_crossbow": lambda conds, rng: rng.choice((
        "Спусти тетиву арбалета",
        "Выстрели из арбалета",
        "Пусть механическая дуга плюнет болтом")),
    "minecraft:fishing_rod_hooked": _hint_fishing,
    "minecraft:target_hit": _hint_target_hit,
    "minecraft:enter_block": _hint_enter_block,
    "minecraft:item_durability_changed": _hint_durability,
    "minecraft:using_item": _hint_using,
    "minecraft:item_used_on_block": _hint_item_used_on_block,
    "minecraft:player_generates_container_loot": _hint_container_loot,
    "minecraft:fall_after_explosion": _hint_fall_after_explosion,
    # ФИДБЕК юзера (б): не называть зомби-жителя явно - в подсказке
    # остаются ТОЛЬКО ингредиенты: зелье слабости и золотое яблоко
    # («напоённого слабостью исцели золотым плодом")
    "minecraft:cured_zombie_villager": lambda conds, rng: rng.choice((
        "Напои слабостью, исцели золотым плодом",
        "Слабость да золотое яблоко - и муки пройдут",
        "Зелье слабости, золотой плод - и терпение",
        "Ослабь хворь зельем, исцели золотым плодом")),
    "minecraft:summoned_entity": _hint_summoned,
    "minecraft:bred_animals": _hint_bred,
    "minecraft:player_interacted_with_entity": _hint_interact,
    "minecraft:bee_nest_destroyed": _hint_bee_nest,
}

_HINT_FALLBACK = "Соверши нечто примечательное"


def _hint_for(trigger, conds, rng):
    """Подсказка критерия ИЗ ЕГО РЕАЛЬНЫХ УСЛОВИЙ: называет конкретный
    блок/предмет/сущность/число из conditions JSON (единый источник
    правды - подсказка не может разойтись с условием). Если построитель
    не нашёл данных (не должно случаться - самотест гоняет все триггеры),
    возвращается запасная фраза."""
    build = _HINT_BUILDERS.get(trigger)
    if build is not None:
        h = build(conds or {}, rng)
        if h:
            return h
    return _HINT_FALLBACK


def _rand_criteria(rng, chest_tables=(), dim_name=None, avail=None):
    """2-4 РАЗНЫХ триггера-группы критериев (требования_matrix: все группы
    срабатывают, т.е. задачи объединены по И - попасть в измерение
    случайно сложно). КАЖДАЯ группа - самостоятельная задача (фидбек
    юзера: «сделать 2-3 вещи не одновременно, а в любое время»): доп.
    player-условий, требовавших одновременности с триггером, больше
    НЕТ - только внутренние условия самого триггера. Подсказка каждого
    критерия строится ПОСЛЕ генерации условий - из РЕАЛЬНОГО conditions
    JSON (см. _hint_for).

    chest_tables - id сундучных лут-таблиц (в цепочке - ТОЛЬКО таблицы
    ПРЕДЫДУЩЕГО измерения; без prev_dim - любые чужие со диска, см.
    _foreign_chest_tables): когда список не пуст, триггер
    player_generates_container_loot становится доступен и занимает
    ЦЕЛУЮ OR-группу из 2-3 альтернативных таблиц (сработает любая -
    иначе поиск одной конкретной структуры стал бы слишком жестоким).
    Подсказка группы называет ИЗМЕРЕНИЕ(я), чьи таблицы попали в группу.
    Пустой список - триггер не выбирается (юзер: «если loot-таблиц
    нет - триггер не выбирать»).

    dim_name - имя измерения: нужно для бирки в player_interacted_with_
    entity (см. _name_tag_custom_name - безымянная бирка не работает).

    avail - пулы кандидатов, отфильтрованные по доступности ПРЕДЫДУЩЕГО
    мира цепочки (_Avail; None = ванильные пулы без фильтров).

    Возвращает ([(trigger, conds, hint), ...], требования requirements):
    обычно одна OR-группа на критерий (т.е. чистое И между критериями),
    но с шансом 15% один критерий получает «запасной» вариант в свою
    OR-группу (requirements вида [["c0","c0b"],["c1"]]). Подсказка
    пуста у «дублёров» контейнерной группы - текст у группы один."""
    av = avail if avail is not None else _Avail()
    k = rng.choice([2, 2, 2, 3, 3, 4])
    pool = [e for e in TRIGGER_POOL if e[0] in av.triggers]
    if not chest_tables:
        pool = [e for e in pool if e[0] != _CONTAINER_TRIGGER]
    rng.shuffle(pool)

    # «запасной» вариант в одну из OR-групп (шанс 15%, если пул позволяет)
    extra_alt = rng.randrange(k) if (rng.random() < 0.15 and k < len(pool)) \
        else None
    picked = pool[:k + (1 if extra_alt is not None else 0)]

    criteria = []      # [(trigger, conds, hint)]
    groups = []        # [[индекс критерия, ...]] - OR внутри, И между
    for i, (trigger, gen) in enumerate(picked):
        if trigger == _CONTAINER_TRIGGER:
            # группа из 2-3 альтернативных таблиц: сработает любая;
            # подсказка называет миры ВСЕХ таблиц группы
            n_alts = min(len(chest_tables), rng.randint(2, 3))
            tables = rng.sample(list(chest_tables), n_alts)
            hint = _hint_for(trigger, {"loot_table": tables}, rng)
            grp = []
            for j, lt in enumerate(tables):
                criteria.append((trigger, {"loot_table": lt},
                                 hint if j == 0 else ""))
                grp.append(len(criteria) - 1)
            if extra_alt is not None and i == k:
                groups[extra_alt].extend(grp)
            else:
                groups.append(grp)
            continue
        conds = _gen_trigger_conds(trigger, gen, rng, av)
        # бирке - конкретное имя измерения (фикс достижимости:
        # безымянная бирка не вызывает триггер, см. _name_tag_custom_name)
        if trigger == "minecraft:player_interacted_with_entity":
            _name_tag_custom_name(conds, dim_name)
        # подсказка из РЕАЛЬНЫХ условий критерия
        hint = _hint_for(trigger, conds, rng)
        criteria.append((trigger, conds, hint))
        if extra_alt is not None and i == k:
            groups[extra_alt].append(len(criteria) - 1)
        else:
            groups.append([len(criteria) - 1])

    # требования: AND между группами, OR внутри группы
    requirements = [["c%d" % j for j in grp] for grp in groups]

    return criteria, requirements


def _rand_conditions(rng):
    """Совместимость со старым API: один критерий (ванильные пулы).
    НЕ используется генератором миров (тот зовёт _rand_criteria),
    оставлено для одиночных проверок."""
    pool = [e for e in TRIGGER_POOL if e[0] != _CONTAINER_TRIGGER]
    trigger, gen = rng.choice(pool)
    conds = _gen_trigger_conds(trigger, gen, rng, _Avail())
    return trigger, conds, _hint_for(trigger, conds, rng)


# Пары «предмет -> зачарование» для allay_drop_item_on_block с match_tool
# + компонент enchantments (формат - vanilla lighten_up). Пары только
# ВЫЖИВНИЕМ-ДОБЫВАЕМЫЕ: зачарование применимо к предмету на столе или
# наковальней (книга не годится - на столе не зачаровывается, а после
# наковальни это уже enchanted_book).
_ENCH_TOOLS = [
    ("minecraft:diamond_sword", "minecraft:sharpness"),
    ("minecraft:diamond_sword", "minecraft:looting"),
    ("minecraft:iron_sword", "minecraft:sharpness"),
    ("minecraft:diamond_pickaxe", "minecraft:efficiency"),
    ("minecraft:diamond_pickaxe", "minecraft:fortune"),
    ("minecraft:iron_pickaxe", "minecraft:efficiency"),
    ("minecraft:diamond_axe", "minecraft:efficiency"),
    ("minecraft:diamond_hoe", "minecraft:efficiency"),
    ("minecraft:bow", "minecraft:power"),
    ("minecraft:crossbow", "minecraft:quick_charge"),
    ("minecraft:fishing_rod", "minecraft:lure"),
    ("minecraft:trident", "minecraft:loyalty"),
    ("minecraft:elytra", "minecraft:mending"),
    ("minecraft:shears", "minecraft:unbreaking"),
    ("minecraft:shield", "minecraft:unbreaking"),
    ("minecraft:carrot_on_a_stick", "minecraft:mending"),
    ("minecraft:warped_fungus_on_a_stick", "minecraft:mending"),
]

# Мобы, у которых СУЩЕСТВУЕТ детёныш (is_baby в player_killed_entity):
# зомби-семейство и пиглины спавнят детёнышей естественно (5%),
# остальных выводят разведением (все есть в BREEDABLE). Криперы,
# скелеты, пауки и пр. детёнышей не имеют - в пул не входят.
# Осёл разводится, мул - стерилен (не включён).
BABY_MOBS = [
    "minecraft:zombie", "minecraft:zombie_villager", "minecraft:husk",
    "minecraft:drowned", "minecraft:zombified_piglin",
    "minecraft:piglin", "minecraft:hoglin", "minecraft:villager",
    "minecraft:cow", "minecraft:pig", "minecraft:sheep",
    "minecraft:chicken", "minecraft:horse", "minecraft:donkey",
    "minecraft:rabbit", "minecraft:fox", "minecraft:wolf",
    "minecraft:cat", "minecraft:llama", "minecraft:goat",
    "minecraft:panda", "minecraft:turtle", "minecraft:bee",
    "minecraft:armadillo", "minecraft:camel", "minecraft:frog",
    "minecraft:strider", "minecraft:mooshroom", "minecraft:axolotl",
    "minecraft:sniffer",
]

# Триггер сундука: выбирается только при непустом списке НАШИХ сундучных
# таблиц других измерений (условие «не в этом измерении» делает таблицы
# САМОГО измерения недостижимыми - их сундуки лежат в его структурах)
_CONTAINER_TRIGGER = "minecraft:player_generates_container_loot"


def _gen_killed(rng, av):
    """player_killed_entity с обогащением (юзер: «используй флаги и
    предикаты в купе с триггером»): иногда is_baby («молодой» - только
    мобы с детёнышами, см. BABY_MOBS), дистанция absolute.max
    («вплотную») или horizontal.min («издалека» - формат vanilla
    sniper_duel), иногда - вовсе без доп. условий."""
    r = rng.random()
    pr = {"minecraft:entity_type": rng.choice(av.mobs_kill)}
    if r < 0.25:
        pr = {"minecraft:entity_type": rng.choice(av.baby_mobs),
              "minecraft:flags": {"is_baby": True}}
    elif r < 0.45:
        pr["minecraft:distance"] = {"absolute": {"max": 2.5}}
    elif r < 0.6:
        pr["minecraft:distance"] = {"horizontal": {"min": float(
            rng.choice([10, 16, 24, 32]))}}
    return {"entity": [{"condition": "minecraft:entity_properties",
                        "entity": "this", "predicate": pr}]}


def _gen_hurt(rng, av):
    """entity_hurt_player с обогащением: урон / блок щитом (vanilla
    deflect_arrow: damage.blocked=true) / прямой удар (damage.type.is_direct
    - DamageSourcePredicate 26.2, байткод)."""
    r = rng.random()
    if r < 0.3:
        dmg = {"blocked": True}
    elif r < 0.45:
        dmg = {"type": {"is_direct": True}}
    else:
        dmg = {"taken": {"min": float(rng.randint(1, 8))}}
    return {"damage": dmg}


def _gen_placed(rng, av):
    """placed_block с обогащением: флаг is_on_ground на игроке (ставишь,
    стоя на земле - vanilla placed_block содержит player flags) -
    опционально, не меняет достижимость."""
    conds = {"location": [_loc_block_pred(rng.choice(av.blocks))]}
    if rng.random() < 0.3:
        conds["player"] = [{
            "condition": "minecraft:entity_properties", "entity": "this",
            "predicate": {"minecraft:flags": {"is_on_ground": True}}}]
    return conds


def _gen_allay(rng, av):
    """allay_drop_item_on_block: блок + предмет (иногда ЗАЧАРОВАННЫЙ -
    match_tool с компонентом enchantments, формат vanilla lighten_up;
    пара предмет/зачарование всегда выживаемая, см. _ENCH_TOOLS)."""
    if rng.random() < 0.4:
        it, ench = rng.choice(av.ench_tools)
        tool = {"items": it,
                "predicates": {"minecraft:enchantments": [{
                    "enchantments": ench,
                    "levels": {"min": 1}}]}}
    else:
        tool = {"items": rng.choice(av.allay_items)}
    return {"location": [_loc_block_pred(rng.choice(av.blocks)),
                         {"condition": "minecraft:match_tool",
                          "predicate": tool}]}


def _gen_item_used_on_block(rng, av):
    """Достижимость: инструмент и блок выбираются ТОЛЬКО валидной парой
    из TOOL_TARGETS (топор -> бревно, мотыга -> земля, лопата -> тропа,
    ножницы -> тыква, огниво -> любой ставящийся блок, соты -> медь) -
    и только из ДОСТУПНЫХ в prev-мире (av.tool_targets)."""
    tool = rng.choice(list(av.tool_targets))
    blk = rng.choice(av.tool_targets[tool])
    return {"item": {"items": tool},
            "location": [{"condition": "minecraft:location_check",
                          "predicate": {"block": {"blocks": blk}}}]}


def _gen_player_interacted(rng, av):
    """Достижимость: сущность и предмет выбираются ТОЛЬКО валидной парой
    из _INTERACT_PAIRS (бирка -> кто угодно, ведро -> корова, пшеница ->
    корова/овца/козёл, морковь -> свинья, яблоко -> лошадь, кость ->
    волк, ножницы -> овца, седло -> лошадь) - и только ДОСТУПНОЙ в
    prev-мире (av.interact_pairs)."""
    ent, item = rng.choice(av.interact_pairs)
    return {"entity": [_ent_pred(ent)], "item": {"items": item}}


def _gen_using(rng, av):
    """using_item: иногда с флагом is_on_ground=false - «используй в
    прыжке» (достижимо: использование продолжается в воздухе)."""
    conds = {"item": {"items": rng.choice(av.usables)}}
    if rng.random() < 0.35:
        conds["player"] = [{
            "condition": "minecraft:entity_properties", "entity": "this",
            "predicate": {"minecraft:flags": {"is_on_ground": False}}}]
    return conds


def _gen_target_hit(rng, av):
    """target_hit: иногда с дистанцией полёта стрелы (vanilla bullseye:
    projectile + minecraft:distance.horizontal.min)."""
    if rng.random() < 0.4:
        return {"signal_strength": 15,
                "projectile": [{"condition": "minecraft:entity_properties",
                                "entity": "this",
                                "predicate": {"minecraft:distance": {
                                    "horizontal": {"min": float(
                                        rng.choice([8, 16, 30]))}}}}]}
    return {"signal_strength": 15}


def _gen_trigger_conds(trigger, gen, rng, av):
    """Условия критерия: dict(gen(rng, av)) + глубокая копия
    возвращаемых генератором вложенных структур (лямбды пула
    переиспользуют общие словари-образцы - без копии наивное
    присвоение мутировало бы соседние критерии; выявлено самотестом
    на дубликатах таблиц)."""
    conds = dict(gen(rng, av)) if gen else {}
    return json.loads(json.dumps(conds))


# ---------------------------------------------------------------------------
# Сундучные таблицы ДРУГИХ измерений: игрок обязан выполнить условие
# ВНЕ своего измерения (player-предикат «не в этом измерении»), поэтому
# триггер player_generates_container_loot годится только с таблицами,
# которые лежат в сундуках структур ДРУГИХ уже сгенерированных миров.
# Собирается BFS-сканом пака с диска (безопасно для данных: только чтение;
# повреждённые файлы молча пропускаются):
#   1) structure_set -> размещённые jigsaw-структуры -> их start_pool;
#   2) template_pool -> используемые .nbt-шаблоны + fallback-пулы;
#   3) .nbt-шаблоны -> тег LootTable сундуков/бочек + пулы следующих
#      шаблонов (jigsaw-блоки внутри);
#   4) LootTable-таблицы волтов игнорируются: волт выдаёт лут при
#      погружении ключа, не при открытии сундука (GENERATE_LOOT не
#      срабатывает); заодно фильтр regexp <имя>_lootN отсекает
#      ванильные таблицы из чужих мобов.
# Свои таблицы измерения (префикс <name>_) исключаются. Неизвлекаемый
# gzip-NBT и битые JSON пропускаются молча - скан не должен ронять
# генерацию. Возвращает ОТСОРТИРОВАННЫЙ список id (детерминизм).
# ---------------------------------------------------------------------------

_CHEST_LOOT_RX = re.compile(r"^[a-z0-9_.\-]+:[a-z0-9_]+_loot[0-9]+$")


def _scan_nbt_loot_tags(path, out):
    """LootTable-строки из gzip-NBT шаблона структуры.

    Мини-ридер NBT (формат писателя gen_structures._nbt_payload -
    gzip + безымянный корневой TAG_Compound). Собираем ЗНАЧЕНИЯ всех
    TAG_String с именем 'LootTable' - в шаблонах это тег block-entity
    сундуков/бочей; у волта LootTable лежит ВНУТРИ вложенного config
    (TAG_Compound) - поэтому вхождения фильтруются позже регексом
    <name>_lootN (конфиги волтов носят те же id... НЕТ: волт ссылается
    на тот же слот <name>_lootN, поэтому совпадения идентичны
    сундучным - и это правильно: волчий слот НЕ МОЖЕТ отличаться от
    сундучного по id, различие только в контейнере). Отсюда: скан
    возвращает ВСЕ LootTable-строки, а фильтр по regexp оставляет
    только наши сундучные id."""
    try:
        with gzip.open(path, "rb") as f:
            data = f.read()
    except Exception:
        return
    pos = [0]

    def u2():
        v = struct.unpack_from(">H", data, pos[0])[0]
        pos[0] += 2
        return v

    def i4():
        v = struct.unpack_from(">i", data, pos[0])[0]
        pos[0] += 4
        return v

    def rname():
        n = u2()
        s = data[pos[0]:pos[0] + n].decode("utf-8", "replace")
        pos[0] += n
        return s

    def payload(tid):
        if tid == 1:                       # TAG_Byte
            pos[0] += 1
        elif tid == 2:                     # TAG_Short
            pos[0] += 2
        elif tid == 3:                     # TAG_Int
            pos[0] += 4
        elif tid == 4:                     # TAG_Long
            pos[0] += 8
        elif tid == 5:                     # TAG_Float
            pos[0] += 4
        elif tid == 6:                     # TAG_Double
            pos[0] += 8
        elif tid == 7:                     # TAG_Byte_Array
            n = i4()                       # ВНИМАНИЕ: pos[0] += i4() -
            pos[0] += n                    # ловушка: правая часть читает
        elif tid == 8:                     # pos ДО вызова, сдвиг внутри
            n = u2()                       # i4()/u2() терялся бы
            pos[0] += n
        elif tid == 9:                     # TAG_List
            it = data[pos[0]]
            pos[0] += 1
            ln = i4()
            if it == 0:
                return                      # пустой список (TAG_End)
            for _ in range(ln):
                payload(it)
        elif tid == 10:                    # TAG_Compound
            while True:
                t = data[pos[0]]
                pos[0] += 1
                if t == 0:
                    break
                nm = rname()
                if t == 8 and nm == "LootTable":
                    n = u2()
                    out.append(data[pos[0]:pos[0] + n].decode(
                        "utf-8", "replace"))
                    pos[0] += n
                else:
                    payload(t)
        elif tid == 11:                    # TAG_Int_Array
            n = i4()
            pos[0] += n * 4
        elif tid == 12:                    # TAG_Long_Array
            n = i4()
            pos[0] += n * 8
        else:
            raise ValueError("unknown NBT tag %d" % tid)

    try:
        if data[pos[0]] != 10:             # корневой TAG_Compound
            return
        pos[0] += 1
        rname()                            # пустое имя корня
        payload(10)
    except Exception:
        return


def _scan_nbt_pool_refs(path, out):
    """Значения TAG_String 'pool' из gzip-NBT - пулы jigsaw-блоков
    шаблона (сырой побайтовый поиск: заголовок 08 00 04 + u16-длина
    + utf-8 строка; коллизии с другими ключами исключены - имя тега
    ровно 'pool')."""
    try:
        with gzip.open(path, "rb") as fh:
            blob = fh.read()
    except Exception:
        return
    i = 0
    pat = b"\x08\x00\x04pool"
    while True:
        j = blob.find(pat, i)
        if j < 0:
            break
        try:
            (n,) = struct.unpack_from(">H", blob, j + len(pat))
            out.append(blob[j + len(pat) + 2:j + len(pat) + 2 + n].decode(
                "utf-8", "replace"))
        except Exception:
            pass
        i = j + len(pat) + 2


def _foreign_chest_tables(data_root, ns, name=None):
    """Сундучные таблицы измерений (детали скана - комментарий над
    _CHEST_LOOT_RX). name исключает таблицы указанного измерения
    (None - ничего не исключать). Возвращает отсортированный список id."""
    root = str(data_root or "")
    if not root:
        return []
    wp = os.path.join(root, ns, "worldgen")
    sp = os.path.join(root, ns, "structure")

    placed = set()
    for f in glob.glob(os.path.join(wp, "structure_set", "*.json")):
        try:
            with open(f, encoding="utf-8") as fh:
                d = json.load(fh)
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        for s in d.get("structures") or ():
            if isinstance(s, dict) and s.get("structure"):
                placed.add(s["structure"])

    pools = {}          # id пула -> путь файла
    pool_dir = os.path.join(wp, "template_pool")
    for f in glob.glob(os.path.join(pool_dir, "**", "*.json"),
                       recursive=True):
        rel = os.path.relpath(f, pool_dir).replace(os.sep, "/")
        pools["%s:%s" % (ns, rel[:-5])] = f

    templates = {}      # id шаблона -> путь .nbt
    for f in glob.glob(os.path.join(sp, "**", "*.nbt"), recursive=True):
        rel = os.path.relpath(f, sp).replace(os.sep, "/")
        templates["%s:%s" % (ns, rel[:-4])] = f

    def _pool_templates(pid, out_t, queue):
        """Шаблоны и fallback-пулы одного файла пула."""
        f = pools.get(pid)
        if not f:
            return
        try:
            with open(f, encoding="utf-8") as fh:
                d = json.load(fh)
        except Exception:
            return
        for e in d.get("elements") or ():
            el = e.get("element") if isinstance(e, dict) else None
            if not isinstance(el, dict):
                continue
            if (el.get("element_type") in (
                    "minecraft:single_pool_element",
                    "minecraft:legacy_single_pool_element")
                    and el.get("location")):
                out_t.add(el["location"])
            if el.get("fallback"):
                queue.append(el["fallback"])

    seen_pools = set()
    used_templates = set()
    queue = []

    # 1) стартовые пулы размещённых jigsaw-структур
    for f in glob.glob(os.path.join(wp, "structure", "*.json")):
        sid = "%s:%s" % (ns, os.path.basename(f)[:-5])
        if sid not in placed:
            continue
        try:
            with open(f, encoding="utf-8") as fh:
                d = json.load(fh)
        except Exception:
            continue
        if d.get("type") == "minecraft:jigsaw" and d.get("start_pool"):
            queue.append(d["start_pool"])
    while queue:
        pid = queue.pop()
        if pid in seen_pools:
            continue
        seen_pools.add(pid)
        _pool_templates(pid, used_templates, queue)

    # 2) фикс-поинт: .nbt-шаблоны дают сундучные LootTable + pool-ссылки
    #    на СЛЕДУЮЩИЕ пулы (jigsaw-блоки) - те приносят новые шаблоны;
    #    каждая новая волна обрабатывается, пока не перестанет расти
    #    used_templates (страховочный потолок - 100 волн).
    tables = set()
    scanned = set()
    for _ in range(100):
        grew = False
        for tid, path in list(templates.items()):
            if tid not in used_templates or tid in scanned:
                continue
            scanned.add(tid)
            raw = []
            _scan_nbt_loot_tags(path, raw)
            refs = []
            _scan_nbt_pool_refs(path, refs)
            for t in raw:
                if t.startswith("%s:" % ns) and _CHEST_LOOT_RX.match(t):
                    tables.add(t)
            for pid in refs:
                if pid not in seen_pools:
                    seen_pools.add(pid)
                    _pool_templates(pid, used_templates, queue)
                    grew = True
        while queue:
            pid = queue.pop()
            if pid in seen_pools:
                continue
            seen_pools.add(pid)
            _pool_templates(pid, used_templates, queue)
            grew = True
        if not grew:
            break

    if name:
        pref = "%s:%s_" % (ns, name)
        tables = {t for t in tables if not t.startswith(pref)}
    return sorted(tables)


def _dim_chest_tables(data_root, ns, dim_name):
    """Сундучные таблицы КОНКРЕТНОГО измерения (для ЦЕПОЧКИ: сундуки
    лежат в структурах именно prev-мира - игрок уже там был)."""
    if not dim_name:
        return []
    pref = "%s:%s_" % (ns, dim_name)
    return [t for t in _foreign_chest_tables(data_root, ns)
            if t.startswith(pref)]


# Пул триггеров (генератор условий принимает (rng, av) - av = пулы
# кандидатов, отфильтрованные по доступности prev-мира цепочки; при
# prev=None это полные ванильные пулы). Все имена триггеров сверены
# с CriteriaTriggers.class клиентского И серверного jar 26.2.
# Непрерывные измерения (distance, damage.taken) уже задаются min/max:
# скаляр в этих предикатах означал бы точное равенство дробной величине.
# Не сужать их до min == max и не преобразовывать ВСЕ числа в диапазоны:
# signal_strength/num_bees_inside - дискретные, durability/levels - IntBounds,
# а experience в rewards остаётся скаляром. Подсказки читают те же границы.
TRIGGER_POOL = [
    ("minecraft:player_killed_entity", _gen_killed),
    ("minecraft:placed_block", _gen_placed),
    ("minecraft:consume_item",
     lambda rng, av: {"item": {"items": rng.choice(av.foods)}}),
    ("minecraft:inventory_changed",
     lambda rng, av: {"items": [{"items": rng.choice(av.items)}]}),
    ("minecraft:effects_changed",
     lambda rng, av: {"effects": {rng.choice(av.effects): {}}}),
    ("minecraft:brewed_potion",
     lambda rng, av: {"potion": rng.choice(av.potions)}),
    ("minecraft:slept_in_bed",
     None),
    ("minecraft:tame_animal",
     lambda rng, av: {"entity": [_ent_pred(rng.choice(av.tameable))]}),
    ("minecraft:villager_trade",
     None),
    # minecraft:construct_beacon УДАЛЁН (аудит 26.2): требует звезду Нижнего
    # мира (убить визера) + пирамиду маяка - непропорционально награде-
    # телепорту в случайное измерение
    ("minecraft:fall_from_height",
     lambda rng, av: {"distance": {"y": {"min": float(rng.randint(20, 200))}}}),
    ("minecraft:ride_entity_in_lava",
     lambda rng, av: {"distance": {"horizontal":
                               {"min": float(rng.randint(10, 50))}}}),
    ("minecraft:allay_drop_item_on_block", _gen_allay),
    ("minecraft:entity_hurt_player", _gen_hurt),
    ("minecraft:levitation",
     lambda rng, av: {"distance": {"y": {"min": float(rng.randint(10, 50))}}}),
    ("minecraft:started_riding",
     lambda rng, av: {"player": [{
         "condition": "minecraft:entity_properties", "entity": "this",
         "predicate": {"minecraft:vehicle": {
             "minecraft:entity_type": rng.choice(av.vehicles)}}}]}),
    ("minecraft:used_totem",
     lambda rng, av: {"item": {"items": "minecraft:totem_of_undying"}}),
    ("minecraft:enchanted_item",
     lambda rng, av: ({"levels": {"min": rng.randint(1, 3)},
                   "item": {"items": rng.choice(av.enchantables)}}
                  if rng.random() < 0.7 else {"levels": {"min": rng.randint(1, 3)}})),
    ("minecraft:filled_bucket",
     lambda rng, av: {"item": {"items": rng.choice(av.buckets)}}),
    # --- редкие триггеры: форматы условий скопированы с ванильных ачивок
    # jar 26.2 (data/minecraft/advancement/*.json) ---
    ("minecraft:shot_crossbow",
     lambda rng, av: {"item": {"items": "minecraft:crossbow"}}),
    # minecraft:killed_by_arrow УДАЛЁН (аудит 26.2): срабатывает ТОЛЬКО при
    # смерти игрока от стрелы - «смерть игрока как условие» неприемлема
    # (пример юзера); подсказка «порази стрелой нескольких» вводила в
    # заблуждение относительно реальной семантики триггера
    ("minecraft:fishing_rod_hooked",
     lambda rng, av: {"item": {"items": rng.choice(av.fish)}}),
    ("minecraft:target_hit", _gen_target_hit),
    # minecraft:slide_down_block УДАЛЁН (аудит 26.2): требует организовать
    # скольжение по стене из медового блока - в случайных мирах почти
    # невыполнимо
    ("minecraft:enter_block",
     lambda rng, av: {"block": rng.choice(av.enterable)}),
    ("minecraft:item_durability_changed",
     # Поле durability = ОСТАТОК прочности (байткод 26.2:
     # ItemDurabilityTrigger.matches: durability.matches(maxDamage -
     # newDamage)). Прежнее delta {"min": 20..100} было НЕВЫПОЛНИМО:
     # delta = oldDamage - newDamage вызывается ДО setDamageValue, т.е.
     # положителен только при ПОЧИНКЕ за одно событие, а Mending чинит
     # малыми порциями (ChangeItemDamage -> hurtAndBreak, ~2 за орб опыта)
     # и наковальня триггер вообще не вызывает. «Доточи до остатка
     # <= N» честно достигается использованием предмета.
     lambda rng, av: {"item": {"items": rng.choice(av.wearables)},
                  "durability": {"max": rng.randint(5, 30)}}),
    ("minecraft:using_item", _gen_using),
    ("minecraft:item_used_on_block",
     _gen_item_used_on_block),
    # minecraft:avoid_vibration УДАЛЁН (аудит 26.2): требует скул-сенсор
    # + подкрадывание мимо него - в случайных мирах почти невыполнимо
    #
    # player_generates_container_loot - условия генерируются в
    # _rand_criteria из сундучных таблиц: в ЦЕПОЧКЕ - ТОЛЬКО таблицы
    # ПРЕДЫДУЩЕГО измерения (его структуры; идеально для достижимости:
    # сундуки лежат в мире, где игрок уже был), без prev_dim - таблицы
    # ДРУГИХ измерений со диска (см. _CONTAINER_TRIGGER /
    # _foreign_chest_tables). Ванильные сундучные таблицы в
    # изолированном наборе кастомных миров недостижимы, а таблицы
    # САМОГО измерения блокируются предикатом «не в этом измерении».
    # Генератор в пуле - плейсхолдер (нужен для одинаковой длины пары;
    # см. _rand_criteria).
    (_CONTAINER_TRIGGER,
     lambda rng, av: {"loot_table": "minecraft:chests/simple_dungeon"}),
    ("minecraft:fall_after_explosion",
     lambda rng, av: {"cause": [_ent_pred(rng.choice(av.explosion_sources))],
                  "distance": {"y": {"min": float(rng.randint(5, 30))}}}),
    # minecraft:kill_mob_near_sculk_catalyst УДАЛЁН (аудит 26.2): требует
    # скул-катализатор в 8 блоках от места убийства - добывается шёлковым
    # касанием в глубокой тьме, встречается крайне редко
    ("minecraft:cured_zombie_villager",
     None),
    ("minecraft:summoned_entity",
     lambda rng, av: {"entity": [_ent_pred(rng.choice(av.summonable))]}),
    ("minecraft:bred_animals",
     lambda rng, av: {"child": [_ent_pred(rng.choice(av.breedable))]}),
    ("minecraft:player_interacted_with_entity",
     _gen_player_interacted),
    ("minecraft:bee_nest_destroyed",
     lambda rng, av: {
         "block": rng.choice(av.bee_blocks),
         "item": {"predicates": {"minecraft:enchantments": [
             {"enchantments": "minecraft:silk_touch",
              "levels": {"min": 1}}]}},
         "num_bees_inside": rng.randint(1, 3)}),
]

# Триггеры, удалённые из TRIGGER_POOL (полные причины - в комментариях
# на местах в пуле и докстринге модуля; константа используется
# самотестом, чтобы удалённое не просочилось обратно):
#   killed_by_arrow          - срабатывает только при СМЕРТИ игрока от стрелы
#   slide_down_block         - скольжение по стене из медового блока
#   avoid_vibration          - скул-сенсор + подкрадывание
#   kill_mob_near_sculk_catalyst - скул-катализатор в 8 блоках
#   construct_beacon         - звезда Нижнего мира (визер) + пирамида маяка
#   changed_dimension        - по задумке пака игрок не попадает в
#                              ад/край/обычный мир (юзер)
#   nether_travel            - путь через Нижний мир недоступен (см. выше)
#   hero_of_the_village      - рейды: деревни есть только в обычном мире
#   channeled_lightning      - грозы в кастомных мирах недоступны (юзер)
#   lightning_strike         - то же: молний в кастомных мирах нет
REMOVED_TRIGGERS = frozenset((
    "minecraft:killed_by_arrow",
    "minecraft:slide_down_block",
    "minecraft:avoid_vibration",
    "minecraft:kill_mob_near_sculk_catalyst",
    "minecraft:construct_beacon",
    "minecraft:changed_dimension",
    "minecraft:nether_travel",
    "minecraft:hero_of_the_village",
    "minecraft:channeled_lightning",
    "minecraft:lightning_strike",
))

# Пул звуковых событий для playsound - ВЕСЬ реестр клиентского jar 26.2
# (извлечён из SoundEvents.class; каждый ID есть и в реестре сервера).
# Заполняется ниже в _SOUND_POOL.
_SOUNDS_RAW = (
    "minecraft:ambient.basalt_deltas.additions ""minecraft:ambient.basalt_deltas.loop ""minecraft:ambient.basalt_deltas.mood ""minecraft:ambient.cave ""minecraft:ambient.crimson_forest.additions ""minecraft:ambient.crimson_forest.loop ""minecraft:ambient.crimson_forest.mood ""minecraft:ambient.nether_wastes.additions "
    "minecraft:ambient.nether_wastes.loop ""minecraft:ambient.nether_wastes.mood ""minecraft:ambient.soul_sand_valley.additions ""minecraft:ambient.soul_sand_valley.loop ""minecraft:ambient.soul_sand_valley.mood ""minecraft:ambient.underwater.enter ""minecraft:ambient.underwater.exit ""minecraft:ambient.underwater.loop "
    "minecraft:ambient.underwater.loop.additions ""minecraft:ambient.underwater.loop.additions.rare ""minecraft:ambient.underwater.loop.additions.ultra_rare ""minecraft:ambient.warped_forest.additions ""minecraft:ambient.warped_forest.loop ""minecraft:ambient.warped_forest.mood ""minecraft:block.amethyst_block.break ""minecraft:block.amethyst_block.chime "
    "minecraft:block.amethyst_block.fall ""minecraft:block.amethyst_block.hit ""minecraft:block.amethyst_block.place ""minecraft:block.amethyst_block.resonate ""minecraft:block.amethyst_block.step ""minecraft:block.amethyst_cluster.break ""minecraft:block.amethyst_cluster.fall ""minecraft:block.amethyst_cluster.hit "
    "minecraft:block.amethyst_cluster.place ""minecraft:block.amethyst_cluster.step ""minecraft:block.ancient_debris.break ""minecraft:block.ancient_debris.fall ""minecraft:block.ancient_debris.hit ""minecraft:block.ancient_debris.place ""minecraft:block.ancient_debris.step ""minecraft:block.anvil.break "
    "minecraft:block.anvil.destroy ""minecraft:block.anvil.fall ""minecraft:block.anvil.hit ""minecraft:block.anvil.land ""minecraft:block.anvil.place ""minecraft:block.anvil.step ""minecraft:block.anvil.use ""minecraft:block.azalea.break "
    "minecraft:block.azalea.fall ""minecraft:block.azalea.hit ""minecraft:block.azalea.place ""minecraft:block.azalea.step ""minecraft:block.azalea_leaves.break ""minecraft:block.azalea_leaves.fall ""minecraft:block.azalea_leaves.hit ""minecraft:block.azalea_leaves.place "
    "minecraft:block.azalea_leaves.step ""minecraft:block.bamboo.break ""minecraft:block.bamboo.fall ""minecraft:block.bamboo.hit ""minecraft:block.bamboo.place ""minecraft:block.bamboo.step ""minecraft:block.bamboo_sapling.break ""minecraft:block.bamboo_sapling.hit "
    "minecraft:block.bamboo_sapling.place ""minecraft:block.bamboo_wood.break ""minecraft:block.bamboo_wood.fall ""minecraft:block.bamboo_wood.hit ""minecraft:block.bamboo_wood.place ""minecraft:block.bamboo_wood.step ""minecraft:block.bamboo_wood_button.click_off ""minecraft:block.bamboo_wood_button.click_on "
    "minecraft:block.bamboo_wood_door.close ""minecraft:block.bamboo_wood_door.open ""minecraft:block.bamboo_wood_fence_gate.close ""minecraft:block.bamboo_wood_fence_gate.open ""minecraft:block.bamboo_wood_hanging_sign.break ""minecraft:block.bamboo_wood_hanging_sign.fall ""minecraft:block.bamboo_wood_hanging_sign.hit ""minecraft:block.bamboo_wood_hanging_sign.place "
    "minecraft:block.bamboo_wood_hanging_sign.step ""minecraft:block.bamboo_wood_pressure_plate.click_off ""minecraft:block.bamboo_wood_pressure_plate.click_on ""minecraft:block.bamboo_wood_trapdoor.close ""minecraft:block.bamboo_wood_trapdoor.open ""minecraft:block.barrel.close ""minecraft:block.barrel.open ""minecraft:block.basalt.break "
    "minecraft:block.basalt.fall ""minecraft:block.basalt.hit ""minecraft:block.basalt.place ""minecraft:block.basalt.step ""minecraft:block.beacon.activate ""minecraft:block.beacon.ambient ""minecraft:block.beacon.deactivate ""minecraft:block.beacon.power_select "
    "minecraft:block.beehive.drip ""minecraft:block.beehive.enter ""minecraft:block.beehive.exit ""minecraft:block.beehive.shear ""minecraft:block.beehive.work ""minecraft:block.bell.resonate ""minecraft:block.bell.use ""minecraft:block.big_dripleaf.break "
    "minecraft:block.big_dripleaf.fall ""minecraft:block.big_dripleaf.hit ""minecraft:block.big_dripleaf.place ""minecraft:block.big_dripleaf.step ""minecraft:block.big_dripleaf.tilt_down ""minecraft:block.big_dripleaf.tilt_up ""minecraft:block.blastfurnace.fire_crackle ""minecraft:block.bone_block.break "
    "minecraft:block.bone_block.fall ""minecraft:block.bone_block.hit ""minecraft:block.bone_block.place ""minecraft:block.bone_block.step ""minecraft:block.brewing_stand.brew ""minecraft:block.bubble_column.bubble_pop ""minecraft:block.bubble_column.upwards_ambient ""minecraft:block.bubble_column.upwards_inside "
    "minecraft:block.bubble_column.whirlpool_ambient ""minecraft:block.bubble_column.whirlpool_inside ""minecraft:block.cactus_flower.break ""minecraft:block.cactus_flower.place ""minecraft:block.cake.add_candle ""minecraft:block.calcite.break ""minecraft:block.calcite.fall ""minecraft:block.calcite.hit "
    "minecraft:block.calcite.place ""minecraft:block.calcite.step ""minecraft:block.campfire.crackle ""minecraft:block.candle.ambient ""minecraft:block.candle.break ""minecraft:block.candle.extinguish ""minecraft:block.candle.fall ""minecraft:block.candle.hit "
    "minecraft:block.candle.place ""minecraft:block.candle.step ""minecraft:block.cave_vines.break ""minecraft:block.cave_vines.fall ""minecraft:block.cave_vines.hit ""minecraft:block.cave_vines.pick_berries ""minecraft:block.cave_vines.place ""minecraft:block.cave_vines.step "
    "minecraft:block.chain.break ""minecraft:block.chain.fall ""minecraft:block.chain.hit ""minecraft:block.chain.place ""minecraft:block.chain.step ""minecraft:block.cherry_leaves.break ""minecraft:block.cherry_leaves.fall ""minecraft:block.cherry_leaves.hit "
    "minecraft:block.cherry_leaves.place ""minecraft:block.cherry_leaves.step ""minecraft:block.cherry_sapling.break ""minecraft:block.cherry_sapling.fall ""minecraft:block.cherry_sapling.hit ""minecraft:block.cherry_sapling.place ""minecraft:block.cherry_sapling.step ""minecraft:block.cherry_wood.break "
    "minecraft:block.cherry_wood.fall ""minecraft:block.cherry_wood.hit ""minecraft:block.cherry_wood.place ""minecraft:block.cherry_wood.step ""minecraft:block.cherry_wood_button.click_off ""minecraft:block.cherry_wood_button.click_on ""minecraft:block.cherry_wood_door.close ""minecraft:block.cherry_wood_door.open "
    "minecraft:block.cherry_wood_fence_gate.close ""minecraft:block.cherry_wood_fence_gate.open ""minecraft:block.cherry_wood_hanging_sign.break ""minecraft:block.cherry_wood_hanging_sign.fall ""minecraft:block.cherry_wood_hanging_sign.hit ""minecraft:block.cherry_wood_hanging_sign.place ""minecraft:block.cherry_wood_hanging_sign.step ""minecraft:block.cherry_wood_pressure_plate.click_off "
    "minecraft:block.cherry_wood_pressure_plate.click_on ""minecraft:block.cherry_wood_trapdoor.close ""minecraft:block.cherry_wood_trapdoor.open ""minecraft:block.chest.close ""minecraft:block.chest.locked ""minecraft:block.chest.open ""minecraft:block.chiseled_bookshelf.break ""minecraft:block.chiseled_bookshelf.fall "
    "minecraft:block.chiseled_bookshelf.hit ""minecraft:block.chiseled_bookshelf.insert ""minecraft:block.chiseled_bookshelf.insert.enchanted ""minecraft:block.chiseled_bookshelf.pickup ""minecraft:block.chiseled_bookshelf.pickup.enchanted ""minecraft:block.chiseled_bookshelf.place ""minecraft:block.chiseled_bookshelf.step ""minecraft:block.chorus_flower.death "
    "minecraft:block.chorus_flower.grow ""minecraft:block.cinnabar.break ""minecraft:block.cinnabar.fall ""minecraft:block.cinnabar.hit ""minecraft:block.cinnabar.place ""minecraft:block.cinnabar.step ""minecraft:block.cobweb.break ""minecraft:block.cobweb.fall "
    "minecraft:block.cobweb.hit ""minecraft:block.cobweb.place ""minecraft:block.cobweb.step ""minecraft:block.comparator.click ""minecraft:block.composter.empty ""minecraft:block.composter.fill ""minecraft:block.composter.fill_success ""minecraft:block.composter.ready "
    "minecraft:block.conduit.activate ""minecraft:block.conduit.ambient ""minecraft:block.conduit.ambient.short ""minecraft:block.conduit.attack.target ""minecraft:block.conduit.deactivate ""minecraft:block.copper.break ""minecraft:block.copper.fall ""minecraft:block.copper.hit "
    "minecraft:block.copper.place ""minecraft:block.copper.step ""minecraft:block.copper_bulb.break ""minecraft:block.copper_bulb.fall ""minecraft:block.copper_bulb.hit ""minecraft:block.copper_bulb.place ""minecraft:block.copper_bulb.step ""minecraft:block.copper_bulb.turn_off "
    "minecraft:block.copper_bulb.turn_on ""minecraft:block.copper_chest.close ""minecraft:block.copper_chest.open ""minecraft:block.copper_chest_oxidized.close ""minecraft:block.copper_chest_oxidized.open ""minecraft:block.copper_chest_weathered.close ""minecraft:block.copper_chest_weathered.open ""minecraft:block.copper_door.close "
    "minecraft:block.copper_door.open ""minecraft:block.copper_golem_statue.break ""minecraft:block.copper_golem_statue.fall ""minecraft:block.copper_golem_statue.hit ""minecraft:block.copper_golem_statue.place ""minecraft:block.copper_golem_statue.step ""minecraft:block.copper_grate.break ""minecraft:block.copper_grate.fall "
    "minecraft:block.copper_grate.hit ""minecraft:block.copper_grate.place ""minecraft:block.copper_grate.step ""minecraft:block.copper_trapdoor.close ""minecraft:block.copper_trapdoor.open ""minecraft:block.coral_block.break ""minecraft:block.coral_block.fall ""minecraft:block.coral_block.hit "
    "minecraft:block.coral_block.place ""minecraft:block.coral_block.step ""minecraft:block.crafter.craft ""minecraft:block.crafter.fail ""minecraft:block.creaking_heart.break ""minecraft:block.creaking_heart.fall ""minecraft:block.creaking_heart.hit ""minecraft:block.creaking_heart.hurt "
    "minecraft:block.creaking_heart.idle ""minecraft:block.creaking_heart.place ""minecraft:block.creaking_heart.spawn ""minecraft:block.creaking_heart.step ""minecraft:block.crop.break ""minecraft:block.deadbush.idle ""minecraft:block.decorated_pot.break ""minecraft:block.decorated_pot.fall "
    "minecraft:block.decorated_pot.hit ""minecraft:block.decorated_pot.insert ""minecraft:block.decorated_pot.insert_fail ""minecraft:block.decorated_pot.place ""minecraft:block.decorated_pot.shatter ""minecraft:block.decorated_pot.step ""minecraft:block.deepslate.break ""minecraft:block.deepslate.fall "
    "minecraft:block.deepslate.hit ""minecraft:block.deepslate.place ""minecraft:block.deepslate.step ""minecraft:block.deepslate_bricks.break ""minecraft:block.deepslate_bricks.fall ""minecraft:block.deepslate_bricks.hit ""minecraft:block.deepslate_bricks.place ""minecraft:block.deepslate_bricks.step "
    "minecraft:block.deepslate_tiles.break ""minecraft:block.deepslate_tiles.fall ""minecraft:block.deepslate_tiles.hit ""minecraft:block.deepslate_tiles.place ""minecraft:block.deepslate_tiles.step ""minecraft:block.dispenser.dispense ""minecraft:block.dispenser.fail ""minecraft:block.dispenser.launch "
    "minecraft:block.dried_ghast.ambient ""minecraft:block.dried_ghast.ambient_water ""minecraft:block.dried_ghast.break ""minecraft:block.dried_ghast.fall ""minecraft:block.dried_ghast.place ""minecraft:block.dried_ghast.place_in_water ""minecraft:block.dried_ghast.step ""minecraft:block.dried_ghast.transition "
    "minecraft:block.dripstone_block.break ""minecraft:block.dripstone_block.fall ""minecraft:block.dripstone_block.hit ""minecraft:block.dripstone_block.place ""minecraft:block.dripstone_block.step ""minecraft:block.dry_grass.ambient ""minecraft:block.enchantment_table.use ""minecraft:block.end_gateway.spawn "
    "minecraft:block.end_portal.spawn ""minecraft:block.end_portal_frame.fill ""minecraft:block.ender_chest.close ""minecraft:block.ender_chest.open ""minecraft:block.eyeblossom.close ""minecraft:block.eyeblossom.close_long ""minecraft:block.eyeblossom.idle ""minecraft:block.eyeblossom.open "
    "minecraft:block.eyeblossom.open_long ""minecraft:block.fence_gate.close ""minecraft:block.fence_gate.open ""minecraft:block.fire.ambient ""minecraft:block.fire.extinguish ""minecraft:block.firefly_bush.idle ""minecraft:block.flowering_azalea.break ""minecraft:block.flowering_azalea.fall "
    "minecraft:block.flowering_azalea.hit ""minecraft:block.flowering_azalea.place ""minecraft:block.flowering_azalea.step ""minecraft:block.froglight.break ""minecraft:block.froglight.fall ""minecraft:block.froglight.hit ""minecraft:block.froglight.place ""minecraft:block.froglight.step "
    "minecraft:block.frogspawn.break ""minecraft:block.frogspawn.fall ""minecraft:block.frogspawn.hatch ""minecraft:block.frogspawn.hit ""minecraft:block.frogspawn.place ""minecraft:block.frogspawn.step ""minecraft:block.fungus.break ""minecraft:block.fungus.fall "
    "minecraft:block.fungus.hit ""minecraft:block.fungus.place ""minecraft:block.fungus.step ""minecraft:block.furnace.fire_crackle ""minecraft:block.gilded_blackstone.break ""minecraft:block.gilded_blackstone.fall ""minecraft:block.gilded_blackstone.hit ""minecraft:block.gilded_blackstone.place "
    "minecraft:block.gilded_blackstone.step ""minecraft:block.glass.break ""minecraft:block.glass.fall ""minecraft:block.glass.hit ""minecraft:block.glass.place ""minecraft:block.glass.step ""minecraft:block.grass.break ""minecraft:block.grass.fall "
    "minecraft:block.grass.hit ""minecraft:block.grass.place ""minecraft:block.grass.step ""minecraft:block.gravel.break ""minecraft:block.gravel.fall ""minecraft:block.gravel.hit ""minecraft:block.gravel.place ""minecraft:block.gravel.step "
    "minecraft:block.grindstone.use ""minecraft:block.growing_plant.crop ""minecraft:block.hanging_roots.break ""minecraft:block.hanging_roots.fall ""minecraft:block.hanging_roots.hit ""minecraft:block.hanging_roots.place ""minecraft:block.hanging_roots.step ""minecraft:block.hanging_sign.break "
    "minecraft:block.hanging_sign.fall ""minecraft:block.hanging_sign.hit ""minecraft:block.hanging_sign.place ""minecraft:block.hanging_sign.step ""minecraft:block.hanging_sign.waxed_interact_fail ""minecraft:block.heavy_core.break ""minecraft:block.heavy_core.fall ""minecraft:block.heavy_core.hit "
    "minecraft:block.heavy_core.place ""minecraft:block.heavy_core.step ""minecraft:block.honey_block.break ""minecraft:block.honey_block.fall ""minecraft:block.honey_block.hit ""minecraft:block.honey_block.place ""minecraft:block.honey_block.slide ""minecraft:block.honey_block.step "
    "minecraft:block.iron.break ""minecraft:block.iron.fall ""minecraft:block.iron.hit ""minecraft:block.iron.place ""minecraft:block.iron.step ""minecraft:block.iron_door.close ""minecraft:block.iron_door.open ""minecraft:block.iron_trapdoor.close "
    "minecraft:block.iron_trapdoor.open ""minecraft:block.ladder.break ""minecraft:block.ladder.fall ""minecraft:block.ladder.hit ""minecraft:block.ladder.place ""minecraft:block.ladder.step ""minecraft:block.lantern.break ""minecraft:block.lantern.fall "
    "minecraft:block.lantern.hit ""minecraft:block.lantern.place ""minecraft:block.lantern.step ""minecraft:block.large_amethyst_bud.break ""minecraft:block.large_amethyst_bud.place ""minecraft:block.lava.ambient ""minecraft:block.lava.extinguish ""minecraft:block.lava.pop "
    "minecraft:block.leaf_litter.break ""minecraft:block.leaf_litter.fall ""minecraft:block.leaf_litter.hit ""minecraft:block.leaf_litter.place ""minecraft:block.leaf_litter.step ""minecraft:block.lever.click ""minecraft:block.lily_pad.place ""minecraft:block.lodestone.break "
    "minecraft:block.lodestone.fall ""minecraft:block.lodestone.hit ""minecraft:block.lodestone.place ""minecraft:block.lodestone.step ""minecraft:block.mangrove_roots.break ""minecraft:block.mangrove_roots.fall ""minecraft:block.mangrove_roots.hit ""minecraft:block.mangrove_roots.place "
    "minecraft:block.mangrove_roots.step ""minecraft:block.medium_amethyst_bud.break ""minecraft:block.medium_amethyst_bud.place ""minecraft:block.metal.break ""minecraft:block.metal.fall ""minecraft:block.metal.hit ""minecraft:block.metal.place ""minecraft:block.metal.step "
    "minecraft:block.metal_pressure_plate.click_off ""minecraft:block.metal_pressure_plate.click_on ""minecraft:block.moss.break ""minecraft:block.moss.fall ""minecraft:block.moss.hit ""minecraft:block.moss.place ""minecraft:block.moss.step ""minecraft:block.moss_carpet.break "
    "minecraft:block.moss_carpet.fall ""minecraft:block.moss_carpet.hit ""minecraft:block.moss_carpet.place ""minecraft:block.moss_carpet.step ""minecraft:block.mud.break ""minecraft:block.mud.fall ""minecraft:block.mud.hit ""minecraft:block.mud.place "
    "minecraft:block.mud.step ""minecraft:block.mud_bricks.break ""minecraft:block.mud_bricks.fall ""minecraft:block.mud_bricks.hit ""minecraft:block.mud_bricks.place ""minecraft:block.mud_bricks.step ""minecraft:block.muddy_mangrove_roots.break ""minecraft:block.muddy_mangrove_roots.fall "
    "minecraft:block.muddy_mangrove_roots.hit ""minecraft:block.muddy_mangrove_roots.place ""minecraft:block.muddy_mangrove_roots.step ""minecraft:block.nether_bricks.break ""minecraft:block.nether_bricks.fall ""minecraft:block.nether_bricks.hit ""minecraft:block.nether_bricks.place ""minecraft:block.nether_bricks.step "
    "minecraft:block.nether_gold_ore.break ""minecraft:block.nether_gold_ore.fall ""minecraft:block.nether_gold_ore.hit ""minecraft:block.nether_gold_ore.place ""minecraft:block.nether_gold_ore.step ""minecraft:block.nether_ore.break ""minecraft:block.nether_ore.fall ""minecraft:block.nether_ore.hit "
    "minecraft:block.nether_ore.place ""minecraft:block.nether_ore.step ""minecraft:block.nether_sprouts.break ""minecraft:block.nether_sprouts.fall ""minecraft:block.nether_sprouts.hit ""minecraft:block.nether_sprouts.place ""minecraft:block.nether_sprouts.step ""minecraft:block.nether_wart.break "
    "minecraft:block.nether_wood.break ""minecraft:block.nether_wood.fall ""minecraft:block.nether_wood.hit ""minecraft:block.nether_wood.place ""minecraft:block.nether_wood.step ""minecraft:block.nether_wood_button.click_off ""minecraft:block.nether_wood_button.click_on ""minecraft:block.nether_wood_door.close "
    "minecraft:block.nether_wood_door.open ""minecraft:block.nether_wood_fence_gate.close ""minecraft:block.nether_wood_fence_gate.open ""minecraft:block.nether_wood_hanging_sign.break ""minecraft:block.nether_wood_hanging_sign.fall ""minecraft:block.nether_wood_hanging_sign.hit ""minecraft:block.nether_wood_hanging_sign.place ""minecraft:block.nether_wood_hanging_sign.step "
    "minecraft:block.nether_wood_pressure_plate.click_off ""minecraft:block.nether_wood_pressure_plate.click_on ""minecraft:block.nether_wood_trapdoor.close ""minecraft:block.nether_wood_trapdoor.open ""minecraft:block.netherite_block.break ""minecraft:block.netherite_block.fall ""minecraft:block.netherite_block.hit ""minecraft:block.netherite_block.place "
    "minecraft:block.netherite_block.step ""minecraft:block.netherrack.break ""minecraft:block.netherrack.fall ""minecraft:block.netherrack.hit ""minecraft:block.netherrack.place ""minecraft:block.netherrack.step ""minecraft:block.note_block.banjo ""minecraft:block.note_block.basedrum "
    "minecraft:block.note_block.bass ""minecraft:block.note_block.bell ""minecraft:block.note_block.bit ""minecraft:block.note_block.chime ""minecraft:block.note_block.cow_bell ""minecraft:block.note_block.didgeridoo ""minecraft:block.note_block.flute ""minecraft:block.note_block.guitar "
    "minecraft:block.note_block.harp ""minecraft:block.note_block.hat ""minecraft:block.note_block.imitate.creeper ""minecraft:block.note_block.imitate.ender_dragon ""minecraft:block.note_block.imitate.piglin ""minecraft:block.note_block.imitate.skeleton ""minecraft:block.note_block.imitate.wither_skeleton ""minecraft:block.note_block.imitate.zombie "
    "minecraft:block.note_block.iron_xylophone ""minecraft:block.note_block.pling ""minecraft:block.note_block.snare ""minecraft:block.note_block.trumpet ""minecraft:block.note_block.trumpet_exposed ""minecraft:block.note_block.trumpet_oxidized ""minecraft:block.note_block.trumpet_weathered ""minecraft:block.note_block.xylophone "
    "minecraft:block.nylium.break ""minecraft:block.nylium.fall ""minecraft:block.nylium.hit ""minecraft:block.nylium.place ""minecraft:block.nylium.step ""minecraft:block.packed_mud.break ""minecraft:block.packed_mud.fall ""minecraft:block.packed_mud.hit "
    "minecraft:block.packed_mud.place ""minecraft:block.packed_mud.step ""minecraft:block.pale_hanging_moss.idle ""minecraft:block.pink_petals.break ""minecraft:block.pink_petals.fall ""minecraft:block.pink_petals.hit ""minecraft:block.pink_petals.place ""minecraft:block.pink_petals.step "
    "minecraft:block.piston.contract ""minecraft:block.piston.extend ""minecraft:block.pointed_dripstone.break ""minecraft:block.pointed_dripstone.drip_lava ""minecraft:block.pointed_dripstone.drip_lava_into_cauldron ""minecraft:block.pointed_dripstone.drip_water ""minecraft:block.pointed_dripstone.drip_water_into_cauldron ""minecraft:block.pointed_dripstone.fall "
    "minecraft:block.pointed_dripstone.hit ""minecraft:block.pointed_dripstone.land ""minecraft:block.pointed_dripstone.place ""minecraft:block.pointed_dripstone.step ""minecraft:block.polished_deepslate.break ""minecraft:block.polished_deepslate.fall ""minecraft:block.polished_deepslate.hit ""minecraft:block.polished_deepslate.place "
    "minecraft:block.polished_deepslate.step ""minecraft:block.polished_tuff.break ""minecraft:block.polished_tuff.fall ""minecraft:block.polished_tuff.hit ""minecraft:block.polished_tuff.place ""minecraft:block.polished_tuff.step ""minecraft:block.portal.ambient ""minecraft:block.portal.travel "
    "minecraft:block.portal.trigger ""minecraft:block.potent_sulfur.break ""minecraft:block.potent_sulfur.fall ""minecraft:block.potent_sulfur.geyser_continuous_eruption ""minecraft:block.potent_sulfur.geyser_continuous_eruption_active ""minecraft:block.potent_sulfur.geyser_eruption ""minecraft:block.potent_sulfur.geyser_eruption_active ""minecraft:block.potent_sulfur.hit "
    "minecraft:block.potent_sulfur.noxious_gas ""minecraft:block.potent_sulfur.place ""minecraft:block.potent_sulfur.step ""minecraft:block.powder_snow.break ""minecraft:block.powder_snow.fall ""minecraft:block.powder_snow.hit ""minecraft:block.powder_snow.place ""minecraft:block.powder_snow.step "
    "minecraft:block.pumpkin.carve ""minecraft:block.redstone_torch.burnout ""minecraft:block.resin.break ""minecraft:block.resin.fall ""minecraft:block.resin.place ""minecraft:block.resin.step ""minecraft:block.resin_bricks.break ""minecraft:block.resin_bricks.fall "
    "minecraft:block.resin_bricks.hit ""minecraft:block.resin_bricks.place ""minecraft:block.resin_bricks.step ""minecraft:block.respawn_anchor.ambient ""minecraft:block.respawn_anchor.charge ""minecraft:block.respawn_anchor.deplete ""minecraft:block.respawn_anchor.set_spawn ""minecraft:block.rooted_dirt.break "
    "minecraft:block.rooted_dirt.fall ""minecraft:block.rooted_dirt.hit ""minecraft:block.rooted_dirt.place ""minecraft:block.rooted_dirt.step ""minecraft:block.roots.break ""minecraft:block.roots.fall ""minecraft:block.roots.hit ""minecraft:block.roots.place "
    "minecraft:block.roots.step ""minecraft:block.sand.break ""minecraft:block.sand.fall ""minecraft:block.sand.hit ""minecraft:block.sand.idle ""minecraft:block.sand.place ""minecraft:block.sand.step ""minecraft:block.scaffolding.break "
    "minecraft:block.scaffolding.fall ""minecraft:block.scaffolding.hit ""minecraft:block.scaffolding.place ""minecraft:block.scaffolding.step ""minecraft:block.sculk.break ""minecraft:block.sculk.charge ""minecraft:block.sculk.fall ""minecraft:block.sculk.hit "
    "minecraft:block.sculk.place ""minecraft:block.sculk.spread ""minecraft:block.sculk.step ""minecraft:block.sculk_catalyst.bloom ""minecraft:block.sculk_catalyst.break ""minecraft:block.sculk_catalyst.fall ""minecraft:block.sculk_catalyst.hit ""minecraft:block.sculk_catalyst.place "
    "minecraft:block.sculk_catalyst.step ""minecraft:block.sculk_sensor.break ""minecraft:block.sculk_sensor.clicking ""minecraft:block.sculk_sensor.clicking_stop ""minecraft:block.sculk_sensor.fall ""minecraft:block.sculk_sensor.hit ""minecraft:block.sculk_sensor.place ""minecraft:block.sculk_sensor.step "
    "minecraft:block.sculk_shrieker.break ""minecraft:block.sculk_shrieker.fall ""minecraft:block.sculk_shrieker.hit ""minecraft:block.sculk_shrieker.place ""minecraft:block.sculk_shrieker.shriek ""minecraft:block.sculk_shrieker.step ""minecraft:block.sculk_vein.break ""minecraft:block.sculk_vein.fall "
    "minecraft:block.sculk_vein.hit ""minecraft:block.sculk_vein.place ""minecraft:block.sculk_vein.step ""minecraft:block.shelf.activate ""minecraft:block.shelf.break ""minecraft:block.shelf.deactivate ""minecraft:block.shelf.fall ""minecraft:block.shelf.hit "
    "minecraft:block.shelf.multi_swap ""minecraft:block.shelf.place ""minecraft:block.shelf.place_item ""minecraft:block.shelf.single_swap ""minecraft:block.shelf.step ""minecraft:block.shelf.take_item ""minecraft:block.shroomlight.break ""minecraft:block.shroomlight.fall "
    "minecraft:block.shroomlight.hit ""minecraft:block.shroomlight.place ""minecraft:block.shroomlight.step ""minecraft:block.shulker_box.close ""minecraft:block.shulker_box.open ""minecraft:block.sign.waxed_interact_fail ""minecraft:block.slime_block.break ""minecraft:block.slime_block.fall "
    "minecraft:block.slime_block.hit ""minecraft:block.slime_block.place ""minecraft:block.slime_block.step ""minecraft:block.small_amethyst_bud.break ""minecraft:block.small_amethyst_bud.place ""minecraft:block.small_dripleaf.break ""minecraft:block.small_dripleaf.fall ""minecraft:block.small_dripleaf.hit "
    "minecraft:block.small_dripleaf.place ""minecraft:block.small_dripleaf.step ""minecraft:block.smithing_table.use ""minecraft:block.smoker.smoke ""minecraft:block.sniffer_egg.crack ""minecraft:block.sniffer_egg.hatch ""minecraft:block.sniffer_egg.plop ""minecraft:block.snow.break "
    "minecraft:block.snow.fall ""minecraft:block.snow.hit ""minecraft:block.snow.place ""minecraft:block.snow.step ""minecraft:block.soul_sand.break ""minecraft:block.soul_sand.fall ""minecraft:block.soul_sand.hit ""minecraft:block.soul_sand.place "
    "minecraft:block.soul_sand.step ""minecraft:block.soul_soil.break ""minecraft:block.soul_soil.fall ""minecraft:block.soul_soil.hit ""minecraft:block.soul_soil.place ""minecraft:block.soul_soil.step ""minecraft:block.spawner.break ""minecraft:block.spawner.fall "
    "minecraft:block.spawner.hit ""minecraft:block.spawner.place ""minecraft:block.spawner.step ""minecraft:block.sponge.absorb ""minecraft:block.sponge.break ""minecraft:block.sponge.fall ""minecraft:block.sponge.hit ""minecraft:block.sponge.place "
    "minecraft:block.sponge.step ""minecraft:block.spore_blossom.break ""minecraft:block.spore_blossom.fall ""minecraft:block.spore_blossom.hit ""minecraft:block.spore_blossom.place ""minecraft:block.spore_blossom.step ""minecraft:block.stem.break ""minecraft:block.stem.fall "
    "minecraft:block.stem.hit ""minecraft:block.stem.place ""minecraft:block.stem.step ""minecraft:block.stone.break ""minecraft:block.stone.fall ""minecraft:block.stone.hit ""minecraft:block.stone.place ""minecraft:block.stone.step "
    "minecraft:block.stone_button.click_off ""minecraft:block.stone_button.click_on ""minecraft:block.stone_pressure_plate.click_off ""minecraft:block.stone_pressure_plate.click_on ""minecraft:block.sulfur.break ""minecraft:block.sulfur.fall ""minecraft:block.sulfur.hit ""minecraft:block.sulfur.place "
    "minecraft:block.sulfur.step ""minecraft:block.sulfur_spike.break ""minecraft:block.sulfur_spike.fall ""minecraft:block.sulfur_spike.hit ""minecraft:block.sulfur_spike.land ""minecraft:block.sulfur_spike.place ""minecraft:block.sulfur_spike.step ""minecraft:block.suspicious_gravel.break "
    "minecraft:block.suspicious_gravel.fall ""minecraft:block.suspicious_gravel.hit ""minecraft:block.suspicious_gravel.place ""minecraft:block.suspicious_gravel.step ""minecraft:block.suspicious_sand.break ""minecraft:block.suspicious_sand.fall ""minecraft:block.suspicious_sand.hit ""minecraft:block.suspicious_sand.place "
    "minecraft:block.suspicious_sand.step ""minecraft:block.sweet_berry_bush.break ""minecraft:block.sweet_berry_bush.pick_berries ""minecraft:block.sweet_berry_bush.place ""minecraft:block.trial_spawner.about_to_spawn_item ""minecraft:block.trial_spawner.ambient ""minecraft:block.trial_spawner.ambient_ominous ""minecraft:block.trial_spawner.break "
    "minecraft:block.trial_spawner.close_shutter ""minecraft:block.trial_spawner.detect_player ""minecraft:block.trial_spawner.eject_item ""minecraft:block.trial_spawner.fall ""minecraft:block.trial_spawner.hit ""minecraft:block.trial_spawner.ominous_activate ""minecraft:block.trial_spawner.open_shutter ""minecraft:block.trial_spawner.place "
    "minecraft:block.trial_spawner.spawn_item ""minecraft:block.trial_spawner.spawn_item_begin ""minecraft:block.trial_spawner.spawn_mob ""minecraft:block.trial_spawner.step ""minecraft:block.tripwire.attach ""minecraft:block.tripwire.click_off ""minecraft:block.tripwire.click_on ""minecraft:block.tripwire.detach "
    "minecraft:block.tuff.break ""minecraft:block.tuff.fall ""minecraft:block.tuff.hit ""minecraft:block.tuff.place ""minecraft:block.tuff.step ""minecraft:block.tuff_bricks.break ""minecraft:block.tuff_bricks.fall ""minecraft:block.tuff_bricks.hit "
    "minecraft:block.tuff_bricks.place ""minecraft:block.tuff_bricks.step ""minecraft:block.vault.activate ""minecraft:block.vault.ambient ""minecraft:block.vault.break ""minecraft:block.vault.close_shutter ""minecraft:block.vault.deactivate ""minecraft:block.vault.eject_item "
    "minecraft:block.vault.fall ""minecraft:block.vault.hit ""minecraft:block.vault.insert_item ""minecraft:block.vault.insert_item_fail ""minecraft:block.vault.open_shutter ""minecraft:block.vault.place ""minecraft:block.vault.reject_rewarded_player ""minecraft:block.vault.step "
    "minecraft:block.vine.break ""minecraft:block.vine.fall ""minecraft:block.vine.hit ""minecraft:block.vine.place ""minecraft:block.vine.step ""minecraft:block.wart_block.break ""minecraft:block.wart_block.fall ""minecraft:block.wart_block.hit "
    "minecraft:block.wart_block.place ""minecraft:block.wart_block.step ""minecraft:block.water.ambient ""minecraft:block.weeping_vines.break ""minecraft:block.weeping_vines.fall ""minecraft:block.weeping_vines.hit ""minecraft:block.weeping_vines.place ""minecraft:block.weeping_vines.step "
    "minecraft:block.wet_grass.break ""minecraft:block.wet_grass.fall ""minecraft:block.wet_grass.hit ""minecraft:block.wet_grass.place ""minecraft:block.wet_grass.step ""minecraft:block.wet_sponge.break ""minecraft:block.wet_sponge.dries ""minecraft:block.wet_sponge.fall "
    "minecraft:block.wet_sponge.hit ""minecraft:block.wet_sponge.place ""minecraft:block.wet_sponge.step ""minecraft:block.wood.break ""minecraft:block.wood.fall ""minecraft:block.wood.hit ""minecraft:block.wood.place ""minecraft:block.wood.step "
    "minecraft:block.wooden_button.click_off ""minecraft:block.wooden_button.click_on ""minecraft:block.wooden_door.close ""minecraft:block.wooden_door.open ""minecraft:block.wooden_pressure_plate.click_off ""minecraft:block.wooden_pressure_plate.click_on ""minecraft:block.wooden_trapdoor.close ""minecraft:block.wooden_trapdoor.open "
    "minecraft:block.wool.break ""minecraft:block.wool.fall ""minecraft:block.wool.hit ""minecraft:block.wool.place ""minecraft:block.wool.step ""minecraft:enchant.thorns.hit ""minecraft:entity.allay.ambient_with_item ""minecraft:entity.allay.ambient_without_item "
    "minecraft:entity.allay.death ""minecraft:entity.allay.hurt ""minecraft:entity.allay.item_given ""minecraft:entity.allay.item_taken ""minecraft:entity.allay.item_thrown ""minecraft:entity.armadillo.ambient ""minecraft:entity.armadillo.brush ""minecraft:entity.armadillo.death "
    "minecraft:entity.armadillo.eat ""minecraft:entity.armadillo.hurt ""minecraft:entity.armadillo.hurt_reduced ""minecraft:entity.armadillo.land ""minecraft:entity.armadillo.peek ""minecraft:entity.armadillo.roll ""minecraft:entity.armadillo.scute_drop ""minecraft:entity.armadillo.step "
    "minecraft:entity.armadillo.unroll_finish ""minecraft:entity.armadillo.unroll_start ""minecraft:entity.armor_stand.break ""minecraft:entity.armor_stand.fall ""minecraft:entity.armor_stand.hit ""minecraft:entity.armor_stand.place ""minecraft:entity.arrow.hit ""minecraft:entity.arrow.hit_player "
    "minecraft:entity.arrow.shoot ""minecraft:entity.axolotl.attack ""minecraft:entity.axolotl.death ""minecraft:entity.axolotl.hurt ""minecraft:entity.axolotl.idle_air ""minecraft:entity.axolotl.idle_water ""minecraft:entity.axolotl.splash ""minecraft:entity.axolotl.swim "
    "minecraft:entity.baby_cat.ambient ""minecraft:entity.baby_cat.beg_for_food ""minecraft:entity.baby_cat.death ""minecraft:entity.baby_cat.eat ""minecraft:entity.baby_cat.hiss ""minecraft:entity.baby_cat.hurt ""minecraft:entity.baby_cat.purr ""minecraft:entity.baby_cat.purreow "
    "minecraft:entity.baby_cat.stray_ambient ""minecraft:entity.baby_chicken.ambient ""minecraft:entity.baby_chicken.death ""minecraft:entity.baby_chicken.hurt ""minecraft:entity.baby_chicken.step ""minecraft:entity.baby_horse.ambient ""minecraft:entity.baby_horse.angry ""minecraft:entity.baby_horse.breathe "
    "minecraft:entity.baby_horse.death ""minecraft:entity.baby_horse.eat ""minecraft:entity.baby_horse.hurt ""minecraft:entity.baby_horse.land ""minecraft:entity.baby_horse.step ""minecraft:entity.baby_nautilus.ambient ""minecraft:entity.baby_nautilus.ambient_land ""minecraft:entity.baby_nautilus.death "
    "minecraft:entity.baby_nautilus.death_land ""minecraft:entity.baby_nautilus.eat ""minecraft:entity.baby_nautilus.hurt ""minecraft:entity.baby_nautilus.hurt_land ""minecraft:entity.baby_nautilus.swim ""minecraft:entity.baby_pig.ambient ""minecraft:entity.baby_pig.death ""minecraft:entity.baby_pig.eat "
    "minecraft:entity.baby_pig.hurt ""minecraft:entity.baby_pig.step ""minecraft:entity.baby_wolf.ambient ""minecraft:entity.baby_wolf.death ""minecraft:entity.baby_wolf.growl ""minecraft:entity.baby_wolf.hurt ""minecraft:entity.baby_wolf.pant ""minecraft:entity.baby_wolf.step "
    "minecraft:entity.baby_wolf.whine ""minecraft:entity.bat.ambient ""minecraft:entity.bat.death ""minecraft:entity.bat.hurt ""minecraft:entity.bat.loop ""minecraft:entity.bat.takeoff ""minecraft:entity.bee.death ""minecraft:entity.bee.hurt "
    "minecraft:entity.bee.loop ""minecraft:entity.bee.loop_aggressive ""minecraft:entity.bee.pollinate ""minecraft:entity.bee.sting ""minecraft:entity.blaze.ambient ""minecraft:entity.blaze.burn ""minecraft:entity.blaze.death ""minecraft:entity.blaze.hurt "
    "minecraft:entity.blaze.shoot ""minecraft:entity.boat.paddle_land ""minecraft:entity.boat.paddle_water ""minecraft:entity.bogged.ambient ""minecraft:entity.bogged.death ""minecraft:entity.bogged.hurt ""minecraft:entity.bogged.shear ""minecraft:entity.bogged.step "
    "minecraft:entity.breeze.charge ""minecraft:entity.breeze.death ""minecraft:entity.breeze.deflect ""minecraft:entity.breeze.hurt ""minecraft:entity.breeze.idle_air ""minecraft:entity.breeze.idle_ground ""minecraft:entity.breeze.inhale ""minecraft:entity.breeze.jump "
    "minecraft:entity.breeze.land ""minecraft:entity.breeze.shoot ""minecraft:entity.breeze.slide ""minecraft:entity.breeze.whirl ""minecraft:entity.breeze.wind_burst ""minecraft:entity.camel.ambient ""minecraft:entity.camel.dash ""minecraft:entity.camel.dash_ready "
    "minecraft:entity.camel.death ""minecraft:entity.camel.eat ""minecraft:entity.camel.hurt ""minecraft:entity.camel.saddle ""minecraft:entity.camel.sit ""minecraft:entity.camel.stand ""minecraft:entity.camel.step ""minecraft:entity.camel.step_sand "
    "minecraft:entity.camel_husk.ambient ""minecraft:entity.camel_husk.dash ""minecraft:entity.camel_husk.dash_ready ""minecraft:entity.camel_husk.death ""minecraft:entity.camel_husk.eat ""minecraft:entity.camel_husk.hurt ""minecraft:entity.camel_husk.saddle ""minecraft:entity.camel_husk.sit "
    "minecraft:entity.camel_husk.stand ""minecraft:entity.camel_husk.step ""minecraft:entity.camel_husk.step_sand ""minecraft:entity.chicken.egg ""minecraft:entity.chicken.step ""minecraft:entity.cod.ambient ""minecraft:entity.cod.death ""minecraft:entity.cod.flop "
    "minecraft:entity.cod.hurt ""minecraft:entity.copper_golem.death ""minecraft:entity.copper_golem.hurt ""minecraft:entity.copper_golem.item_drop ""minecraft:entity.copper_golem.item_no_drop ""minecraft:entity.copper_golem.no_item_get ""minecraft:entity.copper_golem.no_item_no_get ""minecraft:entity.copper_golem.shear "
    "minecraft:entity.copper_golem.spawn ""minecraft:entity.copper_golem.spin ""minecraft:entity.copper_golem.step ""minecraft:entity.copper_golem_become_statue ""minecraft:entity.copper_golem_oxidized.death ""minecraft:entity.copper_golem_oxidized.hurt ""minecraft:entity.copper_golem_oxidized.spin ""minecraft:entity.copper_golem_oxidized.step "
    "minecraft:entity.copper_golem_weathered.death ""minecraft:entity.copper_golem_weathered.hurt ""minecraft:entity.copper_golem_weathered.spin ""minecraft:entity.copper_golem_weathered.step ""minecraft:entity.cow.milk ""minecraft:entity.creaking.activate ""minecraft:entity.creaking.ambient ""minecraft:entity.creaking.attack "
    "minecraft:entity.creaking.deactivate ""minecraft:entity.creaking.death ""minecraft:entity.creaking.freeze ""minecraft:entity.creaking.spawn ""minecraft:entity.creaking.step ""minecraft:entity.creaking.sway ""minecraft:entity.creaking.twitch ""minecraft:entity.creaking.unfreeze "
    "minecraft:entity.creeper.death ""minecraft:entity.creeper.hurt ""minecraft:entity.creeper.primed ""minecraft:entity.dolphin.ambient ""minecraft:entity.dolphin.ambient_water ""minecraft:entity.dolphin.attack ""minecraft:entity.dolphin.death ""minecraft:entity.dolphin.eat "
    "minecraft:entity.dolphin.hurt ""minecraft:entity.dolphin.jump ""minecraft:entity.dolphin.play ""minecraft:entity.dolphin.splash ""minecraft:entity.dolphin.swim ""minecraft:entity.donkey.ambient ""minecraft:entity.donkey.angry ""minecraft:entity.donkey.chest "
    "minecraft:entity.donkey.death ""minecraft:entity.donkey.eat ""minecraft:entity.donkey.hurt ""minecraft:entity.donkey.jump ""minecraft:entity.dragon_fireball.explode ""minecraft:entity.drowned.ambient ""minecraft:entity.drowned.ambient_water ""minecraft:entity.drowned.death "
    "minecraft:entity.drowned.death_water ""minecraft:entity.drowned.hurt ""minecraft:entity.drowned.hurt_water ""minecraft:entity.drowned.shoot ""minecraft:entity.drowned.step ""minecraft:entity.drowned.swim ""minecraft:entity.egg.throw ""minecraft:entity.elder_guardian.ambient "
    "minecraft:entity.elder_guardian.ambient_land ""minecraft:entity.elder_guardian.curse ""minecraft:entity.elder_guardian.death ""minecraft:entity.elder_guardian.death_land ""minecraft:entity.elder_guardian.flop ""minecraft:entity.elder_guardian.hurt ""minecraft:entity.elder_guardian.hurt_land ""minecraft:entity.ender_dragon.ambient "
    "minecraft:entity.ender_dragon.death ""minecraft:entity.ender_dragon.flap ""minecraft:entity.ender_dragon.growl ""minecraft:entity.ender_dragon.hurt ""minecraft:entity.ender_dragon.shoot ""minecraft:entity.ender_eye.death ""minecraft:entity.ender_eye.launch ""minecraft:entity.ender_pearl.throw "
    "minecraft:entity.enderman.ambient ""minecraft:entity.enderman.death ""minecraft:entity.enderman.hurt ""minecraft:entity.enderman.scream ""minecraft:entity.enderman.stare ""minecraft:entity.enderman.teleport ""minecraft:entity.endermite.ambient ""minecraft:entity.endermite.death "
    "minecraft:entity.endermite.hurt ""minecraft:entity.endermite.step ""minecraft:entity.evoker.ambient ""minecraft:entity.evoker.cast_spell ""minecraft:entity.evoker.celebrate ""minecraft:entity.evoker.death ""minecraft:entity.evoker.hurt ""minecraft:entity.evoker.prepare_attack "
    "minecraft:entity.evoker.prepare_summon ""minecraft:entity.evoker.prepare_wololo ""minecraft:entity.evoker_fangs.attack ""minecraft:entity.experience_bottle.throw ""minecraft:entity.experience_orb.pickup ""minecraft:entity.firework_rocket.blast ""minecraft:entity.firework_rocket.blast_far ""minecraft:entity.firework_rocket.large_blast "
    "minecraft:entity.firework_rocket.large_blast_far ""minecraft:entity.firework_rocket.launch ""minecraft:entity.firework_rocket.shoot ""minecraft:entity.firework_rocket.twinkle ""minecraft:entity.firework_rocket.twinkle_far ""minecraft:entity.fish.swim ""minecraft:entity.fishing_bobber.retrieve ""minecraft:entity.fishing_bobber.splash "
    "minecraft:entity.fishing_bobber.throw ""minecraft:entity.fox.aggro ""minecraft:entity.fox.ambient ""minecraft:entity.fox.bite ""minecraft:entity.fox.death ""minecraft:entity.fox.eat ""minecraft:entity.fox.hurt ""minecraft:entity.fox.screech "
    "minecraft:entity.fox.sleep ""minecraft:entity.fox.sniff ""minecraft:entity.fox.spit ""minecraft:entity.fox.teleport ""minecraft:entity.frog.ambient ""minecraft:entity.frog.death ""minecraft:entity.frog.eat ""minecraft:entity.frog.hurt "
    "minecraft:entity.frog.lay_spawn ""minecraft:entity.frog.long_jump ""minecraft:entity.frog.step ""minecraft:entity.frog.tongue ""minecraft:entity.generic.big_fall ""minecraft:entity.generic.burn ""minecraft:entity.generic.death ""minecraft:entity.generic.drink "
    "minecraft:entity.generic.eat ""minecraft:entity.generic.explode ""minecraft:entity.generic.extinguish_fire ""minecraft:entity.generic.hurt ""minecraft:entity.generic.small_fall ""minecraft:entity.generic.splash ""minecraft:entity.generic.swim ""minecraft:entity.ghast.ambient "
    "minecraft:entity.ghast.death ""minecraft:entity.ghast.hurt ""minecraft:entity.ghast.scream ""minecraft:entity.ghast.shoot ""minecraft:entity.ghast.warn ""minecraft:entity.ghastling.ambient ""minecraft:entity.ghastling.death ""minecraft:entity.ghastling.hurt "
    "minecraft:entity.ghastling.spawn ""minecraft:entity.glow_item_frame.add_item ""minecraft:entity.glow_item_frame.break ""minecraft:entity.glow_item_frame.place ""minecraft:entity.glow_item_frame.remove_item ""minecraft:entity.glow_item_frame.rotate_item ""minecraft:entity.glow_squid.ambient ""minecraft:entity.glow_squid.death "
    "minecraft:entity.glow_squid.hurt ""minecraft:entity.glow_squid.squirt ""minecraft:entity.goat.ambient ""minecraft:entity.goat.death ""minecraft:entity.goat.eat ""minecraft:entity.goat.horn_break ""minecraft:entity.goat.hurt ""minecraft:entity.goat.long_jump "
    "minecraft:entity.goat.milk ""minecraft:entity.goat.prepare_ram ""minecraft:entity.goat.ram_impact ""minecraft:entity.goat.screaming.ambient ""minecraft:entity.goat.screaming.death ""minecraft:entity.goat.screaming.eat ""minecraft:entity.goat.screaming.hurt ""minecraft:entity.goat.screaming.long_jump "
    "minecraft:entity.goat.screaming.milk ""minecraft:entity.goat.screaming.prepare_ram ""minecraft:entity.goat.screaming.ram_impact ""minecraft:entity.goat.step ""minecraft:entity.guardian.ambient ""minecraft:entity.guardian.ambient_land ""minecraft:entity.guardian.attack ""minecraft:entity.guardian.death "
    "minecraft:entity.guardian.death_land ""minecraft:entity.guardian.flop ""minecraft:entity.guardian.hurt ""minecraft:entity.guardian.hurt_land ""minecraft:entity.happy_ghast.ambient ""minecraft:entity.happy_ghast.death ""minecraft:entity.happy_ghast.equip ""minecraft:entity.happy_ghast.harness_goggles_down "
    "minecraft:entity.happy_ghast.harness_goggles_up ""minecraft:entity.happy_ghast.hurt ""minecraft:entity.happy_ghast.riding ""minecraft:entity.happy_ghast.unequip ""minecraft:entity.hoglin.ambient ""minecraft:entity.hoglin.angry ""minecraft:entity.hoglin.attack ""minecraft:entity.hoglin.converted_to_zombified "
    "minecraft:entity.hoglin.death ""minecraft:entity.hoglin.hurt ""minecraft:entity.hoglin.retreat ""minecraft:entity.hoglin.step ""minecraft:entity.horse.ambient ""minecraft:entity.horse.angry ""minecraft:entity.horse.armor ""minecraft:entity.horse.breathe "
    "minecraft:entity.horse.death ""minecraft:entity.horse.eat ""minecraft:entity.horse.gallop ""minecraft:entity.horse.hurt ""minecraft:entity.horse.jump ""minecraft:entity.horse.land ""minecraft:entity.horse.saddle ""minecraft:entity.horse.step "
    "minecraft:entity.horse.step_wood ""minecraft:entity.hostile.big_fall ""minecraft:entity.hostile.death ""minecraft:entity.hostile.hurt ""minecraft:entity.hostile.small_fall ""minecraft:entity.hostile.splash ""minecraft:entity.hostile.swim ""minecraft:entity.husk.ambient "
    "minecraft:entity.husk.converted_to_zombie ""minecraft:entity.husk.death ""minecraft:entity.husk.hurt ""minecraft:entity.husk.step ""minecraft:entity.illusioner.ambient ""minecraft:entity.illusioner.cast_spell ""minecraft:entity.illusioner.death ""minecraft:entity.illusioner.hurt "
    "minecraft:entity.illusioner.mirror_move ""minecraft:entity.illusioner.prepare_blindness ""minecraft:entity.illusioner.prepare_mirror ""minecraft:entity.iron_golem.attack ""minecraft:entity.iron_golem.damage ""minecraft:entity.iron_golem.death ""minecraft:entity.iron_golem.hurt ""minecraft:entity.iron_golem.repair "
    "minecraft:entity.iron_golem.step ""minecraft:entity.item.break ""minecraft:entity.item.pickup ""minecraft:entity.item_frame.add_item ""minecraft:entity.item_frame.break ""minecraft:entity.item_frame.place ""minecraft:entity.item_frame.remove_item ""minecraft:entity.item_frame.rotate_item "
    "minecraft:entity.lightning_bolt.impact ""minecraft:entity.lightning_bolt.thunder ""minecraft:entity.lingering_potion.throw ""minecraft:entity.llama.ambient ""minecraft:entity.llama.angry ""minecraft:entity.llama.chest ""minecraft:entity.llama.death ""minecraft:entity.llama.eat "
    "minecraft:entity.llama.hurt ""minecraft:entity.llama.spit ""minecraft:entity.llama.step ""minecraft:entity.llama.swag ""minecraft:entity.magma_cube.death ""minecraft:entity.magma_cube.death_small ""minecraft:entity.magma_cube.hurt ""minecraft:entity.magma_cube.hurt_small "
    "minecraft:entity.magma_cube.jump ""minecraft:entity.magma_cube.squish ""minecraft:entity.magma_cube.squish_small ""minecraft:entity.minecart.inside ""minecraft:entity.minecart.inside.underwater ""minecraft:entity.minecart.riding ""minecraft:entity.mooshroom.convert ""minecraft:entity.mooshroom.eat "
    "minecraft:entity.mooshroom.milk ""minecraft:entity.mooshroom.shear ""minecraft:entity.mooshroom.suspicious_milk ""minecraft:entity.mule.ambient ""minecraft:entity.mule.angry ""minecraft:entity.mule.chest ""minecraft:entity.mule.death ""minecraft:entity.mule.eat "
    "minecraft:entity.mule.hurt ""minecraft:entity.mule.jump ""minecraft:entity.nautilus.ambient ""minecraft:entity.nautilus.ambient_land ""minecraft:entity.nautilus.dash ""minecraft:entity.nautilus.dash_land ""minecraft:entity.nautilus.dash_ready ""minecraft:entity.nautilus.dash_ready_land "
    "minecraft:entity.nautilus.death ""minecraft:entity.nautilus.death_land ""minecraft:entity.nautilus.eat ""minecraft:entity.nautilus.hurt ""minecraft:entity.nautilus.hurt_land ""minecraft:entity.nautilus.riding ""minecraft:entity.nautilus.swim ""minecraft:entity.ocelot.ambient "
    "minecraft:entity.ocelot.death ""minecraft:entity.ocelot.hurt ""minecraft:entity.painting.break ""minecraft:entity.painting.place ""minecraft:entity.panda.aggressive_ambient ""minecraft:entity.panda.ambient ""minecraft:entity.panda.bite ""minecraft:entity.panda.cant_breed "
    "minecraft:entity.panda.death ""minecraft:entity.panda.eat ""minecraft:entity.panda.hurt ""minecraft:entity.panda.pre_sneeze ""minecraft:entity.panda.sneeze ""minecraft:entity.panda.step ""minecraft:entity.panda.worried_ambient ""minecraft:entity.parched.ambient "
    "minecraft:entity.parched.death ""minecraft:entity.parched.hurt ""minecraft:entity.parched.step ""minecraft:entity.parrot.ambient ""minecraft:entity.parrot.death ""minecraft:entity.parrot.eat ""minecraft:entity.parrot.fly ""minecraft:entity.parrot.hurt "
    "minecraft:entity.parrot.imitate.blaze ""minecraft:entity.parrot.imitate.bogged ""minecraft:entity.parrot.imitate.breeze ""minecraft:entity.parrot.imitate.camel_husk ""minecraft:entity.parrot.imitate.creaking ""minecraft:entity.parrot.imitate.creeper ""minecraft:entity.parrot.imitate.drowned ""minecraft:entity.parrot.imitate.elder_guardian "
    "minecraft:entity.parrot.imitate.ender_dragon ""minecraft:entity.parrot.imitate.endermite ""minecraft:entity.parrot.imitate.evoker ""minecraft:entity.parrot.imitate.ghast ""minecraft:entity.parrot.imitate.guardian ""minecraft:entity.parrot.imitate.hoglin ""minecraft:entity.parrot.imitate.husk ""minecraft:entity.parrot.imitate.illusioner "
    "minecraft:entity.parrot.imitate.magma_cube ""minecraft:entity.parrot.imitate.parched ""minecraft:entity.parrot.imitate.phantom ""minecraft:entity.parrot.imitate.piglin ""minecraft:entity.parrot.imitate.piglin_brute ""minecraft:entity.parrot.imitate.pillager ""minecraft:entity.parrot.imitate.ravager ""minecraft:entity.parrot.imitate.shulker "
    "minecraft:entity.parrot.imitate.silverfish ""minecraft:entity.parrot.imitate.skeleton ""minecraft:entity.parrot.imitate.slime ""minecraft:entity.parrot.imitate.spider ""minecraft:entity.parrot.imitate.stray ""minecraft:entity.parrot.imitate.vex ""minecraft:entity.parrot.imitate.vindicator ""minecraft:entity.parrot.imitate.warden "
    "minecraft:entity.parrot.imitate.witch ""minecraft:entity.parrot.imitate.wither ""minecraft:entity.parrot.imitate.wither_skeleton ""minecraft:entity.parrot.imitate.zoglin ""minecraft:entity.parrot.imitate.zombie ""minecraft:entity.parrot.imitate.zombie_horse ""minecraft:entity.parrot.imitate.zombie_nautilus ""minecraft:entity.parrot.imitate.zombie_villager "
    "minecraft:entity.parrot.step ""minecraft:entity.phantom.ambient ""minecraft:entity.phantom.bite ""minecraft:entity.phantom.death ""minecraft:entity.phantom.flap ""minecraft:entity.phantom.hurt ""minecraft:entity.phantom.swoop ""minecraft:entity.pig.saddle "
    "minecraft:entity.pig.step ""minecraft:entity.piglin.admiring_item ""minecraft:entity.piglin.ambient ""minecraft:entity.piglin.angry ""minecraft:entity.piglin.celebrate ""minecraft:entity.piglin.converted_to_zombified ""minecraft:entity.piglin.death ""minecraft:entity.piglin.hurt "
    "minecraft:entity.piglin.jealous ""minecraft:entity.piglin.retreat ""minecraft:entity.piglin.step ""minecraft:entity.piglin_brute.ambient ""minecraft:entity.piglin_brute.angry ""minecraft:entity.piglin_brute.converted_to_zombified ""minecraft:entity.piglin_brute.death ""minecraft:entity.piglin_brute.hurt "
    "minecraft:entity.piglin_brute.step ""minecraft:entity.pillager.ambient ""minecraft:entity.pillager.celebrate ""minecraft:entity.pillager.death ""minecraft:entity.pillager.hurt ""minecraft:entity.player.attack.crit ""minecraft:entity.player.attack.knockback ""minecraft:entity.player.attack.nodamage "
    "minecraft:entity.player.attack.strong ""minecraft:entity.player.attack.sweep ""minecraft:entity.player.attack.weak ""minecraft:entity.player.big_fall ""minecraft:entity.player.breath ""minecraft:entity.player.burp ""minecraft:entity.player.death ""minecraft:entity.player.hurt "
    "minecraft:entity.player.hurt_drown ""minecraft:entity.player.hurt_freeze ""minecraft:entity.player.hurt_on_fire ""minecraft:entity.player.hurt_sweet_berry_bush ""minecraft:entity.player.levelup ""minecraft:entity.player.small_fall ""minecraft:entity.player.splash ""minecraft:entity.player.splash.high_speed "
    "minecraft:entity.player.swim ""minecraft:entity.player.teleport ""minecraft:entity.polar_bear.ambient ""minecraft:entity.polar_bear.ambient_baby ""minecraft:entity.polar_bear.death ""minecraft:entity.polar_bear.hurt ""minecraft:entity.polar_bear.step ""minecraft:entity.polar_bear.warning "
    "minecraft:entity.puffer_fish.blow_out ""minecraft:entity.puffer_fish.blow_up ""minecraft:entity.puffer_fish.death ""minecraft:entity.puffer_fish.flop ""minecraft:entity.puffer_fish.hurt ""minecraft:entity.puffer_fish.sting ""minecraft:entity.rabbit.ambient ""minecraft:entity.rabbit.attack "
    "minecraft:entity.rabbit.death ""minecraft:entity.rabbit.hurt ""minecraft:entity.rabbit.jump ""minecraft:entity.ravager.ambient ""minecraft:entity.ravager.attack ""minecraft:entity.ravager.celebrate ""minecraft:entity.ravager.death ""minecraft:entity.ravager.hurt "
    "minecraft:entity.ravager.roar ""minecraft:entity.ravager.step ""minecraft:entity.ravager.stunned ""minecraft:entity.salmon.ambient ""minecraft:entity.salmon.death ""minecraft:entity.salmon.flop ""minecraft:entity.salmon.hurt ""minecraft:entity.sheep.ambient "
    "minecraft:entity.sheep.death ""minecraft:entity.sheep.hurt ""minecraft:entity.sheep.shear ""minecraft:entity.sheep.step ""minecraft:entity.shulker.ambient ""minecraft:entity.shulker.close ""minecraft:entity.shulker.death ""minecraft:entity.shulker.hurt "
    "minecraft:entity.shulker.hurt_closed ""minecraft:entity.shulker.open ""minecraft:entity.shulker.shoot ""minecraft:entity.shulker.teleport ""minecraft:entity.shulker_bullet.hit ""minecraft:entity.shulker_bullet.hurt ""minecraft:entity.silverfish.ambient ""minecraft:entity.silverfish.death "
    "minecraft:entity.silverfish.hurt ""minecraft:entity.silverfish.step ""minecraft:entity.skeleton.ambient ""minecraft:entity.skeleton.converted_to_stray ""minecraft:entity.skeleton.death ""minecraft:entity.skeleton.hurt ""minecraft:entity.skeleton.shoot ""minecraft:entity.skeleton.step "
    "minecraft:entity.skeleton_horse.ambient ""minecraft:entity.skeleton_horse.ambient_water ""minecraft:entity.skeleton_horse.death ""minecraft:entity.skeleton_horse.gallop_water ""minecraft:entity.skeleton_horse.hurt ""minecraft:entity.skeleton_horse.jump_water ""minecraft:entity.skeleton_horse.step_water ""minecraft:entity.skeleton_horse.swim "
    "minecraft:entity.slime.attack ""minecraft:entity.slime.death ""minecraft:entity.slime.death_small ""minecraft:entity.slime.hurt ""minecraft:entity.slime.hurt_small ""minecraft:entity.slime.jump ""minecraft:entity.slime.jump_small ""minecraft:entity.slime.squish "
    "minecraft:entity.slime.squish_small ""minecraft:entity.small_sulfur_cube.death ""minecraft:entity.small_sulfur_cube.eat ""minecraft:entity.small_sulfur_cube.hurt ""minecraft:entity.small_sulfur_cube.jump ""minecraft:entity.small_sulfur_cube.squish ""minecraft:entity.sniffer.death ""minecraft:entity.sniffer.digging "
    "minecraft:entity.sniffer.digging_stop ""minecraft:entity.sniffer.drop_seed ""minecraft:entity.sniffer.eat ""minecraft:entity.sniffer.happy ""minecraft:entity.sniffer.hurt ""minecraft:entity.sniffer.idle ""minecraft:entity.sniffer.scenting ""minecraft:entity.sniffer.searching "
    "minecraft:entity.sniffer.sniffing ""minecraft:entity.sniffer.step ""minecraft:entity.snow_golem.ambient ""minecraft:entity.snow_golem.death ""minecraft:entity.snow_golem.hurt ""minecraft:entity.snow_golem.shear ""minecraft:entity.snow_golem.shoot ""minecraft:entity.snowball.throw "
    "minecraft:entity.spider.ambient ""minecraft:entity.spider.death ""minecraft:entity.spider.hurt ""minecraft:entity.spider.step ""minecraft:entity.splash_potion.break ""minecraft:entity.splash_potion.throw ""minecraft:entity.squid.ambient ""minecraft:entity.squid.death "
    "minecraft:entity.squid.hurt ""minecraft:entity.squid.squirt ""minecraft:entity.stray.ambient ""minecraft:entity.stray.death ""minecraft:entity.stray.hurt ""minecraft:entity.stray.step ""minecraft:entity.strider.ambient ""minecraft:entity.strider.death "
    "minecraft:entity.strider.eat ""minecraft:entity.strider.happy ""minecraft:entity.strider.hurt ""minecraft:entity.strider.retreat ""minecraft:entity.strider.saddle ""minecraft:entity.strider.step ""minecraft:entity.strider.step_lava ""minecraft:entity.sulfur_cube.absorb "
    "minecraft:entity.sulfur_cube.bounce ""minecraft:entity.sulfur_cube.bouncy.hit ""minecraft:entity.sulfur_cube.bouncy.push ""minecraft:entity.sulfur_cube.death ""minecraft:entity.sulfur_cube.eject ""minecraft:entity.sulfur_cube.explosive.hit ""minecraft:entity.sulfur_cube.explosive.push ""minecraft:entity.sulfur_cube.fast_flat.hit "
    "minecraft:entity.sulfur_cube.fast_flat.push ""minecraft:entity.sulfur_cube.fast_sliding.hit ""minecraft:entity.sulfur_cube.fast_sliding.push ""minecraft:entity.sulfur_cube.high_resistance.hit ""minecraft:entity.sulfur_cube.high_resistance.push ""minecraft:entity.sulfur_cube.hot.hit ""minecraft:entity.sulfur_cube.hot.push ""minecraft:entity.sulfur_cube.hurt "
    "minecraft:entity.sulfur_cube.jump ""minecraft:entity.sulfur_cube.light.hit ""minecraft:entity.sulfur_cube.light.push ""minecraft:entity.sulfur_cube.regular.hit ""minecraft:entity.sulfur_cube.regular.push ""minecraft:entity.sulfur_cube.slow_bouncy.hit ""minecraft:entity.sulfur_cube.slow_bouncy.push ""minecraft:entity.sulfur_cube.slow_flat.hit "
    "minecraft:entity.sulfur_cube.slow_flat.push ""minecraft:entity.sulfur_cube.slow_sliding.hit ""minecraft:entity.sulfur_cube.slow_sliding.push ""minecraft:entity.sulfur_cube.squish ""minecraft:entity.sulfur_cube.sticky.hit ""minecraft:entity.sulfur_cube.sticky.push ""minecraft:entity.tadpole.death ""minecraft:entity.tadpole.flop "
    "minecraft:entity.tadpole.grow_up ""minecraft:entity.tadpole.hurt ""minecraft:entity.tnt.primed ""minecraft:entity.tropical_fish.ambient ""minecraft:entity.tropical_fish.death ""minecraft:entity.tropical_fish.flop ""minecraft:entity.tropical_fish.hurt ""minecraft:entity.turtle.ambient_land "
    "minecraft:entity.turtle.death ""minecraft:entity.turtle.death_baby ""minecraft:entity.turtle.egg_break ""minecraft:entity.turtle.egg_crack ""minecraft:entity.turtle.egg_hatch ""minecraft:entity.turtle.hurt ""minecraft:entity.turtle.hurt_baby ""minecraft:entity.turtle.lay_egg "
    "minecraft:entity.turtle.shamble ""minecraft:entity.turtle.shamble_baby ""minecraft:entity.turtle.swim ""minecraft:entity.vex.ambient ""minecraft:entity.vex.charge ""minecraft:entity.vex.death ""minecraft:entity.vex.hurt ""minecraft:entity.villager.ambient "
    "minecraft:entity.villager.celebrate ""minecraft:entity.villager.death ""minecraft:entity.villager.hurt ""minecraft:entity.villager.no ""minecraft:entity.villager.trade ""minecraft:entity.villager.work_armorer ""minecraft:entity.villager.work_butcher ""minecraft:entity.villager.work_cartographer "
    "minecraft:entity.villager.work_cleric ""minecraft:entity.villager.work_farmer ""minecraft:entity.villager.work_fisherman ""minecraft:entity.villager.work_fletcher ""minecraft:entity.villager.work_leatherworker ""minecraft:entity.villager.work_librarian ""minecraft:entity.villager.work_mason ""minecraft:entity.villager.work_shepherd "
    "minecraft:entity.villager.work_toolsmith ""minecraft:entity.villager.work_weaponsmith ""minecraft:entity.villager.yes ""minecraft:entity.vindicator.ambient ""minecraft:entity.vindicator.celebrate ""minecraft:entity.vindicator.death ""minecraft:entity.vindicator.hurt ""minecraft:entity.wandering_trader.ambient "
    "minecraft:entity.wandering_trader.death ""minecraft:entity.wandering_trader.disappeared ""minecraft:entity.wandering_trader.drink_milk ""minecraft:entity.wandering_trader.drink_potion ""minecraft:entity.wandering_trader.hurt ""minecraft:entity.wandering_trader.no ""minecraft:entity.wandering_trader.reappeared ""minecraft:entity.wandering_trader.trade "
    "minecraft:entity.wandering_trader.yes ""minecraft:entity.warden.agitated ""minecraft:entity.warden.ambient ""minecraft:entity.warden.angry ""minecraft:entity.warden.attack_impact ""minecraft:entity.warden.death ""minecraft:entity.warden.dig ""minecraft:entity.warden.emerge "
    "minecraft:entity.warden.heartbeat ""minecraft:entity.warden.hurt ""minecraft:entity.warden.listening ""minecraft:entity.warden.listening_angry ""minecraft:entity.warden.nearby_close ""minecraft:entity.warden.nearby_closer ""minecraft:entity.warden.nearby_closest ""minecraft:entity.warden.roar "
    "minecraft:entity.warden.sniff ""minecraft:entity.warden.sonic_boom ""minecraft:entity.warden.sonic_charge ""minecraft:entity.warden.step ""minecraft:entity.warden.tendril_clicks ""minecraft:entity.wind_charge.throw ""minecraft:entity.wind_charge.wind_burst ""minecraft:entity.witch.ambient "
    "minecraft:entity.witch.celebrate ""minecraft:entity.witch.death ""minecraft:entity.witch.drink ""minecraft:entity.witch.hurt ""minecraft:entity.witch.throw ""minecraft:entity.wither.ambient ""minecraft:entity.wither.break_block ""minecraft:entity.wither.death "
    "minecraft:entity.wither.hurt ""minecraft:entity.wither.shoot ""minecraft:entity.wither.spawn ""minecraft:entity.wither_skeleton.ambient ""minecraft:entity.wither_skeleton.death ""minecraft:entity.wither_skeleton.hurt ""minecraft:entity.wither_skeleton.step ""minecraft:entity.wolf.shake "
    "minecraft:entity.wolf.step ""minecraft:entity.zoglin.ambient ""minecraft:entity.zoglin.angry ""minecraft:entity.zoglin.attack ""minecraft:entity.zoglin.death ""minecraft:entity.zoglin.hurt ""minecraft:entity.zoglin.step ""minecraft:entity.zombie.ambient "
    "minecraft:entity.zombie.attack_iron_door ""minecraft:entity.zombie.attack_wooden_door ""minecraft:entity.zombie.break_wooden_door ""minecraft:entity.zombie.converted_to_drowned ""minecraft:entity.zombie.death ""minecraft:entity.zombie.destroy_egg ""minecraft:entity.zombie.hurt ""minecraft:entity.zombie.infect "
    "minecraft:entity.zombie.step ""minecraft:entity.zombie_horse.ambient ""minecraft:entity.zombie_horse.angry ""minecraft:entity.zombie_horse.death ""minecraft:entity.zombie_horse.eat ""minecraft:entity.zombie_horse.hurt ""minecraft:entity.zombie_nautilus.ambient ""minecraft:entity.zombie_nautilus.ambient_land "
    "minecraft:entity.zombie_nautilus.dash ""minecraft:entity.zombie_nautilus.dash_land ""minecraft:entity.zombie_nautilus.dash_ready ""minecraft:entity.zombie_nautilus.dash_ready_land ""minecraft:entity.zombie_nautilus.death ""minecraft:entity.zombie_nautilus.death_land ""minecraft:entity.zombie_nautilus.eat ""minecraft:entity.zombie_nautilus.hurt "
    "minecraft:entity.zombie_nautilus.hurt_land ""minecraft:entity.zombie_nautilus.swim ""minecraft:entity.zombie_villager.ambient ""minecraft:entity.zombie_villager.converted ""minecraft:entity.zombie_villager.cure ""minecraft:entity.zombie_villager.death ""minecraft:entity.zombie_villager.hurt ""minecraft:entity.zombie_villager.step "
    "minecraft:entity.zombified_piglin.ambient ""minecraft:entity.zombified_piglin.angry ""minecraft:entity.zombified_piglin.death ""minecraft:entity.zombified_piglin.hurt ""minecraft:event.mob_effect.bad_omen ""minecraft:event.mob_effect.raid_omen ""minecraft:event.mob_effect.trial_omen ""minecraft:event.raid.horn "
    "minecraft:intentionally_empty ""minecraft:item.armor.equip_chain ""minecraft:item.armor.equip_copper ""minecraft:item.armor.equip_diamond ""minecraft:item.armor.equip_elytra ""minecraft:item.armor.equip_generic ""minecraft:item.armor.equip_gold ""minecraft:item.armor.equip_iron "
    "minecraft:item.armor.equip_leather ""minecraft:item.armor.equip_nautilus ""minecraft:item.armor.equip_netherite ""minecraft:item.armor.equip_turtle ""minecraft:item.armor.equip_wolf ""minecraft:item.armor.unequip_nautilus ""minecraft:item.armor.unequip_wolf ""minecraft:item.axe.scrape "
    "minecraft:item.axe.strip ""minecraft:item.axe.wax_off ""minecraft:item.bone_meal.use ""minecraft:item.book.page_turn ""minecraft:item.book.put ""minecraft:item.bottle.empty ""minecraft:item.bottle.fill ""minecraft:item.bottle.fill_dragonbreath "
    "minecraft:item.brush.brushing.generic ""minecraft:item.brush.brushing.gravel ""minecraft:item.brush.brushing.gravel.complete ""minecraft:item.brush.brushing.sand ""minecraft:item.brush.brushing.sand.complete ""minecraft:item.bucket.empty ""minecraft:item.bucket.empty_axolotl ""minecraft:item.bucket.empty_fish "
    "minecraft:item.bucket.empty_lava ""minecraft:item.bucket.empty_powder_snow ""minecraft:item.bucket.empty_sulfur_cube ""minecraft:item.bucket.empty_tadpole ""minecraft:item.bucket.fill ""minecraft:item.bucket.fill_axolotl ""minecraft:item.bucket.fill_fish ""minecraft:item.bucket.fill_lava "
    "minecraft:item.bucket.fill_powder_snow ""minecraft:item.bucket.fill_sulfur_cube ""minecraft:item.bucket.fill_tadpole ""minecraft:item.bundle.drop_contents ""minecraft:item.bundle.insert ""minecraft:item.bundle.insert_fail ""minecraft:item.bundle.remove_one ""minecraft:item.chorus_fruit.teleport "
    "minecraft:item.crop.plant ""minecraft:item.crossbow.hit ""minecraft:item.crossbow.loading_end ""minecraft:item.crossbow.loading_middle ""minecraft:item.crossbow.loading_start ""minecraft:item.crossbow.quick_charge_1 ""minecraft:item.crossbow.quick_charge_2 ""minecraft:item.crossbow.quick_charge_3 "
    "minecraft:item.crossbow.shoot ""minecraft:item.dye.use ""minecraft:item.elytra.flying ""minecraft:item.firecharge.use ""minecraft:item.flintandsteel.use ""minecraft:item.glow_ink_sac.use ""minecraft:item.golden_dandelion.unuse ""minecraft:item.golden_dandelion.use "
    "minecraft:item.hoe.till ""minecraft:item.honey_bottle.drink ""minecraft:item.honeycomb.wax_on ""minecraft:item.horse_armor.unequip ""minecraft:item.ink_sac.use ""minecraft:item.lead.break ""minecraft:item.lead.tied ""minecraft:item.lead.untied "
    "minecraft:item.llama_carpet.unequip ""minecraft:item.lodestone_compass.lock ""minecraft:item.mace.smash_air ""minecraft:item.mace.smash_ground ""minecraft:item.mace.smash_ground_heavy ""minecraft:item.nautilus_saddle_equip ""minecraft:item.nautilus_saddle_underwater_equip ""minecraft:item.nether_wart.plant "
    "minecraft:item.ominous_bottle.dispose ""minecraft:item.saddle.unequip ""minecraft:item.shears.snip ""minecraft:item.shield.block ""minecraft:item.shield.break ""minecraft:item.shovel.flatten ""minecraft:item.spear.attack ""minecraft:item.spear.hit "
    "minecraft:item.spear.lunge_1 ""minecraft:item.spear.lunge_2 ""minecraft:item.spear.lunge_3 ""minecraft:item.spear.use ""minecraft:item.spear_wood.attack ""minecraft:item.spear_wood.hit ""minecraft:item.spear_wood.use ""minecraft:item.spyglass.stop_using "
    "minecraft:item.spyglass.use ""minecraft:item.totem.use ""minecraft:item.trident.hit ""minecraft:item.trident.hit_ground ""minecraft:item.trident.return ""minecraft:item.trident.riptide_1 ""minecraft:item.trident.riptide_2 ""minecraft:item.trident.riptide_3 "
    "minecraft:item.trident.throw ""minecraft:item.trident.thunder ""minecraft:item.wolf_armor.break ""minecraft:item.wolf_armor.crack ""minecraft:item.wolf_armor.damage ""minecraft:item.wolf_armor.repair ""minecraft:music.creative ""minecraft:music.credits "
    "minecraft:music.dragon ""minecraft:music.end ""minecraft:music.game ""minecraft:music.menu ""minecraft:music.nether.basalt_deltas ""minecraft:music.nether.crimson_forest ""minecraft:music.nether.nether_wastes ""minecraft:music.nether.soul_sand_valley "
    "minecraft:music.nether.warped_forest ""minecraft:music.overworld.badlands ""minecraft:music.overworld.bamboo_jungle ""minecraft:music.overworld.cherry_grove ""minecraft:music.overworld.deep_dark ""minecraft:music.overworld.desert ""minecraft:music.overworld.dripstone_caves ""minecraft:music.overworld.flower_forest "
    "minecraft:music.overworld.forest ""minecraft:music.overworld.frozen_peaks ""minecraft:music.overworld.grove ""minecraft:music.overworld.jagged_peaks ""minecraft:music.overworld.jungle ""minecraft:music.overworld.lush_caves ""minecraft:music.overworld.meadow ""minecraft:music.overworld.old_growth_taiga "
    "minecraft:music.overworld.snowy_slopes ""minecraft:music.overworld.sparse_jungle ""minecraft:music.overworld.stony_peaks ""minecraft:music.overworld.sulfur_caves ""minecraft:music.overworld.swamp ""minecraft:music.under_water ""minecraft:music_disc.11 ""minecraft:music_disc.13 "
    "minecraft:music_disc.5 ""minecraft:music_disc.blocks ""minecraft:music_disc.bounce ""minecraft:music_disc.cat ""minecraft:music_disc.chirp ""minecraft:music_disc.creator ""minecraft:music_disc.creator_music_box ""minecraft:music_disc.far "
    "minecraft:music_disc.lava_chicken ""minecraft:music_disc.mall ""minecraft:music_disc.mellohi ""minecraft:music_disc.otherside ""minecraft:music_disc.pigstep ""minecraft:music_disc.precipice ""minecraft:music_disc.relic ""minecraft:music_disc.stal "
    "minecraft:music_disc.strad ""minecraft:music_disc.tears ""minecraft:music_disc.wait ""minecraft:music_disc.ward ""minecraft:particle.soul_escape ""minecraft:ui.button.click ""minecraft:ui.cartography_table.take_result ""minecraft:ui.hud.bubble_pop "
    "minecraft:ui.loom.select_pattern ""minecraft:ui.loom.take_result ""minecraft:ui.stonecutter.select_recipe ""minecraft:ui.stonecutter.take_result ""minecraft:ui.toast.challenge_complete ""minecraft:ui.toast.in ""minecraft:ui.toast.out ""minecraft:weather.end_flash "
    "minecraft:weather.rain ""minecraft:weather.rain.above "
)


def _parse_sounds():
    # _SOUNDS_RAW - неявно склеенные строковые литералы (одна строка);
    # каждый литерал кончается пробелом, поэтому split() даёт весь пул
    out = _SOUNDS_RAW.split()
    if not out:  # страховка на случай порчи константы
        out = ["minecraft:ambient.cave"]
    return out


SOUND_POOL = _parse_sounds()


# ---------------------------------------------------------------------------
# Чтение дерева достижений с диска
# ---------------------------------------------------------------------------

# ачивки-ШАГИ (<name>_step<i>.json) - прогресс-узлы своего измерения,
# НЕ узлы дерева/цепочки: из read_adv_tree исключаются целиком
_STEP_FILE_RX = re.compile(r"_step[0-9]+$")


def read_adv_tree(data_root, ns, skip_name=None):
    """Читает data/<ns>/advancement/adv/*.json и строит состояние дерева
    ВИДИМЫХ (с секцией display) ачивок: {id: parent|None}. Ачивки-шаги
    (суффикс _step<i>) ИСКЛЮЧАЮТСЯ - это прогресс-узлы, а не узлы
    цепочки (инвариант «у узла <= 2 видимых детей» их не считает).

    skip_name - имя измерения, чьи ачивки исключаются (перегенерация того
    же имени: старые файлы ещё на диске, но сейчас будут заменены).
    """
    tree = {}
    adv_dir = os.path.join(str(data_root), ns, "advancement", "adv")
    if not os.path.isdir(adv_dir):
        return tree
    for fn in sorted(os.listdir(adv_dir)):
        if not fn.endswith(".json"):
            continue
        stem = fn[:-5]
        if _STEP_FILE_RX.search(stem):
            continue  # шаги - прогресс-узлы, не часть дерева
        if skip_name is not None and stem in (skip_name, skip_name + "_tp"):
            continue
        try:
            with open(os.path.join(adv_dir, fn), encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        if not isinstance(data, dict) or "display" not in data:
            continue  # скрытые (_tp) в дереве не участвуют
        tree["%s:adv/%s" % (ns, stem)] = data.get("parent")
    return tree


def _chain_tail(tree, root_id):
    """Самый глубокий ЛИСТ дерева - конец цепочки (куда цеплять следующее
    измерение). Осиротевшие узлы (parent удалён при перегенерации
    середины цепочки) не считаются: их ветка «залечится», когда
    перегенерируемый узел вернётся на своё место. Детерминизм: при
    равной глубине - лексикографически минимальный id."""
    children = {}
    for i, p in tree.items():
        if p and p in tree:
            children.setdefault(p, []).append(i)
    depth = {root_id: 0} if root_id in tree else {}
    stack = [root_id] if root_id in tree else []
    while stack:
        cur = stack.pop()
        for ch in children.get(cur, ()):
            depth[ch] = depth[cur] + 1
            stack.append(ch)
    leaves = sorted(i for i in tree
                    if i != root_id and not children.get(i) and i in depth)
    if not leaves:
        return None
    return max(leaves, key=lambda i: depth[i])


def chain_tail(data_root, ns, skip_name=None):
    """Имя измерения в КОНЦЕ цепочки достижений (генератор миров
    передаёт его как prev_dim следующего измерения), либо None -
    цепочки/дерева ещё нет."""
    tail = _chain_tail(read_adv_tree(data_root, ns, skip_name=skip_name),
                       "%s:adv/root" % ns)
    if not tail or "/" not in tail:
        return None
    return tail.split("/", 1)[1]


# ---------------------------------------------------------------------------
# ЦЕПОЧКА ДОСТИЖИМОСТИ: контекст доступности ПРЕДЫДУЩЕГО мира
# ---------------------------------------------------------------------------

# Блоки рельефа, которые НИКОГДА не становятся предметом в выживании (не
# дропаются ни при какой добыче - даже шёлковым касанием) - из TERRAIN
# для placed_block/allay/item_used_on_block исключаются (в ITEMS могут
# попасть - «дикий тир» лута выдаёт любые предметы)
_NEVER_DROPS = frozenset((
    "minecraft:bedrock", "minecraft:barrier", "minecraft:light",
    "minecraft:command_block", "minecraft:chain_command_block",
    "minecraft:repeating_command_block", "minecraft:structure_block",
    "minecraft:jigsaw", "minecraft:test_block",
    "minecraft:test_instance_block", "minecraft:frosted_ice",
    "minecraft:spawner", "minecraft:budding_amethyst",
))

# Предметы с двойной жизнью «блок-предмет» (для правила «предметы ?
# ITEMS ? TERRAIN(блочные)»)
_BLOCK_ITEM_IDS = frozenset(PLACEABLE_BLOCKS)

# Зелье -> эффекты (vanilla brewing; base-варианты зелий дают один
# эффект, turtle_master - два; harming/healing дают instant_damage и
# instant_health, которых нет в пуле EFFECTS, - просто отфильтруются)
_POTION_EFFECT = {
    "minecraft:fire_resistance": ("minecraft:fire_resistance",),
    "minecraft:harming": ("minecraft:instant_damage",),
    "minecraft:healing": ("minecraft:instant_health",),
    "minecraft:infested": ("minecraft:infested",),
    "minecraft:invisibility": ("minecraft:invisibility",),
    "minecraft:leaping": ("minecraft:jump_boost",),
    "minecraft:night_vision": ("minecraft:night_vision",),
    "minecraft:oozing": ("minecraft:oozing",),
    "minecraft:poison": ("minecraft:poison",),
    "minecraft:regeneration": ("minecraft:regeneration",),
    "minecraft:slow_falling": ("minecraft:slow_falling",),
    "minecraft:slowness": ("minecraft:slowness",),
    "minecraft:strength": ("minecraft:strength",),
    "minecraft:swiftness": ("minecraft:speed",),
    "minecraft:turtle_master": ("minecraft:slowness",
                                 "minecraft:resistance"),
    "minecraft:water_breathing": ("minecraft:water_breathing",),
    "minecraft:weakness": ("minecraft:weakness",),
    "minecraft:weaving": ("minecraft:weaving",),
    "minecraft:wind_charged": ("minecraft:wind_charged",),
}


def _walk_json(path, fn):
    """Прочитать JSON с диска и скормить fn (битые файлы молча
    пропускаются - скан не должен ронять генерацию)."""
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception:
        return
    fn(d)


def _collect_terrain(d, out):
    """Идентификаторы блоков из worldgen JSON: Name-строки block state
    (default_block/default_fluid/surface_rule/фичи/процессоры) + списки
    blocks у block-предикатов (matching_blocks - блоки, существующие в
    мире)."""
    if isinstance(d, dict):
        for k, v in d.items():
            if k == "Name" and isinstance(v, str) \
                    and v.startswith("minecraft:"):
                out.add(v)
            elif k == "blocks":
                for b in (v if isinstance(v, list) else [v]):
                    if isinstance(b, str) and b.startswith("minecraft:"):
                        out.add(b)
            else:
                _collect_terrain(v, out)
    elif isinstance(d, list):
        for x in d:
            _collect_terrain(x, out)


def _collect_spawners(d, out):
    """Сущности биомных спавнеров: spawners.{категория}[].type."""
    if isinstance(d, dict):
        sp = d.get("spawners")
        if isinstance(sp, dict):
            for lst in sp.values():
                for e in lst or ():
                    t = e.get("type") if isinstance(e, dict) else None
                    if isinstance(t, str) and t.startswith("minecraft:"):
                        out.add(t)
        for v in d.values():
            _collect_spawners(v, out)
    elif isinstance(d, list):
        for x in d:
            _collect_spawners(x, out)


def _collect_trial_entities(d, out):
    """Сущности trial_spawner'ов: spawn_potentials[].data.entity.id
    (только entity-словари - предметы снаряжения не задеваем)."""
    if isinstance(d, dict):
        ent = d.get("entity")
        if isinstance(ent, dict):
            eid = ent.get("id")
            if isinstance(eid, str) and eid.startswith("minecraft:"):
                out.add(eid)
        for v in d.values():
            _collect_trial_entities(v, out)
    elif isinstance(d, list):
        for x in d:
            _collect_trial_entities(x, out)


def _collect_loot(d, ctx):
    """Предметы лут-таблиц (поля name/id в entries и вложенных пулов/
    компонентов - контейнеры/бандлы кладут предметы как {"id": ...}) и
    зелья/эффекты из potion_contents (potion + custom_effects)."""
    if isinstance(d, dict):
        for k, v in d.items():
            if (k == "name" or k == "id") and isinstance(v, str) \
                    and v.startswith("minecraft:"):
                ctx["items"].add(v)
            elif k == "minecraft:potion_contents" and isinstance(v, dict):
                p = v.get("potion")
                if isinstance(p, str) and p.startswith("minecraft:"):
                    ctx["potions"].add(p)
                    for eff in _POTION_EFFECT.get(p, ()):
                        ctx["potion_effects"].add(eff)
                for ce in v.get("custom_effects") or ():
                    if isinstance(ce, dict):
                        eid = ce.get("id")
                        if isinstance(eid, str) \
                                and eid.startswith("minecraft:"):
                            ctx["potion_effects"].add(eid)
            else:
                _collect_loot(v, ctx)
    elif isinstance(d, list):
        for x in d:
            _collect_loot(x, ctx)


def read_prev_context(data_root, ns, prev_name):
    """Контекст доступности ПРЕДЫДУЩЕГО измерения цепочки - читает его
    данные с диска (data_root - тот же каталог data/, что передаётся в
    rand_advancements) и строит множества:
      terrain         блоки рельефа: default_block/default_fluid/
                      surface_rule (noise_settings) + блоки фич
                      (configured_feature) + блоки структурных процессоров
                      (processor_list)
      mobs            сущности биомных спавнеров + trial_spawner'ов
      items           предметы лут-таблиц (name/id в entries и вложенных)
      eggs            сущности, чьи спавн-яйца есть среди items (яйцо
                      даёт моба!)
      potions /
      potion_effects  зелья и эффекты из potion_contents prev
      chests          сундучные лут-таблицы ЭТОГО измерения (его
                      структуры - скан структуры_set -> jigsaw -> пул
                      -> .nbt, см. _foreign_chest_tables)
    Возвращает None, если данных prev-измерения на диске нет."""
    root = str(data_root or "")
    if not root or not prev_name:
        return None
    base = os.path.join(root, ns)
    if not os.path.isfile(os.path.join(base, "dimension",
                                       prev_name + ".json")):
        return None
    ctx = {"name": prev_name, "terrain": set(), "mobs": set(),
           "items": set(), "eggs": set(), "potions": set(),
           "potion_effects": set(), "chests": set()}
    wg = os.path.join(base, "worldgen")
    # TERRAIN (мульти-файловые реестры - с _-префиксом, как cleanup:
    # glim не должен ловить файлы glimyavane18)
    for f in ([os.path.join(wg, "noise_settings", prev_name + ".json")]
              + glob.glob(os.path.join(wg, "configured_feature",
                                       prev_name + "_*.json"))
              + glob.glob(os.path.join(wg, "processor_list",
                                       prev_name + "_*.json"))):
        _walk_json(f, lambda d: _collect_terrain(d, ctx["terrain"]))
    # MOBS
    for f in glob.glob(os.path.join(wg, "biome", prev_name + "_*.json")):
        _walk_json(f, lambda d: _collect_spawners(d, ctx["mobs"]))
    for f in glob.glob(os.path.join(base, "trial_spawner",
                                    prev_name + "_*.json")):
        _walk_json(f, lambda d: _collect_trial_entities(d, ctx["mobs"]))
    # ITEMS / POTIONS / POTION_EFFECTS
    for f in glob.glob(os.path.join(base, "loot_table",
                                    prev_name + "_*.json")):
        _walk_json(f, lambda d: _collect_loot(d, ctx))
    ctx["eggs"] = {i[:-10] for i in ctx["items"]
                   if i.endswith("_spawn_egg")}
    ctx["chests"] = _dim_chest_tables(data_root, ns, prev_name)
    return ctx


def _planks_or_logs(terrain, items):
    """Доступно ли дерево (брёвна/доски/лодки): из них крафтятся кровать
    и лодка (для триггеров slept_in_bed и boat-транспорта)."""
    for i in items:
        if i.endswith(("_boat", "_planks", "_log")):
            return True
    for b in terrain:
        if b.endswith(("_planks", "_log", "_stem")):
            return True
    return False


class _Avail(object):
    """Пулы кандидатов критериев. По умолчанию - ПОЛНЫЕ ванильные пулы
    (первое измерение цепочки: ванильный оверворлд; старые вызовы без
    prev_dim). _avail_from_ctx(ctx) строит отфильтрованные пулы - каждый
    блок/предмет/моб/эффект гарантированно доступен в ПРЕДЫДУЩЕМ мире
    цепочки. Пул, опустевший после фильтра, расширяется до полного
    ванильного и ЖУРНАЛИРУЕТСЯ в expansions (результат возвращается
    наружу - самотест печатает; условие обязано существовать)."""

    def __init__(self):
        self.blocks = list(PLACEABLE_BLOCKS)
        self.tool_targets = {t: list(bs) for t, bs in TOOL_TARGETS.items()}
        self.interact_pairs = list(_INTERACT_PAIRS)
        self.foods = list(FOODS)
        self.items = list(NOTABLE_ITEMS)
        self.effects = list(EFFECTS)
        self.potions = list(POTIONS)
        self.buckets = list(BUCKETS)
        self.enchantables = list(ENCHANTABLES)
        self.fish = list(FISH_LOOT)
        self.wearables = list(WEARABLE_ITEMS)
        self.usables = list(USABLE_ITEMS)
        self.mobs_kill = list(MOBS)
        self.baby_mobs = list(BABY_MOBS)
        self.tameable = list(TAMEABLE)
        self.vehicles = list(VEHICLES)
        self.breedable = list(BREEDABLE)
        self.summonable = list(SUMMONABLE)
        self.explosion_sources = list(EXPLOSION_SOURCES)
        self.enterable = list(ENTERABLE_BLOCKS)
        self.bee_blocks = ["minecraft:bee_nest", "minecraft:beehive"]
        self.ench_tools = list(_ENCH_TOOLS)
        self.allay_items = list(NOTABLE_ITEMS)
        self.triggers = {t for t, _g in TRIGGER_POOL}
        self.expansions = []


def _avail_from_ctx(ctx):
    """Отфильтрованные по контексту prev-мира пулы (см. класс _Avail).
    Правила фильтрации (фидбек юзера, «ограничивая блоки/мобы/предметы
    необходимыми именно на предыдущем измерении»):
      блоки (placed_block/allay/item_used_on_block/enter_block/bee_nest)
                       ? TERRAIN ? ITEMS;
      сущности (killed/tame/bred/interact/summoned/vehicles/explosion)
                       ? MOBS ? спавн-яйца из ITEMS (tnt/wind_charge -
                       предметы-сущности из ITEMS);
      предметы (consume/inventory/fishing/enchanted/bucket/using/
      durability/инструменты) ? ITEMS ? TERRAIN(блочные);
      эффекты/зелья   - из potion_contents prev;
      сундучные таблицы - только prev-измерения (передаётся отдельно).
    Триггеры с ФИКСИРОВАННЫМ предметом/блоком/сущностью, которых нет в
    prev, становятся недоступными (used_totem/shot_crossbow/bee_nest_
    destroyed/villager_trade/cured_zombie_villager/allay/slept_in_bed/
    ride_entity_in_lava/fishing_rod_hooked)."""
    av = _Avail()
    exp = av.expansions
    terrain, items = ctx["terrain"], ctx["items"]
    mobs = ctx["mobs"] | ctx["eggs"]
    wood = _planks_or_logs(terrain, items)

    def block_ok(b):
        return b in items or (b in terrain and b not in _NEVER_DROPS)

    def item_ok(i):
        return i in items or (i in terrain and i in _BLOCK_ITEM_IDS)

    def ent_ok(e):
        return e in mobs or item_ok(e)   # tnt/wind_charge - предметы

    def pick(pool, ok, what):
        out = [x for x in pool if ok(x)]
        if not out:
            exp.append(what)
            return list(pool)
        return out

    av.blocks = pick(PLACEABLE_BLOCKS, block_ok, "blocks")
    tt = {}
    for t, blks in TOOL_TARGETS.items():
        if item_ok(t):
            bs = [b for b in blks if block_ok(b)]
            if bs:
                tt[t] = bs
    if not tt:
        exp.append("tools")
        tt = {t: list(bs) for t, bs in TOOL_TARGETS.items()}
    av.tool_targets = tt
    av.interact_pairs = pick(_INTERACT_PAIRS,
                             lambda p: ent_ok(p[0]) and item_ok(p[1]),
                             "interact")
    av.ench_tools = pick(_ENCH_TOOLS, lambda p: item_ok(p[0]), "ench_tools")
    av.allay_items = pick(NOTABLE_ITEMS, item_ok, "allay_items")
    av.foods = pick(FOODS, item_ok, "foods")
    av.items = pick(NOTABLE_ITEMS, item_ok, "notable")
    av.effects = pick(EFFECTS, lambda e: e in ctx["potion_effects"],
                      "effects")
    av.potions = pick(POTIONS, lambda p: p in ctx["potions"], "potions")
    av.buckets = pick(BUCKETS, item_ok, "buckets")
    av.enchantables = pick(ENCHANTABLES, item_ok, "enchantables")
    av.fish = pick(FISH_LOOT, item_ok, "fish")
    av.wearables = pick(WEARABLE_ITEMS, item_ok, "wearables")
    av.usables = pick(USABLE_ITEMS, item_ok, "usables")
    av.mobs_kill = pick(MOBS, ent_ok, "mobs")
    av.baby_mobs = pick(BABY_MOBS, ent_ok, "baby_mobs")
    av.tameable = pick(TAMEABLE, ent_ok, "tameable")
    av.breedable = pick(BREEDABLE, ent_ok, "breedable")
    av.summonable = pick(SUMMONABLE, ent_ok, "summonable")
    av.explosion_sources = pick(EXPLOSION_SOURCES, ent_ok, "explosions")
    av.vehicles = pick(VEHICLES,
                       lambda v: ent_ok(v)
                       or (v == "#minecraft:boat" and wood),
                       "vehicles")
    # enter_block: войти можно и в блок без формы предмета (powder_snow -
    # ведром порошкового снега)
    av.enterable = pick(
        ENTERABLE_BLOCKS,
        lambda b: block_ok(b) or (b == "minecraft:powder_snow"
                                  and "minecraft:powder_snow_bucket" in items),
        "enterable")
    # пчелиное гнездо - фиксированные блоки: без них триггер недоступен
    av.bee_blocks = [b for b in ("minecraft:bee_nest", "minecraft:beehive")
                     if block_ok(b)]

    # доступность триггеров с фиксированными требованиями
    if "minecraft:villager" not in mobs:
        av.triggers.discard("minecraft:villager_trade")
    if "minecraft:zombie_villager" not in mobs:
        av.triggers.discard("minecraft:cured_zombie_villager")
    if not wood and not any(i.endswith("_bed") for i in items):
        av.triggers.discard("minecraft:slept_in_bed")
    if "minecraft:allay" not in mobs:
        av.triggers.discard("minecraft:allay_drop_item_on_block")
    if not item_ok("minecraft:totem_of_undying"):
        av.triggers.discard("minecraft:used_totem")
    if not item_ok("minecraft:crossbow"):
        av.triggers.discard("minecraft:shot_crossbow")
    if not av.bee_blocks:
        av.triggers.discard("minecraft:bee_nest_destroyed")
    if "minecraft:lava" not in terrain:
        av.triggers.discard("minecraft:ride_entity_in_lava")
    if "minecraft:water" not in terrain:
        av.triggers.discard("minecraft:fishing_rod_hooked")
    return av


def _merge_dim_guard(conds, dim_id):
    """Добавить в conditions критерия player-условие «игрок НЕ в этом
    измерении» (иначе телепорт зациклится), объединив его с player-
    условиями самого триггера (vehicle у started_riding, flags у
    placed_block/using_item). Мутирует и возвращает conds."""
    extra_players = []
    if "player" in conds:
        pv = conds.pop("player")
        if isinstance(pv, list):
            extra_players = pv
        elif isinstance(pv, dict):
            extra_players = [pv]
    conds["player"] = [{
        "condition": "minecraft:inverted",
        "term": {"condition": "minecraft:location_check",
                 "predicate": {"dimension": dim_id}},
    }] + extra_players
    return conds


def _step_icon(rng, conds_list):
    """Иконка шага: предмет/блок из УСЛОВИЙ шага (тост читается мгновенно
    - «Съешь хлеб» с иконкой хлеба), иначе случайная из ROOT_ICONS /
    PLACEABLE_BLOCKS (фидбек-компромисс «icon random из ROOT_ICONS/блоков»)."""
    for conds in conds_list:
        it = _cond_item(conds)
        if isinstance(it, str):
            return it
        its = conds.get("items")
        if isinstance(its, list) and its and isinstance(its[0], dict) \
                and isinstance(its[0].get("items"), str):
            return its[0]["items"]
        tool = _loc_tool_pred(conds)
        if tool and isinstance(tool.get("items"), str):
            return tool["items"]
    for conds in conds_list:
        for b in _loc_blocks(conds):
            if b in PLACEABLE_BLOCKS:
                return b
        eb = conds.get("block")
        if isinstance(eb, str) and eb in PLACEABLE_BLOCKS:
            return eb
    return rng.choice(ROOT_ICONS + PLACEABLE_BLOCKS)


# ---------------------------------------------------------------------------
# Главная функция
# ---------------------------------------------------------------------------

def rand_advancements(rng, ns, name, default_block, tp_y,
                      data_root=None, loot_ids=None,
                      prev_dim=None, prev_ctx=None):
    """Генерирует достижения + reward-функции для измерения <ns>:<name>:
    видимую (impossible, выдаётся reward-функцией телепорта), скрытую _tp
    (критерии-НЕВОЗМОЖКИ, грантуются ТОЛЬКО шагами), видимые ШАГИ пути
    (реальные триггеры, по одному на группу - ПРОГРЕСС: выполненные
    светятся под ачивкой) и заглушку видимости _show (см. докстринг
    модуля: без выполненного ребёнка ветка вкладки с корнем impossible
    невидима; tick самовыдаётся каждому игроку в первый же тик - в т.ч.
    зашедшим на сервер позже, чего не покрывает grant в load-функции).

    default_block      - блок-основа noise_settings (идёт иконкой видимой
                         ачивки; если у блока нет формы предмета - случайный
                         фолбэк-предмет);
    tp_y               - УЖЕ вычисленная генератором миров безопасная высота
                         телепорта (DimensionGenerator.tp_y: в open - падение
                         с неба, в cavern - ниже кровли, в void - уровень
                         островов); платформу НЕ ставим (решение юзера -
                         поверхность под игроком оставляем миру);
    data_root          - каталог data/ пака (дерево достижений, сундучные
                         таблицы, данные prev-измерения);
    loot_ids           - id лут-таблиц этого измерения (для rewards.loot);
    prev_dim           - имя ПРЕДЫДУЩЕГО измерения ЦЕПОЧКИ (родитель
                         видимой ачивки; пулы критериев фильтруются по
                         доступности его мира) или None = первое (без
                         фильтров - ванильный оверворлд). Вызову доверяем:
                         в --print предыдущее измерение ещё не на диске;
    prev_ctx           - готовый контекст доступности (read_prev_context);
                         если None и prev_dim задан - читается с диска.

    Возвращает {"advancements", "functions", "trigger", "hint",
    "parent", "n_steps", "step_titles", "expansions"} (последние четыре
    ключа - новые; старые потребители первых четырёх не ломаются).
    На диск ничего не пишет."""
    dim_id = "%s:%s" % (ns, name)
    root_id = "%s:adv/root" % ns
    vis_id = "%s:adv/%s" % (ns, name)
    hid_id = "%s:adv/%s_tp" % (ns, name)
    show_id = "%s:adv/%s_show" % (ns, name)
    func_name = "%s_tp" % name
    func_id = "%s:%s" % (ns, func_name)

    # --- ЦЕПОЧКА: родитель видимой ачивки - ачивка ПРЕДЫДУЩЕГО
    #     сгенерированного измерения (generate_dimension пишет миры на
    #     диск последовательно и передаёт порядок). prev_dim=None -
    #     хвост цепочки с диска (самый глубокий лист; перегенерация
    #     середины корректно осиротивает нижнюю ветку) либо корень.
    tree = read_adv_tree(data_root, ns, skip_name=name) if data_root else {}
    if prev_dim is not None and prev_dim != name:
        parent = "%s:adv/%s" % (ns, prev_dim)
    else:
        parent = _chain_tail(tree, root_id) or root_id

    # --- контекст доступности prev-мира: условия критериев на 100%
    #     достижимы из ПРЕДЫДУЩЕГО измерения (его террейн/мобы/лут)
    ctx = prev_ctx
    if ctx is None and prev_dim and prev_dim != name and data_root:
        ctx = read_prev_context(data_root, ns, prev_dim)
    av = _avail_from_ctx(ctx) if ctx else _Avail()

    # --- сундучные таблицы: в цепочке - ТОЛЬКО таблицы prev-измерения
    #     (его структуры: игрок уже там был); без prev_dim - прежнее
    #     поведение, любые чужие миры со диска
    foreign_all = _foreign_chest_tables(data_root, ns, name) \
        if data_root else []
    if prev_dim is not None and prev_dim != name:
        chest_tables = [t for t in foreign_all
                        if _dim_of_loot_table(t) == prev_dim]
    else:
        chest_tables = foreign_all

    # --- критерии: 2-4 группы самостоятельных задач (по И;
    #     requirements_matrix). dim_name нужен бирке в interact-паре
    criteria, requirements = _rand_criteria(rng, chest_tables, name, av)

    # условие «игрок НЕ в этом измерении» + собственные player-условия
    # триггера - теперь в АЧИВКАХ-ШАГАХ (критерии скрытой - DUMMY и
    # условий не проверяют вовсе)
    for _trigger, conds, _hint in criteria:
        _merge_dim_guard(conds, dim_id)

    # --- скрытая ачивка-телепортёр (без display -> не видна в меню):
    #     критерии c0..cN-1 - DUMMY (minecraft:impossible, БЕЗ условий) -
    #     выдаются ТОЛЬКО командой advancement grant ... only <hid> c<i>
    #     из reward-функций ШАГОВ; requirements_matrix прежняя (OR внутри
    #     группы: все члены группы грантуются её шагом вместе);
    #     rewards: функция-телепорт всегда + иногда опыт / лут /
    #     разблокировка рецептов (AdvancementRewards 26.2:
    #     experience | function | loot | recipes - всё сверено с кодеком)
    crit_json = {"c%d" % i: {"trigger": "minecraft:impossible"}
                 for i in range(len(criteria))}

    # подсказка = все условия в одну фразу (соединитель случайный);
    # все критерии, кроме первого, начинаются со строчной буквы -
    # фраза читается как одно предложение; пустые подсказки
    # (дубликаты контейнерной OR-группы) пропускаются
    hint = criteria[0][2]
    for _tr, _c, h in criteria[1:]:
        if not h:
            continue
        h = h[0].lower() + h[1:]
        hint += rng.choice(HINT_JOINERS) + h

    # --- Y телепорта приходит ГОТОВЫМ от генератора миров (tp_y уже учитывает
    #     форму мира: open - у неба, cavern - ниже кровли, void - у островов)

    # --- иконка видимой ачивки: default_block или фолбэк (нет item-формы)
    icon = default_block if default_block not in ITEMLESS_BLOCKS \
        else rng.choice(ROOT_ICONS)

    # --- видимая ачивка (impossible - выдаёт только reward-функция);
    #     description - загадка-присказка + «- путь из N шагов» (ПРОГРЕСС:
    #     под этой ачивкой видны дети-ШАГИ, выполненные светятся)
    pretty = _pretty(name)
    n_steps = len(requirements)
    visual = {
        "parent": parent,
        "criteria": {"grant": {"trigger": "minecraft:impossible"}},
        "display": {
            "announce_to_chat": rng.random() < 0.7,
            "description": {"color": "gray",
                            "text": "%s - путь из %d шагов"
                                     % (hint, n_steps)},
            "frame": rng.choice(["task", "task", "goal", "challenge"]),
            "icon": {"id": icon},
            "show_toast": True,
            "title": {"color": rng.choice(TITLE_COLORS),
                      "text": rng.choice(TITLE_PATTERNS).format(N=pretty)},
        },
        "requirements": [["grant"]],
    }

    rewards = {"function": func_id}
    if rng.random() < 0.5:
        rewards["experience"] = rng.choice([10, 25, 50, 75, 100])
    if loot_ids:
        # наш собственный лут данжей - приятнее ванильных сундуков
        # (loot_ids приходят уже полными id вида <ns>:<name>)
        if rng.random() < 0.6:
            rewards["loot"] = [
                lt if ":" in lt else "%s:%s" % (ns, lt)
                for lt in rng.sample(loot_ids,
                                     rng.randint(1, min(3, len(loot_ids))))]
        elif rng.random() < 0.3:
            rewards["loot"] = ["minecraft:" + rng.choice(CHEST_LOOT)]
    elif rng.random() < 0.3:
        rewards["loot"] = ["minecraft:" + rng.choice(CHEST_LOOT)]
    if rng.random() < 0.3:
        rewards["recipes"] = ["minecraft:" + rng.choice(RECIPE_POOL)
                              for _ in range(rng.randint(1, 3))]

    hidden = {
        "parent": vis_id,
        "criteria": crit_json,
        "requirements": requirements,
        "rewards": rewards,
    }

    advancements = {vis_id: visual, hid_id: hidden}
    functions = {func_name: None}   # текст телепорта - ниже

    # --- ШАГИ ПРОГРЕССА: по одному на группу критериев. Критерии шага -
    #     РЕАЛЬНЫЕ триггеры (перенесены из скрытой); rewards-функция
    #     грантит все c<idx> своей группы + actionbar «шаг открыты» +
    #     звук. После телепорта шаги НЕ отзываются - визуальный рекорд
    step_titles = []
    for j, grp in enumerate(requirements):
        step_id = "%s:adv/%s_step%d" % (ns, name, j)
        step_fname = "%s_step%d" % (name, j)
        step_fid = "%s:%s" % (ns, step_fname)
        g = [criteria[int(cn[1:])] for cn in grp]
        word = _STEP_WORDS.get(g[0][0], "Испытание")
        title = "Шаг %d из %d: %s" % (j + 1, n_steps, word)
        # загадка шага: все критерии группы через «или» (запасной
        # вариант / альтернативные сундуки - читаются как выбор)
        parts = []
        for _tr, _c, h in g:
            if h:
                parts.append(h if not parts else h[0].lower() + h[1:])
        step_hint = " или ".join(parts) or _HINT_FALLBACK
        icon_j = _step_icon(rng, [c for _t, c, _h in g])
        step_crit = {}
        for m, (trig, conds, _h) in enumerate(g):
            step_crit["s%d" % m] = {"conditions": conds, "trigger": trig}
        advancements[step_id] = {
            "parent": vis_id,
            "criteria": step_crit,
            "display": {
                "announce_to_chat": False,
                "description": {"color": "gray", "text": step_hint},
                "frame": "task",
                "icon": {"id": icon_j},
                "show_toast": True,
                "title": {"color": "yellow", "text": title},
            },
            "requirements": [["s%d" % m for m in range(len(g))]],
            "rewards": {"function": step_fid},
        }
        lines = ["# %s - шаг %d из %d пути в %s (%s)"
                 % (step_fid, j + 1, n_steps, dim_id, word)]
        for cn in grp:
            lines.append("advancement grant @s only %s %s" % (hid_id, cn))
        lines.append('title @s actionbar {"text":"%s: шаг %d из %d '
                     'открыт","color":"yellow"}'
                     % (pretty, j + 1, n_steps))
        lines.append("playsound %s master @s ~ ~ ~ 1 1"
                     % rng.choice(SOUND_POOL))
        functions[step_fname] = "\n".join(lines) + "\n"
        step_titles.append(title)

    # --- ЗАГЛУШКА ВИДИМОСТИ: корень вкладки (adv/root) построен на trigger
    #     minecraft:impossible и никогда не выполняется, а правило SHOW
    #     (AdvancementVisibilityEvaluator 26.2) всплывает вверх только от
    #     выполненного/видимого ребёнка - без заглушки вся вкладка
    #     невидима, пока не заработана первая ачивка. Заглушка - ребёнок
    #     видимой ачивки: tick выполняется сам у КАЖДОГО игрока в первый
    #     же тик пребывания в мире (поздно зашедших - тоже; grant в
    #     load-функции их бы не покрыл - осознанный выбор tick).
    #     БЕЗ display (узел невидим сам по себе), БЕЗ rewards и БЕЗ
    #     requirements (один критерий - requirements не нужны; отдельный
    #     файл, механику requirements видимой/скрытой ачивок не трогает).
    #     Имя <name>_show.json совместимо с cleanup_dimension (префикс
    #     <name>_), файл на диск пишет общий цикл generate_dimension.py.
    advancements[show_id] = {
        "parent": vis_id,
        "criteria": {"show": {"trigger": "minecraft:tick"}},
    }

    # --- корень вкладки: создаётся один раз, не пересоздаётся
    if data_root is None or not os.path.exists(
            os.path.join(str(data_root), ns, "advancement", "adv", "root.json")):
        advancements[root_id] = {
            "criteria": {"root": {"trigger": "minecraft:impossible"}},
            "display": {
                "announce_to_chat": False,
                "background": rng.choice(BACKGROUNDS),
                "description": {"color": "gray",
                                "text": rng.choice(ROOT_DESCS)},
                "frame": "task",
                "icon": {"id": rng.choice(ROOT_ICONS)},
                "show_toast": False,
                "title": {"color": rng.choice(TITLE_COLORS),
                          "text": rng.choice(ROOT_TITLES)},
            },
            "requirements": [["root"]],
        }

    # --- reward-функция телепорта: снять скрытую (revoke сбрасывает
    #     прогресс ВСЕХ критериев - шаги при этом остаются выполненными:
    #     визуальный рекорд пути), выдать видимую, телепорт, защита,
    #     случайный звук (весь пул - от ambient до music). Платформу не
    #     ставим (решение юзера) - игрок телепортируется на tp_y, а что
    #     окажется под ногами, решает сам мир.
    sound = rng.choice(SOUND_POOL)
    functions[func_name] = (
        "# %s - телепорт в %s (выдаётся скрытой ачивкой %s, когда все "
        "%d шага пройдены)\n"
        "advancement revoke @s only %s\n"
        "advancement grant @s only %s\n"
        "execute in %s run tp @s ~ %d ~\n"
        "effect give @s minecraft:resistance 30 4 true\n"
        "playsound %s master @s ~ ~ ~ 1 1\n"
    ) % (func_id, dim_id, hid_id, n_steps, hid_id, vis_id,
         dim_id, tp_y, sound)

    return {
        "advancements": advancements,
        "functions": functions,
        "trigger": " + ".join(
            criteria[int(grp[0][1:])][0].split(":", 1)[1]
            for grp in requirements),
        "hint": hint,
        "parent": parent,
        "n_steps": n_steps,
        "step_titles": step_titles,
        "expansions": list(av.expansions),
    }


# ---------------------------------------------------------------------------
# Самопроверка
# ---------------------------------------------------------------------------

def _check_tree_invariants(data_root, ns, n_expected):
    """Мини-проверка дерева на диске: один корень, у узла <= 2 видимых детей,
    все parent-ссылки валидны. Возвращает список проблем."""
    tree = read_adv_tree(data_root, ns)
    problems = []
    if len(tree) != n_expected:
        problems.append("узлов %d, ожидалось %d" % (len(tree), n_expected))
    roots = [i for i, p in tree.items() if not p or p not in tree]
    if len(roots) != 1:
        problems.append("корней %d: %s" % (len(roots), roots))
    children = {}
    for i, p in tree.items():
        if p:
            children.setdefault(p, []).append(i)
    for i, ch in children.items():
        if len(ch) > 2:
            problems.append("у %s детей %d (>2)" % (i, len(ch)))
    for i, p in tree.items():
        if p and p not in tree:
            problems.append("битый parent у %s: %s" % (i, p))
    return problems


# ---------------------------------------------------------------------------
# Хелперы самотеста цепочки достижимости
# ---------------------------------------------------------------------------

def _write_fake_structures(td, ns, nm):
    """Минимальный «прошлый мир» для сундучного скана: полный путь
    structure_set -> jigsaw-структура -> пул -> .nbt-сундук (валидный
    минимальный NBT: корневой compound с одним TAG_String LootTable -
    ридер _scan_nbt_loot_tags строгий)."""
    wp = os.path.join(td, ns, "worldgen")
    for sub in ("structure_set", "structure",
                os.path.join("template_pool", nm)):
        os.makedirs(os.path.join(wp, sub), exist_ok=True)
    with open(os.path.join(wp, "structure_set",
                           nm + "_set1.json"), "w",
              encoding="utf-8") as f:
        json.dump({"placement": {
            "type": "minecraft:random_spread", "salt": 1,
            "spacing": 32, "separation": 8},
            "structures": [
                {"structure": "%s:%s_jig1" % (ns, nm),
                 "weight": 1}]}, f)
    with open(os.path.join(wp, "structure",
                           nm + "_jig1.json"), "w",
              encoding="utf-8") as f:
        json.dump({"type": "minecraft:jigsaw",
                   "biomes": "#%s:has_structure/x" % ns,
                   "step": "surface_structures",
                   "start_pool": "%s:%s/start" % (ns, nm),
                   "start_jigsaw_name": "x",
                   "size": 5,
                   "max_distance_from_center": 39}, f)
    with open(os.path.join(wp, "template_pool", nm,
                           "start.json"), "w",
              encoding="utf-8") as f:
        json.dump({"elements": [{"weight": 1, "element": {
            "element_type": "minecraft:single_pool_element",
            "location": "%s:%s/hut1" % (ns, nm),
            "processors": "minecraft:empty",
            "projection": "rigid"}}]}, f)
    sdir = os.path.join(td, ns, "structure", nm)
    os.makedirs(sdir, exist_ok=True)
    sbytes = ("%s:%s_loot1" % (ns, nm)).encode()
    nbt = (b"\x0a\x00\x00"          # TAG_Compound с пустым именем
           b"\x08\x00\x09LootTable"  # TAG_String "LootTable"
           + struct.pack(">H", len(sbytes)) + sbytes
           + b"\x00")                 # TAG_End
    with open(os.path.join(sdir, "hut1.nbt"), "wb") as f:
        f.write(gzip.compress(nbt, mtime=0))


def _write_fake_prev_world(td, ns, nm, poor=False):
    """Фейковый ПРЕДЫДУЩИЙ мир цепочки для самотеста: пишет только то, что
    читают read_prev_context / _foreign_chest_tables. Нормальный (poor=
    False) мир подобран ТАК, чтобы каждый отфильтрованный пул был непуст
    (расширений не требуется - строгая проверка достижимости); poor=True -
    выжженный мир (только камень): все пулы расширяются и ЖУРНАЛИРУЮТСЯ."""
    base = os.path.join(td, ns)
    for sub in ("dimension", "worldgen/noise_settings",
                "worldgen/configured_feature", "worldgen/biome",
                "loot_table"):
        os.makedirs(os.path.join(base, *sub.split("/")), exist_ok=True)

    def w(rel, obj):
        with open(os.path.join(base, *rel.split("/")), "w",
                  encoding="utf-8") as f:
            json.dump(obj, f)

    w("dimension/%s.json" % nm, {
        "type": "%s:%s" % (ns, nm),
        "generator": {"type": "minecraft:noise",
                      "settings": "%s:%s" % (ns, nm),
                      "biome_source": {"type": "minecraft:fixed",
                                       "biome": "%s:%s_b0" % (ns, nm)}}})
    if poor:
        w("worldgen/noise_settings/%s.json" % nm, {
            "default_block": {"Name": "minecraft:stone"}})
        return
    # TERRAIN: основа/жидкость + слои поверхности + фича-жила
    w("worldgen/noise_settings/%s.json" % nm, {
        "default_block": {"Name": "minecraft:stone"},
        "default_fluid": {"Name": "minecraft:water"},
        "sea_level": 63,
        "surface_rule": {"type": "minecraft:sequence", "sequence": [
            {"type": "minecraft:block",
             "result_state": {"Name": "minecraft:grass_block"}},
            {"type": "minecraft:block",
             "result_state": {"Name": "minecraft:oak_planks"}},
            {"type": "minecraft:block",
             "result_state": {"Name": "minecraft:oak_log"}},
            {"type": "minecraft:block",
             "result_state": {"Name": "minecraft:sand"}},
            {"type": "minecraft:block",
             "result_state": {"Name": "minecraft:glass"}}]}})
    w("worldgen/configured_feature/%s_vein1.json" % nm, {
        "type": "minecraft:ore",
        "config": {"size": 8, "discard_chance_on_air_exposure": 0.0,
                   "targets": [
                       {"target": {"predicate_type": "minecraft:tag_match",
                                   "tag": "minecraft:stone_ore_replaceables"},
                        "state": {"Name": "minecraft:andesite"}},
                       {"target": {"predicate_type": "minecraft:tag_match",
                                   "tag": "minecraft:stone_ore_replaceables"},
                        "state": {"Name": "minecraft:dirt"}}]}})
    # MOBS: спавнеры биома (зомби-семейство, деревенские, животные,
    # крипер/скелет/лошадь/волк; визер - для summoned_entity)
    mobs = ["minecraft:zombie", "minecraft:zombie_villager",
            "minecraft:villager", "minecraft:cow", "minecraft:sheep",
            "minecraft:pig", "minecraft:skeleton", "minecraft:creeper",
            "minecraft:horse", "minecraft:wolf", "minecraft:wither"]
    w("worldgen/biome/%s_b0.json" % nm, {
        "spawners": {
            "monster": [{"type": m, "weight": 10,
                         "minCount": 1, "maxCount": 2} for m in mobs],
            "creature": [{"type": "minecraft:cow", "weight": 10,
                          "minCount": 2, "maxCount": 4}]},
        "spawn_costs": {}, "carvers": {}, "features": [],
        "temperature": 0.7, "downfall": 0.5, "has_precipitation": True,
        "effects": {}, "attributes": {}})
    # ITEMS: широкий набор (все отфильтрованные пулы непусты)
    loot_items = [
        # еда / заметные предметы
        "minecraft:bread", "minecraft:apple", "minecraft:golden_apple",
        "minecraft:cookie", "minecraft:cooked_beef",
        "minecraft:honey_bottle", "minecraft:iron_ingot",
        "minecraft:diamond", "minecraft:emerald", "minecraft:gold_ingot",
        "minecraft:coal", "minecraft:bone", "minecraft:string",
        "minecraft:stick", "minecraft:arrow", "minecraft:book",
        "minecraft:paper", "minecraft:name_tag", "minecraft:saddle",
        "minecraft:wheat", "minecraft:carrot",
        # зачаровываемое / используемое / изнашиваемое
        "minecraft:diamond_sword", "minecraft:iron_sword",
        "minecraft:diamond_pickaxe", "minecraft:bow",
        "minecraft:crossbow", "minecraft:spyglass",
        "minecraft:wooden_sword", "minecraft:golden_sword",
        "minecraft:fishing_rod", "minecraft:flint_and_steel",
        # инструменты item_used_on_block / интеракции
        "minecraft:iron_axe", "minecraft:iron_hoe",
        "minecraft:iron_shovel", "minecraft:shears",
        "minecraft:honeycomb", "minecraft:bucket", "minecraft:water_bucket",
        "minecraft:milk_bucket", "minecraft:cod",
        "minecraft:enchanted_book",
        # спавн-яйца (яйцо даёт моба!)
        "minecraft:zombie_spawn_egg", "minecraft:cow_spawn_egg",
        "minecraft:wolf_spawn_egg", "minecraft:cat_spawn_egg",
        "minecraft:villager_spawn_egg", "minecraft:horse_spawn_egg",
        "minecraft:allay_spawn_egg", "minecraft:sheep_spawn_egg",
        "minecraft:pig_spawn_egg", "minecraft:skeleton_spawn_egg",
        # особое
        "minecraft:red_bed", "minecraft:totem_of_undying",
        "minecraft:bee_nest", "minecraft:oak_boat", "minecraft:tnt",
    ]
    w("loot_table/%s_loot1.json" % nm, {"pools": [{"rolls": 1, "entries": [
        {"type": "minecraft:item", "name": it, "weight": 1}
        for it in loot_items]}]})
    # POTIONS / POTION_EFFECTS: potion_contents (potion + custom_effects)
    w("loot_table/%s_loot2.json" % nm, {"pools": [{"rolls": 1, "entries": [
        {"type": "minecraft:item", "name": "minecraft:potion",
         "weight": 1,
         "functions": [{"function": "minecraft:set_components",
                        "components": {"minecraft:potion_contents": {
                            "potion": "minecraft:swiftness"}}}]},
        {"type": "minecraft:item", "name": "minecraft:splash_potion",
         "weight": 1,
         "functions": [{"function": "minecraft:set_components",
                        "components": {"minecraft:potion_contents": {
                            "potion": "minecraft:fire_resistance",
                            "custom_effects": [
                                {"id": "minecraft:mining_fatigue",
                                 "amplifier": 1, "duration": 200},
                                {"id": "minecraft:regeneration",
                                 "amplifier": 1, "duration": 200}]}}}]},
        {"type": "minecraft:item", "name": "minecraft:lingering_potion",
         "weight": 1,
         "functions": [{"function": "minecraft:set_components",
                        "components": {"minecraft:potion_contents": {
                            "potion": "minecraft:weakness"}}}]},
        {"type": "minecraft:item", "name": "minecraft:potion",
         "weight": 1,
         "functions": [{"function": "minecraft:set_components",
                        "components": {"minecraft:potion_contents": {
                            "potion": "minecraft:healing"}}}]}]}]})
    # структура с сундуком (контейнерный триггер следующего измерения)
    _write_fake_structures(td, ns, nm)


def _write_fake_advancements(td, ns, res):
    """Выгрузка результата rand_advancements на диск (имитация main)."""
    adv_dir = os.path.join(td, ns, "advancement", "adv")
    os.makedirs(adv_dir, exist_ok=True)
    for aid, ajson in res["advancements"].items():
        with open(os.path.join(adv_dir, aid.split("/", 1)[1] + ".json"),
                  "w", encoding="utf-8") as f:
            f.write(json.dumps(ajson))


def _step_cond_refs(res):
    """Все блоки/предметы/мобы/эффекты/зелья/таблицы из критериев ШАГОВ
    результата (для проверки достижимости из prev-мира)."""
    out = {"blocks": [], "items": [], "entities": [], "effects": [],
           "potions": [], "tables": []}
    for aid, a in res["advancements"].items():
        if not _STEP_FILE_RX.search(aid.split("/", 1)[-1]):
            continue
        for cv in a["criteria"].values():
            conds = cv.get("conditions") or {}
            it = conds.get("item")
            if isinstance(it, dict) and isinstance(it.get("items"), str):
                out["items"].append(it["items"])
            for e in (conds.get("items") or ()):
                if isinstance(e, dict) and isinstance(e.get("items"), str):
                    out["items"].append(e["items"])
            tool = _loc_tool_pred(conds)
            if tool and isinstance(tool.get("items"), str):
                out["items"].append(tool["items"])
            for b in _loc_blocks(conds):
                out["blocks"].append(b)
            eb = conds.get("block")
            if isinstance(eb, str):
                out["blocks"].append(eb)
            for key in ("entity", "victims", "cause", "child",
                        "projectile", "bystander"):
                out["entities"] += _entity_ids(conds, key)
            # vehicle в player-условиях самого триггера (started_riding)
            pl = conds.get("player")
            for p in (pl if isinstance(pl, list)
                      else [pl] if isinstance(pl, dict) else ()):
                if isinstance(p, dict) and p.get("condition") == \
                        "minecraft:entity_properties":
                    v = p.get("predicate", {}).get("minecraft:vehicle", {}) \
                        .get("minecraft:entity_type")
                    if v:
                        out["entities"].append(v)
            effs = conds.get("effects")
            if isinstance(effs, dict):
                out["effects"] += list(effs)
            p = conds.get("potion")
            if isinstance(p, str):
                out["potions"].append(p)
            lt = conds.get("loot_table")
            if isinstance(lt, str):
                out["tables"].append(lt)
    return out


def _assert_reachable(res, ctx, name):
    """(а) самотеста ЦЕПОЧКИ: каждый блок/предмет/моб/эффект/зелье из
    условий ШАГОВ измерения <name> доступен в ПРЕДЫДУЩЕМ мире (его
    ctx). Правила зеркальны фильтрам _avail_from_ctx (tnt/wind_charge -
    предметы-сущности из ITEMS; лодка - из дерева; powder_snow - из
    ведра порошкового снега)."""
    refs = _step_cond_refs(res)
    terrain, items = ctx["terrain"], ctx["items"]
    mobs = ctx["mobs"] | ctx["eggs"]
    wood = _planks_or_logs(terrain, items)
    for b in refs["blocks"]:
        ok = b in terrain or b in items or (
            b == "minecraft:powder_snow"
            and "minecraft:powder_snow_bucket" in items)
        assert ok, (name, "блок недоступен в prev:", b)
    for i in refs["items"]:
        assert i in items or (i in terrain and i in _BLOCK_ITEM_IDS), \
            (name, "предмет недоступен в prev:", i)
    for e in refs["entities"]:
        if e == "#minecraft:boat":
            assert wood or any(x.endswith("_boat") for x in items), \
                (name, "лодка недоступна в prev")
        else:
            assert e in mobs or e in items or \
                (e in terrain and e in _BLOCK_ITEM_IDS), \
                (name, "существо недоступно в prev:", e)
    for eff in refs["effects"]:
        assert eff in ctx["potion_effects"], \
            (name, "эффект недоступен в prev:", eff)
    for p in refs["potions"]:
        assert p in ctx["potions"], (name, "зелье недоступно в prev:", p)
    for t in refs["tables"]:
        assert _dim_of_loot_table(t) == ctx["name"], \
            (name, "сундук не из prev-мира:", t)


def _self_test(seeds=24):
    """Прогон на seeds seed'ах: воспроизводимость, инварианты дерева при
    инкрементальной генерации, валидность ID и mcfunction-команд, заглушки
    видимости _show, отсутствие удалённых триггеров и недостижимых в
    изолированном наборе кастомных миров условий (другие измерения,
    порталы, ванильные сундуки, грозы), согласованность requirements-
    матрицы со criteria; русские имена для всех id всех пулов; ЗАГАДКИ
    в духе фольклора для всех блоков/предметов (две по 4-14 слов с тегом
    приёма, первое колено <= 7 слов, без канцелярита, >= 3 приёма на
    окно из 20) и НЕПУСТЫЕ ОПОЗНАВАЕМЫЕ подсказки (каждый триггер,
    ~12-15 слов на критерий, без незаполненных шаблонов и многоточий;
    итоговая склейка <= ~15 слов на критерий и тоже без канцелярита);
    контейнерный триггер только с НАШИМИ таблицами (в цепочке - только
    ПРЕДЫДУЩЕГО измерения) и только когда такие таблицы есть.

    НОВОЕ (переработка прогресса/независимости/цепочки):
    - скрытая _tp: критерии DUMMY impossible, выдаются только шагами;
    - ШАГИ: по одному на группу, валидный parent/display/rewards,
      функция грантит критерии СВОЕЙ группы + actionbar с номером;
      реальные триггеры (с «не в этом измерении») живут в шагах;
    - НЕЗАВИСИМОСТЬ: в критериях шагов нет доп. player-условий
      (эффект/предмет в руке/верхом) - только «не в этом измерении»
      и собственные условия триггера (flags/vehicle);
    - ЦЕПОЧКА достижимости: 4 измерения последовательно - (а) каждый
      блок/предмет/моб условий шага i-го ? доступности (i-1)-го
      (строго: без расширений пул), (б) шаги валидны, (в) дерево -
      цепочка (parent каждой видимой = предыдущая), (г) независимость;
    - ПУСТОЙ prev-мир: пулы расширяются до ванильных и ЖУРНАЛИРУЮТСЯ
      (expansions - в печать самотеста)."""
    import tempfile

    id_rx = re.compile(r"^[a-z0-9_/]+$")
    # первые слова команд сервера 26.2 (из generated/reports/commands.json)
    valid_cmds = set(
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

    def _words(s):
        return [w for w in s.split() if w != "+"]

    # --- русские имена: КАЖДЫЙ id каждого пула назван (иначе подсказке
    #     не из чего строиться), все падежные формы непустые ---
    for pname, pool in (
            ("MOBS", MOBS), ("TAMEABLE", TAMEABLE), ("VEHICLES", VEHICLES),
            ("BREEDABLE", BREEDABLE), ("INTERACTABLE", INTERACTABLE),
            ("SUMMONABLE", SUMMONABLE),
            ("EXPLOSION_SOURCES", EXPLOSION_SOURCES)):
        for eid in pool:
            assert eid in RU_ENT, "%s: нет русского имени для %s" % (pname, eid)
            forms = RU_ENT[eid]
            assert len(forms) == 4 and all(forms), (eid, forms)
    for eid in VEHICLES:
        assert RU_VEHICLES.get(eid), eid
    # предметы: именительный обязателен, винительный = "a" либо
    # производен от "n" (как в _item_acc - неодуш. ср/муж род),
    # творительный нужен еде (старые шаблоны) и инструментам
    for pname, pool, need_i in (
            ("FOODS", FOODS, True),
            ("NOTABLE_ITEMS", NOTABLE_ITEMS, False),
            ("ENCHANTABLES", ENCHANTABLES, False),
            ("USABLE_ITEMS", USABLE_ITEMS, False),
            ("FISH_LOOT", FISH_LOOT, False),
            ("WEARABLE_ITEMS", WEARABLE_ITEMS, False),
            ("BUCKETS", BUCKETS, False),
            ("TOOL_ITEMS", TOOL_ITEMS, True)):
        for iid in pool:
            e = RU_ITEM.get(iid)
            assert isinstance(e, dict) and e.get("n"), \
                "%s: нет русского имени для %s" % (pname, iid)
            assert e.get("a", e["n"]), (pname, iid)     # винительный
            if need_i:
                assert e.get("i"), \
                    "%s: у %s нет творительного" % (pname, iid)
            assert _item_acc(iid), (pname, iid)         # аксессор не падает
    for _e, iid in _INTERACT_PAIRS:
        assert RU_ITEM.get(iid, {}).get("n"), iid
        assert iid in _INTERACT_HINTS, iid
    block_ids = set(PLACEABLE_BLOCKS) | set(ENTERABLE_BLOCKS) | \
        {"minecraft:bee_nest", "minecraft:beehive"}
    for _t, blks in TOOL_TARGETS.items():
        block_ids |= set(blks)
    for bid in block_ids:
        e = RU_BLOCK.get(bid)
        assert isinstance(e, dict) and e.get("n") and e.get("a", e["n"]), bid
        assert _block_acc(bid), bid                   # аксессор не падает
    for eff in EFFECTS:
        assert RU_EFFECT.get(eff), eff
    for potion in POTIONS:
        assert RU_POTION.get(potion), potion

    # --- ЗАГАДКИ (главные таблицы подсказок, стиль русского фольклора):
    #     каждый блок/предмет каждого пула описан ДВУМЯ загадками 4-14
    #     слов с тегом приёма (neg/contrast/person/metaphor/number/
    #     notab/action); первый вариант - КОРОТКОЕ «колено» <= 7 слов
    #     (его берут двойные подсказки «предмет + блок»); канцелярит
    #     («который», «является»...) под запретом; приёмы разнообразны -
    #     >= 3 разных тега в каждом окне из 20 загадок подряд и >= 6
    #     приёмов по всем таблицам; прозвища врагов - только для мобов
    #     из пула MOBS ---
    def _riddle_len_ok(r):
        return 4 <= len(_words(r)) <= 14

    for bid in block_ids:
        rs = RIDDLE_BLOCKS.get(bid)
        assert rs and len(rs) == 2, \
            "RIDDLE_BLOCKS: нет 2 загадок для %s" % bid
        for tag, r in rs:
            assert tag in _RIDDLE_TAGS, (bid, tag)
            assert _riddle_len_ok(r), (bid, len(_words(r)), r)
        assert len(_words(rs[0][1])) <= 7, \
            "RIDDLE_BLOCKS: длинное первое колено: %s" % (rs[0][1],)
    interact_items = {iid for _e, iid in _INTERACT_PAIRS}
    item_ids = (set(FOODS) | set(NOTABLE_ITEMS) | set(ENCHANTABLES)
                | set(USABLE_ITEMS) | set(FISH_LOOT) | set(WEARABLE_ITEMS)
                | set(BUCKETS) | set(TOOL_ITEMS) | interact_items)
    for iid in item_ids:
        e = RIDDLE_ITEMS.get(iid)
        assert e and e.get("a") and len(e["a"]) == 2, \
            "RIDDLE_ITEMS: нет 2 загадок для %s" % iid
        for tag, r in e["a"]:
            assert tag in _RIDDLE_TAGS, (iid, tag)
            assert _riddle_len_ok(r), (iid, len(_words(r)), r)
        assert len(_words(e["a"][0][1])) <= 7, \
            "RIDDLE_ITEMS: длинное первое колено: %s" % (e["a"][0][1],)
        if iid in set(TOOL_ITEMS) | interact_items:
            assert e.get("i") and len(e["i"]) == 2, \
                "%s: нет 2 творительных загадок" % iid
            for tag, r in e["i"]:
                assert tag in _RIDDLE_TAGS, (iid, tag)
                assert _riddle_len_ok(r), (iid, len(_words(r)), r)
            assert len(_words(e["i"][0][1])) <= 7, (iid, e["i"][0][1])
        # аксессоры не падают ни на одном id - и УВАЖАЮТ бюджет слов
        # (двойные подсказки получают короткое колено <= max_words)
        assert _riddle_item(random.Random(1), iid), iid
        if e.get("i"):
            assert _riddle_item_i(random.Random(1), iid), iid
            short_i = _riddle_item_i(random.Random(2), iid, max_words=7)
            assert len(_words(short_i)) <= 7, (iid, short_i)
    for bid in list(RIDDLE_BLOCKS):
        assert _riddle_block(random.Random(1), bid), bid
        short = _riddle_block(random.Random(2), bid, max_words=7)
        assert len(_words(short)) <= 7, (bid, short)

    # канцелярит под запретом - загадка должна звучать по-народному
    # (маркеры канцелярита по фидбеку юзера: «который», «является»;
    # формы местоимения ловим по префиксу «котор» - котором/которой/...)
    _bureau_exact = frozenset((
        "является", "являются", "представляет", "осуществляет",
        "используется", "специальный", "специальная", "специальное"))

    def _no_bureau(r):
        for w in r.lower().split():
            w = w.strip(",.;:!\u2014-\u00ab\u00bb()?")
            if w.startswith("котор") or w in _bureau_exact:
                return False
        return True

    _all_riddles = [(t, r) for rs in RIDDLE_BLOCKS.values() for t, r in rs]
    for e in RIDDLE_ITEMS.values():
        _all_riddles += list(e.get("a", ())) + list(e.get("i", ()))
    for t, r in _all_riddles:
        assert _no_bureau(r), (t, r)
    # разнообразие приёмов: в каждом окне из 20 загадок - минимум 3 тега;
    # по всем таблицам (500+ загадок) - не меньше шести приёмов
    for i in range(0, len(_all_riddles), 20):
        win = _all_riddles[i:i + 20]
        assert len({t for t, _r in win}) >= 3, (i, win)
    assert len({t for t, _r in _all_riddles}) >= 6, "мало приёмов"
    # прозвища врагов - только для узнаваемых мобов, формы непустые
    for eid, (pn, pa) in POETIC_ENT.items():
        assert eid in MOBS, eid
        assert pn and pa, (eid, pn, pa)

    # --- достижимость (правки аудита 26.2 + фидбек юзера) ---
    assert "minecraft:zombie_horse" not in VEHICLES
    assert "minecraft:brush" not in TOOL_ITEMS
    assert set(TOOL_ITEMS) == set(TOOL_TARGETS), "инструмент без валидных блоков"
    for ent, iid in _INTERACT_PAIRS:
        assert ent in INTERACTABLE and ent in _INTERACT_ITEMS[iid], (ent, iid)
    # порталов в другие миры в enter_block нет
    assert "minecraft:nether_portal" not in ENTERABLE_BLOCKS
    assert "minecraft:end_gateway" not in ENTERABLE_BLOCKS
    # эффект героя деревни недостижим без рейдов (деревни - обычный мир)
    assert "minecraft:hero_of_the_village" not in EFFECTS
    for eff in EFFECTS:
        assert eff in RU_EFFECT, eff
    # детёнышный вариант player_killed_entity: только мобы с детёнышами
    # (естественный спавн 5% или разведение - все есть в BREEDABLE)
    for eid in BABY_MOBS:
        assert eid in RU_ENT, eid
        assert eid in MOBS or eid in BREEDABLE, eid
    assert "minecraft:creeper" not in BABY_MOBS
    assert "minecraft:skeleton" not in BABY_MOBS
    assert "minecraft:mule" not in BABY_MOBS   # мул стерилен
    # пары зачарований allay валидны и покрыты загадками
    for it, ench in _ENCH_TOOLS:
        assert it in RIDDLE_ITEMS, it
        assert ench.startswith("minecraft:"), ench
    # слово-намёк есть у КАЖДОГО триггера пула (заголовки шагов)
    assert set(_STEP_WORDS) == {t for t, _g in TRIGGER_POOL}, \
        "_STEP_WORDS != TRIGGER_POOL"
    # зелье -> эффекты: ключи - валидные зелья, значения - id эффектов
    assert set(_POTION_EFFECT) <= set(POTIONS) | {"minecraft:healing"}
    for _p, effs in _POTION_EFFECT.items():
        for eff in effs:
            assert eff.startswith("minecraft:"), (eff,)

    # --- каждый триггер пула даёт непустую КОНКРЕТНУЮ подсказку: без
    #     незаполненных шаблонов, многоточий, запасной фразы; ~12 слов
    #     на критерий (потолок 18 - редкие двойные загадки «предмет +
    #     блок» вроде зачарованного подарка алаю) ---
    _vanilla_av = _Avail()
    for ti, (trig, gen) in enumerate(TRIGGER_POOL):
        for s in range(60):
            rng2 = random.Random((ti + 1) * 7919 + s * 104729)
            if trig == _CONTAINER_TRIGGER:
                conds2 = {"loot_table": "rndim:test_loot1"}
            else:
                conds2 = _gen_trigger_conds(trig, gen, rng2, _vanilla_av)
            h2 = _hint_for(trig, conds2, rng2)
            assert h2 and h2.strip(), (trig, h2)
            assert "{" not in h2 and "}" not in h2, (trig, h2)
            assert "..." not in h2, (trig, h2)
            assert h2 != _HINT_FALLBACK, (trig, h2)
            assert h2[0].isupper(), (trig, h2)
            assert len(_words(h2)) <= 18, (trig, h2)

    total_adv = 0
    n_container_crit = 0
    for seed in range(1, seeds + 1):
        with tempfile.TemporaryDirectory() as td:
            # инкрементальная генерация 8 измерений - дерево растёт;
            # после КАЖДОГО пишем «прошлый мир» (structure_set ->
            # jigsaw -> пул -> .nbt с сундуком) - контейнерный триггер
            # следующих измерений должен находить эти таблицы сканом
            names = ["dim%d_%d" % (seed, i) for i in range(8)]
            for i, nm in enumerate(names):
                rng = random.Random(seed * 1000 + i)
                loot_ids = ["%s_loot%d" % (nm, j) for j in range(3)] \
                    if i % 3 == 0 else []
                res = rand_advancements(rng, "rndim", nm, "minecraft:stone",
                                        200, data_root=td,
                                        loot_ids=loot_ids)
                # подсказка видимой ачивки (заклинание-присказка из всех
                # критериев): непустая, без незаполненных шаблонов
                # (многоточие допустимо - это соединители " ... и ... "),
                # без канцелярита и не длиннее ~15 слов на критерий
                # (+ запас на соединители и суффиксы доп. условий)
                assert res["hint"] and res["hint"].strip(), (nm, res["hint"])
                assert "{" not in res["hint"] and "}" not in res["hint"], \
                    (nm, res["hint"])
                assert _no_bureau(res["hint"]), (nm, res["hint"])
                _ncrit = len(res["advancements"]["rndim:adv/%s_tp" % nm]
                             ["criteria"])
                assert len(_words(res["hint"])) <= 18 * _ncrit + 10, \
                    (nm, len(_words(res["hint"])), _ncrit)
                # пишем сами (модуль на диск не пишет) - имитация main
                adv_dir = os.path.join(td, "rndim", "advancement", "adv")
                os.makedirs(adv_dir, exist_ok=True)
                for aid, ajson in res["advancements"].items():
                    with open(os.path.join(adv_dir, aid.split("/", 1)[1]
                                           + ".json"), "w",
                              encoding="utf-8") as f:
                        f.write(json.dumps(ajson))
                # id-валидность: путь после ns: только [a-z0-9_/]
                for aid in res["advancements"]:
                    assert id_rx.match(aid.split(":", 1)[1]), aid
                for fname in res["functions"]:
                    assert id_rx.match(fname), fname
                    assert ":" not in fname, fname  # NTFS ADS - никакого :

                # --- скрытая ачивка: критерии DUMMY + шаги ---
                hid = res["advancements"]["rndim:adv/%s_tp" % nm]
                crit = hid["criteria"]
                # 2-4 группы; контейнерная группа добавляет до 2 дублёров,
                # запасной вариант - ещё один
                assert 2 <= len(crit) <= 7, len(crit)
                # requirements покрывает каждый критерий ровно один раз
                flat = [c for grp in hid["requirements"] for c in grp]
                assert sorted(flat) == sorted(crit), (flat, sorted(crit))
                assert len(flat) == len(set(flat)), "критерий в двух группах"
                # критерии скрытой - DUMMY: impossible БЕЗ условий,
                # выдаются ТОЛЬКО reward-функциями шагов
                for cn, cv in crit.items():
                    assert cv == {"trigger": "minecraft:impossible"}, \
                        (nm, cn, cv)

                # --- ШАГИ ПРОГРЕССА: по одному на группу критериев ---
                n_groups = len(hid["requirements"])
                steps = sorted((k for k in res["advancements"]
                                if _STEP_FILE_RX.search(k)),
                               key=lambda k: int(k.rsplit("_step", 1)[1]))
                assert len(steps) == n_groups == res["n_steps"], \
                    (nm, steps, n_groups)
                seen_trigs = set()
                foreign = set("rndim:%s_loot1" % n2 for n2 in names[:i])
                for j, sid in enumerate(steps):
                    st = res["advancements"][sid]
                    # (б) parent = видимая ачивка измерения; display на месте
                    assert st["parent"] == "rndim:adv/%s" % nm, sid
                    disp = st["display"]
                    assert disp["show_toast"] is True, sid
                    assert disp["icon"]["id"].startswith("minecraft:"), sid
                    assert disp["title"]["text"].startswith(
                        "Шаг %d из %d: " % (j + 1, n_groups)), sid
                    assert disp["description"]["text"].strip(), sid
                    # критерии шага - РЕАЛЬНЫЕ триггеры; requirements -
                    # одна OR-группа поверх всех критериев шага
                    sc = st["criteria"]
                    req = st["requirements"]
                    assert len(req) == 1 and sorted(req[0]) == sorted(sc), sid
                    for cn, cv in sc.items():
                        t = cv["trigger"]
                        assert t.startswith("minecraft:") and \
                            t != "minecraft:impossible", (sid, cn, t)
                        # «не в этом измерении» - первым player-условием
                        pl = cv["conditions"]["player"]
                        assert isinstance(pl, list) and pl and \
                            pl[0]["condition"] == "minecraft:inverted" and \
                            pl[0]["term"]["predicate"]["dimension"] == \
                            "rndim:" + nm, (sid, cn)
                        # (г) НЕЗАВИСИМОСТЬ: никаких доп. player-условий
                        # (эффект/предмет в руке/верхом) - только
                        # «не в этом измерении» и собственные условия
                        # триггера (flags у placed/using, vehicle у riding)
                        for p in pl[1:]:
                            assert p["condition"] == \
                                "minecraft:entity_properties" and \
                                set(p["predicate"]) <= {
                                    "minecraft:flags",
                                    "minecraft:vehicle"}, (sid, cn, p)
                        # достижимость в изолированном наборе миров:
                        # ни других измерений, ни порталов, ни ванильных
                        # сундуков - теперь в критериях ШАГОВ
                        blob = json.dumps(cv["conditions"])
                        for bad in ("the_nether", "the_end",
                                    "minecraft:overworld", "nether_portal",
                                    "end_gateway", "chests/"):
                            assert bad not in blob, (sid, bad)
                        # контейнерный критерий - только НАШИ таблицы
                        # чужих миров, и только когда они есть на диске
                        if t == _CONTAINER_TRIGGER:
                            assert foreign, (nm, "контейнер без чужих таблиц")
                            lt = cv["conditions"]["loot_table"]
                            assert lt in foreign, (nm, lt)
                            n_container_crit += 1
                        else:
                            assert t not in seen_trigs, (nm, t)
                            seen_trigs.add(t)
                    # (б) rewards: функция грантит критерии СВОЕЙ группы
                    # скрытой + actionbar с номером шага
                    assert st["rewards"]["function"] == \
                        "rndim:%s_step%d" % (nm, j), sid
                    ftxt = res["functions"]["%s_step%d" % (nm, j)]
                    for cn in hid["requirements"][j]:
                        assert ("advancement grant @s only "
                                "rndim:adv/%s_tp %s" % (nm, cn)) in ftxt, \
                            (sid, cn)
                    assert "title @s actionbar" in ftxt and \
                        ("шаг %d из %d" % (j + 1, n_groups)) in ftxt, sid
                # видимой ачивке дописан «- путь из N шагов»
                vis_desc = res["advancements"]["rndim:adv/%s" % nm][
                    "display"]["description"]["text"]
                assert vis_desc.endswith("путь из %d шагов" % n_groups), \
                    (nm, vis_desc)
                assert not res["expansions"], (nm, res["expansions"])

                # rewards скрытой: валидные поля и id
                rw = hid["rewards"]
                assert "function" in rw and rw["function"] == \
                    "rndim:%s_tp" % nm, rw
                assert set(rw) <= {"function", "experience", "loot", "recipes"}
                for lt in rw.get("loot", ()):
                    nsx = lt.split(":", 1)
                    assert len(nsx) == 2 and \
                        (nsx[0] == "rndim" or nsx[1].startswith("chests/")), lt
                for rc in rw.get("recipes", ()):
                    assert rc.startswith("minecraft:") and " " not in rc, rc
                if "experience" in rw:
                    assert isinstance(rw["experience"], int) and rw["experience"] > 0
                # «+» возвращает строку триггеров (для summary)
                assert isinstance(res["trigger"], str) and \
                    "+" in res["trigger"], res["trigger"]

                # mcfunction: непустой, команды с валидного слова
                for fname, text in res["functions"].items():
                    lines = [l.strip() for l in text.splitlines()
                             if l.strip() and not l.strip().startswith("#")]
                    assert lines, fname
                    for l in lines:
                        w = l.split(None, 1)[0].lower()
                        assert w in valid_cmds, (fname, l)
                        assert " fill " not in " " + l + " ", \
                            (fname, l)  # платформ больше нет
                total_adv += len(res["advancements"])

                # «прошлый мир» для следующих измерений: полный путь
                # structure_set -> jigsaw-структура -> пул -> .nbt-сундук
                _write_fake_structures(td, "rndim", nm)
            # инварианты дерева: 1 корень + 8 видимых = 9 узлов
            probs = _check_tree_invariants(td, "rndim", 9)
            assert not probs, (seed, probs)

        # воспроизводимость: одинаковый seed + одинаковый диск -> одинаковый JSON
        with tempfile.TemporaryDirectory() as td1:
            with tempfile.TemporaryDirectory() as td2:
                r1 = rand_advancements(random.Random(777), "rndim", "aaa",
                                       "minecraft:stone", 100, td1)
                r2 = rand_advancements(random.Random(777), "rndim", "aaa",
                                       "minecraft:stone", 100, td2)
                assert json.dumps(r1, sort_keys=True) == \
                    json.dumps(r2, sort_keys=True), "невоспроизводимо"

    # --- ГЛАВНЫЙ СЦЕНАРИЙ: ЦЕПОЧКА ДОСТИЖИМОСТИ. 4 измерения
    #     последовательно во временный data_root: dim0 - из ванильного
    #     оверворлда (prev=None), dim1..3 - каждое с prev_dim=предыдущему
    #     и фейковыми данными prev-мира на диске. Проверяется:
    #     (а) каждый блок/предмет/моб условий шага i-го измерения ?
    #         доступности (i-1)-го - СТРОГО (расширений пул нет);
    #     (б) шаги валидны (parent/display/rewards грантит правильные
    #         критерии) - плюс отдельные проверки ниже;
    #     (в) дерево-цепочка: parent каждой видимой = предыдущая;
    #     (г) независимость (нет player-доп-условий в шагах)
    chain_samples = []
    for seed in range(1, 7):
        with tempfile.TemporaryDirectory() as td:
            names = ["chain%d_%d" % (seed, i) for i in range(4)]
            prev = None
            results = []
            for i, nm in enumerate(names):
                if i > 0:
                    _write_fake_prev_world(td, "rndim", names[i - 1])
                rng = random.Random(seed * 7717 + i)
                res = rand_advancements(rng, "rndim", nm,
                                        "minecraft:stone", 100,
                                        data_root=td, prev_dim=prev)
                results.append(res)
                _write_fake_advancements(td, "rndim", res)
                prev = nm
            # (в) дерево-цепочка: первая видная - ребёнок root, каждая
            # следующая - ребёнок предыдущей (родителя доверяем вызову -
            # как в --print, где prev ещё не на диске)
            assert results[0]["parent"] == "rndim:adv/root", results[0]["parent"]
            for i in range(1, 4):
                assert results[i]["parent"] == "rndim:adv/%s" % names[i - 1], \
                    (seed, names[i], results[i]["parent"])
            # (а) достижимость из prev-мира - СТРОГО, без расширений
            for i in range(1, 4):
                prev_ctx = read_prev_context(td, "rndim", names[i - 1])
                assert prev_ctx, (seed, names[i - 1])
                _assert_reachable(results[i], prev_ctx, names[i])
                assert not results[i]["expansions"], \
                    (seed, names[i], results[i]["expansions"])
            # шаги каждой размерности: корректные grants + независимость
            # (те же проверки, что в общем сценарии, на цепочных данных)
            for i, res in enumerate(results):
                hid = res["advancements"]["rndim:adv/%s_tp" % names[i]]
                n_groups = len(hid["requirements"])
                for j in range(n_groups):
                    sid = "rndim:adv/%s_step%d" % (names[i], j)
                    st = res["advancements"][sid]
                    assert st["parent"] == "rndim:adv/%s" % names[i]
                    assert st["rewards"]["function"] == \
                        "rndim:%s_step%d" % (names[i], j)
                    ftxt = res["functions"]["%s_step%d" % (names[i], j)]
                    for cn in hid["requirements"][j]:
                        assert ("advancement grant @s only "
                                "rndim:adv/%s_tp %s" % (names[i], cn)) \
                            in ftxt, (sid, cn)
                    for cv in st["criteria"].values():
                        for p in cv["conditions"]["player"][1:]:
                            assert set(p.get("predicate", {})) <= {
                                "minecraft:flags",
                                "minecraft:vehicle"}, (sid, p)
            if seed == 1:
                # пример цепочки для отчёта (первая тройка)
                chain_samples = [
                    (names[i], results[i]["trigger"],
                     results[i]["step_titles"])
                    for i in range(4)]

    # --- ПУСТОЙ prev-мир: пулы расширяются до ванильных и ЖУРНАЛИРУЮТСЯ
    #     (expansions - факт расширения виден в печати самотеста)
    depleted_expansions = set()
    with tempfile.TemporaryDirectory() as td:
        _write_fake_prev_world(td, "rndim", "poorland", poor=True)
        _write_fake_advancements(
            td, "rndim",
            rand_advancements(random.Random(4242), "rndim", "poorland",
                              "minecraft:stone", 100, data_root=td))
        for seed in range(3):
            res = rand_advancements(random.Random(909000 + seed), "rndim",
                                    "afterpoor%d" % seed,
                                    "minecraft:stone", 100,
                                    data_root=td, prev_dim="poorland")
            assert res["expansions"], \
                (seed, "выжженный prev - расширения обязательны")
            assert res["parent"] == "rndim:adv/poorland", res["parent"]
            depleted_expansions.update(res["expansions"])

    # без чужих миров на диске контейнерный триггер НЕ выбирается
    # (реальные триггеры теперь в ШАГАХ - проверяем их критерии)
    with tempfile.TemporaryDirectory() as td0:
        for seed in range(30):
            res = rand_advancements(random.Random(555000 + seed), "rndim",
                                    "lonely%d" % seed, "minecraft:stone", 100,
                                    data_root=td0)
            for aid, a in res["advancements"].items():
                if not _STEP_FILE_RX.search(aid.split("/", 1)[-1]):
                    continue
                for cv in a["criteria"].values():
                    assert cv["trigger"] != _CONTAINER_TRIGGER, \
                        (seed, "нет чужих таблиц - нет и триггера")

    # --- заглушки видимости + удалённые триггеры/условия: 30 seed с точной
    #     сигнатурой вызова из generate_dimension.py (data_root=None -
    #     дерево пустое, loot_ids из одного id)
    forbidden_conds = ('"minecraft:luck"', '"minecraft:unluck"',
                       '"minecraft:health_boost"', '"minecraft:cake"')
    for seed in range(30):
        nm = "test%d" % seed
        res = rand_advancements(random.Random(100000 + seed), "rndim", nm,
                                default_block="minecraft:stone", tp_y=100,
                                data_root=None,
                                loot_ids=["rndim:x_loot1"])
        adv = res["advancements"]
        vis_id = "rndim:adv/%s" % nm
        show_id = "rndim:adv/%s_show" % nm
        hid_id = "rndim:adv/%s_tp" % nm
        # заглушка присутствует; parent = id видимой ачивки; ровно один
        # критерий tick; нет display/rewards/requirements
        assert show_id in adv, (nm, sorted(adv))
        stub = adv[show_id]
        assert set(stub) == {"parent", "criteria"}, sorted(stub)
        assert stub["parent"] == vis_id, stub["parent"]
        assert list(stub["criteria"]) == ["show"]
        assert stub["criteria"]["show"] == {"trigger": "minecraft:tick"}
        # все ачивки результата: requirements-матрица согласована
        # с criteria (каждый критерий ровно один раз; отсутствие
        # requirements допустимо только при <= 1 критерии)
        for aid, a in adv.items():
            crit = a["criteria"]
            assert crit and all("trigger" in cv for cv in crit.values()), aid
            req = a.get("requirements")
            if req is None:
                assert len(crit) <= 1, (aid, sorted(crit))
                continue
            flat = [c for grp in req for c in grp]
            assert sorted(flat) == sorted(crit), (aid, flat, sorted(crit))
            assert len(flat) == len(set(flat)), (aid, "критерий дважды")
            assert all(isinstance(g, list) and g for g in req), aid
        # удалённые триггеры не встречаются ни в одном критерии
        for a in adv.values():
            for cv in a["criteria"].values():
                t = cv["trigger"]
                assert t not in REMOVED_TRIGGERS, (nm, t)
        # невыполнимые условия не встречаются в критериях (rewards не
        # проверяем: minecraft:cake там - легитимный id РЕЦЕПТА из
        # RECIPE_POOL, а несъедобен только предмет-тортик)
        for aid, a in adv.items():
            blob = json.dumps(a["criteria"])
            for fb in forbidden_conds:
                assert fb not in blob, (nm, aid, fb)
        # rewards скрытой: только валидные поля; лут - наш id или ванильный
        # сундук; функция-телепорт на месте
        hid = adv[hid_id]
        rw = hid["rewards"]
        assert set(rw) <= {"function", "experience", "loot", "recipes"}
        assert rw["function"] == "rndim:%s_tp" % nm
        for lt in rw.get("loot", ()):
            assert lt == "rndim:x_loot1" or \
                lt.startswith("minecraft:chests/"), lt
        # сигнатура не сломана: старые ключи результата на месте + новые
        assert set(res) == {"advancements", "functions", "trigger", "hint",
                            "parent", "n_steps", "step_titles",
                            "expansions"}, sorted(res)
        assert res["functions"] and isinstance(res["hint"], str)
        assert res["hint"].strip() and "{" not in res["hint"] and \
            "}" not in res["hint"], (nm, res["hint"])

    # --- скан реального пака: сундучные таблицы находятся и все - наши
    #     (запуск из каталога пака; пустой результат допустим для
    #     «свежего» пака без структур)
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    if os.path.isdir(os.path.join(here, "rndim", "structure")):
        tabs = _foreign_chest_tables(here, "rndim", "zzz")
        for t in tabs:
            assert t.startswith("rndim:") and "_loot" in t, t

    # пула звуков не пуст и валиден
    assert 1000 < len(SOUND_POOL) < 2500 and \
        all(s.startswith("minecraft:") and " " not in s for s in SOUND_POOL)
    # пул триггеров: ровно 32, без пересечений с удалёнными
    assert len(TRIGGER_POOL) == 32, len(TRIGGER_POOL)
    assert not REMOVED_TRIGGERS & {t for t, _g in TRIGGER_POOL}, \
        "удалённый триггер вернулся в пул"
    assert len({t for t, _g in TRIGGER_POOL}) == len(TRIGGER_POOL), \
        "дубликат триггера в пуле"
    # у каждого триггера пула есть построитель подсказки
    assert {t for t, _g in TRIGGER_POOL} == set(_HINT_BUILDERS), \
        "триггер без построителя подсказки"
    print("OK: %d seed'ов (+30 на заглушки, +30 без чужих сундуков, "
          "+6 цепочка x4, +3 выжженный prev), ачивек сгенерировано %d, "
          "контейнерных критериев %d, триггеров в пуле %d, звуков в "
          "пуле %d, русских имён %d, загадок %d (приёмов: %d)"
          % (seeds, total_adv, n_container_crit, len(TRIGGER_POOL),
             len(SOUND_POOL),
             len(RU_ENT) + len(RU_ITEM) + len(RU_BLOCK) + len(RU_EFFECT)
             + len(RU_POTION) + len(RU_VEHICLES),
             len(_all_riddles), len({t for t, _r in _all_riddles})))
    print("ЦЕПОЧКА (пример, seed 1): корень -> %s" %
          " -> ".join(nm for nm, _t, _s in chain_samples))
    for nm, trig, titles in chain_samples:
        print("  %s: %s | %s" % (nm, trig, "; ".join(titles)))
    print("ВЫЖЖЕННЫЙ prev-мир: расширения пул -> %s"
          % ", ".join(sorted(depleted_expansions)))


if __name__ == "__main__":
    _self_test()
