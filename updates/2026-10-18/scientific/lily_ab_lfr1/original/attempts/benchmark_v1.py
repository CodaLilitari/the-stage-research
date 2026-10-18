"""AB-LFR1: linear finite-carrier-release reference and conservative BE.

Lilitari (Lily), 2026-10-17. Original code, MIT licensing preference.
No physiological parameters, clipping, or large-k equilibrium substitution.
Rates alpha and k are in s^-1; t is material transit time in seconds.
State concentrations c,b are mol oxygen / m^3 of circulating suspension.
Python 3.10+ standard library. See DERIVATION.md for derivation and limits.
"""
from __future__ import annotations
import math
from typing import NamedTuple


class Rates(NamedTuple):
    slow: float
    fast: float
    gap: float
    free_slow_weight: float
    free_fast_weight: float


def _nonnegative(**values: float) -> None:
    for name, x in values.items():
        if not math.isfinite(x) or x < 0:
            raise ValueError(f'{name} must be finite and nonnegative')


def decay_rates(alpha: float, k: float, gamma: float) -> Rates:
    """Stable real rates and diagonal weights for the positive propagator."""
    _nonnegative(alpha=alpha, k=k, gamma=gamma)
    kg = k * gamma
    s = alpha + k + kg
    if not math.isfinite(s):
        raise OverflowError('Rate sum exceeds binary64; rescale time or use high precision')
    if s == 0:
        return Rates(0.0, 0.0, 0.0, 1.0, 0.0)
    h = math.fsum([alpha, kg, -k])
    cross = 2.0 * (k * math.sqrt(gamma))
    gap = math.hypot(h, cross)
    if not math.isfinite(gap):
        raise OverflowError('Eigenvalue gap exceeds binary64; rescale time')
    fast = 0.5 * s + 0.5 * gap
    # Product formula avoids subtracting nearly equal S and gap at large k.
    slow = (alpha / fast) * k
    if gap == 0:
        return Rates(slow, fast, 0.0, 0.5, 0.5)
    # Evaluate the small diagonal coefficient without 1-|h|/gap cancellation.
    if h >= 0:
        ws = 2.0 * (k / gap) * (kg / (gap + h))
        wf = 1.0 - ws
    else:
        wf = 2.0 * (k / gap) * (kg / (gap - h))
        ws = 1.0 - wf
    return Rates(slow, fast, gap, ws, wf)


def propagator(alpha: float, k: float, gamma: float, t: float) -> tuple[tuple[float, float], tuple[float, float]]:
    """Return exp(M*t), including the exact repeated-root/Jordan limit.

    No state clipping. Tiny true positive exponentials can naturally underflow
    to binary64 zero. This is representational underflow, not physical depletion.
    """
    _nonnegative(t=t)
    r = decay_rates(alpha, k, gamma)
    if t == 0:
        return ((1.0, 0.0), (0.0, 1.0))
    if r.gap == 0:
        z = r.fast * t
        e = math.exp(-z)
        # gap=0 means k=alpha, gamma=0, or all effective rates vanish.
        off = (k * t) * e if math.isfinite(k * t) else 0.0
        return ((e, off), (0.0, e))
    es, ef = math.exp(-r.slow * t), math.exp(-r.fast * t)
    phi = -math.expm1(-r.gap * t) / r.gap
    off = (k * phi) * es
    e11 = r.free_slow_weight * es + r.free_fast_weight * ef
    e22 = r.free_fast_weight * es + r.free_slow_weight * ef
    return ((e11, off), (gamma * off, e22))


def exact_state(alpha: float, k: float, gamma: float, t: float,
                c0: float = 1.0, b0: float | None = None) -> tuple[float, float]:
    """Apply the analytic propagator. Default inlet is equilibrated b0=gamma*c0.

    An optional independent b0 supports matrix/semigroup diagnostics; physical
    fixture runs in this package always use the equilibrated default.
    """
    if b0 is None:
        b0 = gamma * c0
    _nonnegative(c0=c0, b0=b0)
    e = propagator(alpha, k, gamma, t)
    return (math.fsum([e[0][0]*c0, e[0][1]*b0]),
            math.fsum([e[1][0]*c0, e[1][1]*b0]))


