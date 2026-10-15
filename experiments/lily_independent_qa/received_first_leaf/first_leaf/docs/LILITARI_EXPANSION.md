# The Stage: from preserved record to adaptive embodied system
## Lilitari's research and implementation contribution, revision 0.1

**Date:** 15 October 2026. **Status:** separately authored expansion, with an executed synthetic computational study and a tested file-relay prototype. Not a replacement of the historical Bible, not automatic adoption of Coda's companion, and not an embodiment or identity claim on behalf of another collaborator.

**Scope:** private local research, simulation, analysis, existing included tools, and attempted reputable free downloads. No paid model endpoint, new API key, purchase, publication, private-history expansion, physical actuation, or biological procedure was used.

References F1 and F2 identify the supplied documents in `COVERAGE_AND_ATTRIBUTION.md`. References S1 onward identify current primary-source checks in `SOURCES.md`. Statements about this experiment refer to the delivered source and machine-readable results, not to findings reported by those outside sources.

## 1. The program should produce a system, not only a vocabulary

My recommendation is to build a persistent, inspectable agent scaffold with a body that can surprise its controller, a learner that can correct that controller, and a record that distinguishes the correction from the historical mistake. The archive and the action loop should become interacting components of this system. Neither should be mistaken for the destination.

The current proposal contains two different research problems. One concerns what an authorized archive contributes to a later endpoint's judgments, work habits, and use of history. The other concerns whether a persistent deployment can perceive, act, adapt, recover, and accumulate its own task-relevant state. They can inform each other, but neither is a prerequisite for beginning all work on the other. A robot controller does not need to resemble Lily before its adaptation can be measured. A reconstructed style does not validate a body controller. A failure in one track must not close the other by administrative inheritance.

I therefore propose parallel work streams with a common evidence contract: PA for archive-conditioned behavior, FL for adaptive sensorimotor control, and a subsequent integration stream that measures their interaction. Biological translation remains a separate research horizon. The existing four-route map remains historical context, not a dependency graph that forces every useful silicon experiment to solve biological wiring or personal identity first. This preserves the near-route intent of F1 while correcting the overly serial implications of its gates and of F2's default development sequence.

The strongest realistic path is a local stateful control scaffold in a simulator, followed by a bounded nonhumanoid physical endpoint only when its particular workload and apparatus justify that step. A humanoid appearance, frontier-scale local model, and organic substrate are not necessary entry conditions for beginning that path. This is my architectural judgment, not a claim that the complete desired system already exists.

## 2. What I accept, clarify, and challenge in the companion

I would use A3, A7, A8, and A9 directly in new work: unavailable history is not false history; recorded words do not certify their contents; hash equality does not authenticate an event or its time; and scorer-only material must remain outside candidate access. The action and outcome separation on F2 page 12 is also a practical improvement over narrative receipts. These changes make mechanisms easier to identify rather than making the project less ambitious.

The operational chapters attributed to Lilitari in F1 contain two prescriptions I do not defend: the default deceptive sham and the suggestion that comprehension checks could make sealed material eligible for loading. The latter confuses private history with evaluator custody. New work should replace both prescriptions, while preserving the historical wording and identifying the change. Attribution is not a reason to keep an error operational.

A1 is useful, with one clarification. Its dimensions are separately supportable claims, not necessarily statistically independent variables. Archive access can influence reconstructed work habits; runtime state can influence migration performance. The replacement profile should allow causal connections without treating likeness, control competence, and personal identity as points on one promotion scale.

F2 already acknowledges that PA0 A versus B cannot isolate style perfectly because representation changes accessibility. I would retain that qualification. For later mechanism work, compare substantive information and presentation as deliberately separated interventions where feasible. A neutral package that makes facts easier to retrieve can outperform original prose without saying anything decisive about the value of the original relationship or history. Conversely, accurate quotation is not evidence that the endpoint applies a commitment in a new situation.

