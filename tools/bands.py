"""
Полосы урона No Safe Level: группы атак с близким уроном, одним типом урона и одним типом атаки.
Перк получает по записи на полосу, скрипт считает для каждой свой множитель (PLAN.md, «Реализация»).

Четыре вида полос:
  weapon   — оружие Fallout4.esm, условие GetIsID (цепочка через OR) на вкладке оружия атакующего;
  creature — безоружные атаки существ Fallout4.esm с ненулевым уроном оружия (таракан 2, гуль 15, ...):
             GetIsID оружия + диапазон UnarmedDamage атакующего. Калибровка показала, что урон такой
             атаки = урон оружия + UnarmedDamage (светящийся таракан: 2 + 2), а UnarmedDamage у вариантов
             одного существа разный (гули 0..90), поэтому одной полосы на оружие мало;
  unarmed  — атаки существ с уроном оружия 0 (коготь смерти, кротокрыс, ...), диапазон UnarmedDamage;
  fallback — оружие DLC и модов (нет в NSL_KnownWeapons), категории по ключевым словам Fallout4.esm.

Без изменений (ваниль) остаются: взрывчатка и всё, чей урон идёт через взрыв снаряда (множитель
перка лёг бы и на взрыв, а взрывы движок усиливает сверхлинейно), огнемёты роботов и ловушек
(урон 1 у оружия, настоящий — от заклинания), служебные и тестовые «оружия».

    python tools/bands.py        -> data/bands.json + сводка
"""

import json
import math
import os
import re
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EXPLOSIVE_KW = {'WeaponTypeExplosive', 'WeaponTypeGrenade', 'WeaponTypeMine', 'WeaponTypeThrown',
                'WeaponTypeMissileLauncher', 'WeaponTypeFatman', 'WeaponTypeMolotov'}
MELEE_KW = {'WeaponTypeMelee1H', 'WeaponTypeMelee2H', 'WeaponTypeHandToHand', 'WeaponTypeUnarmed'}
FLAMER_KW = {'WeaponTypeFlamer', 'WeaponTypeCryolater'}
SKIP_EDID = re.compile(r'(?i)^(test|aaa_|dummy|tutorial|vrworkshop)|dummy|_fake$|flamethrower|trap')
# Дальние атаки существ, которые не помечены WeaponTypeUnarmed, но по сути — атака существа.
CREATURE_RANGED = {'WeapBloatfly', 'WeapMirelurkQueenLeft', 'WeapMirelurkQueenRight', 'WeapMirelurkKing'}
# Урон попадания, измеренный в игре, когда он не совпадает с записью оружия. Дутень: у WeapBloatfly урон 1,
# но выстрел дутня 75-го уровня бьёт на ~27, 9-го — на ~17 (2026-10-06: множитель полосы выставлялся из
# консоли, ×1/×4/×13 дают 30/27/26; откуда урон и его рост с уровнем, не найдено). При уроне 1 множитель
# полосы тянул выстрел к «полу» с ошибкой в разы — дутень убивал с одного выстрела.
MEASURED_HIT = {'WeapBloatfly': 27.0}
# «Безоружные» атаки людей: их урон с уровнем не растёт, им K нужен, как оружию.
HUMAN_UNARMED = {'UnarmedHuman', 'UnarmedSuperMutant', 'UnarmedPowerArmor', 'BoxingGlove', 'Knuckles',
                 'PowerFist', 'DeathclawGauntlet'}


def is_creature(w):
    """Атака существа: урон задан видом существа и растёт с уровнем варианта, K к ней не применяется."""
    if w['edid'] in CREATURE_RANGED:
        return True
    return 'WeaponTypeUnarmed' in w['keywords'] and w['edid'] not in HUMAN_UNARMED
# Огнемёты роботов без ключевого слова огнемёта: урон оружия условный, настоящий — от заклинания.
ROBOT_FLAMER = re.compile(r'(?i)flamer')
MIN_HIT, MAX_HIT = 3.0, 400.0

# Доля «пола» на одно попадание (PLAN.md, c_тип).
FLOOR_COEF = {'1': 1.0, 'A': 0.3, 'F': 0.1}
ATTACK_NAMES = {'1': 'single', 'A': 'auto', 'S': 'shotgun', 'F': 'flamer'}

# Границы полос по урону одного попадания (геометрически, шаг ~1.4).
WEAPON_EDGES = [0.5, 1.5, 3, 4.2, 5.9, 8.2, 11.5, 16, 22.5, 31.5, 44, 62, 86, 121, 169, 237, 400]
UNARMED_EDGES = [0.5, 1.5, 3.5, 6.5, 9, 12.5, 17.5, 22.5, 27.5, 32.5, 37.5, 42.5, 47.5, 57.5, 72.5,
                 87.5, 110, 145, 190, 300, 10000]

CREATURE_AV_MAX = 10000.0

