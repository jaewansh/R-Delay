"""Original R-Delay SIS, with hours as time and C[i,j] denoting j -> i.

The count equation is preserved even when population sizes differ. No silent
clipping is used to conceal unstable integration. This is not a flow balance
for the number of ships in a queue.
"""
from __future__ import annotations
import numpy as np


def coupling_matrix(kappa: float = 1.0) -> np.ndarray:
    if not np.isfinite(kappa) or not 0 <= kappa <= 3:
        raise ValueError("kappa must be finite and in [0,3]")
    return np.eye(2) + kappa * np.array([[0.0, 0.0], [0.5, 0.0]])


def incidence(x, beta, C, N=(100.0, 100.0)) -> np.ndarray:
    """New-delay intensity, in events/hour, not the change in the stock I."""
    x, beta, C, N = map(np.asarray, (x, beta, C, N))
    return beta * (1.0 - x) * ((x * N) @ C.T)


def rhs(x, beta, gamma, C, N=(100.0, 100.0)) -> np.ndarray:
    N = np.asarray(N, dtype=float)
    if np.any(N <= 0):
        raise ValueError("population sizes must be positive")
    return incidence(x, beta, C, N) / N - np.asarray(gamma) * x


def rk4_step(x, beta, gamma, C, dt: float, N=(100.0, 100.0)) -> np.ndarray:
    if not np.isfinite(dt) or dt <= 0:
        raise ValueError("dt must be positive")
    x = np.asarray(x, dtype=float)
    k1 = rhs(x, beta, gamma, C, N)
    k2 = rhs(x + 0.5 * dt * k1, beta, gamma, C, N)
    k3 = rhs(x + 0.5 * dt * k2, beta, gamma, C, N)
    k4 = rhs(x + dt * k3, beta, gamma, C, N)
    y = x + dt / 6 * (k1 + 2*k2 + 2*k3 + k4)
    if not np.all(np.isfinite(y)) or np.any(y < 0) or np.any(y > 1):
        raise ValueError("SIS integration left [0,1]; reduce the time step")
    return y


def delay_index(x, beta, gamma, C) -> np.ndarray:
    """Spectral radius of diag(beta*(1-x)) C Gamma^-1 for each particle.

    This frozen-state diagnostic is NOT a shipment deadline probability.
    """
    x = np.atleast_2d(np.asarray(x, dtype=float))
    beta = np.broadcast_to(np.asarray(beta, dtype=float), x.shape)
    gamma = np.asarray(gamma, dtype=float)
    if np.any(gamma <= 0):
        raise ValueError("recovery rates must be positive")
    K = (beta*(1-x))[:, :, None] * np.asarray(C)[None, :, :] / gamma[None, None, :]
    return np.max(np.abs(np.linalg.eigvals(K)), axis=1).real
