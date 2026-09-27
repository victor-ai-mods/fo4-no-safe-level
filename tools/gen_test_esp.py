"""
Генератор тестового плагина `NoSafeLevel_Test.esp` — проверки из PLAN.md до основной работы.

Перк на игроке с набором записей точек урона. Каждая запись умножает урон на (1 + AV игрока),
поэтому при AV = 0 она ничего не делает, а скрипт включает их по одной (AV = 3 -> x4).

    AVIF  NSL_T_*          — управляющие AV (Variable, по умолчанию 0), как HC_IncomingDamageMult
    FLST  NSL_T_WeaponList — 10-мм пистолет (для IsWeaponInList)
    PERK  NSL_T_Perk       — записи ниже
    QUST  NSL_TestQuest    — НЕ Start Game Enabled: запускается из консоли `startquest NSL_TestQuest`,
                             скрипт NSL:TestQuest проводит весь тест сам (механика перков, без мода)
    QUST  NSL_CalibQuest   — `startquest NSL_CalibQuest`: калибровка с установленным NoSafeLevel.esp,
                             скрипт NSL:CalibQuest (враги по очереди, мод выключен/включён)

Раскладка PERK снята с ванильного HC_DamageMultPerk (EP 36, «Multiply Actor Value Mult» на AV
HC_IncomingDamageMult) и CompCodsworthPerk (EP 94 с EPIsDamageType на 4-й вкладке):
  PRKE (тип 2, ранг, приоритет) -> DATA (точка, функция, число вкладок) -> PRKC+CTDA...
  -> EPFT 8 (AVIF) -> EPFB (уникальный id записи) -> EPFD (AV + множитель) -> PRKF

    python tools/gen_test_esp.py
"""

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from esp_writer import (PROP_OBJECT, TES4_LIGHT, Record, Script, build_plugin, vmad,  # noqa: E402
                        zstring)

PLUGIN_NAME = 'NoSafeLevel_Test.esp'

# --- Fallout4.esm -----------------------------------------------------------
AV_HEALTH = 0x2D4
AV_DAMAGE_RESIST = 0x2E3
AV_ENERGY_RESIST = 0x2EB
AV_HC_INCOMING = 0x84A          # HC_IncomingDamageMult (по умолчанию 2.0)
GLOB_HC_SCALE_DAMAGE = 0x84C    # HC_Rule_ScaleDamage
DT_PHYSICAL = 0x60A87
DT_ENERGY = 0x60A81
KW_BALLISTIC = 0x92A86          # WeaponTypeBallistic (есть у 10-мм)
WEAP_10MM = 0x4822
WEAP_LASER = 0x9983B            # LaserGun
AMMO_10MM = 0x1F276
AMMO_FUSION_CELL = 0xC1897
NPC_RAIDER = 0x1E7429           # EncRaider02b, ур. 9
NPC_RADROACH = 0x475DF          # EncRadRoach, ур. 1, UnarmedDamage нет
NPC_RADROACH_GLOWING = 0x1BBEAA # EncRadRoachGlowingNOSCALE, UnarmedDamage 2
NPC_MOLERAT = 0x1D966           # EncMolerat01Template, UnarmedDamage 5
NPC_FERAL_GHOUL = 0x758AD       # encFeralGhoul01Template (UnarmedFeralGhoul 15)
NPC_DEATHCLAW = 0x1DB4C         # EncDeathclaw01Template, UnarmedDamage 60
WEAP_PIPE = 0x24F55             # PipeGun
AMMO_38 = 0x4CE87
AV_UNARMED_DAMAGE = 0x2DF
EXPL_FRAG = 0xE574F             # fragGrenadeExplosion

# --- точки и функции перков (wbDefinitionsFO4.pas) --------------------------
EP_INCOMING_WEAPON = 36         # вкладки: 0 владелец, 1 атакующий, 2 оружие атакующего
EP_TYPED_INCOMING = 94          # + 3 тип урона
EP_INCOMING_EXPLOSION = 124     # одна вкладка
TABS = {EP_INCOMING_WEAPON: 3, EP_TYPED_INCOMING: 4, EP_INCOMING_EXPLOSION: 1}
FN_ADD_AV_MULT = 5
FN_MUL_1_PLUS_AV_MULT = 14
EPFT_AVIF = 8

# --- функции условий --------------------------------------------------------
CF_GET_AV = 14
CF_GET_IS_ID = 72
CF_IS_WEAPON_IN_LIST = 398
CF_HAS_KEYWORD = 560
CF_EP_IS_DAMAGE_TYPE = 736

