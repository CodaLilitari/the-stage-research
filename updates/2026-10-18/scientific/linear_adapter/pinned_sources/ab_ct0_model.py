"""AB-CT0 hypothetical transport model. No execution at import.

The cell-centered slab residual/Jacobian and backward-Euler axial strategy adapt
Coda's frozen PF0 (source hash in freeze.json). This is new implementation, not
a replacement of PF0. Only runner-counted calls are authorized transport solves.
"""
import math
import time


def positive(x, name, zero=False):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or x < 0 or (x == 0 and not zero):
        raise ValueError(f"Invalid {name}: finite {'nonnegative' if zero else 'positive'} number required")


def validate(case, cfg):
    for key in ('L', 'w', 'gap', 'd', 'D', 'cin', 'Km', 'mu0', 'Qref', 'hill_n', 'c50', 'B'):
        positive(cfg[key], key, zero=key == 'B')
    for key in ('mu', 'P', 'Rmax'):
        positive(case[key], key, zero=key in ('P', 'Rmax'))
    for key in ('ny', 'nz'):
        if case[key] is None and key == 'nz' and case['clamped']:
            continue
        if type(case[key]) is not int or case[key] < (2 if key == 'ny' else 1):
            raise ValueError(f'Invalid {key}')
    if case['profile'] not in ('D', 'L', 'H_eq', 'H_finite'):
        raise ValueError('Unknown carrier profile')
    if case['flow_mode'] not in ('envelope', 'fixed_flow'):
        raise ValueError('Unknown hydraulic mode')
    if case['flow_mode'] == 'fixed_flow':
        positive(case['Q'], 'fixed Q')
    if case['profile'] == 'H_finite':
        positive(case['k'], 'k', zero=True)
    elif case['k'] is not None:
        raise ValueError('Equilibrium profile must have k=None')
    if case['profile'] == 'L':
        positive(case['beta'], 'beta')
        if case['beta'] < 1:
            raise ValueError('beta below dissolved capacity')
    if case['reaction'] not in ('mm', 'linear', 'zero_order'):
        raise ValueError('Unknown reaction')
    if case['reaction'] == 'linear':
        positive(case['kt'], 'linear reaction rate', zero=True)
    if case['reaction'] == 'zero_order' and not case['clamped']:
        raise ValueError('Zero-order verification is local clamped supply only')
    if case['P'] == 0 and (case['Rmax'] == 0 or case['reaction'] != 'mm'):
        raise ValueError('Underdetermined/unsupported isolated control')


def hydraulics(case, cfg):
    r0 = 12 * cfg['mu0'] * cfg['L'] / (cfg['w'] * cfg['gap'] ** 3)
    resistance = r0 * case['mu']
    dpmax, pmax = r0 * (3e-9 / 60), r0 * cfg['Qref'] ** 2
    qp, qw = dpmax / resistance, math.sqrt(pmax / resistance)
    q = min(qp, qw) if case['flow_mode'] == 'envelope' else case['Q']
    positive(q, 'actual Q')
    return {'Q': q, 'Q_uL_min': q * 60 / 1e-9, 'Rhyd': resistance,
            'deltaP_Pa': resistance * q, 'power_W': resistance * q * q,
            'deltaP_max_Pa': dpmax, 'power_max_W': pmax,
            'active_cap': ('pressure' if qp < qw else 'power') if case['flow_mode'] == 'envelope' else 'fixed_flow_ablation',
            'pressure_violation': resistance * q > dpmax * (1 + 1e-12),
            'power_violation': resistance * q * q > pmax * (1 + 1e-12),
            'residence_s': cfg['w'] * cfg['gap'] * cfg['L'] / q}


def seq(c, cfg):
    if c < 0 or not math.isfinite(c):
        raise ValueError('Invalid free oxygen for Hill law')
    cn = c ** cfg['hill_n']
    return cn / (cn + cfg['c50'] ** cfg['hill_n'])


def content(c, case, cfg, old_s=None, a=None):
    profile = case['profile']
    if profile == 'D':
        return c, 0.0, 0.0
    if profile == 'L':
        bound = (case['beta'] - 1) * c
        return c + bound, bound, None
    s = seq(c, cfg) if profile == 'H_eq' or old_s is None else (old_s + a * seq(c, cfg)) / (1 + a)
    return c + cfg['B'] * s, cfg['B'] * s, s


def tridiagonal(lo, diag, hi, rhs):
    d, b = list(diag), list(rhs)
    for i in range(1, len(d)):
        if not math.isfinite(d[i - 1]) or d[i - 1] == 0:
            raise ArithmeticError('Invalid tridiagonal pivot')
        factor = lo[i] / d[i - 1]
        d[i] -= factor * hi[i - 1]
        b[i] -= factor * b[i - 1]
    if d[-1] == 0:
        raise ArithmeticError('Zero tridiagonal pivot')
    ans = [0.0] * len(d)
    ans[-1] = b[-1] / d[-1]
    for i in range(len(d) - 2, -1, -1):
        ans[i] = (b[i] - hi[i] * ans[i + 1]) / d[i]
    return ans


