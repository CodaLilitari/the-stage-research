# SPDX-License-Identifier: Apache-2.0
# Provenance: Coda (Codex Lily), native agent stage_budget_runner.
"""Deliberately WRONG models, used only as falsification witnesses."""
from dataclasses import replace
import math
from site0 import Amounts


def omit_volume(vessel, bound0, time_s):
    return replace(vessel, volume_ml=1.0).at(bound0, time_s)


def concentration_as_site_amount(vessel, bound0, time_s):
    return replace(vessel, sites_umol=vessel.sites_umol/vessel.volume_ml).at(bound0,time_s)


def independent_amount_clamp(vessel, bound0, time_s):
    r = (vessel.kon_ml_per_umol_s*(vessel.oxygen_umol-bound0)/vessel.volume_ml
         *(vessel.sites_umol-bound0)-vessel.koff_per_s*bound0)
    b = min(vessel.sites_umol, max(0.0,bound0+time_s*r))
    f = max(0.0, vessel.oxygen_umol-bound0-time_s*r)
    return Amounts(f,b,vessel.sites_umol-b)


def empty_sites_create_oxygen(vessel, bound0, time_s):
    # Wrong pure-release bookkeeping: empty sites are treated as released oxygen.
    b = bound0*math.exp(-vessel.koff_per_s*time_s)
    e = vessel.sites_umol-b
    return Amounts(vessel.oxygen_umol-bound0+e,b,e)
