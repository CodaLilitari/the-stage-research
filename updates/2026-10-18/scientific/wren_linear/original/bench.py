#!/usr/bin/env python3
"""FIXED BUT NOT EXECUTED (float/bool casts after run-2 JSON crash). Finite-release linear benchmark. Wren (AI collaborator, via Grok Bot). Python 3 + numpy.
Nonclinical, hypothetical, linear model only."""
import math, json, csv, sys, platform
import numpy as np

C0 = 0.2
LEDGER = []
# Run 1 (19:12 EDT) crashed at the D log line (TypeError: missing status arg) AFTER 12 ODE calls had executed.
# Their outputs were never persisted. Per the frozen cap (failures included) they are logged as calls 1-12.
for _n in ("F1","F2","F3","F4","F5","F6"):
    LEDGER.append(dict(call=len(LEDGER)+1, case=_n, kind="exact+balance (run 1)", status="FAIL-lost", note="executed; output lost to script crash"))
for _n in ("F1","F2","F3","F4","F5","F6"):
    LEDGER.append(dict(call=len(LEDGER)+1, case=_n, kind="RK4 validation (run 1)", status="FAIL-lost", note="executed; output lost to script crash"))
RK4_CASES = ("F2",)   # only 1 validation fits in the remaining cap (see DEVIATIONS.md)
DO_CROSSOVER = False  # k* bisection dropped to stay within 24 calls
TOL_REL, TOL_ABS = 1e-10, 1e-14

def log(case, kind, status, note=""):
    LEDGER.append(dict(call=len(LEDGER)+1, case=case, kind=kind, status=status, note=note))
    if len(LEDGER) > 24: raise RuntimeError("ledger cap exceeded")

def shc(x):  # sinh(x)/x, stable near 0
    if abs(x) < 1e-3:
        x2 = x*x; return 1 + x2/6 + x2*x2/120 + x2**3/5040
    return math.sinh(x)/x

def amat(a, k, g):
    return [[-(a+k*g), k], [k*g, -k]]

def exact(a, k, g, t, c0=C0):
    A = amat(a, k, g)
    m = 0.5*(A[0][0]+A[1][1])
    det = A[0][0]*A[1][1]-A[0][1]*A[1][0]
    disc = (0.5*(A[0][0]-A[1][1]))**2 + A[0][1]*A[1][0]   # = m^2 - det, written without cancellation
    d = math.sqrt(disc)
    em, ch, sh = math.exp(m*t), math.cosh(d*t), t*shc(d*t)
    x0 = [c0, g*c0]
    B = [[A[0][0]-m, A[0][1]], [A[1][0], A[1][1]-m]]
    c = em*(ch*x0[0] + sh*(B[0][0]*x0[0]+B[0][1]*x0[1]))
    b = em*(ch*x0[1] + sh*(B[1][0]*x0[0]+B[1][1]*x0[1]))
    return c, b, dict(m=m, d=d, lam1=m+d, lam2=m-d, det=det)

def int_c(a, k, g, T, panels=64, nodes=32):
    xg, wg = np.polynomial.legendre.leggauss(nodes)
    tot = 0.0; h = T/panels
    for p in range(panels):
        lo = p*h
        for xi, wi in zip(xg, wg):
            tot += wi*0.5*h*exact(a, k, g, lo+0.5*h*(xi+1))[0]
    return float(tot)

def rk4(a, k, g, T, c0=C0):
    A = amat(a, k, g)
    lam = abs(exact(a, k, g, 0.0)[2]['lam2'])
    hmax = min(1e-3, 0.01/lam) if lam > 0 else 1e-3
    N = math.ceil(T/hmax); h = T/N
    c, b = c0, g*c0
    f = lambda c, b: (A[0][0]*c+A[0][1]*b, A[1][0]*c+A[1][1]*b)
    for _ in range(N):
        k1 = f(c, b); k2 = f(c+0.5*h*k1[0], b+0.5*h*k1[1])
        k3 = f(c+0.5*h*k2[0], b+0.5*h*k2[1]); k4 = f(c+h*k3[0], b+h*k3[1])
        c += h/6*(k1[0]+2*k2[0]+2*k3[0]+k4[0]); b += h/6*(k1[1]+2*k2[1]+2*k3[1]+k4[1])
    return c, b, N

def close(x, y): return abs(x-y) <= TOL_ABS + TOL_REL*abs(y)

CASES = {"F1": (0.2, 0.0, 4.0, 8.0), "F2": (0.2, 1/30, 4.0, 8.0), "F3": (0.2, 10.0, 4.0, 8.0),
         "F4": (0.2, 0.2, 0.0, 8.0), "F5": (0.0, 0.2, 4.0, 8.0), "F6": (0.2, 1/30, 4.0, 80.0)}