# Запасные категории: (имя, вид урона, тип атаки, типичный урон за попадание,
#   [группы условий: список ключевых слов через OR, «!» — ключевого слова нет]).
FALLBACKS = [
    ('melee', 'phys', '1', 25.0, [['WeaponTypeMelee1H', 'WeaponTypeMelee2H', 'WeaponTypeHandToHand']]),
    ('heavy', 'phys', 'A', 15.0, [['WeaponTypeHeavyGun'], ['!WeaponTypeMelee1H'], ['!WeaponTypeMelee2H']]),
    ('energy', 'energy', '1', 25.0, [['WeaponTypeLaser', 'WeaponTypePlasma', 'WeaponTypeAlienBlaster',
                                       'WeaponTypeGammaGun'], ['!WeaponTypeHeavyGun'], ['!WeaponTypeMelee1H'],
                                      ['!WeaponTypeMelee2H']]),
    ('shotgun', 'phys', 'S', 6.0, [['WeaponTypeShotgun'], ['!WeaponTypeHeavyGun']]),
    ('auto', 'phys', 'A', 18.0, [['WeaponTypeBallistic'], ['WeaponTypeAutomatic'], ['!WeaponTypeShotgun'],
                                 ['!WeaponTypeHeavyGun']]),
    ('ballistic', 'phys', '1', 35.0, [['WeaponTypeBallistic'], ['!WeaponTypeAutomatic'], ['!WeaponTypeShotgun'],
                                      ['!WeaponTypeHeavyGun']]),
]
FALLBACK_PELLETS = 8
# Для запасных категорий: оружия нет в NSL_KnownWeapons и это не взрывчатка и не атака существа.
FALLBACK_EXCLUDE = sorted(EXPLOSIVE_KW | {'WeaponTypeUnarmed'})


def load_weapons():
    with open(os.path.join(ROOT, 'data', 'weapons.json'), encoding='utf-8') as f:
        return json.load(f)


def load_creatures():
    """{(файл, id оружия расы): [значения UnarmedDamage у NPC этой расы]} — из scan_weapons.py."""
    with open(os.path.join(ROOT, 'data', 'creatures.json'), encoding='utf-8') as f:
        raw = json.load(f)
    out = {}
    for key, values in raw.items():
        name, fid = key.split('|')
        out[(name, int(fid))] = values
    return out


def gmean(values):
    values = [v for v in values if v > 0]
    if not values:
        return 0.0
    return math.exp(sum(math.log(v) for v in values) / len(values))


def bin_index(edges, value):
    for i in range(len(edges) - 1):
        if edges[i] <= value < edges[i + 1]:
            return i
    return None


def classify(w):
    """(причина пропуска или None, вид урона, тип атаки, урон физ., урон энерг. за попадание)."""
    kw = set(w['keywords'])
    energy = w['types'].get('dtEnergy', 0.0)
    other = sum(v for t, v in w['types'].items() if t != 'dtEnergy')
    phys = MEASURED_HIT.get(w['edid'], w['base']) + other
    n = max(1, w['num_proj'])
    if kw & EXPLOSIVE_KW:
        return 'explosive', None, None, 0, 0
    if w['expl'] > 0:
        return 'projectile explosion', None, None, 0, 0
    if SKIP_EDID.search(w['edid'] or ''):
        return 'service/test', None, None, 0, 0
    if ROBOT_FLAMER.search(w['edid'] or '') and not kw & FLAMER_KW:
        return 'robot flamer', None, None, 0, 0
    if 'WeaponTypeUnarmed' in kw and w['base'] <= 0 and not w['types']:
        return 'unarmed (UnarmedDamage)', None, None, 0, 0
    hit = (phys + energy) / n
    # Атаки существ бывают слабыми по-настоящему (таракан — 2), им нижний порог не нужен.
    creature = 'WeaponTypeUnarmed' in kw or w['edid'] in CREATURE_RANGED
    min_hit = 0.5 if creature else MIN_HIT
    if hit < min_hit or hit > MAX_HIT:
        return 'damage %.1f' % hit, None, None, 0, 0
    dtype = 'phys' if energy <= 0 else ('energy' if phys <= 0 else 'mixed')
    if kw & MELEE_KW:
        attack = '1'
    elif kw & FLAMER_KW:
        attack = 'F'
    elif n > 1:
        attack = 'S'
    elif w['auto']:
        attack = 'A'
    else:
        attack = '1'
    return None, dtype, attack, phys / n, energy / n


def floor_coef(attack, pellets):
    return 1.0 / pellets if attack == 'S' else FLOOR_COEF[attack]


