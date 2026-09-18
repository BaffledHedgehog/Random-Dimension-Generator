# random_dim — генератор случайных измерений (Minecraft 26.2)

Датапак + Python-скрипт, который при каждом запуске добавляет в датапак **+1
полностью случайное измерение**. Все синтаксические конструкции сверены с
ванильным jar-файлом Minecraft **26.2** (`pack_format` **107**) и проверены
запуском реального сервера 26.2.

## Что случайно В КАЖДОМ измерении

| Категория | Случайные параметры |
|---|---|
| Геометрия | **Форма мира**: `open` (~60%, дно без потолка), `cavern` (~13%, дно + кровля — мир-пещера наизнанку), `void` (~27%, БЕЗ дна — парящие острова над пустотой); `min_y` (−2032…0), высота **с убывающей вероятностью** (128 блоков ~35%, 1536+ — редкость, 2032 почти не выпадает), `logical_height`, `coordinate_scale`, `size_horizontal`/`size_vertical` ячеек шума | |
| Тип измерения | `has_skylight` (**93% светлый** — только cavern-миры и редкие аутсайдеры тёмные), `ambient_light`, `skybox` (none/end), `cardinal_light`, `infiniburn`, часы/таймлайны, монстр-спавн свет, `has_ender_dragon_fight` |
| Атрибуты | цвета неба/тумана/облаков/ambient light/ночного зрения/подсветки блоков (полностью случайный hex), высота облаков, все дистанции тумана (5 видов), bed_rule, respawn anchor, испарение воды, быстрый лавопад, зомбификация пиглинов, спавн пиглина из портала, рейды, капельные частицы, ambient-звуки — **все 47 атрибутов** EnvironmentAttributes 26.2 |
| Шумы генерации | у каждого шума **свой случайный спектр**: `firstOctave` (−16…1) и 1–16 случайных амплитуд на октаву; случайные `xz_scale`/`y_scale` |
| Noise router | `final_density` — случайное дерево density-функций из **всех** типов 26.2: `add, mul, min, max, clamp, abs, square, cube, squeeze, half_negative, quarter_negative, interpolated, blend_density, noise, shifted_noise, shift_a, shift_b, y_clamped_gradient, range_choice, interval_select, spline, cache_once, cache_2d, flat_cache, end_islands`; climate-каналы (continents/erosion/ridges/depth/temperature/vegetation) тоже случайные |
| Играбельность | Рампа «твёрдое дно → воздух сверху» со случайным уровнем поверхности гарантирует, что террейн существует (в void-мирах её нет — острова держатся на clamped-шумах), а всё остальное — хаос. **Характер рельефа** (равнины — редкость!): rolling/mountainous/chaotic/terraced/spiky — амплитуды с тяжёлым хвостом, масштабы лог-равномерные (холмы чаще континентов), ridged (abs) и плато-формы (square/cube) |
| Поверхность | **Гарантированные слои как у ванили**: **СВОЙ профиль у КАЖДОГО биома** (раньше биомы бились на 2–6 общих групп) — свой верхний блок (stone_depth) + подповерхностная полоса на 2–12 блоков; глубинная полоса-«deepslate» (ниже случайной глубины весь массив — другой блок); заплатки noise_threshold с ванильными шумами; случайные условия (stone_depth/y_above/water/hole/steep/temperature/noise_threshold[в т.ч. 3D]/biome/not/vertical_gradient → случайные блоки) + bedrock-дно (в cavern — и кровля). Без catch-all: база — default_block, разноцветье дают слои |
| Биомы | **ПЕР-БИОМНАЯ ГЕНЕРАЦИЯ**: количество биомов случайно — в среднем ~10, почти всегда 5–15, редкие «мегамиры» до 50 (`--biomes N` — оверрайд). У КАЖДОГО биома своё: цвета неба/тумана/воды/травы/листвы, частицы, ambient-звуки, музыка, температура/осадки/`frozen`, **свои configured+placed фичи** (1–6 своих + 0–2 из общего пула + ванильный фон), **свои карверы** (непересекающиеся порции пула), **своя фауна** (`_deal_mobs`: каждый моб достаётся 1–2 биомам), **свой профиль поверхности**, **свои структуры** (каждая структура принадлежит 1–3 биомам → и лут сундуков/мобов привязан к биому) и — в multi_noise-мирах с climate-корреляцией (**95% всех измерений**) — **свой рельеф**. Источник биомов: multi_noise — основной (95%, все свои биомы со случайным климатом), редко checkerboard/fixed/пресет overworld/nether/the_end (5%) |
| Пер-биомный рельеф | **95% миров**. Биомы бьются на 3–6 «кластеров рельефа»; кластер получает свой непересекающийся диапазон continentalness, а канал continents router'а выносится в DF-файл, на который ссылается и размещение биомов (multi_noise), и **spline в `final_density`** (формат сверен с ванильным overworld/offset.json): регион кластера = регион своего базового уровня поверхности (равнины/горы/острова у разных биомов). Один шум — две роли; сдвиг плотности ±0.5 |
| Свои фичи | configured + placed features **50 типов**: деревья (случайный ствол/листва/форма кроны/стволовый плейсер), руды, диски, озёра, поля растений, источники, валуны, колонны, piles, bamboo, basalt columns/pillar, blue_ice, кораллы, delta_feature, desert_well, fallen_tree, fill_layer, fossil, **geode** (полный формат 26.2 с layers/crack), glowstone_blob, огромные грибы/фунгусы, iceberg, kelp, **large_dripstone**, monster_room, multiface_growth, replace_single_block, root_system, sculk_patch, sea_pickle, seagrass, селекторы (simple/weighted), twisting/weeping_vines, underwater_magma, vegetation_patch, sequence, speleothem и др. **20+ типов placement** (count/in_square/height_range/heightmap/count_on_every_layer/biome/environment_scan/block_predicate_filter/random_offset/rarity_filter/noise_threshold_count/...) с предикатами и IntProvider'ами. **Естественная плотность растительности** (ванильные рецепты): count-провайдеры с большой дисперсией (рощи/прогалы), noise_based_count / noise_threshold_count (региональные сгустки), rarity+count (рощи в 1/N чанков), rarity-only (изолированные одиночки); `in_square` обязателен (без него фичи встают в идеальную сетку по углам чанков), `count_on_every_layer` — только незер/пещерным видам и без heightmap. **Количество — убывающее с тяжёлым хвостом**: медиана ~7 configured, в среднем ~10, но редкие миры получают десятки и сотни (до ~300) |
| Карверы | Свои configured_carver'ы: пещеры/nether-пещеры/каньоны со случайной вероятностью, y-диапазоном, толщиной, множителями и формой каньона. **Пул размером под все биомы** (в среднем ~ по числу биомов, редкие выбросы до ~150), раскладывается **непересекающимися порциями по биомам** — у биома свои 0–3 карвера (плюс ванильные с шансом 0.35) |
| Структуры | **Все 16 типов** структур 26.2 на измерение: **в среднем ~4, редкие миры — до ~125**. Jigsaw со своими template_pool'и (в т.ч. из собственных .nbt-построек), mineshaft (normal/mesa), ocean_ruin (cold/warm), nether_fossil, shipwreck (вкл. beached), ruined_portal (6 схем размещения: on_land_surface…in_nether…on_ocean_floor, с mossiness/vines/blackstone), desert_pyramid, end_city, fortress, igloo, jungle_temple, woodland_mansion, ocean_monument, stronghold, swamp_hut, buried_treasure — все со случайными `spawn_overrides`, `terrain_adaptation` (none/bury/beard_thin/beard_box/encapsulate) и placement'ом (`random_spread` с frequency-редукцией или `concentric_rings`). Привязка к биомам через свой тег `#ns:has_structure/...` или список ID; processor_lists (rule/block_rot/capped). **Материалы стен/полов/колонн и поверхности — только `PALETTE_BLOCKS`** (T0–T2 без block-entity: медные големы-статуи, спавнеры, сундуки, trial_spawner'ы и т.п. исключены — блочные сущности в массовой заливке просаживают FPS; copper_bulb проверен javap'ом — не block-entity, оставлен) |
| Лут | **У каждой особой сущности и каждого контейнера измерения — СВОЯ уникальная таблица** (класс `LootSlots`: trial_spawner'ы → структуры → jigsaw выделяют слоты `<name>_lootN` общим счётчиком, освобождённые слоты переиспользуются; таблицы создаёт один вызов `rand_loot` ровно под все занятые + минимум 1–2 на награды ачивок): 8 типов таблиц, 10 функций лута, 5 условий, NumberProviders; **все 1523 предмета** реестра `minecraft:item` (курированные пулы по характеру таблиц + «дикий тир» ~5% на любой предмет), **100 из 111 компонентов** реестра `DataComponents` 26.2 на предметах (custom_name, lore, enchantments, attribute_modifiers, potion_contents, trim, dyed_color, food, consumable, tool, weapon, equippable, glider, death_protection, fireworks, bundle_contents, container_loot, written_book_content, banner_patterns, can_place_on/can_break, profile, lodestone_tracker, bees, map_decorations, painting/variant, tooltip_style, варианты сущностей спавн-яиц, звуковые варианты... — 23 добавлены сверкой с байткодом jar; отклонены только технические/бессмысленные для лута), зачарования, зелья, rarity; рандомизировано всё игровое содержание (звуки equippable/blocks_attacks/kinetic_weapon, allowed_entities, bypassed_by, use_remainder, размер container, джиттер set_count, table_bonus по разным зачарованиям, rotation карт 0–360°...); предметы со сгенерированными русскими именами («Поющий Раскол Мешка Соли», «Клинок-Полночь»); пулы — тяжёлый хвост, роллы 1–30 со средним ~2.6. **Валидаторные запреты** (серверная проба всех 1523 предметов): damageable-предметам не даётся `max_stack_size>1` («Item cannot be both damageable and stackable» — патч отвергается целиком, `_DAMAGEABLE` — 84 предмета), фантомные предметы lang-суперсета отфильтрованы (`_PHANTOM_ITEMS`: lodestone_compass — в 26.2 это компас с компонентом), stack-1 предметам (240: кровати/лодки/шалкеры/зелья/диски/супы/брони коней/узоры знамён/книги/тотем... — `_STACK1`) count>1 не даётся ни в container/bundle_contents (`validateContainedItemSizes`), ни в set_count записей; линт `--check` ловит все три нарушения по генерируемым таблицам |
| Мобы-«боссы» | В собственных .nbt-постройках (подмешаны в jigsaw-пулы) изредка попадаются мобы **с полным NBT**: кастомные имена с цветом, снаряжение с зачарованиями (`equipment` со `components`), атрибуты, эффекты, `drop_chances`, `DeathLootTable` на сгенерированную таблицу лута, `NoAI`/`Glowing`/`Invulnerable`/`PersistenceRequired` и др.; сундуки с `LootTable` и спавнеры (18%, см. «Спавнеры данжей») |
| Спавнеры данжей | `mob_spawner` в .nbt-постройках и jigsaw-кусках спавнят **ЛЮБЫЕ сущности**, не только мобов: **мобы 85%** (85 типов из STRUCTURE_MOBS; смесь NBT-глубины 40% голый тип / 40% лёгкий CustomName-или-Health / 20% полный генератор босса) + **спец-типы 15%** со своими NBT-генераторами (формат каждого сверен javap'ом jar 26.2): `item` (зачарованное/именное оружие и броня, редкие материалы, полезные стаки), `armor_stand` (equipment + ShowArms/Small/...), `tnt` (`fuse` 20-200, иногда `explosion_power`/`block_state`-маскировка), `falling_block` (BlockState из палитры измерения), `experience_orb` (Value 1-50), `chest_boat`/`chest_minecart` (Items 3-6 со Slot), `item_frame`/`glow_item_frame` (Item + ItemRotation), `firework_rocket` (FireworksItem с 1-3 зарядами: shape/colors/fade_colors/has_trail), `area_effect_cloud` (Radius/Duration + potion_contents: готовое зелье или custom_effects), `boat`/`minecart` (лёгкий), `wind_charge` (редкий). Имена по реестру entity_type 26.2 (boat/chest_boat — только по породам дерева, сундук-вагонетка — `chest_minecart`; весь пул проверяется против `ENTITY_TYPE_IDS` — копии реестра EntityTypeIds из jar). Спавнеры **быстрые**: MinSpawnDelay 40-100, MaxSpawnDelay 120-240, SpawnCount 3-5, MaxNearbyEntities 6-9, RequiredPlayerRange 24-32 (не больше 32), SpawnRange 4-6; числовые поля — short, как пишет BaseSpawner |
| Trial spawners и вольты | ~90% измерений: свои конфиги `trial_spawner` — **парами normal + ominous** (в среднем ~3 пары, редкие выбросы до ~20), реестр без `worldgen/`. Мобы-претенденты **с полным NBT** (боссы с именами/снаряжением/DeathLootTable), жёсткие лимиты: simultaneous_mobs 1–3, ticks_between_spawn ≥ 40, 1–3 спавн-претендента. Normal-конфиг всегда выкидывает trial-ключ (парный vault открывается!), ominous добавляет зловещие ключи и припасы. **Vault-блоки** (36% спец-блоков): встроенная таблица лута + ключ trial_key |
| Зачарования | ~85% измерений: **свои зачарования** (в среднем ~5-7, выбросы до ~30) + 2–5 `enchantment_provider` (single/by_cost/by_cost_with_difficulty): случайные компоненты эффектов 26.2 (**все 31** — damage, attributes, post_attack, hit_block, projectile_spawned, projectile_spread, equipment_drops, damage_immunity...), требования, стоимости, exclusive_set; ValueEffect — **все 6 типов**, вкл. `exponential` (ScaleExponentially: value × base^exponent, для «уменьшающих» компонент base < 1; в ванили не используется). **Имена описывают реальный эффект**: название строится по фактическому содержимому effects — «Громовое Пробитие» (projectile_piercing), «Яд и Отброс» (post_attack-яд + knockback), «Кошачья Лапа» (damage_immunity [is_fall]), «Проклятие Хрупкости» (item_damage+), «Магическая Отплата» (damage_entity magic), «Быстрый Взвод» (charge_time−); прилагательные согласованы с родом, знак учтён для ammo_use/item_damage/charge_time; сценарий миграции старых паков — `migrate_ench_names.py`. **Связка**: run_function-эффекты вызывают свою mcfunction (id = id зачарования), которая по predicate перекрашивает предмет item_modifier'ом; id зачарований подмешиваются в `set_enchantments`/`enchant_randomly` таблиц лута и в снаряжение мобов-боссов |
| Predicates / item_modifiers | ~75% измерений: свои predicates (все типы условий: entity_properties, location_check, match_tool, damage_source, weather, random_chance... с вложенностью до 4 уровней и ссылками друг на друга) и ~70% — item_modifiers-«персонажи» (1–6 функций лута на модификатор, пустой модификатор как редкий краевой случай). Корень predicate-файла никогда не бывает голым безпараметрическим условием (survives_explosion/killed_by_player — interned-синглтоны, два таких корня роняют весь пак). Связаны с зачарованиями через их mcfunction |
| Jigsaw-постройки | 0–3 на мир (каждый десятый — до 8): **свои многочастные jigsaw-структуры** — генерируются комнаты/коридоры/лестницы с портами (12 ориентаций), сундуками (наши таблицы лута), мобами с NBT и лестницами-переходами; свои template_pool'и (в т.ч. pool_aliases), processor_lists (rule + block_rot только по стенам — швы не дырявит), structure_set'ы |
| Ачивки-телепорты | На каждое измерение: **3 файла достижений** — видимая (вкладка «За гранью мира», пирамидка: у узла ≤ 2 детей, иконка = блок-основа, название с именем измерения, описание = подсказки всех условий), скрытая и **заглушка `_show`** (критерий `minecraft:tick` — самовыполняется у каждого игрока в первый тик, parent = видимая ачивка, без display → не рендерится, но своим выполнением делает видимыми родителя и всю ветку до root: **страница достижений видна всегда**, даже до первой заработанной ачивки и для зашедших позже игроков). Скрытая: **2–4 РАЗНЫХ триггера, объединённых по И** (requirements_matrix — случайно попасть нельзя; с шансом 15% одному критерию даётся «запасной» вариант в OR-группу). Пул — **37 триггеров** (невыполнимые удалены: killed_by_arrow/slide_down_block/avoid_vibration/kill_mob_near_sculk_catalyst/construct_beacon + исправлены невыполнимые условия внутри item_durability_changed и пулов POTIONS/EFFECTS/FOODS), форматы условий скопированы с ванильных ачивок jar 26.2 (в т.ч. редкие: target_hit, lightning_strike, fall_after_explosion, bee_nest_destroyed, nether_travel, player_generates_container_loot, enter_block, summoned_entity, hero_of_the_village...). Каждый критерий получает своё условие «не в этом измерении» и с шансом 35% доп. player-предикат (эффект / предмет в руке / взгляд на сущность / верхом). Rewards: функция-телепорт (снять скрытую — revoke сбрасывает все критерии, выдать видимую, телепорт на безопасную высоту tp_y, resistance 5 на 30 с, случайный звук из всего реестра звуков) + часто опыт, лут (наши таблицы данжей или ванильные сундуки) и разблокировка ванильных рецептов |
| Время | ~65% измерений: свои `world_clock` + 1–3 `timeline` — случайная длина суток (600–96000 тиков, включая «лунные» циклы ×2–8), до 8 дорожек (цвета неба/облаков ARGB, углы солнца/луны с cubic_bezier, фазы луны, яркость звёзд, горение монстров, активности жителей, шансы) с 30 видами ease и per-атрибутными модификаторами, именованные маркеры времени |
| Теги | ~45% измерений: свой infiniburn-тег — **почти всегда 1–2 блока (в среднем ~1), редкие выбросы до ~100** |
| Мир | `default_block` и изредка `default_fluid` — **413 блоков по тирам «странности»** (камень/земля/дерево — частые, шерсть/руды/медь — обычные, froglights/infested/bedrock/командные блоки — редкие; веса 16/8/4/2/1, динамит исключён — он не бывает основой террейна); `default_fluid` — вода/лава/воздух/снег, в 1.5% случаев вообще любой solid-блок; `sea_level`, аквиферы, рудные жилы, `spawn_target`, `legacy_random_source`. **Динамит** при этом встречается как редкий блок фич (~0.1% выборки) — «жилы» TNT и TNT-диски/глыбы в декорациях, примерно в каждом четвёртом измерении |
| Спавн мобов | **80 сущностей — whitelist по реестру `SpawnPlacements` 26.2** (проверено декомпиляцией): в биомные спавнеры попадают ТОЛЬКО мобы с зарегистрированными правилами спавна (иначе `checkSpawnRules` возвращает TRUE без проверок света/поверхности — моб плодится в воздухе тысячами: так было с allay/tadpole/zombie_nautilus/bee/sniffer/copper_golem/piglin_brute — удалены) и ТОЛЬКО в список своей истинной категории из `EntityTypes` (моб-кап считается по собственной категории: моб в чужом списке обходит кап и копится бесконечно). Тиры «странности» (16 — коровы/зомби/криперы, 8 — пиглины/фантомы, 4 — эвокеры/варды, 1 — визер и дракон Края), MISC-мобы (жители/големы) в пулах отсутствуют; `SPAWNABLE_MOBS` + `_validate_spawn_pools()` проверяют пулы при каждом импорте. **ЖЁСТКИЕ лимиты плотности**: монстры спавнятся только в темноте (свет ≤ 7, block_light_limit ≤ 8 — факелы реально защищают), в биоме максимум 4 монстрозаписи / 3 животных (группы ≤ 4, у водных и лягушек ≤ 2), spawn_costs с низким energy_budget на каждого монстра, спавнеры в структурах быстрые (Min/MaxSpawnDelay 40-100/120-240), но с малым радиусом активности (RequiredPlayerRange 24-32); рыбы и лягушки — редкие тиры (после жалобы на кишащие рыбой поверхности); **фауна пер-биомная** — моб достаётся 1–2 биомам (`_deal_mobs`), пустая категория = «тихий» биом; **спавн-теги**: поверхностные блоки (default_block + слои surface_rule) ВСЕХ измерений пака дописываются в 13 ванильных блок-тегов `data/minecraft/tags/block/animals_spawnable_on` и др. (merge без replace, пересборка по всем noise_settings при каждой генерации) — иначе спавн-правила животных требуют grass_block/stone/... и фауна не появляется на случайных поверхностях |

## Использование

```text
python generate_dimension.py                 # +1 случайное измерение
python generate_dimension.py --count 5       # +5 измерений за раз
python generate_dimension.py --seed 12345    # воспроизводимый результат
python generate_dimension.py --name mydim    # своё имя измерения
python generate_dimension.py --biomes 16     # оверрайд числа биомов (по умолч. случайно: в среднем ~10, 5–15, макс 50)
python generate_dimension.py --namespace foo # другой namespace (по умолчанию rndim)
python generate_dimension.py --list          # список созданных
python generate_dimension.py --check         # проверка целостности данных
python generate_dimension.py --print         # только вывести JSON, не писать
python generate_dimension.py --regen         # удалить все сгенерированные измерения
python migrate_ench_names.py                # переименовать существующие зачарования
                                             # (описательные имена по эффектам;
                                             # меняет ТОЛЬКО текст description)
```

После запуска скрипта:

1. В игре выполни `/reload`. Если команда `/execute in rndim:...` говорит, что
   измерение не найдено — сохранись и перезайди в мир (новые измерения
   подхватываются не при каждом `/reload`).
2. Зайди в измерение командой из вывода скрипта, например:
   `/execute in rndim:myxaeloon run tp @s 0 -1696 0`

Каждое измерение лежит в датапаке (`data/rndim/`) в виде: `dimension/`,
`dimension_type/`, `worldgen/noise_settings/`, `worldgen/noise/`,
`worldgen/biome/` (32 своих биома), `worldgen/density_function/`,
`worldgen/configured_feature/` + `placed_feature/` (свои фичи),
`worldgen/configured_carver/`, `worldgen/structure/` + `structure_set/` +
`template_pool/` + `processor_list/` (структуры), `structure/` (бинарные
.nbt-постройки с мобами с NBT), `loot_table/` (свои таблицы лута),
`trial_spawner/` (конфиги normal+ominous), `enchantment/` +
`enchantment_provider/`, `predicate/`, `item_modifier/`, `function/`
(mcfunction зачарований и телепортов), `world_clock/` и
`timeline/` (своё время), `tags/` (infiniburn, биомы структур, timelines)
— все файлы можно править руками.

## Совместимость

* Minecraft **26.2** (формат данных **107**; в `pack.mcmeta` используются новые
  обязательные поля `min_format`/`max_format` — старого `pack_format` в 26.2
  для новых паков уже недостаточно).
* Fabric: датапак не зависит от модов — работает и в чистом клиенте, и с Fabric.
* Скрипту нужен Python 3.8+ (только стандартная библиотека).

## Что изменилось в синтаксисе 26.2 (учтено в генераторе)

Проверено запуском настоящего сервера 26.2 с этим датапаком:

* `dimension_type` — новый формат `attributes` с namespaced-ключами
  (`minecraft:visual/*`, `minecraft:gameplay/*`), поля `skybox`,
  `cardinal_light`, `default_clock`, `timelines`; время измерения задаётся
  реестрами `world_clock`/`timeline`.
* **Биомы**: почти всё из старого `effects` переехало в `attributes`
  (`minecraft:visual/sky_color|fog_color|water_fog_color|ambient_particles`,
  `minecraft:audio/ambient_sounds|background_music|music_volume`,
  `minecraft:gameplay/increased_fire_burnout|snow_golem_melts|...`);
  в `effects` остались только цвета (`water_color`, `grass_color`,
  `foliage_color`, `dry_foliage_color`, `grass_color_modifier`).
  `carvers` — строка ИЛИ список ID карверов (старый словарь `{"air": ...}`
  больше не используется). Цвета — hex-строки `"#78a7ff"`.
* **Features**: `random_patch` удалён — патчи теперь `simple_block` +
  `random_offset` в placement; у дерева `dirt_provider` →
  `below_trunk_provider` (rule_based); lake получил 3 новых поля-предиката;
  block_blob — `state` + `can_place_on`.
* **Время**: реестры `world_clock/` и `timeline/` лежат БЕЗ префикса
  `worldgen/` (как dimension_type); world_clock — запись-пустышка `"{}"`;
  в timeline у каждого атрибута свой допустимый модификатор
  (`or`/`and`/`maximum`/`multiply`/ничего — сверьте с ванилью), а
  `cloud_color` требует 8-значный ARGB `"#rrggbbaa"`.
* **Процессоры структур**: в 26.2 их 4 типа — `rule`, `block_rot`,
  `protected_blocks`, `capped` (старых block_replace/block_swap/guarded нет:
  их роль играет `rule`). Типов structure 16; деревни = jigsaw,
  mansion переименован в `woodland_mansion`, `jungle_pyramid` → `jungle_temple`.
* `noise_router.preliminary_surface` → `preliminary_surface_level`;
  `find_top_surface` теперь требует `lower_bound` и `upper_bound`.
* `noise_threshold` в surface rules получил `is_3d`.
* Ссылки `minecraft:overworld/...` и другие density-функции из папки
  `worldgen/density_function/` работают как обычно.