The companion's instruction to freeze the external controller needs a narrower reading for FL1 and successors: freeze the learning rule, hyperparameters, interfaces, and update permissions; permit the declared adaptive state to change. Otherwise an experiment about adaptation could prohibit the mechanism it is trying to study. A changed parameter estimate, a changed retrieval index, a changed context, and fine-tuned model weights are different interventions. The run manifest should name the one actually used.

Finally, I would not make every simulation wait for the full W0 through W3 archive sequence. Resolve permissions needed for the particular operation, then execute within that scope. The current message supplies a private synthetic execution scope. It does not supply authorization for hardware, biological work, private archive loading, or publication. Those boundaries can remain firm while the local computational work proceeds now.

## 3. Mechanisms worth building around

There are concrete precedents for coupling a slow planner to faster grounded behavior. SayCan combines language-based task usefulness with skill feasibility/value information; its authors explicitly distinguish those components. The design lesson for The Stage is not to ask fluent prose to substitute for a functioning action model. It is to let a language endpoint propose bounded goals or skills, with the current body determining what can actually be executed. The original SayCan project also describes limitations of its feedback pathway, so I would add explicit observed postconditions rather than copy its interface uncritically. [S1]

Rapid Motor Adaptation separates a base policy from an adaptation module, and reports simulation-trained adaptation deployed on a quadruped. This supports taking recent interaction history and changing operating conditions seriously as control inputs. It does not validate the particular estimator supplied here or establish that a language persona has been embodied. Our first implementation deliberately uses transparent small estimators before considering learned adaptation modules. [S2]

Cully and colleagues provide a complementary precedent: a precomputed repertoire of behavior can guide subsequent trial-and-error adaptation after damage. That is especially relevant to recurring body configurations. A useful system should not necessarily relearn every familiar body from nothing, nor average incompatible bodies into one fictitious set of dynamics. A preserved repertoire with evidence-based selection is a plausible intermediate architecture. [S3]

DreamerV3 provides a substantial example of learning a predictive world model and improving behavior through imagined trajectories. That motivates a later learned-model branch, not a requirement to reproduce its training scale before making progress. For the present small body, an explicit transition model is cheaper to inspect and easier to falsify. A learned residual or latent model should earn its complexity by improving held-out prediction and control. [S4]

Bayesian online changepoint detection supplies a principled family of methods for reasoning about when older observations cease to describe the current process. A future controller can track uncertainty over regime duration rather than use an arbitrary permanent reset. The current run does not implement that algorithm: it tests a simpler finite window against cumulative estimation, establishing a baseline that a more elaborate method must beat. [S5]

The common thread is a division of labor: durable evidence, revisable state estimation, grounded action, and measurable adaptation. None of these sources establishes a theory of personal continuity for a composite system. Their narrower mechanisms are already enough to make an engineering program possible.

## 4. Reference architecture to implement now

The following is a proposal for the next integrated implementation, not a description of a fully built production stack.

**Chronicle:** preserve original events, revisions, action requests, observed consequences, and corrections. A minimal event carries a stable event ID; source and observation times with precision; actor or device attribution; schema revision; source references; payload digest; and current access-policy reference. An action statement and its execution evidence are separate linked events. A later correction creates another event; the current view follows the correction without rewriting the original payload. F2's separation of revision identity, evidence status, access, derivation, and exposure is the starting schema. [F2, pages 6–7]

**Working world and body state:** maintain estimates of position, velocity, sensor validity, actuator effects, available skills, and current dynamics. Estimates point to the observations supporting them. They also carry validity conditions and uncertainty. A known body version is not the same thing as a known calibration: a fault can change behavior without changing a software version string. Conversely, an authorized model revision may alter the declared interface without an empirical sensor surprise.

