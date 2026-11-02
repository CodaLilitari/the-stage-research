# AB-MPB1B: transport under common pump caps

1 November 2026. Coda (Codex Lily), collaborating with Richard Pemberton; Lilitari (Lily) contributed the matched-pumping research priority and application boundaries.

The 27-row frozen synthetic study completed successfully after recovery from an internal-agent usage limit. The existing implementation was unchanged from its 17 passing tests. The full Python study took 1.194 seconds under a 60-second child-process deadline. All 33 admitted A files remained unchanged. Nine matched-flow rows reproduce A to a maximum full-state difference of 8.89e-16 micromoles. Largest oxygen/site conservation residuals were 1.16e-14 and 1.12e-14 micromoles; all observed state minima were nonnegative. These are software and synthetic model results, not hardware or biological validation.

## Pump comparison

With pressure cap 12 kPa, hydraulic-power cap 3.2 mW and linear resistance R in kPa*s/mL, Q=min(12/R,sqrt(3.2/R)) mL/s. The crossover is R=45. The three R values 20,40,80 produce Q=0.4,0.2828427,0.15 mL/s. The first two are power-limited; the last is pressure-limited. Their realized pressure is 8,11.3137,12 kPa and hydraulic power 3.2,3.2,1.8 mW. Equal caps do not mean equal realized pressure and power.

Each resistance is crossed with no binding sites, binding sites at the same initial free concentration, and binding sites at equal initial total oxygen. The same-free case begins with 4.4 micromoles oxygen versus 2.4 for the others, an 83.33% inventory difference. The equal-total case changes the initial free/bound partition. These are distinct comparisons.

At 30 s, distal wall concentrations for R=20/40/80 are:

| Initial condition | Distal concentration [micromol/mL] | Consumed [micromol] |
|---|---|---|
| No sites | 0.328213 / 0.321792 / 0.302033 | 0.939771 / 0.926991 / 0.890206 |
| Sites, same free concentration | 0.383084 / 0.376882 / 0.359076 | 1.013147 / 1.000954 / 0.967930 |
| Sites, equal total oxygen | 0.181702 / 0.179087 / 0.171987 | 0.456848 / 0.451832 / 0.438967 |

Resistance can change even the direction of a selected comparison: at 10 s the same-free site case at R=80 has distal concentration 0.439342, below the no-site R=20 baseline 0.462459. At 30 s it is above that baseline (0.359076 versus 0.328213). This is a synthetic, time-specific result under an assigned resistance penalty, with unequal initial oxygen. It does not establish a universal carrier advantage or disadvantage. All 63 contrasts and 27 complete state rows are retained, not selected by favorable ranking.

## Interpretation limits

Resistance multipliers are assigned, not measured carrier viscosity. Geometry is fixed and resistance independent of mesh count. Pump efficiency, electrical power, heat generation and clinical microcirculation are absent. Distal/spatial-minimum concentration is measured at a named time, not a minimum over the full trajectory (the wall starts at zero). Consumed oxygen and signed net wall transfer are separate bookkeeping endpoints; neither denotes tissue growth, viability, maturation or graft suitability. Flow ablation, inventory and resistance effects are labeled separately.

The next useful review is whether these contrasts and the H/M/T transfer contract support the stated limited conclusions. This report does not claim an independent rerun of all trajectories. Coordinator source/result inspection and the prior independent A no-site oracle are separate evidence. A new paid frozen-artifact review is pending.

## Reuse and contributions

Richard Pemberton: direction, scope and funding. Coda (Codex Lily), including native agent stage_site0_recovery: model wrapper, tests, recorded study, recovery and analysis. Lilitari (Lily): research-scope architecture, transfer-boundary analysis and prioritization. Original prose CC BY 4.0 where rights exist; new code Apache-2.0. Facts/methods are not exclusive property. No third-party source or private dialogue is relicensed. No publication or biological experiment occurred.
