"""Time-varying FCFS M(t)/M(t)/m berth model, conditional on an SIS path.

The finite state space is 0..K plus an ABSORBING overflow state, not a
reflecting cap. A tagged ship is inserted exactly once at its arrival.
Post-arrival background ships cannot overtake it in the FIFO queue.
"""
from __future__ import annotations
import math
import numpy as np


def queue_step(distribution, arrival_rate, service_rate, servers: int, dt: float):
    """Uniformization for piecewise-constant rates on this time interval.

    Rows = particles, columns = 0..K and overflow. The generator is applied
    without constructing dense matrices. Poisson-series omitted mass <1e-14.
    """
    q = np.atleast_2d(np.asarray(distribution, dtype=float))
    if q.shape[1] < 3 or servers < 1 or dt < 0:
        raise ValueError("invalid queue shape, servers or interval")
    if np.min(q) < 0 or not np.allclose(q.sum(axis=1), 1, atol=1e-10):
        raise ValueError("queue distribution must be normalized and nonnegative")
    rows = len(q)
    a = np.broadcast_to(np.asarray(arrival_rate, dtype=float), (rows,))
    mu = np.broadcast_to(np.asarray(service_rate, dtype=float), (rows,))
    if np.any(a < 0) or np.any(mu < 0) or not np.all(np.isfinite(a+mu)):
        raise ValueError("queue rates must be finite and nonnegative")
    rate = float(np.max(a + servers*mu))
    if rate == 0 or dt == 0:
        return q.copy()
    lam = rate*dt
    if lam > 10:
        raise ValueError("uniformization interval too large; subdivide time")
    finite = q.shape[1]-1
    deaths = mu[:, None]*np.minimum(np.arange(finite), servers)[None, :]

    def embedded(v):
        birth = v[:, :finite]*a[:, None]/rate
        death = v[:, :finite]*deaths/rate
        nxt = v.copy()
        nxt[:, :finite] -= birth+death
        nxt[:, 1:finite] += birth[:, :-1]
        nxt[:, -1] += birth[:, -1]
        nxt[:, :finite-1] += death[:, 1:]
        return nxt

    term = q.copy()
    probability = math.exp(-lam)
    total_probability = probability
    result = probability*term
    for j in range(1, 200):
        term = embedded(term)
        probability *= lam/j
        result += probability*term
        total_probability += probability
        if 1.0-total_probability < 1e-14 and j > lam:
            break
    else:
        raise ValueError("uniformization did not converge")
    # Add the remaining tiny Poisson tail at its current transition term;
    # error <= omitted mass, preserves total probability including overflow.
    if total_probability < 1:
        result += (1-total_probability)*term
    if result.min() < -1e-14 or not np.allclose(result.sum(axis=1), 1, atol=1e-11):
        raise ValueError("queue mass/positivity check failed")
    return result


def cumulative_integral(times, rates):
    rates = np.asarray(rates, dtype=float)
    times = np.asarray(times, dtype=float)
    increments = .5*(rates[:, :-1]+rates[:, 1:])*np.diff(times)[None, :]
    return np.concatenate([np.zeros((len(rates), 1)), np.cumsum(increments, axis=1)], axis=1)


def invert_hazard(times, cumulative, target, earliest=None):
    """Invert monotone cumulative work; return inf beyond the horizon.

    A zero hazard target during an outage must not move service backwards in
    time, hence earliest is an explicit argument for immediate-start cases.
    """
    if not np.isfinite(target) or target > cumulative[-1]+1e-12:
        return float("inf")
    j = int(np.searchsorted(cumulative, target, side="left"))
    if j == 0:
        value = float(times[0])
    elif j >= len(times):
        return float("inf")
    else:
        delta = cumulative[j]-cumulative[j-1]
        value = float(times[j] if delta <= 0 else times[j-1] +
                      (times[j]-times[j-1])*(target-cumulative[j-1])/delta)
    return max(value, earliest) if earliest is not None else value


def tagged_ship(times, hazards, counts, arrival, servers, rng):
    """Draw conditional FIFO waiting and tagged service completion times.

    When n>=m, n-m+1 service completions are needed before the tagged ship
    starts. In per-server operational time their sum is Gamma(n-m+1,1/m).
    Tagged service itself then needs independent Exp(1) operational work.
    This requires identical non-preemptive servers with common time-varying
    exponential hazards; it is not a general berth scheduling algorithm.
    """
    count = len(counts)
    begin = np.full(count, np.inf)
    finish = np.full(count, np.inf)
    waiting_work = np.zeros(count)
    need = np.maximum(np.asarray(counts)-servers+1, 0)
    active = need > 0
    waiting_work[active] = rng.gamma(need[active], 1.0/servers)
    own_work = rng.exponential(1.0, count)
    for i, n in enumerate(counts):
        if n < 0:  # overflow sample, not treated as a finite queue
            continue
        at_arrival = float(np.interp(arrival, times, hazards[i]))
        start_target = at_arrival + waiting_work[i]
        begin[i] = invert_hazard(times, hazards[i], start_target, earliest=arrival)
        finish[i] = invert_hazard(times, hazards[i], start_target+own_work[i], earliest=arrival)
    return begin, finish


def land_completion(times, work, ready, vehicle_at):
    """No second berth-wait addition: ready already contains the ship result."""
    starts = np.maximum(ready, vehicle_at)
    finishes = np.full(len(ready), np.inf)
    for i, start in enumerate(starts):
        if not np.isfinite(start) or start > times[-1]:
            continue
        target = float(np.interp(start, times, work[i])) + 1.0
        finishes[i] = invert_hazard(times, work[i], target, earliest=float(start))
    return starts, finishes
