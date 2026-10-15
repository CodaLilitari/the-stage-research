#!/usr/bin/env python3
"""Recompute all FL1-R summaries from complete per-episode measurements.

Standard library only. Intervals resample whole synthetic seeds, not time steps.
Secondary contrasts are exploratory, without multiplicity-adjusted inference.
"""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import random
import statistics
from first_leaf import ROOT, load_protocol


def mean(xs):
    return statistics.fmean(xs)


def quantile(xs, q):
    s = sorted(xs)
    z = (len(s) - 1) * q
    i = int(z)
    return s[i] + (z - i) * (s[min(i + 1, len(s) - 1)] - s[i])


def interval(values, cfg):
    rng = random.Random(cfg['inference']['bootstrap_seed'])
    n = len(values)
    boot = [mean(values[rng.randrange(n)] for _ in range(n))
            for _ in range(cfg['inference']['resamples'])]
    return {'mean': mean(values), 'ci95': [quantile(boot, .025), quantile(boot, .975)],
            'n_seeds': n}


def read_rows(out, cfg, profile):
    status = json.loads((out / f'evaluation_{profile}_status.json').read_text())
    assert status['completed'] == status['scheduled_runs'] and not status['failures'], status
    with open(out / f'evaluation_{profile}_episodes.csv', newline='') as f:
        rows = list(csv.DictReader(f))
    expected = cfg['evaluation_seeds']['count'] * len(cfg['algorithms']) * cfg['episodes']
    assert len(rows) == expected, (profile, len(rows), expected)
    index = {}
    for r in rows:
        r['seed'], r['episode'] = int(r['seed']), int(r['episode'])
        r['recovery_tick'] = int(r['recovery_tick']) if r['recovery_tick'] else None
        for k in ['mean_distance', 'early32_distance', 'velocity_mse', 'body_model_error',
                  'final_distance', 'final_within_0_15', 'executed_steps']:
            r[k] = float(r[k])
        key = (r['seed'], r['algorithm'], r['episode'])
        assert key not in index
        index[key] = r
    return index, status