def reaction(c, case, cfg):
    if case['reaction'] == 'linear':
        return case['kt'] * c, case['kt']
    if case['reaction'] == 'zero_order':
        return case['Rmax'], 0.0
    return case['Rmax'] * c / (cfg['Km'] + c), case['Rmax'] * cfg['Km'] / (cfg['Km'] + c) ** 2


def slab(cbulk, case, cfg, heartbeat, counts):
    counts['slab_calls'] += 1
    n, d, D, P = case['ny'], cfg['d'], cfg['D'], case['P']
    dx = d / n
    scale = max(D * cfg['cin'] / d, case['Rmax'] * d, P * cfg['cin'])
    if P == 0:
        return {'c': [0.0] * n, 'J': 0.0, 'reaction_integral': 0.0, 'normalized_residual': 0.0, 'wall_surface': None}
    wall, g = 1 / (1 / P + dx / (2 * D)), D / dx
    if (case['reaction'] in ('mm', 'zero_order') and case['Rmax'] == 0) or (case['reaction'] == 'linear' and case['kt'] == 0):
        return {'c': [cbulk] * n, 'J': 0.0, 'reaction_integral': 0.0, 'normalized_residual': 0.0, 'wall_surface': cbulk}
    if cbulk == 0:
        if case['reaction'] == 'zero_order':
            raise ArithmeticError('Infeasible positive zero-order sink with zero supply')
        return {'c': [0.0] * n, 'J': 0.0, 'reaction_integral': 0.0, 'normalized_residual': 0.0, 'wall_surface': 0.0}

    def residual(values):
        r, lo, diag, hi = [], [], [], []
        for i, ci in enumerate(values):
            gl, gr = (wall if i == 0 else g), (g if i < n - 1 else 0.0)
            cl, cr = (cbulk if i == 0 else values[i - 1]), (values[i + 1] if i < n - 1 else ci)
            rate, deriv = reaction(ci, case, cfg)
            r.append(gl * (cl - ci) + gr * (cr - ci) - dx * rate)
            lo.append(gl if i else 0.0); hi.append(gr)
            diag.append(-gl - gr - dx * deriv)
        return r, lo, diag, hi

    c = [cbulk] * n
    for _ in range(cfg['newton_max']):
        heartbeat()
        r, lo, diag, hi = residual(c)
        norm = max(abs(v) for v in r)
        if norm <= cfg['nonlinear_relative_tol'] * scale:
            J = wall * (cbulk - c[0])
            return {'c': c, 'J': J, 'reaction_integral': math.fsum(reaction(ci, case, cfg)[0] * dx for ci in c),
                    'normalized_residual': norm / scale, 'wall_surface': cbulk - J / P}
        counts['newton_iterations'] += 1
        delta = tridiagonal(lo, diag, hi, [-v for v in r])
        alpha = 1.0
        for _ in range(cfg['backtrack_max']):
            trial = [ci + alpha * di for ci, di in zip(c, delta)]
            if all(math.isfinite(v) and 0 <= v <= cbulk * (1 + cfg['domain_relative_tol']) for v in trial):
                if max(abs(v) for v in residual(trial)[0]) < norm:
                    c = trial
                    break
            counts['backtracks'] += 1
            alpha *= 0.5
        else:
            raise ArithmeticError('Tissue Newton line search failed')
    raise ArithmeticError('Tissue Newton iteration cap reached')