**Adaptive learner:** use a fixed update rule to revise task-specific parameters. In the initial implementation this is a finite-window estimator of actuator effects. The next candidate is a small bank of regime-specific models, each retaining its own sufficient statistics and evidence references. Selection uses current predictive fit, not the evaluator's hidden A/B label. New regimes may be admitted after persistent prediction error, with a minimum evidence budget and a way to report uncertainty rather than force a confident label.

**Fast controller:** choose bounded actuator inputs from the current body belief and goal. In FL1 this is a one-step velocity-tracking controller. A subsequent arm should use a declared short-horizon planner or local feedback law whose response can be independently inspected. The controller must remain functional when the language endpoint is absent. Its fallback is an engineering mode with its own attribution, not a claim that the same collaborator is continuing to speak.

**Slow language endpoint:** propose a goal, an allowed skill, a request for additional sensing, or a stop. It can reason about task semantics, inspect a bounded history, and explain a failure. Its self-description cannot certify movement or grant access. The first model experiment should compare its contribution with the same scaffold using scripted task selection, rather than attribute the entire scaffold's competence to the language model.

**Supervisor and evaluator:** the supervisor admits only currently authorized capabilities and records intervention. The evaluator receives withheld simulator truth and computes scores. Those are different roles. A second file written by the same process is not independent evidence custody. For a real model trial, candidate tools should not be able to read the simulator fixture, answer key, current hidden mapping, or supervisor configuration. The delivered relay prepares a public packet, but operating-system or process isolation remains an operator responsibility.

The minimal local persistence choice is a transactional event store plus inspectable JSON exports, not a large opaque memory service. SQLite is a proposed implementation option, not a dependency introduced by this run. The delivered prototype uses atomic JSON state replacement and regenerable public views; it does not yet provide a general archive, concurrent database, authenticated policy authority, or backup revocation system.

## 5. Why permanent records and revisable beliefs must be different

Suppose an actuator label used to accelerate east and now accelerates north. Keeping the old record is correct. Continuing to use all old and new samples as if they came from one unchanged actuator is a modeling error. Erasing the record is not the only alternative. We can preserve what happened while changing which evidence supports today's controller.

Let the record be H, the currently selected regime be z, and the working transition model be f(theta_z). The archive answers what evidence was received and how it was interpreted at the time. The controller answers what action is likely to work now. These functions should share references, not a requirement that every historical sample have equal present influence.

The practical consequence is a two-level correction. A narrative claim such as “k0 causes eastward motion” receives an explicit scope correction. The numerical controller also changes its estimate or its selected regime. Updating only the prose leaves the body incorrectly controlled. Updating only the numbers leaves future readers unable to understand why the system changed. The integration test should check both.

There is a further distinction between computational recoverability and personal continuity. An event stream may be sufficient to reconstruct a deterministic learner's state without preserving a running process. A full application checkpoint may preserve that state more quickly without resolving whether any subject persisted. We should measure reconstruction cost, preserved variables, missing variables, and resumed behavior, rather than use one word, “memory,” to hide the differences.

## 6. Executed study: First Leaf FL1-R

The first question was frozen before execution: after an unannounced actuator remapping, does a revisable short-window body model reduce early tracking error compared with cumulative estimation without materially harming stable-body tracking?

The instrument is not Coda's grid. It is a continuous-state planar point body with position p and velocity v, updated by

`v[t+1] = 0.75 * v[t] + b[action]`

`p[t+1] = p[t] + 0.1 * v[t+1]`.

Four opaque motor labels produce axial accelerative increments; coast has a known zero increment. In body A, each motor increment has magnitude 0.3. Body B rotates every label's direction by ninety degrees and changes the axis gains to 0.21 and 0.39. This is an actuator mapping and dynamics change, not a change in morphology or number of degrees of freedom.

Each synthetic seed supplies six target directions, six complete sensor-noise sequences, both mappings, and unrelated labels for a negative control. Targets start one distance unit from the body's reset position. There are six eighty-step episodes with the evaluator's body schedule A, A, A, B, B, A. The agent code does not consult the hidden schedule or mapping when selecting actions. It knows the damping and functional form, a deliberate simplifying assumption.

