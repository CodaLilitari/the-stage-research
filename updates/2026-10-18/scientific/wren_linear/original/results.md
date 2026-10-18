# Finite-release linear benchmark: HONEST PARTIAL RESULT
Wren (AI collaborator, via Grok Bot), 2026-10-17. Nonclinical, hypothetical, linear model only; nothing measured.
Status: the 24-call ledger was used up by two crashed runs (see DEVIATIONS.md). Only D, E, F1 and the
hydraulic flows were captured. F2-F6, RK4 validation, the T=80 diagnostic and k* were NOT obtained.

## Derivation
x=[c,b], x' = A x, A = [[-(a+k g), k], [k g, -k]], x(0)=[c0, g c0], c0=0.2 mol/m^3.
tr A = -(a+k+k g), det A = a k >= 0, discriminant ((a+k g-k)/2)^2 + k^2 g >= 0, so eigenvalues are real and <= 0.
exp(At) = e^{mt}[cosh(dt) I + (A-mI) t sinh(dt)/(dt)], m = tr/2, d = sqrt(disc); the sinh(x)/x series keeps the
repeated case (F4: g=0, a=k, d=0) finite. With x(0) an equilibrium-loaded state, b'(0)=0.
Uptake per volume U = c0(1+g) - (c(T)+b(T)) = a * integral_0^T c dt (mol/m^3). Delivery rate = Q U (mol/s).
Limits: k=0 gives c = c0 e^{-aT}, b = g c0 frozen (bound O2 never released). k -> inf gives s=(1+g)c, s'=-a c,
c = c0 e^{-aT/(1+g)} (case E). a=0 gives U=0.
Hydraulics: R = 12 mu L/(W h^3) = 9.36e9 Pa s/m^3 (base), 3.744e10 (carrier).

## Captured results
| case | T s | c(T) | b(T) | U mol/m^3 | Q m^3/s | Q*U mol/s |
|---|---|---|---|---|---|---|
| D dissolved | 3 | 0.109762 | 0 | 0.0902377 | 3.333e-11 | 3.008e-12 |
| E equilibrium | 8 | 0.145230 | 0.580919 | 0.273851 | 1.25e-11 | 3.423e-12 |
| F1 k=0 | 8 | 0.040379 (hand: 1-U-b) | 0.800000 | 0.159621 | 1.25e-11 | 1.995e-12 |
Checks captured: D balance exact; F1 balance |U - a int c| = 5e-17 (passes); F1 b = 0.8 (k=0 limit holds);
E U difference-form vs expm1-form differ by 1.1e-16 (cancellation illustration).

## Hydraulics (assumed parameters; binding and delivered values are hand arithmetic)
Dissolved: power cap binds; Q=3.333e-11 m^3/s; residence 3.0 s; dP 0.312 Pa (< 0.468 cap); power 1.04e-11 W.
Carrier: pressure cap binds; Q=1.25e-11 m^3/s; residence 8.0 s; dP 0.468 Pa; power 5.85e-12 W (< cap).
So the provided 3 s and 8 s are consistent. Same caps do NOT mean equal delivered power (carrier gets ~56%).

## Answers (linear model only)
1. E beats D in outlet free c iff T_E/(1+g) < T_D: 1.6 < 3, so yes (0.1452 vs 0.1098).
   With k=0 the carrier decays at the full rate a for longer (8 s > 3 s): 0.0404, it loses.
   The ranking flip from E-wins to finite-exchange-loses can exist only if T_D < T_E < (1+g) T_D (3 < 8 < 15 here):
   then the k=0 limit loses and the k->inf limit wins, so by continuity some k* gives c_F = c_D.
   k* and whether F2 (k=1/30, slow vs a residence of 8 s) falls below D were NOT computed.
2. Uptake and outlet free c do NOT share an ordering. Outlet c: E > D > F1. Uptake per volume: E > F1 > D
   (F1's longer residence removes more free O2 per volume while leaving less outlet c). Q*U: E > D > F1,
   because the carrier's lower flow outweighs F1's larger per-volume uptake.

## Limitations
Partial run; no independent validation obtained; monotonicity of c_F in k is unproven; uptake as a difference of
near-equal totals loses digits when aT is small (expm1/integral form preferred); near-repeated eigenvalues use the
series branch, not validated here. No generalization to the nonlinear Hill/tissue model.
