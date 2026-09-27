"""
Чтение игровых данных: побеждающие версии записей по порядку загрузки, разбор WEAP / OMOD / COBJ /
PROJ / EXPL. Взято из проекта анализа оружия (fo4-weapon-analysis); esm.py, ba2.py, strings_file.py —
из fo4-survival-automedic.

Раскладки — по wbDefinitionsFO4.pas (xEdit, ветка dev), сверены на записях.
Ключ записи везде — (файл-владелец, локальный id).
"""

import os
import struct

from esm import Plugin
from ba2 import BA2
from strings_file import load_from_ba2

GAME = os.environ.get('FO4_PATH', r'D:\Games\Fallout 4')
DATA = os.path.join(GAME, 'Data')
PLUGINS_TXT = os.path.join(os.environ['LOCALAPPDATA'], 'Fallout4', 'Plugins.txt')
LANG = 'ru'
OFFICIAL = ['Fallout4.esm', 'DLCRobot.esm', 'DLCworkshop01.esm', 'DLCCoast.esm',
            'DLCworkshop02.esm', 'DLCworkshop03.esm', 'DLCNukaWorld.esm']
LOCALIZED = 0x80

# Номера свойств OMOD для оружия (wbWeaponPropertyEnum).
P_SPEED, P_ATTACK_DELAY, P_AMMO_CAP, P_IS_AUTO = 0, 4, 12, 25
P_DAMAGE, P_KEYWORDS, P_FIRE_SECONDS, P_NUM_PROJ = 28, 31, 50, 51
P_AMMO, P_RELOAD_SPEED, P_DMG_TYPES, P_OVERRIDE_PROJ = 61, 76, 77, 80
P_CRIT_MULT, P_FULL_POWER, P_MIN_POWER = 90, 84, 87
PROP_NAMES = {P_SPEED: 'Speed', P_ATTACK_DELAY: 'AttackDelaySec', P_AMMO_CAP: 'AmmoCapacity',
              P_IS_AUTO: 'IsAutomatic', P_DAMAGE: 'AttackDamage', P_KEYWORDS: 'Keywords',
              P_FIRE_SECONDS: 'FireSeconds', P_NUM_PROJ: 'NumProjectiles', P_AMMO: 'Ammo',
              P_RELOAD_SPEED: 'ReloadSpeed', P_DMG_TYPES: 'DamageTypeValues',
              P_OVERRIDE_PROJ: 'OverrideProjectile', P_CRIT_MULT: 'CriticalDamageMult',
              P_FULL_POWER: 'FullPowerSeconds', P_MIN_POWER: 'MinPowerPerShot'}
FN_SET, FN_MULADD, FN_ADD = 0, 1, 2


