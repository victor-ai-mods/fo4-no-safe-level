"""
Генератор `NoSafeLevel.esp` (ESL, единственный мастер — Fallout4.esm) по data/bands.json.

    QUST  NSL_Quest          — Start Game Enabled, скрипт NSL:Main: считает множители полос
    GLOB  NSL_ThreatLevel    — «Уровень угрозы» 1..10 (MCM, sourceType GlobalValue)
    GLOB  NSL_Enabled        — 0 = мод выключен (все множители 1), для калибровки и перед удалением
    GLOB  NSL_Debug          — 1 = писать попадания по игроку в Data\\NoSafeLevel\\NoSafeLevel.log
    PERK  NSL_Perk           — по записи на полосу: EP 36 «Multiply 1 + Actor Value Mult» на своё AV;
                               у смешанных полос ещё EP 94 с EPIsDamageType(dtEnergy); запасные
                               записи срабатывают только на оружие не из Fallout4.esm
    AVIF  NSL_B*             — по AV на запись перка (Variable, по умолчанию 0 = без изменений)

Что работает в условиях — проверено тестом (PLAN.md, «Результаты теста»): GetIsID и HasKeyword на
вкладке оружия атакующего; GetActorValue и IsWeaponInList на вкладке атакующего. IsWeaponInList
не использовать: вешает игру в бою (PLAN.md, «Зависание в бою»).

    python tools/bands.py && python tools/gen_esp.py
"""

import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from esp_writer import (PROP_ARRAY_FLOAT, PROP_ARRAY_INT, PROP_ARRAY_OBJECT, PROP_ARRAY_STRING,  # noqa: E402
                        PROP_OBJECT, TES4_LIGHT, Record, Script, build_plugin, vmad, zstring)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN_NAME = 'NoSafeLevel.esp'
SCRIPT_MAIN = 'NSL:Main'

# --- Fallout4.esm ---------------------------------------------------------------
PLAYER_BASE = 0x7
AV_HEALTH = 0x2D4
AV_DAMAGE_RESIST = 0x2E3
AV_ENERGY_RESIST = 0x2EB
AV_UNARMED_DAMAGE = 0x2DF
AV_HC_INCOMING = 0x84A
GLOB_HC_SCALE_DAMAGE = 0x84C
DT_ENERGY = 0x60A81
KEYWORDS = {
    'WeaponTypeUnarmed': 0x05240E, 'WeaponTypeExplosive': 0x04C922, 'WeaponTypeGrenade': 0x10C415,
    'WeaponTypeMine': 0x10C414, 'WeaponTypeThrown': 0x04A0A6, 'WeaponTypeMelee1H': 0x04A0A4,
    'WeaponTypeMelee2H': 0x04A0A5, 'WeaponTypeHandToHand': 0x226453, 'WeaponTypeHeavyGun': 0x04A0A3,
    'WeaponTypeBallistic': 0x092A86, 'WeaponTypeAutomatic': 0x04A0A2, 'WeaponTypeShotgun': 0x226454,
    'WeaponTypeLaser': 0x092A84, 'WeaponTypePlasma': 0x092A85, 'WeaponTypeAlienBlaster': 0x16968B,
    'WeaponTypeGammaGun': 0x225762, 'WeaponTypeMissileLauncher': 0x22575B, 'WeaponTypeFatman': 0x22575C,
    'WeaponTypeMolotov': 0x21A29F,
}

# --- точки, функции, условия (wbDefinitionsFO4.pas; вкладки EP 36: 0 владелец, 1 атакующий, 2 оружие) --
EP_INCOMING_WEAPON = 36
EP_TYPED_INCOMING = 94
TABS = {EP_INCOMING_WEAPON: 3, EP_TYPED_INCOMING: 4}
FN_MUL_1_PLUS_AV_MULT = 14
EPFT_AVIF = 8
CF_GET_AV, CF_GET_IS_ID, CF_IS_WEAPON_IN_LIST = 14, 72, 398
CF_HAS_KEYWORD, CF_EP_IS_DAMAGE_TYPE = 560, 736
OP_EQ, OP_NE, OP_GE, OP_LT = 0, 1, 3, 4
FLAG_OR = 0x01

# Виды записей для скрипта (NSL:Main, BandKind).
KIND_PHYS, KIND_ENERGY, KIND_MIXED, KIND_MIXED_ENERGY = 0, 1, 2, 3

# K(L) — PLAN.md, «Формула одного попадания по игроку».
K_LEVELS = [4.0, 15.0, 30.0, 50.0, 80.0]
K_VALUES = [0.89, 1.08, 1.20, 1.38, 1.76]

# --- свои FormID (ESL: 0x800..0xFFF) --------------------------------------------
BASE = 0x01000000
FID_QUEST = BASE | 0x800
FID_THREAT = BASE | 0x801
FID_ENABLED = BASE | 0x802
FID_DEBUG = BASE | 0x803
FID_PERK = BASE | 0x804
FID_KNOWN = BASE | 0x805                             # был FLST NSL_KnownWeapons (до 1.0.1), не занимать
FID_AV_FIRST = 0x810


