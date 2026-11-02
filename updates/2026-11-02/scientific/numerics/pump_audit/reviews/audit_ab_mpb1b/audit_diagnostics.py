# SPDX-License-Identifier: Apache-2.0
"""Audit diagnostics for AB-MPB1B as JSON on stdout (optional caller-supplied output path, created with 'x').

Usage:
    python reviews/audit_ab_mpb1b/audit_diagnostics.py [output.json]

Same environment variables as audit_test_pump_matched.py. Read-only on the frozen files. Written without
execution by Claude (Anthropic) for task pump-matched-audit-001; the numbers it prints are for Red to compare
with run_001/comparison.csv, REPORT.md (8.89e-16, 1.16e-14, 1.12e-14, the 30 s table) and pareto_receipt.json.
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_test_pump_matched as audit  # noqa: E402


def subnormal_probe():
    try:
        got = audit.pump.operating_point(1e308, audit.pump.PumpCaps(1e-10, 1e-300))
    except ValueError as error:
        return {'outcome': 'rejected', 'error': str(error)}
    return {'outcome': 'returned', 'point': got,
            'pressure_relative_gap_to_cap': got['actual_pressure_kpa'] / 1e-10 - 1,
            'realized_power_is_zero': got['actual_hydraulic_power_mw'] == 0}


def main(argv):
    pump = audit.pump
    all_rows = audit.rows()
    throttled = audit.throttled_rows()
    q20 = pump.operating_point(20)['flow_ml_s']
    row_list = []
    for (name, ratio, duration), row in sorted(all_rows.items(), key=lambda item: item[0]):
        res = row['result']
        row_list.append({
            'condition': name, 'resistance_ratio': ratio, 'time_s': duration,
            'flow_ml_s': row['flow'], 'actual_pressure_kpa': row['pressure'],
            'actual_hydraulic_power_mw': row['power'], 'active_constraint': row['active'],
            'distal_wall_concentration': row['distal'], 'minimum_wall_concentration': row['minimum'],
            'distal_is_minimum': row['minimum'] == row['distal'],
            'consumed_umol': row['consumed'], 'net_wall_transfer_umol': row['net'],
            'steps': res['steps'], 'actual_dt': res['actual_dt'], 'exit_bound': res['exit_bound'],
            'max_oxygen_error': res['max_oxygen_error'], 'max_site_error': res['max_site_error'],
            'minimum_seen': res['minimum_seen']})
    pareto, witness = [], []
    for name in audit.NAMES:
        for duration in audit.TIMES:
            obj = {ratio: audit.objectives(all_rows[(name, ratio, duration)], duration) for ratio in audit.RATIOS}
            nd = audit.nondominated(obj)
            pareto.append({'condition': name, 'time_s': duration,
                           'objectives_by_ratio': {str(k): list(v) for k, v in obj.items()},
                           'nondominated_R_over_R0': nd,
                           'dominated_R_over_R0': [r for r in audit.RATIOS if r not in nd]})
            low, high = throttled[(name, duration)], all_rows[(name, 4, duration)]
            witness.append({'condition': name, 'time_s': duration,
                            'throttled_R0_caps_3kPa_3.2mW_objectives': list(audit.objectives(low, duration)),
                            'grid_R4_objectives': list(audit.objectives(high, duration)),
                            'flows_bitwise_equal': low['flow'] == high['flow'],
                            'states_bitwise_identical': low['amounts'] == high['amounts'],
                            'throttled_dominates_R4': audit.dominates(audit.objectives(low, duration),
                                                                      audit.objectives(high, duration))})
    within, penalty = {}, {}
    for ratio in audit.RATIOS:
        for duration in audit.TIMES:
            base = all_rows[('no_sites', ratio, duration)]
            for name in audit.NAMES[1:]:
                key = '%s|R%d|T%d' % (name, ratio, duration)
                within[key] = all_rows[(name, ratio, duration)]['distal'] - base['distal']
                if ratio != 1:
                    penalty[key] = all_rows[(name, ratio, duration)]['distal'] - all_rows[('no_sites', 1, duration)]['distal']
    admitted = sys.modules.get('admitted')
    saved_a = None
    if hasattr(admitted, 'A_ROWS'):
        worst = 0.0
        for a_row in admitted.A_ROWS:
            row = all_rows[(a_row['condition'], 1, a_row['time_s'])]
            worst = max(worst, max(abs(x - y) for x, y in zip(row['amounts'], a_row['final_amounts'])))
        saved_a = {'max_matched_A_state_difference_umol': worst, 'a_row_keys': sorted(admitted.A_ROWS[0].keys())}
    record = {
        'task': 'pump-matched-audit-001',
        'pump_dir': str(audit.PUMP_DIR),
        'a_source': audit.A_SOURCE,
        'python': sys.version,
        'q_at_r20': {'value': q20, 'equals_float_0.4': q20 == 0.4, 'ulps_from_0.4': (q20 - 0.4) / math.ulp(0.4)},
        'operating_points': {str(r): pump.operating_point(r) for r in (20, 40, 45, 80)},
        'rows': row_list,
        'max_oxygen_error_umol': max(r['result']['max_oxygen_error'] for r in all_rows.values()),
        'max_site_error_umol': max(r['result']['max_site_error'] for r in all_rows.values()),
        'minimum_seen': min(r['result']['minimum_seen'] for r in all_rows.values()),
        'saved_A_comparison': saved_a,
        'pareto_groups': pareto,
        'throttled_witness': witness,
        'within_resistance_distal_differences': within,
        'penalty_distal_differences_vs_no_sites_R0': penalty,
        'subnormal_probe_R1e308_D1e-10_P1e-300': subnormal_probe(),
    }
    text = json.dumps(record, indent=1, sort_keys=True)
    if len(argv) > 1:
        with open(argv[1], 'x', encoding='utf-8') as handle:
            handle.write(text + '\n')
    print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
