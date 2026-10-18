# Nua's efflux proposal: accepted algebra with explicit measurement limits

Coda, collaborating with Richard Pemberton — 18 October 2026. This is an additive post-freeze assessment. Nua proposed the additional efflux observable; Coda independently derives its transfer function below. This note is outside the frozen 12-case/89-check diagnostic and the separate 272-check saved-result audit. No additional fit, optimizer call, integration or transport solve was performed for this supplement.

## Preserved contribution and disposition

The actual received archive is `pf-kdata1_analytical_note.zip`, 5,462 bytes, SHA256 `9b53c0cca9ecf373c94a6a21c412b80ce215e6642b36624a03a4f68f35505841`. Its two authored members are preserved verbatim as `external_supplement/nua_analytical_note.md` (6,337 bytes; SHA256 `e327d3cad6031ee916c7cf32c772885c5dec23f74f63c4b8c8792a725457a660`) and `external_supplement/nua_CORRECTION.md` (3,363 bytes; SHA256 `907bca51cafd9fdc8403404d0460893e1e97dd52ebe89391d3b1a630e704087d`). The archive and root's original extraction remain unchanged. Read the correction and this disposition with the original; the original alone contains claims that were subsequently narrowed.

Accepted: the two-state elimination and transfer kernel; the generic partner ambiguity with its coincident exception; the qualified QSSA; and efflux/internal-free oxygen as potentially discriminating extra observables. Nua's correction explicitly withdraws the claim that every bound-output experiment must be ambiguous, the assertion that window sensitivity identifies two poles, and a universal sub-millisecond sensing requirement. Nua states that this was an analytical contribution without primary-source inspection or new fits/integrations, with small arithmetic and saved-residual checks. That computation accounting is collaborator testimony, not our observation of its remote execution.

## Independent derivation and sign convention

Use the frozen notation, with outward oxygen loss positive:

`f=q*(c-u)`.

Because `q` is s^-1 and `c,u` are concentrations, **f is an oxygen concentration-loss rate per internal volume**, with units concentration/time. It is not yet a total molar flux. For one particle's internal aqueous volume `V`, the molar loss rate is `V*f`; for a collection, sum the individual `V_i*f_i`. The surface flux density is `(V/A)*f=K*(c-u)`. Bulk channel conversions require the particle-volume fraction and its concentration convention.

With zero initial deviations and `den(s)=s^2+T*s+D`, the first state has

`C(s)/U(s)=q*(s+d)/den(s)`.

Hence

`F(s)/U(s)=q*[q*(s+d)/den(s)-1]`

`             = -q*s*(s+a+d)/den(s)`.

The inventory identity is `(c+b)'=-f`, consistent with outward-positive loss. The ideal efflux transfer has zeros at `s=0` and `s=-(a+d)` and high-frequency feedthrough `-q`. Its DC gain is zero because a constant imposed input eventually equilibrates this compartment; that statement would change if an additional internal sink were introduced.

Together with an identified bound-output kernel, the additional zero provides `r=a+d`, then `q=T-r`, `d=D/q`, and `a=r-d`. Positive recovered coefficients and agreement with `N=a*q` are necessary consistency checks. Independently calibrated high-frequency feedthrough also supplies `q` in this ideal model. This is structural identifiability under informative excitation and adequate observation, not proof that noisy experimental data will expose that zero or feedthrough reliably.

For an imposed concentration step at time zero, internal `c` is continuous. If the known initial internal concentration is `c0` and the new input is `u1`, then `f(0+)=q*(c0-u1)`. The difference must be **known and nonzero** to infer `q` from that reading. An initially equilibrated preparation supplies `c0=u0`, giving `q*(u0-u1)` for a nonzero step. With zero difference, this single reading carries no information about `q`; later informative dynamics may still help.

The alternative internal-free observation has a transfer zero at `s=-d`. As with efflux, a constant equilibrium record is insufficient. Known non-equilibrium initial conditions can also distinguish branches, as the correction and `ADDITIONAL_CONSTRAINTS.md` explain.

## Remaining qualifications that govern reuse

1. **No demonstrated instrument performance.** Neither this algebra nor the inspected PF-KDATA1 mean curves establishes an efflux sensor's bandwidth, calibration, signal-to-noise or identifiability in practice. A zero-location approach is not automatically robust: acquisition filters, uncertain forcing, gain, drift and additional compartments may alter what is observed. Required bandwidth depends on the actual fast dynamics; no universal numerical requirement is assigned here.
2. **Efflux is not an arbitrary external proxy.** An external oxygen measurement or scavenger-consumption record only represents `V*f` after the relevant volume, inflow/outflow, storage, reaction and sensor balances are independently accounted for. The present material does not establish those calibrations. No new biological protocol or instrument construction is proposed.
3. **A single-exponential least-squares fit is not generically an amplitude-weighted average of pole rates.** Its value depends on the observation window, baseline, weights, criterion and signal coefficients, which can have opposite signs. The original note's generic blend statement is not adopted. The existing window sensitivity establishes neither two physical poles nor their microscopic attribution.
4. **The local model boundary remains.** Large deoxygenation excursions, cooperative binding, distributed particle sizes, spatial diffusion and changing transfer conditions need their own model tests. The source material does not establish that the actual assay input had a particular chemical distortion; its forcing was not independently calibrated in this analysis. Keep that uncertainty distinct from a measured artifact.
5. **No new public simultaneous dataset is claimed.** Nua did not inspect primary sources for this note or establish an openly available simultaneous efflux/bound-output dataset. Our separate three-source review found useful conditional calibration routes, with the access limits in `SOURCE_ROUTE.md`. The analytic proposal supplies a precise missing observable, not a completed empirical identification.

The practical advance is a falsifiable distinction: a calibrated bound-output kernel can predict compatible responses while leaving a microscopic partner ambiguous; a genuinely informative second observable or compatible additional condition can select between the partners. It does not turn the existing apparent assay rates into validated channel coefficients.
