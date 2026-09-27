"""
Прикидочные расчёты к ANALYSIS.md: сколько попаданий до смерти игрока в ванили,
что даёт схема «K от штурмотрона + базовый DPS», подгонка GMST под
«снижение урона бронёй x0.75» и множители K(L) для варианта «нормировка по попаданиям».

Все допущения — в константах ниже (эталонная броня, типичный урон оружия по уровню).
Формула брони сверена с GMST (fPhysicalDamageFactor 0.15, fPhysicalArmorDmgReductionExp 0.365).
«Выживание» измерено тестовым плагином (2026-09-27, PLAN.md): x2 ДО брони (перк HC_DamageMultPerk,
AV HC_IncomingDamageMult = 2) и x2 ПОСЛЕ брони (GMST fDiffMultHPToPCSV); при DR 0 броня пропускает 100%.
Для энергоурона коэффициент брони считается от базового урона оружия — здесь не моделируется.

    python calc.py
"""
import math

ALPHA, BETA = 0.15, 0.365
SURV_PRE = 2.0                                        # HC_DamageMultPerk, до брони
SURV_POST = 2.0                                       # fDiffMultHPToPCSV, после брони
LEVELS = [4, 15, 30, 50, 80]
DR_REF = {4: 20, 15: 80, 30: 180, 50: 300, 80: 400}   # допущение: типичная броня игрока без силовой
D_REF = {4: 18, 15: 26, 30: 36, 50: 45, 80: 50}       # допущение: типичный урон выстрела врага своего уровня
ASSAULTRON_MELEE_DPS = 60                             # допущение: ~50 урона клинком за ~0.8 с
FLOOR_HITS = 4                                        # «пол»: столько попаданий без брони (Выживание)


def coeff(dmg, dr, a=ALPHA, b=BETA):
    """Доля урона, проходящая через броню (ванильная формула)."""
    if dr <= 0:
        return 1.0
    return min(0.99, max(0.01, (a * dmg / dr) ** b))


def coeff_soft(dmg, dr):
    """Предложение: снижение урона бронёй x0.75."""
    return 0.25 + 0.75 * coeff(dmg, dr)


def hp(level, end):
    return 80 + 5 * end + (level - 1) * (2.5 + end / 2)


def hit(dmg, dr, soft=False):
    """Урон по игроку на Выживании от базового урона dmg."""
    p = dmg * SURV_PRE
    return p * (coeff_soft(p, dr) if soft else coeff(p, dr)) * SURV_POST


def vanilla_table():
    print('== Ваниль, Выживание, ВЫН 5, эталонная броня: %% HP за попадание (попаданий до смерти) ==')
    weapons = [('самопал 13', 13), ('самопал-револьвер 24', 24), ('боевая винтовка 33', 33),
               ('модиф. винтовка 45', 45)]
    for lv in LEVELS:
        cells = []
        for name, d in weapons:
            f = hit(d, DR_REF[lv])
            cells.append('%s: %.1f%% (%d)' % (name, 100 * f / hp(lv, 5), math.ceil(hp(lv, 5) / f)))
        print('ур.%-2d HP %3.0f DR %3d | %s' % (lv, hp(lv, 5), DR_REF[lv], ' | '.join(cells)))
    print('Когти смерти (урон из UnarmedDamage варианта), игрок того же уровня:')
    for lv, d in [(22, 60), (31, 75), (41, 90), (51, 105), (61, 120), (81, 150)]:
        dr = 20 + (lv - 4) * 380 / 76
        print('  ур.%d урон %d DR %.0f -> %.0f%% HP за удар' % (lv, d, dr, 100 * hit(d, dr) / hp(lv, 5)))


def user_scheme():
    print('\n== Схема «K от штурмотрона + база HP/10 в секунду» (NPC стреляет 1 раз/с) ==')
    for lv in LEVELS:
        print('  ур.%d K = %.2f' % (lv, 0.9 * hp(lv, 10) / ASSAULTRON_MELEE_DPS))
    for lv, name, d in [(4, 'самопал-револьвер', 24), (4, 'самопал', 13), (50, 'боевая винтовка', 33),
                        (50, 'самопал', 13), (80, 'модиф. винтовка', 45)]:
        k = 0.9 * hp(lv, 10) / ASSAULTRON_MELEE_DPS
        paper = k * d + hp(lv, 5) / 10
        f = hit(paper, DR_REF[lv], soft=True)
        print('  ур.%d %-18s DR %3d: %.0f за попадание = %.0f%% HP' % (lv, name, DR_REF[lv], f, 100 * f / hp(lv, 5)))


