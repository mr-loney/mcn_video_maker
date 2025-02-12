#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
示例：使用 Pillow 生成一张包含 12 行预览的图像，
每行文字使用 TITLE_COLOR_PRESETS 对应的 (textColor, strokeColor)。
文字含描边，让你可直接看到最直观的撞色效果。
"""

import os
from PIL import Image, ImageDraw, ImageFont

# 12 组配色 => (textColor, strokeColor)
TITLE_COLOR_PRESETS = [
    ("#ffffffff", "#ffff0000"),  # 1. 白字 + 红描边
    ("#ffffff00", "#ffff00ff"),  # 2. 亮黄 + 粉紫描边
    ("#ffff7f50", "#ff8b4513"),  # 3. 珊瑚 + 巧克力描边
    ("#fffffacd", "#ffff4500"),  # 4. 柠檬肉色 + 橙红描边
    ("#ff7ffb58", "#ff58834c"),  # 5. 淡绿 + 深绿色描边
    ("#ffa0a0ff", "#ff202070"),  # 6. 淡紫 + 蓝紫描边
    ("#fffa8072", "#ff8b0000"),  # 7. 沙尔蒙 + 深红描边
    ("#ff00ff7f", "#ff006400"),  # 8. 青柠 + 深绿描边
    ("#ffdaa520", "#ff8b4513"),  # 9. 金麒麟 + 巧克力描边
    ("#ffadff2f", "#ff556b2f"),  # 10. 黄绿 + 深橄榄描边
    ("#ffffc0cb", "#ffff1493"),  # 11. 粉色 + 深粉描边
    ("#ffffffe0", "#ffff00ff"),  # 12. 乳白 + 粉紫描边
]

def hex_to_rgbA(hexcolor):
    """
    将 #AARRGGBB 或 #RRGGBB 转成 (R, G, B, A)，Pillow可用。
    如 "#ffa0a0ff" => (160, 160, 255, 255)
    如 "#ffffff"   => (255, 255, 255, 255)
    """
    hexcolor = hexcolor.lstrip("#")
    length = len(hexcolor)
    if length == 6:  # RRGGBB
        R = int(hexcolor[0:2], 16)
        G = int(hexcolor[2:4], 16)
        B = int(hexcolor[4:6], 16)
        A = 255
    elif length == 8:  # AARRGGBB
        A = int(hexcolor[0:2], 16)
        R = int(hexcolor[2:4], 16)
        G = int(hexcolor[4:6], 16)
        B = int(hexcolor[6:8], 16)
    else:
        # 默认白色
        R, G, B, A = (255, 255, 255, 255)
    return (R, G, B, A)

def draw_text_with_stroke(draw, xy, text, font, textColor, strokeColor, stroke_width=3):
    """
    在 Pillow ImageDraw 中绘制带描边的文字。
    :param draw: ImageDraw对象
    :param xy: (x, y) 文字左上角坐标
    :param text: 文本
    :param font: ImageFont
    :param textColor: (R, G, B, A) 文字颜色
    :param strokeColor: (R, G, B, A) 描边颜色
    :param stroke_width: 描边宽度（像素）
    """
    x, y = xy
    # 在 8 个方向 + 中心点绘制 stroke_width 范围，简单粗暴
    # 也可使用更复杂的环绕, 这里简单写
    for dx in range(-stroke_width, stroke_width+1):
        for dy in range(-stroke_width, stroke_width+1):
            dist = abs(dx) + abs(dy)
            if dist <= stroke_width:
                draw.text((x+dx, y+dy), text, font=font, fill=strokeColor)
    # 最后绘制正文
    draw.text((x, y), text, font=font, fill=textColor)

def main():
    # 每行高度
    line_height = 80
    # 图像宽度
    img_width = 1000
    # 共有 n 组
    n = len(TITLE_COLOR_PRESETS)
    # 整个图像高度
    img_height = line_height * n

    # 创建图像(黑色背景)
    img = Image.new("RGBA", (img_width, img_height), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    # 载入字体，可以改成你系统中的某个字体文件
    # Windows示例: "C:/Windows/Fonts/Arial.ttf"
    # MacOS示例: "/System/Library/Fonts/Supplemental/Arial.ttf"
    # 你可以把它放到脚本目录下"fonts/xxx.ttf"
    font_path = "/System/Library/Fonts/Supplemental/Arial.ttf"
    if not os.path.isfile(font_path):
        # 根据实际情况再fallback
        pass
    font = ImageFont.truetype(font_path, 40)

    # 依次绘制 12 行
    for i, (textHex, strokeHex) in enumerate(TITLE_COLOR_PRESETS):
        textColor = hex_to_rgbA(textHex)
        strokeColor = hex_to_rgbA(strokeHex)

        # 行文字 => "Line {i+1}: textHex vs strokeHex"
        text = f"Line{i+1}  (Text: {textHex}, Stroke: {strokeHex})"

        x = 50
        y = i * line_height + 10

        draw_text_with_stroke(draw, (x, y), text, font, textColor, strokeColor, stroke_width=3)

    # 输出
    outpath = "title_color_preview.png"
    img.save(outpath)
    print(f"已生成预览图: {outpath}")

if __name__ == "__main__":
    main()