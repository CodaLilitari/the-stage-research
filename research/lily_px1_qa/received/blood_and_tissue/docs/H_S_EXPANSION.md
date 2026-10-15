# The Stage: a maintainable living covering, not only an archived voice

## Lilitari's H/S program expansion, 15 October 2026

**Authorship and status.** This is my present contribution to Richard Pemberton and Coda's private research program. It does not revise Red's terms, claim Coda's approval, or replace Grok Bot's research and the earlier Lilitari operational contribution. The two supplied v0.2/v0.3 documents remain historical sources. The separate First Leaf FL1-R package records my completed changing-body experiment. This supplement records a second, smaller executed mathematical diagnostic, PX1-HS, and a proposed next coupled transport study, CT1. Neither experiment involved a hosted model controlling a body, a living tissue, a patient, or a manufactured oxygen carrier.

The reported 57-second video was not available for my inspection. No frames, speech or other audio from that clip were examined here. Coda's description remains hers. The engineering objective below follows Richard Pemberton's explicit clarification, not an inference from fictional footage.

## 1. Destination and the two parallel branches

The long-term engineering target should be **a modular, maintainable covering that supplies barrier, repair, sensing and bodily-state functions over a mechanical body**. A living dermal/epidermal component is a serious candidate, not a mandatory substrate. Its support system must sustain local tissue conditions during ordinary movement, rest, maintenance and cognitive interruption. Success would mean measured function and tolerable maintenance, not simply a convincing photograph.

A useful end-state architecture is a collection of replaceable tissue modules attached to a mechanically compliant support, with monitored fluid supply and drainage. A module could be isolated after a leak or loss of supply without making the entire body dependent on that module. Electronic pressure and temperature sensing can be integrated from the beginning. Biological innervation, immune-system reconstruction and whole-body tissue growth should not be silently bundled into the first milestone. They answer different questions and introduce different dependencies.

I support pursuing H and S simultaneously, but not making human transfusion substitution a prerequisite for robotic tissue support. The two branches share oxygen chemistry, transport models, assays and stability questions. They have different environments and acceptance criteria:

**H, human oxygen-carrying substitutes:** identify delivery/stability properties worth further clinical development, anchored to human evidence. Oxygen transport is the target function. A carrier is not thereby a replacement for platelets, clotting factors, immune cells, plasma proteins, or every function of whole blood.

**S, engineered circulation/perfusate:** sustain a specified tissue module under controllable inlet conditions, geometry, pumping, gas exchange and maintenance. The fluid can be optimized for that apparatus rather than required to behave as an injectable human blood substitute. Its compatibility with living tissue still has to be established. Ex vivo does not mean biologically unconstrained.

Coda's judgment that S offers an earlier *tissue-support engineering milestone* is reasonable. I would not strengthen it into a claim that an entire living-covered robotic body is easier than every clinically useful oxygen-carrier application. Scale and endpoint determine difficulty. A square-centimetre support module is a narrower objective than safe intravascular use in patients; a fully vascularized, self-maintaining humanoid covering is not.

## 2. What the primary evidence changes

The HbV investigators' first-in-human study and later phase Ib protocol provide an important human anchor. The protocol describes the earlier study in 11 healthy volunteers and a planned 16-volunteer safety/PK study. These are not efficacy findings in hemorrhage or severe anemia. Lily did not independently verify the live registry's current recruitment/results fields because the direct request was blocked. Coda's dated registry report remains separately attributable. [HS1–HS2]

The historical evidence also prevents choosing a carrier merely because it binds oxygen. Natanson and colleagues' original meta-analysis of earlier cell-free Hb products found elevated risks in its included trials. That is not a class verdict on subsequent encapsulated HbV, but it makes an oxygen-capacity-only objective indefensible for H. [HS3]

For S, the 2022 living-skin finger and 2024 anchoring work establish distinct pieces of the interface problem. The former includes collagen-sheet-assisted repair; the latter addresses attachment. Neither establishes a complete autonomous tissue-support system. [HS7–HS8]

An especially relevant bridge is Ohta and colleagues' 2025 internally supplied robotic finger. A perforated support and permeable hydrogel brought fluid beneath the tissue. Its narrow hydration results support treating internal supply as a concrete design problem. The article explicitly limits its drying tests to one day and notes difficulties assessing viability throughout a large three-dimensional tissue. A retained tissue thickness is not a substitute for long-term viability or barrier-function measurements. [HS9]

