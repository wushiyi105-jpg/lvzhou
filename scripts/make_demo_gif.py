"""生成 assets/demo.gif：960×600 的终端风演示动图。

只用 Pillow（开发期依赖，不进 requirements）。跑法：
    python scripts/make_demo_gif.py

画面里的分数都是真算出来的：9 个要求技能，2 个完全没有、4 个只在技能栏；
模型给出 6 条改写，0 条凭空加数字。
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

W, H = 960, 600
BG = "#0b0f14"
BAR = "#161b22"
LINE = "#21262d"
GREEN = "#7ee787"
TEXT = "#c9d1d9"
DIM = "#8b949e"
BLUE = "#79c0ff"
YELLOW = "#e3b341"
RED = "#ff7b72"

FONT_PATH = r"C:\Windows\Fonts\msyh.ttc"

LINE_H = 25
MAX_W = W - 56

COLORS = {"cmd": GREEN, "out": TEXT, "dim": DIM, "cite": BLUE, "warn": YELLOW, "bad": RED}


def font(size: int):
    return ImageFont.truetype(FONT_PATH, size)


_MEASURE = ImageDraw.Draw(Image.new("RGB", (1, 1)))


def clip(text: str, size: int = 16) -> str:
    f = font(size)
    if _MEASURE.textlength(text, font=f) <= MAX_W:
        return text
    while text and _MEASURE.textlength(text + "…", font=f) > MAX_W:
        text = text[:-1]
    return text + "…"


def render(rows, cursor_row=None):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 36], fill=BAR)
    for i, color in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        d.ellipse([16 + i * 22, 12, 28 + i * 22, 24], fill=color)
    d.text((92, 9), "lvzhou — 简历对账，改写只准改措辞，不许加事实", font=font(15), fill=DIM)
    d.line([0, 36, W, 36], fill=LINE)

    y = 54
    for idx, (style, text) in enumerate(rows):
        shown = clip(text)
        d.text((26, y), shown, font=font(16), fill=COLORS[style])
        if cursor_row == idx:
            w = _MEASURE.textlength(shown, font=font(16))
            d.rectangle([26 + w + 4, y + 2, 26 + w + 12, y + 19], fill=GREEN)
        y += LINE_H
        if y > H - 16:
            break
    return img


SCRIPT = [
    ("cmd", "> python -m lvzhou match 1 1"),
    ("out", "匹配度 48.9/100 · 2/9 个要求技能简历里完全没有，4 个只在技能栏"),
    ("dim", "  弱 sql     只在技能栏写了，经历里没体现"),
    ("dim", "  有 excel   有，而且在经历里用过"),
    ("bad", "  缺 数据分析 简历里没有"),
    ("dim", "  弱 用户研究 只在技能栏写了"),
    ("dim", "  有 需求分析 有，而且在经历里用过"),
    ("bad", "  缺 大模型   简历里没有"),
    ("warn", "  ! JD 要 CET-6，简历里是 CET-4"),
    ("cmd", "> python -m lvzhou advice 1 1"),
    ("out", "1. 梳理校园社交 App 需求，撰写 12 份需求文档"),
    ("dim", "   去掉「负责」，动词前置"),
    ("out", "2. 使用 Excel 分类用户反馈，提取 340 条有效反馈"),
    ("out", "4. 使用 Python 清洗 2017-2025 年政策文本，完成词频统计"),
    ("warn", "一句话：完全没有 AI / 大模型经验，英语也不满足硬性要求"),
    ("dim", "改写里凭空加的数字：0 个"),
]
TAIL = [
    ("warn", "模型改简历最爱做的事是替你编一段经历：「服务 300 万用户」。"),
    ("dim", "改后的每一句都过核：数字必须在原文里，技能必须原文有或 JD 要，过不了就标出来。"),
]


def build():
    frames, shown = [], []
    for style, text in SCRIPT:
        if style == "cmd":
            for i in range(6, len(text) + 1, 6):
                frames.append(render(shown + [("cmd", text[:i])], cursor_row=len(shown)))
        shown = shown + [(style, text)]
        frames.append(render(shown))
    for _ in range(12):
        frames.append(render(shown + TAIL))

    frames = [f.quantize(colors=20, method=Image.MEDIANCUT) for f in frames]
    os.makedirs("assets", exist_ok=True)
    out = os.path.join("assets", "demo.gif")
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=140, loop=0, optimize=True)
    print(f"ok -> {out}  {len(frames)} 帧  {os.path.getsize(out) / 1024:.1f} KB")


if __name__ == "__main__":
    build()
