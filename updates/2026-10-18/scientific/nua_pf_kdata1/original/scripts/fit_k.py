"""PF-KDATA1 fit script — frozen plan implementation.
Fits M1 (single exponential) and M2 (exponential with lag) per carrier group,
plus M1 window-sensitivity refits. Every optimizer invocation increments
notes/fit_ledger.json (budget: 30 calls). Run: python3 scripts/fit_k.py
"""
import json, csv
import numpy as np
from scipy.optimize import curve_fit

BASE = "<HISTORICAL_SANDBOX_PATH_OMITTED>"  # Public copy; use tools/reproduce.py, not this historical entry point.
LEDGER = f"{BASE}/notes/fit_ledger.json"

def ledger_call(desc, ok, extra=None):
    L = json.load(open(LEDGER))
    L["calls_used"] += 1
    entry = {"n": L["calls_used"], "desc": desc, "ok": ok}
    if extra: entry.update(extra)
    L["calls"].append(entry)
    json.dump(L, open(LEDGER, "w"), indent=2)
    if L["calls_used"] > L["budget_max_calls"]:
        raise RuntimeError("fit-call budget exceeded")

def m1(t, Ainf, dA, k):
    return Ainf - dA * np.exp(-k * t)

def m2(t, Ainf, dA, k, tlag):
    te = np.where(t >= tlag, t - tlag, 0.0)
    return Ainf - dA * np.exp(-k * te)

def load():
    d = {}
    with open(f"{BASE}/inputs/o2_offloading_exp.csv") as f:
        for r in csv.DictReader(f):
            d.setdefault(r["group"], []).append((float(r["t_s"]), float(r["absorbance_437nm"])))
    return {g: (np.array([p[0] for p in v]), np.array([p[1] for p in v])) for g, v in d.items()}

def guess(t, y):
    Ainf0 = float(y[-50:].mean()); A0 = float(y[:10].mean())
    dA0 = max(Ainf0 - A0, 1e-6)
    mid = A0 + 0.5 * dA0
    idx = np.argmax(y >= mid)
    thalf = float(t[idx]) if idx > 0 else float(t[-1]) / 4
    k0 = np.log(2) / max(thalf, 1e-6)
    return Ainf0, dA0, k0

def fit(model, t, y, p0, bounds, desc):
    try:
        popt, pcov = curve_fit(model, t, y, p0=p0, bounds=bounds, maxfev=20000)
        perr = np.sqrt(np.diag(pcov))
        resid = y - model(t, *popt)
        ss = float(np.sum(resid ** 2)); n = len(y); p = len(popt)
        aicc = float(n * np.log(ss / n) + 2 * p + 2 * p * (p + 1) / max(n - p - 1, 1))
        ledger_call(desc, True, {"ss": ss, "aicc": aicc})
        return {"popt": [float(x) for x in popt], "se": [float(x) for x in perr],
                "ss": ss, "aicc": aicc, "n": n,
                "resid_rms": float(np.sqrt(ss / n)),
                "resid": [float(x) for x in resid]}
    except Exception as e:
        ledger_call(desc, False, {"error": str(e)[:200]})
        return {"error": str(e)[:200]}

def main():
    data = load()
    out = {}
    for g, (t, y) in data.items():
        Ainf0, dA0, k0 = guess(t, y)
        tspan = float(t[-1] - t[0])
        r1 = fit(m1, t, y, [Ainf0, dA0, k0],
                 ([0, 0, 0], [np.inf, np.inf, np.inf]), f"M1 {g} full")
        r2 = fit(m2, t, y, [Ainf0, dA0, k0, 0.0],
                 ([0, 0, 0, 0], [np.inf, np.inf, np.inf, 0.2 * tspan]),
                 f"M2 {g} full")
        # window sensitivity for M1: drop first 10% / last 20% of time span
        wins = {"full": (t, y)}
        m10 = t[0] + 0.10 * tspan; m20 = t[0] + 0.80 * tspan
        wins["drop_first10pct"] = (t[t >= m10], y[t >= m10])
        wins["drop_last20pct"] = (t[t <= m20], y[t <= m20])
        sens = {}
        for wn, (tw, yw) in wins.items():
            if wn == "full":
                sens[wn] = r1
                continue
            A0_, dA0_, k0_ = guess(tw, yw)
            sens[wn] = fit(m1, tw, yw, [A0_, dA0_, k0_],
                           ([0, 0, 0], [np.inf, np.inf, np.inf]),
                           f"M1 {g} {wn}")
        out[g] = {"M1": r1, "M2": r2, "M1_window_sensitivity": sens,
                  "t_range": [float(t[0]), float(t[-1])], "n": len(t)}
    json.dump(out, open(f"{BASE}/outputs/fit_results.json", "w"), indent=2)
    L = json.load(open(LEDGER))
    print("calls used:", L["calls_used"], "| failures:",
          sum(1 for c in L["calls"] if not c["ok"]))
    for g, r in out.items():
        for m in ["M1", "M2"]:
            rr = r[m]
            if "error" in rr:
                print(g, m, "FAILED:", rr["error"]); continue
            p, s = rr["popt"], rr["se"]
            ks = f"k={p[2]:.3f}±{s[2]:.3f}" if len(p) > 2 else ""
            extra = f" tlag={p[3]:.4f}±{s[3]:.4f}s" if m == "M2" else ""
            print(f"{g} {m}: {ks}{extra} ss={rr['ss']:.2e} aicc={rr['aicc']:.1f}")

if __name__ == "__main__":
    main()