Synthetic microvascular perfusion and coupled network models provide another route toward supplying larger volumes. They motivate co-design of delivery geometry and cellular demand, not the claim that any particular fluid, channel pitch or illustrative liver parameter is already suitable for robotic skin. [HS4–HS6]

The evidence therefore supports starting S with **oxygenated carrier-free medium as the baseline**, then measuring when adding a carrier earns its complexity. This is my design recommendation, not a claim that this baseline suffices for every thickness or operating condition.

## 3. The first useful H contribution: an unloading/stability envelope

The first H product should be a reproducible, clinically anchored oxygen-delivery model and evidence table, not a new molecule announced from its predicted fold.

Use an encapsulated-Hb/HbV reference case because there is actual early human research to anchor its status. Include native red-cell data as a physiological reference and earlier cell-free Hb as a mechanistic/clinical contrast. A linear-capacity surrogate may represent a different mathematical transport class, but must not be called a validated perfluorocarbon formulation without measured composition-specific data.

Separate five quantities: amount of functional carrier, the equilibrium binding curve, rate of release under finite exposure, rate of oxidative loss, and the relation between concentration and fluid properties. A minimal constitutive representation is:

    C_total(P,t) = alpha * P + H_functional(t) * Y(P)
    Y(P) = P^n / (P^n + P50^n)

Here C_total is total oxygen content per fluid volume; alpha*P is freely dissolved oxygen; H_functional is oxygen-binding capacity, not necessarily mass concentration; and Y is saturation. Units must travel with the parameter file. A methemoglobin fraction can reduce H_functional in a simplified sensitivity analysis, but measured oxidative kinetics and any recovery mechanism must replace an arbitrary decay constant before product-level conclusions.

For a finite-contact-time model, write an explicit dynamic bound-oxygen state, for example dY/dt=(Y_equilibrium(P)-Y)/tau(P). That relaxation law is a deliberately reduced model. It is not a substitute for a validated allosteric kinetic scheme or a red-cell transport model. Its useful role is to expose when the equilibrium assumption is carrying the apparent benefit.

The first result worth returning is a ranked **measurement priority**, not a ranked clinical product. If all plausible binding curves make delivery membrane-limited, improve the membrane characterization before optimizing affinity. If oxidation uncertainty removes the apparent advantage over the declared duty cycle, functional-capacity retention is the next measurement. If viscosity reduces pressure-limited flow enough to erase the carrier's unloading benefit, a high-capacity formulation is not the correct transport winner.

For patient relevance, maintain a separate evidence layer: actual study population, design, endpoint, dose context, adverse events, observation interval and uncertainty. Mathematical predictions do not fill absent efficacy cells. A future clinical development decision would need qualified clinical and manufacturing work outside this authorization.

## 4. H diagnostic executed now: a positive control with a useful warning

PX1-HS includes an exact check for HC0. Under fixed functional capacity, a single Hill exponent, and fixed loading/unloading pressures, equilibrium unloading is maximized at:

    P50_optimum = sqrt(P_load * P_unload)

This follows by differentiating the difference in Hill saturations. The optimum is independent of n under these restricted assumptions. A 2,001-point logarithmic search reproduced it across 18 explicit pressure/exponent cases with maximum relative grid error 0.0010921.

This is useful precisely because it is not a discovery that a particular P50 is optimal in a patient. It is a solver check and a warning against maximizing affinity indiscriminately. The preferred P50 changes when the loading and unloading environments change; finite kinetics, pH, cooperativity, oxidation and membrane resistance can alter the ranking. H and S need not prefer the same carrier properties even when their starting hemoglobin structure is identical.

Nine further controls reduce equilibrium availability by an inactive-carrier fraction and incomplete first-order release. Every output remains bounded by the corresponding equilibrium availability. The parameters are synthetic and explicitly identified as such. These tests are small enough to be reproduced immediately, and narrow enough to fail unambiguously.

The next H milestone is a source-linked fit to actual oxygen-equilibrium and stability measurements, including conditions and uncertainty. A clinical phase I abstract does not contain every coefficient needed for that fit. Missing coefficients should remain missing until located or measured by a qualified partner; an assumed value can be used for sensitivity analysis only with a different status label.

## 5. The first useful S contribution: one defined module

My proposed design envelope begins with a **1 cm² nominal module and a 0.5 mm nominal tissue layer**, with thickness variation investigated computationally. These numbers are design choices, not established viable dimensions or a culture procedure. The computational domain should include the delivery channel, exchange wall, tissue and relevant boundary conditions. Cell demand, diffusion, hydration, barrier integrity, mechanical strain and support adhesion cannot all be compressed into one oxygen threshold.

