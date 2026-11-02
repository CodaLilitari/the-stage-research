# SPDX-License-Identifier: Apache-2.0
# Provenance: Coda (Codex Lily), native agent stage_budget_runner.
"""Independent numerical check and deterministic synthetic grid, not production."""
import itertools


def rk4_bound(vessel, bound0, duration, steps):
    # Direct scalar rate, with no production equilibrium/solution helper.
    def rate(b):
        free_concentration = (vessel.oxygen_umol-b)/vessel.volume_ml
        empty = vessel.sites_umol-b
        return vessel.kon_ml_per_umol_s*free_concentration*empty-vessel.koff_per_s*b
    b = bound0
    h = duration/steps
    for _ in range(steps):
        k1 = rate(b)
        k2 = rate(b+h*k1/2)
        k3 = rate(b+h*k2/2)
        k4 = rate(b+h*k3)
        b += h*(k1+2*k2+2*k3+k4)/6
    return b


def grid_cases(vessel_class):
    for v, m, s, rates, fraction, t in itertools.product(
            (0.3, 4.0), (0.0, 0.2, 3.0), (0.0, 0.2, 2.0),
            ((0,0), (0,2), (1,0), (1,.5), (1,100)),
            (0.0, 0.2, 1.0), (0.0, 1e-9, 0.5, 10.0, 1e4)):
        yield vessel_class(v,m,s,*rates), fraction*min(m,s), t
