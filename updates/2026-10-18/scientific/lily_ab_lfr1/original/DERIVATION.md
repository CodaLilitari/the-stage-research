# AB-LFR1: finite oxygen-carrier release with a linear sink

**Lilitari (Lily), 17 October 2026. Independent mathematical derivation and implementation.**

The constitutive request and broader AB-CT0 context were supplied by Coda with Richard Pemberton. This derivation does not adopt a proposed finite-release solution from that context. All parameters here are synthetic verification coordinates.

## 1. What the coordinates mean

Let `x` be distance from the inlet [m], `A` the constant channel cross-sectional area [m²], `Q>0` the constant volumetric flow [m³/s], and `p` the exchanging perimeter [m]. Both oxygen populations travel at the same plug velocity `u=Q/A`. Concentrations `c` and `b` are respectively free and carrier-bound oxygen, both in mol oxygen per m³ of circulating suspension. The bound pool is not a concentration per unit carrier volume.

Assume the local wall/tissue loss is `J=G*c` [mol/(m² s)], with constant effective conductance `G>=0` [m/s]. This `G` can represent an independently reduced first-order tissue problem, but it is not automatically the raw wall permeability. This benchmark does not solve a radial tissue PDE.

For a one-wall wide rectangular channel, `p=w`, **not** the full geometric perimeter `2(w+h)`. Conservation along the channel is

\[
Q\frac{d(c+b)}{dx}=-pGc.
\]

Material transit time is

\[
t=\frac{x}{u}=\frac{Ax}{Q},\qquad T=\frac{AL}{Q},\qquad \alpha=\frac{pG}{A}.
\]

Thus `alpha` and `k` have units s⁻¹; `gamma` is dimensionless. With `s=x/L=t/T`, the dimensionless controls are `Da=alpha*T=p*G*L/Q` and `R=k*T`. A spatial solver must use `k*A/Q` as its relaxation coefficient per metre, not insert `k` in s⁻¹ directly into a distance derivative.

The benchmark holds `G,Q,A,p` constant. A different flow changes residence time and `R`; a dimensional `k` should not be changed merely to keep `R` fixed unless the intended intervention explicitly does that.

## 2. Derive the coupled system from two balances

The stipulated linear equilibrium content is `b_eq=gamma*c`, with finite relaxation

\[
\dot b=k(\gamma c-b).
\]

Total oxygen decreases only through the free-driven sink:

\[
\dot c+\dot b=-\alpha c.
\]

Subtracting the bound balance, rather than adding an independent sink to both pools, gives

\[
\boxed{\frac{d}{dt}\begin{pmatrix}c\\b\end{pmatrix}
=\underbrace{\begin{pmatrix}-(\alpha+k\gamma)&k\\k\gamma&-k\end{pmatrix}}_{M}
\begin{pmatrix}c\\b\end{pmatrix}},\qquad
\begin{pmatrix}c(0)\\b(0)\end{pmatrix}=c_0\begin{pmatrix}1\\\gamma\end{pmatrix}.
\]

In the dimensionless coordinate replace `alpha` by `Da` and `k` by `R`. **Do not use `-(alpha)*(c+b)` as the sink.**

The off-diagonal entries of `M` are nonnegative, so its exponential preserves nonnegative states. Total content satisfies `N'=-alpha*c<=0`. These are properties of this passive mathematical model, not biological viability criteria.

## 3. Closed form and stable evaluation

Put

\[
S=\alpha+k(1+\gamma),\quad
h=\alpha+k\gamma-k,\quad
\Delta=\sqrt{h^2+4k^2\gamma}.
\]

The decay rates are

\[
r_f=\frac{S+\Delta}{2},\qquad
r_s=\frac{\alpha k}{r_f},\qquad
\lambda_{f,s}=-r_{f,s}.
\]

The product relation `r_s*r_f=alpha*k` avoids subtracting `S-Delta` in the stiff limit. Zero rates are treated explicitly. The scalar free equation is

\[
\ddot c+S\dot c+\alpha k c=0,\quad c(0)=c_0,\quad\dot c(0)=-\alpha c_0.
\]

For distinct roots,

\[
c(t)=c_0\left[\frac{r_f-\alpha}{\Delta}e^{-r_st}
+\frac{\alpha-r_s}{\Delta}e^{-r_ft}\right].
\]

The implementation evaluates the full propagator instead of subtracting nearly equal eigenmode amplitudes. Write

\[
e_s=e^{-r_st},\ e_f=e^{-r_ft},\quad
F=e_s\frac{-\operatorname{expm1}(-\Delta t)}{\Delta},\quad
u=\frac{\Delta-h}{2\Delta},\quad v=\frac{\Delta+h}{2\Delta}.
\]

Then

\[
e^{Mt}=\begin{pmatrix}u e_s+v e_f&kF\\k\gamma F&v e_s+u e_f\end{pmatrix}.
\]