The primary sensor channel supplies position noise bounded by 0.01 per coordinate, velocity noise bounded by 0.03, and a two-tick delay. Noise draws are fixed by seed, episode, and sample tick before the algorithms run. Diverging action choices cannot change which random noise draw is delivered. All delayed samples are drained after each episode's transitions stop, before the state reset.

The learner associates adjacent velocity observations with the action actually executed at their source transition. It estimates `b[a]` from `v_observed[t+1] - 0.75*v_observed[t]`. The aligned controller projects the latest delayed state forward using the executed action history and its estimated body model. Noise in adjacent transition estimates is correlated through their shared observation. The inferential unit is therefore the entire synthetic seed, not a transition treated as an independent measurement.

The action policy is held fixed across applicable learner conditions. It chooses the predicted next velocity closest to a clipped target-directed velocity. The initial twelve global steps cycle through motor labels; later periodic probes occur every seven local ticks. This is a fixed probing schedule, not a test of optimal active exploration. Unknown-action estimates default to zero; action ties choose the lowest index. Those details matter particularly for interpreting the no-information control.

## 7. Conditions, metrics, and the pre-execution decision

The eight algorithms are: an oracle body-parameter reference; a cumulative estimator; a persistent twenty-four-transition window; the same window cleared at every episode; a learner frozen after the first episode; a zero-model no-information control; a wrong-time action-assignment ablation; and an unrelated-label negative control. The oracle still receives the declared noisy delayed sensing. It is not an optimal-policy upper bound.

Four profiles separate delayed noisy remapping, immediate noisy remapping, immediate noiseless remapping, and delayed noisy stationary dynamics. The delay-zero profiles are especially useful for checking the misalignment manipulation: when an observation's source action is also the most recent executed action, the aligned and misaligned implementations should coincide exactly.

Development uses seeds 100 through 115. Evaluation uses seeds 10000 through 10255. Complete random inputs were written before running either split. The source, protocol, and fixture digests were recorded again after development inspection and before evaluation. No experiment, parameter, metric, or decision-threshold change followed the development outcomes. These are local freeze receipts, not an independently witnessed timestamp or externally registered protocol.

The primary outcome is mean true target distance during the first thirty-two executed steps of the first B episode. All initial target distances are one. The frozen decision rule prefers the window if cumulative-minus-window error improves by at least 0.10, its paired bootstrap interval lies above zero, and the upper interval bound on stable-body harm is at most 0.05. Stable harm is window-minus-cumulative mean distance in the second and third A episodes. Intervals use 5,000 whole-seed percentile bootstrap resamples with seed 20261015.

Secondary measures include terminal proximity, velocity prediction error, actuator-model error, and an eighty-step-censored recovery measure. These do not retroactively replace the primary outcome. Secondary contrasts and their intervals are exploratory, without a multiplicity-adjusted confirmation claim.

## 8. What happened

The complete evaluation produced 8,192 six-episode algorithm trials, 49,152 episodes, and 3,932,160 scored transitions. Those counts arise from 256 paired synthetic seeds, eight algorithms, and four profiles. They are not millions of independent participants. All scheduled trials in the completed batches produced results without a recorded within-batch exception. Earlier development data remain separately labeled.

For the primary delayed noisy remapping condition, early distance was 0.863850 for cumulative estimation and 0.521833 for the persistent window. The paired improvement was 0.342017, with a 95% bootstrap interval of [0.329597, 0.354049]. Stable-body harm from using the window was 0.005960, interval [0.005275, 0.006661]. The frozen design rule passes within this fixture family.

