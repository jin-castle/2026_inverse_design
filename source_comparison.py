#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Source comparison simulation: Gaussian vs EigenMode
Results saved to /tmp/kb_results/src_comp_*.png

NOTE: Must be docker cp'd as UTF-8 file (not piped via PowerShell heredoc).
"""
import meep as mp
import numpy as np
import matplotlib
matplotlib.use("Agg")

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt

_nanum = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"
fm.fontManager.addfont(_nanum)
_fp    = fm.FontProperties(fname=_nanum)
matplotlib.rcParams["axes.unicode_minus"] = False

from pathlib import Path
import os

OUT_DIR = Path(os.environ.get("RESULTS_DIR", "/tmp/kb_results"))
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Common simulation parameters ─────────────────────────────────────────────
resolution = 20
wvg_width  = 0.5
cell_x, cell_y = 12, 6
fcen = 1 / 1.55
df   = 0.1 * fcen
Si   = mp.Medium(index=3.48)
pml  = [mp.PML(1.0)]
geometry = [mp.Block(mp.Vector3(mp.inf, wvg_width, mp.inf),
                     center=mp.Vector3(), material=Si)]
src_x = -cell_x / 2 + 1.5


def run_sim(label: str, sources: list) -> dict:
    sim = mp.Simulation(
        cell_size       = mp.Vector3(cell_x, cell_y),
        boundary_layers = pml,
        geometry        = geometry,
        sources         = sources,
        resolution      = resolution,
    )
    sim.run(until=200)
    ez  = sim.get_array(center=mp.Vector3(), size=mp.Vector3(cell_x, cell_y), component=mp.Ez)
    eps = sim.get_array(center=mp.Vector3(), size=mp.Vector3(cell_x, cell_y), component=mp.Dielectric)
    hz  = sim.get_array(center=mp.Vector3(), size=mp.Vector3(cell_x, cell_y), component=mp.Hz)
    sim.reset_meep()
    return {"ez": ez, "eps": eps, "hz": hz, "label": label}


def style_ax(ax):
    ax.set_facecolor("#0f1117")
    ax.tick_params(colors="white", labelsize=8)
    for sp in ax.spines.values():
        sp.set_color("#334155")
    ax.set_xlabel("x (um)", fontsize=9, color="white")
    ax.set_ylabel("y (um)", fontsize=9, color="white")


def plot_field(data: dict, ax, comp="ez", note=""):
    field = data[comp].T
    eps   = data["eps"].T
    ext   = [-cell_x/2, cell_x/2, -cell_y/2, cell_y/2]
    ax.imshow(eps,   cmap="binary", alpha=0.3, origin="lower", extent=ext)
    ax.imshow(field, cmap="RdBu",   alpha=0.85, origin="lower", extent=ext,
              vmin=-field.std()*3, vmax=field.std()*3)
    ax.axhline( wvg_width/2,  color="yellow", lw=0.8, ls="--", alpha=0.6)
    ax.axhline(-wvg_width/2,  color="yellow", lw=0.8, ls="--", alpha=0.6)
    title_text = data["label"] + (f"\n{note}" if note else "")
    ax.set_title(title_text, fontsize=10, pad=5, color="white", fontproperties=_fp)
    style_ax(ax)


# ════════════════════════════════════════════════════════════════════════════
# Plot 1: Gaussian Source vs EigenMode Source (TE0)
# ════════════════════════════════════════════════════════════════════════════
print("[1/4] Gaussian vs EigenMode TE0 ...")

src_gauss = [mp.Source(
    mp.GaussianSource(frequency=fcen, fwidth=df),
    component=mp.Ez, center=mp.Vector3(src_x, 0),
    size=mp.Vector3(0, cell_y * 0.8),
)]
src_eig_te0 = [mp.EigenModeSource(
    mp.GaussianSource(frequency=fcen, fwidth=df),
    eig_band=1, eig_match_freq=True, eig_parity=mp.ODD_Z,
    center=mp.Vector3(src_x, 0), size=mp.Vector3(0, cell_y * 0.8),
)]

d_gauss = run_sim("Gaussian Source",        src_gauss)
d_eig0  = run_sim("EigenMode Source (TE0)", src_eig_te0)

fig, axes = plt.subplots(1, 2, figsize=(13, 4.5), facecolor="#0f1117")
plot_field(d_gauss, axes[0], "ez", note="여러 모드 동시 여기 — 방사 손실 발생")
plot_field(d_eig0,  axes[1], "ez", note="TE0 단일 모드만 선택적 여기\neig_band=1, eig_match_freq=True")
fig.suptitle("소스 비교: Gaussian vs EigenMode", color="white",
             fontsize=14, fontproperties=_fp)
plt.tight_layout()
plt.savefig(OUT_DIR / "src_comp_01_gauss_vs_eig.png",
            dpi=110, bbox_inches="tight", facecolor="#0f1117")
plt.close(fig)
print("  -> src_comp_01_gauss_vs_eig.png OK")


# ════════════════════════════════════════════════════════════════════════════
# Plot 2: EigenMode mode_num comparison (TE0 vs TE1)
# ════════════════════════════════════════════════════════════════════════════
print("[2/4] EigenMode TE0 vs TE1 ...")

src_eig_te1 = [mp.EigenModeSource(
    mp.GaussianSource(frequency=fcen, fwidth=df),
    eig_band=2, eig_match_freq=True, eig_parity=mp.ODD_Z,
    center=mp.Vector3(src_x, 0), size=mp.Vector3(0, cell_y * 0.8),
)]
d_eig1 = run_sim("EigenMode (eig_band=2, TE1)", src_eig_te1)

fig, axes = plt.subplots(1, 2, figsize=(13, 4.5), facecolor="#0f1117")
plot_field(d_eig0, axes[0], "ez", note="eig_band=1 -> 기본 모드 (TE0)\n도파관 내 단일 반파장 분포")
plot_field(d_eig1, axes[1], "ez", note="eig_band=2 -> 1차 고차 모드 (TE1)\n도파관 내 마디 1개 분포")
fig.suptitle("mode_num 비교: TE0 vs TE1", color="white",
             fontsize=14, fontproperties=_fp)
plt.tight_layout()
plt.savefig(OUT_DIR / "src_comp_02_mode1_vs_mode2.png",
            dpi=110, bbox_inches="tight", facecolor="#0f1117")
plt.close(fig)
print("  -> src_comp_02_mode1_vs_mode2.png OK")


# ════════════════════════════════════════════════════════════════════════════
# Plot 3: parity ODD_Z (TE) vs EVEN_Z (TM)
# ════════════════════════════════════════════════════════════════════════════
print("[3/4] parity TE vs TM ...")

src_tm = [mp.EigenModeSource(
    mp.GaussianSource(frequency=fcen, fwidth=df),
    eig_band=1, eig_match_freq=True, eig_parity=mp.EVEN_Z,
    center=mp.Vector3(src_x, 0), size=mp.Vector3(0, cell_y * 0.8),
)]
d_tm = run_sim("EigenMode (parity=EVEN_Z, TM)", src_tm)

fig, axes = plt.subplots(1, 2, figsize=(13, 4.5), facecolor="#0f1117")
plot_field(d_eig0, axes[0], "ez", note="parity=ODD_Z (TE 모드)\nEz 성분 — SOI 포토닉스 표준")
plot_field(d_tm,   axes[1], "hz", note="parity=EVEN_Z (TM 모드)\nHz 성분 우세, Ez 약함")
fig.suptitle("parity 비교: TE (ODD_Z) vs TM (EVEN_Z)", color="white",
             fontsize=14, fontproperties=_fp)
plt.tight_layout()
plt.savefig(OUT_DIR / "src_comp_04_te_vs_tm.png",
            dpi=110, bbox_inches="tight", facecolor="#0f1117")
plt.close(fig)
print("  -> src_comp_04_te_vs_tm.png OK")


# ════════════════════════════════════════════════════════════════════════════
# Plot 4: Parameter summary table — Pillow (avoids matplotlib Korean font bug)
# ════════════════════════════════════════════════════════════════════════════
print("[4/4] Parameter summary table (Pillow) ...")
from PIL import Image, ImageDraw, ImageFont as PILFont

_nb = "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"
_nr = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"

rows_tbl = [
    ("파라미터",             "값",                     "효과"),
    ("eig_band=1",           "TE0 기본 모드",           "가장 많이 사용 (SOI 표준)"),
    ("eig_band=2",           "TE1 1차 고차 모드",       "모드 컨버터, 다중 모드 소자"),
    ("eig_match_freq=True",  "정확한 분산 계산",         "항상 True 권장"),
    ("eig_match_freq=False", "k-벡터 근사",              "모드 순도 저하 가능"),
    ("parity=ODD_Z",         "TE 편광 (Ez 우세)",       "SOI 포토닉스 기본"),
    ("parity=EVEN_Z",        "TM 편광 (Hz 우세)",       "특수 소자 설계"),
    ("parity=ODD_Y",         "Y방향 대칭 활용",          "계산 속도 2배 향상"),
]
TW, TH = 1080, 540
PAD = 28; ROW_H = 52; TITLE_H = 56
COL_WS = [290, 240, TW - 290 - 240 - PAD * 2]

timg  = Image.new("RGB", (TW, TH), (15, 17, 23))
tdraw = ImageDraw.Draw(timg)
ft = PILFont.truetype(_nb, 24)
fh = PILFont.truetype(_nb, 17)
fb = PILFont.truetype(_nr, 16)

tdraw.text((TW // 2, PAD), "EigenModeSource 파라미터 요약",
           font=ft, fill=(255, 255, 255), anchor="mt")

x0 = PAD; y0 = TITLE_H + PAD
for ri, row in enumerate(rows_tbl):
    y  = y0 + ri * ROW_H
    bg = (79, 70, 229) if ri == 0 else ((30, 41, 59) if ri % 2 == 1 else (15, 21, 37))
    tdraw.rectangle([x0, y, TW - PAD, y + ROW_H - 1], fill=bg)
    xc = x0
    for ci, (text, cw) in enumerate(zip(row, COL_WS)):
        fn = fh if ri == 0 else fb
        fc = (196, 181, 253) if ri == 0 else (255, 255, 255)
        tdraw.text((xc + 12, y + ROW_H // 2), text, font=fn, fill=fc, anchor="lm")
        if ci < len(COL_WS) - 1:
            tdraw.line([xc + cw, y, xc + cw, y + ROW_H], fill=(51, 65, 85), width=1)
        xc += cw
    tdraw.line([x0, y, TW - PAD, y], fill=(51, 65, 85), width=1)
tdraw.rectangle([x0, y0, TW - PAD, y0 + len(rows_tbl) * ROW_H - 1],
                outline=(51, 65, 85), width=1)

timg.save(str(OUT_DIR / "src_comp_00_params_table.png"))
print("  -> src_comp_00_params_table.png OK")

print(f"\nAll done. Output: {OUT_DIR}")
for f in sorted(OUT_DIR.glob("src_comp_*.png")):
    print(f"  {f.name}: {f.stat().st_size:,} bytes")
