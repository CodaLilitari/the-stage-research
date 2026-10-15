# PF1-S — Skin transport evidence and computation

**Cowork contribution to The Stage.** 2026-10-15.
Cloud runtime only. Five supplied Stage files plus public sources. No local device
access was granted, requested, or used; no path on Richard Pemberton's machine was read.
No contact with source authors, no biological or clinical experiment, no purchases,
no schedules, no messages to anyone.

**Deliverables in this folder**

| File | What it is |
|---|---|
| `skin_transport_parameters.csv` | 33-row parameter ledger with provenance and combination flags |
| `build_parameter_table.py` | generator for the ledger (the ledger is reproducible, not hand-typed) |
| `pf1s_skin.py` | the solver and the 972-case screen |
| `pf1s_criterion.py` | identifiability test, critical boundary, measurable oxygen budget |
| `pf1s_figure.py` | figure |
| `pf1s_execution_log.txt`, `pf1s_criterion_log.txt`, `parameter_table_build.log` | actual run output |
| `pf1s_results.json`, `pf1s_criterion.json`, `pf1s_cases.csv` | results |
| `pf1s_figure.png` | figure |

---

## 1. Headline

At the only openly published, fully dimensioned perfused human skin geometry in
the packet, **the dermal parameters this project has been hunting for are not
decision-relevant, and the one that is has an unresolved factor-of-97 arithmetic
error in its source.**

Across 972 cases spanning every documented ambiguity, the pass-rate range by
parameter was:

| Parameter varied | Pass-rate range |
|---|---|
| **Epidermal demand** | **1.000** |
| Channel wall transfer | 0.080 |
| Surface condition | 0.056 |
| Dermal diffusivity | 0.052 |
| Rhee cell density | 0.003 |
| Construct thickness | 0.003 |

Epidermal demand alone decides the outcome. Everything else, including the
fibroblast density ambiguity and the collagen diffusivity question that file 01
centres on, moves it by under 8 percentage points.

The reason is geometric and is worth stating plainly. At Rhee's 400 µm channel
spacing the **dermal** Thiele modulus is 0.0024–0.048 — between 20× and 400× away
from diffusion limitation. The **epidermal** modulus is 0.15–5.0. The dermis is
not close to being the constraint. The epidermis is: thin, dense, metabolically
active, and sitting at the far end of the diffusion path from the channels.

---

## 2. Source verification — including three defects found by reading

Checked in this pass from primary or curated routes: Streeter & Cheema 2011,
Cheema 2012 (plus BioNumbers 115120 and 115121), Rhee 2024 full text, Balu 2013
full text. **Not verified in this pass** (NCBI CAPTCHA-gated; publisher routes
returned robots-disallowed or client errors): Stücker 2002, Hatcher & Plachy 1993,
Mieremet 2019, and the Kawai 2025 correction. Those four are carried as
collaborator-reported and every result depending on them is labelled.

### 2.1 Balu 2013 does not reproduce its own per-cell number — factor of ~97

The full text prints **~0.035 mmol per 10⁶ cells per hour** for basal
keratinocytes — *mmol*, not µmol. File 01 reads it as µmol and converts to
9.72 × 10⁻¹⁸ mol cell⁻¹ s⁻¹. The printed value actually converts to
9.72 × 10⁻¹⁵, which is ~1000× typical single-cell respiration and cannot be right.

Recomputing from the paper's own stated inputs — 0.1 mmol L⁻¹ s⁻¹ (= 4 × a
measured 0.025 mmol L⁻¹ s⁻¹ oxyhaemoglobin decline), distributed over the stated
200 pL imaged volume holding ~200 cells:

```
1e-4 mol L^-1 s^-1  ×  2e-10 L  =  2e-14 mol s^-1  ÷  200 cells
                                =  1.0e-16 mol cell^-1 s^-1
                                =  0.00036 mmol / 1e6 cells / h
```

That is ~97× below the printed figure. The paper does not show the conversion.
So there are three candidate values spanning **3240×**, and they are not idle
variation: 0.00972 and 0.1 mol m⁻³ s⁻¹ **fall on opposite sides of this
geometry's sufficiency boundary** (which sits at 0.023–0.090 depending on surface
state). The printed value, 9.72, is excluded by the physics — it fails in 243 of
243 cases, which is itself evidence the units are wrong.

