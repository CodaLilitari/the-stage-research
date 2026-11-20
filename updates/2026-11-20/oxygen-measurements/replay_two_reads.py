"""Enclose a two-stage instrument contrast over continuous hypothetical parameter ranges."""
import json
from decimal import Decimal, localcontext


def replay():
    d = Decimal
    with localcontext() as context:
        context.prec = 55
        width, shift, weight = d(".020"), d(".010"), d(".353")
        early, late = d(".08"), d(".28")
        # Decimal.exp uses correctly rounded half-even results. Enclose arithmetic at
        # 55 significant digits by expanding bounds by 1e-40. In these boxes each
        # divisor >= .02, |intermediates| < 1e3 and there are <20 operations per bound.
        pad = d("1e-40")
        def box(a, b):
            gain_low = a/width*((width/b).exp()-1)*(-shift/a).exp()*d(".98")-pad
            gain_high = b/width*((width/a).exp()-1)*(shift/a).exp()*d("1.02")+pad
            response_low = (-late/a).exp()-weight*(-early/b).exp()-pad
            response_high = (-late/b).exp()-weight*(-early/a).exp()+pad
            products = [g*z for g in (gain_low, gain_high) for z in (response_low, response_high)]
            offset_limit = (1-weight)*d(".01")
            return min(products)-offset_limit-pad, max(products)+offset_limit+pad
        def cover(first, last):
            a, b = d(first), d(last)
            increment = (b-a)/4096
            boxes = [box(a+i*increment, a+(i+1)*increment) for i in range(4096)]
            return min(lo for lo, _ in boxes), max(hi for _, hi in boxes)
        fast = cover(".128", ".192")
        slow = cover(".2304", ".3456")
        # Each hypothetical trace may use independent additive errors in both reads.
        radius = d(".008")*(1+weight)
        separation = slow[0]-radius-(fast[1]+radius)
        threshold = (slow[0]+fast[1])/2
        if not (separation > d(".01172") and fast[1]+radius < threshold < slow[0]-radius):
            raise ArithmeticError("Classification certificate failed")
        return {"fast_noiseless": list(map(str,fast)), "slow_noiseless": list(map(str,slow)),
                "decision_threshold": str(threshold), "guaranteed_gap_after_noise": str(separation)}


if __name__ == "__main__":
    print(json.dumps(replay(), indent=2))
