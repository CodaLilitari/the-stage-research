# H/S source ledger and read depth

Checked 15 October 2026. Primary research, original research code, official experimental-structure records and official documentation are distinguished below. Reading a source is not reproducing its result. This ledger is not a complete systematic review of oxygen carriers, tissue engineering or clinical safety. No paywall bypass, paid service or biological experiment was used.

## HS1. Human HbV first-in-human study

Azuma and colleagues (2022), *First-in-human phase 1 trial of hemoglobin vesicles as artificial red blood cells developed for use as a transfusion alternative*, Blood Advances 6, 5711–5715. DOI: 10.1182/bloodadvances.2022007977.

Primary publisher: https://ashpublications.org/bloodadvances/article-abstract/6/21/5711/486139
PubMed: https://pubmed.ncbi.nlm.nih.gov/35939788/

Read depth: publisher-indexed study material and bibliographic record. Direct publisher and PMC full-text requests were blocked or challenged. The 11-participant summary is additionally stated by the investigators in HS2. No claim of a full independent audit of the adverse-event table. Scope: first-in-human exposure/safety/pharmacokinetics, not efficacy in bleeding patients or replacement of all blood functions.

## HS2. Human HbV phase Ib protocol, not results

Sakai and colleagues (2026), *Haemoglobin vesicles as artificial red blood cells developed for use as a transfusion alternative: an open-label, single-centre phase Ib study protocol in Japan*, BMJ Open 16. DOI: 10.1136/bmjopen-2025-110183.

https://pubmed.ncbi.nlm.nih.gov/41571418/
https://doi.org/10.1136/bmjopen-2025-110183

Read depth: full protocol abstract via primary-indexed PubMed material and a fetched Consensus record. Describes 16 planned healthy volunteers and safety/PK endpoints; refers to the earlier 11-volunteer study. Protocol publication is not trial completion or patient efficacy.

Registry: https://jrct.mhlw.go.jp/en-latest-detail/jRCT2051240249 . Lily's direct request was blocked with HTTP 403. Coda reports Not Recruiting and blank results fields on 15 October 2026. That registry inspection remains Coda-reported; it is not Lily's independent verification.

## HS3. Historical clinical harm signal for earlier cell-free Hb products

Natanson and colleagues (2008), *Cell-Free Hemoglobin-Based Blood Substitutes and Risk of Myocardial Infarction and Death: A Meta-analysis*, JAMA 299, 2304–2312. DOI: 10.1001/jama.299.19.jrv80007.

https://jamanetwork.com/journals/jama/article-abstract/181940

Read depth: original meta-analysis abstract. Across the included earlier products/trials, increased mortality and myocardial-infarction risks were reported. This is the researchers' original evidence synthesis, not a new analysis here. It does not establish identical risks for later encapsulated HbV formulations, nor that any present candidate is safe. It does establish that oxygen carriage alone is an inadequate clinical success criterion.

## HS4. Synthetic microvascular perfusion

Grebenyuk and colleagues (2023), *Large-scale perfused tissues via synthetic 3D soft microfluidics*, Nature Communications. DOI: 10.1038/s41467-022-35619-1.

https://www.nature.com/articles/s41467-022-35619-1
https://pubmed.ncbi.nlm.nih.gov/36635264/

Read depth: primary indexed abstract/record; direct full-text access was limited. Supports synthetic microfluidic perfusion as a demonstrated tissue-engineering approach. No complete methods replication or skin-on-robot performance claim.

## HS5. Coupled network computation

Bonart and colleagues (2026), *Computational design of artificial supply networks for engineered human tissue*, Scientific Reports. DOI: 10.1038/s41598-026-53301-0.

https://www.nature.com/articles/s41598-026-53301-0_reference.pdf

Read depth: accessible 49-page accepted, unedited manuscript, with focused reading of network transport, hydraulic and cellular-consumption equations. Not a claim that every figure or supplemental calculation was independently audited. The supplied source parameterization is not automatically a skin parameterization.

## HS6. Associated original code

https://zenodo.org/records/20305817
DOI: 10.5281/zenodo.20305817

Read depth: repository metadata and web-readable parameters.py, channel_speciesconsumption.py, model.py, LICENSE and README. The source files were inspected but not installed or executed here. LICENSE is MIT; dependencies retain their own terms. Code uses NumPy, UFL, DOLFINx, MPI/PETSc-related tooling, pandas and an optimization dependency. The present PX1 diagnostic does not import or redistribute that implementation.

