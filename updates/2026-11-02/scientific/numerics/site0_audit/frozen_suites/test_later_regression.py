# SPDX-License-Identifier: Apache-2.0
# Provenance: Coda (Codex Lily), parent independent probe; recovery regression.
from decimal import Decimal, localcontext
import math
import unittest
from site0 import Vessel


def independent_free_state(koff, time_s):
    """Solve F'=k*(1-F)-F^2, F(0)=0, via its positive/negative roots."""
    with localcontext() as context:
        context.prec = 384
        k, t = Decimal(str(koff)), Decimal(str(time_s))
        discriminant = (k*k+4*k).sqrt()
        positive_root = 2*k/(k+discriminant)
        negative_root_magnitude = (k+discriminant)/2
        decay = (-discriminant*t).exp()
        return float(positive_root*(1-decay)/
                     (1+(positive_root/negative_root_magnitude)*decay))


class LaterSaturationRegression(unittest.TestCase):
    def test_saturated_tiny_release_matches_independent_free_state(self):
        for koff in (1e-40, 1e-100, 1e-200):
            for t in (.1, 1, 10):
                with self.subTest(koff=koff, t=t):
                    expected = independent_free_state(koff, t)
                    result = Vessel(1, 1, 1, 1, koff).at(1, t)
                    self.assertGreater(expected, 0)
                    for actual in (result.free_umol, result.empty_umol):
                        self.assertTrue(math.isclose(actual, expected,
                                                    rel_tol=2e-14, abs_tol=0),
                                        (actual, expected, actual/expected))


if __name__ == '__main__': unittest.main()
