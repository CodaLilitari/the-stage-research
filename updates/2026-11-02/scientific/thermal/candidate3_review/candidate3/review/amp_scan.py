#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Gauss pivot amplification of every plan case (candidate 3 review; Claude, Anthropic; diagnostic only).

Usage:  python3 amp_scan.py [--top N]
  THERMAL_CANDIDATE    module to scan   (default ../thermal_contract.py = candidate3/thermal_contract.py)
  THERMAL_SAMPLE_PLAN  plan JSON        (default ../../original/sample_plan.json)
Prints the N largest amplifications with resistances and the guard ratio
GAUSS_CHECK_ERROR_FACTOR * u * amp / agreement_tol_K (the guard fires at ratio >= 1), the per-group
maxima and the overall min/max.  Also runs on candidate 2 (amplification recomputed locally with the
same arithmetic when the module does not report it).  Writes nothing.
"""
import argparse
import importlib.util
import json
import math
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODE = Path(os.environ.get("THERMAL_CANDIDATE", str(HERE.parent / "thermal_contract.py"))).resolve()
PLAN = Path(os.environ.get("THERMAL_SAMPLE_PLAN",
                           str(HERE.parent.parent / "original" / "sample_plan.json"))).resolve()
U = sys.float_info.epsilon / 2.0


def local_amplification(G_HS, G_SA, G_rej):
    """Same arithmetic as candidate 3's gauss_pivot_amplification for the thermal matrix (no pivot swap)."""
    a, b, c, d = G_HS + G_rej, -G_HS, -G_HS, G_HS + G_SA
    fb = (c / a) * b
    d2 = d - fb
    return math.inf if d2 == 0.0 else (abs(d) + abs(fb)) / abs(d2)


def main(argv=None):
    ap = argparse.ArgumentParser(description="pivot amplification scan of a plan")
    ap.add_argument("--top", type=int, default=12)
    args = ap.parse_args(argv)
    spec = importlib.util.spec_from_file_location("thermal_under_scan", str(CODE))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    cfg = json.loads(PLAN.read_text(encoding="utf-8"))
    m.validate_config(cfg)
    tol = cfg["numerics"]["agreement_tol_K"]
    factor = getattr(m, "GAUSS_CHECK_ERROR_FACTOR", 16.0)
    rows = []
    for cond in m.build_shared_conditions(cfg):
        for stack in cfg["stacks"]:
            p = m.resolve_parameters(cfg, cond)
            R = m.assemble_resistances(stack, p)
            G = [m.conductance_W_K(R[k]) for k in ("R_HS_K_W", "R_SA_K_W", "R_rej_K_W")]
            sol = m.solve_two_node(G[0], G[1], G[2], p["P_body"], p["P_sensor"], p["T_amb"], p["T_res"])
            if sol["status"] != "solved":
                continue
            amp = sol.get("gauss_amplification")
            if amp is None:
                amp = local_amplification(G[0], G[1], G[2])
            rows.append((amp, "%s__%s" % (stack["stack_id"], cond["condition_id"]), cond["group"],
                         R["R_HS_K_W"], R["R_SA_K_W"], R["R_rej_K_W"]))
    print("module %s\nplan   %s" % (CODE, PLAN))
    if not rows:
        print("no solved cases")
        return 0
    rows.sort(key=lambda r: (-r[0], r[1]))
    print("%-40s %-28s %10s %10s %10s %10s %12s" % ("case_id", "group", "amp", "R_HS", "R_SA", "R_rej",
                                                     "guard_ratio"))
    for amp, cid, grp, rhs, rsa, rrej in rows[:args.top]:
        print("%-40s %-28s %10.4g %10.5g %10.5g %10.5g %12.3e" % (cid, grp, amp, rhs, rsa, rrej,
                                                                   factor * U * amp / tol))
    groups = {}
    for amp, cid, grp, _rhs, _rsa, _rrej in rows:
        if amp > groups.get(grp, (-1.0, ""))[0]:
            groups[grp] = (amp, cid)
    for grp in sorted(groups):
        print("group max %-28s %10.4g  (%s)" % (grp, groups[grp][0], groups[grp][1]))
    print("solved cases %d; amp min %.4g max %.4g; max guard ratio %.3e (fires at >= 1); "
          "u = %r factor = %r tol = %r" % (len(rows), rows[-1][0], rows[0][0],
                                            factor * U * rows[0][0] / tol, U, factor, tol))
    return 0


if __name__ == "__main__":
    sys.exit(main())
