"""
The Stage - skin oxygen transport parameter ledger.

Emits skin_transport_parameters.csv.

Every row carries units, cell/tissue type, condition, exact location in the
source, evidence status, and whether THIS pass verified it from a primary or
curated route. Rows that must not be combined carry explicit flags.

Evidence status vocabulary (deliberately narrow):
  measured            instrument reading reported as such
  model_derived       obtained by fitting/inverting a transport model on measured data
  recomputed_here     arithmetic performed in this pass from the source's own stated inputs
  as_printed          the number the source prints, reproduced without endorsement
  asserted_no_data    the source asserts it without supporting measurement
  analyst_assumed     chosen by an analyst (ours or a prior one), not from data
  standard_constant   textbook physical constant, not from any of these papers

Verification vocabulary:
  verified_primary    read in this pass from publisher/open full text or abstract
  verified_curated    read in this pass from a curated database that cites the primary
  not_verified_here   access blocked in this cloud pass; carried as collaborator-reported
"""

import csv
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent

# --- source register -------------------------------------------------------

SOURCES = {
    "streeter2011": "Streeter I, Cheema U. Analyst 2011;136(19):4013-9. doi:10.1039/C1AN15249A. PMID 21804989",
    "cheema2012": "Cheema U et al. J Tissue Eng Regen Med 2012;6(1):77-84. doi:10.1002/term.402. PMID 21312340",
    "bnid115121": "BioNumbers BNID 115121 (curated entry titled 'Oxygen consumption rate (Vm) for HDFs')",
    "bnid115120": "BioNumbers BNID 115120 (curated entry, O2 diffusion through collagen scaffolds)",
    "hatcher1993": "Hatcher ME, Plachy WZ. Biochim Biophys Acta 1993;1149(1):73-78. doi:10.1016/0005-2736(93)90026-V. PMID 8391321",
    "stucker2002": "Stucker M et al. J Physiol 2002;538(Pt 3):985-994. doi:10.1113/jphysiol.2001.013067. PMID 11826181. PMC2290093",
    "rhee2024": "Rhee S et al. Bioengineering 2024;11(11):1055. doi:10.3390/bioengineering11111055. PMC11591533",
    "balu2013": "Balu M et al. Biophys J 2013;104(2):258-267. doi:10.1016/j.bpj.2012.11.3809. PMID 23332078",
    "mieremet2019": "Mieremet A et al. Sci Rep 2019;9:7811. doi:10.1038/s41598-019-44204-4. PMC6534609",
    "kawai2022": "Kawai Y et al. Matter 2022;5(7):2190-2208. doi:10.1016/j.matt.2022.05.019",
    "kawai2025corr": "Correction to Kawai et al. Matter 2025. doi:10.1016/j.matt.2025.102162",
    "pf0": "Supplied Stage file 02-pf0.py / 03-report.txt (analyst-selected benchmark, liver-like)",
    "coda_gap": "Supplied Stage file 01-skin_parameter_gap.txt (collaborator Coda, 2026-10-15)",
    "physiol_const": "Standard physiological solubility of O2 in plasma/water at 37 C",
}

# --- ledger ----------------------------------------------------------------

