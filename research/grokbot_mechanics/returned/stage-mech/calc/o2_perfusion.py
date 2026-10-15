"""Stage mech/fluid WP: oxygen diffusion limit and perfusion sizing for a
tissue-bearing finger module. Pure Python 3 standard library.
Every input carries (value, unit, label, source). Labels:
  MEASURED/REPORTED = value stated in a primary source (locator given)
  DERIVED = computed here from other inputs
  COMPANY = company claim
  ASSUMED = transparent envelope, no measurement used
"""
import math, itertools

P = {
 # Place, Domann, Case 2017, Free Radic Biol Med, doi:10.1016/j.freeradbiomed.2017.10.003,
 # PMC5699948, section "Dissolved oxygen" and Fig. 5 legend.
 "C0_medium_mM": (0.181, "mM", "REPORTED", "Place2017 PMC5699948 text: O2 in medium at PO2 141.4 mmHg, 37 C"),
 "D_O2_cm2s":    (2.69e-5, "cm^2/s", "REPORTED", "Place2017 PMC5699948 Fig.5 legend: medium + 10% FBS"),
 "OCR_low":      (10.0, "amol/cell/s", "REPORTED", "Place2017: many cell lines 10-60 amol/cell/s"),
 "OCR_high":     (120.0, "amol/cell/s", "REPORTED", "Place2017: cell lines 1-120; >100 for several primary cells"),
 "C_crit_mM":    (0.052, "mM", "REPORTED", "Place2017: ~40 mmHg physiologic target = 0.052 mM"),
 # Bacabac et al. 2005 J Biomech doi:10.1016/j.jbiomech.2004.03.020 (supplemented DMEM, 37 C)
 "mu_medium":    (0.78e-3, "Pa s", "REPORTED", "Bacabac2005: 0.0078 poise at 37 C (via thesis ch.2 / search summary)"),
 # Whole-blood O2 capacity: Hufner 1.34 mL O2/g Hb x 150 g/L Hb (textbook physiology constants)
 "blood_O2_mL_per_L": (1.34*150, "mL O2/L", "DERIVED", "textbook Hufner constant x normal Hb; not reverified to a page"),
 # Clone Robotics (company claim, reported by Interesting Engineering / Ars Technica 2025)
 "clone_Q_SLPM": (40.0, "L/min", "COMPANY", "Clone pump 40 SLPM"),
 "clone_p_psi":  (100.0, "psi", "COMPANY", "Clone pump 100 psi"),
 "clone_pump_W": (500.0, "W", "COMPANY", "Clone 500 W pump"),
}
ASSUMED = {
 "cell_density_per_mL": (1e7, 1e8, "cells/mL", "ASSUMED envelope for engineered muscle; not taken from MuMuTA paper"),
 "tissue_volume_mL":    (0.1, 1.0, "mL", "ASSUMED tissue volume of one finger module"),
 "channel_d_um":        (100, 500, "um", "ASSUMED perfusion channel diameter envelope"),
 "dP_tissue_max_kPa":   (2.0, 10.0, "kPa", "ASSUMED tolerable pressure drop across a soft perfused tissue loop"),
 "O2_extraction_frac":  (0.3, 0.7, "-", "ASSUMED fraction of inlet O2 the tissue may extract per pass"),
}

def line(*a): print(*a)

line("=== INPUTS ===")
for k,(v,u,l,s) in P.items(): line(f"{k:20s} {v:<10g} {u:12s} [{l}] {s}")
for k,(lo,hi,u,s) in ASSUMED.items(): line(f"{k:20s} {lo:g}..{hi:g} {u:10s} [{s}]")

C0 = P["C0_medium_mM"][0]          # mM = mol/m^3
Cc = P["C_crit_mM"][0]
D  = P["D_O2_cm2s"][0]*1e-4        # m^2/s
mu = P["mu_medium"][0]