def load_order():
    active = []
    with open(PLUGINS_TXT, encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if line.startswith('*'):
                active.append(line[1:])
    light = [p for p in active if p.lower().endswith(('.esm', '.esl'))]
    esp = [p for p in active if p.lower().endswith('.esp')]
    return OFFICIAL + light + esp


class Game:
    SIGS = (b'WEAP', b'OMOD', b'COBJ', b'KYWD', b'AMMO', b'PROJ', b'EXPL', b'DMGT', b'PERK', b'LVLI')

    def __init__(self):
        self.order = load_order()
        self.plugins = {}
        self.rec = {s: {} for s in self.SIGS}   # sig -> key -> (Record, Plugin)
        self.defined_in = {}                      # key -> sig (для проверок ссылок)
        for name in self.order:
            path = os.path.join(DATA, name)
            if not os.path.exists(path):
                continue
            p = Plugin(path)
            self.plugins[name] = p
            for sig in self.SIGS:
                for r in p.records(sig):
                    k = p.resolve(r.form_id)
                    self.rec[sig][k] = (r, p)
                    self.defined_in[k] = sig
        self._strings = {}
        self.kw_edid = {k: r.editor_id() for k, (r, p) in self.rec[b'KYWD'].items()}
        self.kw_by_edid = {v: k for k, v in self.kw_edid.items() if v}

    # -- общее -------------------------------------------------------------

    def ref(self, p, fid):
        return None if fid == 0 else p.resolve(fid)

    def text(self, r, p, tag=b'FULL'):
        v = r.first(tag)
        if v is None:
            return None
        loc = struct.unpack_from('<I', p.buf, 8)[0] & LOCALIZED
        if not loc:
            return v.rstrip(b'\x00').decode('utf-8', 'replace')
        sid = struct.unpack('<I', v[:4])[0]
        if sid == 0:
            return ''
        stem = os.path.splitext(p.name)[0]
        if stem not in self._strings:
            arc = 'Fallout4 - Interface.ba2' if stem == 'Fallout4' else stem + ' - Main.ba2'
            path = os.path.join(DATA, arc)
            self._strings[stem] = load_from_ba2(BA2(path), stem, LANG) if os.path.exists(path) else {}
        return self._strings[stem].get(sid, '?%08X' % sid)

    def name(self, sig, key):
        r, p = self.rec[sig][key]
        return self.text(r, p) or r.editor_id()

    # -- WEAP --------------------------------------------------------------

    def weapon(self, key):
        r, p = self.rec[b'WEAP'][key]
        d = r.first(b'DNAM')
        f = r.first(b'FNAM')
        w = {'key': key, 'edid': r.editor_id(), 'name': self.text(r, p), 'flags': r.flags}
        (ammo, speed, reload_speed, reach, min_r, max_r, attack_delay) = struct.unpack_from('<I6f', d, 0)
        # 28: unknown(4), 32: out-of-range mult, 36: on hit, 40: skill, 44: resist, 48: flags
        (wflags,) = struct.unpack_from('<I', d, 48)
        (capacity, anim_type) = struct.unpack_from('<HB', d, 52)
        (secondary, weight, value, base) = struct.unpack_from('<ffIH', d, 55)
        # 69: sound level(4) + 8 звуков (32) = 105: accuracy(1), 106: attack seconds
        (accuracy,) = struct.unpack_from('<B', d, 105)
        (attack_sec,) = struct.unpack_from('<f', d, 106)
        (ap_cost, full_power, min_power) = struct.unpack_from('<fff', d, 112)
        w.update(ammo=self.ref(p, ammo), speed=speed, reload_speed=reload_speed,
                 attack_delay=attack_delay, wflags=wflags, capacity=capacity, anim_type=anim_type,
                 weight=weight, value=value, base_damage=base, attack_sec=attack_sec,
                 ap_cost=ap_cost, full_power=full_power, min_power=min_power)
        if f:
            (fire_sec,) = struct.unpack_from('<f', f, 0)
            (reload_sec,) = struct.unpack_from('<f', f, 16)
            (nproj,) = struct.unpack_from('<B', f, 28)
            (oproj,) = struct.unpack_from('<I', f, 29)
            w.update(fire_sec=fire_sec, reload_sec=reload_sec, num_proj=nproj, override_proj=self.ref(p, oproj))
        dama = r.first(b'DAMA')
        w['dmg_types'] = {}
        if dama:
            for i in range(0, len(dama), 8):
                t, amt = struct.unpack_from('<II', dama, i)
                w['dmg_types'][self.ref(p, t)] = float(amt)
        kw = r.first(b'KWDA')
        w['keywords'] = {self.ref(p, x) for x in struct.unpack('<%dI' % (len(kw) // 4), kw)} if kw else set()
        appr = r.first(b'APPR')
        w['slots'] = [self.ref(p, x) for x in struct.unpack('<%dI' % (len(appr) // 4), appr)] if appr else []
        w['templates'] = self.templates(r, p)
        return w

    def templates(self, r, p):
        """OBTE: список (имя, default, [omod keys]) — стандартные сборки оружия."""
        out = []
        cur_name = None
        for tag, v in r.subrecords():
            if tag == b'FULL':
                cur_name = v
            elif tag == b'OBTS':
                inc_count, prop_count = struct.unpack_from('<II', v, 0)
                # 8: lvlmin u8, u8, lvlmax u8, u8, addon index i16, default u8
                default = v[14]
                (nkw,) = struct.unpack_from('<B', v, 15)
                pos = 16 + nkw * 4
                pos += 2  # min level for ranks, alt levels per tier
                incs = []
                for i in range(inc_count):
                    (mod,) = struct.unpack_from('<I', v, pos)
                    incs.append(self.ref(p, mod))
                    pos += 7
                out.append({'default': bool(default), 'mods': incs})
        return out

    # -- OMOD --------------------------------------------------------------

    def omod(self, key):
        r, p = self.rec[b'OMOD'][key]
        d = r.first(b'DATA')
        inc_count, prop_count = struct.unpack_from('<II', d, 0)
        form_type = d[10:14]
        (attach,) = struct.unpack_from('<I', d, 16)
        pos = 20
        (nslots,) = struct.unpack_from('<I', d, pos)
        pos += 4
        slots = [self.ref(p, x) for x in struct.unpack_from('<%dI' % nslots, d, pos)]
        pos += 4 * nslots
        (nitems,) = struct.unpack_from('<I', d, pos)
        pos += 4 + 8 * nitems
        incs = []
        for i in range(inc_count):
            (mod,) = struct.unpack_from('<I', d, pos)
            incs.append(self.ref(p, mod))
            pos += 7
        props = []
        for i in range(prop_count):
            vt, fn, prop = struct.unpack_from('<B3xB3xH2x', d, pos)
            v1raw = d[pos + 12:pos + 16]
            v2raw = d[pos + 16:pos + 20]
            props.append(self._prop(p, vt, fn, prop, v1raw, v2raw))
            pos += 24
        if pos != len(d):
            raise ValueError('OMOD %s: DATA разобран на %d из %d байт' % (r.editor_id(), pos, len(d)))
        def kwlist(tag):
            v = r.first(tag)
            return [self.ref(p, x) for x in struct.unpack('<%dI' % (len(v) // 4), v)] if v else []
        return {'key': key, 'edid': r.editor_id(), 'name': self.text(r, p), 'flags': r.flags,
                'form_type': form_type, 'attach': self.ref(p, attach), 'slots': slots,
                'includes': incs, 'props': props, 'target_kw': kwlist(b'MNAM'),
                'filter_kw': kwlist(b'FNAM'), 'loose': self.ref(p, struct.unpack('<I', r.first(b'LNAM'))[0]) if r.first(b'LNAM') else None}

    def _prop(self, p, vt, fn, prop, v1raw, v2raw):
        if vt == 0:
            v1, v2 = struct.unpack('<I', v1raw)[0], struct.unpack('<I', v2raw)[0]
        elif vt == 1:
            v1, v2 = struct.unpack('<f', v1raw)[0], struct.unpack('<f', v2raw)[0]
        elif vt == 2:
            v1, v2 = struct.unpack('<I', v1raw)[0] != 0, struct.unpack('<I', v2raw)[0] != 0
        elif vt == 4:
            v1, v2 = self.ref(p, struct.unpack('<I', v1raw)[0]), struct.unpack('<I', v2raw)[0]
        elif vt == 6:
            v1, v2 = self.ref(p, struct.unpack('<I', v1raw)[0]), struct.unpack('<f', v2raw)[0]
        elif vt == 5:
            v1, v2 = struct.unpack('<I', v1raw)[0], None
        else:
            v1, v2 = v1raw.hex(), v2raw.hex()
        return {'vt': vt, 'fn': fn, 'prop': prop, 'v1': v1, 'v2': v2}
