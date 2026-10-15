# Two-loop architecture for a first tissue-bearing moving module

Target module: one finger with living muscle actuators (MuMuTA-like bundles, Ren 2025) and/or a living skin cover (Kawai 2022), driven by or assisted by a non-living actuator. Numbers marked (calc) come from calc/output.txt.

## Loop A: tissue-support circulation
- **Perfusate options, in order of near-term feasibility:**
  1. Plain oxygenated culture medium (serum-free defined medium preferred), air-equilibrated: 0.181 mM O2 (Place 2017). Lowest risk, but it carries the least O2.
  2. Synthetic carrier: perfluorocarbon emulsion. O2 is physically dissolved, linear in PO2, and there are no human donor issues. Its capacity was NOT quantified here (no primary source opened); open item.
  3. Human-derived: washed RBCs or HBOC. Whole-blood-equivalent Hb carries about 50x more O2 than air-equilibrated medium (derived, calc sec. 2). Costs: hemolysis under pump shear, short RBC storage life, HBOC methemoglobin and NO scavenging, and the sourcing ethics. A parallel branch, not the first build.
- **Temperature:** 37 C +/- 0.5 C (standard culture practice, assumed target).
- **pH / CO2:** pH 7.2 to 7.4 with 5 % CO2 bicarbonate buffering, or HEPES if the gas exchanger is off-line (standard practice, assumed target).
- **Sterility:** closed loop, 0.2 um sterile filter on gas and makeup lines, single-use wetted parts. No shared seals with Loop B.
- **Filtration and waste:** in-line cell-debris filter; lactate and ammonia removed by bleed-and-feed medium exchange. The exchange rate is an open item because no source I accessed gives a MuMuTA metabolite load.
- **Flow (calc sec. 2):** plain medium needs 0.005 to 13 mL/min per module across the envelope, mid case 1.19 mL/min for 1 mL of tissue. An Hb-level carrier cuts that by 50x (mid case 0.024 mL/min).

## Loop B: mechanical / energy fluid
- **Option B1, hydraulic muscles (Clone-like):** water-based hydraulic fluid at up to 100 psi (689 kPa) and about 460 W hydraulic power for a full android (company claims, calc sec. 4).
- **Option B2, redox electrolyte (Aubin 2019):** a ZnI2 flow-battery electrolyte that is both energy store and hydraulic fluid. It is electrochemically active, and at 0.5 to 3.5 M it is about 5 to 36x plasma osmolality (derived, calc sec. 5).
- **Option B3, HASEL:** a sealed dielectric liquid (vegetable transformer oil) that never circulates. Its interface is electrical (kV), not fluidic.

## Can one fluid serve both loops? Condition by condition

| Condition | Required for tissue | B1 hydraulic water | B2 redox electrolyte | B3 dielectric oil | Shared possible today? |
|---|---|---|---|---|---|
| Biocompatibility | non-toxic, nutrient-bearing | Only if the fluid IS medium | No: Zn2+ / polyiodide chemistry | No: oil, not aqueous | **Fail** for B2, B3 |
| Osmolality | ~290 mOsm/kg | can match | 1500 to 10500 mOsm/L (calc) | n/a | **Fail** for B2 |
| Temperature | 37 C | pump heat must be rejected | cell heat | high-field heating | Conditional |
| Pressure | soft tissue loop: 2 to 10 kPa budget (assumed) | 689 kPa (C) | NR | sealed | **Fail**: 69x mismatch (calc sec. 4) |
| Sterility | aseptic | contaminated industrial loop | no | no | **Fail** |
| Electrochemical activity | none | none | by design | n/a | **Fail** for B2 |
| Viscosity vs pump power | 0.78 mPa s; tissue loop needs only tens of uW (calc sec. 4) | similar viscosity | NR | higher | Not the limiting factor |
| Contamination | no wear particles or oil | seals, wear debris | metal plating, iodine | permeation "sweating" | **Fail** |

Plain statement: **a redox electrolyte or an actuator working fluid is NOT a biocompatible perfusate.** The only route to a shared fluid is the inverse one, where the actuator runs on sterile, isotonic culture medium at tissue-loop pressures. At those pressures (<= 10 kPa) hydraulic muscles would deliver about 70x less stress than at 100 psi, so that route gives up the actuator's purpose. **Today, sharing fails on biocompatibility, osmolality, pressure, sterility and contamination.**