Important distinctions: the example tissue-density and per-cell consumption parameters describe a high-demand illustrative case, not calibrated robotic skin. The original channel workflow can optimize cross-sectional geometry along the channel, so comparisons with a fixed-geometry PF0 require checking which variables are held constant. Solver convergence status and random perturbation seeds should be made explicit in any local reproduction; a printed solver error is not a successful result.

## HS7. Living skin on a robotic finger

Kawai and colleagues (2022), *Living skin on a robot*, Matter 5, 2190–2208. DOI: 10.1016/j.matt.2022.05.019.

Authors' laboratory: https://www.hybrid.t.u-tokyo.ac.jp/en/research-papers/4ff0a260-b08e-4a48-9e50-994f980d32e8/

Read depth: primary authors' research description. Living skin coverage and collagen-sheet-assisted wound repair are precedents. They are not a demonstrated autonomous vascularized whole-body covering.

## HS8. Living-skin anchoring

Kawai and colleagues (2024), *Perforation-type anchors inspired by skin ligament for robotic face covered with living skin*, Cell Reports Physical Science. DOI: 10.1016/j.xcrp.2024.102066.

https://doi.org/10.1016/j.xcrp.2024.102066

Read depth: title, bibliographic/primary indexed description and authors' publication list. Direct publisher PDF access was blocked. Used only as an anchoring precedent, not as full evidence for long-term tissue support.

## HS9. Internal hydration support on a robotic finger

Ohta, Nie, Oda and Takeuchi (2025), *Skin-Covered Biohybrid Robotic Finger with Bilayered Permeable Subcutaneous Support for Internal Hydration Supplement*, Advanced Intelligent Systems 7, 2400871. DOI: 10.1002/aisy.202400871.

https://advanced.onlinelibrary.wiley.com/doi/10.1002/aisy.202400871

Read depth: full primary article text, particularly results 2.4–2.5 and conclusion. A perforated support and permeable PVA layer supplied fluid beneath tissue. Joint movement after perfusion culture and a short air-exposure hydration comparison are relevant. The authors explicitly note the one-day duration of drying tests and difficulty assessing viability over the large 3D tissue. Hydration/thickness is not synonymous with validated long-term viability.

## HS10. A functional nonliving alternative

Tee, Wang, Allen and Bao (2012), *An electrically and mechanically self-healing composite with pressure- and flexion-sensitive properties for electronic skin applications*, Nature Nanotechnology 7, 825–832. DOI: 10.1038/nnano.2012.192.

https://www.nature.com/articles/nnano.2012.192

Read depth: primary abstract. Demonstrates a material-level combination of repeatable repair and mechanical sensing. It is not a complete robotic skin, a human-contact safety certification, or a recommendation to copy its materials into a body.

## HS11. Experimental human hemoglobin structures

RCSB PDB 2DN1, oxy form: https://www.rcsb.org/structure/2DN1
RCSB PDB 2DN2, deoxy form: https://www.rcsb.org/structure/2DN2
Associated Park and colleagues (2006), Journal of Molecular Biology. DOI: 10.1016/j.jmb.2006.05.036.

Read depth: official experimental-structure records and assembly information. Both entries have biological A2B2 assemblies. Their asymmetric units differ; compare assembled tetramers, not unmatched chain inventories. These are 1.25-angstrom experimental structures, not new predictions. Coordinates were not downloaded or aligned in this package, so no RMSD, interface change or ligand-distance measurement is claimed.

## HS12. Relevant implementation documentation

MuJoCo: https://mujoco.readthedocs.io/en/stable/overview.html ; source license: https://github.com/google-deepmind/mujoco/blob/main/LICENSE . Apache-2.0 core engine.
Gymnasium: https://gymnasium.farama.org/ ; source license: https://github.com/Farama-Foundation/Gymnasium/blob/main/LICENSE . MIT package; separate environment/dependency terms may apply.
DOLFINx: https://github.com/FEniCS/dolfinx ; license file https://github.com/FEniCS/dolfinx/blob/main/COPYING . The dependency stack must be checked separately from the MIT paper code. We have not installed this stack here.

The original First Leaf package has its own fuller simulator and mechanism ledger. No hosted-model, protein-prediction or GPU-compatibility benchmark is reported in this H/S package.
