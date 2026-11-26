"""生成大肥鱼表情包（原创、透明底、512x512）。"""
from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
SIZE = 512
BODY = "#58a9e8"
BODY_DARK = "#2e6f9e"
BELLY = "#dff4ff"
INK = "#173b57"
BLUSH = "#ff9fbe"
WHITE = "#f8fdff"

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
]


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def base(draw: ImageDraw.ImageDraw) -> None:
    # 尾巴
    draw.polygon([(120, 230), (50, 175), (70, 255), (45, 340), (120, 300)], fill=BODY, outline=BODY_DARK, width=8)
    # 身体
    draw.ellipse((110, 150, 402, 376), fill=BODY, outline=BODY_DARK, width=10)
    # 肚皮
    draw.ellipse((162, 250, 350, 360), fill=BELLY)
    # 背鳍
    draw.polygon([(205, 152), (245, 95), (292, 152)], fill="#77c2f2", outline=BODY_DARK, width=6)
    # 侧鳍
    draw.polygon([(335, 270), (420, 245), (395, 315)], fill="#77c2f2", outline=BODY_DARK, width=6)
    # 腮红
    draw.ellipse((145, 275, 185, 300), fill=BLUSH)
    draw.ellipse((325, 275, 365, 300), fill=BLUSH)


def eyes_open(draw: ImageDraw.ImageDraw, pupils: str = INK) -> None:
    for cx in (205, 305):
        draw.ellipse((cx - 30, 215, cx + 30, 275), fill=WHITE, outline=BODY_DARK, width=4)
        draw.ellipse((cx - 13, 232, cx + 13, 258), fill=pupils)
        draw.ellipse((cx - 7, 234, cx + 2, 243), fill=WHITE)


def eyes_closed(draw: ImageDraw.ImageDraw) -> None:
    for cx in (205, 305):
        draw.arc((cx - 28, 222, cx + 28, 266), 10, 170, fill=INK, width=7)


def smile(draw: ImageDraw.ImageDraw, wide: int = 34) -> None:
    draw.arc((256 - wide, 285, 256 + wide, 335), 15, 165, fill=INK, width=7)


def flat_mouth(draw: ImageDraw.ImageDraw) -> None:
    draw.line((230, 315, 282, 315), fill=INK, width=7)


def label(draw: ImageDraw.ImageDraw, text: str) -> None:
    f = font(28)
    box = draw.textbbox((0, 0), text, font=f)
    w = box[2] - box[0]
    draw.rounded_rectangle((256 - w / 2 - 14, 382, 256 + w / 2 + 14, 430), radius=24,
                           fill=(15, 36, 55, 220))
    draw.text((256 - w / 2, 390), text, font=f, fill=WHITE)


def sparkle(draw: ImageDraw.ImageDraw, x: int, y: int, r: int, color: str = "#ffe9a8") -> None:
    draw.polygon([(x, y - r), (x + r * .32, y - r * .32), (x + r, y), (x + r * .32, y + r * .32),
                  (x, y + r), (x - r * .32, y + r * .32), (x - r, y), (x - r * .32, y - r * .32)], fill=color)


def heart(draw: ImageDraw.ImageDraw, x: int, y: int, r: int, color: str) -> None:
    draw.ellipse((x - r, y - r, x, y + r * .35), fill=color)
    draw.ellipse((x, y - r, x + r, y + r * .35), fill=color)
    draw.polygon([(x - r, y + r * .05), (x + r, y + r * .05), (x, y + r * 1.15)], fill=color)


