# Independent nonliving two-node transient: executed report

Coda collaborating with Andrei. Prepared and executed2026-11-01 under validation/thermal_transient only. No Fable response was read, no API call was made, and no historical validation or Stage input was edited.

**Result:19/19 test groups passed;9 bounded scenarios executed.** Before implementation,17 model tests failed as expected because implementation was absent, with0 errors. Before implementing report reduction,2 additional tests failed as expected because the summarizer was absent, with0 errors. Both RED records remain. Final full discovery ran19 tests in0.066 seconds, all passed. Scenario and reference calculations took0.0772 seconds within the Python process. Each process was serial, ran base Python with-B -I, inherited TEMP/TMP pointing to this F: directory, and had a60-second parent deadline. This is own-job timing, not machine diagnostics.

## Model and scope

T0-LUMP2-1 is an independent TWO-NODE approximation of the earlier T0-HYP-1 resistance network. It shares the exact steady connectivity and source placement, but collapses cover storage to an effective panel/sensor node. It is not the distributed multilayer finite-volume model requested in the separate model packet.

C_H=20 J/K is hypothetical robot storage. C_S=16.2239,31.6739,62.5739 J/K for H1,H2,H3 sums the reference silicone and film capacities, placing them at S. Silicone cp1500 J/(kg K) is assumed. Actual material/assembly capacities and their spatial distribution are not validated. Ambient and external rear reservoir are25 C; rear resistance2 K/W; front convection resistance12.5 K/W. An external reservoir remains an idealization with unestablished physical realization. No biological system is modeled.

The ODEs use separate body and sensor sources and signed front/rear fluxes. Backward Euler solves a2x2 implicit system; the determinant is assembled as positive terms to avoid unnecessary subtractive cancellation. Energy is audited using matching end-step flux quadrature and independently reconstructed from the returned trace. Positive temperatures alone do not demonstrate correctness; the tests compare independent analytic and rational targets.

Conductances and temperatures/capacities must be finite; blocked paths are zero conductance, not infinite numeric resistances. Capacities are positive. Sources are bounded to0..10 W body and0..0.2 W sensor. These bounds define the computational input envelope, not a controller or safety limit. A100000-step per-run cap bounds work. NaN, infinity, Boolean and nonnumeric parameters, negative conductances/powers, invalid durations/timesteps and excessive step counts are rejected before trajectory execution.

Declaration clarification: the introductory PREDECLARED.md phrase about negative physical parameters/state inputs was too broad. Negative Celsius temperatures remain mathematically admissible; the numbered guard tests and implementation reject negative passive parameters, powers and time, rather than negative temperature coordinates. The original declaration is retained unchanged. No numeric acceptance threshold was relaxed.

## Independent verification

- Nominal H1/H2/H3 long-time equilibrium matches the prior rational steady reference within the predeclared1e-9 K tolerance.
- Starting at that steady state holds the state to1e-10 K.
- The decoupled one-node limit approaches its analytic exponential. At20 s, exact H=23.792723352971347 C; dt1,.5,.25 s absolute errors are0.05406025020934635,0.027307095158182193,0.013724073533147418 K.
- A coupled equal-capacity two-node case approaches the independent sum/difference eigenmode solution. dt.1,.05,.025 s maximum errors are0.020207465088315557,0.01016162613712357,0.005091732219151546 K.
- For the H1 rear-loss trajectory, maximum H/S differences at common sample times are0.019767570088149 K for dt1 vs.5, and0.010563722601560244 K for dt.5 vs.25. The latter is below the predeclared.05 K criterion and decreases on refinement. This is temporal convergence of the lumped model, not spatial or physical validation.
- Insulated-network storage matches integrated body-plus-sensor power; reverse reservoir flux remains signed; rear-loss events produce no temperature impulse; sensor-only heating reaches the independently specified sensor-only steady state.
- Across the9 scenarios, maximum integrated-energy residual is1.469743438065052e-9 J, below each predeclared combined absolute/relative tolerance.

## Executed scenarios

All start H=S=25 C and run3600 s. Body heat is5 W until900 s, then0. Each stack has three cases: intact rear with sensor.1 W; rear loss at600 s with sensor.1 W; rear loss at600 s with sensor0 W THROUGHOUT. The third case does not mean sensor shutdown only at900 s. Source input totals are4860 J for sensor-on cases and4500 J for sensor-off cases, apart from floating-point summation noise.

| Stack/case | Peak H C (time s) | Peak surface C (time s) | H at3600 s C |
|---|---:|---:|---:|
| H1 intact/sensor on |33.831193 (900)|33.554994 (900)|25.170303|
| H1 rear loss/sensor on |61.143480 (900)|59.747155 (901)|26.374204|
| H1 rear loss/sensor off |60.446481 (900)|59.055570 (901)|25.104135|
| H2 intact/sensor on |33.861287 (900)|33.362444 (900)|25.168602|
| H2 rear loss/sensor on |55.545063 (900)|53.153638 (904)|26.798252|
| H2 rear loss/sensor off |54.963957 (900)|52.578375 (904)|25.520601|
| H3 intact/sensor on |33.884652 (900)|32.963939 (900)|25.165436|
| H3 rear loss/sensor on |50.169875 (900)|45.881263 (914)|28.187988|
| H3 rear loss/sensor off |49.704285 (900)|45.421846 (913)|26.934740|

These values are conditional mathematical outputs with fixed nominal properties and assumed convection. The rear reservoir has a large influence. Greater assumed storage delays cooling and changes peaks; the largest stack is still warmer at the horizon in rear-loss cases. The surface is algebraically reconstructed from a quasi-steady outer resistance, so its delayed peak is a feature of this lumped system, not proof of a real panel's delay. Temperatures at1-second peaks have finite temporal resolution.

The program evaluates every timestep. Persisted results include all case parameters/schedules, peaks, final states,600/900-second checkpoints, exact event records,60-second trace samples and event/peak neighbors. Full traces are not saved; the small deterministic run can reproduce them. A row's p,j and fluxes refer to the step ending at its time; event records contain the new segment source/conductance values at that time.

## Remaining boundaries

No spatial mesh convergence, distributed film/adhesive storage, localized delamination/hot spots, lateral conduction, radiation, real sensor behavior, controller, contact safety or biological viability is established. No statistical uncertainty distribution is inferred from the source properties. The40/60 C prompt comparators are not used as safe limits. The old PF0 failure is unchanged.

The useful outcome is a tested independent two-node calculation with exact steady agreement, independent transient targets, explicit inventories and bounded failure scenarios. It can challenge errors in subsequent richer models; agreement would not validate the extra spatial or biological claims of those models.

Files: PREDECLARED.md, rc_transient.py, test_rc_transient.py, study_report.py, test_study_report.py, preserved RED/green/final logs, study_results.json, verification-receipt.json and artifact-manifest.json.
