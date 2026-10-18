# Additive algebra after the AB-KMAP0 freeze

Coda, 18 October 2026. These are symbolic qualifications to the derivation, added after the 12-case diagnostic. They were not extra diagnostic cases and must not be counted within its 89 executed checks. The frozen source and results remain unchanged.

For calibrated coefficients `T=q+a+d`, `D=q*d`, `N=a*q`, strict positivity of `q,a,d` implies `T,D,N>0` and

`T^2 - 4*(D+N) = (q-a-d)^2 >= 0`.

These conditions are also sufficient for at least one positive triple: solve `q=[T±sqrt(T^2-4*(D+N))]/2`, then `a=N/q`, `d=D/q`. Generically there are two distinct triples. At equality, they coincide; these are parameter branches, not the two temporal decay poles, whose discriminant is instead `T^2-4D`. Thus "exactly two distinct parameter sets for every case" would overstate the ambiguity. For an uncalibrated optical numerator `g*N`, this inequality cannot be applied without knowing the gain and its sign/concentration convention.

A known non-equilibrium initial state can break the calibrated partner ambiguity. Under the partner transform, its initial bound derivative is multiplied by `q/(a+d)`:

`b'_partner(0)=[q/(a+d)]*[a*c(0)-d*b(0)]`.

If the initial chemical imbalance is nonzero, this generally differs from the original derivative. If the known initial state is on the common equilibrium line `b=(a/d)*c`, both derivatives are zero and this discriminator disappears. These are exact statements about the declared local model; practical derivative estimation through an instrument may be ill-conditioned.

The current published mean traces do not supply a calibrated known internal non-equilibrium state, both poles and the gain needed to use these identities as a new empirical estimate. This note supplies falsifiable future model constraints, not additional measurements.

The independent saved-result review also makes an observability qualification explicit: internal-free oxygen distinguishes the partner only under informative excitation. Two constant equilibrium records do not. C05 uses zero external concentration with positive internal free oxygen and compares the initial free derivatives; its initial binding reaction is at equilibrium. It does not establish that every conceivable second-observable record suffices. C07 likewise implements its particular contradictory witness rather than a complete classification of arbitrary two-condition data.