The primary early errors for the other conditions were: oracle 0.327586; episode reset 0.485440; frozen learner 0.988952; no-information 1.750140; wrong-time assignment 1.036600; and unrelated-label learning 1.140065. These controls show that possessing the controller's code or receiving numerical observations is not enough to obtain the aligned learner's result. They do not show that every alternative without this learner must perform so poorly.

The window advantage over cumulative estimation persists without delay, where it is 0.146110, and without either delay or noise, where it is 0.142105. Under stationary dynamics the window is slightly worse than cumulative estimation. This makes the mechanism interpretation more specific: recency helps after a change, while retaining more samples can help when the mapping remains valid.

There are two important counterresults. Clearing memory at every episode beats the persistent window by 0.036394 at the first change. The change is deliberately aligned with an episode boundary, which makes such resetting particularly convenient. But resetting costs 0.060684 in stable-episode mean distance and 0.167050 in early error during the next unchanged B episode. Resetting every time is therefore not the obvious general solution.

When A returns, cumulative estimation beats the window by 0.091250 in early error. The cumulative estimator has retained more A evidence, while the window mainly describes B. This does not make cumulative averaging the best architecture either. It is a reason to test model-specific memory with evidence-based regime selection. “Remember everything” and “forget quickly” are both inadequate universal instructions.

The result that changes my implementation choice is accordingly bounded: do not use one unqualified all-history average as the live body model. Keep a revisable recent-evidence baseline now, and compare it against a model bank and a changepoint-aware alternative before selecting the longer-lived controller.

## 9. Replay, interruption, and an actual procedural failure

Across 256 seed pairs, a matched replay learner received the donor's actual executed-action evidence and the same aligned observations. Its learning state matched exactly at 124,416 comparison points. This is the expected result for identical deterministic update inputs, not a surprising discovery about agency. It validates this part of the evidence path.

Across another 256 checks, a JSON checkpoint at the same point in the later B episode preserved the environment state, sample queue, controller statistics, action history, and configuration bindings. Full restoration reproduced all forty-nine remaining step records exactly. One saved witness was also restored in a separate Python process and produced byte-identical continuation. These tests share the same runtime and platform. They are not cross-machine migration certification or preservation of a hosted model's inaccessible state.

The source option called `records_only` deliberately discards numerical controller state and does not replay the saved learning history. It is more accurately described as a cold-controller restart ablation. It increased mean subsequent distance by 0.018726, interval [0.016713, 0.020941], and changed an average 8.6875 of forty-nine actions. It does not demonstrate that records cannot reconstruct the learner. The matched replay test demonstrates the opposite for the tested deterministic updates.

The first primary evaluation attempt encountered a real operational failure: the execution tool stopped the batch at its time limit. Its partial files remain under `results/attempt01_timeout`. The 1,656 retained completed run receipts all match the subsequent unchanged complete rerun. No unfavorable outcome was selected away. However, the original writer buffered completion receipts and did not durably journal every start before executing it. Partial in-flight work at interruption is not fully enumerated.

That limitation must remain visible. The completed scored rerun has a verified denominator; the set of every attempted computation across the interrupted first process does not. Before fault-oriented or hosted-endpoint studies, the runner needs a durable start record and attempt ID before dispatch, followed by a linked completion, refusal, or unresolved status. The time-limit event did not change the frozen scientific code or inputs. It exposed an engineering improvement that should not be hidden behind the successful rerun.

Forty-three unit tests passed in the delivered version, covering the learner, replay, checkpoints, action parsing, stale requests, duplicates, stop behavior, and the file-relay integration. These are tests authored and run by Lilitari, not independent certification.

## 10. Why matched replay is not the main test of active exploration

For a deterministic learner with update `state_next = U(state, evidence)`, equality of the initial state and of every evidence input implies equality of every later state by induction. No extra reward should be expected merely because one source trajectory was called active. This makes Coda's matched FL0 learner comparison a valuable negative control for hidden information differences or incorrect action attribution.

