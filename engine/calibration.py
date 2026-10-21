"""Conditional constant-gamma baseline; not an exogenous-variable AI model.

Past-episode observations and known beta/coupling are separate from the new
forecast scenario. Synthetic truth is used by the sample generator, never
passed to estimate_gamma(). No field performance is inferred from recovery.
"""
from __future__ import annotations
import numpy as np
from scipy.integrate import simpson


def analytic_land(t, gamma=0.9):
    t = np.asarray(t, dtype=float)
    b = .45-gamma
    d = np.sqrt(b*b+.36)
    positive, negative = (b+d)/1.2, (b-d)/1.2
    z = np.exp(-d*t)
    return positive*(1-z)/(1-positive/negative*z)


def synthetic_observations(mode="clean"):
    if mode not in ("clean", "noise_a", "noise_b"):
        raise ValueError("unknown synthetic observation mode")
    times = np.arange(0, 2.01, .5)
    values = analytic_land(times)
    error = np.array([0, .005, -.005, .005, -.005])
    if mode == "noise_a":
        values += error
    elif mode == "noise_b":
        values -= error
    return [{"time_h": float(t), "sea_fraction": .5, "land_fraction": float(y)}
            for t, y in zip(times, values)]


def estimate_gamma(observations, beta_land=.6, coupling_lp=.5):
    if len(observations) < 3 or len(observations) % 2 != 1:
        raise ValueError("need odd number of >=3 observations for composite Simpson")
    t = np.array([v["time_h"] for v in observations], dtype=float)
    p = np.array([v["sea_fraction"] for v in observations], dtype=float)
    l = np.array([v["land_fraction"] for v in observations], dtype=float)
    if not np.all(np.isfinite(np.concatenate([t,p,l]))):
        raise ValueError("nonfinite observations")
    steps = np.diff(t)
    if np.any(steps <= 0) or not np.allclose(steps, steps[0]):
        raise ValueError("observations must be increasing and equally spaced")
    if np.any((p < 0)|(p > 1)|(l < 0)|(l > 1)):
        raise ValueError("observed fractions must be in [0,1]")
    if not np.isfinite(beta_land+coupling_lp) or beta_land <= 0 or coupling_lp < 0:
        raise ValueError("invalid known calibration coefficients")
    integrated = float(simpson(l, x=t))
    if integrated <= 1e-6:
        raise ValueError("insufficient delayed-state information; no fallback coefficient")
    inflow = beta_land*(1-l)*(l+coupling_lp*p)
    gamma = float((simpson(inflow,x=t)-(l[-1]-l[0]))/integrated)
    if not np.isfinite(gamma) or not 0 < gamma <= 5:
        raise ValueError("estimated recovery outside supported positive range (0,5]")
    return {"gamma_land_per_h":gamma, "integrated_delay_h":integrated,
            "method":"conditional integral identity / composite Simpson",
            "known_beta_land":beta_land, "known_coupling_lp":coupling_lp,
            "training_interval_h":[float(t[0]),float(t[-1])],
            "confidence_interval":None,
            "limitation":"Other coefficients assumed known; not joint identification or trained AI."}


def fit_sample(mode="clean"):
    observations = synthetic_observations(mode)
    fit = estimate_gamma(observations)
    future = []
    for t in (3.,4.):
        future.append({"time_h":t, "synthetic_truth":float(analytic_land(t)),
                       "forecast":float(analytic_land(t,fit["gamma_land_per_h"]))})
    fit.update({"data_type":"synthetic", "mode":mode, "observations":observations,
                "holdout":future,
                "rmse":float(np.sqrt(np.mean([(v["forecast"]-v["synthetic_truth"])**2 for v in future]))),
                "persistence_rmse":float(np.sqrt(np.mean([(observations[-1]["land_fraction"]-v["synthetic_truth"])**2 for v in future]))),
                "application":"Applied to a separate future episode; no backdating decisions."})
    return fit
