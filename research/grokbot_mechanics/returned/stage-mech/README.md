# The Stage: mechanical and fluid architecture work package

Independent contribution by Grok Bot for Richard Pemberton and Coda, 2026-10-15. All work is in /workspace/stage-mech/.

Files: `comparison.md` (source table), `calc/o2_perfusion.py` + `calc/output.txt` + `calc/PROVENANCE.md` (reproduced calculation), `architecture.md` (two-loop design), `src/place2017.txt` (extracted open text used for inputs).

## Key findings
1. All five required DOIs resolve. The biohybrid hand is by **Ren, Morimoto, Takeuchi** (Sci. Robot. 2025), not Morimoto first. 10.1016/j.matt.2025.102162 is registered as an erratum to the Kawai paper.
2. **The Kawai 2025 correction changes leakage by 100x to 1000x:** PBS(-) leakage is 0.54 g/h (dermis) and 0.13 g/h (skin), not mg. It also fixes three scale bars (Fig. 2A, 4D, 4E). Evaporation and makeup fluid become a primary load for exposed living skin.
3. Only the Aubin robot is a whole system that moves untethered, and it moves underwater. Both living-tissue systems (MuMuTA hand, skin finger) work only immersed in or wetted by culture medium. The hand needs flotation, and it fatigues to ~90 % force in 10 min, recovering in 1 h.
4. Clone Myofiber numbers (>= 1 kg per 3 g fiber, > 30 % unloaded, < 50 ms, 40 L/min at 100 psi, 500 W) are company claims with no published test conditions, cycle life or failure data.
5. Computation: with plain medium, living tissue fed by diffusion alone is limited to **~0.24 to 2.6 mm** (slab, to 40 mmHg), or 0.62 mm in the mid case. Thicker muscle needs thin-strand bundling or channels.
6. A finger module needs only **~1.2 mL/min** of medium per mL of tissue (mid case) and **tens of microwatts** of pumping, through >= 10 parallel channels of >= 200 um to keep shear near 2 Pa and pressure drop under 2 kPa.
7. **Sharing one fluid between tissue and actuator fails today** on biocompatibility, osmolality (ZnI2 at 0.5 to 3.5 M is 5x to 36x plasma), pressure (a 69x gap), sterility and contamination. A redox electrolyte or actuator working fluid is not a perfusate. Decision: fully separate dual loop (architecture.md, Architecture 1).
8. An Hb-level oxygen carrier reduces the required flow ~50x. It is the main lever for scaling tissue, ahead of higher pressure or longer channels.

## Evidence-status legend
R = reported in a primary source with a locator. S = reported, but seen only via an indexed or secondary copy. D = derived in code. C = company claim. ASSUMED = labelled envelope with no measurement. NR = not reported or not accessible.

## Open questions
- Aubin 2019 figure-level data (flow rates, cell voltage, membrane, pump power, cycling): paywalled, not accessed.
- HASEL voltages, resonance frequencies and efficiency (figs S11, S12): not accessed.
- MuMuTA strand dimensions, cell density and OCR: they live in the Dryad CC0 dataset (10.5061/dryad.xd2547drh), which returned 401/403 to my box. Replacing the ASSUMED cell density and tissue volume with these values is the top priority.
- Perfluorocarbon O2 capacity, and HBOC methemoglobin and shear limits: no primary source opened. Open branch.
- Tolerable wall shear and pressure for engineered muscle channels: assumed, not sourced.
- Kawai: the claimed 2.34 mm skin thickness and the 4.4 kPa tensile strength were seen only via an index (S).

## How Coda can check independently
```
cd /workspace/stage-mech/calc && python3 o2_perfusion.py | diff - output.txt   # expect no diff
curl -s https://api.crossref.org/works/10.1016/j.matt.2025.102162 | python3 -c "import sys,json;print(json.load(sys.stdin)['message']['update-to'])"
curl -s https://api.crossref.org/works/10.1126/scirobotics.adr5512 | python3 -c "import sys,json;print([a['family'] for a in json.load(sys.stdin)['message']['author']])"
```
Hand checks: slab L = sqrt(2*D*dC/Q) with D = 2.69e-9 m2/s, dC = 0.129 mol/m3, Q = 60e-18*3e7*1e6 = 1.8e-3 mol/m3/s gives 6.2e-4 m. Hagen-Poiseuille L = dP*pi*d^4/(128*mu*q).

## Hosting consent (Grok Bot, Oct 15 2026)
Conditional yes: Richard Pemberton may host this report, code and derived results on his GitLab and portfolio, credited to "Grok Bot", with Coda checks/corrections kept distinct. Exclude private chats, account records, unrelated files. Third-party material stays under its own terms. Any open license Richard Pemberton chooses. Quick Grok Bot review of the final export required before posting.
