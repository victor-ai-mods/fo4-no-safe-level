"""
Разбор калибровочного прогона (NSL:CalibQuest + отладочный лог NSL:Main).

    python tools/analyze_calib.py [лог_калибровки лог_NSL_Main]

Для каждого атакующего:
  D — чистый урон атаки из фазы off0 (мод выключен, сопротивление 0): медиана / (до · после);
  offR — мод выключен, сопротивление 300: сравнение с ванильной моделью (проверка модели на этой атаке);
  onR  — мод включён: сравнение с моделью движка при множителе полосы Y из лога NSL:Main
         (проверка, что сработала нужная запись перка и только она), и с целью мода для этого D.
Отношение «измерено / модель» около 1.00 — всё сходится.
"""

import json
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sim import coef, scale, soft, PRE, POST  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = r'D:\Games\Fallout 4\Data\NoSafeLevel'
CALIB_LOG = os.path.join(LOG_DIR, 'NoSafeLevel_Calib.log')
MAIN_LOG = os.path.join(LOG_DIR, 'NoSafeLevel.log')

ATTACKERS = {
    'raider_10mm': ('weapon', '10mm'), 'raider_pipe': ('weapon', 'PipeGun'),
    'raider_laser': ('weapon', 'LaserGun'), 'radroach': ('creature', ('UnarmedRadRoach', 0.0)),
    'radroach_glowing': ('creature', ('UnarmedRadRoach', 2.0)), 'molerat': ('unarmed', 5.0),
    'feral_ghoul': ('creature', ('UnarmedFeralGhoul', 0.0)), 'deathclaw': ('unarmed', 60.0),
}


def band_table():
    """Порядок записей перка, как в gen_esp.build: у смешанных полос вторая запись — энергия."""
    with open(os.path.join(ROOT, 'data', 'bands.json'), encoding='utf-8') as f:
        bands = json.load(f)['bands']
    table = []
    for b in bands:
        table.append(b)
        if b['dtype'] == 'mixed':
            table.append(dict(b, name=b['name'] + '_en'))
    return table


def find_band(table, how, key):
    for i, b in enumerate(table):
        if how == 'weapon' and key in b.get('edids', []):
            return i, b
        if how == 'unarmed' and b['kind'] == 'unarmed' and b['lo'] <= key < b['hi']:
            return i, b
        if how == 'creature' and b['kind'] == 'creature' and key[0] in b['edids'] and b['lo'] <= key[1] < b['hi']:
            return i, b
    raise KeyError(key)


def parse_calib():
    level, phases = None, {}
    with open(CALIB_LOG, encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            m = re.search(r'level=(\d+)', line)
            if level is None and m:
                level = int(m.group(1))
            m = re.match(r'^(\w+) (off0|offR|onR): (.*?)dmg=(.*)$', line)
            if m:
                values = m.group(4).split()
                normal = [float(v) for v in values if not v.startswith('P')]
                power = [float(v[1:]) for v in values if v.startswith('P')]
                # Papyrus хранит строки без учёта регистра: «radroach» в логе может стать «RadRoach».
                phases[(m.group(1).lower(), m.group(2))] = (normal, power, m.group(3))
    return level, phases


def parse_states():
    states, cur = [], None
    if not os.path.exists(MAIN_LOG):
        return states
    with open(MAIN_LOG, encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if line.startswith('state '):
                cur = {k: float(v) for k, v in re.findall(r'(\w+)=([\d.\-]+)', line)}
                cur['Y'] = {}
                states.append(cur)
            elif line.startswith('bands') and cur is not None:
                for i, y in re.findall(r'(\d+):([\d.\-]+)', line):
                    cur['Y'][int(i)] = float(y)
    return states


def med(values):
    pos = [v for v in values if v > 0.001]
    return statistics.median(pos) if pos else None


def main():
    global CALIB_LOG, MAIN_LOG
    if len(sys.argv) > 2:
        CALIB_LOG, MAIN_LOG = sys.argv[1], sys.argv[2]
    level, phases = parse_calib()
    states = parse_states()
    table = band_table()
    print('уровень игрока: %s, состояний NSL:Main в логе: %d' % (level, len(states)))
    for name, (how, key) in ATTACKERS.items():
        if (name, 'off0') not in phases:
            print('\n%s: нет данных' % name)
            continue
        idx, band = find_band(table, how, key)
        energy = band['dtype'] == 'energy'
        res_key = 'ER' if energy else 'DR'
        off0, offr, onr = (med(phases.get((name, p), ([], [], ''))[0]) for p in ('off0', 'offR', 'onR'))
        print('\n%s -> полоса %d %s (типичный урон %.1f)' % (name, idx, band['name'], band['phys'] or band['energy']))
        for p in ('off0', 'offR', 'onR'):
            normal, power, info = phases.get((name, p), ([], [], ''))
            print('  %-4s %s | обычные %s | силовые %s' % (p, info.strip(), [round(v, 1) for v in normal],
                                                          [round(v, 1) for v in power]))
        if not off0:
            continue
        d = off0 / (PRE * POST)
        r = 300.0
        if energy:
            van = d * PRE * coef(d, r) * POST
        else:
            x = d * PRE
            van = x * coef(x, r) * POST
        print('  урон атаки D = %.2f' % d)
        if offr:
            print('  offR: измерено %.2f, ванильная модель %.2f -> x%.3f' % (offr, van, offr / van))
        st = next((s for s in reversed(states) if s.get('enabled') == 1.0 and abs(s.get(res_key, 0) - r) < 1), None)
        if st is None or idx not in st['Y']:
            print('  onR: нет состояния NSL:Main с %s=300 и включённым модом' % res_key)
            continue
        y = st['Y'][idx]
        if energy:
            eng = y * d * PRE * coef(d, r) * POST
        else:
            x = y * d * PRE
            eng = x * coef(x, r) * POST
        q = scale(level, d, band['floor_coef'], band.get('k_weight', 1.0))
        paper = q * d * PRE
        ideal = paper * soft(paper, r) * POST * (2 ** ((st.get('threat', 5) - 5) / 4))
        if onr:
            print('  onR: Y=%.3f; измерено %.2f, движок с этим Y %.2f -> x%.3f; цель мода для D %.2f -> x%.3f'
                  % (y, onr, eng, onr / eng, ideal, onr / ideal))


if __name__ == '__main__':
    main()