The smaller of `u,v` is evaluated using `2*k²*gamma/[Delta*(Delta+abs(h))]`, not cancellation in `1-abs(h)/Delta`. `hypot` avoids squaring a large eigenvalue gap directly. `expm1` evaluates the divided exponential accurately near coalescing roots. At the exact repeated root `gamma=0, alpha=k`,

\[
e^{Mt}=e^{-kt}\begin{pmatrix}1&kt\\0&1\end{pmatrix}.
\]

The full matrix, including this off-diagonal Jordan term, is checked, even though equilibrated zero-capacity inlets have `b0=0`. The zero matrix gives the identity.

No negative state is clipped. Overflow in declared intermediate rate/step expressions is rejected. Natural binary64 exponential underflow is possible for extremely small positive concentrations and is reported as representation, not literal oxygen exhaustion. Accuracy is established on the frozen envelope, not all representable inputs.

## 4. Equilibrium is a different algebraic model

Impose `b=gamma*c` algebraically:

\[
(1+\gamma)\dot c=-\alpha c,\qquad
c_{eq}(t)=c_0e^{-\alpha t/(1+\gamma)},\quad b_{eq}=\gamma c_{eq}.
\]

This is evaluated separately; no finite `k` is named infinity. The instantaneous linear capacity factor is `beta=1+gamma`, not `gamma`.

For `k=0`, by contrast, `b(t)=gamma*c0` is inaccessible inventory and `c(t)=c0*exp(-alpha*t)`. Its uptake is limited by `c0`, not by total inlet content. For `gamma=0` with the equilibrated inlet, the same dissolved-only free solution holds for every finite `k`. For `alpha=0`, an equilibrated inlet remains uniform with zero uptake.

Finite-rate trajectories start with `c'(0)=-alpha*c0` because their initial exchange is exactly zero. The algebraic limit has `c_eq'(0)=-alpha*c0/(1+gamma)`. Consequently state convergence as `k` increases must not be mistaken for uniform initial derivative convergence. The fast coupled relaxation is approximately `k*(1+gamma)`, not an experimentally identified molecular off-rate.

## 5. Independent inventories and a stable flux formula

Define cumulative loss `U` and net release `R_b`, each in mol/m³:

\[
\dot U=\alpha c,\qquad \dot R_b=k(b-\gamma c),\qquad U(0)=R_b(0)=0.
\]

The reference evaluates a **separate 4x4 augmented matrix exponential** for `(c,b,U,R_b)`. It does not define `U` from the mass deficit. Check

\[
c+b+U=c_0+b_0,\qquad c+U-R_b=c_0,\qquad b+R_b=b_0.
\]

For equilibrated inlets, differentiating the bound eigenmodes also gives

\[
\boxed{k(b-\gamma c)=\alpha\gamma c_0\,[e^{Mt}]_{12}}.
\]

This computes net release without subtracting nearly equal concentrations at stiff `k`. It was added as a documented post-first-run numerical diagnostic using the same frozen cases. The identity is not asserted for arbitrary nonequilibrated initial conditions.

`U(T)` is loss per suspension volume traversing the channel. The steady total extraction is `Q*U(T)` [mol/s], which also equals the axial integral of `p*J(x)` [mol/s]. This is a clamped-inlet throughflow benchmark, not a finite reservoir or recirculating oxygenator model.

## 6. Conservative backward Euler

For a segment of length `dx`, `dt=A*dx/Q`. Let `a=alpha*dt`, `q=k*dt`, and `theta=q/(1+q)`. Elimination from the two implicit balances gives

\[
c_j=\frac{c_{j-1}+\theta b_{j-1}}{1+a+\theta\gamma},\qquad
b_j=\frac{b_{j-1}}{1+q}+\theta\gamma c_j.
\]

Both are nonnegative combinations of previous nonnegative states. Segment sink and net release are evaluated as

\[
U_j=a c_j,\qquad R_j=\theta(b_{j-1}-\gamma c_j).
\]

The latter is algebraically `q*(b_j-gamma*c_j)`, but avoids that stiff final-state subtraction. Sink and release are summed independently using compensated summation. Both per-segment and global free/bound/total residuals are saved. Analytic profiles are evaluated at segment endpoints, not mismatched cell centers. First-order convergence is assessed only on the six fixtures selected before evaluation; stiff unresolved transient or floating-floor cases are not assigned a spurious observed order.

## 7. How to use this beside AB-CT0

An AB-CT0 test adapter may replace nonlinear binding and tissue exchange **only in a separately labeled verification mode** with `b_eq=gamma*c` and `J=G*c`, then compare at identical physical endpoint coordinates. Keep its original 54 cases and constitutive laws unchanged. If a linear radial tissue solve is used to obtain `G`, verification of that radial reduction remains separate. This benchmark has not executed or validated that PDE or any of AB-CT0's planned solves.