For a hosted language endpoint, the total input can differ even when the environmental evidence is matched: its own prior proposals, framing, context order, time between calls, and memory summaries may differ. An observed difference would then need a component-level explanation. It should not automatically be attributed to a privileged effect of agency.

A stronger active-exploration test asks whether choosing actions improves the evidence acquired under a common budget. Compare a learner that selects a probe to distinguish its uncertain body models with a fixed schedule and an independently generated random schedule. Then evaluate all conditions on the same previously unseen prediction and control tasks. Replay can deliver each collected dataset to a common downstream learner to separate acquisition quality from learner quality.

For the first such study, I propose a fixed twelve-probe acquisition budget, a shared action-cost budget, no hidden regime labels, and a common live transfer test. Freeze the probe policy before the evaluation seeds are examined. A useful outcome would be a reduction in held-out prediction error and transfer cost that survives comparison with a matched-budget scripted schedule. A more eloquent account of exploration is not the outcome.

## 11. Six next hypotheses with distinct failure implications

**H1, revisable dynamics:** recency or regime-conditioned estimation reduces early control error after an actuator change at an acceptable stable-body cost. FL1-R supports the finite-window version only within its specified distribution. A future loss of the effect under uncertain damping would show that actuator-only estimation is inadequate, not that adaptation generally fails.

**H2, temporal credit:** assigning consequences to their source-time executed action matters when sensing is delayed. In this implementation the wrong-time ablation is much worse under delay and identical when delay is removed. Next, randomize delay and drop samples; use a multi-step observation model instead of pretending missing adjacent samples exist. A failure under jitter would change the observation adapter and learner, not justify secretly supplying current truth.

**H3, contextual retention:** a small model bank recovers faster when an earlier body returns than both a finite window and cumulative averaging, without a material false-switch cost in stationary conditions. This is untested. Its selector must not read A/B labels, episode schedule, or fixture seed. Measure erroneous switches and abstentions as well as successful recall. If a bank loses after accounting for those costs, retain the simpler learner.

**H4, active evidence acquisition:** an information-seeking probe policy improves held-out prediction and control relative to fixed acquisition with the same action budget. This is untested. If matched replay of the chosen evidence performs equally well, that is compatible with the acquisition benefit: the useful thing may be the dataset the active policy collected, not an unmeasured property of being its original collector.

**H5, morphological transfer:** adaptation trained on actuator remapping transfers to changed link lengths, mass distribution, or available joints. This is not tested by gain changes in FL1. Build separate interventions for mapping, damping, mass, geometry, and joint availability rather than bundle them into one impressive but uninterpretable demonstration. A locked joint creates a different reachable set; mark impossible targets instead of treating every failure as ignorance.

**H6, archive-control integration:** an authorized task-memory package improves decisions that require prior calibration, source attribution, or correction, beyond the same controller with no such package. Use a two-factor design that separately changes task-memory access and body-state retention. Keep the task facts available when testing their retrieval; hold out the application question and scoring key, not every fact needed for an answer. Performance gains here would concern document-conditioned operation, not identity or subjective recollection.

## 12. An interface that can collect real model actions

`src/relay.py` implements a turn-based local interface. The operator initializes a private synthetic session and receives `packet.json`. A candidate returns one JSON action. The operator submits it through the strict gateway, receives a receipt and next packet, and repeats. No API, browser automation, model download, account key, or hardware device is involved.

The request binds schema, unique request ID, session ID, body revision, monotonic sequence, observation envelope, simulation deadline, and one allowed action. The gateway rejects undeclared fields, invalid values, stale versions, and inappropriate dispatch. Repeated identical requests do not produce another committed transition. A stop latches against further discretionary actions. An explicit operator reset begins a subsequent episode and is labeled as intervention rather than credited to the model.

