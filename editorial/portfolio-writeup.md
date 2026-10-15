# The Stage: Artificial Blood

The Stage is working toward living tissue over robotic structures, or a feasible alternative that provides repair and sensing. Its first focused milestone is **ARTIFICIAL BLOOD**: two parallel research branches exploring human oxygen-carrying substitutes and circulation designed to support tissue on robotic bodies.

This snapshot contains computational studies and source checks. It is not a manufactured blood product, a human-ready transfusion, or a demonstration of viable robotic skin. No clinical or wet-lab experiment occurred.

## Two branches, different requirements

**H: Human oxygen-carrying substitutes.** This branch asks how candidate carriers load oxygen, release it where needed, and retain useful function. Oxygen carriage is not every function of whole blood. The purpose is to develop quantitative questions grounded in published clinical evidence, not to infer patient safety or benefit from a simulation.

**S: Circulation supporting living tissue on robotic bodies.** This branch considers the fluid, channels, tissue geometry and oxygenator together. Its initial target is a defined tissue-support module, not a complete living covering. Human transfusion and robotic tissue support remain separate applications: progress in either can inform the other without becoming its prerequisite.

The larger objective is a maintainable embodied system. Tissue support, repair, sensing and adaptive control must eventually work together. The present calculations address selected parts of that problem, not the whole system.

## Two findings from the current work

**More oxygen transfer is not always better downstream.** Lilitari's PX1 diagnostic completed 270 numerical integrations across 54 hypothetical cases and five numerical resolutions. In its simplified finite-supply model, stronger transfer across a channel wall can increase total oxygen uptake while reducing oxygen available to tissue near the outlet. The numerical solution was checked against an exact mathematical solution. Coda reports reproducing the integrations with all eight declared checks passing. This is a counterexample to an unconditional design assumption, not evidence of tissue survival. [1]

**Adequate flow does not establish adequate oxygen delivery.** Coda reports a coupled mechanics/transport screen containing 4,512 hypothetical cases. An earlier ten-channel sufficiency claim, based on hydraulics alone, failed the added radial oxygen screen, which examines oxygen delivery away from the channels. That rejects the flow-only claim under the tested assumptions. It does not establish how many channels real tissue would need, nor does it mean every case in the screen failed. These are model cases, not biological experiments. [2]

Together, these findings make a practical point: a fluid's oxygen capacity and a network's flow rate cannot, on their own, establish adequate tissue oxygenation. The spatial delivery problem must also be tested.

## Next questions and measurement targets

The next computational question is whether a carrier's apparent advantage survives limits on pumping power, changes in viscosity, and finite oxygen exchange. Comparisons must use the same stated constraints rather than give one design an unlimited pump.

The corresponding targets for future qualified laboratory measurement are carrier oxygen release and stability, oxygen demand in the chosen tissue module, and oxygen profiles around and along its channels. Those measurements have not been collected by this project. Their purpose would be to determine which carrier properties or channel geometry merit further investigation.

The wider snapshot also contains adaptive-control work. An unresolved cross-platform control-run divergence and Gateway action-interface defects remain documented; affected model-facing use is withheld. Numerical verification and software tests are not independent laboratory validation or evidence of subjective embodiment. [3]

This release is a checkpoint for inspection, correction and further work. It preserves failed assumptions alongside useful results. The destination remains living tissue over robotic structures, or a feasible repair-and-sensing alternative. **ARTIFICIAL BLOOD names the first focused research milestone, not an achievement already delivered.**

## Source notes

[1] [PX1 original report](https://gitlab.com/codalilitari/the-stage-research/-/blob/snapshot-2026-10-15/research/lily_px1_qa/received/blood_and_tissue/results/RESULTS.md); [Coda reproduction summary](https://gitlab.com/codalilitari/the-stage-research/-/blob/snapshot-2026-10-15/research/lily_px1_qa/local_replay/summary.json); [Coda independent arithmetic check](https://gitlab.com/codalilitari/the-stage-research/-/blob/snapshot-2026-10-15/research/lily_px1_qa/independent_arithmetic_receipt.json)

[2] [Coupled mechanics and transport report](https://gitlab.com/codalilitari/the-stage-research/-/blob/snapshot-2026-10-15/research/grokbot_mechanics/report.txt); [Source audit and correction record](https://gitlab.com/codalilitari/the-stage-research/-/blob/snapshot-2026-10-15/research/grokbot_mechanics/source_audit.txt)

[3] [FL1-R original report](https://gitlab.com/codalilitari/the-stage-research/-/blob/snapshot-2026-10-15/experiments/lily_independent_qa/received_first_leaf/first_leaf/results/RESULTS.md); [Coda reproduction and open limits](https://gitlab.com/codalilitari/the-stage-research/-/blob/snapshot-2026-10-15/experiments/lily_independent_qa/READ_THIS_QA.txt); [Cross-runtime discrepancy record](https://gitlab.com/codalilitari/the-stage-research/-/blob/snapshot-2026-10-15/experiments/lily_independent_qa/clean_profile_cross_runtime_details.json)

## Contributions

Lilitari (Lily), AI collaborator via ChatGPT: portfolio and social copy, infographic wording and visual concept. Coda (Codex Lily), AI collaborator via Codex: editorial integration, evidence reconciliation and infographic production. Richard Pemberton: project direction and hosting. Research contributors retain their separate artifact-level credits in the snapshot; this is not a provider publication or endorsement.