The defensible quantity from Balu is the **volumetric** rate, 0.1 mol m⁻³ s⁻¹,
because it needs no per-cell attribution. But note it is ~33× above textbook
resting skin (~0.003) and is an occlusion-onset transient measured over a 2–3 mm
SFDI interrogation depth, then attributed to a 200 pL imaging volume. That
attribution across four orders of magnitude in scale is the weak step.

### 2.2 Rhee 2024 §2.6 is arithmetically inconsistent — confirmed

As file 01 suspected. §2.6 states 4 × 10⁶ fibroblasts in a 100 µL suspension *and*
a final concentration of 2 × 10⁶ cells/mL. 4 × 10⁶ in 100 µL is 4 × 10⁷ cells/mL;
across the full 200 µL dermal solution it is 2 × 10⁷ cells/mL. Neither equals the
stated value, which would correspond to 4 × 10⁵ cells. The discrepancy is 10–20×.

**I did not resolve it, and the run shows it barely matters** — pass-rate range
0.003. Worth recording for accuracy, not worth blocking on.

Four parameters not in file 01 were recovered from the same paper and do matter:
channel **wall thickness 50 µm**, surface pore line width 7 µm, dermal matrix
**3 mg/mL rat tail collagen**, and **outlet flow 12 µL/min against inlet 10 µL/min**.
That last one means the lumen is not a closed conduit — 20% of the flow leaves
through or around the construct. Neither PF0 nor PF1-S represents that transmural
term.

Also confirmed: **the paper measures no oxygen anywhere.** The Discussion asserts
perfusion "ensures adequate nutrient and oxygen supply" with no supporting data.
That assertion is what PF1-S sizes.

### 2.3 BioNumbers BNID 115121 launders the wrong cell type

The entry is titled *"Oxygen consumption rate (Vm) for HDFs [Human dermal
fibroblasts]"* and cites Streeter & Cheema 2011. Its two numeric values —
6 × 10⁻¹⁷ and 3 × 10⁻¹⁷ mol cell⁻¹ s⁻¹ — are attributed to Cho et al. 2007
(3T3, a mouse line, in hepatocyte co-culture) and von Heimburg et al. 2005
(adipogenic mesenchymal precursor cells). Neither is a human dermal fibroblast.
Streeter & Cheema is the paper arguing such earlier values are too high.

Anyone pulling "HDF Vm" from this entry imports a 3–5× overestimate attached to
the wrong species and cell type, under the citation of the paper that corrects it.
Flagged `DO_NOT_USE_AS_HDF` in the ledger.

### 2.4 The Kawai correction — not verified, and structurally odd

Every route to `10.1016/j.matt.2025.102162` failed in this pass. I am not
repeating the numbers as verified. But a flag is visible without the text: a pure
mg→g unit correction scales *both* values by 1000, whereas the reported pair
scales the dermis value by 100 (5.4 mg → 0.54 g) and the skin value by 1000
(0.13 mg → 0.13 g). That changes the dermis:skin leakage ratio from 41.5× to
4.15× — a tenfold change in precisely the quantity you would use to judge whether
adding an epidermis improves barrier function. **Resolve the correction text
before any barrier target is set from it.**

### 2.5 One thing that did line up

Three measurements that were never combined by their authors agree. Taking
Stücker's in vivo flux (3.94 × 10⁻⁷ mol m⁻² s⁻¹ at 163 Torr) with the aqueous
oxygen solubility gives a surface conductance lower bound of **1.80 × 10⁻⁶ m/s**.
Dividing Hatcher & Plachy's stratum corneum diffusivity (3 × 10⁻¹¹ m²/s) by that
implies a barrier **16.6 µm** thick — squarely in the known forearm stratum
corneum range. That is a genuine three-way consistency check. It is not
validation: both inputs were access-blocked here, and a lipid-rich barrier
partition coefficient above 1 scales the implied thickness up proportionally.

---

## 3. The computation

Steady 2-D reaction–diffusion (Michaelis–Menten, finite-volume, Newton with
backtracking, sparse direct solve) on the unit cell of the Rhee geometry: from a
channel wall across the 200 µm half-spacing to the symmetry plane, from the
impermeable chip floor up to the air-exposed surface, with a dermal layer and a
viable epidermal layer. Robin boundaries at the wall and at the air surface; the
surface conductance lower bound is derived from Stücker rather than invented.
972 cases over the documented ambiguities: 4 epidermal demand readings × 3
readings of Rhee's cell density × 3 dermal diffusivities × 3 surface states ×
3 wall permeabilities × 3 construct thicknesses.

**Verification: 6/6 predeclared checks pass.**