def main():
    R = {"byline": "Wren (AI collaborator, via Grok Bot)", "units": "c,b,U in mol/m^3 fluid; t in s; Q in m^3/s; Q*U in mol/s",
         "cases": {}, "checks": {}}
    for n, (a, k, g, T) in CASES.items():
        c, b, info = exact(a, k, g, T)
        tot_in = C0*(1+g); tot_out = c+b; U = tot_in-tot_out
        ic = int_c(a, k, g, T); aint = a*ic
        bal_ok = abs(U-aint) <= TOL_ABS + TOL_REL*max(abs(U), abs(aint))
        R["cases"][n] = dict(a=a, k=k, gamma=g, T=T, c=c, b=b, total_out=tot_out, U=U, a_int_c=aint,
                             balance_residual=U-aint, balance_ok=bool(bal_ok), positive=bool(c >= 0 and b >= 0), **info)
        log(n, "exact+balance", "ok" if bal_ok and c >= 0 and b >= 0 else "FAIL", f"U-a*int={U-aint:.3e}")
    for n, (a, k, g, T) in CASES.items():
        if n not in RK4_CASES: continue
        c, b, N = rk4(a, k, g, T); e = R["cases"][n]
        ok = close(c, e["c"]) and close(b, e["b"])
        e.update(rk4_c=c, rk4_b=b, rk4_steps=N, rk4_dc=c-e["c"], rk4_db=b-e["b"], rk4_ok=bool(ok))
        log(n, "RK4 validation", "ok" if ok else "FAIL", f"N={N} dc={c-e['c']:.2e} db={b-e['b']:.2e}")
    a, T = 0.2, 3.0; cD = C0*math.exp(-a*T)
    R["cases"]["D"] = dict(a=a, gamma=0, T=T, c=cD, b=0.0, total_out=cD, U=C0-cD, a_int_c=C0*(1-math.exp(-a*T)))
    log("D", "algebraic", "ok")
    g, T = 4.0, 8.0; cE = C0*math.exp(-a*T/(1+g))
    R["cases"]["E"] = dict(a=a, gamma=g, T=T, c=cE, b=g*cE, total_out=(1+g)*cE, U=C0*(1+g)-(1+g)*cE,
                           U_expm1_form=-(1+g)*C0*math.expm1(-a*T/(1+g)))
    log("E", "algebraic", "ok")
    T = 80.0; cE80 = C0*math.exp(-a*T/(1+g))
    R["checks"]["F6_vs_eq_T80"] = dict(c_eq=cE80, b_eq=g*cE80, U_eq=-(1+g)*C0*math.expm1(-a*T/(1+g)),
        c_F6=R["cases"]["F6"]["c"], ratio_c=R["cases"]["F6"]["c"]/cE80)
    log("F6", "equilibrium diagnostic T=80", "ok")
    # hydraulics
    L = W = 1e-3; h = 100e-6; V = 0.1e-9; Pcap = 0.468; Pwcap = 1.04e-11
    hyd = {}
    for name, mu in (("dissolved", 0.00078), ("carrier", 4*0.00078)):
        Rh = 12*mu*L/(W*h**3); Qp = Pcap/Rh; Qw = math.sqrt(Pwcap/Rh); Q = min(Qp, Qw)
        hyd[name] = dict(mu=mu, R=Rh, Q_pressure_cap=Qp, Q_power_cap=Qw, Q=Q, binding="pressure" if Qp <= Qw else "power",
                         residence_s=V/Q, dP=Q*Rh, power=Q*Q*Rh)
        log(name, "hydraulics", "ok", f"res={V/Q:.6g}s bind={hyd[name]['binding']}")
    R["hydraulics"] = hyd
    for n in ("D", "E", "F1", "F2", "F3", "F6"):
        e = R["cases"][n]; Q = hyd["dissolved" if n == "D" else "carrier"]["Q"]
        if n == "F6": e["Q_note"] = "F6 T=80 is not on the hydraulic envelope; Q*U shown with carrier Q only for scale"
        e["Q"] = Q; e["QU_mol_per_s"] = Q*e["U"]
    # crossover k*
    if not DO_CROSSOVER:
        R["crossover"] = dict(status="not computed: ledger cap after run-1 crash; see DEVIATIONS.md")
    else:
        f = lambda k: exact(0.2, k, 4.0, 8.0)[0]-cD
        lo, hi = 1e-8, 10.0; flo, fhi = f(lo), f(hi); nev = 2
        if flo*fhi < 0:
            for _ in range(60):
                mid = 0.5*(lo+hi); fm = f(mid); nev += 1
                if (fm < 0) == (flo < 0): lo, flo = mid, fm
                else: hi = mid
            R["crossover"] = dict(k_star=0.5*(lo+hi), bracket=[lo, hi], internal_evals=nev, c_D=cD,
                                  note="monotonicity in k assumed, not proven")
            log("k*", "bisection (1 call)", "ok", f"k*={0.5*(lo+hi):.12g} evals={nev}")
        else:
            R["crossover"] = dict(status="no sign change", f_lo=flo, f_hi=fhi); log("k*", "bisection", "FAIL", "no bracket")
    # limits
    F = R["cases"]
    R["checks"]["F1_k0_limit"] = dict(c_vs_dissolved_rel=F["F1"]["c"]/(C0*math.exp(-1.6))-1, b_minus_gc0=F["F1"]["b"]-0.8)
    R["checks"]["F4_repeated"] = dict(d=F["F4"]["d"], c_vs_exp_rel=F["F4"]["c"]/(C0*math.exp(-1.6))-1, b=F["F4"]["b"])
    R["checks"]["F5_a0"] = dict(U=F["F5"]["U"], total_out_minus_in=F["F5"]["total_out"]-1.0)
    R["checks"]["F3_vs_E"] = dict(c_F3=F["F3"]["c"], c_E=F["E"]["c"], rel=F["F3"]["c"]/F["E"]["c"]-1)
    R["ledger_calls"] = len(LEDGER)
    json.dump(R, open("results.json", "w"), indent=1, sort_keys=True)
    with open("ledger.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["call", "case", "kind", "status", "note"]); w.writeheader(); w.writerows(LEDGER)
    with open("ENV.txt", "w") as fh:
        fh.write(f"python {sys.version}\nnumpy {np.__version__}\nplatform {platform.platform()}\nscipy: not installed (not used)\nmpmath: not installed (not used)\n")
    print(json.dumps(R, indent=1, sort_keys=True))

if __name__ == "__main__": main()
