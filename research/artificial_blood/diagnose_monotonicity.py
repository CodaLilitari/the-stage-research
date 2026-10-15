"""Post-run diagnosis of PF0's falsified wall-permeability monotonicity assumption."""
import json
import time
from datetime import datetime, timezone
from pf0 import ROOT, CONFIG, simulate, slab, sha, write_json

started = datetime.now(timezone.utc).isoformat()
t0 = time.perf_counter()
rows = []
for depth in [0.0002, 0.0004]:
    for permeability in [0.000005, 0.00005, 0.0002]:
        coupled = simulate(depth, 0.5, permeability, 1, tissue_cells=48, axial_segments=128)
        local = slab(0.2, depth, permeability, CONFIG["source_parameters"], 96)
        rows.append({"depth_um": depth * 1e6, "P_mm_s": permeability * 1e3, "refined_coupled_minimum": coupled["minimum_free_tissue_mol_m3"], "refined_outlet_free": coupled["outlet_free_mol_m3"], "refined_uptake": coupled["uptake_mol_s"], "fixed_lumen_minimum": min(local["c"]), "mass_balance_error": coupled["relative_mass_balance_error"]})
reversals, local_monotonic = [], []
for depth in [200.0, 400.0]:
    group = [r for r in rows if r["depth_um"] == depth]
    reversals.append(group[-1]["refined_coupled_minimum"] < group[-2]["refined_coupled_minimum"])
    local_monotonic.append(all(b["fixed_lumen_minimum"] >= a["fixed_lumen_minimum"] for a, b in zip(group, group[1:])))
result = {"status": "post-run diagnostic, not a prespecified confirmatory test", "started_at_utc": started, "elapsed_seconds": time.perf_counter() - t0, "source_pf0_sha256": sha(ROOT / "pf0.py"), "diagnostic_source_sha256": sha(__file__), "rows": rows, "both_coupled_reversals_reproduced": all(reversals), "fixed_lumen_monotonicity_holds": all(local_monotonic), "interpretation": "The predeclared universal wall-permeability monotonicity expectation was too strong. Improved wall transfer raises local oxygen under a fixed lumen concentration but can increase upstream extraction and lower the downstream minimum in a limited-flow channel. The original failed check remains failed; this diagnostic supplies a mechanism-specific counterexample, not a retroactive pass."}
write_json(ROOT / "monotonicity_diagnostic.json", result)
print(json.dumps(result, indent=2))
