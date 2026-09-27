"""
Применение модификаций (OMOD) к оружию и итоговые характеристики.

Семантика свойств (проверяется калибровкой по вики, см. calibrate.py):
  float  SET — заменить; MUL+ADD — копятся Σmul и Σadd, итог = база*(1+Σmul)+Σadd;
         ADD — прибавить v1.
  int    так же (MUL+ADD у int встречается с float-v1 — трактуем как долю).
  bool   SET / AND / OR.
  FormID,Int   (vt 4): Keywords ADD/REM, Ammo SET, DamageTypeValues ADD/SET (тип, кол-во).
  FormID,Float (vt 6): DamageTypeValues MUL+ADD (тип, доля) / SET / ADD.
Включённые моды (includes) применяются вместе с модом.
"""

from gamedata import (Game, FN_SET, FN_MULADD, FN_ADD, P_SPEED, P_ATTACK_DELAY, P_AMMO_CAP,
                      P_IS_AUTO, P_DAMAGE, P_KEYWORDS, P_NUM_PROJ, P_AMMO, P_RELOAD_SPEED,
                      P_DMG_TYPES, P_OVERRIDE_PROJ, P_FIRE_SECONDS)

FLOAT_PROPS = {P_SPEED: 'speed', P_ATTACK_DELAY: 'attack_delay', P_RELOAD_SPEED: 'reload_speed',
               P_FIRE_SECONDS: 'fire_sec'}
INT_PROPS = {P_AMMO_CAP: 'capacity', P_DAMAGE: 'base_damage', P_NUM_PROJ: 'num_proj'}


def expand(g, omod_keys, seen=None):
    """OMOD с их includes (рекурсивно), без повторов."""
    out = []
    seen = set() if seen is None else seen
    for k in omod_keys:
        if k is None or k in seen or k not in g.rec[b'OMOD']:
            continue
        seen.add(k)
        o = g.omod(k)
        out.append(o)
        out.extend(expand(g, o['includes'], seen))
    return out


def apply_mods(g, w, omods):
    """Характеристики оружия w (из Game.weapon) после модов omods (список dict из Game.omod)."""
    s = {'speed': w['speed'], 'attack_delay': w['attack_delay'], 'reload_speed': w['reload_speed'],
         'fire_sec': w.get('fire_sec', 0.0), 'capacity': w['capacity'],
         'base_damage': float(w['base_damage']), 'num_proj': w.get('num_proj', 1) or 1,
         'ammo': w['ammo'], 'auto': bool(w['wflags'] & 0x8000),
         'keywords': set(w['keywords']), 'dmg_types': dict(w['dmg_types']),
         'override_proj': w.get('override_proj')}
    mul = {}
    add = {}
    dmul = {}
    for o in omods:
        for pr in o['props']:
            p, fn, v1, v2 = pr['prop'], pr['fn'], pr['v1'], pr['v2']
            if p in FLOAT_PROPS or p in INT_PROPS:
                name = FLOAT_PROPS.get(p) or INT_PROPS[p]
                if fn == FN_SET:
                    s[name] = float(v1)
                    mul.pop(name, None)
                    add.pop(name, None)
                elif fn == FN_MULADD:
                    mul[name] = mul.get(name, 0.0) + float(v1)
                    add[name] = add.get(name, 0.0) + float(v2 or 0)
                elif fn == FN_ADD:
                    add[name] = add.get(name, 0.0) + float(v1)
            elif p == P_IS_AUTO:
                if fn == FN_SET:
                    s['auto'] = bool(v1)
                elif fn == 2:  # OR
                    s['auto'] = s['auto'] or bool(v1)
                elif fn == 1:  # AND
                    s['auto'] = s['auto'] and bool(v1)
            elif p == P_KEYWORDS:
                if fn == 2:
                    s['keywords'].add(v1)
                elif fn == 1:
                    s['keywords'].discard(v1)
            elif p == P_AMMO and fn == FN_SET:
                s['ammo'] = v1
            elif p == P_OVERRIDE_PROJ and fn == FN_SET:
                s['override_proj'] = v1
            elif p == P_DMG_TYPES:
                t = v1
                if fn == FN_SET:
                    s['dmg_types'][t] = float(v2)
                elif fn == FN_ADD:
                    s['dmg_types'][t] = s['dmg_types'].get(t, 0.0) + float(v2)
                elif fn == FN_MULADD:
                    dmul[t] = dmul.get(t, 0.0) + float(v2)
    for name in set(mul) | set(add):
        s[name] = s[name] * (1.0 + mul.get(name, 0.0)) + add.get(name, 0.0)
    for t, m in dmul.items():
        if t in s['dmg_types']:
            s['dmg_types'][t] *= (1.0 + m)
    s['damage_mul'] = mul.get('base_damage', 0.0)
    return s
