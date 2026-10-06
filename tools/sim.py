"""
Зеркало расчёта NSL:Main на Python и проверка по модели движка из теста (PLAN.md, «Результаты теста»).

Для каждой полосы и ситуации: множитель Y, как его посчитает скрипт; урон, который выдаст движок с этим
множителем (физический: x·m(x), x = Y·P·pre; энергия: Y·P·pre·m(P)); и целевой урон по формуле мода.
Они должны совпасть — это проверка обратной задачи. Ещё печатается «попаданий до смерти» для типичных
атак. Правишь математику в Main.psc — правь и здесь.

    python tools/sim.py
"""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALPHA, BETA, MAX_COEF, ARMOR_EFFECT = 0.15, 0.365, 0.99, 0.75
K_LEVELS = [4.0, 15.0, 30.0, 50.0, 80.0]
K_VALUES = [0.89, 1.08, 1.20, 1.38, 1.76]
PRE, POST = 2.0, 2.0          # Выживание
Q_MAX = 20.0
PA_REFERENCE = 0.7            # PADamageMult целой ванильной силовой брони


def coef(d, r):
    if r <= 0:
        return 1.0
    return min(MAX_COEF, (ALPHA * d / r) ** BETA)


def soft(d, r):
    return 1.0 - ARMOR_EFFECT * (1.0 - coef(d, r))


def invert(t, r):
    if r <= 0:
        return t
    x = (t * (r / ALPHA) ** BETA) ** (1.0 / (1.0 + BETA))
    if coef(x, r) >= MAX_COEF:
        x = t / MAX_COEF
    return x


def k_for(level):
    if level <= K_LEVELS[0]:
        return K_VALUES[0]
    i = 1
    while i < len(K_LEVELS) - 1 and level > K_LEVELS[i]:
        i += 1
    t = (level - K_LEVELS[i - 1]) / (K_LEVELS[i] - K_LEVELS[i - 1])
    return K_VALUES[i - 1] + t * (K_VALUES[i] - K_VALUES[i - 1])


def floor_damage(level):
    return (105.0 + 5.0 * (level - 1)) / 16.0


def solve_phys(p, q, s, pre, r, pa=1.0):
    paper = q * p * pre
    return invert(s * paper * soft(paper, r), r) / (p * pre * pa)


def solve_energy(p, q, s, pre, r, pa=1.0):
    paper = q * p * pre
    return s * paper * soft(paper, r) / (p * pre * pa * coef(p, r))


def scale(level, total, floor_coef, k_weight=1.0):
    k = 1.0 + k_weight * (k_for(level) - 1.0)
    return min(max(k * total, floor_coef * floor_damage(level)) / total, Q_MAX)


def engine(dtype, p, y, pre, r, pa=1.0):
    """Урон движка (до множителя после брони) с множителем y — модель из теста; pa — PADamageMult."""
    x = y * p * pre * pa
    if dtype == 'energy':
        return x * coef(p, r)
    return x * coef(x, r)


def target(p, q, s, pre, r):
    paper = q * p * pre
    return s * paper * soft(paper, r)


def threat_scale(threat, pa=None):
    """s: «Уровень угрозы» и, в силовой броне, сломанные части (PADamageMult / 0.7)."""
    s = 2 ** ((threat - 5) / 4)
    return s * pa / PA_REFERENCE if pa else s


def hp(level, end=5):
    return 80 + 5 * end + (level - 1) * (2.5 + end / 2)


def main():
    with open(os.path.join(ROOT, 'data', 'bands.json'), encoding='utf-8') as f:
        bands = {b['name']: b for b in json.load(f)['bands']}
    situations = [(4, 20, 15, 1, None), (15, 80, 60, 5, None), (50, 300, 250, 5, None), (50, 700, 600, 5, None),
                  (80, 400, 350, 9, None), (75, 1890, 1460, 5, 0.70), (75, 1620, 1250, 5, 0.75), (75, 1890, 1460, 5, None)]
    worst = 0.0
    for level, dr, er, threat, pa in situations:
        s, m = threat_scale(threat, pa), pa or 1.0
        for b in bands.values():
            p = b['phys'] or b['energy']
            dtype = 'energy' if b['dtype'] == 'energy' else 'phys'
            r = er if dtype == 'energy' else dr
            q = scale(level, p, b['floor_coef'], b['k_weight'])
            y = (solve_energy if dtype == 'energy' else solve_phys)(p, q, s, PRE, r, m)
            got, want = engine(dtype, p, y, PRE, r, m), target(p, q, s, PRE, r)
            worst = max(worst, abs(got - want) / want)
    print('обратная задача: макс. относительная ошибка %.2e (ситуаций %d, полос %d)'
          % (worst, len(situations), len(bands)))

    print('\nПопаданий до смерти (ВЫН 5, Выживание), ваниль -> мод:')
    def by_weapon(edid):
        return next(b for b in bands.values() if edid in b.get('edids', []))

    def by_unarmed(value):
        return next(b for b in bands.values() if b['kind'] == 'unarmed' and b['lo'] <= value < b['hi'])

    cases = [('самопал', by_weapon('PipeGun')), ('10-мм', by_weapon('10mm')),
             ('боевая винтовка', by_weapon('CombatRifle')), ('.44', by_weapon('44')), ('лазер', by_weapon('LaserGun')),
             ('миниган, пуля', by_weapon('Minigun')), ('таракан', by_weapon('UnarmedRadRoach')),
             ('дутень', by_weapon('WeapBloatfly')),
             ('кротокрыс (5)', by_unarmed(5)), ('коготь смерти (105)', by_unarmed(105))]
    for level, dr, er, threat, pa in situations:
        s, m = threat_scale(threat, pa), pa or 1.0
        cells = []
        for label, b in cases:
            p = b['phys'] or b['energy']
            dtype = 'energy' if b['dtype'] == 'energy' else 'phys'
            r = er if dtype == 'energy' else dr
            q = scale(level, p, b['floor_coef'], b['k_weight'])
            y = (solve_energy if dtype == 'energy' else solve_phys)(p, q, s, PRE, r, m)
            van = engine(dtype, p, 1.0, PRE, r, m) * POST
            mod = engine(dtype, p, y, PRE, r, m) * POST
            cells.append('%s %.0f->%.1f' % (label, hp(level) / van, hp(level) / mod))
        where = ' СБ %.2f' % pa if pa else ''
        print('  ур.%d DR %d ER %d угроза %d%s: %s' % (level, dr, er, threat, where, '; '.join(cells)))


if __name__ == '__main__':
    main()
