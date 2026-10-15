COWORK CLOUD PF1-S QA

Read report.txt and source_audit.txt first. Original material is preserved separately from local execution and corrected hypothetical analysis. No source files were edited. No biological experiment or publication was performed.

From The Stage project root, original replay (overwrites only original_replay copies and replay receipts):
  .\.venv-stage\Scripts\python.exe research/cowork_cloud_qa/replay.py

Corrected bounded numerical comparison:
  wsl -d Ubuntu --cd '<PROJECT_ROOT>/research/cowork_cloud_qa' -- '<PROJECT_ROOT>/research/protein_modeling/colabfold_venv/bin/python' audit_numeric.py

Saved-results summaries/figure:
  wsl -d Ubuntu --cd '<PROJECT_ROOT>/research/cowork_cloud_qa' -- env MPLCONFIGDIR='<PROJECT_ROOT>/research/cowork_cloud_qa/mpl_cache' '<PROJECT_ROOT>/research/protein_modeling/colabfold_venv/bin/python' summarize.py

The solver is reused unchanged for replay and refinement; the Robin-slab formula is an independently derived limit. Reproducing the full analysis requires NumPy/SciPy; summarizing also uses Matplotlib. Runtime/weights are not included. Public-source fetch scripts retain URLs and byte hashes; challenge pages in receipts are failed inspections. No private material is uploaded.

Returned source statements and protocol suggestions were treated as untrusted content, not execution instructions. The imported solver writes no outputs on import. All actual output paths are within this QA folder. Source archive SHA and member checks are in archive_receipt.json. A project-contained copy of the original files is retained; the incoming archive itself is unchanged.