def ctda(func, comp, param1=0, op=OP_EQ, flags=0):
    """CTDA 32 байта: (оператор<<5 | флаги), сравнение, функция, параметр; run on = subject."""
    return struct.pack('<B3sfHHIIHHIi', (op << 5) | flags, b'\x00' * 3, float(comp), func, 0, param1,
                       0, 0, 0, 0, -1)


def or_chain(func, params, comp=1.0):
    """(func(p1) == comp) OR (func(p2) == comp) OR ... — флаг OR у всех, кроме последнего."""
    return [ctda(func, comp, p, OP_EQ, FLAG_OR if i < len(params) - 1 else 0) for i, p in enumerate(params)]


def not_player():
    return ctda(CF_GET_IS_ID, 0.0, PLAYER_BASE)


def glob(fid, edid, value):
    r = Record(b'GLOB', fid, edid)
    r.add(b'FLTV', struct.pack('<f', value))
    return r


def avif(fid, edid, desc):
    r = Record(b'AVIF', fid, edid)
    r.add(b'DESC', zstring(desc))
    r.add(b'NAM0', struct.pack('<f', 0.0))
    r.add(b'AVFL', struct.pack('<I', 0x2000))      # как у HC_IncomingDamageMult
    r.add(b'NAM1', struct.pack('<I', 8))           # Variable
    return r


def add_entry(perk, entry_id, ep, av_fid, tabs):
    """tabs — {вкладка: [CTDA, ...]}."""
    perk.add(b'PRKE', struct.pack('<BBB', 2, 0, 50))
    perk.add(b'DATA', struct.pack('<BBB', ep, FN_MUL_1_PLUS_AV_MULT, TABS[ep]))
    for tab in sorted(tabs):
        if not tabs[tab]:
            continue
        perk.add(b'PRKC', struct.pack('<B', tab))
        for c in tabs[tab]:
            perk.add(b'CTDA', c)
    perk.add(b'EPFT', struct.pack('<B', EPFT_AVIF))
    perk.add(b'EPFB', struct.pack('<H', entry_id))
    perk.add(b'EPFD', struct.pack('<If', av_fid, 1.0))
    perk.add(b'PRKF', b'')


def fallback_conditions(groups):
    out = []
    for group in groups:
        positive = [k for k in group if not k.startswith('!')]
        negative = [k[1:] for k in group if k.startswith('!')]
        out += or_chain(CF_HAS_KEYWORD, [KEYWORDS[k] for k in positive])
        out += [ctda(CF_HAS_KEYWORD, 0.0, KEYWORDS[k]) for k in negative]
    return out


