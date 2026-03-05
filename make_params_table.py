#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EigenModeSource 파라미터 요약 테이블 이미지 생성 (Pillow 사용)"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

_nanum   = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"
_nanum_b = "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"
OUT_DIR  = Path("/tmp/kb_results")
OUT_DIR.mkdir(parents=True, exist_ok=True)

rows = [
    ("파라미터",             "값",                     "효과"),
    ("eig_band=1",           "TE0 기본 모드",           "가장 많이 사용 (SOI 표준)"),
    ("eig_band=2",           "TE1 1차 고차 모드",       "모드 컨버터, 다중 모드 소자"),
    ("eig_match_freq=True",  "정확한 분산 계산",         "항상 True 권장"),
    ("eig_match_freq=False", "k-벡터 근사",              "모드 순도 저하 가능"),
    ("parity=ODD_Z",         "TE 편광 (Ez 우세)",       "SOI 포토닉스 기본"),
    ("parity=EVEN_Z",        "TM 편광 (Hz 우세)",       "특수 소자 설계"),
    ("parity=ODD_Y",         "Y방향 대칭 활용",          "계산 속도 2배 향상"),
]

W, H   = 1080, 540
PAD    = 28
ROW_H  = 52
TITLE_H = 56
COL_WS = [290, 240, W - 290 - 240 - PAD * 2]

BG      = (15, 17, 23)
HDR_BG  = (79, 70, 229)
ROW_BG1 = (30, 41, 59)
ROW_BG2 = (15, 21, 37)
BORDER  = (51, 65, 85)
WHITE   = (255, 255, 255)
ACCENT  = (196, 181, 253)

img  = Image.new("RGB", (W, H), BG)
draw = ImageDraw.Draw(img)

fn_title  = ImageFont.truetype(_nanum_b, 24)
fn_header = ImageFont.truetype(_nanum_b, 17)
fn_body   = ImageFont.truetype(_nanum,   16)

# 제목
draw.text((W // 2, PAD), "EigenModeSource 파라미터 요약",
          font=fn_title, fill=WHITE, anchor="mt")

# 표
x0 = PAD
y0 = TITLE_H + PAD

for ri, row in enumerate(rows):
    y  = y0 + ri * ROW_H
    bg = HDR_BG if ri == 0 else (ROW_BG1 if ri % 2 == 1 else ROW_BG2)
    draw.rectangle([x0, y, W - PAD, y + ROW_H - 1], fill=bg)

    xc = x0
    for ci, (text, cw) in enumerate(zip(row, COL_WS)):
        fn = fn_header if ri == 0 else fn_body
        fc = ACCENT if ri == 0 else WHITE
        draw.text((xc + 12, y + ROW_H // 2), text,
                  font=fn, fill=fc, anchor="lm")
        # 컬럼 구분선
        if ci < len(COL_WS) - 1:
            draw.line([xc + cw, y, xc + cw, y + ROW_H], fill=BORDER, width=1)
        xc += cw

    # 행 구분선
    draw.line([x0, y, W - PAD, y], fill=BORDER, width=1)

# 테이블 외곽선
draw.rectangle([x0, y0, W - PAD, y0 + len(rows) * ROW_H - 1],
               outline=BORDER, width=1)

path = OUT_DIR / "src_comp_00_params_table.png"
img.save(str(path))
print(f"OK: {path.stat().st_size:,} bytes")