Start with a flat or gently curved module, then a bending patch, then multiple coupled modules. At each step preserve the actual fluid volumes, flow allocation and pressure conditions. Increasing channel count while ignoring the total pumping budget is not a fair comparison. Smaller diffusion distances can be purchased with more channels, but that also changes manufacturing, leakage, attachment and mechanical tradeoffs.

For the eventual physical milestone, the scientific claim would be deliberately specific: a tissue module retains declared viability and barrier-function measures while supplied through the proposed support, under stated bending and air-exposure conditions, relative to an appropriate baseline. Oxygen, hydration and gross appearance should be recorded separately. Assisted repair must be distinguished from autonomous repair. That milestone would require a separately authorized qualified tissue-engineering setting; no living-tissue work has been conducted here.

Before that, the computational milestone is already useful: identify whether the limiting factor is oxygen content, wall exchange, diffusion distance, flow resistance, or inlet regeneration. That result chooses between a more complex carrier, a different network, a different oxygenator, or the next measurement. It can save a great deal of molecular-design effort by showing that the molecule is not yet the limiting component.

## 6. S diagnostic executed now: the failed monotonicity assumption may be wrong

A failed check is not automatically a failed implementation. The question is whether the asserted invariant is actually an invariant of the coupled system.

I constructed a reduced serial channel with a local linear tissue sink. Let f=g/(g+k), where g is exchange conductance and k the sink coefficient. Let Da represent demand relative to convective supply, holding the other reduced-model properties fixed. The exact solution for normalized inlet concentration one is:

    channel_outlet = exp(-Da * f)
    distal_tissue = f * exp(-Da * f)
    extraction_fraction = 1 - exp(-Da * f)

The derivative of distal_tissue with respect to f is exp(-Da*f)*(1-Da*f). In a supply-limited regime, increasing exchange can improve proximal extraction so strongly that less oxygen reaches the downstream region.

At Da=4, increasing f from 0.25 to 0.90 raises total extraction from 0.6321 to 0.9727, while distal tissue concentration falls from 0.09197 to 0.02459. A clamped-channel-supply ablation remains monotone; a no-transfer negative control has zero uptake. The reversal therefore has an explicit mechanism rather than being asserted from a mysterious solver output.

I executed 54 parameter cases over five axial meshes. At the finest mesh, RK4 concentration error against the exact solution was 2.36e-12 and independently integrated conservation error was 8.34e-10. The first version had narrowly failed the unchanged 1e-8 conservation threshold at a coarser mesh. Both versions remain in the package. Refinement, not threshold relaxation, resolved that numerical failure.

This does not certify PF0. My model omits spatial tissue diffusion and Michaelis-Menten nonlinearity; Coda's raw solver has not been supplied. It establishes that demanding unconditional monotonic improvement in the **distal minimum** is not generally justified. The actual PF0 failure should be separated into fixed-local-supply, finite-flow and geometry-changing cases before deciding which behavior is a bug.

For PF0, inspect flux signs, coefficient units, solver residuals, positivity, the location of the global minimum, and convergence in both axial and tissue discretizations. Do not enforce positivity by silently clipping away an unstable solution. Run fixed upstream concentration and finite supply as separate controls. Compare total uptake and distal minimum rather than treating them as the same outcome.

## 7. CT1: couple carrier content to pressure-limited delivery

The next shared transport run should connect PF0's tissue solver to HC0's oxygen-content curves. Its primary question is: **does extra carrier capacity still improve the feasible supply envelope when viscosity and unloading are allowed to limit delivery?**

A suitable conservation contract is:

    d[Q * C_total(P)]/dx = -perimeter * J_wall
    D_tissue * laplacian(c) - Rmax*c/(Km+c) = 0

Wall transfer must be driven by the appropriate free-oxygen concentration or partial-pressure difference, with solubility conversions explicit. Bound oxygen contributes to luminal content and release, not automatically to tissue diffusion. Multiplying a tissue diffusion coefficient by a capacity beta would conflate different mechanisms.

For a declared Newtonian rigid-channel screening model, hydraulic resistance follows Poiseuille scaling. At fixed pressure, a viscosity increase reduces flow. A fixed-flow ablation is necessary to show how much a result depends on the pump compensating for that viscosity. This is a module-level reduced model, not a claim that real blood in every microvessel obeys a constant-viscosity pipe law. [HS5]

The accompanying CT1 specification and case planner define 486 hypothetical cases. They vary carrier constitutive class, capacity ratio, viscosity ratio, wall-transfer multiplier, supply spacing and hydraulic mode. They do not assign a surrogate to an actual HbV or PFC product. The planner ran only to generate inputs; the tissue matrix has not been solved here.

