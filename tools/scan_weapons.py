"""
Скан оружия и атак существ для полос урона No Safe Level.

Читает только официальные файлы (Fallout4.esm + DLC) — мод публикуется для всех, чужие правки
порядка загрузки в таблицы попадать не должны. Урон оружия — с шаблоном по умолчанию (OBTE default):
тест показал, что оружие, выданное NPC через AddItem, бьёт именно так (10-мм 18, лазерный пистолет 21).

    python tools/scan_weapons.py            -> data/weapons.json, сводка в консоль
"""

import json
import os
import struct
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import gamedata  # noqa: E402
from gamedata import Game, OFFICIAL  # noqa: E402
from weapons import apply_mods, expand  # noqa: E402

gamedata.load_order = lambda: list(OFFICIAL)

DT_PHYSICAL = ('Fallout4.esm', 0x60A87)
DT_ENERGY = ('Fallout4.esm', 0x60A81)


def default_mods(g, w):
    for t in w['templates']:
        if t['default']:
            return expand(g, t['mods'])
    return expand(g, w['templates'][0]['mods']) if w['templates'] else []


def expl_damage(g, proj):
    """Урон взрыва снаряда (как в fo4-weapon-analysis: только при флаге PROJ Explosion 0x2)."""
    if not proj or proj not in g.rec[b'PROJ']:
        return 0.0
    r, p = g.rec[b'PROJ'][proj]
    d = r.first(b'DNAM')
    if not d or len(d) < 36 or not (struct.unpack_from('<H', d, 0)[0] & 0x2):
        return 0.0
    ex = p.resolve(struct.unpack_from('<I', d, 32)[0])
    if not ex or ex not in g.rec[b'EXPL']:
        return 0.0
    er, _ = g.rec[b'EXPL'][ex]
    return struct.unpack_from('<f', er.first(b'DATA'), 28)[0]


def projectile(g, s):
    if s.get('override_proj'):
        return s['override_proj']
    ammo = s['ammo']
    if not ammo or ammo not in g.rec[b'AMMO']:
        return None
    r, p = g.rec[b'AMMO'][ammo]
    return p.resolve(struct.unpack_from('<I', r.first(b'DNAM'), 0)[0])


def main():
    g = Game()
    kw = g.kw_edid
    out = []
    for key in g.rec[b'WEAP']:
        w = g.weapon(key)
        s = apply_mods(g, w, default_mods(g, w))
        kws = sorted(kw.get(k) or str(k) for k in s['keywords'] if k is not None)
        types = {}
        for t, v in s['dmg_types'].items():
            name = g.rec[b'DMGT'][t][0].editor_id() if t in g.rec[b'DMGT'] else str(t)
            types[name] = round(v, 2)
        out.append({
            'file': key[0], 'id': key[1], 'edid': w['edid'], 'name': w['name'],
            'base': round(s['base_damage'], 2), 'types': types, 'num_proj': s['num_proj'],
            'auto': s['auto'], 'speed': round(s['speed'], 3), 'anim_type': w['anim_type'],
            'expl': round(expl_damage(g, projectile(g, s)), 1),
            'nonplayable': bool(w['flags'] & 0x4) or bool(w['wflags'] & 0x20),
            'keywords': [k for k in kws if k.startswith(('WeaponType', 'Anims'))],
        })
    os.makedirs(os.path.join(ROOT, 'data'), exist_ok=True)
    with open(os.path.join(ROOT, 'data', 'weapons.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('оружия:', len(out))
    c = Counter()
    for w in out:
        for k in w['keywords']:
            if k.startswith('WeaponType'):
                c[k] += 1
    print('ключевые слова WeaponType*:', dict(c.most_common()))

    # Атаки существ: безоружное оружие расы (RACE.UNWP) и какие UnarmedDamage встречаются у NPC этой расы.
    # Калибровка показала: урон атаки существа = урон оружия + UnarmedDamage (светящийся таракан 2 + 2).
    av_unarmed = ('Fallout4.esm', 0x2DF)
    race_weapon = {}
    for name in OFFICIAL:
        p = g.plugins.get(name)
        if p is None:
            continue
        for r in p.records(b'RACE'):
            u = r.first(b'UNWP')
            if u:
                race_weapon[p.resolve(r.form_id)] = p.resolve(struct.unpack('<I', u)[0])
    combos = {}
    vals = Counter()
    for name in OFFICIAL:
        p = g.plugins.get(name)
        if p is None:
            continue
        for r in p.records(b'NPC_'):
            av = 0.0
            props = r.first(b'PRPS')
            if props:
                for i in range(0, len(props), 8):
                    f, v = struct.unpack_from('<If', props, i)
                    if p.resolve(f) == av_unarmed:
                        av = v
                        vals[round(v)] += 1
            rn = r.first(b'RNAM')
            w = race_weapon.get(p.resolve(struct.unpack('<I', rn)[0])) if rn else None
            if w:
                combos.setdefault('%s|%d' % w, set()).add(round(av, 1))
    with open(os.path.join(ROOT, 'data', 'creatures.json'), 'w', encoding='utf-8') as f:
        json.dump({k: sorted(v) for k, v in sorted(combos.items())}, f, indent=1)
    print('UnarmedDamage у NPC (значение: сколько записей):', dict(sorted(vals.items())))
    print('пар «оружие расы: UnarmedDamage»:', len(combos))


if __name__ == '__main__':
    main()