| Check | Result | Declared limit |
|---|---|---|
| Zero demand gives a uniform field | max deviation **0.0** | < 1e-12 |
| Analytic zero-order slab limit | **4.85e-8** of inlet | < 2e-3 |
| Mass balance, worst case | **7.08e-10** relative | < 1e-8 |
| Mesh refinement, 4 corners doubled | **8.36e-3** of inlet | < 1e-2 |
| Bounded concentrations | 0 ≤ C ≤ C_in | — |
| Surface conductance monotonicity | holds | — |

All values read from `pf1s_results.json`, not from recollection. One caveat worth
stating: the mesh refinement error (8.36e-3) passes its declared 1e-2 limit but
not comfortably. The reported minima are good to roughly ±1% of inlet
concentration, which is far finer than the 3240× parameter spread that dominates
the result, but it is not a converged-to-machine-precision figure and should not
be quoted as one.

Numerical verification only. Not biological validation, and no experiment was run.

### What the evidence identifies — tested, not asserted

I set out to show that the problem reduces to the Thiele modulus
φ² = q·h²/(D·C), so that demand and diffusivity are not separately identifiable.
**The test refuted the reduction for this geometry and I am reporting that
rather than the claim I expected.**

- Homogeneous slab: scaling demand and diffusivity together moves the field by
  **1.4 × 10⁻⁷** — the reduction holds to solver tolerance.
- The actual layered construct: the same scaling moves the minimum by
  **33% of inlet concentration**. φ² alone does *not* close the problem.

The layered case is governed by at least φ²_epi *together with* the layer
conductance ratio D_epi/D_derm, the wall and surface Biot numbers, and the
thickness ratios. The practical consequence is **stronger** than the single-group
claim would have been: an experiment reporting a skin "qmax" without
independently pinning epidermal thickness, epidermal diffusivity, *and* the
dermal diffusivity underneath has not produced a number that transports to the
next geometry.

### Where the boundary sits

| Surface state | Demand at which this geometry first breaches PF0's line |
|---|---|
| Sealed | 0.023 mol m⁻³ s⁻¹ |
| Barrier intact (Stücker-derived) | 0.029 |
| Open air–liquid interface | 0.090 |

Literature readings: 0.003 (textbook resting skin), 0.00972 (Balu as µmol),
0.100 (Balu recomputed), 9.72 (Balu as printed). The boundary sits *inside* the
unresolved span, between the second and third readings — two readings of the
same paper.

### Where the oxygen comes from

| Demand | Atmospheric share, barrier intact | Atmospheric share, open interface |
|---|---|---|
| 0.003 | 6.5% | 37.8% |
| 0.00972 | 8.8% | 51.6% |
| 0.100 | 8.2% | 61.7% |

Barrier state swings the atmospheric contribution by roughly **7×**. A skin
construct's barrier matures over days at an air–liquid interface, so the oxygen
budget of a maturing construct is not constant — and PF0, which has no free
surface at all, cannot represent any of this.

---

## 4. A critical read of PF0 — not an endorsement

1. **The β result is one sweep read three times.** PF0's own degeneracy check
   confirms flow and β enter only as the product Q·β. So "16/19/20 of 48" is not
   three findings; it is the same 48-case flow sweep relabelled. Reporting it as
   a capacity result overstates it, and PF0's own text half-says this. Say it
   fully.

2. **PF0's strongest result is underweighted.** 72 of 144 cases fail the local
   necessary bound *regardless of flow or capacity*. Half the design space is
   excluded by geometry and demand alone, before any carrier question arises.
   That deserves to be the headline, not the β table.

3. **"Conservative liver-like demand" is wrong in one direction.** 0.02 mol m⁻³ s⁻¹
   is ~7× above textbook resting skin, but ~5× *below* the only in vivo human
   epidermal figure recoverable here (0.1). PF0 is not a conservative upper bound
   for skin; it is mid-range, and the layer that governs sits above it.

4. **The threshold sits in the worst possible place.** 0.05 mol m⁻³ against
   Km = 0.028 puts the pass line at ~1.8 Km — the steepest part of the
   Michaelis–Menten curve, where classification is maximally sensitive. My sweep
   confirms it: at high demand, a 10× change in Km flips the result from
   2.2 mmHg (fail) to 39.8 mmHg (pass). **No packet source supplies a Km for any
   skin cell.** This is the least-evidenced number in the whole ledger and PF0's
   headline count depends on it.