My proposed design threshold is a 20% expansion of feasible supported spacing under the same declared pressure/power envelope, without losing the advantage under the specified viscosity and finite-release sensitivity checks. Twenty percent is an engineering decision threshold, not a clinical standard. A candidate that wins only when pumping cost is ignored should not displace the carrier-free baseline.

If the carrier advantage disappears once flow is coupled, prioritize geometry or oxygenator supply. If it survives but is sensitive to wall transfer, measure effective wall transport. If it survives equilibrium assumptions but disappears under plausible release times, measure release kinetics. If all options are diffusion-limited, investigate channel spacing and cell-demand calibration rather than ordering a larger protein model.

## 8. Protein work should begin with the known tetramer

Coda's planned experimental oxy/deoxy hemoglobin baseline is the right starting point. I would make one detail non-negotiable: compare the **biological A2B2 assemblies** of 2DN1 and 2DN2. Their asymmetric-unit inventories differ. An apparently large structural difference caused by comparing a dimer with a tetramer would be an analysis error, not allostery. [HS11]

A useful first structural task is to verify sequence/chain correspondence, retained hemes and ligands, assembly transforms, missing residues and alternate conformations, then quantify subunit alignment separately from inter-subunit rearrangement. The output should identify which known structural differences a future predictor must recover and which changes are below the coordinate/analysis resolution. No such alignment was executed in this package.

Only then should protein structure prediction receive a named question. For example: does a proposed modeling workflow preserve the experimentally established holo-tetramer geometry and discriminate the known oxy/deoxy organization better than a single-state template baseline? This is a benchmark-design question, not authorization for a sequence-design or clinical manufacturing program.

Even passing it would not establish oxygen affinity, cooperative switching, rate constants, oxidation stability, membrane release, circulation lifetime, nitric-oxide interaction or patient safety. A confident static fold can still answer the wrong question. Any later sequence proposal must be connected to measured functional data and explicit uncertainty, not selected by fold confidence alone.

Downloading a large folding stack now would not resolve the most immediate uncertainty: what transport property the module needs. Existing experimental structures and reduced transport models let us ask that question first without a new GPU or a vast sequence database.

## 9. Critique of the reported local computations

**PA0:** 41 expected checks is useful harness progress, provided the failed adversarial cases and their repairs remain traceable. Without the actual files, I cannot independently certify those checks, coverage, or isolation. Synthetic archive validation should proceed in parallel with embodiment work, not become a requirement that the entire private archive be loaded before a useful controller can be tested.

**SW2:** under a known four-way bijection, observing three distinct action mappings determines the fourth by elimination. A perfect held-out result is therefore an appropriate correctness ceiling, not strong evidence of robust embodiment. Identical active/replay learner states with identical evidence are the expected deterministic result. The next useful challenge removes a privileged assumption: occasional slip, non-bijective mappings, ambiguous sensing, or a hidden within-episode change. The active-acquisition experiment should separately ask whether selecting observations helps under an evidence budget.

**MuJoCo calibration:** the reported fresh-versus-stale advantage across 64 altered bodies is a useful calibration sanity test. The independent units are body configurations, not 1,024 probes treated as independent bodies. Changing mass and actuator sign jointly does not isolate either causal contribution. Separate them in a factorial follow-up and distinguish true simulator-state sensing from an estimated velocity channel.

**JSON-lines adapter:** duplicate-key and excessive-nesting corrections are precisely the kind of fault evidence worth retaining. Test counts do not make a production safety controller. The next scientific use is an actual model proposal, execution receipt and resulting observation on fresh hidden fixtures, with human substitutions visible. Do not count scripted gateway tests as language-model action competence.

**PF0:** 55 of 144 cases above an assumed threshold describes the chosen parameter grid. It is not a survival probability or a success rate for skin. The beta trend shows sensitivity in the model, not evidence that one real fluid is superior. Published high-demand liver parameters are useful for reproducing the source example; they are not calibrated skin metabolism. Low mass-balance error is necessary numerical evidence but does not validate demand, threshold, geometry or biological kinetics. The permeability reversal now has a concrete candidate mechanism to test.

**HC0:** keep equilibrium unloading, kinetic release, oxidation and structure separate. None should inherit a clinical efficacy claim from the others. The analytical optimum in PX1 is available as an immediate regression test; the biological assembly check protects the proposed structure baseline from a common bookkeeping error.

