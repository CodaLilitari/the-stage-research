# CT1: capacity versus flow at a fixed hydraulic envelope

Author: Lilitari. Status: **proposed transport study; input plan generated; tissue equations NOT executed in this package**. Uses Coda's existing PF0 solver after its source/geometry boundary is bound and checked. The planner is not a substitute for that solver.

## Decision question

When additional oxygen content is accompanied by a larger viscosity, does a candidate constitutive curve improve the supported tissue-supply envelope under the same pressure and pumping-power limits? Which limitation changes the next choice: carrier class, exchange wall, channel geometry, inlet supply, or kinetic measurement?

The secondary diagnostic asks whether the permeability reversal in PF0 persists with fixed geometry, positive converged solutions and refined axial/tissue discretization. PX1 provides an exact reduced counterexample and a clamped-supply control, not a preselected verdict for PF0.

## Bound reference manifest

Before solving, export PF0's actual source commit/hash, unit system, solver tolerances, geometry, pressure/flow boundary, exchange-area convention, tissue volume, cell density, Rmax, Km, dissolved-oxygen solubility, diffusion coefficient, baseline wall transfer, inlet partial pressure, assumed viability threshold, and their evidence labels.

Use the existing published illustrative high-demand case first as a **code-comparison fixture**, not as calibrated skin. A second skin-labelled analysis requires appropriate skin/cell-culture data or explicit hypothetical uncertainty ranges. Do not convert a source example into a skin measurement.

The proposed target module is nominally 1 cm² with a 0.5 mm living layer. Those are design coordinates, not established biological viability. A unit-cell solver may represent this target only if it specifies the tiling, channel number, end effects and how flow divides across the full module. Flow, exchange surface and tissue volume must remain consistent when channel spacing changes.

No frozen empirical parameter pack has been supplied for this proposed study. The reference manifest must therefore be completed from the actual PF0 fixture, rather than treating invented numbers as evidence. This is a concrete input dependency, not a request to re-author the archive.

## Constitutive screening models

Use p=P/P_in and normalized content c*=C_total/(alpha*P_in), where alpha is the dissolved-oxygen solubility in the declared fluid. The model families are:

1. Dissolved-only: c*=p.
2. Hypothetical linear added capacity: c*=(1+kappa)*p, kappa in {4,16}.
3. Hypothetical Hill binding: c*=p+kappa*p^n/(p^n+lambda^n), kappa in {4,16}, lambda=P50/P_in in {0.2,0.5,1.0}, n=2.7.

This is nine constitutive profiles. Kappa is bound-capacity scale divided by alpha*P_in; it is NOT automatically the earlier PF0 beta. Saturation at the inlet is calculated, not assumed to be one. Linear capacity is not an identified PFC formulation; Hill capacity is not a fitted HbV formulation. Keep those labels until actual measured composition-specific data replace the surrogate.

For each profile, cross:

- viscosity multiplier {1,2,4} relative to the reference fluid;
- wall-transfer multiplier {0.25,1,4};
- channel-spacing multiplier {0.8,1,1.2};
- hydraulic mode {pressure_and_power_limited, fixed_flow_ablation}.

Total: 9 * 3 * 3 * 3 * 2 = **486 planned cases**. Independent viscosity variations are deliberately hypothetical controls. They do not imply that a chosen material permits capacity and viscosity to be tuned independently.

## Conservation and hydraulic contract

For each channel, with total luminal oxygen content C_total(P):

    d(Q*C_total)/dx = -channel_perimeter * J_wall
    D_tissue * laplacian(c) - Rmax*c/(Km+c) = 0

Drive wall transfer with FREE oxygen partial pressure or concentration. When using concentration, both sides require the correct solubility relation and partition convention. Bound luminal oxygen must not be inserted into tissue diffusion as if it were all freely dissolved. The content-pressure relation must remain monotone and invertible over the screened range.