def build(out):
    cfg = load_protocol()
    seeds = list(range(cfg['evaluation_seeds']['first'],
                       cfg['evaluation_seeds']['first'] + cfg['evaluation_seeds']['count']))
    data, statuses, summaries = {}, {}, {}
    for p in cfg['profiles']:
        data[p], statuses[p] = read_rows(out, cfg, p)
        summaries[p] = {}
        for a in cfg['algorithms']:
            rows = [data[p][(s, a, e)] for s in seeds for e in range(cfg['episodes'])]
            phase = [data[p][(s, a, 3)] for s in seeds]
            rec = [r['recovery_tick'] for r in phase if r['recovery_tick'] is not None]
            summaries[p][a] = {
                'early32_first_remap': mean(r['early32_distance'] for r in phase),
                'stable_mean': mean(data[p][(s, a, e)]['mean_distance'] for s in seeds for e in [1, 2]),
                'second_B_early32': mean(data[p][(s, a, 4)]['early32_distance'] for s in seeds),
                'return_A_early32': mean(data[p][(s, a, 5)]['early32_distance'] for s in seeds),
                'overall_mean_distance': mean(r['mean_distance'] for r in rows),
                'overall_velocity_mse': mean(r['velocity_mse'] for r in rows),
                'overall_body_model_error': mean(r['body_model_error'] for r in rows),
                'final_within_0_15_fraction': mean(r['final_within_0_15'] for r in rows),
                'first_remap_recovery_reached_count': len(rec),
                'first_remap_recovery_not_reached_by80_count': len(seeds) - len(rec),
                'first_remap_recovery_median_among_reached': statistics.median(rec) if rec else None,
                'first_remap_recovery_definition': 'First end-of-step tick completing eight consecutive pre-action model-error values <= 0.08; not onset of recovery.'}
    def diff(profile, a, b, eps, metric):
        return [mean(data[profile][(s, a, e)][metric] - data[profile][(s, b, e)][metric]
                     for e in eps) for s in seeds]
    definitions = {
        'primary_cumulative_minus_window': ('primary', 'cumulative', 'window', [3], 'early32_distance'),
        'stable_window_minus_cumulative': ('primary', 'window', 'cumulative', [1, 2], 'mean_distance'),
        'remap_reset_minus_window': ('primary', 'episode_reset', 'window', [3], 'early32_distance'),
        'stable_reset_minus_window': ('primary', 'episode_reset', 'window', [1, 2], 'mean_distance'),
        'second_B_reset_minus_window': ('primary', 'episode_reset', 'window', [4], 'early32_distance'),
        'return_A_cumulative_minus_window': ('primary', 'cumulative', 'window', [5], 'early32_distance'),
        'primary_misaligned_minus_window': ('primary', 'misaligned', 'window', [3], 'early32_distance'),
        'no_delay_cumulative_minus_window': ('no_delay', 'cumulative', 'window', [3], 'early32_distance'),
        'clean_cumulative_minus_window': ('clean', 'cumulative', 'window', [3], 'early32_distance'),
        'stationary_window_minus_cumulative': ('stationary', 'window', 'cumulative', [3], 'early32_distance'),
    }
    contrasts = {name: {**interval(diff(*args), cfg), 'profile': args[0],
                       'difference': f'{args[1]} minus {args[2]}', 'episodes': args[3], 'metric': args[4]}
                 for name, args in definitions.items()}
    g = contrasts['primary_cumulative_minus_window']
    p = contrasts['stable_window_minus_cumulative']
    selected = (g['mean'] >= cfg['design_rule']['minimum_mean_early_gain'] and
                g['ci95'][0] > cfg['design_rule']['paired_95_percent_interval_lower_bound_must_exceed'] and
                p['ci95'][1] <= cfg['design_rule']['maximum_stable_penalty'])
    comparison = {'status': 'not_available'}
    old_path = out / 'attempt01_timeout/evaluation_primary_runs.jsonl'
    if old_path.exists():
        old = [json.loads(l) for l in old_path.read_text().splitlines()]
        new = {(r['seed'], r['algorithm']): r for r in
               (json.loads(l) for l in (out / 'evaluation_primary_runs.jsonl').read_text().splitlines())}
        mismatch = [r for r in old if r != new[(r['seed'], r['algorithm'])]]
        assert not mismatch, 'Interrupted-attempt overlap failed reproducibility'
        comparison = {'status': 'all_retained_completed_receipts_match', 'count': len(old),
                      'unrecorded_in_flight_work': 'unknown; completion receipts were buffered, not a durable start journal'}
    no_delay_equality = {}
    for profile in ['no_delay', 'clean']:
        receipts = [json.loads(l) for l in (out / f'evaluation_{profile}_runs.jsonl').read_text().splitlines()]
        d = {(r['seed'], r['algorithm']): r['trace_sha256'] for r in receipts}
        eq = sum(d[(s, 'window')] == d[(s, 'misaligned')] for s in seeds)
        assert eq == len(seeds)
        no_delay_equality[profile] = {'identical_full_trace_pairs': eq, 'total_pairs': len(seeds)}
    result = {'protocol': cfg['protocol_id'], 'scope': cfg['scope'],
              'evaluation_counts': {'seed_fixtures': len(seeds), 'profiles': len(statuses),
                  'algorithm_trials': sum(s['completed'] for s in statuses.values()),
                  'episodes': sum(len(d) for d in data.values()),
                  'scored_transitions': int(sum(r['executed_steps'] for d in data.values() for r in d.values())),
                  'failures_in_completed_batches': sum(len(s['failures']) for s in statuses.values())},
              'by_profile': summaries, 'paired_contrasts': contrasts,
              'design_rule_passed_within_fixture_family': selected,
              'interrupted_attempt_comparison': comparison, 'no_delay_alignment_identity': no_delay_equality,
              'inference': cfg['inference'], 'statuses': statuses,
              'source_note': 'Analysis authored after data collection to implement the frozen metrics and decision rule; no algorithm/parameter/threshold changes after development.'}
    invariant_path = out / 'invariants.json'
    if invariant_path.exists():
        result['invariants'] = json.loads(invariant_path.read_text())
    (out / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    report = ['# First Leaf FL1-R: executed results', '',
      f"Protocol: `{cfg['protocol_id']}`. Author and local executor: Lilitari. Private synthetic algorithm experiment.", '',
      '## Execution and units', '',
      f"The completed evaluation contains {result['evaluation_counts']['algorithm_trials']:,} six-episode trials and "
      f"{result['evaluation_counts']['scored_transitions']:,} scored transitions. There are 256 independent synthetic seed fixtures, reused in paired algorithm/profile comparisons. Time steps and repeated conditions are not independent replications.", '',
      'The earlier 16-seed development batches are separate. No science-code, parameter, metric, seed, or decision-threshold changes were made after inspecting development outcomes. The local freeze is not independently witnessed preregistration.', '',
      '## First-remap outcome', '',
      'Mean distance to target over the first 32 steps after the first remap, starting one distance unit from the target. Lower is better.', '',
      '| Algorithm | Delay + noise | No delay | No delay or noise | Stationary body |',
      '|---|---:|---:|---:|---:|']
    for a in cfg['algorithms']:
        report.append('| ' + a + ' | ' + ' | '.join(f"{summaries[p][a]['early32_first_remap']:.6f}" for p in cfg['profiles']) + ' |')
    report += ['', '## Frozen design rule', '',
      f"Cumulative minus window: **{g['mean']:.6f}**, paired 95% bootstrap interval **[{g['ci95'][0]:.6f}, {g['ci95'][1]:.6f}]**.", '',
      f"Stable-body penalty, window minus cumulative: **{p['mean']:.6f}**, interval **[{p['ci95'][0]:.6f}, {p['ci95'][1]:.6f}]**.", '',
      f"The frozen rule (gain at least 0.10, gain interval lower bound above zero, stable-penalty upper bound at most 0.05) **{'passes' if selected else 'does not pass'}** within this fixture family.", '',
      '## Other planned contrasts', '', '| Contrast | Mean difference | Paired 95% interval |', '|---|---:|---:|']
    for k, c in contrasts.items():
        report.append(f"| {k} | {c['mean']:.6f} | [{c['ci95'][0]:.6f}, {c['ci95'][1]:.6f}] |")
    report += ['', 'Secondary intervals are exploratory. No familywise correction or claim of general population coverage is made.', '',
      '## Verification and deviations', '',
      f"The first primary batch attempt hit a tool timeout. Its {comparison.get('count', 0):,} retained completed receipts match the entire unchanged rerun. Partial in-flight work is not fully enumerated: the original batch writer was completion-based and buffered. The scored rerun is complete; the interrupted attempt is preserved and is not additional independent evidence.", '',
      'The wrong-time action-assignment ablation becomes byte-identical to the aligned learner when observation delay is zero, on all 256 seed pairs in both applicable profiles. This is an exact implementation check, not a nonsignificance result.', '',
      '## Interpretation', '',
      'A bounded recent-evidence body model is preferable to an all-history pooled estimator for this specific nonstationary control problem. This does not establish that a fixed window is optimal. Resetting memory every episode recovers faster at the deliberately episode-aligned change, but sacrifices information on unchanged episodes. A context-conditioned model bank or change-point method is a motivated next comparator, not a result already obtained.', '',
      'The body is a continuous-state planar point mass with momentum, not a grid. Mapping and anisotropic actuation gains change together. Morphology, contact, camera sensing, unknown damping, real hardware, hosted-language-model action selection, and personal continuity were not tested.', '',
      'All source code, frozen random draws, per-episode outcomes and per-trial trace hashes are supplied. Full raw step traces are retained for the first evaluation seed in each algorithm/profile, with deterministic regeneration available for every other trace. Raw-trace gzip header times are not the semantic trace digest.', '']
    if invariant_path.exists():
        report += ['## Replay and recovery checks', '', '```json', json.dumps(result['invariants']['summary'], indent=2), '```', '',
                   'The records-only condition in source code means an intentionally reset numerical controller. It does not replay the saved learning history. It is therefore a state-restoration ablation, not evidence that event records cannot reconstruct learned state.', '']
    (out / 'RESULTS.md').write_text('\n'.join(report))
    print(json.dumps({'counts': result['evaluation_counts'], 'primary': g, 'stable': p,
                      'design_rule_passed': selected, 'overlap': comparison}, indent=2))
    return result

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, default=ROOT / 'results')
    args = parser.parse_args()
    build(args.results)