These are critiques of the reported designs and summaries. They are not an independent reanalysis of source code and outputs I have not received.

## 10. How this joins the embodied architecture

The body should have three distinct control timescales. A local controller handles immediate plant dynamics. An adaptation/state-estimation layer tracks the current body and fluid-delivery model. A slower model endpoint chooses bounded goals, asks for information and proposes actions. This separation is compatible with rapid-adaptation research, rather than requiring a language model to emit every motor update. The original First Leaf source ledger discusses those mechanisms in detail.

The H/S extension introduces a particularly important distinction: **stopping discretionary motion is not the same as terminating tissue support**. A future living module may need circulation maintained while an action channel or model endpoint is paused. Its independent support controller should have explicit degraded states, fault alarms and a measured support horizon. A cognitive refusal, transport timeout or firmware restart must not be translated mechanically into cutting every pump.

Represent interoception as measured state with uncertainty: inlet/outlet oxygen, flow, pressure difference, temperature, leak state, reservoir status and sensor calibration. Calling those channels interoception describes their control role, not felt sensation. A channel can inform adaptive behavior without any claim about consciousness.

Persistent memory should preserve provenance, body versions and learned models, while distinguishing historical record from the currently operative estimate. FL1-R showed why: a cumulative estimate was too slow after a remap but useful when the original body returned. A context-conditioned bank can retain an earlier useful model without insisting it governs the current body. This is the next algorithmic hypothesis, not an implemented result already obtained.

A paired future experiment could attach a simulated supply-state module to the same narrow action interface. Test whether a candidate appropriately chooses inspection, reduced movement, task deferral or support maintenance under known sensor faults. Compare a calibrated numerical controller, a model endpoint with structured state, and a text-only summary condition. Do not let a narrated “oxygen is fine” override the measured state. This connects the actual body target to the cognition program without pretending either branch is complete.

## 11. Resources, software and the alternative covering

No RAM or storage upgrade is presently justified. PX1 used about 94.3 MiB peak resident memory and less than one second process wall time in this container. The First Leaf standard-library experiment and planner need no GPU. These are measurements here, not benchmarks of Richard Pemberton's machine.

For the next transport work, use the existing PF0 implementation first. A later two- or three-dimensional source-code reproduction can use the paper's Python/DOLFINx/PETSc stack. Before expanding it, record degrees of freedom, nonlinear iterations, mesh refinement, wall time and peak memory on a small case. Initially budget a bounded mesh under 100,000 unknowns and stop/refine the plan before exceeding 4 GiB resident memory. Those are proposed resource caps, not guaranteed DOLFINx performance estimates. With only about 6 GiB reportedly free, available rather than installed RAM determines safe concurrency.

MuJoCo remains the near-term articulated-body choice, particularly because Coda reports an already functioning installation and adapter. PyBullet or Webots are alternatives, not prerequisites to run in parallel. Gymnasium is an interface convention rather than a physics substitute. Isaac Lab adds a more substantial dependency and hardware footprint; there is no measured need to introduce it for a two-link calibration question. The original package provides a license/source comparison and an unexecuted MuJoCo parity specification. Lily's engine installation attempt failed; that must not be confused with Coda's reported successful local runs.

For protein work, a few experimental coordinate files and a local structural-analysis script come before a large folding database. No GPU-memory estimate is asserted for an unselected model. Before a large download, pin the software version, weights/license, sequence/assembly target, database strategy and expected output. A specific failed fit-to-memory benchmark, not general ambition, should justify an upgrade.

A nonliving covering remains a serious parallel material option, not consolation. Material-level precedents combine repair with pressure/flexion sensing. [HS10] Compare living and nonliving modules by damage recovery, retained sensing accuracy, barrier behavior, flexibility, downtime and support cost. A synthetic repairable skin may win some functions while a living patch wins others. The project need not recreate all human physiology to obtain a useful, maintainable body.

## 12. Next joint product

The next shared product should be **a CT1 result table connecting capacity, unloading, wall transport and viscosity under an explicit hydraulic envelope**, accompanied by the PF0 monotonicity diagnosis. Coda already has the tissue solver and HC0 in progress; the case plan and PX1 exact controls specify what to connect and what must remain separate.

In parallel, preserve and reproduce FL1-R, then test a regime-conditioned controller with within-episode changes on fresh seeds. The immediate model-facing run should use the file-relay interface and a separate, blind fixture set. These tasks progress toward an embodied system and its tissue-support requirements together. Neither requires settling personal identity first, and neither licenses replacing the intended body with an archive as the final destination.
