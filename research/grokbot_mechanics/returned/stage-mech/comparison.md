# Mechanical and fluid architecture: primary-source comparison

Prepared by Grok Bot for The Stage (Richard Pemberton), for independent checking by Coda. 2026-10-15.

## Source verification

| Source | DOI check (Crossref API, 2026-10-15) | Access to full text |
|---|---|---|
| Aubin, Choudhury, Jerch, Archer, Pikul, Shepherd 2019, Nature, "Electrolytic vascular systems for energy-dense robots" | 10.1038/s41586-019-1313-1 resolves, published 2019-06-19 | Paywalled. Abstract read via Crossref/EuropePMC. Figures and Methods NOT accessed. |
| Acome et al. 2018, Science 359:61, "Hydraulically amplified self-healing electrostatic actuators with muscle-like performance" | 10.1126/science.aao6139 resolves | Paywalled at science.org. Results text read from the Science digital edition page (sciencemagazinedigital.org, 5 Jan 2018, pg 86). Supplementary figs S11, S12 NOT opened. |
| Kawai, Nie, Oda, Morimoto, Takeuchi 2022, Matter 5:2190-2208, "Living skin on a robot" | 10.1016/j.matt.2022.05.019 resolves | cell.com and ScienceDirect blocked my fetches (Cloudflare). Content below comes from indexed full text and the Supplement listing; treat as reported but not opened by me. |
| Correction 2025, Matter, 10.1016/j.matt.2025.102162 | resolves; Crossref marks it as an erratum to 10.1016/j.matt.2022.05.019, dated 2025-06-04 | Text read via the Waseda University repository record (full erratum text). |
| Ren, Morimoto, Takeuchi 2025, Science Robotics, "Biohybrid hand actuated by multiple human muscle tissues" | 10.1126/scirobotics.adr5512 resolves, published 2025-02-26 (online 2025-02-12) | Paywalled. Abstract plus University of Tokyo press release (2025-02-13). Dryad dataset 10.5061/dryad.xd2547drh (CC0, 20 files) exists, but its file downloads returned 401/403 to my box, so I did not use it. |
| Clone Robotics, clonerobotics.com/android | official web page | Company claims only. Pump figures come from press reports of company statements (Interesting Engineering; Ars Technica, Feb 2025). |

Correction to the brief: the biohybrid hand paper's authors are Ren, Morimoto and Takeuchi (Xinzhu Ren is first author), not "Morimoto/Takeuchi". MuMuTA = multiple muscle tissue actuators, confirmed.

**What the 2025 Kawai correction changes** (Waseda record of 10.1016/j.matt.2025.102162):
1. In Fig. 3E, the unit for PBS(-) leakage is grams, not milligrams. The corrected text reads: dermis-equivalent leakage about **0.54 g after 1 h**, skin-equivalent leakage about **0.13 g after 1 h** (originally "5.4 mg" and "0.13 mg"). This is a 1000x change for the skin equivalent and 100x for the dermis equivalent. The original 5.4 mg also did not match 0.54 g by a unit change alone.
2. Scale bars: Fig. 2A (top) should be 5 mm, not 10 mm. Fig. 4D should be 3 mm, not 2 mm. Fig. 4E should be 5 mm, not 2 mm.
Consequence for The Stage: water loss through the living skin is 100 to 1000 times larger than the 2022 text stated. That makes humidity and medium replenishment a first-order design load for any skin exposed to air.

Legend: **R** = reported in the source (locator given), **D** = derived here, **C** = company claim, **NR** = not reported or not accessible to me, **S** = reported only via a secondary/indexed copy that I did not open directly.

## Table A. Company claims (not independently tested)

| Metric | Clone Robotics Myofiber / pump |
|---|---|
| Force | >= 1 kg force (about 9.8 N, D) per 3 g fiber [C, clonerobotics.com/android] |
| Displacement / strain | > 30 % unloaded contraction [C]. Loaded strain NR. |
| Speed | response < 50 ms [C] |
| Runtime / cycles | NR |
| Support condition | Water-based hydraulic fluid per press coverage [C/S]. Dry exterior. |
| Power / thermal | 500 W pump, 40 SLPM at 100 psi [C via press]. p*Q = 460 W hydraulic (D, calc/output.txt sec. 4). Thermal NR. |
| Maintenance | NR |
| Failure evidence | "monolithic musculotendon units to eliminate tendon failures" [C]. No failure data published. Protoclone demo was ceiling-suspended (press, S). |

