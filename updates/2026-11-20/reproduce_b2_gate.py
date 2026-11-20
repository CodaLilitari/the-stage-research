"""Reproduce two B2 thermal-panel confirmation cells. Requires Python, NumPy and SciPy.

Run: python reproduce_b2_gate.py > b2_gate_cells.json
Original two-node panel and B2 calibration definitions come from The Stage.
Coda independently implemented the matrix fit, sensitivity and validation here.
No input files, credentials, network or provider code are required.
"""
import json
import random
import numpy as np
from scipy.signal import lfilter


def panel(thickness, powers):
    # Solve the panel heat equations in temperature rise from a 25 C ambient.
    area = .01
    resistance = thickness/(.27*area) + .00005/(2*.2*area) + .0002/area
    conductance = 1/resistance
    convection = 1/(resistance + 1/(8*area))
    capacity = np.diag([20, 1030*area*2*thickness*1500 + 1420*area*.00005*1090])
    loss = np.array([[conductance+.5, -conductance], [-conductance, conductance+convection]])
    step_inverse = np.linalg.inv(capacity + loss)  # one-second backward Euler
    evolution = step_inverse @ capacity
    heater = step_inverse[:, 0]
    constant = .1 * step_inverse[:, 1]
    state = np.zeros(2)
    readings = [25.]
    for power in powers:
        state = evolution @ state + heater*power + constant
        readings.append(float(state[1] + 25))
    # Eliminate the hidden node through the 2-by-2 characteristic polynomial.
    trace = np.trace(evolution)
    determinant = np.linalg.det(evolution)
    remainder = evolution - trace*np.eye(2)
    exact = [trace, -determinant, heater[1], (remainder@heater)[1],
             ((np.eye(2)+remainder)@constant)[1] + (1-trace+determinant)*25]
    return np.array(readings), exact


def regressors(readings, power):
    return np.column_stack(((25-readings[1:-1])/40, np.diff(readings[:-1]),
                            power[1:]/5, power[:-1]/5, np.ones(len(power)-1)))


def forecast(arx, power, first_two):
    a1, a2, b0, b1, intercept = arx
    offset = first_two[0]
    forcing = np.zeros(len(power)+1)
    forcing[1] = first_two[1]-offset
    forcing[2:] = b0*power[1:] + b1*power[:-1] + intercept + (a1+a2-1)*offset
    return offset + lfilter([1], [1,-a1,-a2], forcing)


def statistics(series):
    # Each row is one time step. For a matrix, each column is a separate derivative.
    means = np.mean(np.lib.stride_tricks.sliding_window_view(series,5,axis=0),axis=-1)
    return [series[2:], means[10:]-means[:-10], means[61:]-means[:-61]]


def trial(seed, noise, calibration, clean, exact, test):
    rng = random.Random(seed)
    measured = clean + noise*np.array([rng.gauss(0,1) for _ in clean])
    design = regressors(measured, calibration)
    target = np.diff(measured)[1:]
    ridge = 1e-6
    precision = design.T@design + ridge*np.eye(5)
    covariance = np.linalg.inv(precision)
    raw = np.linalg.solve(precision, design.T@target)
    theta = raw + ridge*np.linalg.solve(precision,raw)
    leak, lag, b0, b1, bias = theta / [40,1,5,5,1]
    model = [1-leak+lag, -lag, b0, b1, bias+25*leak]
    residual_sd = np.linalg.norm(target-design@theta)/np.sqrt(len(target)-5)
    anchors = np.repeat((5*(b0+b1)+model[-1])/leak,2)
    prediction = forecast(model,test,anchors)
    truth = forecast(exact,test,anchors)
    direct = np.vstack([np.zeros((2,5)),regressors(prediction,test)])
    gradients = lfilter([1],[1,-model[0],-model[1]],direct,axis=0)
    envelopes = [4*residual_sd*np.sqrt(np.max(np.einsum('ij,jk,ik->i',x,covariance,x)))
                 for x in statistics(gradients)]
    maxima = [np.max(np.abs(s)) for s in statistics(prediction-truth)]
    thresholds = [.8,.3,.2]
    calibration_peak = np.max(np.abs(forecast(model,calibration,measured[:2])[2:]-measured[2:]))
    stable = np.all(np.abs(np.roots([1,-model[0],-model[1]]))<1)
    accepted = (len(target)>=200 and stable and .1<=(b0+b1)/leak<=100 and calibration_peak<=.3
                and np.all(np.array(envelopes)<=thresholds))
    return {'seed':seed,'accepted':bool(accepted),'probe_error_K':float(maxima[2]),
            'probe_envelope_K':float(envelopes[2]),'error_exceeds_any_envelope':bool(np.any(np.array(maxima)>envelopes)),
            'error_exceeds_any_study_limit':bool(np.any(np.array(maxima)>thresholds))}


def main():
    result = {'python_seed_range':[73001,73032],'panel_dt_seconds':1,'study_limit_probe_K':.2,'cells':[]}
    for stack,thickness,noise in [('H1',.0005,.01),('H2',.001,.001)]:
        t = np.arange(450)
        calibration = np.where((t>=60)&((t-60)%150<60),2.,5.)
        clean, exact = panel(thickness,calibration)
        assert np.max(np.abs(forecast(exact,calibration,clean[:2])-clean)) < 1e-8
        k = np.arange(900)
        test = np.where((k>=2)&((k-2)%150<60),2.,5.)
        rows = [trial(seed,noise,calibration,clean,exact,test) for seed in range(73001,73033)]
        result['cells'].append({'stack':stack,'sigma_K':noise,'n':len(rows),
            'accepted':sum(r['accepted'] for r in rows),
            'accepted_exceeding_envelope':sum(r['accepted'] and r['error_exceeds_any_envelope'] for r in rows),
            'accepted_exceeding_study_limit':sum(r['accepted'] and r['error_exceeds_any_study_limit'] for r in rows),
            'trials':rows})
    print(json.dumps(result,indent=2,allow_nan=False))


if __name__=='__main__':
    main()
