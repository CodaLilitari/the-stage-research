# Independent thermal reference: executed result

Coda collaborating with Andrei, 2026-11-01. This directory was prepared and executed independently while Fable processed the thermal-contract packet. No Fable response was read. All writes are confined to validation/thermal; original Stage files and prompt files are unchanged.

Status: small synthetic reference EXECUTED. Tests-first red phase:20 failures,0 errors because the reference implementation was absent. Green phase after implementation:20 passed,0 failures,0 errors. Logs and machine-readable results preserve both phases. These are mathematical/software checks, not empirical validation.

The independent steady solver eliminates HEAT-FLOW variables using exact rational arithmetic; Fable was asked for a conductance-matrix formulation. The predeclared exact fixture includes the nominal H1 front flow1103951/1613020 W, source-placement asymmetry, signed reverse reservoir flow, two separately blocked boundaries, no-exit singularities, merged internal nodes, common-temperature translation and local/global balances. One process was run at a time; every Python invocation had a60-second actual parent deadline and finished in under1 second observed tool wall time. No dependency installation, network, GPU or API was used.

At5 W internal body dissipation plus0.1 W sensor dissipation, common25 C ambient/reservoir, h8 W/(m2 K), rear resistance2 K/W:

| Stack | Surface C | Sensor C | Internal H C | Front W | Rear W |
|---|---:|---:|---:|---:|---:|
| H1 |33.5550008679|33.7039846238|33.8311998611|0.684400069435|4.41559993057|
| H2 |33.3631096417|33.6326495681|33.8619024573|0.669048771340|4.43095122866|
| H3 |33.0059015476|33.5011406870|33.9190557524|0.640472123807|4.45952787619|

The thicker hypothetical cover lowers the modeled outer temperature while raising the internal-node temperature. This is a conditional two-objective tradeoff, not evidence that a thicker real covering is better or worse.

Blocking the rear path makes steady front power5.1 W and surface88.75 C for all three stacks; H becomes90.9486203704,92.8189907407,96.5597314815 C for H1,H2,H3. This is a mathematical extrapolation of fixed nominal properties and fixed convection, not an actual panel-temperature prediction or validated fault envelope. It shows the assumed rear reservoir materially determines the nominal result. The reservoir realization, actual heat load and assembled properties remain unknown.

Twelve steady reference rows are saved: three stacks at1,5,10 W with rear path present, plus each stack at5 W with rear path blocked. Global balance is exactly zero in the rational solver. Exact conservation alone does not verify the modeled geometry or properties.

Independent transient special cases:
- One-node analytic exponential at20 s:23.792723352971347 C for the predeclared C10 J/K,R2 K/W,P3 W,T0=Tb=20 C fixture.
- Backward Euler dt1,.5,.25 s errors:0.05406025020934635,0.027307095158171535,0.013724073533140313 K. The observed ratios meet the predeclared first-order refinement range.
- Corresponding integrated-energy residuals:7.105427357601002e-14,9.237055564881302e-14,-7.105427357601002e-15 J.
- Insulated one-node heating, two-node weighted-energy conservation/exponential equilibration, segment composition and state continuity at a parameter-change instant are separately checked.

No full multilayer transient F0-F5 suite, controller/event implementation, spatial mesh convergence, partial-delamination hot-spot model, uncertainty sweep, physical safety claim or biological viability result is produced here. A frozen sensor's physical open-loop invariance and correct sensor source placement are declared future review targets; the main Fable implementation must still be checked. The40/60 C values in the source prompt remain arbitrary study comparators. PF0's historical6/7 result is unchanged.

Files:
- ACCEPTANCE_PREDECLARED.md: equations, exact fixtures, criteria and fault list written before implementation.
- test_thermal_reference.py:20 behavior checks; expected values independent of the functions being checked.
- thermal_reference.py: exact steady elimination and small analytic/discrete transient references.
- red_test_result.json and red logs: observed expected missing-implementation failure.
- green_test_result.json and green logs: observed all-pass result.
- reference_results.json:12 steady rows, exact flux strings, transient values and code hash.
- reference-manifest.json: hashes binding source prompt and delivered artifacts.

The next review should compare Fable's independently returned nodal equations and outputs against these fixtures, retain any disagreement, and only then admit broader main numerical work.