# --- свои FormID (ESL: 0x800..0xFFF) ----------------------------------------
BASE = 0x01000000
TEST_AVS = [
    # (EDID, описание — в плагине строки cp1252, поэтому по-английски)
    ('NSL_T_Mul36', 'EP36 x(1+AV), no conditions'),
    ('NSL_T_Mul94Phys', 'EP94 x(1+AV), damage type physical'),
    ('NSL_T_Mul94En', 'EP94 x(1+AV), damage type energy'),
    ('NSL_T_Mul124', 'EP124 x(1+AV), explosions'),
    ('NSL_T_Add36', 'EP36 +AV (Add Actor Value Mult)'),
    ('NSL_T_ListA', 'EP36 x(1+AV), attacker: IsWeaponInList'),
    ('NSL_T_ListW', 'EP36 x(1+AV), attacker weapon: IsWeaponInList'),
    ('NSL_T_IdW', 'EP36 x(1+AV), attacker weapon: GetIsID(10mm)'),
    ('NSL_T_AttAV', 'EP36 x(1+AV), attacker: GetActorValue(NSL_T_Marker) == 5'),
    ('NSL_T_KwW', 'EP36 x(1+AV), attacker weapon: HasKeyword(WeaponTypeBallistic), control'),
    ('NSL_T_Marker', 'marker on the test NPC'),
]
FID_AV = {edid: BASE | (0x800 + i) for i, (edid, _) in enumerate(TEST_AVS)}
FID_LIST = BASE | 0x820
FID_PERK = BASE | 0x821
FID_QUEST = BASE | 0x822
FID_CALIB = BASE | 0x823
NEXT_OBJECT_ID = 0x824

SCRIPT_QUEST = 'NSL:TestQuest'
SCRIPT_CALIB = 'NSL:CalibQuest'


def ctda(func, comp, param1=0, op=0):
    """CTDA 32 байта: оператор<<5, сравнение (float), функция, параметры; run on = subject."""
    return struct.pack('<B3sfHHIIHHIi', op << 5, b'\x00' * 3, comp, func, 0, param1, 0, 0, 0, 0, -1)


def build_avif(edid, desc):
    r = Record(b'AVIF', FID_AV[edid], edid)
    r.add(b'DESC', zstring(desc))
    r.add(b'NAM0', struct.pack('<f', 0.0))
    r.add(b'AVFL', struct.pack('<I', 0x2000))      # как у HC_IncomingDamageMult
    r.add(b'NAM1', struct.pack('<I', 8))           # Variable
    return r


def build_list():
    r = Record(b'FLST', FID_LIST, 'NSL_T_WeaponList')
    r.add(b'LNAM', struct.pack('<I', WEAP_10MM))
    return r


def entry(r, entry_id, ep, fn, av_edid, conds=()):
    """conds — [(вкладка, CTDA), ...]."""
    r.add(b'PRKE', struct.pack('<BBB', 2, 0, 50))
    r.add(b'DATA', struct.pack('<BBB', ep, fn, TABS[ep]))
    for tab, c in conds:
        r.add(b'PRKC', struct.pack('<B', tab))
        r.add(b'CTDA', c)
    r.add(b'EPFT', struct.pack('<B', EPFT_AVIF))
    r.add(b'EPFB', struct.pack('<H', entry_id))
    r.add(b'EPFD', struct.pack('<If', FID_AV[av_edid], 1.0))
    r.add(b'PRKF', b'')


def build_perk():
    r = Record(b'PERK', FID_PERK, 'NSL_T_Perk')
    r.add(b'FULL', zstring('No Safe Level test'))
    r.add(b'DESC', zstring(''))
    r.add(b'DATA', bytes([0, 0, 1, 1, 1]))        # как у HC_DamageMultPerk
    mul, add = FN_MUL_1_PLUS_AV_MULT, FN_ADD_AV_MULT
    entry(r, 0, EP_INCOMING_WEAPON, mul, 'NSL_T_Mul36')
    entry(r, 1, EP_TYPED_INCOMING, mul, 'NSL_T_Mul94Phys', [(3, ctda(CF_EP_IS_DAMAGE_TYPE, 1.0, DT_PHYSICAL))])
    entry(r, 2, EP_TYPED_INCOMING, mul, 'NSL_T_Mul94En', [(3, ctda(CF_EP_IS_DAMAGE_TYPE, 1.0, DT_ENERGY))])
    entry(r, 3, EP_INCOMING_EXPLOSION, mul, 'NSL_T_Mul124')
    entry(r, 4, EP_INCOMING_WEAPON, add, 'NSL_T_Add36')
    entry(r, 5, EP_INCOMING_WEAPON, mul, 'NSL_T_ListA', [(1, ctda(CF_IS_WEAPON_IN_LIST, 1.0, FID_LIST))])
    entry(r, 6, EP_INCOMING_WEAPON, mul, 'NSL_T_ListW', [(2, ctda(CF_IS_WEAPON_IN_LIST, 1.0, FID_LIST))])
    entry(r, 7, EP_INCOMING_WEAPON, mul, 'NSL_T_IdW', [(2, ctda(CF_GET_IS_ID, 1.0, WEAP_10MM))])
    entry(r, 8, EP_INCOMING_WEAPON, mul, 'NSL_T_AttAV',
          [(1, ctda(CF_GET_AV, 5.0, FID_AV['NSL_T_Marker']))])
    entry(r, 9, EP_INCOMING_WEAPON, mul, 'NSL_T_KwW', [(2, ctda(CF_HAS_KEYWORD, 1.0, KW_BALLISTIC))])
    return r