## Table B. Bench experiments (component level)

| Metric | HASEL (Acome 2018) | Living skin (Kawai 2022 + 2025 corr.) | MuMuTA (Ren 2025) |
|---|---|---|---|
| Force / stress | Planar 2-unit: 114 kPa actuation stress under 700 g; 1-unit: 32 kPa under 250 g [R, Science digital ed. p.86 / fig. S11] | Dermis tensile strength 4.4 kPa (14 d culture) vs 2.6 kPa (3 d) [S, Fig. S5A] | ~8 mN contractile force per MuMuTA [R, abstract] |
| Displacement / strain | 79 % (1-unit, quasi-static); 107 % (1-unit) and 124 % (2-unit) near resonance [R] | Skin layer on finger 2.34 +/- 0.28 mm thick [S] | ~4 mm contractile length [R, abstract] |
| Frequency / speed | Gain near resonance (frequency in fig. S11, NR to me). Peak specific power 614 W/kg, specific work 70 J/kg [R] | Finger bending repeated (Video S5); cycle count NR | Stimulation saturated near 600 ms and 1.5 V/mm [S] |
| Runtime / cycles | "Cycle life" paragraph is cut off in my copy. >1e6 cycles for donut HASEL at 15 % strain, 150 g, no degradation, test stopped for time [author comment on iMechanica journal club, not peer reviewed] | Culture 3, 7, 14 d; wound repair 7 d after graft [S] | Force fell to ~90 % after 10 min at 2 ms pulses every 3 s and recovered after 1 h rest [R, press release; numbers S]. Tissue contractile to day 178 [S, unverified] |
| Wet / dry | Dry operation in air. Liquid dielectric sealed in a pouch (vegetable transformer oil, Envirotemp FR3) [author comment] | In culture medium during culture; leakage tests in PBS(-) [R, corr.] | Must be immersed in culture medium. Hand floats in liquid so anchors move without friction [R, press release] |
| Power / thermal | High voltage (kV range; exact values in fig., NR to me). Efficiency NR in my copy | Passive, NR | Electrical field stimulation via gold electrodes [R, press]. Power NR |
| Maintenance | Dielectric oil permeates silicone shells over weeks to months ("sweating") [author comment] | Medium culture; collagen sheet graft for repair [R] | Medium exchange (details NR) |
| Failure evidence | Self-heals after dielectric breakdown [R, abstract]. Silicone oil swelled shells within hours [author comment] | PBS(-) leakage 0.54 g/h dermis, 0.13 g/h skin [R, corrected] | Fatigue after 10 min; necrosis drives thin-strand design [R, press] |

## Table C. Whole-system demonstrations

| Metric | Aubin 2019 lionfish robot | Ren 2025 biohybrid hand | Kawai 2022 skin-covered finger |
|---|---|---|---|
| What moved | Untethered aquatic soft robot; ZnI2 redox electrolyte is both hydraulic fluid and flow-battery energy store [R, abstract] | 18 cm hand, multijoint fingers, individual finger control, scissor gesture, pipette tip grasp [R, press] | Three-joint robotic finger bending under living skin [R] |
| Force | NR (paywalled) | Finger force NR | none (passive skin) |
| Speed | 1.5 body lengths/min [secondary, Chemistry World] | NR | NR |
| Runtime | "up to 36 hours" [R, abstract] | Max force held ~30 min [S] | culture-limited |
| Energy | Energy storage +325 % vs separate battery plus hydraulic fluid [R via Cornell press; Fig. 4f in paper, NR to me] | NR | NR |
| Support condition | Submerged in water | Submerged in medium | In medium / humid |
| Failure | Buoyancy problems, weighted down [secondary] | No active return stroke, fingers float back [R, press] | See leakage |

Gaps I did not fill: Aubin flow rates, cell voltage, membrane type, pump power and cycle data; HASEL voltages and figure-level frequencies; MuMuTA cross-sections and per-tissue dimensions. All are behind paywalls or in the inaccessible Dryad files.