def make_sticker(kind: str) -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    base(d)
    if kind == "happy":
        eyes_open(d)
        smile(d, 40)
        for x, y, r in ((92, 150, 18), (438, 190, 13), (410, 110, 9)):
            sparkle(d, x, y, r)
        label(d, "开心")
    elif kind == "comfort":
        eyes_closed(d)
        smile(d, 30)
        # 两只小鳍抱过来
        d.arc((115, 235, 240, 350), 250, 80, fill=BODY_DARK, width=9)
        d.arc((272, 235, 397, 350), 100, 290, fill=BODY_DARK, width=9)
        heart(d, 420, 145, 26, "#ff8eb6")
        label(d, "抱抱")
    elif kind == "sleepy":
        eyes_closed(d)
        d.arc((238, 305, 274, 330), 200, 340, fill=INK, width=5)
        label(d, "困困")
        f = font(54)
        d.text((390, 150), "Z", font=f, fill="#9bd6ff")
        d.text((432, 105), "z", font=font(34), fill="#9bd6ff")
    elif kind == "speechless":
        for cx in (205, 305):
            d.ellipse((cx - 12, 235, cx + 12, 259), fill=INK)
        flat_mouth(d)
        for i, x in enumerate((345, 375, 405)):
            d.ellipse((x, 210 - i * 8, x + 9, 219 - i * 8), fill="#7c9bb5")
        label(d, "无语")
    elif kind == "angry":
        d.line((170, 205, 230, 222), fill=INK, width=9)
        d.line((340, 205, 280, 222), fill=INK, width=9)
        for cx in (205, 305):
            d.ellipse((cx - 20, 235, cx + 20, 260), fill=WHITE, outline=BODY_DARK, width=3)
            d.ellipse((cx - 8, 240, cx + 8, 256), fill=INK)
        d.arc((228, 300, 284, 330), 200, 340, fill=INK, width=6)
        # 怒气符号
        for ang in range(0, 360, 45):
            a = math.radians(ang)
            d.line((430 + math.cos(a) * 10, 160 + math.sin(a) * 10,
                    430 + math.cos(a) * 28, 160 + math.sin(a) * 28), fill="#e64d66", width=6)
        label(d, "生气")
    elif kind == "shy":
        eyes_open(d)
        for cx in (205, 305):
            d.ellipse((cx - 42, 285, cx + 42, 330), fill="#ffc0d5")
        d.arc((238, 300, 274, 322), 200, 340, fill=INK, width=5)
        for x, y, r in ((95, 120, 12), (420, 120, 9)):
            sparkle(d, x, y, r, "#ffc4d9")
        label(d, "害羞")
    elif kind == "love":
        for cx in (205, 305):
            d.ellipse((cx - 30, 215, cx + 30, 275), fill=WHITE, outline=BODY_DARK, width=4)
            heart(d, cx, 226, 17, "#ff6f9f")
        smile(d, 30)
        for x, y, r in ((96, 150, 20), (425, 200, 16), (392, 105, 10)):
            heart(d, x, y, r, "#ff8eb6")
        label(d, "喜欢")
    elif kind == "thinking":
        eyes_open(d)
        flat_mouth(d)
        d.arc((350, 250, 430, 330), 230, 330, fill=INK, width=6)
        f = font(64)
        d.text((420, 135), "?", font=f, fill="#ffd36e")
        label(d, "想想")
    return img


MANIFEST = [
    {"name": "happy", "label": "开心", "file": "happy.png", "desc": "尾巴翘起来，眼睛发亮"},
    {"name": "comfort", "label": "抱抱", "file": "comfort.png", "desc": "张开小鳍，靠过来"},
    {"name": "sleepy", "label": "困困", "file": "sleepy.png", "desc": "眼睛闭上，冒 Z"},
    {"name": "speechless", "label": "无语", "file": "speechless.png", "desc": "平嘴，旁边一排省略点"},
    {"name": "angry", "label": "生气", "file": "angry.png", "desc": "眉毛竖起来，冒怒气"},
    {"name": "shy", "label": "害羞", "file": "shy.png", "desc": "脸红，冒粉色星星"},
    {"name": "love", "label": "喜欢", "file": "love.png", "desc": "心形眼睛，冒爱心"},
    {"name": "thinking", "label": "想想", "file": "thinking.png", "desc": "歪嘴，冒问号"},
]


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    for item in MANIFEST:
        img = make_sticker(item["name"])
        img.save(ROOT / item["file"])
    (ROOT / "manifest.json").write_text(json.dumps(MANIFEST, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(f"generated {len(MANIFEST)} stickers in {ROOT}")


if __name__ == "__main__":
    main()
