"""
Раскладка мода по игре.

  python tools/deploy.py                   — NoSafeLevel.esp, NSL\\Main.pex, MCM, переводы, папка лога; включить
  python tools/deploy.py --remove          — снять плагин и убрать его файлы (лог остаётся)
  python tools/deploy.py --test [--remove] — то же для тестового NoSafeLevel_Test.esp (TEST.md)

`Plugins.txt` в этой установке живёт в ДВУХ местах (игра читает
`%LOCALAPPDATA%\\Fallout4\\Plugins.txt`) — правятся оба. Всё, что перезаписывается,
сначала уезжает в `<игра>\\Backup`.
"""

import argparse
import datetime
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.environ.get('FO4_PATH', r'D:\Games\Fallout 4')
DATA = os.path.join(GAME, 'Data')
TARGETS = {
    False: ('NoSafeLevel.esp', [os.path.join('NSL', 'Main.pex')], True),
    True: ('NoSafeLevel_Test.esp', [os.path.join('NSL', 'TestQuest.pex'), os.path.join('NSL', 'CalibQuest.pex')],
           False),
}
PLUGIN, SCRIPTS, WITH_MOD_FILES = TARGETS[False]
MOD_FILES = os.path.join(ROOT, 'mod')           # пути внутри — как от Data

PLUGIN_LISTS = [
    os.path.join(os.environ['LOCALAPPDATA'], 'Fallout4', 'Plugins.txt'),
    os.path.join(GAME, 'fallout4', 'Plugins.txt'),
]


def backup(path):
    if not os.path.exists(path):
        return None
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    target_dir = os.path.join(GAME, 'Backup')
    os.makedirs(target_dir, exist_ok=True)
    target = os.path.join(target_dir, '%s.%s.bak' % (os.path.basename(path), stamp))
    shutil.copy2(path, target)
    return target


def copy(src, dst):
    saved = backup(dst)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    print('  %s%s' % (dst, ('  (старый -> %s)' % os.path.basename(saved)) if saved else ''))


def set_enabled(enabled):
    for path in PLUGIN_LISTS:
        if not os.path.exists(path):
            print('  нет %s — пропущено' % path)
            continue
        with open(path, encoding='utf-8-sig') as f:
            lines = f.read().splitlines()
        kept = [ln for ln in lines if ln.lstrip('*').strip().lower() != PLUGIN.lower()]
        if enabled:
            kept.append('*' + PLUGIN)
        if kept != lines:
            backup(path)
            with open(path, 'w', encoding='utf-8', newline='\n') as f:
                f.write('\n'.join(kept) + '\n')
        print('  %s: %s' % (path, 'включён' if enabled else 'выключен'))


def mod_files():
    if not WITH_MOD_FILES:
        return [os.path.join('NoSafeLevel', 'ReadMe.txt')]
    out = []
    for base, _, names in os.walk(MOD_FILES):
        for name in names:
            out.append(os.path.relpath(os.path.join(base, name), MOD_FILES))
    return sorted(out)


def script_paths():
    return [(os.path.join(ROOT, 'build', 'scripts', n), os.path.join(DATA, 'Scripts', n)) for n in SCRIPTS
            if os.path.exists(os.path.join(ROOT, 'build', 'scripts', n))]


def install():
    print('Файлы:')
    copy(os.path.join(ROOT, 'build', PLUGIN), os.path.join(DATA, PLUGIN))
    for src, dst in script_paths():
        copy(src, dst)
    for rel in mod_files():
        copy(os.path.join(MOD_FILES, rel), os.path.join(DATA, rel))
    print('Порядок загрузки:')
    set_enabled(True)


def remove():
    print('Порядок загрузки:')
    set_enabled(False)
    print('Файлы:')
    extra = [os.path.join(DATA, rel) for rel in mod_files() if not rel.lower().endswith('readme.txt')]
    for path in [os.path.join(DATA, PLUGIN)] + [dst for _, dst in script_paths()] + (extra if WITH_MOD_FILES else []):
        if os.path.exists(path):
            backup(path)
            os.remove(path)
            print('  удалён %s' % path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--remove', action='store_true')
    ap.add_argument('--test', action='store_true', help='тестовый плагин вместо мода')
    args = ap.parse_args()
    global PLUGIN, SCRIPTS, WITH_MOD_FILES
    PLUGIN, SCRIPTS, WITH_MOD_FILES = TARGETS[args.test]
    if args.remove:
        remove()
    else:
        install()
        print('\nesp и .pex подхватываются только при запуске игры.')


if __name__ == '__main__':
    main()
