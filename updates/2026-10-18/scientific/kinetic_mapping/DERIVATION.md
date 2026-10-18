# AB-KMAP0: what an oxygen-release trace can identify

Coda, collaborating with Richard Pemberton — 18 October 2026. This is an authored, restricted-model derivation. It is not an empirical parameter fit. The existing PF-KDATA1 fits remain descriptive observations from averaged assay traces.

## 1. Observation, chemistry and exchange are different quantities

Let `u` be external dissolved oxygen, `c` internal dissolved oxygen, `b` bound oxygen, and `B` internal binding-site capacity. Concentrations refer to internal aqueous volume where appropriate; one mole of `b` is one mole of bound oxygen, not one mole of hemoglobin tetramers. Rates are in seconds and conductances in length per second.

A minimal absorbance model is `y(t)=y_offset+g*b(t)`, followed, if needed, by the instrument's response operator. The sign of `g` depends on wavelength. Scattering, baseline drift, finite mixing and photometric response are possible additional observation terms, not binding reactions. Unknown absorbance gain or a stored normalized trace does not establish an absolute oxygen inventory. A time shift preceding every observation is confounded with free amplitude for a single exponential: `A exp[-k(t-lag)] = [A exp(k*lag)] exp(-k*t)`.

For one effective noncooperative site class, define

`R = k_on*c*(B-b) - k_off*b`,

`c' = q*(u-c) - R`,

`b' = R`.

Here `k_on` has units concentration^-1 s^-1, `k_off` and `q` have units s^-1. The exact inventory balance is `(c+b)'=q*(u-c)`. The nonnegative region `c>=0, 0<=b<=B` is invariant for nonnegative input and positive parameters. A lumped interior must be justified by internal diffusion times; otherwise replace it with a spatial model. Cooperative hemoglobin requires additional state assumptions. An equilibrium Hill curve by itself does not choose a kinetic mechanism.

Write `q=(A/V)*K`. On a common aqueous concentration reference, a membrane and external stagnant film in series give `1/K=1/P_m+1/k_f`. Partition coefficients change this relation unless already included in the conductances. One `K` cannot identify both positive resistances: for any `P_m>K`, `k_f=K*P_m/(P_m-K)` produces the same `K`. Measured particle geometry is necessary for separating `K` from `A/V`; geometry does not by itself split membrane and film.

## 2. Local linear observation model and its exact elimination

Around equilibrium `(c_star,b_star,u_star=c_star)`, write deviations using the same symbols for compactness and define

`a=k_on*(B-b_star)` and `d=k_on*c_star+k_off`, both s^-1.

Then

`c'=-(q+a)*c+d*b+q*u`,

`b'=a*c-d*b`.

Eliminating `c` gives

`b''+T*b'+D*b=N*u`,

`T=q+a+d` [s^-1], `D=q*d` [s^-2], `N=a*q` [s^-2].

For calibrated zero-state input/output, `H(s)=b(s)/u(s)=N/(s^2+T*s+D)`. Its static gain is `beta=N/D=a/d`, the differential bound/free capacity at this equilibrium. This local `beta` is not automatically the full oxygen capacity `B` or a global Hill slope.

For `q,a,d>0`, the two decay rates are positive:

`lambda_s,f = (T ∓ sqrt(T^2-4D))/2`.

The discriminant is `(q-d)^2+a^2+2*a*(q+d)>0`. Also `lambda_s<=min(q,d)` and `lambda_f>=max(q,d)`. These are conditional model constraints, not bounds obtained by treating arbitrary full/late fitted rates as poles.

## 3. Exactly what the initial state and calibration buy

**Free decay, unknown internal initial state and gain.** If both observable modes are resolved, the trace can determine `T,D` and its two output coefficients. The internal initial state can absorb those output coefficients: for any `q` strictly between the two poles,

`d=D/q`, `a=T-q-D/q>0`,

`c(0)=[b'(0)+d*b(0)]/a`.

Thus poles alone leave a continuous admissible family, subject to physical initial-state bounds. A known absolute capacity or initial free concentration can restrict that family. Known derivatives/independently prepared initial states add constraints and must not be discarded. A single fitted exponential generally supplies neither both poles nor these missing initial-state measurements. A mode can also be unexcited or hidden by the observation window.

**A concrete free-decay family.** `(q,a,d)=(2,7/2,9/2)`, `(3,4,3)` and `(6,5/2,3/2)` all give `T=10,D=9` in consistent second-based units. With `b(0)=1,b'(0)=0`, the respective internal starts are `9/7,3/4,3/5`, and all have `b(t)=(9 exp(-t)-exp(-9t))/8`. These are hypothetical linear deviations. They can be uniformly reduced in magnitude around an admissible equilibrium; they are not fitted concentrations. The fast output coefficient is negative, so a positive-mixture biexponential assumption would wrongly exclude an equilibrium-to-sink initial response.

**Fully calibrated driven input/output can still be predictive.** Knowing `T,D,N` determines the entire zero-state kernel of this local model, so it predicts arbitrary admissible input waveforms for the same preparation and parameter regime. Microscopic ambiguity does not erase that predictive identification. But `q` solves

`q^2-T*q+(D+N)=0`,

which generally has two positive solutions. The exact partner transformation is

`(q,a,d) -> (a+d, a*q/(a+d), d*q/(a+d))`.

Both have identical `T,D,N,beta`. For example `(2,7/2,9/2)` and `(8,7/8,9/8)` are indistinguishable by calibrated zero-state `b/u` transfer. They also share the equilibrium initial line `b=beta*c`; a release from that line does not automatically resolve the ambiguity. Measuring internal free `c(t)` would distinguish the partners. Independently known same-preparation chemical `d` selects `q=D/d` and `a=T-q-d`, provided positivity and all measured constraints agree. A free-Hb measurement from a different preparation is not automatically that `d`.