def build_qust():
    r = Record(b'QUST', FID_QUEST, 'NSL_TestQuest')
    s = Script(SCRIPT_QUEST)
    objects = [
        ('TestPerk', FID_PERK),
        ('Health', AV_HEALTH), ('DamageResist', AV_DAMAGE_RESIST), ('EnergyResist', AV_ENERGY_RESIST),
        ('HC_IncomingDamageMult', AV_HC_INCOMING), ('HC_Rule_ScaleDamage', GLOB_HC_SCALE_DAMAGE),
        ('RaiderBase', NPC_RAIDER), ('Pistol10mm', WEAP_10MM), ('LaserPistol', WEAP_LASER),
        ('Ammo10mm', AMMO_10MM), ('AmmoFusionCell', AMMO_FUSION_CELL), ('FragExplosion', EXPL_FRAG),
    ]
    for edid, _ in TEST_AVS:
        objects.append((edid[len('NSL_T_'):], FID_AV[edid]))
    for name, fid in objects:
        s.prop(name, PROP_OBJECT, fid)
    r.add(b'VMAD', vmad([s]))
    r.add(b'FULL', zstring('No Safe Level test'))
    r.add(b'DNAM', struct.pack('<HBBII', 0x0010, 0, 0x5E, 0, 0))   # без Start Game Enabled и Run Once
    r.add(b'NEXT', b'')
    r.add(b'ANAM', struct.pack('<I', 0))
    return r


def build_calib():
    r = Record(b'QUST', FID_CALIB, 'NSL_CalibQuest')
    s = Script(SCRIPT_CALIB)
    for name, fid in [
            ('Health', AV_HEALTH), ('DamageResist', AV_DAMAGE_RESIST), ('EnergyResist', AV_ENERGY_RESIST),
            ('UnarmedDamage', AV_UNARMED_DAMAGE), ('RaiderBase', NPC_RAIDER), ('Pistol10mm', WEAP_10MM),
            ('PipeGun', WEAP_PIPE), ('LaserPistol', WEAP_LASER), ('Ammo10mm', AMMO_10MM), ('Ammo38', AMMO_38),
            ('AmmoFusionCell', AMMO_FUSION_CELL), ('RadRoachBase', NPC_RADROACH),
            ('RadRoachGlowingBase', NPC_RADROACH_GLOWING), ('MoleratBase', NPC_MOLERAT),
            ('FeralGhoulBase', NPC_FERAL_GHOUL), ('DeathclawBase', NPC_DEATHCLAW)]:
        s.prop(name, PROP_OBJECT, fid)
    r.add(b'VMAD', vmad([s]))
    r.add(b'FULL', zstring('No Safe Level calibration'))
    r.add(b'DNAM', struct.pack('<HBBII', 0x0010, 0, 0x5E, 0, 0))
    r.add(b'NEXT', b'')
    r.add(b'ANAM', struct.pack('<I', 0))
    return r


def check(path):
    from esm import Plugin
    plugin = Plugin(path)
    assert plugin.masters == ['Fallout4.esm'], 'мастера: %r' % (plugin.masters,)
    counts = {sig.decode(): sum(1 for _ in plugin.records(sig)) for sig in (b'AVIF', b'FLST', b'PERK', b'QUST')}
    assert counts == {'AVIF': len(TEST_AVS), 'FLST': 1, 'PERK': 1, 'QUST': 2}, counts
    perk = next(plugin.records(b'PERK'))
    n = sum(1 for tag, _ in perk.subrecords() if tag == b'PRKE')
    assert n == 10, 'записей в перке: %d' % n
    print('  проверка: мастер один, записи %s, записей в перке %d' % (counts, n))


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_path = os.path.join(root, 'build', PLUGIN_NAME)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    groups = [
        (b'AVIF', [build_avif(edid, desc) for edid, desc in TEST_AVS]),
        (b'FLST', [build_list()]),
        (b'PERK', [build_perk()]),
        (b'QUST', [build_qust(), build_calib()]),
    ]
    blob = build_plugin(['Fallout4.esm'], groups, NEXT_OBJECT_ID, flags=TES4_LIGHT)
    with open(out_path, 'wb') as f:
        f.write(blob)
    print('%s: %d байт' % (out_path, len(blob)))
    check(out_path)


if __name__ == '__main__':
    main()