def build():
    weapons = load_weapons()
    creatures = load_creatures()
    groups = defaultdict(list)
    creature_groups = defaultdict(list)
    skipped = defaultdict(list)
    known = []
    for w in weapons:
        if w['file'] != 'Fallout4.esm':
            continue
        known.append(w['id'])
        why, dtype, attack, ph, en = classify(w)
        if why:
            skipped[why].append(w['edid'])
            continue
        race_avs = creatures.get(('Fallout4.esm', w['id']))
        if race_avs is not None and is_creature(w) and dtype == 'phys' and w['edid'] not in CREATURE_RANGED:
            creature_groups[ph].append((w, race_avs))
            continue
        pellets = max(1, w['num_proj']) if attack == 'S' else 1
        b = bin_index(WEAPON_EDGES, ph + en)
        groups[(dtype, attack, pellets, is_creature(w), b)].append((w, ph, en))

    bands = []
    for (dtype, attack, pellets, creature, b), members in sorted(groups.items()):
        ph = gmean([m[1] for m in members])
        en = gmean([m[2] for m in members])
        name = '%s%s_%s%s_%g' % ('creature_' if creature else '', dtype, ATTACK_NAMES[attack],
                                 pellets if attack == 'S' else '', round(ph + en, 1))
        bands.append({'kind': 'weapon', 'name': name, 'dtype': dtype, 'phys': round(ph, 2), 'energy': round(en, 2),
                      'floor_coef': round(floor_coef(attack, pellets), 4), 'k_weight': 0.0 if creature else 1.0,
                      'weapons': sorted(m[0]['id'] for m in members),
                      'edids': sorted(m[0]['edid'] for m in members)})

    for base, members in sorted(creature_groups.items()):
        # Сплошные диапазоны UnarmedDamage: границы посередине между встречающимися значениями,
        # чтобы вариант с непредусмотренным значением (моды) попал в ближайшую полосу, а не выпал.
        avs = sorted({v for _, values in members for v in values})
        for i, v in enumerate(avs):
            lo = 0.0 if i == 0 else (avs[i - 1] + v) / 2
            hi = CREATURE_AV_MAX if i == len(avs) - 1 else (v + avs[i + 1]) / 2
            bands.append({'kind': 'creature', 'name': 'creature_%g_av%g' % (base, v), 'dtype': 'phys',
                          'phys': round(base + v, 2), 'energy': 0.0, 'floor_coef': 1.0, 'k_weight': 0.0,
                          'lo': lo, 'hi': hi, 'weapons': sorted(m[0]['id'] for m in members),
                          'edids': sorted(m[0]['edid'] for m in members)})

    for i in range(len(UNARMED_EDGES) - 1):
        lo, hi = UNARMED_EDGES[i], UNARMED_EDGES[i + 1]
        rep = math.sqrt(lo * hi) if hi < 1000 else lo * 1.2     # последняя полоса открыта сверху
        bands.append({'kind': 'unarmed', 'name': 'unarmed_%g_%g' % (lo, hi), 'dtype': 'phys',
                      'phys': round(rep, 2), 'energy': 0.0, 'floor_coef': 1.0, 'k_weight': 0.0, 'lo': lo, 'hi': hi})

    # Оружие-«атаки существ» с ненулевым базовым уроном: из полос UnarmedDamage их исключаем,
    # они уже в полосах оружия (или пропущены как служебные).
    unarmed_with_base = sorted(w['id'] for w in weapons
                               if w['file'] == 'Fallout4.esm' and 'WeaponTypeUnarmed' in w['keywords']
                               and (w['base'] > 0 or w['types']))

    for name, dtype, attack, hit, groups_kw in FALLBACKS:
        pellets = FALLBACK_PELLETS if attack == 'S' else 1
        bands.append({'kind': 'fallback', 'name': 'fallback_' + name, 'dtype': dtype,
                      'phys': hit if dtype == 'phys' else 0.0, 'energy': hit if dtype == 'energy' else 0.0,
                      'floor_coef': round(floor_coef(attack, pellets), 4), 'k_weight': 1.0,
                      'keywords': groups_kw})

    return {'bands': bands, 'known': sorted(known), 'unarmed_with_base': unarmed_with_base,
            'fallback_exclude': FALLBACK_EXCLUDE,
            'skipped': {k: sorted(v) for k, v in skipped.items()}}


def main():
    data = build()
    with open(os.path.join(ROOT, 'data', 'bands.json'), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    kinds = defaultdict(int)
    for b in data['bands']:
        kinds[b['kind']] += 1
    print('полос: %d (%s), известного оружия: %d' % (len(data['bands']), dict(kinds), len(data['known'])))
    for b in data['bands']:
        if b['kind'] in ('weapon', 'creature'):
            print('  %-26s физ %6.1f энерг %6.1f пол x%-6s %2d: %s' % (
                b['name'], b['phys'], b['energy'], b['floor_coef'], len(b['weapons']), ', '.join(b['edids'][:6])))
    for why, names in data['skipped'].items():
        print('  пропущено (%s): %d — %s' % (why, len(names), ', '.join(names[:8])))


if __name__ == '__main__':
    main()