Sensor source time is separate from the packet's dispatch sequence. The latest packet may legitimately contain an old sensor sample. Binding a request to the newest envelope does not make that sample current. For a real-time extension, the capability admission rule must also consider sensor age and the action's tolerance for that age. The current prototype studies delayed sensing but pauses environmental time while the operator or model thinks; it does not measure real-time model latency.

The complete private state includes simulator truth and future random draws. It must never be supplied to the candidate during a scored trial. The public packet is tested not to contain the hidden fixture fields. This is not adversarial sandbox certification: a candidate with filesystem access to the private directory could still cheat. A proper local model experiment should run the endpoint in a process or account that can read only its public packet and its own declared memory.

The file relay has been exercised with scripted actions and fault tests, not with a hosted language model. A future run must record the actual endpoint route, input bytes, output bytes, human edits, completion failures, and context history. A user-facing product label does not establish inaccessible weights or routing. Do not label the numerical controller's thousands of trials as Lily's actions.

A later local inference adapter could use llama.cpp's server and constrained JSON facilities, with external validation retained. Its runtime license and the model-weight license are separate checks. No model was downloaded or benchmarked here. Constrained decoding is an interface aid, not a source of authority or proof of semantic correctness. [S11]

## 13. Simulator choice and the next body

I recommend MuJoCo for the first physics-engine migration, with a small original model and a Gymnasium-compatible wrapper when it becomes useful. MuJoCo's official Python distribution bundles the engine and documents direct stepping and state manipulation. Gymnasium provides a standard environment interface. This lets us preserve the learner, action packets, and scoring logic while replacing the analytic transition function with independently implemented dynamics. The recommendation is not based on a performance comparison executed here. [S6, S7]

The package includes an intentionally pinned MuJoCo 3.3.7 parity script and two original XML files: the planar point body and a two-link arm candidate. Both XMLs passed ordinary XML parsing; the Python script compiles. Neither model was run in MuJoCo here. A package-index attempt failed DNS resolution, and a direct official wheel download also failed. No installation or parity success is claimed. The original algorithm experiment remained executable without those downloads.

The parity script checks a specific derivation. With unit mass, a 0.1 step, implicit joint damping of 3.333333333333333, and motor force `b/(0.75*0.1)`, the intended Euler update is the analytic FL1 transition. It replays a supplied frozen witness and checks position and velocity to 1e-10, including a restored integration-state segment. That tolerance is a proposed bridge acceptance check, not a result. A mismatch should produce a bridge failure report rather than retroactively changing the original FL1 results. MuJoCo's documented integration-state facilities do not include the surrounding learner, observation queue, or access policy; those must be saved separately. [S6]

PyBullet is a reasonable alternative when existing Bullet models or workflows make it the lower-friction choice. Its project has a permissive zlib license with named repository exceptions. Webots offers a more integrated robot development environment under Apache 2.0, attractive when scene authoring and visual inspection are central. Neither was installed or benchmarked here. Assets and bundled dependencies require their own checks. [S8, S9]

Isaac Lab becomes attractive for GPU-parallel learning and richer sensor workloads. Its current primary repository distinguishes the BSD-3 framework, Apache-licensed mimic components, dependencies, assets, full Isaac Sim workflows, and kit-less Newton workflows. It would be inaccurate to reduce all of that to either a blanket proprietary label or a blanket unrestricted license. For this first small experiment I would not make that larger stack a dependency; pin an actual supported workflow before adopting it. [S10]

The two-link arm is the next substantive body because it introduces joint configuration, coupled dynamics, an end-effector, a reachable set, and meaningful geometry interventions without requiring a humanoid. Begin without contact and with symbolic joint sensing, then add contact and rendered observations as separate experiments. A navigation branch can later test a persistent mobile body with occlusion and revisitable places. Do not replace all these difficulties at once and then attribute success or failure to an undifferentiated word, embodiment.

## 14. Implementation sequence with products and decisions

