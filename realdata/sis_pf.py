"""R-Delay 물동량 보정 다층 SIS의 실자료 입자필터(해상 S·육상 L 2층).

엔진(docs/py/rdelay)의 sis·stats 함수를 그대로 쓰고, 장기 자료를 한 번에 흘려 보내는 연속 필터로 돌린다
(엔진의 particle_filter는 전체 경로를 메모리에 담아 3.8년 자료에는 맞지 않는다).
- S: '지연' = 정박지 대기. x_S = 대기 척수 / (대기 + 선석 체류 척수). 관측 H_S ~ 베타-이항, Y_S(2시간 신규 투묘) ~ 음이항.
- L: '지연' = 기준속도의 60% 미만 콘존. 관측 H_L ~ 베타-이항(측정 콘존 수 중 혼잡 수). 교통량 자료가 없어 ξ_L = 1.
- ξ_S = 최근 24시간 총톤수 가중 도착량 / 최근 28일 평균.
- z(로그 전파율 배수)는 로그-OU, 평균 z̄ = f_ω(기상·휴일·태풍). f_ω는 고정시차 평활 E[z|y]로 릿지 학습(train_ai.py와 같은 방식).
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "docs" / "py"))
from rdelay import sis, stats  # noqa: E402

FEAT = ["wind_bsn_max6", "hs_geoje_max6", "offday", "ty_near500"]
FEAT_CENTER = {"wind_bsn_max6": 4.5, "hs_geoje_max6": 1.2, "offday": 0.0, "ty_near500": 0.0}
FEAT_SCALE = {"wind_bsn_max6": 3.0, "hs_geoje_max6": 1.0, "offday": 1.0, "ty_near500": 1.0}


def features(g: pd.DataFrame) -> np.ndarray:
    X = np.zeros((len(g), len(FEAT)))
    for k, c in enumerate(FEAT):
        X[:, k] = (g[c].fillna(FEAT_CENTER[c]).to_numpy() - FEAT_CENTER[c]) / FEAT_SCALE[c]
    return X


def moments(g: pd.DataFrame) -> dict:
    """학습 기간 적률로 정한 기본 모수(β̄_S는 우도 격자로 따로 고른다)."""
    xs = (g["n_wait"] / g["n_present"].clip(lower=1)).mean()
    lam_s = g["anch_2h"].mean() / 2.0                                   # 신규 투묘 /h
    n_s = g["n_present"].mean()
    xl = (g["road_cong"] / g["road_n"].clip(lower=1)).mean()
    return {"x_s": float(xs), "lam_s": float(lam_s), "n_s": float(n_s), "x_l": float(max(xl, 1e-4))}


def params(g_train: pd.DataFrame, beta_s: float, kappa: float, gamma_s: float, gamma_l: float = 0.7) -> dict:
    m = moments(g_train)
    inc = m["lam_s"] / (m["n_s"] * (1 - m["x_s"]))                       # 감수성 선박 1척당 신규 지연률
    eps_s = max(inc - beta_s * m["x_s"], 1e-6)
    eps_l = gamma_l * m["x_l"] / (1 - m["x_l"])
    C = np.array([[1.0, kappa * 0.5], [kappa * 1.0, 1.0]])               # C[i,j]: j → i 영향(S←L 0.5κ, L←S κ)
    return {"beta": np.array([beta_s, 0.05]), "gamma": np.array([gamma_s, gamma_l]), "eps": np.array([eps_s, eps_l]),
            "C": C, "ou_rate": 0.1, "ou_sigma": 0.25, "nb_size": 3.0, "conc": np.array([30.0, 30.0]),
            "x0": np.array([m["x_s"], m["x_l"]])}


def run(g: pd.DataFrame, p: dict, zbar: np.ndarray | None = None, P: int = 512, dt: float = 0.5, seed: int = 1,
        lag_obs: int = 3, return_particles: bool = False) -> dict:
    """g: 2시간 격자(시간순). 각 τ의 필터 요약과 τ−lag 고정시차 평활 z를 돌려준다."""
    rng = np.random.default_rng(seed)
    T = len(g)
    n = 2
    sub = int(round(2.0 / dt))
    xi = np.ones((T, n))
    xi[:, 0] = g["xi_sea"].clip(0.2, 3.0).fillna(1.0).to_numpy()
    zb = np.zeros((T, n)) if zbar is None else zbar
    N = np.stack([g["n_present"].clip(lower=1).to_numpy(), g["road_n"].clip(lower=1).to_numpy()], axis=1).astype(float)
    hs = g["n_wait"].to_numpy()
    ns = g["n_present"].to_numpy()
    ys = g["anch_2h"].to_numpy()
    hl = g["road_cong"].to_numpy()
    nl = g["road_n"].to_numpy()
    beta_bar, gamma, eps, C = p["beta"], p["gamma"], p["eps"], p["C"]
    x0 = p["x0"]
    x = rng.beta(30 * x0, 30 * (1 - x0), size=(P, n))
    z = zb[0][None, :] + p["ou_sigma"] / np.sqrt(2 * p["ou_rate"]) * rng.standard_normal((P, n))
    w = np.full(P, 1.0 / P)
    out = {k: np.full(T, np.nan) for k in ("x_s", "x_l", "z_s", "rd", "p_rd1", "loglik")}
    z_hist = np.zeros((P, lag_obs + 1))
    z_smooth = np.full(T, np.nan)
    decay = np.exp(-p["ou_rate"] * dt)
    sd = p["ou_sigma"] * np.sqrt(-np.expm1(-2 * p["ou_rate"] * dt) / (2 * p["ou_rate"]))
    total = 0.0
    for s in range(T):
        inc = np.zeros(P)
        if s > 0:
            for _ in range(sub):                                     # τ−2h → τ 적분 (입력은 직전 격자 값)
                beta = beta_bar * np.exp(z)
                r0 = sis.new_delay_rate(x, xi[s - 1], beta, eps, C, N[s - 1])[:, 0]
                x = sis.heun_step(x, xi[s - 1], beta, gamma, eps, C, dt)
                z = zb[s][None, :] + (z - zb[s][None, :]) * decay + sd * rng.standard_normal(z.shape)
                r1 = sis.new_delay_rate(x, xi[s - 1], beta_bar * np.exp(z), eps, C, N[s - 1])[:, 0]
                inc += 0.5 * dt * (r0 + r1)
        ll = np.zeros(P)
        if ns[s] >= 1:
            ll += stats.betabinom_logpmf(np.full(P, hs[s]), np.full(P, ns[s]), np.clip(x[:, 0], 1e-6, 1 - 1e-6), p["conc"][0])
        if s > 0:
            ll += stats.nb_logpmf(np.full(P, ys[s]), np.maximum(inc, 1e-9), p["nb_size"])
        if nl[s] >= 10 and np.isfinite(hl[s]):
            ll += stats.betabinom_logpmf(np.full(P, hl[s]), np.full(P, nl[s]), np.clip(x[:, 1], 1e-6, 1 - 1e-6), p["conc"][1])
        with np.errstate(divide="ignore"):
            w, evid = stats.normalize_log_weights(np.log(w) + ll)
        out["loglik"][s] = evid
        total += evid
        K = sis.next_gen(x, xi[s], beta_bar * np.exp(z), gamma, C)
        rd = sis.spectral_radius(K)
        out["x_s"][s], out["x_l"][s], out["z_s"][s] = w @ x[:, 0], w @ x[:, 1], w @ z[:, 0]
        out["rd"][s], out["p_rd1"][s] = w @ rd, w @ (rd > 1.0)
        z_hist = np.roll(z_hist, -1, axis=1)
        z_hist[:, -1] = z[:, 0]
        if s - lag_obs >= 0:
            z_smooth[s - lag_obs] = w @ z_hist[:, 0]
        if stats.ess(w) < P / 2:
            idx = stats.systematic_resample(w, rng)
            x, z, z_hist = x[idx], z[idx], z_hist[idx]
            w = np.full(P, 1.0 / P)
            lx = np.log(np.clip(x, 1e-6, 1 - 1e-6) / np.clip(1 - x, 1e-6, 1))
            x = 1.0 / (1.0 + np.exp(-(lx + 0.05 * rng.standard_normal(x.shape))))
    for k in range(lag_obs):
        z_smooth[T - lag_obs + k] = np.nan
    out["z_smooth"] = z_smooth
    out["total_loglik"] = float(total)
    return out


def fit_fomega(g: pd.DataFrame, z_label: np.ndarray, lam: float = 5.0) -> dict:
    X = features(g)
    ok = np.isfinite(z_label)
    Xk, yk = X[ok], z_label[ok]
    mx, my = Xk.mean(axis=0), yk.mean()
    A = (Xk - mx).T @ (Xk - mx) + lam * np.eye(X.shape[1])
    coef = np.linalg.solve(A, (Xk - mx).T @ (yk - my))
    return {"features": FEAT, "coef": coef.tolist(), "intercept": float(my - mx @ coef)}


def zbar_from(model: dict | None, g: pd.DataFrame) -> np.ndarray | None:
    if not model:
        return None
    zs = model["intercept"] + features(g) @ np.asarray(model["coef"])
    return np.stack([zs, np.zeros(len(g))], axis=1)


def _grid_job(args):
    g_train, rs, kappa, gamma_s = args
    p = params(g_train, beta_s=rs * gamma_s, kappa=kappa, gamma_s=gamma_s)
    return rs, kappa, run(g_train, p)["total_loglik"]


def calibrate(g_train: pd.DataFrame, gamma_s: float, ratios=(0.0, 0.3, 0.6, 0.9, 1.2), kappas=(0.0, 0.5),
              workers: int = 2) -> dict:
    """학습 기간 우도 격자로 β̄_S(= r·γ_S)와 결합 강도 κ를 고른다."""
    from concurrent.futures import ProcessPoolExecutor
    jobs = [(g_train, r, k, gamma_s) for r in ratios for k in kappas]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        res = list(ex.map(_grid_job, jobs))
    best = max(res, key=lambda t: t[2])
    return {"grid": [{"beta_ratio": r, "kappa": k, "loglik": ll} for r, k, ll in res],
            "best": {"beta_ratio": best[0], "kappa": best[1], "loglik": best[2]}, "gamma_s": gamma_s}
