# SPDX-License-Identifier: Apache-2.0
# Provenance: Coda (Codex Lily), native agents stage_budget_runner and
# stage_site0_recovery. Lily supplied the staged SITE0 specification.
"""Closed-vessel finite-site analytical reference; no transport or empirical fit.

Amounts: micromoles; volume: mL; time: seconds; kon: mL/(micromole second).
Decimal working precision is 96 digits; returned amounts are binary floats.
This is not a certified interval implementation over arbitrary parameter scales.
No state clipping, integration, network access, or filesystem side effects.
"""
from dataclasses import dataclass
from decimal import Decimal, localcontext
import math


def _number(value, name, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(name + ' must be a finite int or float')
    try:
        valid = math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid or value < 0 or (positive and value == 0):
        raise ValueError(name + ' is outside its finite physical domain')
    return Decimal(str(value))


def _decay(x):
    """Return exp(-x), 1-exp(-x), retaining the latter at very small x."""
    if x == 0:
        return Decimal(1), Decimal(0)
    if x < Decimal('0.01'):
        # Taylor terms for 1-exp(-x); terminates at the active precision.
        term = total = x
        n = 1
        while True:
            n += 1
            term *= -x / n
            next_total = total + term
            if next_total == total:
                break
            total = next_total
        return Decimal(1) - total, total
    w = (-x).exp()
    return w, Decimal(1) - w


def _amounts(free, bound, empty):
    values = tuple(float(x) for x in (free, bound, empty))
    if any(not math.isfinite(x) or x < 0 for x in values):
        raise ArithmeticError('Analytical state is not finite and nonnegative')
    return Amounts(*values)


def _roots(m, s, rho):
    """Stable physical root and free/empty complements without cancellation."""
    if rho == 0:
        bound = min(m, s)
        return bound, m-bound, s-bound, abs(m-s)
    d = ((m-s)**2 + 2*rho*(m+s) + rho*rho).sqrt()
    bound = 2*m*s/(m+s+rho+d)
    cf = s-m+rho
    ce = m-s+rho
    free = 2*rho*m/(d+cf) if cf >= 0 else (d-cf)/2
    empty = 2*rho*s/(d+ce) if ce >= 0 else (d-ce)/2
    return bound, free, empty, d


@dataclass(frozen=True)
class Amounts:
    free_umol: float
    bound_umol: float
    empty_umol: float


@dataclass(frozen=True)
class Vessel:
    volume_ml: float
    oxygen_umol: float
    sites_umol: float
    kon_ml_per_umol_s: float
    koff_per_s: float

    def __post_init__(self):
        _number(self.volume_ml, 'volume_ml', positive=True)
        for name in ('oxygen_umol', 'sites_umol', 'kon_ml_per_umol_s', 'koff_per_s'):
            _number(getattr(self, name), name)

    def _parameters(self):
        return tuple(Decimal(str(x)) for x in (
            self.volume_ml, self.oxygen_umol, self.sites_umol,
            self.kon_ml_per_umol_s, self.koff_per_s))

    def at(self, bound0_umol, time_s):
        b0 = _number(bound0_umol, 'bound0_umol')
        t = _number(time_s, 'time_s')
        with localcontext() as context:
            context.prec = 96
            v, m, s, kon, koff = self._parameters()
            if b0 > min(m, s):
                raise ValueError('Initial occupied sites exceed oxygen or sites')
            f0, e0 = m-b0, s-b0
            if t == 0 or (kon == 0 and koff == 0) or min(m, s) == 0:
                return _amounts(f0, b0, e0)
            if kon == 0:
                w, h = _decay(koff*t)
                return _amounts(f0+b0*h, b0*w, e0+b0*h)
            a = kon/v
            if koff == 0 and m == s:
                advance = a*f0*t
                denominator = 1+advance
                # Retain tiny newly bound amounts even when m-free rounds to 0.
                return _amounts(f0/denominator,
                                (b0+m*advance)/denominator, e0/denominator)
            beq, feq, eeq, d = _roots(m, s, koff/a)
            w, h = _decay(a*d*t)
            q = 1-(b0-beq)/d
            equilibrium_weight = q*h
            denominator = w+equilibrium_weight
            if q < 0 or denominator <= 0:
                raise ArithmeticError('Invalid analytical interpolation weights')
            return _amounts((f0*w+feq*equilibrium_weight)/denominator,
                            (b0*w+beq*equilibrium_weight)/denominator,
                            (e0*w+eeq*equilibrium_weight)/denominator)

    def equilibrium(self):
        with localcontext() as context:
            context.prec = 96
            v, m, s, kon, koff = self._parameters()
            if min(m, s) == 0:
                return _amounts(m, Decimal(0), s)
            if kon == 0:
                return None if koff == 0 else _amounts(m, Decimal(0), s)
            bound, free, empty, _ = _roots(m, s, koff/(kon/v))
            return _amounts(free, bound, empty)