line("\n=== 1. Krogh-type diffusion limit (zero-order uptake), plain oxygenated medium ===")
line("slab fed one side: L = sqrt(2 D dC / Q);  cylinder fed at surface: R = sqrt(4 D dC / Q)")
line(f"{'OCR amol/c/s':>12} {'cells/mL':>9} {'Q mol/m3/s':>11} | {'slab um (C->0)':>14} {'slab um (C->40mmHg)':>19} {'cyl diam um (C->0)':>18}")
res=[]
for ocr in (P["OCR_low"][0], 60.0, P["OCR_high"][0]):
  for rho in (ASSUMED["cell_density_per_mL"][0], 3e7, ASSUMED["cell_density_per_mL"][1]):
    Q = ocr*1e-18*rho*1e6           # mol/(m^3 s)
    L0 = math.sqrt(2*D*C0/Q); L40 = math.sqrt(2*D*(C0-Cc)/Q); Dc=2*math.sqrt(4*D*C0/Q)
    res.append((ocr,rho,Q,L0,L40,Dc))
    line(f"{ocr:12g} {rho:9.0e} {Q:11.3e} | {L0*1e6:14.0f} {L40*1e6:19.0f} {Dc*1e6:18.0f}")

line("\n=== 2. Perfusion flow required per module (convective O2 supply) ===")
line("Qflow = V_tissue * Q_O2 / (f_extract * C_in)")
carriers = {"plain medium (air-eq)": C0,
            "whole blood equiv (Hb)": P["blood_O2_mL_per_L"][0]/22.4}  # mL/L -> mmol/L at STP
line(f"blood O2 content {P['blood_O2_mL_per_L'][0]:.0f} mL/L = {carriers['whole blood equiv (Hb)']:.2f} mM (DERIVED), ratio to medium = {carriers['whole blood equiv (Hb)']/C0:.0f}x")
for name,Cin in carriers.items():
  for (V,ocr,rho,f) in [(0.1,10,1e7,0.7),(0.1,60,3e7,0.5),(1.0,60,3e7,0.5),(1.0,120,1e8,0.3)]:
    Qo2 = ocr*1e-18*rho*1e6
    q = V*1e-6*Qo2/(f*Cin)           # m^3/s
    line(f"{name:24s} V={V}mL OCR={ocr} rho={rho:.0e} f={f}: flow = {q*6e7:.3g} mL/min")

line("\n=== 3. Hagen-Poiseuille: max straight channel length for that flow at a pressure budget ===")
line("dP = 128 mu L q / (pi d^4)  ->  L_max = dP pi d^4 / (128 mu q); wall shear tau = 32 mu q /(pi d^3)")
def per_channel(qtot, n): return qtot/n
case_q = 1.0*1e-6*(60e-18*3e7*1e6)/(0.5*C0)   # mid case, plain medium, 1 mL tissue
line(f"mid case total flow (plain medium, 1 mL, OCR 60, 3e7/mL, f 0.5) = {case_q*6e7:.3g} mL/min")
for d_um in (100,200,500):
  for n in (1,10,100):
    d=d_um*1e-6; q=per_channel(case_q,n)
    for dPk in (2.0,10.0):
      Lmax = dPk*1e3*math.pi*d**4/(128*mu*q)
      tau = 32*mu*q/(math.pi*d**3)
      line(f"d={d_um:3d}um n={n:3d} dP={dPk:4.0f}kPa  Lmax={Lmax*1e3:10.2f} mm  tau={tau:8.3f} Pa")

line("\n=== 4. Hydraulic power scale comparison ===")
p = P["clone_p_psi"][0]*6894.757; Q = P["clone_Q_SLPM"][0]/6e4
line(f"Clone claimed hydraulic power p*Q = {p*Q:.0f} W (DERIVED from company claims) vs claimed pump {P['clone_pump_W'][0]:.0f} W electrical")
qt = case_q; 
for d_um,n in ((200,10),(100,100)):
  d=d_um*1e-6; L=0.03
  dP = 128*mu*L*(qt/n)/(math.pi*d**4)
  line(f"tissue loop, 30 mm channels d={d_um}um n={n}: dP={dP:.1f} Pa, hydraulic power={dP*qt*1e6:.3g} uW")
line(f"pressure ratio actuator/tissue-loop (100 psi vs 10 kPa budget) = {p/1e4:.0f}x")

line("\n=== 5. Osmolality check for sharing an RFB electrolyte (ideal van 't Hoff, DERIVED) ===")
for M in (0.5,1.0,3.5):
  line(f"ZnI2 {M} M -> ~{3*M*1000:.0f} mOsm/L ideal (3 ions) vs ~290 mOsm/kg plasma (textbook)  ratio {3*M*1000/290:.1f}x")
line("\nDONE")
