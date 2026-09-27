"""Шапка страницы Nexus из иллюстрированной обложки.

    images/cover2.png  (картинка из ChatGPT, уже с заголовком)  ->  images/banner2.png  1300x372

Из обложки берётся полоса сцены (шлем, стена, коготь смерти, рейдеры); заголовок, подзаголовок и HUD
перерисовываются поверх, потому что в полосу они не помещаются.

    python tools/gen_banner.py
"""

import os

from PIL import Image, ImageDraw

from gen_cover import GREEN, RED, WHITE, font, glow_text

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, 'images')

W, H = 1300, 372
CROP_TOP = 193        # верх полосы в пикселях обложки: сразу под её подзаголовком
SHADE_H = 150         # высота затемнения сверху, под заголовком


def shade(img, h, alpha):
    """Затемнение сверху вниз с мягким краем — под заголовком."""
    mask = Image.new('L', img.size, 0)
    d = ImageDraw.Draw(mask)
    for y in range(h):
        d.line((0, y, img.width, y), fill=int(alpha * (1 - y / h) ** 1.5))
    img.paste(Image.new('RGB', img.size, (0, 0, 0)), (0, 0), mask)


def main():
    src = Image.open(os.path.join(IMG, 'cover2.png')).convert('RGB')
    scaled = src.resize((W, round(src.height * W / src.width)), Image.LANCZOS)
    top = round(CROP_TOP * W / src.width)
    img = scaled.crop((0, top, W, top + H))

    shade(img, SHADE_H, 230)
    glow_text(img, (W // 2, 50), 'NO SAFE LEVEL', font(92, 'Bold Condensed'), GREEN, radius=10)
    d = ImageDraw.Draw(img, 'RGBA')
    d.text((W // 2, 110), 'The Commonwealth stays dangerous at any level', font=font(27, 'SemiBold Condensed'),
           fill=WHITE + (255,), anchor='mm')

    # HUD как на обложке: уровень 80 и почти пустая шкала здоровья
    x, y = 26, 318
    glow_text(img, (x, y - 6), 'LVL 80', font(24, 'SemiBold'), GREEN, anchor='ld', radius=4, strength=1)
    d = ImageDraw.Draw(img, 'RGBA')
    d.rectangle((x, y, x + 200, y + 18), outline=GREEN + (255,), width=2)
    d.rectangle((x + 4, y + 4, x + 11, y + 14), fill=RED + (255,))

    img.save(os.path.join(IMG, 'banner2.png'))
    print('images/banner2.png')


if __name__ == '__main__':
    main()
