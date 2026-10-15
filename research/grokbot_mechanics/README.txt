MECH1 — LOCAL GROK BOT AUDIT

Read report.txt and source_audit.txt first. returned/ contains unmodified supplied material and cloud output; screen_results.json contains Coda's new conditional model results. The two analyses have separate authority and limits.

The safe extraction and code/config freeze have already been executed. Preserve these frozen files. For reproduction without changing the delivered evidence, copy this folder to another local destination and use the matching environment. All numerical computations require only Python standard library. Plotting uses existing project matplotlib; no install is needed.

From <PROJECT_ROOT>:
& '.venv-stage\Scripts\python.exe' 'research\grokbot_mechanics\replay_original.py'
& '.venv-stage\Scripts\python.exe' 'research\grokbot_mechanics\coupled_screen.py'

Already-executed freeze command (refuses an existing freeze):
& '.venv-stage\Scripts\python.exe' 'research\grokbot_mechanics\coupled_screen.py' --freeze

Figure command:
wsl -d Ubuntu --cd '<PROJECT_ROOT>/research/grokbot_mechanics' -- env MPLCONFIGDIR='<PROJECT_ROOT>/research/grokbot_mechanics/mpl_cache' '<PROJECT_ROOT>/research/protein_modeling/colabfold_venv/bin/python' plot_screen.py

Original archive members are hashed in archive_receipt.json. Original replay receipt records command, return code, output hashes and newline-normalized comparison. freeze.json binds the new model code/config and original code. manifest.json hashes deliverable files excluding caches and itself.

Attribution: Grok Bot authored the returned package; Coda authored source checking, this coupled model and corrections with Richard Pemberton. Neither local execution nor collaborator assent clears third-party copyrights or authorizes publication. The returned architecture contains unvalidated tissue-support operating proposals. They are retained as historical source material, not adopted or authorized experimental instructions; Coda's corrections in report.txt govern the current interpretation.
