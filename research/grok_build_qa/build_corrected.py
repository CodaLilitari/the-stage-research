"""Targeted Coda corrections to the frozen Grok Build toy implementation.

Writes a distinct derivative; never edits original.py. No biological calibration.
"""
import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
original = HERE / 'original.py'
assert hashlib.sha256(original.read_bytes()).hexdigest() == '00fd5b98815a22021d58c7cd6801eb7da19f1a8e4e35f98d293bfb1c3b826429'
source = original.read_text(encoding='utf-8')
replacements = {
'hydraulic_power': '''def hydraulic_power(delta_p_pa, q_m3_s):
    """Nonnegative pump power for this toy model; signed pumping is outside scope."""
    return validate_nonnegative("delta_p", delta_p_pa) * validate_nonnegative("flow", q_m3_s)
''',
'delivered_oxygen_mol_s': '''def delivered_oxygen_mol_s(q_m3_s, c_in_mol_m3, c_out_mol_m3):
    q = validate_nonnegative("flow", q_m3_s)
    c_in = validate_nonnegative("c_in", c_in_mol_m3)
    c_out = validate_nonnegative("c_out", c_out_mol_m3)
    if c_out > c_in:
        raise ValueError("c_out exceeds c_in")
    return q * (c_in - c_out)
''',
'_interval_or_empty': '''def _interval_or_empty(q_lo, q_hi):
    # Never turn a physically empty interval into a feasible singleton.
    if math.isnan(q_lo) or math.isnan(q_hi) or q_lo < 0 or q_hi < 0:
        raise ValueError("invalid interval endpoint")
    if math.isinf(q_lo) or q_lo > q_hi:
        return None
    return (q_lo, q_hi)
''',
'gamma_linear': '''def gamma_linear(demand, alpha_max, c_in, eta, p_elec_max, resistance):
    demand = validate_nonnegative("demand", demand)
    c_in = validate_nonnegative("c_in", c_in)
    p_elec_max = validate_nonnegative("p_elec_max", p_elec_max)
    resistance = validate_nonnegative("resistance", resistance)
    eta = validate_efficiency(eta)
    alpha_max = validate_efficiency(alpha_max)
    if demand == 0:
        return math.inf
    if resistance == 0:
        return math.inf if c_in > 0 else 0.0
    if c_in == 0 or p_elec_max == 0:
        return 0.0
    return alpha_max**2 * c_in**2 * eta * p_elec_max / (demand**2 * resistance)
''',
'global_supply_met': '''def global_supply_met(q, c_in, alpha_max, demand):
    q = validate_nonnegative("flow", q)
    c_in = validate_nonnegative("c_in", c_in)
    demand = validate_nonnegative("demand", demand)
    alpha_max = validate_efficiency(alpha_max)
    return alpha_max * q * c_in >= demand
''',
'branch_delivered': '''def branch_delivered(q, phi, c_in, alpha_max, ceiling_mol_s):
    q = validate_nonnegative("flow", q)
    phi = validate_nonnegative("flow fraction", phi)
    if phi > 1:
        raise ValueError("flow fraction must be <= 1")
    c_in = validate_nonnegative("c_in", c_in)
    alpha_max = validate_efficiency(alpha_max)
    ceiling = validate_nonnegative("ceiling", ceiling_mol_s)
    return min(phi * q * alpha_max * c_in, ceiling)
''',
'local_supply_met': '''def local_supply_met(q, phis, c_in, alpha_max, ceilings, demands):
    if len(phis) != len(ceilings) or len(phis) != len(demands):
        raise ValueError("branch arrays differ in length")
    q = validate_nonnegative("flow", q)
    c_in = validate_nonnegative("c_in", c_in)
    alpha_max = validate_efficiency(alpha_max)
    phis = [validate_nonnegative("flow fraction", x) for x in phis]
    ceilings = [validate_nonnegative("ceiling", x) for x in ceilings]
    demands = [validate_nonnegative("demand", x) for x in demands]
    if any(x > 1 for x in phis) or (phis and abs(math.fsum(phis) - 1) > 1e-12):
        raise ValueError("flow fractions must be <=1 and sum to 1")
    # The sum tolerance is dimensionless input-roundoff only. There is no
    # absolute oxygen-rate tolerance that can supply a stagnant branch.
    return all(branch_delivered(q, p, c_in, alpha_max, c) >= d
               for p, c, d in zip(phis, ceilings, demands))
''',
'power_ok_linear': '''def power_ok_linear(q, eta, p_elec_max, resistance):
    q = validate_nonnegative("flow", q)
    eta = validate_efficiency(eta)
    p_elec_max = validate_nonnegative("p_elec_max", p_elec_max)
    resistance = validate_nonnegative("resistance", resistance)
    if p_elec_max == 0 and resistance > 0:
        return q == 0  # Also protects the exact boundary against underflow.
    return electrical_power(linear_delta_p(resistance, q), q, eta) <= p_elec_max
''',
'series_path': '''def series_path(q, c_in, requested_drops, ceilings):
    q = validate_nonnegative("flow", q)
    c_in = validate_nonnegative("c_in", c_in)
    if len(requested_drops) != len(ceilings):
        raise ValueError("series arrays differ in length")
    drops = [validate_nonnegative("drop", x) for x in requested_drops]
    caps = [validate_nonnegative("ceiling", x) for x in ceilings]
    c = c_in
    deliveries, inlets = [], []
    for drop, ceiling in zip(drops, caps):
        inlets.append(c)
        taken = 0.0 if q == 0 else min(drop, c, ceiling / q)
        deliveries.append(q * taken)
        c -= taken
    return {"segment_inlet_mol_m3": inlets, "segment_delivery_mol_s": deliveries,
            "delivered_once_mol_s": math.fsum(deliveries), "end_to_end_mol_s": q * (c_in - c),
            "carrier_capacity_mol_s": q * c_in, "path_outlet_mol_m3": c}
''',
}
lines = source.splitlines(keepends=True)
nodes = {n.name: n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)}
for name in sorted(replacements, key=lambda n: nodes[n].lineno, reverse=True):
    node = nodes[name]
    lines[node.lineno-1:node.end_lineno] = [replacements[name]]