## Measurable interfaces between the loops
| Interface | What it does | Target / measurement | Basis |
|---|---|---|---|
| Heat exchanger (plate, wall-separated) | moves pump and actuator heat out of Loop A | Loop A outlet 37 +/- 0.5 C; thermistors at both inlets and outlets | culture practice (assumed target) |
| Gas exchanger (hollow-fiber membrane, Loop A only) | O2 in, CO2 out | inline PO2 sensor; keep tissue-outlet PO2 >= ~40 mmHg (0.052 mM) | Place 2017 |
| Pressure isolation | Loop B never pressurizes Loop A | Loop A < 10 kPa (assumed budget) vs Loop B up to 689 kPa (C); burst rating >= 2x Loop B; pressure transducers on both sides | calc sec. 4 |
| Mechanical coupling | force crosses, fluid does not | Cable or tendon through a sealed, sterile bellows or sleeve (Ren 2025 uses cable drive) | Ren 2025 |
| Leak / cross-contamination sensor | detects a breach | conductivity or Zn2+/oil sensor in Loop A; any rise is a hard stop | design choice |
| Wall shear | endothelium or tissue tolerance | tau ~0.2 to 2 Pa in channels (calc sec. 3); target range is an assumption, not sourced | assumed |
| Humidity for exposed skin | limits evaporation | corrected leakage 0.13 to 0.54 g/h per sample (Kawai corr.) sets the makeup-fluid rate to measure | Kawai 2025 corr. |

## Architecture 1 (recommended first build): fully separate dual loop
Loop A is a low-pressure, sterile medium loop, starting with plain oxygenated medium. It perfuses MuMuTA-like strands and the skin. Loop B is a sealed electric or hydraulic actuator pack outside the sterile boundary, coupled only by cable and heat exchanger. The living muscle is assistive or sensory at first. The non-living actuator carries the load.

## Alternative 2: cell-free tissue support plus electric actuator
No living muscle. Actuation is HASEL or electric motors (dry, no circulating fluid). Living tissue is limited to a skin cover fed by a thin medium-perfused dermal channel layer and humidity control. This removes Loop B fluid entirely, so the only fluid is Loop A, and that loop is small.

## Alternative 3: non-living synthetic skin fallback
A silicone or hydrogel skin over Clone-like or HASEL actuators, with no perfusion. It is used if Loop A sterility or lifetime fails. Mechanically it is the most mature, but it gives up "living tissue", so it is the fallback, not the goal.

## The design decision the computation changes
1. **Tissue thickness is capped, so muscle must be built as bundles of thin strands (as MuMuTA does) or be perfused.** With plain medium and a 40 mmHg floor, a slab fed from one side is limited to **240 to 2630 um** across the envelope, and to **621 um** in the mid case (OCR 60 amol/cell/s, 3e7 cells/mL). A cylinder fed from its surface is limited to about **0.8 to 8.8 mm** diameter, with C going to 0. Any solid living muscle thicker than about 0.6 mm in the mid case needs internal channels. That fixes the strand diameter for the first module at <= ~0.6 mm for a sheet fed from one face (roughly double if fed from both faces), or else requires perfusion.
2. **Channel layout:** in the mid case (1.19 mL/min of plain medium for 1 mL of tissue), a single 100 um channel can only be **0.32 mm** long at a 2 kPa budget and carries **158 Pa** wall shear, which is unusable. Ten 200 um channels allow **50 mm** at 2 kPa with **~2 Pa** shear, so a finger-length (~30 mm) module needs roughly >= 10 parallel channels of >= 200 um per mL of tissue. Done that way the tissue loop costs only **~24 uW** of hydraulic power, against **~460 W** (claimed) for a Clone-class actuator system.
3. **Therefore a shared loop buys nothing and costs everything.** Pumping power is not a reason to share: the tissue loop's needs are about 7 orders of magnitude smaller. The 69x pressure gap and the osmolality and toxicity failures make sharing infeasible, so Architecture 1 (separate loops) is chosen, not as a preference but because of these numbers. The computation also says that moving to an Hb-level O2 carrier cuts the required flow 50x. That is the lever to pull before lengthening channels or raising Loop A pressure.