def gmst_refit():
    print('\n== Подгонка GMST (alpha, beta) под 0.25 + 0.75*m ==')
    best = None
    for ai in range(200):
        a = 0.01 + ai * 0.001
        for bi in range(100):
            b = 0.08 + bi * 0.003
            err = max(abs(coeff(x, 1, a, b) - coeff_soft(x, 1))
                      for x in (10 ** (-2 + i * 2.5 / 59) for i in range(60)))
            if best is None or err < best[0]:
                best = (err, a, b)
    err, a, b = best
    print('  alpha=%.3f beta=%.3f, макс. ошибка %.3f' % (a, b, err))
    for x in [0.01, 0.03, 0.1, 0.3, 1, 2, 3]:
        print('   урон/DR=%-5s ваниль %.2f  цель %.2f  GMST %.2f'
              % (x, coeff(x, 1), coeff_soft(x, 1), coeff(x, 1, a, b)))
    print('  для сравнения DR x0.75: урон x%.3f при любом уроне' % (0.75 ** -BETA))


def own_k():
    print('\n== Вариант «нормировка по попаданиям»: K(L) до брони, цель — попаданий до смерти как в Корвеге ==')
    target = hit(D_REF[4], DR_REF[4]) / hp(4, 5)
    print('  Корвега (ур.4, урон 18, DR 20): %.1f%% HP за попадание, %.1f попаданий' % (100 * target, 1 / target))
    for soft in (False, True):
        cells = []
        for lv in LEVELS:
            want = target * hp(lv, 5)
            lo, hi = 0.1, 50.0
            for _ in range(80):
                k = (lo + hi) / 2
                if hit(D_REF[lv] * k, DR_REF[lv], soft) < want:
                    lo = k
                else:
                    hi = k
            cells.append('ур.%d K=%.2f' % (lv, k))
        print('  броня %s: %s' % ('x0.75' if soft else 'ваниль', ', '.join(cells)))


def floor_paper(level, hits=FLOOR_HITS):
    """Урон «пола» до брони: без брони на Выживании убивает за hits попаданий."""
    return hp(level, 5) / (hits * SURV_PRE * SURV_POST)


def floor_vs_armor():
    print('\n== Пол (%d ударов без брони) против брони, ур.50 ==' % FLOOR_HITS)
    lv = 50
    p = floor_paper(lv)
    for dr in (100, 300, 500, 700, 1000):
        print('  DR %4d: ваниль гасит %.0f%%, мод %.0f%% -> ударов %.1f -> %.1f'
              % (dr, 100 * (1 - coeff(p, dr)), 100 * (1 - coeff_soft(p, dr)),
                 hp(lv, 5) / hit(p, dr), hp(lv, 5) / hit(p, dr, soft=True)))


def k_with_floor():
    print('\n== K(L) при поле: минимум vs добавка (броня x0.75) ==')
    target = hit(D_REF[4], DR_REF[4]) / hp(4, 5)
    for hits, mode in ((10, 'add'), (10, 'min'), (FLOOR_HITS, 'min')):
        cells = []
        for lv in LEVELS:
            f = floor_paper(lv, hits)
            lo, hi = 0.0, 50.0
            for _ in range(80):
                k = (lo + hi) / 2
                paper = max(k * D_REF[lv], f) if mode == 'min' else k * D_REF[lv] + f
                if hit(paper, DR_REF[lv], soft=True) < target * hp(lv, 5):
                    lo = k
                else:
                    hi = k
            cells.append('ур.%d K=%.2f' % (lv, k))
        print('  пол %d ударов, %s: %s' % (hits, mode, ', '.join(cells)))


def threat_levels():
    print('\n== «Уровень угрозы» (MCM): s = 2^((n-5)/4) ==')
    corvega = hp(4, 5) / hit(D_REF[4], DR_REF[4])
    for n in range(1, 11):
        s = 2 ** ((n - 5) / 4)
        print('  %2d: s=%.2f, слабый враг без брони %.1f удара, рейдер в Корвеге %.1f попаданий'
              % (n, s, FLOOR_HITS / s, corvega / s))


if __name__ == '__main__':
    vanilla_table()
    user_scheme()
    gmst_refit()
    own_k()
    floor_vs_armor()
    k_with_floor()
    threat_levels()
