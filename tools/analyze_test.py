"""
Разбор лога тестового плагина (Data\\NoSafeLevel\\NoSafeLevel_Test.log).

    python tools/analyze_test.py [путь_к_логу]

Для каждой фазы — медиана урона за попадание (медиана устойчива к попаданиям в голову и
к редким «склеенным» событиям). Затем отношения к базовой фазе и выводы:
  x1   — запись перка не действует;
  x4   — множитель применяется ПОСЛЕ брони;
  x6.6 — ДО брони (урон растёт как 4^1.365, потому что броня пропускает долю ~ урон^0.365).
"""

import os
import re
import statistics
import sys

DEFAULT_LOG = r'D:\Games\Fallout 4\Data\NoSafeLevel\NoSafeLevel_Test.log'
ALPHA, BETA = 0.15, 0.365
MULT = 4.0
ADD = 50.0


def coeff(dmg, dr):
    if dr <= 0:
        return 0.99
    return min(0.99, max(0.01, (ALPHA * dmg / dr) ** BETA))


def parse(path):
    header, phases = [], {}
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            m = re.match(r'^([XPQL]\d+) [^:]*:(.*?)dmg=(.*)$', line)
            if not m:
                header.append(line)
                continue
            values = [float(v) for v in m.group(3).split()]
            info = dict(re.findall(r'(\w+)=([\d.\-]+)', m.group(2)))
            phases[m.group(1)] = {'line': line, 'values': values, 'info': info}
    return header, phases


def med(phases, key):
    p = phases.get(key)
    if not p:
        return None
    pos = [v for v in p['values'] if v > 0.001]
    return statistics.median(pos) if pos else 0.0


def verdict(ratio):
    if ratio is None:
        return 'нет данных'
    if 0.8 <= ratio <= 1.25:
        return 'НЕ действует'
    if 3.3 <= ratio <= 4.8:
        return 'действует, ПОСЛЕ брони'
    if 5.3 <= ratio <= 8.5:
        return 'действует, ДО брони'
    return 'неясно'


def ratio_line(phases, key, base, label):
    a, b = med(phases, key), med(phases, base)
    if a is None or not b:
        print('  %-44s нет данных' % label)
        return None
    r = a / b
    print('  %-44s %6.2f / %6.2f = x%.2f  -> %s' % (label, a, b, r, verdict(r)))
    return r


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_LOG
    if not os.path.exists(path):
        sys.exit('нет лога: %s' % path)
    header, phases = parse(path)
    print('== Лог ==')
    for line in header:
        print('  ' + line)
    print('\n== Фазы: медиана урона за попадание ==')
    for key in sorted(phases, key=lambda k: (k[0], int(k[1:]))):
        p = phases[key]
        zeros = sum(1 for v in p['values'] if v <= 0.001)
        extra = ' '.join('%s=%s' % (k, p['info'][k]) for k in ('hits', 'bash', 'other') if k in p['info'])
        print('  %-4s медиана %7.2f  (%d значений, нулей %d) %s' % (key, med(phases, key), len(p['values']),
                                                                zeros, extra))

    print('\n== Точки перков (DR/ER 1000, x4) ==')
    ratio_line(phases, 'P1', 'P0', 'EP36, пули 10 мм')
    ratio_line(phases, 'P2', 'P0', 'EP94 физ., пули 10 мм')
    ratio_line(phases, 'P3', 'P0', 'EP94 энерг., пули 10 мм (ожидается x1)')
    ratio_line(phases, 'L1', 'L0', 'EP94 энерг., лазер')
    ratio_line(phases, 'L2', 'L0', 'EP94 физ., лазер (ожидается x1)')
    ratio_line(phases, 'L3', 'L0', 'EP36, лазер')
    ratio_line(phases, 'X1', 'X0', 'EP36, взрыв')
    ratio_line(phases, 'X2', 'X0', 'EP94 физ., взрыв')
    ratio_line(phases, 'X3', 'X0', 'EP124, взрыв')
    ratio_line(phases, 'Q1', 'Q0', 'EP36 при DR 0 (ожидается x4 в любом случае)')
    ratio_line(phases, 'P10', 'P0', 'повтор базы (x1 = урон стабилен)')

    print('\n== Условия (сравнить с EP36 без условий) ==')
    ratio_line(phases, 'P5', 'P0', 'атакующий: IsWeaponInList')
    ratio_line(phases, 'P6', 'P0', 'оружие атакующего: IsWeaponInList')
    ratio_line(phases, 'P7', 'P0', 'оружие атакующего: GetIsID(10mm)')
    ratio_line(phases, 'P8', 'P0', 'атакующий: GetActorValue(метка) == 5')
    ratio_line(phases, 'P9', 'P0', 'оружие: HasKeyword (контроль, должно работать)')

    # Множитель сложности до или после брони: при DR 0 броня пропускает 0.99 в любом случае,
    # при DR 1000 — m(D) (после) или m(S*D) (до). S берём 2 (Выживание), D выводим из DR 0.
    print('\n== Множитель сложности: до или после брони (S = 2) ==')
    for base0, base1, what in (('Q0', 'P0', 'пули 10 мм'), ('L4', 'L0', 'лазер')):
        q, p = med(phases, base0), med(phases, base1)
        if not q or not p:
            print('  %s: нет данных' % what)
            continue
        s = 2.0
        d = q / (0.99 * s)
        post = d * s * coeff(d, 1000)
        pre = d * s * coeff(d * s, 1000)
        print('  %s: урон оружия ~%.1f; при 1000 измерено %.2f, если после брони %.2f, если до %.2f'
              % (what, d, p, post, pre))

    print('\n== Add Actor Value Mult (+50) ==')
    p0, p4, q0 = med(phases, 'P0'), med(phases, 'P4'), med(phases, 'Q0')
    if p0 and p4 and q0:
        s = 2.0
        d = q0 / (0.99 * s)
        print('  измерено %.2f (база %.2f, разница %+.2f)' % (p4, p0, p4 - p0))
        print('  прогноз: до брони %.2f | после брони, до сложности %.2f | после сложности %.2f'
              % ((d + ADD) * s * coeff(d + ADD, 1000), (d * coeff(d, 1000) + ADD) * s,
                 d * coeff(d, 1000) * s + ADD))
    else:
        print('  нет данных')


if __name__ == '__main__':
    main()