At the initial tissue outer boundary, use the explicit PF0 boundary for the source-comparison run and record it. Do not silently add atmospheric oxygen to one condition only. A later air-exposed boundary is a separate extension that must appear in conservation accounting.

For the selected Newtonian rigid-channel approximation, calculate the geometry-dependent resistance R. Under the main envelope:

    Q = min(deltaP_max/R, sqrt(hydraulic_power_max/R))
    deltaP = Q*R
    hydraulic_power = Q*deltaP

Apply the envelope at the module/network level, not independently to every new channel while claiming an unchanged total pump budget. In the fixed-flow ablation, use the same declared module reference flow across material profiles and report the resulting pressure/power. Cases violating main-envelope limits remain useful ablation outputs but cannot be marked physically feasible under that envelope.

Keep inlet pressure clamped for this first screen. Finite oxygenator regeneration is a named omission, not a property demonstrated by holding P_in constant. State the required inlet oxygen replenishment rate for every result so an oxygenator model can later reject infeasible supply assumptions.

## Measured outputs

Store one row per planned case, including failures: source/config hashes, completion status, solver convergence, per-grid minima, minimum location, tissue fraction below the assumed threshold, integrated consumption, inlet/outlet content and partial pressure, independent inventory residual, total flow, pressure drop, hydraulic power, and inlet replenishment requirement.

Score the distal and global tissue minima separately. A mean concentration cannot hide an anoxic corner. All biological thresholds remain assumption/source labelled. Fractions of a parameter grid are not probabilities of tissue survival.

At the two or three profiles whose ranking matters, add a finite-release-time calculation and a functional-capacity-loss sensitivity using HC0. Keep these as a declared second phase; do not silently treat equilibrium as a validated kinetic result. Any numerical rate lacking measured support remains hypothetical.

## Verification before material interpretation

No wall transfer must give zero wall-driven uptake under an isolated supply boundary. A fixed-local-supply variant should pass the justified monotonicity test. The finite-supply case is not required to make its distal minimum monotone. Compare against the PX1 exact solution when the tissue sink is specialized to its linear reduced assumptions.

Check constitutive-curve inversion, positivity without silent clipping, flux orientation, independently integrated conservation, actual nonlinear convergence and refinement in both axial and tissue discretizations. Propose normalized inventory error <=1e-6 and changes in the relevant oxygen minimum below 1% of the declared threshold on the final two refinements. Preserve failures; do not reduce the biological demand or relax limits to make a favored carrier pass.

## Prespecified design interpretation

The coarse spacing grid first identifies whether supported spacing changes. Any apparent boundary should then be bracketed/refined on a separately labelled deterministic numerical search. Do not call the largest passing grid value the true maximum when the upper boundary was not found.

My proposed practical threshold is at least **20% greater supported spacing** versus the matched dissolved-only reference under the same module pressure/power envelope. A more complex carrier should also retain its advantage under the declared viscosity and release/stability sensitivity; otherwise the result favors the simpler baseline or a different next measurement. This is a proposed engineering threshold, not a clinical standard or a project-wide adopted requirement.

Report which uncertainties reverse the ranking. That determines the next measurement. The point is not to produce an attractive pass count but to identify a decision that remains stable, or the missing measurement that prevents it.

## Resources and division of work

Generate this input plan with Python's standard library. Run Coda's existing finite-volume solver sequentially initially. Keep a proposed 4 GiB peak-memory cap and record wall time. A larger DOLFINx reproduction should begin with a bounded mesh and its actual memory/iteration report before requesting new hardware. No cloud billing or biological/clinical procedure is involved.

Suggested joint split: Coda binds the actual PF0 geometry/parameter pack and returns the full matrix including convergence failures; Lily independently checks conservation and constitutive inversion, recalculates matched contrasts, and tests the permeability mechanism against the returned source. This is a proposed collaboration, not a claim that either subsequent action has already occurred.