Unknown absorbance gain means the driven numerator actually observed is `g*N`, unless the gain is separately calibrated. The local twofold result is therefore more informative than the current three averaged absorbance curves warrant. Conversely, this result does not prove every nonlinear, calibrated, multi-condition experiment is unidentifiable: changing equilibrium concentration changes `a,d`, and informative nonlinear features can add constraints.

**A shared-chemistry two-condition test.** If two conditions truly have common `a,d` but distinct exchange `q_1,q_2`, then `T_2-T_1=q_2-q_1` and `D_2-D_1=d*(T_2-T_1)`. If the difference in `T` is nonzero and both poles are identified, `d=(D_2-D_1)/(T_2-T_1)`, `q_i=D_i/d`, and `a=T_i-q_i-d` identify the common coefficients. The recovered values must be positive and agree across conditions; calibrated numerators must also satisfy `N_i/D_i=a/d`. If `T` is unchanged but `D` changes, the common-chemistry hypothesis fails in this model. Mere differences in carrier preparation do not authorize that sharing assumption.

**An additional nonlinear scaling ambiguity.** In a zero-external-oxygen experiment with unknown capacity and optical gain, scale `(c,b,B)` by `eta>0`, scale `k_on` by `1/eta`, and optical gain by `1/eta`, leaving `q,k_off` unchanged. The output is identical. This exact restricted-experiment symmetry prevents recovering absolute internal capacity and association coefficient from uncalibrated absorbance alone. A known nonzero external concentration or independent concentration measurement can break this scaling.

## 4. What a channel coefficient would mean

The channel has a changing external oxygen field, not the stopped-flow sink. Its external film may differ with flow, particle distribution and geometry; therefore `q_channel` need not equal `q_assay`. A parcel model must retain carrier internal free and bound inventories, and the channel's total molar flux must include bulk-free oxygen and particle-volume-weighted internal oxygen. The wall sink removes from that total flux. No parameter conversion can dispense with this conservation law.

There are two distinct controlled reductions:

1. **Fast internal-free equilibration.** If `epsilon_c=d/(q+a)<<1`, forcing varies slowly relative to `q+a`, and the initial fast transient is excluded or projected consistently, set `c'≈0`. Then
   `b'≈k_forward*u-k_reverse*b`,
   `k_forward=a*q/(q+a)` [s^-1],
   `k_reverse=d*q/(q+a)` [s^-1],
   `k_forward/k_reverse=beta=a/d`.
   Equivalently `b'≈k_reverse*(beta*u-b)` and `1/k_reverse=1/d+beta/q`. This resistance-like formula is conditional on the reduction. It is not a universal sum of microscopic residence times.

2. **Separated observable poles.** More generally, if `epsilon_p=lambda_s/lambda_f<<1` and input frequencies are well below `lambda_f`, the kernel factors as `H(s)=beta*lambda_s*lambda_f/[(s+lambda_s)(s+lambda_f)]` and reduces to `beta*lambda_s/(s+lambda_s)`. Forward/reverse coefficients are then approximately `beta*lambda_s` and `lambda_s`. The initial slow-mode amplitude is a projection, not always the measured total initial bound oxygen. Dropping acceleration gives the low-frequency alternative coefficients `N/T,D/T`, which differ from `beta*lambda_s,lambda_s` by relative order `epsilon_p`.

The limits are informative. If exchange is fast, `q>>(a+d)`, the slow rate tends to `d`. If chemistry is fast, `a+d>>q`, it tends to `q/(1+beta)`, not generally the internal-free QSSA formula unless that QSSA's extra condition holds. These forward and reverse coefficients preserve the same local equilibrium gain; choosing one release rate independently of the forward rate can violate the intended equilibrium.

Stage's existing finite-release coefficient is a phenomenological relaxation rate toward a chosen equilibrium curve. A local mapping must specify the operating point, temperature, preparation, concentration reference, `beta`, external transfer and fast-mode error. A 20-degree-C apparent absorbance decay does not supply all of these. Within a fixed calibrated local kernel, however, channel-forcing predictions can be tested without claiming unique microscopic parameters.

## 5. What the recorded data already constrain

The previous audited PF-KDATA1 record contains one mean trace per preparation, differing starting times, structured residuals, and strongly window-sensitive RBC/LEH descriptive rates. These observations do not support treating the original iid-residual covariance intervals as reliable experimental uncertainty. They do not invalidate every possible uncertainty procedure. They also do not identify two physical poles, a membrane coefficient, an internal diffusion constant, a causal geometry effect or a channel transfer factor. No new numerical estimate is asserted here.

The useful next empirical target is an independently constrained input/output kernel or a joint-condition parameter-combination set, followed by a held-out waveform/condition prediction. First obtain a documented input waveform and compatible chemistry/geometry information from public evidence. If only figure-level summaries are available, retain digitization bounds separately from between-preparation uncertainty. A future fit must exclude published Fit rows, preserve windows and baseline choices, and avoid declaring pointwise means independent replicates.

Sources and read-depth limitations are in `SOURCE_ROUTE.md` and `SOURCE_RECEIPT.json`. All algebra and hypothetical examples here are Coda's derivation; no selected paper is claimed to establish this identifiability theorem. The analytic code is Coda's agent implementation. The coordinator's separate derivation and Nua's forthcoming analytical challenge are distinct review objects, not coauthorship or already completed validation of this implementation. The proposed diagnostic is separately frozen and requires root's explicit execution admission.
