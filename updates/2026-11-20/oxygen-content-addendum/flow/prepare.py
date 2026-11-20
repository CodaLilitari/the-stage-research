"""Check the source, recover the native oxygen figure and prepare the stagnant profile."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import numpy as np
from PIL import Image
from scipy.optimize import minimize_scalar

ROOT = Path(__file__).resolve().parent
CAPS = [(84,99),(92,109),(97,117),(102,123),(105,128),(110,133),(113,138),
        (118,143),(123,146),(128,151),(133,154),(136,157),(141,160),(144,164),
        (149,167),(154,168),(157,170),(162,172),(165,175)]
PDF = '9ca10ae9db1204ad44e53ee91b54b5ef7aabb57b7f8c204827f0fe9456ba5e4f'


def verify(source):
    if hashlib.sha256(source.read_bytes()).hexdigest()!=PDF:
        raise ValueError('Source version differs from conference paper')
    with tempfile.TemporaryDirectory() as temp:
        out = Path(temp)/'oxygen'
        flags = ['-f','3','-l','3','-png']
        if shutil.which('pdfimages'):
            command = ['pdfimages',*flags,str(source),str(out)]
        elif os.name=='nt' and shutil.which('wsl.exe'):
            paths = [subprocess.check_output(['wsl.exe','-e','wslpath','-a',p.as_posix()],
                                             text=True).strip() for p in [source,out]]
            command = ['wsl.exe','-e','pdfimages',*flags,*paths]
        else:
            raise SystemExit('Install Poppler locally or in the default WSL distribution')
        subprocess.run(command,check=True)
        with Image.open(out.with_name('oxygen-000.png')) as image:
            if image.size!=(540,590):
                raise ValueError('Figure has unexpected dimensions')
            upper = np.asarray(image.crop((0,0,540,235)).convert('L'))
        # Confirm ink on the digitized upper and lower caps in a narrow
        # neighborhood. Some caps overlap a marker, axis, or the published line.
        for i,(top,bottom) in enumerate(CAPS):
            x = round(154+i*13.95)
            for y in (top,bottom):
                local = upper[y-1:y+2,x-4:x+5]
                if (local<100).sum(axis=1).max()<3:
                    raise ValueError(f'Cannot confirm cap at {(x,y)}')


def prepare():
    axis = np.polyfit([54,80,106,130,156,182],[250,200,150,100,50,0],1)
    x = np.arange(19)*100
    y = np.polyval(axis,[.5*(u+v+1) for u,v in CAPS])
    se = [abs(axis[0])*(v-u)/2 for u,v in CAPS]
    tol = abs(axis[0])*1.5
    out = ROOT/'input'
    out.mkdir(exist_ok=True)
    with (out/'train.csv').open('w',newline='') as f:
        w = csv.writer(f)
        w.writerow(['depth_um','oxygen_umol_per_l','se_umol_per_l','chart_tolerance_umol_per_l'])
        w.writerows(zip(x,y,se,[tol]*len(y)))
    def error(k):
        if k==0:
            pred = np.interp(x,[x[0],x[-1]],[y[0],y[-1]])
        else:
            pred = (y[0]*np.sinh(k*(x[-1]-x))+y[-1]*np.sinh(k*x))/np.sinh(k*x[-1])
        return float(np.mean((pred-y)**2)**.5)
    fit = minimize_scalar(error,bounds=(0,.002),method='bounded',options={'xatol':1e-14})
    return {'left_and_right_umol_per_l':y[[0,-1]].tolist(),'chart_halfwidth_umol_per_l':tol,
            'k_per_um':float(fit.x),'first_order_RMSE_umol_per_l':float(fit.fun),
            'chord_RMSE_umol_per_l':error(0)}


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_pdf',type=Path)
    args = parser.parse_args()
    verify(args.source_pdf.resolve())
    print(json.dumps(prepare(),indent=2))
