"""
Генератор MCM и переводов No Safe Level.

Выход (в mod/, откуда их раскладывает tools/deploy.py):
    MCM/Config/NoSafeLevel/config.json            — страница, тексты токенами $NSL_*
    Interface/Translations/NoSafeLevel_{en,ru}.txt — UTF-16 LE с BOM, TAB, CRLF

Настройки — ползунки прямо на глобальные переменные (sourceType GlobalValue; ключи GlobalValue/sourceForm
есть в MCM.swf): «Уровень угрозы» (NSL_ThreatLevel) и уровень, после которого врагам убирается прибавка
+5 здоровья за уровень (NSL_HealthLevelCap, 0 = выключено). Значения живут в сохранении, скрипт NSL:Main
сам замечает изменение в течение нескольких секунд. Механику урона тексты не раскрывают.

    python tools/gen_mcm.py
"""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'mod')
MOD = 'NoSafeLevel'
PLUGIN = 'NoSafeLevel.esp'
THREAT_GLOBAL = PLUGIN + '|801'
HEALTH_CAP_GLOBAL = PLUGIN + '|806'

STRINGS = {
    'en': {
        'MOD_NAME': 'No Safe Level',
        'ABOUT': 'The Commonwealth stays dangerous at any level. Armor damage resistance is reduced by 25%, '
                 'and enemy damage gets correction multipliers.',
        'SEC_MAIN': 'Difficulty',
        'THREAT': 'Threat level',
        'THREAT_HELP': 'Higher is harder. 5 is the intended balance, tuned for Survival. '
                       'Takes effect within a few seconds.',
        'SEC_HEALTH': 'Enemy health',
        'HEALTH_CAP': 'Remove +5 enemy health per level above level',
        'HEALTH_CAP_HELP': 'Enemies above this level keep the base health of their type, but their +5 health '
                           'per level counts only up to this level. 0 = off. Takes effect within a few seconds.',
    },
    'ru': {
        'MOD_NAME': 'No Safe Level',
        'ABOUT': 'Содружество остаётся опасным на любом уровне. Сопротивление урону снижено на 25%, '
                 'для урона врагов введены поправочные коэффициенты.',
        'SEC_MAIN': 'Сложность',
        'THREAT': 'Уровень угрозы',
        'THREAT_HELP': 'Больше — сложнее. 5 — задуманный баланс, настроенный под «Выживание». '
                       'Применяется через несколько секунд.',
        'SEC_HEALTH': 'Здоровье врагов',
        'HEALTH_CAP': 'Убрать прибавку +5 к здоровью врагов после уровня',
        'HEALTH_CAP_HELP': 'У врагов выше этого уровня остаётся базовое здоровье их вида, а прибавка +5 за '
                           'уровень считается только до него. 0 — выключено. Применяется через несколько секунд.',
    },
}


def t(key):
    return '$NSL_' + key


def config():
    return {
        'modName': MOD,
        'displayName': t('MOD_NAME'),
        'minMcmVersion': 2,
        'pluginRequirements': [PLUGIN],
        'content': [
            {'type': 'text', 'text': t('ABOUT')},
            {'type': 'spacer'},
            {'type': 'section', 'text': t('SEC_MAIN')},
            {'type': 'slider', 'text': t('THREAT'), 'help': t('THREAT_HELP'),
             'valueOptions': {'min': 1, 'max': 10, 'step': 1,
                              'sourceType': 'GlobalValue', 'sourceForm': THREAT_GLOBAL}},
            {'type': 'spacer'},
            {'type': 'section', 'text': t('SEC_HEALTH')},
            {'type': 'slider', 'text': t('HEALTH_CAP'), 'help': t('HEALTH_CAP_HELP'),
             'valueOptions': {'min': 0, 'max': 100, 'step': 1,
                              'sourceType': 'GlobalValue', 'sourceForm': HEALTH_CAP_GLOBAL}},
        ],
    }


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\r\n') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        f.write('\n')


def main():
    cfg_dir = os.path.join(OUT, 'MCM', 'Config', MOD)
    write_json(os.path.join(cfg_dir, 'config.json'), config())
    keys = set(STRINGS['en'])
    tr_dir = os.path.join(OUT, 'Interface', 'Translations')
    os.makedirs(tr_dir, exist_ok=True)
    for lang, table in STRINGS.items():
        assert set(table) == keys, '%s: ключи не совпадают с en: %s' % (lang, keys ^ set(table))
        for k, v in table.items():
            assert '\t' not in v and '\n' not in v, (lang, k)
            if k.endswith('_HELP') and len(v) > 165:
                print('  ! %s %s: подсказка %d символов (> 165 — мелкий шрифт)' % (lang, k, len(v)))
        text = ''.join('%s\t%s\r\n' % (t(k), v) for k, v in table.items())
        with open(os.path.join(tr_dir, '%s_%s.txt' % (MOD, lang)), 'wb') as f:
            f.write(b'\xff\xfe' + text.encode('utf-16-le'))
    print('MCM: %s, переводы: %s' % (os.path.relpath(cfg_dir, ROOT), ', '.join(STRINGS)))


if __name__ == '__main__':
    main()
