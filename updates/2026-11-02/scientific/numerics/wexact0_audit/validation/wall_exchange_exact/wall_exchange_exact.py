# SPDX-License-Identifier: Apache-2.0
"""Independent closed-form exchange oracle; no production-model imports.

Coefficients and invariants use rational arithmetic. exp is evaluated with
50-digit Decimal working precision and returned as binary floats; it is not
a certified interval enclosure. Units: mL, umol, mL/s, seconds.
"""
from dataclasses import dataclass
from decimal import Decimal, localcontext
from fractions import Fraction


def rational(value, name, *, positive=False):
    try:
        if isinstance(value,bool):raise ValueError('Boolean is not a quantity')
        result=Fraction(str(value))
    except (ValueError,ZeroDivisionError,TypeError) as exc:
        raise ValueError(f'{name} must be a finite rational quantity') from exc
    if result < 0 or (positive and result == 0):
        raise ValueError(f'{name} has invalid sign')
    return result


def decimal(value):
    return Decimal(value.numerator)/Decimal(value.denominator)


@dataclass(frozen=True)
class ExchangeSolution:
    eq1: Fraction
    eq2: Fraction
    b1: Fraction
    b2: Fraction
    rate: Fraction

    def amounts(self,time):
        time=rational(time,'time')
        if time == 0 or self.rate == 0:
            return float(self.eq1+self.b1),float(self.eq2+self.b2)
        with localcontext() as context:
            context.prec=50
            attenuation=(-decimal(self.rate*time)).exp()
            first=decimal(self.eq1)+decimal(self.b1)*attenuation
            second=decimal(self.eq2)+decimal(self.b2)*attenuation
            return float(first),float(second)


def derive(v1,v2,a10,a20,k):
    """Derive equilibrium and opposite exponential amplitudes algebraically."""
    v1=rational(v1,'v1',positive=True); v2=rational(v2,'v2',positive=True)
    a10=rational(a10,'a10'); a20=rational(a20,'a20'); k=rational(k,'k')
    total=a10+a20
    eq1=total*v1/(v1+v2); eq2=total*v2/(v1+v2)
    amplitude=a10-eq1
    return ExchangeSolution(eq1,eq2,amplitude,-amplitude,k*(1/v1+1/v2))