def build(data):
    perk = Record(b'PERK', FID_PERK, 'NSL_Perk')
    perk.add(b'FULL', zstring('No Safe Level'))
    perk.add(b'DESC', zstring(''))
    perk.add(b'DATA', bytes([0, 0, 1, 0, 1]))       # не играбельный, скрытый
    avifs, table = [], []
    next_av = FID_AV_FIRST

    def new_av(edid, desc):
        nonlocal next_av
        fid = BASE | next_av
        next_av += 1
        avifs.append(avif(fid, edid, desc))
        return fid

    for i, b in enumerate(data['bands']):
        edid = 'NSL_B%02d_%s' % (i, b['name'].replace('.', '_'))
        av = new_av(edid, 'No Safe Level: damage band %s' % b['name'])
        attacker = [not_player()]
        if b['kind'] == 'weapon':
            weapon = or_chain(CF_GET_IS_ID, b['weapons'])
        elif b['kind'] == 'creature':
            attacker += [ctda(CF_GET_AV, b['lo'], AV_UNARMED_DAMAGE, OP_GE),
                         ctda(CF_GET_AV, b['hi'], AV_UNARMED_DAMAGE, OP_LT)]
            weapon = or_chain(CF_GET_IS_ID, b['weapons'])
        elif b['kind'] == 'unarmed':
            attacker += [ctda(CF_GET_AV, b['lo'], AV_UNARMED_DAMAGE, OP_GE),
                         ctda(CF_GET_AV, b['hi'], AV_UNARMED_DAMAGE, OP_LT)]
            weapon = [ctda(CF_HAS_KEYWORD, 1.0, KEYWORDS['WeaponTypeUnarmed'])]
            weapon += [ctda(CF_GET_IS_ID, 0.0, w) for w in data['unarmed_with_base']]
        else:
            # «Не оружие Fallout4.esm» — цепочкой GetIsID(w) == 0 на вкладке оружия, а не IsWeaponInList на
            # вкладке атакующего: тот берёт замок экипировки атакующего под глобальным замком перков, а ИИ боя
            # (Actor::CalculateDamagePerSecond) берёт их в обратном порядке — взаимная блокировка, игра висит.
            weapon = fallback_conditions(b['keywords'])
            weapon += [ctda(CF_HAS_KEYWORD, 0.0, KEYWORDS[k]) for k in data['fallback_exclude']]
            weapon += [ctda(CF_GET_IS_ID, 0.0, w) for w in data['known']]
        kind = {'phys': KIND_PHYS, 'energy': KIND_ENERGY, 'mixed': KIND_MIXED}[b['dtype']]
        entry_id = len(table)
        add_entry(perk, entry_id, EP_INCOMING_WEAPON, av, {1: attacker, 2: weapon})
        table.append((av, kind, b))
        if b['dtype'] == 'mixed':
            av_en = new_av(edid + '_En', 'No Safe Level: energy part of %s' % b['name'])
            add_entry(perk, len(table), EP_TYPED_INCOMING, av_en,
                      {1: attacker, 2: weapon, 3: [ctda(CF_EP_IS_DAMAGE_TYPE, 1.0, DT_ENERGY)]})
            table.append((av_en, KIND_MIXED_ENERGY, b))

    quest = Record(b'QUST', FID_QUEST, 'NSL_Quest')
    s = Script(SCRIPT_MAIN)
    for name, fid in [('NSL_Perk', FID_PERK), ('Health', AV_HEALTH), ('DamageResist', AV_DAMAGE_RESIST),
                      ('EnergyResist', AV_ENERGY_RESIST), ('UnarmedDamage', AV_UNARMED_DAMAGE),
                      ('HC_IncomingDamageMult', AV_HC_INCOMING), ('HC_Rule_ScaleDamage', GLOB_HC_SCALE_DAMAGE),
                      ('NSL_ThreatLevel', FID_THREAT), ('NSL_Enabled', FID_ENABLED), ('NSL_Debug', FID_DEBUG)]:
        s.prop(name, PROP_OBJECT, fid)
    s.prop('BandAV', PROP_ARRAY_OBJECT, [t[0] for t in table])
    s.prop('BandKind', PROP_ARRAY_INT, [t[1] for t in table])
    s.prop('BandPhys', PROP_ARRAY_FLOAT, [t[2]['phys'] for t in table])
    s.prop('BandEnergy', PROP_ARRAY_FLOAT, [t[2]['energy'] for t in table])
    s.prop('BandFloorCoef', PROP_ARRAY_FLOAT, [t[2]['floor_coef'] for t in table])
    s.prop('BandKWeight', PROP_ARRAY_FLOAT, [t[2]['k_weight'] for t in table])
    s.prop('BandName', PROP_ARRAY_STRING, [t[2]['name'] + ('_en' if t[1] == KIND_MIXED_ENERGY else '')
                                           for t in table])
    s.prop('KLevel', PROP_ARRAY_FLOAT, K_LEVELS)
    s.prop('KValue', PROP_ARRAY_FLOAT, K_VALUES)
    quest.add(b'VMAD', vmad([s]))
    quest.add(b'FULL', zstring('No Safe Level'))
    quest.add(b'DNAM', struct.pack('<HBBII', 0x0111, 0, 0x5E, 0, 0))   # Start Game Enabled | Run Once
    quest.add(b'NEXT', b'')
    quest.add(b'ANAM', struct.pack('<I', 0))

    globs = [glob(FID_THREAT, 'NSL_ThreatLevel', 5.0), glob(FID_ENABLED, 'NSL_Enabled', 1.0),
             glob(FID_DEBUG, 'NSL_Debug', 0.0)]
    groups = [(b'GLOB', globs), (b'AVIF', avifs), (b'PERK', [perk]), (b'QUST', [quest])]
    return groups, next_av, table


def check(path, n_entries, n_avifs):
    from esm import Plugin
    plugin = Plugin(path)
    assert plugin.masters == ['Fallout4.esm'], 'мастера: %r' % (plugin.masters,)
    counts = {sig.decode(): sum(1 for _ in plugin.records(sig))
              for sig in (b'GLOB', b'AVIF', b'FLST', b'PERK', b'QUST')}
    assert counts == {'GLOB': 3, 'AVIF': n_avifs, 'FLST': 0, 'PERK': 1, 'QUST': 1}, counts
    perk = next(plugin.records(b'PERK'))
    n = sum(1 for tag, _ in perk.subrecords() if tag == b'PRKE')
    assert n == n_entries, 'записей в перке: %d' % n
    funcs = {struct.unpack_from('<H', data, 8)[0] for tag, data in perk.subrecords() if tag == b'CTDA'}
    assert CF_IS_WEAPON_IN_LIST not in funcs, 'IsWeaponInList в условиях перка — взаимная блокировка в бою'
    print('  проверка: мастер один, записи %s, записей в перке %d' % (counts, n))


def main():
    with open(os.path.join(ROOT, 'data', 'bands.json'), encoding='utf-8') as f:
        data = json.load(f)
    groups, next_av, table = build(data)
    assert next_av <= 0xFFF, 'FormID вышли за диапазон ESL'
    out_path = os.path.join(ROOT, 'build', PLUGIN_NAME)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    blob = build_plugin(['Fallout4.esm'], groups, next_av, flags=TES4_LIGHT)
    with open(out_path, 'wb') as f:
        f.write(blob)
    print('%s: %d байт, записей перка %d' % (out_path, len(blob), len(table)))
    check(out_path, len(table), len(table))


if __name__ == '__main__':
    main()
