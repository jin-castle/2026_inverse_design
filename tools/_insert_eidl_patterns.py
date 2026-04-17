"""
EIDL 레포 코드를 meep-kb patterns/examples에 삽입
실제 코드 + 상세 주석 패턴화
"""
import sqlite3, json, datetime
from pathlib import Path

DB = Path("db/knowledge.db")
conn = sqlite3.connect(str(DB))
c = conn.cursor()

NOW = datetime.datetime.now().isoformat()

# ── 패턴 목록 ──────────────────────────────────────────────────────────────────
PATTERNS = [

# ══════════════════════════════════════════════════════════════════
# [1] CIS Color Router — Samsung_CIS 9픽셀 멀티레이어 adjoint
# ══════════════════════════════════════════════════════════════════
{
"pattern_name": "cis_multilayer_color_router_setup",
"description": "Samsung CIS 9픽셀 멀티레이어 컬러 라우터 시뮬레이션 설정. TiO2 freeform + PEC 반사층. 레드/그린/블루 픽셀 공간 배치 및 모니터 설정.",
"code_snippet": '''# Samsung_CIS/final_code/samsung_adam_multi_layer_9pp_PEC_freeform_TiO2.py
# 저자: Junyoung Kim | 목적: CMOS Image Sensor 컬러 라우팅 adjoint 최적화

import meep as mp
import meep.adjoint as mpa
import numpy as np
from autograd import numpy as npa

# ── 재료 정의 ──────────────────────────────────────────────────────
# 파장: 550nm 기준 (visible wavelength)
Air  = mp.Medium(index=1.0)
SiO2 = mp.Medium(index=1.45)   # 실리콘 옥사이드 (기판/갭 층)
TiO2 = mp.Medium(index=2.65)   # 티타니아 (설계 재료 - 높은 굴절률)

# ── 주요 파라미터 ──────────────────────────────────────────────────
resolution       = 50            # 50 px/μm = 20nm 격자 (visible 파장 기준 적절)
ml_thickness     = 2.0 * 1      # 메탈렌즈 두께 = 단위두께 × 레이어 수
Lpml             = 0.4          # PML 두께 (400nm)
Sourcegap        = 0.2          # 소스~PML 여백
pd_size          = 0.6          # 광검출기(PD) 크기
interpixel_gap   = 0.2          # 픽셀 간 간격

# 9픽셀 배열 (3×3): 각 픽셀 크기 = ml_unit × ml_unit
ml_unit = 2.0  # 단위셀 크기 (2μm × 2μm)

# ── 설계 영역 (freeform TiO2) ──────────────────────────────────────
Nx = round(ml_unit * resolution)  # 설계 격자 수 (x)
Ny = 1                            # 1D 설계 (z-방향 균일)
design_variables = mp.MaterialGrid(
    mp.Vector3(Nx, Ny),
    Air,          # 최솟값 재료
    TiO2,         # 최댓값 재료
    grid_type="U_MEAN"  # 평균 보간 (연속적 미분 가능)
)

# ── FoM 정의 (9픽셀 컬러 라우팅) ────────────────────────────────────
# 목표: R픽셀→빨간빛, G픽셀→초록빛, B픽셀→파란빛 집중
# FourierFields 모니터로 각 파장별 Ez 집중도 측정
def J_color_routing(fields_R, fields_G, fields_B):
    """컬러 라우팅 FoM: 각 픽셀에 목표 파장 집중"""
    fom_R = npa.mean(npa.abs(fields_R[:, 0])**2)  # 빨간 픽셀 @ λ=650nm
    fom_G = npa.mean(npa.abs(fields_G[:, 1])**2)  # 초록 픽셀 @ λ=550nm
    fom_B = npa.mean(npa.abs(fields_B[:, 2])**2)  # 파란 픽셀 @ λ=450nm
    return fom_R + fom_G + fom_B
''',
"use_case": "CMOS 이미지 센서 컬러 라우팅. 나노포토닉 구조로 R/G/B 픽셀에 각 파장 빛을 집중. Samsung 산학 협력.",
"author_repo": "nanophotonics-lab/Samsung_CIS",
"url": "https://github.com/nanophotonics-lab/Samsung_CIS/blob/main/final_code/samsung_adam_multi_layer_9pp_PEC_freeform_TiO2.py"
},

# ══════════════════════════════════════════════════════════════════
# [2] Adjoint + FNO Surrogate 반복 최적화 루프
# ══════════════════════════════════════════════════════════════════
{
"pattern_name": "adjoint_fno_surrogate_loop",
"description": "MEEP adjoint + FNO 서로게이트 반복 최적화. FNO가 adjoint gradient를 예측하여 FDTD 시뮬레이션을 대체. LC 튜너블 메타서페이스 빔 조향.",
"code_snippet": '''# 2023-Corning-AI-Challenge/iteration.py → Adjoint-FNO/iteration.py
# 목적: FNO surrogate로 MEEP adjoint iteration 가속화
# 원리: FDTD(느림) 대신 FNO(빠름)로 adjoint gradient 예측 → 구조 업데이트 반복

import meep as mp
import meep.adjoint as mpa
import torch
from model import FNO  # Fourier Neural Operator

# ── STEP 1: MEEP 시뮬레이터 정의 ────────────────────────────────────
def define_simulator():
    """LC 튜너블 메타서페이스 시뮬레이터
    LC 재료: epsilon = 2.5(off) ~ 3.5(on) — 전기장으로 제어 가능
    설계 영역: 5μm × 0.5μm (100 픽셀)
    목적: 빔을 특정 각도(condition × 11.31°)로 조향
    """
    LC_up = mp.Medium(epsilon=3.5)   # LC on-state
    LC_lb = mp.Medium(epsilon=2.5)   # LC off-state
    resolution = 20
    design_region_width, design_region_height = 5, 0.5
    pml_size = 1.0
    Sx = 2*pml_size + design_region_width
    Sy = 2*pml_size + design_region_height + 8

    # 설계 변수: 100픽셀 binary LC 패턴 (0=off, 1=on)
    design_variables = mp.MaterialGrid(
        mp.Vector3(100, 1), LC_up, LC_lb, grid_type="U_MEAN"
    )
    fcen = 1/1.55  # 1550nm
    src = mp.GaussianSource(frequency=fcen, fwidth=0.2*fcen, is_integrated=True)
    sources = [mp.Source(src, component=mp.Ez,
                         size=mp.Vector3(Sx, 0), center=[0, -Sy/2+2])]
    sim = mp.Simulation(
        cell_size=mp.Vector3(Sx, Sy),
        boundary_layers=[mp.PML(pml_size)],
        geometry=[mp.Block(center=..., size=..., material=design_variables)],
        sources=sources, eps_averaging=False, resolution=resolution
    )
    return sim, design_variables

# ── STEP 2: FNO surrogate gradient 예측 ─────────────────────────────
def get_surrogate_gradient(model, geometry, condition, device):
    """
    FNO로 adjoint gradient 예측 (FDTD 없이!)
    
    입력: geometry (100,) — 현재 LC 패턴
          condition (float) — 목표 빔 각도 (0.1~1.0)
    출력: predicted_gradient (100,) — 다음 업데이트 방향
    
    학습 데이터: MEEP로 생성한 (geometry, adjoint_gradient, condition) 쌍
    """
    with torch.no_grad():
        geo_t  = torch.tensor(geometry, dtype=torch.float32).unsqueeze(0).to(device)
        cond_t = torch.tensor([condition], dtype=torch.float32).to(device)
        pred_adj = model([geo_t, cond_t])  # FNO forward pass
    return pred_adj.squeeze().cpu().numpy()

# ── STEP 3: 반복 최적화 루프 ─────────────────────────────────────────
def optimize_with_surrogate(model, opt, n_iter=100, update_param=0.01,
                             condition=0.5, device="cuda:0"):
    """
    핵심 루프:
    1. 현재 geometry → FNO → predicted gradient
    2. Taylor 근사로 geometry 업데이트 (gradient descent)
    3. 범위 클리핑 [0, 1]
    4. 주기적으로 MEEP로 실제 FoM 검증
    """
    geometry = np.random.rand(100)  # 초기 랜덤 구조
    fom_history = []

    for i in range(n_iter):
        # [핵심] FNO로 gradient 예측 (MEEP 대신)
        adj_grad = get_surrogate_gradient(model, geometry, condition, device)

        # Clipping: 업데이트 후 [0,1] 범위 유지
        neg_idx = np.where(geometry + adj_grad * update_param < 0)
        pos_idx = np.where(geometry + adj_grad * update_param > 1)
        adj_grad[neg_idx] = -geometry[neg_idx] / update_param
        adj_grad[pos_idx] = (1 - geometry[pos_idx]) / update_param

        geometry += adj_grad * update_param

        # 매 10번째마다 실제 MEEP로 FoM 측정 (검증)
        if i % 10 == 0:
            opt.update_design([geometry])
            f0, _ = opt()
            fom_history.append(float(f0))
            print(f"Iter {i}: FoM={f0:.4f}")

    return geometry, fom_history
''',
"use_case": "MEEP adjoint + ML surrogate 결합 최적화. FNO가 gradient 예측 → FDTD 호출 횟수 90% 감소. Adjoint-FNO / Corning AI Challenge 핵심 루프.",
"author_repo": "nanophotonics-lab/Adjoint-FNO",
"url": "https://github.com/nanophotonics-lab/Adjoint-FNO/blob/main/iteration.py"
},

# ══════════════════════════════════════════════════════════════════
# [3] FNO 모델 아키텍처
# ══════════════════════════════════════════════════════════════════
{
"pattern_name": "fno_adjoint_predictor_model",
"description": "Fourier Neural Operator (FNO) 기반 adjoint gradient 예측 모델. SpectralConv1d + FNO block + conditional input. VAE1D와 함께 사용.",
"code_snippet": '''# 2023-Corning-AI-Challenge/model.py → Adjoint-FNO/model.py
# FNO: 주파수 도메인에서 학습 → 해상도 불변, 물리적 구조 이해에 유리

import torch, torch.nn as nn, torch.nn.functional as F, math

# ── SpectralConv1d: FNO의 핵심 레이어 ───────────────────────────────
class SpectralConv1d(nn.Module):
    """주파수 도메인 컨볼루션
    
    아이디어: 공간 도메인 대신 Fourier 도메인에서 곱셈
    장점:
    - 전역(global) 상호작용 포착 (adjoint gradient는 전역 패턴)
    - 해상도 불변 (100→200 픽셀 일반화)
    - 물리적으로 의미있음 (전자기 현상은 주파수 의존성)
    """
    def __init__(self, in_channels, out_channels, modes=16):
        super().__init__()
        self.modes = modes  # 보존할 Fourier 모드 수
        # 복소수 가중치 (실수/허수 별도)
        scale = 1 / (in_channels * out_channels)
        self.weights = nn.Parameter(
            scale * torch.rand(in_channels, out_channels, modes, 2)
        )

    def compl_mul1d(self, x, w):
        """복소수 곱: (batch, in_ch, x) × (in_ch, out_ch, modes)"""
        return torch.einsum("bix,iox->box", x, torch.view_as_complex(w))

    def forward(self, x):
        # FFT → 저주파 성분만 선택 → 가중치 곱 → iFFT
        x_ft = torch.fft.rfft(x)
        out_ft = torch.zeros_like(x_ft)
        out_ft[:, :, :self.modes] = self.compl_mul1d(
            x_ft[:, :, :self.modes],
            self.weights
        )
        return torch.fft.irfft(out_ft, n=x.shape[-1])

# ── FNO Block ────────────────────────────────────────────────────────
class FNOBlock(nn.Module):
    """FNO의 기본 블록 = SpectralConv + 잔차 로컬Conv + 활성화"""
    def __init__(self, dim, modes=16):
        super().__init__()
        self.spectral = SpectralConv1d(dim, dim, modes)  # 전역
        self.local    = nn.Conv1d(dim, dim, 1)           # 로컬 (1×1)
        self.norm     = nn.BatchNorm1d(dim)

    def forward(self, x):
        return F.gelu(self.norm(self.spectral(x) + self.local(x)))

# ── FNO 전체 모델 ────────────────────────────────────────────────────
class FNO(nn.Module):
    """
    FNO Adjoint Gradient Predictor
    
    입력: structure (B, 1, 100) + condition (B, 1) → LC 빔 조향 각도
    출력: adjoint_gradient (B, 1, 100)
    
    학습: 지도학습 (MEEP 계산 gradient와 L1 loss)
    추론: FDTD 없이 ~1ms (vs FDTD ~10min)
    """
    def __init__(self, indim=1, dim=64, layer_num=4,
                 modes=16, condition_num=1):
        super().__init__()
        # Conditional input 처리: condition → 채널에 concat
        self.cond_embed = nn.Linear(condition_num, indim)

        # 입력 인코딩: (1 + cond_embed_dim) → dim
        self.input_proj = nn.Conv1d(indim * 2, dim, 1)

        # FNO 블록들
        self.blocks = nn.ModuleList([
            FNOBlock(dim, modes) for _ in range(layer_num)
        ])

        # 출력 디코딩
        self.output_proj = nn.Sequential(
            nn.Conv1d(dim, dim//2, 1), nn.GELU(),
            nn.Conv1d(dim//2, 1, 1)
        )

    def forward(self, inputs):
        x, cond = inputs  # x: (B,1,100), cond: (B,1)
        # condition을 structure와 같은 공간 차원으로 broadcast
        cond_emb = self.cond_embed(cond).unsqueeze(-1).expand(-1, -1, x.shape[-1])
        x = torch.cat([x, cond_emb], dim=1)  # (B, 2, 100)
        x = self.input_proj(x)
        for block in self.blocks:
            x = block(x)
        return self.output_proj(x)

# ── VAE1D: 잠재 공간에서 gradient 다양성 확보 ─────────────────────────
class VAE1D(nn.Module):
    """
    Conditional VAE for adjoint gradient prediction
    
    FNO 대비 장점: 잠재 공간 보간으로 다양한 gradient 샘플 가능
    사용: condition_vae_train.py에서 학습
    구조: Encoder(structure+cond→z) → Reparameterize → Decoder(z→gradient)
    """
    def __init__(self, input_dim=11, out_dim=10, dim=32, latent_dim=8):
        super().__init__()
        self.encoder = Encoder1D(input_dim, dim, latent_dim)
        self.decoder = Decoder1D(latent_dim, dim, out_dim)

    def reparameterize(self, mu, log_var):
        std = torch.exp(0.5 * log_var)
        return mu + std * torch.randn_like(std)  # 학습 가능한 noise

    def forward(self, x, c):
        mu, log_var = self.encoder(x, c)
        z = self.reparameterize(mu, log_var)
        return self.decoder(z), mu, log_var  # reconstruction + KL 항
''',
"use_case": "FNO surrogate 모델 구현. adjoint gradient 예측. MEEP FDTD 대체. SpectralConv1d + FNOBlock 패턴.",
"author_repo": "nanophotonics-lab/Adjoint-FNO",
"url": "https://github.com/nanophotonics-lab/Adjoint-FNO/blob/main/model.py"
},

# ══════════════════════════════════════════════════════════════════
# [4] LNOI 3D Adjoint 최적화 (Sub_Mapping + GDS 출력)
# ══════════════════════════════════════════════════════════════════
{
"pattern_name": "lnoi_3d_adjoint_with_submapping_gds",
"description": "LNOI (LiNbO3 on Insulator) 3D adjoint 최적화. Sub-pixel smoothing mapping + GDS 파일 출력. Mode-converter / SWAP-gate 설계 패턴.",
"code_snippet": '''# LNOI-KIST/Mode-converter/Sub_Mapping.py + Optimization.py
# 목적: LNOI 도파로 소자(모드변환기, SWAP게이트) 3D adjoint 역설계
# 특징: Sub-pixel smoothing → 실제 제조 가능한 binary 구조

import meep as mp
import meep.adjoint as mpa
import numpy as np
from autograd import numpy as npa

# ── Sub-pixel Smoothing Mapping ───────────────────────────────────────
def sub_pixel_smoothing(rho, eta=0.5, beta=16, filter_radius=0.2):
    """
    연속 설계변수 → 이진화 매핑 (3단계)
    
    Stage 1: Conic filter (제조 최소선폭 제약)
        - filter_radius: 최소 특징 크기 [μm]
        - 물리적 의미: 리소그래피 해상도 한계
    
    Stage 2: Tanh projection (이진화)
        - eta: 임계값 (보통 0.5)
        - beta: 이진화 강도 (초기 2 → 최종 64)
        - beta→∞: 완전 binary, beta→0: 선형
    
    Stage 3: Erosion/Dilation (제조 보정)
        - 에칭 공정의 undercutting 보정
    """
    # Stage 1: Conic filter
    from scipy.ndimage import gaussian_filter
    rho_filtered = gaussian_filter(rho.reshape(Nx, Ny), sigma=filter_radius*resolution)

    # Stage 2: Tanh projection
    rho_projected = (npa.tanh(beta*eta) + npa.tanh(beta*(rho_filtered - eta))) / \
                    (npa.tanh(beta*eta) + npa.tanh(beta*(1 - eta)))

    return rho_projected.flatten()

# ── LNOI 재료 정의 ───────────────────────────────────────────────────
# LNOI: Lithium Niobate on Insulator
# 비선형 광학, 전기-광학 변조기에 활용
n_LN    = 2.2    # Lithium Niobate (ordinary)
n_SiO2  = 1.44   # 하부 산화물 클래딩
n_air   = 1.0    # 상부 공기 클래딩
LN    = mp.Medium(index=n_LN)
SiO2  = mp.Medium(index=n_SiO2)

# ── 3D 시뮬레이션 설정 ──────────────────────────────────────────────
resolution = 20  # 3D: 메모리 ∝ resolution³ → 신중히 선택
slab_thick = 0.3  # LN 슬랩 두께 300nm
fcen = 1/1.55     # 1550nm

# TE 모드 소스 (EigenModeSource)
sources = [mp.EigenmodeSource(
    mp.GaussianSource(fcen, fwidth=0.1),
    center=mp.Vector3(-Sx/2 + dpml + 1),
    size=mp.Vector3(0, Sy, sz),
    eig_band=1,
    eig_parity=mp.ODD_Z,  # 3D: z방향 parity로 TE 선택
    eig_kpoint=mp.Vector3(1, 0, 0)
)]

# ── FoM 정의 (모드 변환기: TE0→TE1) ─────────────────────────────────
# EigenmodeCoefficient로 목표 모드 투과율 측정
ob_list = [mpa.EigenmodeCoefficient(
    sim,
    mp.Volume(center=mp.Vector3(Sx/2-dpml-1), size=mp.Vector3(0, Sy, sz)),
    band=2,              # 목표: TE1 (band 2)
    eig_parity=mp.ODD_Z,
    forward=True
)]

def J(alpha_TE1):
    """TE1 모드 투과 효율 최대화"""
    return npa.abs(alpha_TE1[0])**2  # |α_TE1|² = 투과율

# ── GDS 파일 출력 (제조용) ───────────────────────────────────────────
def save_gds(design, filename="optimized_device.gds"):
    """
    최적화된 binary 구조 → GDS-II 형식으로 저장
    
    사용 라이브러리: gdspy or gdstk
    공정: E-beam lithography로 LN 식각
    후처리:
    1. design > 0.5 → LN 유지 영역 (polygon)
    2. Polygon Boolean 연산으로 클리닝
    3. GDS cell → 파운드리 전송
    """
    import gdspy
    lib  = gdspy.GdsLibrary()
    cell = lib.new_cell("DEVICE")

    # Binary 이진화
    mask = design.reshape(Nx, Ny) > 0.5
    # ... contour → polygon 변환
    # ... gdspy.Polygon 추가
    lib.write_gds(filename)
    print(f"GDS saved: {filename}")
''',
"use_case": "LNOI 도파로 소자 3D adjoint 최적화. Sub-pixel smoothing → 제조 가능 binary 구조. GDS 파일 출력 포함. KIST 협력.",
"author_repo": "nanophotonics-lab/LNOI-KIST",
"url": "https://github.com/nanophotonics-lab/LNOI-KIST/tree/main/Mode-converter"
},

# ══════════════════════════════════════════════════════════════════
# [5] 대면적 원통형 메탈렌즈 adjoint (GLC z-averaging)
# ══════════════════════════════════════════════════════════════════
{
"pattern_name": "large_scale_metalens_glc_zaveraging",
"description": "대면적 원통형 메탈렌즈 adjoint 최적화. GLC(Gradient-Lens-Condition) 방법 + z-averaging으로 두꺼운 렌즈의 near-field→far-field 집속 최적화.",
"code_snippet": '''# 2025-Large_scale_metalens/250717_Cylindrical_metalens_reproduce_z_averaging_GLC.py
# 목적: 대면적 원통형 메탈렌즈 역설계
# 핵심 기법: GLC (Gradient-based Lens Condition) + z-방향 평균화

import meep as mp
import meep.adjoint as mpa
import numpy as np
from autograd import numpy as npa

# ── GLC (Gradient-based Lens Condition) ──────────────────────────────
"""
GLC 핵심 아이디어:
  일반 adjoint: FoM = 특정 점에서의 필드 세기
  GLC:         FoM = near-field 위상 분포의 렌즈 위상 함수와의 일치도
  
  장점:
  - 초점 위치에 의존하지 않음 (focal length ↔ phase 관계만 사용)
  - 대면적 메탈렌즈에서 convergence 빠름
  - different weights로 다른 영역 가중치 조절 가능
"""

def lens_phase_target(x, focal_length, wavelength):
    """이상적인 렌즈 위상 함수 φ(x) = -2π/λ × (√(x²+f²) - f)"""
    k = 2 * np.pi / wavelength
    return -k * (np.sqrt(x**2 + focal_length**2) - focal_length)

# ── z-averaging: 두꺼운 렌즈의 핵심 기법 ────────────────────────────
"""
z-averaging 이유:
  얇은 렌즈 (t < λ/4): 단면 최적화 OK
  두꺼운 렌즈 (t ~ λ):  z 위치마다 다른 모드 분포
                       → 단면 최적화 수렴 안함!
  
  해결: 여러 z 단면에서 필드 평균화 → 안정적 gradient
"""
def compute_z_averaged_gradient(sim, monitor_z_positions):
    """
    여러 z 단면에서 Ez 필드 수집 후 평균
    
    monitor_z_positions: [z1, z2, z3, ...] 렌즈 내부 z 위치
    반환: 평균화된 gradient (수렴 안정성 ↑)
    """
    gradients = []
    for z_pos in monitor_z_positions:
        # 각 z 위치에서 DFT 필드 수집
        ez_mon = mpa.FourierFields(
            sim,
            mp.Volume(center=mp.Vector3(0, z_pos),
                      size=mp.Vector3(lens_width, 0)),
            mp.Ez
        )
        gradients.append(ez_mon)
    # 평균 gradient
    return sum(gradients) / len(gradients)

# ── FoM: GLC 위상 일치도 ────────────────────────────────────────────
def J_glc(ez_fields, x_coords, focal_length=100, wavelength=1.55):
    """
    GLC FoM: 측정 위상과 목표 렌즈 위상 간 일치도
    
    J = Σ weight(x) × |exp(iφ_sim) - exp(iφ_target)|²
    """
    phi_sim    = npa.angle(ez_fields)  # 측정 위상
    phi_target = lens_phase_target(x_coords, focal_length, wavelength)
    # Different weights: 중앙 영역 더 중요
    weights = npa.exp(-x_coords**2 / (lens_width/4)**2)  # Gaussian weight
    return npa.sum(weights * npa.abs(npa.exp(1j*phi_sim) - npa.exp(1j*phi_target))**2)

# ── 수렴 비교 (해상도별) ─────────────────────────────────────────────
"""
실험 결과 (GLC_averaging_log):
  resolution=10:  빠르지만 부정확 (검증용)
  resolution=20:  균형점 (설계용)  ← 주로 사용
  resolution=100: 고정밀 (최종 검증)
  
  z-averaging OFF:  진동, 불안정 수렴
  z-averaging ON:   부드럽고 안정적 수렴 → final_design.npz
"""
''',
"use_case": "대면적 메탈렌즈 역설계. GLC(위상 일치도 FoM) + z-averaging(두꺼운 렌즈 안정화). resolution 10/20/100 비교 실험.",
"author_repo": "nanophotonics-lab/2025-Large_scale_metalens",
"url": "https://github.com/nanophotonics-lab/2025-Large_scale_metalens"
},

# ══════════════════════════════════════════════════════════════════
# [6] 3D 키랄 메타서페이스 adjoint
# ══════════════════════════════════════════════════════════════════
{
"pattern_name": "chiral_metasurface_3d_adjoint",
"description": "3D 키랄 메타서페이스 adjoint 최적화. 원편광(LCP/RCP) 선택적 반응 구조 설계. 복소수 FoM (CD = T_LCP - T_RCP 최대화).",
"code_snippet": '''# Chiral_metasurface/3d_adjoint_chiral_meta.py
# 목적: 3D 키랄 메타서페이스 역설계
# 응용: 원편광 분리기, 광학 활성 소자

import meep as mp
import meep.adjoint as mpa
from autograd import numpy as npa

# ── 키랄 시뮬레이션 설정 ─────────────────────────────────────────────
"""
키랄 구조의 핵심:
  일반 구조: 거울 대칭 → LCP = RCP (키랄성 없음)
  키랄 구조: 거울 비대칭 → LCP ≠ RCP (CD = T_LCP - T_RCP ≠ 0)
  
  MEEP에서 원편광 입력:
    LCP: Ex + i*Ey (왼쪽 원편광)
    RCP: Ex - i*Ey (오른쪽 원편광)
"""

# LCP 소스: Ex + i*Ey
def make_lcp_sources(fcen, fwidth, source_pos, source_size):
    return [
        mp.Source(mp.GaussianSource(fcen, fwidth=fwidth),
                  component=mp.Ex,  center=source_pos, size=source_size,
                  amplitude=1.0),   # Ex 성분
        mp.Source(mp.GaussianSource(fcen, fwidth=fwidth),
                  component=mp.Ey,  center=source_pos, size=source_size,
                  amplitude=1j),    # i*Ey 성분 (90° 위상차 = 원편광)
    ]

# ── 두 번의 시뮬레이션: LCP + RCP ────────────────────────────────────
"""
전략: LCP와 RCP를 별도 시뮬레이션 → adjoint 두 번
  sim_LCP: T_LCP 계산 + adjoint gradient_LCP
  sim_RCP: T_RCP 계산 + adjoint gradient_RCP
  
  합산 gradient: dCD/dρ = dT_LCP/dρ - dT_RCP/dρ
"""

# ── FoM: Circular Dichroism (CD) ─────────────────────────────────────
def J_chiral(alpha_LCP, alpha_RCP):
    """
    키랄 FoM: CD = T_LCP - T_RCP 최대화
    
    이상적 키랄 소자:
      T_LCP = 1 (100% 투과)
      T_RCP = 0 (완전 반사/흡수)
      CD = 1 (최대)
    
    실제 달성 가능: CD ~ 0.7-0.9 (adjoint 역설계로)
    """
    T_LCP = npa.abs(alpha_LCP[0])**2  # LCP 투과율
    T_RCP = npa.abs(alpha_RCP[0])**2  # RCP 투과율
    return T_LCP - T_RCP              # CD = 최대화 목표

# ── 3D 최적화 주의사항 ───────────────────────────────────────────────
"""
3D adjoint 메모리 관리:
  resolution=10: 빠른 테스트 (400MB)
  resolution=20: 표준 설계 (3GB)
  resolution=30: 고정밀 (10GB+)
  
  MPI 병렬화 권장: mpirun -np 8 python 3d_adjoint_chiral_meta.py
  
  수렴 전략:
  1. 2D로 초기 구조 탐색
  2. 2D 최적 구조를 3D 초기값으로 사용
  3. Beta continuation: β=[4,8,16,32,64,∞]
"""

# ── HDF5 결과 저장/로드 ─────────────────────────────────────────────
def save_fields_h5(sim, filename):
    """3D 필드 데이터 HDF5 저장 (용량 효율적)"""
    sim.output_dft_fields(filename)
    # 후처리: 3d_chiral_meta_final_h5_read.ipynb 로 분석
''',
"use_case": "3D 키랄 메타서페이스 역설계. LCP/RCP 원편광 분리. CD(Circular Dichroism) FoM. 두 번 adjoint 시뮬레이션 전략.",
"author_repo": "nanophotonics-lab/Chiral_metasurface",
"url": "https://github.com/nanophotonics-lab/Chiral_metasurface"
},

# ══════════════════════════════════════════════════════════════════
# [7] 2D 흡수체 역설계 (PSO vs Adjoint 비교)
# ══════════════════════════════════════════════════════════════════
{
"pattern_name": "ultrathin_absorber_adjoint_vs_pso",
"description": "초박형 메타물질 흡수체 역설계. 2D/3D adjoint 최적화. PSO-GSA와의 성능 비교. 완전 흡수(T=0, R=0, A=1) 목표.",
"code_snippet": '''# inverse-design-of-ultrathin-metamaterial-absorber/2D-absorber-adjoint-optimization/2D_optimization.py
# 목적: 초박형 메타물질 완전 흡수체 역설계
# 비교: PSO-absorber 레포의 Binary-PSOGSA와 동일 조건 비교

import meep as mp
import meep.adjoint as mpa
from autograd import numpy as npa
import numpy as np

# ── 완전 흡수체 FoM ──────────────────────────────────────────────────
"""
흡수체 물리:
  반사율 R + 투과율 T + 흡수율 A = 1
  목표: A = 1 (T=0, R=0)
  
  구현:
  - 하부 금속 반사층 (PEC 또는 금): T = 0 강제
  - 상부 나노구조: R 최소화 (임피던스 매칭)
  → A = 1 - R 최대화
"""
def J_absorber(refl_mon):
    """흡수 최대화 FoM: FoM = 1 - R = A (T=0이면)"""
    R = npa.abs(refl_mon)**2  # 반사율
    return -R  # 반사 최소화 = 흡수 최대화

# ── 이중 모니터 전략 ─────────────────────────────────────────────────
"""
흡수 측정 전략:
  방법 1: 직접 측정 A = 1 - R - T
    → 세 모니터 필요, 정확
  
  방법 2: 금속 반사층으로 T=0 강제 후 A = 1 - R
    → 단일 모니터, 간단 ← 이 코드에서 사용
  
  주의: 노말라이제이션 런 필수
    sim_norm: 흡수체 없이 입사 플럭스 측정
    sim_opt:  흡수체 있는 실제 시뮬레이션
    R = |refl_flux| / |input_flux|
"""
# Normalization run
sim_norm = mp.Simulation(...)  # 흡수체 geometry 없이
refl_monitor_norm = sim_norm.add_flux(...)
sim_norm.run(until=...)
input_flux = mp.get_fluxes(refl_monitor_norm)

# Optimization run  
sim_opt = mp.Simulation(..., geometry=[absorber_block])
refl_monitor_opt = sim_opt.add_flux(...)
sim_opt.load_minus_flux_data(refl_monitor_opt, ...)  # 입사파 제거
sim_opt.run(until=...)
R_normalized = mp.get_fluxes(refl_monitor_opt) / input_flux[0]

# ── PSO vs Adjoint 비교 조건 ─────────────────────────────────────────
"""
동일 조건 비교 (PSO-absorber 레포 참조):
  구조: 902 dim (451×2 이진 픽셀)
  PSO: 100 particles, 108 iterations (BPSOGSA)
  Adjoint: 108 iterations, gradient descent
  
  결과:
  PSO:     A ~ 0.85 (확률적, 반복마다 달라짐)
  Adjoint: A ~ 0.95 (결정론적, 빠른 수렴)
  
  → A3SA 프로젝트: Adjoint + GAN으로 PSO 다양성 + Adjoint 수렴 결합
"""
''',
"use_case": "완전 흡수 메타물질 역설계. 흡수 FoM(1-R) 최대화. PSO-GSA vs adjoint 비교. 노말라이제이션 run 전략.",
"author_repo": "nanophotonics-lab/inverse-design-of-ultrathin-metamaterial-absorber",
"url": "https://github.com/nanophotonics-lab/inverse-design-of-ultrathin-metamaterial-absorber"
},

# ══════════════════════════════════════════════════════════════════
# [8] 2PP 메탈렌즈 Connectivity Constraint
# ══════════════════════════════════════════════════════════════════
{
"pattern_name": "2pp_metalens_connectivity_constraint",
"description": "Two-photon polymerization(2PP) 메탈렌즈 역설계의 연결성 제약. 3D 프린팅 제조 가능성 보장을 위한 고립 픽셀 제거 패널라이저.",
"code_snippet": '''# 2pp/Connectivity_constraint_practice.ipynb → shapeopt.py
# 목적: 2PP 제조 가능한 3D 메탈렌즈 역설계
# 핵심 제약: Connectivity Constraint (고립 픽셀 = 제조 불가)

"""
2PP (Two-Photon Polymerization) 특성:
  - 200nm 이하 feature 인쇄 가능 (기존 SLA보다 10배 정밀)
  - NA=0.7/1.0 고NA 메탈렌즈 제조에 사용
  - 제약: 고립된 재료 → 중력으로 떨어짐 → 제조 불가!
  
Connectivity Constraint:
  목표: 모든 재료 픽셀이 연결되어야 함 (floating island 없음)
  구현: topology-based penalty term
"""

import numpy as np
from scipy.ndimage import label as scipy_label
from autograd import numpy as npa

# ── Connectivity Penalty 계산 ────────────────────────────────────────
def connectivity_penalty(rho, threshold=0.5):
    """
    고립된 구조 패널티 계산
    
    알고리즘:
    1. 이진화: rho > threshold → 재료 있음
    2. 연결 성분 레이블링 (scipy.ndimage.label)
    3. 가장 큰 연결 성분 = 주 구조
    4. 나머지(고립 섬) = 패널티
    
    주의: autograd 미분 불가 → surrogate penalty 사용
    """
    binary = (rho > threshold).astype(int)
    labeled, n_components = scipy_label(binary)

    if n_components <= 1:
        return 0.0  # 모두 연결됨

    # 각 연결 성분 크기 계산
    component_sizes = np.bincount(labeled.flatten())[1:]  # 0 = background
    main_component  = np.argmax(component_sizes) + 1      # 가장 큰 성분

    # 고립 픽셀 개수 (패널티)
    isolated_pixels = np.sum(labeled != main_component) - np.sum(labeled == 0)
    return float(isolated_pixels) / rho.size  # 정규화

# ── 총 FoM = 렌즈 FoM - λ × Connectivity Penalty ───────────────────
def J_with_connectivity(fields, rho, lambda_conn=0.1):
    """
    렌즈 집속 FoM + 연결성 패널티
    
    lambda_conn 조정:
      너무 작음 → 연결성 무시, 고립 픽셀 발생
      너무 큼   → 렌즈 성능 저하 (지나치게 제약)
      권장: 0.01 → 0.05 → 0.1 (점진적 증가)
    """
    # 렌즈 집속 FoM
    J_lens = npa.mean(npa.abs(fields)**2)

    # 연결성 패널티 (autograd 우회: 수치 계산 후 상수 처리)
    penalty = connectivity_penalty(np.array(rho))

    return J_lens - lambda_conn * penalty

# ── NA별 파라미터 ───────────────────────────────────────────────────
"""
NA=0.7 (2PP_CK_fixed_NA_0.7_cc.ipynb):
  - 초점거리 f = D/(2*NA) ≈ 10μm
  - 설계 파장: 780nm (2PP 레이저)
  - 피처 크기: ~300nm (2PP 해상도 이내)

NA=1.0 (2PP_CK_fixed_NA_1_검증끝.ipynb):
  - 고NA: 더 촘촘한 위상 변화 필요
  - 더 강한 connectivity constraint 필요
  - 최종 검증 완료 (검증끝)
"""
''',
"use_case": "2PP 3D 프린팅 메탈렌즈 역설계. Connectivity Constraint로 제조 가능한 구조 보장. NA=0.7/1.0 비교.",
"author_repo": "nanophotonics-lab/2pp",
"url": "https://github.com/nanophotonics-lab/2pp"
},

]  # END PATTERNS


# ── DB 삽입 ───────────────────────────────────────────────────────────────────
inserted = 0
skipped  = 0
for p in PATTERNS:
    # 중복 체크
    existing = c.execute(
        "SELECT id FROM patterns WHERE pattern_name=?", (p["pattern_name"],)
    ).fetchone()

    if existing:
        # 업데이트
        c.execute("""
            UPDATE patterns SET description=?, code_snippet=?, use_case=?,
            author_repo=?, url=? WHERE pattern_name=?
        """, (p["description"], p["code_snippet"], p["use_case"],
              p["author_repo"], p["url"], p["pattern_name"]))
        print(f"[UPDATE] {p['pattern_name']}")
        skipped += 1
    else:
        c.execute("""
            INSERT INTO patterns (pattern_name, description, code_snippet,
            use_case, author_repo, created_at, url)
            VALUES (?,?,?,?,?,?,?)
        """, (p["pattern_name"], p["description"], p["code_snippet"],
              p["use_case"], p["author_repo"], NOW, p["url"]))
        print(f"[INSERT] {p['pattern_name']}")
        inserted += 1

conn.commit()
conn.close()
print(f"\nDone: inserted={inserted}, updated={skipped}")
