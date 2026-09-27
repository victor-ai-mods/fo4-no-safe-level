"""
Архив для Nexus: release/NoSafeLevel/ (раскладка как в Data) и release/NoSafeLevel-<версия>.zip.

    python tools/package.py 1.0.0

Внутри: NoSafeLevel.esp, Scripts\\NSL\\Main.pex, исходник Scripts\\Source\\User\\NSL\\Main.psc,
MCM\\Config\\NoSafeLevel\\config.json, Interface\\Translations\\NoSafeLevel_{en,ru}.txt и
NoSafeLevel\\ReadMe.txt (папка для отладочного лога: Garden of Eden папки не создаёт).
Тестовый плагин в архив не входит.
"""

import os
import shutil
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, 'build')
OUT = os.path.join(ROOT, 'release')
NAME = 'NoSafeLevel'


def files():
    """(источник, путь в архиве)."""
    out = [(os.path.join(BUILD, 'NoSafeLevel.esp'), 'NoSafeLevel.esp'),
           (os.path.join(BUILD, 'scripts', 'NSL', 'Main.pex'), os.path.join('Scripts', 'NSL', 'Main.pex')),
           (os.path.join(ROOT, 'papyrus', 'NSL', 'Main.psc'),
            os.path.join('Scripts', 'Source', 'User', 'NSL', 'Main.psc'))]
    mod = os.path.join(ROOT, 'mod')
    for base, _, names in os.walk(mod):
        for n in names:
            src = os.path.join(base, n)
            out.append((src, os.path.relpath(src, mod)))
    return sorted(out, key=lambda t: t[1])


def main():
    if len(sys.argv) != 2:
        sys.exit('версия? python tools/package.py 1.0.0')
    version = sys.argv[1]
    folder = os.path.join(OUT, NAME)
    os.makedirs(OUT, exist_ok=True)
    if os.path.exists(folder):
        shutil.rmtree(folder)
    archive = os.path.join(OUT, '%s-%s.zip' % (NAME, version))
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for src, rel in files():
            if not os.path.exists(src):
                sys.exit('нет %s — сначала собери мод (README.ru.md, «Сборка»)' % src)
            dst = os.path.join(folder, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            z.write(src, rel.replace(os.sep, '/'))
            print('  %s' % rel)
    print('%s: %d байт' % (archive, os.path.getsize(archive)))


if __name__ == '__main__':
    main()
