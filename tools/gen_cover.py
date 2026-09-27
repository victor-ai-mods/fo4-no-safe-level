"""
Картинки для Nexus: обложка и шапка в стиле экрана Пип-боя (зелёный на тёмном, сетка, строки развёртки).
Мотив — шкала здоровья, почти пустая на любом уровне: «опасно всегда». Механику не раскрывает.

    images/cover.png   1920x1080 — картинка галереи / миниатюра
    images/banner.png  1300x372  — шапка страницы (Nexus режет по центру — всё важное в середине по высоте)

    python tools/gen_cover.py
"""

import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, 'images')
FONT = r'C:\Windows\Fonts\bahnschrift.ttf'

GREEN = (26, 255, 110)
GREEN_DIM = (14, 120, 60)
AMBER = (255, 176, 40)
RED = (255, 70, 50)
WHITE = (225, 240, 228)
DARK = (6, 14, 10)

LEVELS = [(5, 0.34), (25, 0.28), (50, 0.31), (80, 0.25)]    # уровень, остаток здоровья на шкале


def font(size, weight='Bold'):
    f = ImageFont.truetype(FONT, size)
    try:
        f.set_variation_by_name(weight)
    except (OSError, ValueError):
        pass
    return f


def background(w, h, seed=7):
    """Тёмный экран: радиальная подсветка, сетка, строки развёртки, лёгкий шум, виньетка."""
    img = Image.new('RGB', (w, h), DARK)
    glow = Image.new('L', (w, h), 0)
    ImageDraw.Draw(glow).ellipse((-w * 0.2, -h * 0.35, w * 1.2, h * 1.35), fill=70)
    glow = glow.filter(ImageFilter.GaussianBlur(min(w, h) // 3))
    img = Image.composite(Image.new('RGB', (w, h), (18, 60, 34)), img, glow)
    d = ImageDraw.Draw(img, 'RGBA')
    step = max(24, w // 40)
    for x in range(0, w, step):
        d.line((x, 0, x, h), fill=GREEN + (14,), width=1)
    for y in range(0, h, step):
        d.line((0, y, w, y), fill=GREEN + (14,), width=1)
    for y in range(0, h, 3):
        d.line((0, y, w, y), fill=(0, 0, 0, 38), width=1)
    rnd = random.Random(seed)
    for _ in range(w * h // 400):
        x, y = rnd.randrange(w), rnd.randrange(h)
        d.point((x, y), fill=GREEN + (rnd.randrange(10, 40),))
    vignette = Image.new('L', (w, h), 0)
    ImageDraw.Draw(vignette).ellipse((-w * 0.15, -h * 0.25, w * 1.15, h * 1.25), fill=255)
    vignette = vignette.filter(ImageFilter.GaussianBlur(min(w, h) // 5))
    return Image.composite(img, Image.new('RGB', (w, h), (0, 0, 0)), vignette)


def glow_text(img, xy, text, f, fill, anchor='mm', radius=14, strength=2):
    """Текст со свечением, как на ЭЛТ-экране."""
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).text(xy, text, font=f, fill=fill + (255,), anchor=anchor)
    halo = layer.filter(ImageFilter.GaussianBlur(radius))
    for _ in range(strength):
        img.paste(halo, (0, 0), halo)
    img.paste(layer, (0, 0), layer)


def hp_bar(img, x, y, w, h, fraction, label):
    """Шкала здоровья в стиле HUD: рамка, деления, красно-янтарная заливка."""
    d = ImageDraw.Draw(img, 'RGBA')
    d.rectangle((x, y, x + w, y + h), outline=GREEN + (230,), width=3)
    fill_w = int((w - 10) * fraction)
    d.rectangle((x + 5, y + 5, x + 5 + fill_w, y + h - 5), fill=RED + (235,))
    d.rectangle((x + 5, y + 5, x + 5 + fill_w, y + 5 + (h - 10) // 3), fill=AMBER + (120,))
    ticks = 10
    for i in range(1, ticks):
        tx = x + 5 + (w - 10) * i // ticks
        d.line((tx, y + h - 12, tx, y + h - 4), fill=GREEN + (160,), width=2)
    f = font(max(18, h // 2), 'SemiBold')
    d.text((x, y - 8), label, font=f, fill=GREEN + (255,), anchor='ld')
    d.text((x + w, y - 8), 'HP', font=f, fill=GREEN_DIM + (255,), anchor='rd')


def cover():
    w, h = 1920, 1080
    img = background(w, h)
    glow_text(img, (w // 2, 250), 'NO SAFE LEVEL', font(190), GREEN, radius=18)
    d = ImageDraw.Draw(img, 'RGBA')
    d.text((w // 2, 400), 'The Commonwealth stays dangerous at any level', font=font(52, 'SemiBold'),
           fill=WHITE + (255,), anchor='mm')
    d.line((w // 2 - 520, 460, w // 2 + 520, 460), fill=GREEN + (160,), width=2)
    bar_w, gap = 360, 60
    total = len(LEVELS) * bar_w + (len(LEVELS) - 1) * gap
    x0 = (w - total) // 2
    for i, (level, frac) in enumerate(LEVELS):
        hp_bar(img, x0 + i * (bar_w + gap), 610, bar_w, 54, frac, 'LEVEL %d' % level)
    d = ImageDraw.Draw(img, 'RGBA')
    d.text((w // 2, 790), 'Armor damage resistance -25%   |   Enemy damage correction multipliers',
           font=font(40, 'SemiBold'), fill=GREEN + (235,), anchor='mm')
    d.text((w // 2, 860), 'Threat level 1-10 in MCM   |   Tuned for Survival   |   ESL, no DLC required',
           font=font(36, 'Regular'), fill=WHITE + (210,), anchor='mm')
    img.save(os.path.join(IMG, 'cover.png'))


def banner():
    w, h = 1300, 372
    img = background(w, h, seed=11)
    glow_text(img, (w // 2, 118), 'NO SAFE LEVEL', font(118), GREEN, radius=12)
    d = ImageDraw.Draw(img, 'RGBA')
    d.text((w // 2, 196), 'The Commonwealth stays dangerous at any level', font=font(34, 'SemiBold'),
           fill=WHITE + (255,), anchor='mm')
    bar_w, gap = 240, 40
    total = len(LEVELS) * bar_w + (len(LEVELS) - 1) * gap
    x0 = (w - total) // 2
    for i, (level, frac) in enumerate(LEVELS):
        hp_bar(img, x0 + i * (bar_w + gap), 275, bar_w, 36, frac, 'LEVEL %d' % level)
    img.save(os.path.join(IMG, 'banner.png'))


if __name__ == '__main__':
    cover()
    banner()
    print('images/cover.png, images/banner.png')
