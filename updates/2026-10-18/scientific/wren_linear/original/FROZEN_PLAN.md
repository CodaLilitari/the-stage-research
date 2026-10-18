# FROZEN PLAN: finite-release linear benchmark (The Stage)
Byline: Wren (AI collaborator, via Grok Bot)
Frozen: 2026-10-17 ~19:11 EDT (UTC-4), before any computation. Nonclinical, hypothetical, linear model only.
No result here generalizes to the nonlinear Hill/tissue model.

## Model
State x=[c,b] (mol/m^3 of fluid), t = residence time (s) along a constant-speed channel.
db/dt = k(gamma c - b); d(c+b)/dt = -a c  =>  dc/dt = -(a + k gamma) c + k b.
x' = A x, A = [[-(a+k gamma), k], [k gamma, -k]], x(0) = [c0, gamma c0], c0 = 0.2.
Uptake per fluid volume U = c0(1+gamma) - (c(T)+b(T)) [mol/m^3]. Delivery rate = Q*U [mol/s].

## Cases (8)
F1 a=0.2,k=0,gamma=4,T=8 | F2 a=0.2,k=1/30,gamma=4,T=8 | F3 a=0.2,k=10,gamma=4,T=8
F4 a=0.2,k=0.2,gamma=0,T=8 (repeated eigenvalue) | F5 a=0,k=0.2,gamma=4,T=8 | F6 a=0.2,k=1/30,gamma=4,T=80
D dissolved, algebraic: c=c0 exp(-aT), a=0.2,T=3 (b=0)
E instantaneous equilibrium, algebraic: c=c0 exp(-aT/(1+gamma)), b=gamma c, gamma=4,T=8
F6 diagnostic: algebraic E expression evaluated at T=80 (no extra scan).

## Algorithm
Exact: Putzer/Sylvester 2x2 form exp(At) = e^{mt}[cosh(dt) I + (A - mI) t*shc(dt)],
m = tr(A)/2, d = sqrt(m^2 - det A) (real here: disc = ((a+k gamma-k)/2)^2 + k^2 gamma >= 0),
shc(x)=sinh(x)/x with Taylor series for |x|<1e-3 (stable at d=0, F4 exactly repeated).
Balance: U vs a*integral_0^T c dt by composite Gauss-Legendre (numpy leggauss, 32 nodes x 64 panels) on exact c(t).
Independent validation: hand-written fixed-step classical RK4, h = T/N, N = ceil(T / min(1e-3, 0.01/|lambda_max|)).
Crossover k*: own bisection on f(k)=c_F(k;a=0.2,gamma=4,T=8) - c_D on [1e-8, 10], 60 iterations,
using exact formula; counted as ONE ledger call with its internal evaluation count reported.
Monotonicity of c_F in k is assumed, not proven; a sign change at the bracket ends is required.
Hydraulics: R = 12 mu L/(W h^3); Q = min(Pcap/R, sqrt(Pwcap/R)); residence = V/Q; report binding cap,
delivered dP = Q R and power = Q^2 R. Assumed parameters, not measured.

## Tolerances
Exact vs RK4: |diff| <= 1e-14 + 1e-10*|exact| per component.
Balance: |U - a*int c| <= 1e-14 + 1e-10*max(U, a*int c).
Positivity: c(T)>=0, b(T)>=0 (reported raw, never clipped).
Limits: F1 b(T)=gamma c0 and c(T)=c0 e^{-aT} (rel 1e-12); F5 U ~ 0 and total conserved (abs 1e-14);
F3 vs E at T=8 reported (expected close, not equal; no tolerance pass/fail, diagnostic only);
F4 vs c0 e^{-aT} (rel 1e-12).

## Ledger (cap 24 calls total including failures/retries)
Planned: 6 exact (F1-F6) + 6 RK4 validations + D + E + F6-eq diagnostic + 2 hydraulics + 1 crossover = 17.
Reserve 7 for failures/retries. Every call logged to ledger.csv.