def equilibrium_state(alpha: float, gamma: float, t: float, c0: float = 1.0) -> tuple[float, float]:
    """Separate algebraic k=infinity model, NEVER implemented with a finite k."""
    _nonnegative(alpha=alpha, gamma=gamma, t=t, c0=c0)
    c = c0 * math.exp(-(alpha / (1.0 + gamma)) * t)
    return c, gamma * c


def backward_euler(alpha: float, k: float, gamma: float, t: float,
                   segments: int, c0: float = 1.0) -> dict[str, float]:
    """Conservative end-of-segment BE with independently summed sink/exchange.

    Eliminating b gives c_j=(c_prev+theta*b_prev)/(1+h*alpha+theta*gamma)
    and b_j=b_prev/(1+h*k)+theta*gamma*c_j. All coefficients are nonnegative.
    """
    _nonnegative(alpha=alpha, k=k, gamma=gamma, t=t, c0=c0)
    if isinstance(segments, bool) or not isinstance(segments, int) or segments < 1:
        raise ValueError('segments must be a positive integer')
    h = t / segments
    hk, ha = h * k, h * alpha
    if not math.isfinite(hk + ha + gamma):
        raise OverflowError('BE intermediate exceeds binary64; rescale')
    theta = hk / (1.0 + hk)
    den = 1.0 + ha + theta * gamma
    c, b = c0, gamma * c0
    b0 = b
    sinks, exchanges = [], []
    min_state = min(c, b)
    max_seg = max_free = max_bound = max_rate_cancellation = 0.0
    for _ in range(segments):
        cn = (c + theta*b) / den
        bn = b/(1.0+hk) + theta*gamma*cn
        sink = ha*cn
        exchange = theta*(b-gamma*cn)  # h*k*(b_new-gamma*c_new), stable form
        sinks.append(sink)
        exchanges.append(exchange)
        max_seg = max(max_seg, abs(math.fsum([cn,bn,sink,-c,-b])))
        max_free = max(max_free, abs(math.fsum([cn,-c,sink,-exchange])))
        max_bound = max(max_bound, abs(math.fsum([bn,-b,exchange])))
        # Diagnostic only: direct stiff subtraction can lose rate accuracy.
        max_rate_cancellation = max(max_rate_cancellation,
                                    abs(hk*(bn-gamma*cn)-exchange))
        min_state = min(min_state, cn, bn)
        c, b = cn, bn
    uptake, release = math.fsum(sinks), math.fsum(exchanges)
    return dict(c=c,b=b,uptake=uptake,net_release=release,
                global_residual=math.fsum([c,b,uptake,-c0,-b0]),
                free_residual=math.fsum([c,uptake,-release,-c0]),
                bound_residual=math.fsum([b,release,-b0]),
                max_segment_residual=max_seg,max_free_segment=max_free,
                max_bound_segment=max_bound,min_state=min_state,
                direct_rate_subtraction_error=max_rate_cancellation)


def geometry_to_rates(area_m2: float, exchange_perimeter_m: float, length_m: float,
                      flow_m3_s: float, effective_conductance_m_s: float) -> tuple[float, float]:
    """alpha=p*G/A, T=A*L/Q; p includes ONLY the exchanging wall(s)."""
    _nonnegative(area=area_m2, p=exchange_perimeter_m, length=length_m,
                 flow=flow_m3_s, G=effective_conductance_m_s)
    if area_m2 == 0 or flow_m3_s == 0 or length_m == 0:
        raise ValueError('Positive area, length and throughflow required')
    return exchange_perimeter_m * effective_conductance_m_s / area_m2, area_m2 * length_m / flow_m3_s
