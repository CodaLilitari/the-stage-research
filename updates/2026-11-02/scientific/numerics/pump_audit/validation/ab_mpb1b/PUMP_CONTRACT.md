# AB-MPB1B pumping contract — frozen before implementation

1 November 2026. Prepared by Coda (Codex Lily), native agent stage_site0_recovery, collaborating with Richard Pemberton. The coordinator approved this design before implementation. Prose CC BY 4.0; code/interface definitions Apache-2.0, to the extent applicable rights exist.

## Purpose and chosen approach

Add one algebraic pumping constraint around the exact admitted AB-MPB1A kernel. A remains unchanged. The alternatives were a direct resistance factor or an empirical site-concentration/viscosity closure; only the direct, explicitly synthetic factor is justified here. No new transport kernel, rheology fit, pump hardware or biology is introduced.

The complete loop resistance R is a supplied positive finite scalar in kPa*s/mL for a fixed declared geometry. Pressure cap D is nonnegative finite kPa; hydraulic power cap P is nonnegative finite mW. Since kPa*mL/s = mW, admissible flow is

`Q = min(D/R, sqrt(P/R))`, `deltaP = R*Q`, `Phyd = deltaP*Q`.

This chooses the largest nonnegative flow satisfying both inequalities, deltaP <= D and Phyd <= P. Either zero cap forces zero flow. Zero resistance is rejected as a singular/undefined contract, including when a cap is zero. Negative, Boolean, nonnumeric and nonfinite inputs are rejected. Arithmetic beyond representable finite nonzero flow is rejected rather than silently replaced by zero or infinity. The normal finite calculations allow rounding-level residuals, which are reported.

The wrapper replaces only Config.flow, then calls the exact A solve entry with the original duration, timestep, geometry and initial state. Resistance is independent of numerical cell count. It is not inferred from carrier concentration or a mesh. The fluid remains the idealized A medium; R ratios are assumptions, not measured viscosity ratios or pressure-drop distributions.

Both caps are applied simultaneously. A row can be pressure-limited, power-limited, both, or zero-flow. The same caps do not imply the same realized pressure or the same realized hydraulic power across rows. Hydraulic power excludes electrical input, efficiency, thermal costs and heat-transfer guarantees.

## Frozen study and comparisons

Use R0 = 20 kPa*s/mL and ratios 1, 2 and 4, D = 12 kPa, P = 3.2 mW. Independent algebra gives:

| R | Q (mL/s) | deltaP (kPa) | Phyd (mW) | Active limit |
|---:|---:|---:|---:|---|
| 20 | 0.4 | 8 | 3.2 | Power |
| 40 | sqrt(0.08) | sqrt(128) | 3.2 | Power |
| 80 | 0.15 | 12 | 1.8 | Pressure |

At R = D^2/P = 45, Q = 4/15 mL/s and both caps bind.

The full crossed design has three unchanged A initial conditions, three R ratios and T = 2, 10, 30 s: 27 rows. Use three channel cells, no return cells, requested dt = 0.01 s, reservoir/channel/wall volumes 2/1/0.5 mL, G = 0.3 mL/s, kon = 0.5 mL/(micromole s), koff = 0.2/s and sink = 0.15/s. Initial wall and consumed amounts are zero.

| Condition | Free concentration | Site concentration | Occupied fraction | Initial O (micromoles) | Initial sites (micromoles) |
|---|---:|---:|---:|---:|---:|
| no_sites | 0.8 | 0 | 0 | 2.4 | 0 |
| sites_same_initial_free | 0.8 | 1 | 2/3 | 4.4 | 3 |
| sites_equal_initial_oxygen | (-0.6+sqrt(1.64))/2 | 1 | C/(0.4+C) | 2.4 | 3 |

All conditions receive every resistance. Keep these comparisons separate:

1. **Resistance-only:** no-sites R = 40/80 against no-sites R = 20 at the same time.
2. **Within-resistance inventory/binding comparisons:** each site case against no-sites at the same R and time. Same-free has extra oxygen; equal-total changes its initial free/bound partition and early dissolved supply.
3. **Assigned resistance penalty:** site cases at R = 40/80 against no-sites R = 20. This explicitly combines assumed resistance, binding and inventory/partition changes. It is not a material or isolated viscosity effect.
4. **Prescribed-flow ablation:** compare each B row with the saved A row having the same initial condition and elapsed time at Q = 0.4. At R = 20 this must reduce to A. For R = 40/80 the fixed-flow reference would require deltaP = 16/32 kPa and Phyd = 6.4/12.8 mW, so it is an unconstrained reference that violates these caps.

Retain all rows regardless of ranking. Record initial free/bound/empty amounts and inventories, all caps and realized pump values, full final state, all wall concentrations, distal and spatial-minimum wall concentration at the sample time, cumulative consumed amount and net wall transfer. Net transfer is final wall plus consumed minus their initial sum; it is not gross one-way flux. An initially empty wall makes the minimum over the whole trajectory zero, so it is not the primary endpoint.

## Scope and evidence

This is a synthetic finite-compartment oxygen bookkeeping experiment. No real resistance, carrier rheology, attainable hardware flow, electrical power, tissue growth, compatibility, maturation or biological respiration is inferred. No continuum convergence claim follows from cell-count invariance of an algebraic pump rule. The prior sink remains a first-order ledger, not a growth law.

Pin A kernel d05cdd81f64464091148570d2f8c78f668e4960ffb10ae137f1ee6ad2f63c172, A manifest 14416f7f4e4650da4e6ef3182953646ef3e02064ed37646f33c9be761e0741b4 and A numerical receipt 859fd45ea16751d7722c3b2e85a241e5981a10906512c66cb05025b46dc1e90e. Check all 33 A manifest entries before and after execution. Whole Python child deadline 60 seconds, bytecode disabled, F-only TEMP/TMP. Preserve RED, failures and immutable study output. Any deadline alteration requires the coordinator.
