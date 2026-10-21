"""Log-OU / bootstrap particle-filter primitives.

Beta-binomial: bounded snapshot counts. Negative-binomial: incident events
in a stated observation interval. These observation mappings are additional
R-Delay design assumptions, not field-validated identities.
"""
from __future__ import annotations
import numpy as np
from scipy.special import logsumexp
from scipy.stats import betabinom, nbinom


def ou_step(z, theta, mean, sigma, dt, rng):
    z = np.asarray(z, dtype=float)
    if theta <= 0 or sigma < 0 or dt <= 0:
        raise ValueError("invalid OU parameters")
    decay = np.exp(-theta*dt)
    variance = sigma*sigma*(-np.expm1(-2*theta*dt))/(2*theta)
    return mean + (z-mean)*decay + np.sqrt(variance)*rng.standard_normal(z.shape)


def snapshot_loglik(y: int, n: int, p, concentration: float = 30.0):
    if not isinstance(y, (int, np.integer)) or not isinstance(n, (int, np.integer)):
        raise ValueError("snapshot counts must be integers")
    if n < 1 or y < 0 or y > n or concentration <= 0:
        raise ValueError("invalid snapshot counts or concentration")
    p = np.asarray(p, dtype=float)
    if not np.all(np.isfinite(p)) or np.any((p < 0) | (p > 1)):
        raise ValueError("probability outside [0,1]")
    out = np.full(p.shape, -np.inf)
    middle = (p > 0) & (p < 1)
    out[middle] = betabinom.logpmf(y, n, concentration*p[middle], concentration*(1-p[middle]))
    if y == 0:
        out[p == 0] = 0
    if y == n:
        out[p == 1] = 0
    return out


def incident_loglik(y: int, mean, dispersion: float = 12.0):
    mean = np.asarray(mean, dtype=float)
    if not isinstance(y, (int, np.integer)) or y < 0 or dispersion <= 0:
        raise ValueError("invalid incident count or dispersion")
    if not np.all(np.isfinite(mean)) or np.any(mean < 0):
        raise ValueError("incident mean must be nonnegative")
    out = np.full(mean.shape, -np.inf)
    positive = mean > 0
    out[positive] = nbinom.logpmf(y, dispersion, dispersion/(dispersion+mean[positive]))
    if y == 0:
        out[~positive] = 0
    return out


def update_weights(weights, log_likelihood):
    weights = np.asarray(weights, dtype=float)
    ll = np.asarray(log_likelihood, dtype=float)
    if weights.shape != ll.shape or np.any(weights < 0) or not np.isclose(weights.sum(), 1):
        raise ValueError("invalid particle weights")
    with np.errstate(divide="ignore"):
        logw = np.log(weights) + ll
    evidence = logsumexp(logw)
    if not np.isfinite(evidence):
        raise ValueError("observation is impossible under every particle; no silent reset")
    posterior = np.exp(logw-evidence)
    ess = float(1.0/np.sum(posterior**2))
    return posterior, ess, float(evidence)


def systematic_indices(weights, rng):
    weights = np.asarray(weights, dtype=float)
    if np.any(weights < 0) or not np.isclose(weights.sum(), 1):
        raise ValueError("invalid resampling weights")
    positions = (rng.random()+np.arange(len(weights)))/len(weights)
    cumulative = np.cumsum(weights)
    cumulative[-1] = 1.0  # floating-point summation boundary, not weight clipping
    return np.searchsorted(cumulative, positions, side="right")


def weighted_quantile(values, weights, probabilities=(.1, .5, .9)):
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    order = np.argsort(values)
    cumulative = np.cumsum(weights[order])
    cumulative /= cumulative[-1]
    indices = np.searchsorted(cumulative, probabilities, side="left")
    return values[order[np.minimum(indices, len(order)-1)]]