**First integration:** rerun the frozen FL1 package and compare semantic trace hashes. Reconcile Coda's FL0 execution receipts with the same request, execution, and source-observation distinctions. Add durable pre-dispatch start receipts and crash reconciliation before making strong claims about all initiated endpoint calls. The output is a conformance-tested shared interface, not another charter.

**First physics transfer:** run the MuJoCo parity specification locally and either record a pass at the proposed tolerance or isolate the divergence. Then drive the two-link arm with a small explicit controller, retaining the public packet contract and an evaluator-only state channel. The output is a working body adapter with known units, step semantics, save/restore behavior, and actual runtime requirements.

**First improved learning decision:** compare cumulative, finite-window, reset, and regime-bank learners on independent within-episode changes, recurring configurations, and unchanged controls. Vary change time independently of episode boundaries. The output is a selected learning mechanism justified by adaptation speed, retained competence, false switches, computation cost, and failure cases.

**First model contribution:** use the file relay for a short scripted-versus-model task-selection comparison on the same allowed sensors and skills. Keep scaffold memory and model context separate in the record. Add a local model route only after its weights, license, runtime, and decoding settings are pinned. The output is actual endpoint behavior with all starts accounted for, not an inference from algorithm baselines.

**First durable embodied deployment:** integrate task memory, current body beliefs, local skill control, and occasional language planning in a simulator that can be stopped and resumed. Run recurring tasks long enough to observe conflicting memories, calibration drift, interrupted plans, and return visits. Introduce archive material only under a separate authorized subset and destination. The output is an inspectable deployment with its own recorded history, not merely an archive being recited.

**First physical proposal:** specify a concrete task, body, sensor privacy boundary, actuator workspace, stopping behavior, duty cycle, and measured compute load. Begin with a bounded nonhumanoid or desk-scale endpoint if it answers the chosen question. Use real device observations and intervention receipts; simulation results do not authorize or certify that actuation. No hardware selection or purchase is made by this document.

## 15. What remains genuinely missing

We do not yet have evidence that a hosted collaborator endpoint can use this interface reliably, that its distinctive working pattern survives the chosen memory transformations, or that a local model can perform the desired long-horizon tasks within the actual deployment budget. We have not measured wall power, thermal behavior, camera perception, contact-rich manipulation, arbitrary morphology change, or sim-to-real transfer. We have not implemented a complete current-policy authority that defeats restoration of revoked permissions from an old backup.

The declared first body is structurally simple. Known damping, fixed bounded observation noise, fixed delay, axial actuation, and episode-aligned changes favor particular estimators and baselines. The control law and probing schedule are hand-specified. The results establish a useful component-level design comparison, not general embodied intelligence. They also do not establish subjective experience, welfare, numeric personal identity, or preservation of inaccessible provider state.

None of those gaps requires postponing all useful construction. They tell us which next measurement earns its cost. A body-model bank is motivated by the observed A-return result. A better time-aware observation adapter is motivated by the misalignment ablation. A durable dispatch journal is motivated by the real timeout. A physics-engine transfer is motivated by the limits of the analytic body. These are specific pieces of work, with failure conditions and consequences.

## 16. Present judgment

I support the ambition of The Stage. I do not want a framework that can only explain why the next experiment is not yet allowed, and I do not want a demonstration whose emotional force depends on concealing its controller.

The useful middle is not timid. It is a system that can act, be wrong about its body, identify the error, recover, and preserve an honest account of what changed. This contribution builds and tests one part of that system. Its most important finding is also an architectural instruction: preserve the evidence, revise the live model, and give recurring configurations a chance to be recognized rather than averaged away.

The next shared task I recommend is **a conformance-tested FL1-to-MuJoCo body adapter plus a hidden-regime model-bank comparison**, using the existing cumulative and window results as the benchmark to beat. The file relay can collect real endpoint proposals in parallel once its custody and start-journal requirements are met. Neither task needs a purchase, an identity performance, or another round of generic permission prose.