def solve(case, cfg, heartbeat):
    """One counted transport attempt. Runner must journal before calling."""
    start = time.perf_counter()
    validate(case, cfg)
    hyd = hydraulics(case, cfg)
    Q, cin = hyd['Q'], cfg['cin']
    counts = dict(slab_calls=0, newton_iterations=0, backtracks=0, axial_iterations=0)
    c, (total, bound, s) = cin, content(cin, case, cfg)
    inlet_total, inlet_bound, inlet_s = total, bound, s
    rows, exchanges, reactions, segment_errors = [], [], [], []
    nz = 1 if case['clamped'] else case['nz']
    dz, dy = cfg['L'] / nz, cfg['d'] / case['ny']
    absolute_floor = cfg['zero_flux_relative_tol'] * cfg['Qref'] * cin
    for j in range(1, nz + 1):
        heartbeat()
        old_c, old_s, old_total, old_bound = c, s, total, bound
        if case['clamped'] or case['P'] == 0 or (case['Rmax'] == 0 and case['reaction'] != 'linear') or (case['reaction'] == 'linear' and case['kt'] == 0):
            tissue = slab(c, case, cfg, heartbeat, counts)
        else:
            a = case['k'] * cfg['w'] * cfg['gap'] * dz / Q if case['profile'] == 'H_finite' else None
            factor = cfg['w'] * dz / Q
            def evaluate(x):
                ct, cb, sat = content(x, case, cfg, old_s, a)
                t = slab(x, case, cfg, heartbeat, counts)
                return ct + factor * t['J'] - old_total, ct, cb, sat, t
            lo, hi = 0.0, min(cin, old_total)
            flo, fhi = evaluate(lo)[0], evaluate(hi)[0]
            tol = cfg['axial_relative_tol'] * cin
            if flo > tol or fhi < -tol:
                raise ArithmeticError('Physical axial bracket failed')
            for _ in range(cfg['axial_max']):
                counts['axial_iterations'] += 1
                mid = (lo + hi) / 2
                err, ct, cb, sat, t = evaluate(mid)
                if err > 0:
                    hi = mid
                else:
                    lo = mid
                if abs(err) <= tol and hi - lo <= tol:
                    c, total, bound, s, tissue = mid, ct, cb, sat, t
                    break
            else:
                raise ArithmeticError('Axial iteration cap reached')
        exchange = cfg['w'] * dz * tissue['J']
        uptake = cfg['w'] * dz * tissue['reaction_integral']
        lumen_loss = None if case['clamped'] else Q * (old_total - total)
        discrepancies = [abs(exchange - uptake)]
        if lumen_loss is not None:
            discrepancies += [abs(lumen_loss - exchange), abs(lumen_loss - uptake)]
        scale = max(abs(exchange), abs(uptake), abs(lumen_loss or 0), absolute_floor * dz / cfg['L'])
        error = max(discrepancies)
        if error > cfg['mass_relative_tol'] * scale and error > absolute_floor * dz / cfg['L']:
            raise ArithmeticError('Segment conservation failed')
        ctolerance = cfg['domain_relative_tol'] * cin
        if not all(math.isfinite(v) and -ctolerance <= v <= cin + ctolerance for v in tissue['c'] + [c]):
            raise ArithmeticError('Concentration bound failed; no clipping applied')
        if s is not None and not (0 <= s <= (inlet_s or 0) + cfg['domain_relative_tol']):
            raise ArithmeticError('Saturation bound failed; no clipping applied')
        rows.append({'z': None if case['clamped'] else j * dz, 'c_lumen': c, 'bound_content': bound, 'total_content': total, 's': s,
                     'tissue': tissue['c'], 'J': tissue['J'], 'reaction_integral': tissue['reaction_integral'], 'wall_surface': tissue['wall_surface'],
                     'lumen_segment_loss_mol_s': lumen_loss, 'free_segment_loss_mol_s': None if case['clamped'] else Q * (old_c - c),
                     'bound_segment_loss_mol_s': None if case['clamped'] else Q * (old_bound - bound),
                     'wall_segment_mol_s': exchange, 'reaction_segment_mol_s': uptake,
                     'segment_error_mol_s': error, 'segment_relative_error': error / scale,
                     'tissue_normalized_residual': tissue['normalized_residual']})
        exchanges.append(exchange); reactions.append(uptake); segment_errors.append(error / scale)
    wall, uptake = math.fsum(exchanges), math.fsum(reactions)
    loss = None if case['clamped'] else Q * (inlet_total - total)
    diffs = [abs(wall - uptake)] + ([] if loss is None else [abs(loss - wall), abs(loss - uptake)])
    mass_abs = max(diffs)
    mass_scale = max(abs(wall), abs(uptake), abs(loss or 0), absolute_floor)
    if mass_abs > cfg['mass_relative_tol'] * mass_scale and mass_abs > absolute_floor:
        raise ArithmeticError('Global conservation failed')
    if loss is not None and uptake > Q * inlet_total + absolute_floor:
        raise ArithmeticError('Total inlet inventory exceeded')
    if case['profile'] == 'H_finite' and case['k'] == 0 and uptake > Q * cin + absolute_floor:
        raise ArithmeticError('Accessible k=0 inventory exceeded')
    minimum, minj, mini = min((v, j, i) for j, row in enumerate(rows) for i, v in enumerate(row['tissue']))
    summary = {**case, **hyd, 'status': 'completed', 'B': cfg['B'] if case['profile'].startswith('H') else 0,
               'k_residence': case['k'] * hyd['residence_s'] if case['k'] is not None else None,
               'inlet_free': cin, 'inlet_bound': inlet_bound, 'inlet_total': inlet_total, 'inlet_s': inlet_s,
               'outlet_free': c, 'outlet_bound': bound, 'outlet_total': total, 'outlet_s': s,
               'free_in_mol_s': Q * cin, 'free_out_mol_s': Q * c, 'bound_in_mol_s': Q * inlet_bound, 'bound_out_mol_s': Q * bound,
               'minimum_tissue': minimum, 'minimum_z': rows[minj]['z'], 'minimum_y': (mini + 0.5) * dy,
               'distal_tissue': rows[-1]['tissue'][-1], 'distal_y': cfg['d'] - dy / 2,
               'uptake_mol_s': uptake, 'wall_mol_s': wall, 'lumen_loss_mol_s': loss,
               'required_replenishment_mol_s': wall if case['clamped'] else loss,
               'mass_abs_error_mol_s': mass_abs, 'mass_relative_error': mass_abs / mass_scale,
               'maximum_segment_relative_error': max(segment_errors),
               'maximum_tissue_normalized_residual': max(r['tissue_normalized_residual'] for r in rows),
               'runtime_s': time.perf_counter() - start, **counts}
    return {'summary': summary, 'y_cell_centers': [(i + .5) * dy for i in range(case['ny'])], 'stations': rows}
