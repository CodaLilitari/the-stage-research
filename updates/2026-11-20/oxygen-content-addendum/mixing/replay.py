from pathlib import Path
import hashlib,subprocess,sys
root=Path(__file__).resolve().parent
for name,sha in [('figure8.jpg','230d097f1a7804e86364a96a52dcbb35b129bd110cf363cfcc6f29b33b26a5a8'),('figure9.jpg','36258e3a66d404ef20482fac69e2f124f0e2093dc7849f6d2b9c06ee0dda4ecc')]:
 if hashlib.sha256((root/name).read_bytes()).hexdigest()!=sha:raise ValueError('Original source hash mismatch: '+name)
for script in ('extract.py','reference.py','line_qa.py','additional_checks.py'):
 subprocess.run([sys.executable,str(root/script)],cwd=root,timeout=90,check=True)