ROWS = [
    # ---------------- cellular oxygen demand ----------------
    dict(
        param_id="Q_HDF_STREETER",
        quantity="oxygen consumption rate per cell, human dermal fibroblast",
        value="1.19e-17", units="mol cell^-1 s^-1",
        value_si="1.19e-17", units_si="mol cell^-1 s^-1",
        cell_or_tissue="human dermal fibroblast (HDF)", species="human",
        condition="3D native type-I collagen scaffold; density varied to create O2 gradients; O2 tension measured at defined positions then rate inverted from a transport model",
        source="streeter2011", location="abstract; value also discussed p.4018 right col. per BNID 115121",
        evidence_status="model_derived", verification="verified_primary",
        combinable_flags="NOT_A_VMAX; no Km reported in the abstract; must not be substituted for a Michaelis-Menten qmax; do not pair with PF0 cell density",
        notes="Companion value in the same abstract: human bone-marrow stromal cells 7.91e-18 mol cell^-1 s^-1. Authors state both rates are LOWER than previously published values.",
    ),
    dict(
        param_id="Q_HBMSC_STREETER",
        quantity="oxygen consumption rate per cell, human bone marrow stromal cell",
        value="7.91e-18", units="mol cell^-1 s^-1",
        value_si="7.91e-18", units_si="mol cell^-1 s^-1",
        cell_or_tissue="human bone marrow derived stromal cell", species="human",
        condition="3D native type-I collagen scaffold, same method as Q_HDF_STREETER",
        source="streeter2011", location="abstract",
        evidence_status="model_derived", verification="verified_primary",
        combinable_flags="not a skin cell; carried only as a same-method comparator",
        notes="Included to show the within-method spread between two primary human cell types (1.5x).",
    ),
    dict(
        param_id="Q_HDF_BNID_CONTAMINATED",
        quantity="values published under a 'HDF Vm' heading in a curated database",
        value="6e-17 and 3e-17", units="mol cell^-1 s^-1",
        value_si="6e-17; 3e-17", units_si="mol cell^-1 s^-1",
        cell_or_tissue="NOT human dermal fibroblast - see notes", species="mouse / human precursor",
        condition="values carried over from two unrelated studies",
        source="bnid115121", location="BNID 115121 value field",
        evidence_status="as_printed", verification="verified_curated",
        combinable_flags="DO_NOT_USE_AS_HDF; provenance defect found in this pass",
        notes="The entry is titled for human dermal fibroblasts and cites Streeter & Cheema 2011, but the two numeric values are attributed to Cho et al. 2007 (3T3 fibroblast/hepatocyte co-culture, mouse line) and von Heimburg et al. 2005 (adipogenic mesenchymal precursor cells). Streeter & Cheema is the paper arguing such earlier values are too high. Pulling 'HDF Vm' from this entry imports a 3-5x overestimate with the wrong cell type.",
    ),
    dict(
        param_id="Q_KERAT_BALU_PRINTED",
        quantity="keratinocyte oxygen consumption rate as printed",
        value="0.035", units="mmol per 1e6 cells per hour",
        value_si="9.72e-15", units_si="mol cell^-1 s^-1",
        cell_or_tissue="keratinocyte, stratum basale", species="human, in vivo",
        condition="volar forearm; 220 mmHg arterial-venous cuff occlusion; SFDI haemodynamics combined with two-photon NADH; n=1 subject, 5 repeats",
        source="balu2013", location="abstract and Results; Eq. 1",
        evidence_status="as_printed", verification="verified_primary",
        combinable_flags="IRREPRODUCIBLE_FROM_OWN_INPUTS; see Q_KERAT_BALU_RECOMPUTED",
        notes="Units in the full text are mmol, not micromol. 9.72e-15 mol/cell/s is ~1000x typical mammalian single-cell respiration, so the printed figure is not usable as stated.",
    ),
    dict(
        param_id="Q_KERAT_BALU_RECOMPUTED",
        quantity="keratinocyte oxygen consumption rate recomputed from the source's own inputs",
        value="0.00036", units="mmol per 1e6 cells per hour",
        value_si="1.0e-16", units_si="mol cell^-1 s^-1",
        cell_or_tissue="keratinocyte, stratum basale", species="human, in vivo",
        condition="0.1 mmol L^-1 s^-1 volumetric rate distributed over the stated 200 pL imaged volume containing ~200 cells",
        source="balu2013", location="recomputed in this pass from Eq. 1 output and the stated imaged volume/cell count",
        evidence_status="recomputed_here", verification="verified_primary",
        combinable_flags="differs from the printed value by a factor of ~97; the source does not show the per-cell conversion",
        notes="Arithmetic: 1e-4 mol L^-1 s^-1 x 2e-10 L = 2e-14 mol s^-1 over ~200 cells = 1.0e-16 mol cell^-1 s^-1. Coincidentally equal to PF0's assumed liver-like per-cell rate.",
    ),
    dict(
        param_id="QV_CUTANEOUS_BALU",
        quantity="bulk volumetric oxygen consumption rate of perfused forearm skin",
        value="0.1", units="mmol L^-1 s^-1",
        value_si="0.1", units_si="mol m^-3 s^-1",
        cell_or_tissue="forearm skin + underlying tissue within the SFDI interrogation depth (~2-3 mm)", species="human, in vivo",
        condition="onset of 220 mmHg cuff occlusion; = 4 x measured oxyhaemoglobin decline of 0.025 mmol L^-1 s^-1",
        source="balu2013", location="Eq. 1 and the stated ctO2Hb decline rate",
        evidence_status="model_derived", verification="verified_primary",
        combinable_flags="interrogation volume (mm scale) is ~4 orders larger than the two-photon imaged volume; attributing this rate to the imaged 200 pL is the weak step in the per-cell conversion",
        notes="This is the most defensible quantity recoverable from Balu because it needs no per-cell attribution. It is ~33x higher than textbook resting skin consumption (~0.003 mol m^-3 s^-1), consistent with an occlusion-onset transient rather than a steady basal rate.",
    ),
    dict(
        param_id="N_EPIDERMAL_BALU",
        quantity="epidermal cell number density implied by the source's stated imaging volume",
        value="1e15", units="cells m^-3",
        value_si="1e15", units_si="cells m^-3",
        cell_or_tissue="viable epidermis", species="human, in vivo",
        condition="~200 cells in a ~200 pL imaged volume",
        source="balu2013", location="recomputed in this pass from the stated imaged volume and cell count",
        evidence_status="recomputed_here", verification="verified_primary",
        combinable_flags="an imaging-ROI density, not a validated histological cell density",
        notes="5x higher than PF0's assumed 2e14 cells/m^3. Use only with Q_KERAT_BALU_RECOMPUTED, since the two come from the same stated inputs.",
    ),

    # ---------------- matrix transport ----------------
    dict(
        param_id="D_COLLAGEN_11PCT",
        quantity="oxygen diffusion coefficient, 11% density collagen scaffold",
        value="4.5e-6", units="cm^2 s^-1",
        value_si="4.5e-10", units_si="m^2 s^-1",
        cell_or_tissue="acellular dense type-I collagen scaffold", species="not applicable",
        condition="plastic-compressed dense collagen; core O2 monitored by optical fibre; coefficient obtained by Fick's law fit",
        source="cheema2012", location="abstract; cross-checked against BNID 115120 (listed as 450 um^2 s^-1)",
        evidence_status="model_derived", verification="verified_primary+curated",
        combinable_flags="DENSE_COMPRESSED_COLLAGEN_ONLY; must not be applied to a dilute collagen gel such as Rhee's 3 mg/mL; collagen 'density %' definition not verified against mg/mL",
        notes="4.5e-6 cm^2/s and 450 um^2/s agree exactly on conversion, so the SI value 4.5e-10 m^2/s is sound.",
    ),
    dict(
        param_id="D_COLLAGEN_34PCT",
        quantity="oxygen diffusion coefficient, 34% density collagen scaffold",
        value="1.7e-6", units="cm^2 s^-1",
        value_si="1.7e-10", units_si="m^2 s^-1",
        cell_or_tissue="acellular dense type-I collagen scaffold", species="not applicable",
        condition="as D_COLLAGEN_11PCT, higher compression",
        source="cheema2012", location="abstract; BNID 115120 lists 170 um^2 s^-1",
        evidence_status="model_derived", verification="verified_primary+curated",
        combinable_flags="DENSE_COMPRESSED_COLLAGEN_ONLY",
        notes="2.6x spread across the two densities sets the matrix-transport uncertainty band for compressed constructs.",
    ),
    dict(
        param_id="D_COLLAGEN_11PCT_XL",
        quantity="oxygen diffusion coefficient, photochemically crosslinked 11% collagen",
        value="3.4e-6", units="cm^2 s^-1",
        value_si="3.4e-10", units_si="m^2 s^-1",
        cell_or_tissue="acellular crosslinked dense collagen", species="not applicable",
        condition="as above with photochemical crosslinking",
        source="cheema2012", location="abstract; present in the source but omitted from the BNID 115120 value field",
        evidence_status="model_derived", verification="verified_primary",
        combinable_flags="DENSE_COMPRESSED_COLLAGEN_ONLY",
        notes="Crosslinking lowers D by ~25% at matched density.",
    ),
    dict(
        param_id="D_WATER_37C",
        quantity="oxygen diffusion coefficient in water / dilute hydrogel",
        value="2.0e-9 to 3.0e-9", units="m^2 s^-1",
        value_si="2.0e-9", units_si="m^2 s^-1",
        cell_or_tissue="dilute aqueous gel (upper bound for a 3 mg/mL collagen gel)", species="not applicable",
        condition="37 C",
        source="physiol_const", location="standard constant, not from the packet sources",
        evidence_status="standard_constant", verification="not_verified_here",
        combinable_flags="use as an UPPER bound for a dilute construct; the true value for a 3 mg/mL cellularised gel lies between this and D_COLLAGEN_11PCT and was not measured in any packet source",
        notes="PF0 uses 2e-9 m^2/s. For a dilute gel that is defensible as an upper bound; for compressed collagen it is 4-12x too high.",
    ),
    dict(
        param_id="D_STRATUM_CORNEUM",
        quantity="oxygen diffusion coefficient, human stratum corneum",
        value="3e-7", units="cm^2 s^-1",
        value_si="3e-11", units_si="m^2 s^-1",
        cell_or_tissue="human stratum corneum (dead keratinised barrier)", species="human",
        condition="37 C; EPR time-dependent oxygen line broadening; approximate activation energy 44 kJ/mol",
        source="hatcher1993", location="abstract, per collaborator read",
        evidence_status="model_derived", verification="not_verified_here",
        combinable_flags="BARRIER_LAYER_ONLY - must never be assigned to living dermis; diffusivity alone is NOT permeability without an oxygen solubility/partition coefficient for the same material, which no packet source supplies",
        notes="Access blocked in this cloud pass (publisher and NCBI routes). Carried as collaborator-reported from file 01. ~67x lower than the dilute-gel value and ~15x lower than dense collagen.",
    ),
    dict(
        param_id="ALPHA_O2_PLASMA_37C",
        quantity="oxygen solubility in plasma/water",
        value="1.34e-3", units="mol m^-3 mmHg^-1",
        value_si="1.34e-3", units_si="mol m^-3 mmHg^-1",
        cell_or_tissue="aqueous phase", species="not applicable",
        condition="37 C; equivalent to 0.003 mL O2 dL^-1 mmHg^-1",
        source="physiol_const", location="standard constant",
        evidence_status="standard_constant", verification="not_verified_here",
        combinable_flags="NOT valid for stratum corneum, which is lipid-rich and has a different partition coefficient that no packet source measures",
        notes="Needed to convert any pO2 boundary condition into the mol/m^3 units PF0 and this model use. At 150 mmHg this gives 0.20 mol/m^3 - which is where PF0's 0.2 inlet effectively comes from.",
    ),

    # ---------------- construct geometry (Rhee) ----------------
    dict(
        param_id="RHEE_CHANNEL_INNER_EDGE",
        quantity="perfusable channel inner edge dimension",
        value="500", units="um",
        value_si="5.0e-4", units_si="m",
        cell_or_tissue="printed channel in full-thickness skin equivalent", species="not applicable",
        condition="skin-on-a-chip, printed channel",
        source="rhee2024", location="Methods, channel fabrication",
        evidence_status="measured", verification="verified_primary",
        combinable_flags="",
        notes="",
    ),
    dict(
        param_id="RHEE_WALL_THICKNESS",
        quantity="channel wall thickness",
        value="50", units="um",
        value_si="5.0e-5", units_si="m",
        cell_or_tissue="printed channel wall", species="not applicable",
        condition="skin-on-a-chip",
        source="rhee2024", location="Methods, channel fabrication",
        evidence_status="measured", verification="verified_primary",
        combinable_flags="a physical wall thickness, NOT a mass-transfer coefficient; converting it to PF0's wall permeability needs an O2 diffusivity and partition coefficient for the wall material, which the source does not report",
        notes="Not present in the collaborator's file 01. PF0 lumps the wall into a single permeability with no thickness; this is the geometric datum that would let that lump be grounded.",
    ),
    dict(
        param_id="RHEE_CHANNEL_SPACING",
        quantity="spacing between adjacent channels",
        value="400", units="um",
        value_si="4.0e-4", units_si="m",
        cell_or_tissue="skin equivalent between channels", species="not applicable",
        condition="skin-on-a-chip",
        source="rhee2024", location="Methods / Figure 2",
        evidence_status="measured", verification="verified_primary",
        combinable_flags="",
        notes="Half-spacing (200 um) is the diffusion half-path the dermis must be supplied across. This is the single most important geometric number for the oxygen question.",
    ),
    dict(
        param_id="RHEE_SURFACE_PORE_WIDTH",
        quantity="surface open-pore line width",
        value="7", units="um",
        value_si="7.0e-6", units_si="m",
        cell_or_tissue="chip surface structure", species="not applicable",
        condition="skin-on-a-chip",
        source="rhee2024", location="Methods, channel fabrication",
        evidence_status="measured", verification="verified_primary",
        combinable_flags="",
        notes="Not present in the collaborator's file 01.",
    ),
    dict(
        param_id="RHEE_FLOW_IN",
        quantity="perfusion inlet flow rate",
        value="10", units="uL min^-1",
        value_si="1.667e-10", units_si="m^3 s^-1",
        cell_or_tissue="not applicable", species="not applicable",
        condition="keratinocyte medium + 1.64 mM CaCl2, from day 4",
        source="rhee2024", location="Section 2.6 and Section 2.3",
        evidence_status="measured", verification="verified_primary",
        combinable_flags="an operating point chosen by the authors, NOT a measured minimum oxygen-sufficient flow",
        notes="",
    ),
    dict(
        param_id="RHEE_FLOW_OUT",
        quantity="perfusion outlet flow rate",
        value="12", units="uL min^-1",
        value_si="2.0e-10", units_si="m^3 s^-1",
        cell_or_tissue="not applicable", species="not applicable",
        condition="set deliberately faster than inlet to prevent leakage",
        source="rhee2024", location="Section 2.3 / Figure 2",
        evidence_status="measured", verification="verified_primary",
        combinable_flags="implies a net transmural/ambient flow term; PF0 has no interstitial or transmural flow and cannot represent this",
        notes="Not present in the collaborator's file 01. Outlet exceeding inlet by 20% means the lumen is not a closed conduit; some fluid is drawn through or around the construct. Any oxygen budget that assumes Q_in = Q_out is wrong for this geometry.",
    ),
    dict(
        param_id="RHEE_COLLAGEN_CONC",
        quantity="dermal matrix collagen concentration",
        value="3", units="mg mL^-1",
        value_si="3.0", units_si="kg m^-3",
        cell_or_tissue="rat tail collagen I dermal matrix", species="rat (matrix), human (cells)",
        condition="90 uL collagen + 10 uL neutralisation + 100 uL fibroblast suspension; 150 uL seeded; crosslinked 37 C 30 min",
        source="rhee2024", location="Section 2.6",
        evidence_status="measured", verification="verified_primary",
        combinable_flags="DILUTE GEL - this is why Cheema's compressed-collagen D values must not be transplanted here",
        notes="Not present in the collaborator's file 01. A 3 mg/mL gel is ~0.3% solids by mass, far from Cheema's 11% and 34% constructs.",
    ),
    dict(
        param_id="RHEE_FIBROBLAST_COUNT",
        quantity="fibroblast number stated for the dermal suspension",
        value="4e6", units="cells",
        value_si="4e6", units_si="cells",
        cell_or_tissue="neonatal human dermal fibroblast (HDFn)", species="human",
        condition="in a 100 uL suspension forming part of a 200 uL dermal solution",
        source="rhee2024", location="Section 2.6",
        evidence_status="as_printed", verification="verified_primary",
        combinable_flags="ARITHMETICALLY_INCONSISTENT_WITH_RHEE_FIBROBLAST_CONC - do not use either as a model input without clarification from the authors",
        notes="4e6 cells in 100 uL is 4e7 cells/mL; spread over the full 200 uL it is 2e7 cells/mL. Neither equals the stated 2e6 cells/mL.",
    ),
    dict(
        param_id="RHEE_FIBROBLAST_CONC",
        quantity="final fibroblast concentration as stated",
        value="2e6", units="cells mL^-1",
        value_si="2e12", units_si="cells m^-3",
        cell_or_tissue="neonatal human dermal fibroblast (HDFn)", species="human",
        condition="stated final dermal concentration",
        source="rhee2024", location="Section 2.6",
        evidence_status="as_printed", verification="verified_primary",
        combinable_flags="ARITHMETICALLY_INCONSISTENT_WITH_RHEE_FIBROBLAST_COUNT",
        notes="Confirmed independently in this pass, as the collaborator asked. The discrepancy is 10x (against the 200 uL reading) to 20x (against the 100 uL reading). The stated concentration would correspond to 4e5 cells, not 4e6. This single ambiguity spans the oxygen pass/fail boundary in the PF1-S sweep.",
    ),
    dict(
        param_id="RHEE_KERATINOCYTE_COUNT",
        quantity="keratinocyte number seeded for the epidermis",
        value="10e6", units="cells",
        value_si="1e7", units_si="cells",
        cell_or_tissue="neonatal human epidermal keratinocyte (HEKn)", species="human",
        condition="100 uL suspension pipetted onto the dermis, 4 h attachment",
        source="rhee2024", location="Section 2.6",
        evidence_status="as_printed", verification="verified_primary",
        combinable_flags="a SEEDING number, not a viable cell density at any later timepoint; no stated concentration to cross-check against",
        notes="~1e8 cells/mL in suspension. Final viable epidermal density after stratification is not reported.",
    ),
    dict(
        param_id="RHEE_O2_EVIDENCE",
        quantity="oxygen measurement in the perfused construct",
        value="none", units="not applicable",
        value_si="", units_si="",
        cell_or_tissue="full-thickness perfused skin equivalent", species="human cells",
        condition="whole study",
        source="rhee2024", location="Discussion",
        evidence_status="asserted_no_data", verification="verified_primary",
        combinable_flags="the claim that perfusion 'ensures adequate nutrient and oxygen supply' carries no oxygen measurement anywhere in the paper",
        notes="Confirmed in this pass. This is the gap PF1-S is built to size: the only openly published, fully dimensioned perfused human skin construct in the packet never measured oxygen.",
    ),
    dict(
        param_id="RHEE_REPLICATES",
        quantity="replicate structure",
        value="3", units="technical replicates (n=4 in Fig. 6)",
        value_si="", units_si="",
        cell_or_tissue="not applicable", species="not applicable",
        condition="'all experiments performed in triplicate unless otherwise stated'",
        source="rhee2024", location="Methods; Figs. 3c, 6, 7",
        evidence_status="as_printed", verification="verified_primary",
        combinable_flags="donor independence NOT established; commercial neonatal primary cells, donor numbers not given",
        notes="Data available from corresponding author on request; no public repository. Confirms the collaborator's read.",
    ),

    # ---------------- boundary conditions ----------------
    dict(
        param_id="FLUX_SKIN_EXTERNAL",
        quantity="external (atmospheric) oxygen uptake through skin surface",
        value="0.53 +/- 0.27", units="mL O2 min^-1 m^-2",
        value_si="3.94e-7", units_si="mol m^-2 s^-1",
        cell_or_tissue="human volar forearm skin", species="human, in vivo",
        condition="33 C, humidified, surface pO2 163 +/- 9 Torr, superficial horny scales removed; 20 volunteers (10 under 30, 10 over 70)",
        source="stucker2002", location="Table 1 and Results, per collaborator read of the open full text",
        evidence_status="measured", verification="not_verified_here",
        combinable_flags="NOT an untouched, dry, covered or submerged boundary - scale removal lowers barrier resistance; molar conversion assumes 22.414 L/mol reference gas conditions, which were not verified",
        notes="Access blocked in this cloud pass (NCBI CAPTCHA, Wiley and publisher routes failed). Carried as collaborator-reported. SI conversion performed here: 0.53e-6 m^3 min^-1 m^-2 / 0.022414 m^3 mol^-1 / 60 s = 3.94e-7 mol m^-2 s^-1.",
    ),
    dict(
        param_id="DEPTH_ATMOSPHERIC_SUPPLY",
        quantity="depth of skin supplied by atmospheric oxygen",
        value="0.25 to 0.40", units="mm",
        value_si="2.5e-4 to 4.0e-4", units_si="m",
        cell_or_tissue="human skin", species="human, in vivo",
        condition="derived by the authors from their flux plus other transport data",
        source="stucker2002", location="Results/Discussion, per collaborator read",
        evidence_status="model_derived", verification="not_verified_here",
        combinable_flags="NOT a universal viability thickness; model-derived, with transport constants this pass could not inspect",
        notes="Implied average volumetric demand over that depth = 3.94e-7 / 3.25e-4 = 1.21e-3 mol m^-3 s^-1, i.e. ~80x below the Balu occlusion-onset bulk rate. The two cannot both describe the same tissue in the same state.",
    ),
    dict(
        param_id="OCCLUSION_FLUX_RISE",
        quantity="increase in external oxygen flux on blood flow interruption",
        value="9.5 +/- 6.3", units="%",
        value_si="", units_si="",
        cell_or_tissue="human volar forearm skin", species="human, in vivo",
        condition="5 minute blood-flow interruption",
        source="stucker2002", location="Results, per collaborator read",
        evidence_status="measured", verification="not_verified_here",
        combinable_flags="",
        notes="A ~10% rise means the atmospheric path is a minority but non-trivial supply route when perfusion stops. Useful as a functional check on a module's surface boundary term.",
    ),
    dict(
        param_id="FUNCTIONAL_O2_3PCT_VS_20PCT",
        quantity="functional response of skin equivalents to external oxygen level",
        value="3% vs 20%", units="% O2, external atmosphere",
        value_si="", units_si="",
        cell_or_tissue="human fibroblast/keratinocyte full-thickness skin equivalent", species="human",
        condition="5 primary-cell donors, healthy surplus breast skin; 14-15 days at air-liquid interface",
        source="mieremet2019", location="Methods/Results, per collaborator read",
        evidence_status="measured", verification="not_verified_here",
        combinable_flags="NOT a concentration, a demand curve, a safe lower bound, or an endurance test",
        notes="Lower external oxygen changed proliferation, differentiation and barrier lipids, with several features CLOSER to native skin. Direct evidence against a 'more oxygen is better' design objective, and against any monotone oxygen pass criterion.",
    ),
    dict(
        param_id="LEAKAGE_KAWAI_CORRECTED",
        quantity="water leakage after 1 h, dermis equivalent vs skin equivalent",
        value="0.54 g vs 0.13 g (reported); originals stated as 5.4 mg and 0.13 mg", units="g per hour per sample",
        value_si="", units_si="",
        cell_or_tissue="dermis equivalent and skin equivalent on a robotic finger", species="human cells",
        condition="1 hour; corrected values per the 2025 correction",
        source="kawai2025corr", location="correction notice",
        evidence_status="as_printed", verification="not_verified_here",
        combinable_flags="UNVERIFIED AND INTERNALLY ODD - see notes; do not adopt as a barrier target until the correction text is read directly",
        notes="Access to the correction was blocked on every route available in this pass (publisher robots policy, Cell Press error, search did not surface the text). Structural flag raised here: a pure mg->g unit correction would scale BOTH values by 1000, but the reported pair scales the dermis value by 100 (5.4 mg -> 0.54 g) and the skin value by 1000 (0.13 mg -> 0.13 g). That changes the dermis:skin leakage ratio from 41.5x to 4.15x - a 10x change in exactly the quantity used to judge whether adding an epidermis improves barrier function. Resolve before any barrier criterion is set.",
    ),

    # ---------------- PF0 benchmark, for contrast only ----------------
    dict(
        param_id="PF0_QMAX",
        quantity="maximum volumetric oxygen consumption used in PF0",
        value="0.02", units="mol m^-3 s^-1",
        value_si="0.02", units_si="mol m^-3 s^-1",
        cell_or_tissue="illustrative liver-like high-demand case", species="not applicable",
        condition="= 2e14 cells/m^3 x 1e-16 mol/cell/s",
        source="pf0", location="02-pf0.py CONFIG.source_parameters",
        evidence_status="analyst_assumed", verification="verified_primary",
        combinable_flags="NOT measured skin physiology; the packet's own provenance string says so",
        notes="Sits between the textbook resting-skin bulk rate (~0.003) and the Balu occlusion-onset bulk rate (0.1). So PF0 is not uniformly conservative for skin: it is ~7x high for resting dermis and ~5x LOW against the only in vivo human epidermal figure recoverable here.",
    ),
    dict(
        param_id="PF0_KM",
        quantity="Michaelis constant used in PF0",
        value="0.028", units="mol m^-3",
        value_si="0.028", units_si="mol m^-3",
        cell_or_tissue="illustrative liver-like case", species="not applicable",
        condition="Michaelis-Menten kinetics",
        source="pf0", location="02-pf0.py CONFIG.source_parameters",
        evidence_status="analyst_assumed", verification="verified_primary",
        combinable_flags="NO packet source supplies a Km for dermal fibroblasts or keratinocytes; Streeter & Cheema report a rate, not a Km",
        notes="Km is the parameter with the weakest evidential support anywhere in this ledger, and it sits right next to the 0.05 threshold, where the kinetics are most nonlinear. It is also the parameter PF0's threshold result is structurally most sensitive to.",
    ),
    dict(
        param_id="PF0_THRESHOLD",
        quantity="oxygen threshold used to classify PF0 cases",
        value="0.05", units="mol m^-3",
        value_si="0.05", units_si="mol m^-3",
        cell_or_tissue="not applicable", species="not applicable",
        condition="assumed pass line",
        source="pf0", location="02-pf0.py CONFIG.source_parameters",
        evidence_status="analyst_assumed", verification="verified_primary",
        combinable_flags="classifies a model field; certifies nothing about survival or function",
        notes="Equivalent to ~37 mmHg at ALPHA_O2_PLASMA_37C. No packet source establishes 37 mmHg as a skin viability or function threshold, and Mieremet 2019 is direct evidence that function is not monotone in oxygen.",
    ),
]

FIELDS = [
    "param_id", "quantity", "value", "units", "value_si", "units_si",
    "cell_or_tissue", "species", "condition", "source_key", "source_citation",
    "location", "evidence_status", "verification", "combinable_flags", "notes",
]


def main():
    out_csv = OUT / "skin_transport_parameters.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in ROWS:
            row = dict(r)
            row["source_key"] = row.pop("source")
            row["source_citation"] = SOURCES[row["source_key"]]
            w.writerow(row)

    digest = hashlib.sha256(out_csv.read_bytes()).hexdigest()
    meta = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "rows": len(ROWS),
        "csv_sha256": digest,
        "python_version": platform.python_version(),
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "verification_counts": {
            k: sum(1 for r in ROWS if r["verification"] == k)
            for k in sorted({r["verification"] for r in ROWS})
        },
        "evidence_status_counts": {
            k: sum(1 for r in ROWS if r["evidence_status"] == k)
            for k in sorted({r["evidence_status"] for r in ROWS})
        },
        "rows_with_combination_flags": sum(1 for r in ROWS if r["combinable_flags"]),
    }
    (OUT / "parameter_table_meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(meta, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