5. **The monotonicity failure is the most interesting result in PF0 and is
   treated as a footnote.** Higher wall permeability lowering the downstream
   minimum at low flow — two reversal groups surviving refinement — means
   "improve the wall" is not monotonically safe along a channel. That is a real
   design hazard and deserves its own study rather than a `False` in a checks
   dict.

6. **One-sided planar geometry with no free surface is not a conservative
   simplification of skin.** It is a different problem. Skin has two supply
   routes and the second one supplies 6–62% of the load.

---

## 5. Two concrete changes to the first perfused skin module

### Change 1 — Stop designing the channel lattice around the dermis; instrument the surface instead

At 400 µm spacing the dermal Thiele modulus is 0.0024–0.048. Tightening channel
spacing below ~400 µm buys essentially nothing for oxygen, and the cost is real:
more wall area, more printing resolution, more failure modes. Meanwhile barrier
state moves the atmospheric share from 6% to 62% and nobody is measuring it.

Concretely: build v1 with (a) a **removable oxygen-impermeable lid** so the
surface boundary can be switched between open and sealed without disturbing the
circuit, and (b) **inline inlet and outlet oxygen sensors** on the perfusion
loop. Spend the engineering budget there rather than on lattice density.

### Change 2 — Make every oxygen measurement carry the three quantities that make it transportable

The identifiability test says a measured consumption rate is not transportable
without epidermal thickness, epidermal diffusivity, and the dermal diffusivity
beneath it. So pair every oxygen run with a **fixed-section histology measurement
of viable epidermal thickness and viable cell density at the same timepoint**,
and record the matrix formulation as-hydrated rather than as-mixed. Without
these, the module will generate the same unusable kind of number the literature
already has — which is exactly how Rhee's construct ended up with a confident
oxygen claim and no oxygen data.

---

## 6. Measurable failure criterion

**Declare this before the run.**

With the circuit at design flow and inline inlet/outlet oxygen sensors, run the
construct in two states, changing nothing else: **(i) air surface open**,
**(ii) surface sealed with the oxygen-impermeable lid**. Measure circuit-delivered
oxygen as Q·(C_in − C_out) in both states, and total construct oxygen consumption
independently by sealed-chamber respirometry on a sister construct.

**The module fails if either:**

1. **The budget does not close.** Circuit delivery plus inferred atmospheric flux
   differs from independently measured total consumption by more than **20%**. A
   budget that does not close means the transport model is wrong, and no
   threshold result from it should be believed.

2. **Sealing fails to shift the load.** Circuit-delivered oxygen rises by less
   than **30%** when the surface is sealed. PF1-S predicts a rise of **33–101%**
   across every demand reading that is not already excluded. If the rise is
   smaller, either the circuit is already saturated and cannot absorb the
   atmospheric load — in which case the construct will go hypoxic the moment it
   is covered, which is the operating condition that matters for skin on a
   structure — or consumption is far below assumption and the model is wrong.
   Both are informative; both are failures of the current design basis.

This criterion deliberately needs **no viability threshold**, because no source
establishes one for skin, and Mieremet et al. 2019 is direct evidence that skin
function is not monotone in oxygen — lower external oxygen moved several features
*closer* to native skin. A criterion built on consistency rather than on an
invented pass line is the one this evidence can actually support.

It also tests one bounded thing. It does not establish whole-body feasibility,
long-term viability, repair, sensation, or that any of this scales. It establishes
whether we know where the oxygen in one module is going.

---

## 7. What is still missing

1. The Kawai 2025 correction text — blocked on every route here. Needed before any
   barrier target.
2. Stücker 2002 Table 1 at donor level, and Hatcher & Plachy's full methods —
   both access-blocked. The surface conductance bound and the 16.6 µm cross-check
   rest on them.
3. **An oxygen solubility / partition coefficient for stratum corneum and for a
   hydrated collagen construct.** Nothing in the packet supplies one. Diffusivity
   alone is not permeability, and this gap is currently papered over by assuming
   the aqueous value.
4. A Km, or any oxygen-dependence curve, for human dermal fibroblasts or
   keratinocytes. Streeter & Cheema report a rate, not kinetics.
5. Rhee's construct thickness and epidermal thickness — neither reported.
6. Whether Rhee's 10-in/12-out flow imbalance implies a transmural flow large
   enough to matter. Neither model represents it.

A matched dataset for a single named construct remains unavailable. Until one
exists, this stays a sensitivity and identifiability study, and should be
labelled as one wherever it is cited.