corrected = ''.join(lines)
old = '(q >= interval[0] - 1e-15) and (math.isinf(hi) or q <= hi + 1e-15)'
assert corrected.count(old) == 1
corrected = corrected.replace(old, '(q >= interval[0]) and (math.isinf(hi) or q <= hi)')
corrected = corrected.replace('"screen": "toy_pump_power_vs_oxygen_transport",', '"screen": "toy_pump_power_vs_oxygen_transport",\n        "implementation": "Coda corrected derivative of frozen Grok Build script; original is separate",')
corrected = '# Coda corrected derivative. Original Grok Build derivation/script preserved in original.py.\n' + corrected
ast.parse(corrected)
target = HERE / 'corrected.py'
target.write_text(corrected, encoding='utf-8')
freeze = {'before_first_corrected_execution_utc': datetime.now(timezone.utc).isoformat(),
          'original_sha256': hashlib.sha256(original.read_bytes()).hexdigest(),
          'corrected_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
          'changed_functions': list(replacements), 'other_change': 'Strict sweep membership; derivative attribution',
          'roundoff_policy': 'Strict binary64 inequalities; may conservatively reject a rounded near-boundary point. No dimensioned absolute tolerance may create supply or power. Flow-fraction sum retains dimensionless 1e-12 input tolerance.',
          'limits': 'No arbitrary-precision solver or proof over all finite floating-point inputs; extreme overflow/subnormal behavior is outside declared scientific range. No biological validation.'}
(HERE / 'corrected_freeze.json').write_text(json.dumps(freeze, indent=2)+'\n', encoding='utf-8')
print(json.dumps(freeze))
