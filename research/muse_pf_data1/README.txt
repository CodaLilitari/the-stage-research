PF-DATA1 AUDIT REPRODUCTION

Read report.txt first. Original outputs are not corrected results. No local package changes are needed on this machine.

Working directory:
<PROJECT_ROOT>

Exact primary-table verification (Windows):
& '.venv-stage\Scripts\python.exe' 'research\muse_pf_data1\verify_primary.py'

The local freeze was already created before execution:
& '.venv-stage\Scripts\python.exe' 'research\muse_pf_data1\run_replays.py' --freeze
Do not recreate/overwrite it. For an archival rerun, first copy the folder to a new destination and adapt runtime paths if needed. The run commands below overwrite derived outputs; preserve this completed evidence set.

Original script and corrected analysis replay (records argv/exit codes):
& '.venv-stage\Scripts\python.exe' 'research\muse_pf_data1\run_replays.py' --run

PF0 sensitivity, stdlib only:
& '.venv-stage\Scripts\python.exe' 'research\muse_pf_data1\corrected\pf0_sensitivity.py'

WSL post-run plot/arithmetic and test-method diagnostics:
wsl -d Ubuntu --cd '<PROJECT_ROOT>/research/muse_pf_data1' -- env MPLCONFIGDIR='<PROJECT_ROOT>/research/muse_pf_data1/mpl_cache' '<PROJECT_ROOT>/research/protein_modeling/colabfold_venv/bin/python' finish_audit.py
wsl -d Ubuntu --cd '<PROJECT_ROOT>/research/muse_pf_data1' -- env MPLCONFIGDIR='<PROJECT_ROOT>/research/muse_pf_data1/mpl_cache' '<PROJECT_ROOT>/research/protein_modeling/colabfold_venv/bin/python' wilcoxon_diagnostic.py

Analysis runtime: existing isolated project ColabFold environment was used as a read-only Python/scientific-library provider. No model, network or folding function was used. Matplotlib cache is confined to this audit folder. Relevant versions are recorded in wilcoxon_diagnostic.json. The original script uses SciPy's default Wilcoxon method, whose numerical result differed from the returned JSON; the explicit diagnostic explains and preserves that discrepancy.

Authorship: Nua supplied the original CSV, code and returned analysis. Coda independently checked the source, replayed it, authored corrections and executed the conditional PF0 sensitivity for Richard Pemberton. Numeric transcription derives from Stuecker et al. 2002; the historical demand range is cited through that paper. Reuse/publication rights are separate from local access and this audit.
