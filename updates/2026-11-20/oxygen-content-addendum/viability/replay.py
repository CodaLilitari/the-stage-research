"""Reproduce the Stage viability interpolation on two original conference figures.

Usage: python replay.py /path/to/306e.pdf
Requires Poppler pdfimages on PATH, NumPy, SciPy and Pillow.
"""
import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import numpy as np
from PIL import Image
from scipy.optimize import linprog


PDF_SHA = '9ca10ae9db1204ad44e53ee91b54b5ef7aabb57b7f8c204827f0fe9456ba5e4f'
DEPTH_EDGES = np.array([0, 255, 511, 766, 1021, 1277, 1532, 1787])
TRAIN = [0, 1, 4, 6]
HOLD = [2, 3, 5]
# Coordinates bracket the published SE caps on the stagnant mean (Figure 4A).
CAPS = [(84,99),(92,109),(97,117),(102,123),(105,128),(110,133),(113,138),
        (118,143),(123,146),(128,151),(133,154),(136,157),(141,160),(144,164),
        (149,167),(154,168),(157,170),(162,172),(165,175)]
PAID = {
    'independent_affine_oxygen': [40.46407710388905,29.40588907191661,11.053297023223447],
    'regularized_oxygen_and_density': [43.878532707715046,32.029667195288624,11.202990912079354],
    'minimum_slope_midpoint': [43.037790856365376,29.59212985229527,10.99723865528215],
}


def source_readings(pdf, temp):
    binary = shutil.which('pdfimages')
    for page, name in [(3,'oxygen'), (6,'viability')]:
        flags = ['-f',str(page),'-l',str(page),'-png']
        if binary:
            command = [binary,*flags,str(pdf),str(temp/name)]
        elif os.name=='nt' and shutil.which('wsl.exe'):
            paths = [subprocess.check_output(['wsl.exe','-e','wslpath','-a',p.as_posix()],
                                             text=True).strip() for p in [pdf,temp/name]]
            command = ['wsl.exe','-e','pdfimages',*flags,*paths]
        else:
            raise SystemExit('Install Poppler pdfimages locally or in the default WSL distribution')
        subprocess.run(command,check=True)
    with Image.open(temp/'oxygen-000.png') as im:
        if im.size != (540,590):
            raise ValueError('Unexpected Figure 4 native dimensions')
        # Read the upper stagnant panel only. No external-flow data enter this test.
        stagnant = np.array(im.crop((0,0,540,235)).convert('L'))
    if stagnant.min() > 32:
        raise ValueError('Figure 4 source image changed')
    oxygen_axis = np.polyfit([54,80,106,130,156,182],[250,200,150,100,50,0],1)
    means = np.polyval(oxygen_axis,[.5*(u+v+1) for u,v in CAPS])
    x = np.arange(19)*100
    oxygen = []
    for lo,hi in zip(DEPTH_EDGES,DEPTH_EDGES[1:]):
        z = np.r_[lo,x[(lo<x)&(x<hi)],hi]
        oxygen.append(np.trapezoid(np.interp(z,x,means),z)/(hi-lo))
    with Image.open(temp/'viability-000.png') as im:
        if im.size != (720,489):
            raise ValueError('Unexpected Figure 5 native dimensions')
        image = np.asarray(im.convert('L'))
    viability,errors = [],[]
    for i in range(7):
        cx = round(385+(i+.5)*328/7)
        wide = (image[40:169,cx-11:cx+12]<80).sum(axis=1)>=13
        top = int(np.flatnonzero(wide)[0])+40
        cap = top
        while cap>35 and (image[cap-1,cx-4:cx+5]<80).any():
            cap -= 1
        viability.append((169-top)*80/124)
        errors.append((top-cap)*80/124 if top!=cap else None)
    depth = .5*(DEPTH_EDGES[1:]+DEPTH_EDGES[:-1])
    return depth,np.array(oxygen),np.array(viability),errors


def residual_matrix(x, train, held):
    x = np.array(x)
    xc = x[train]-np.mean(x[train])
    weights = np.full((len(held),len(train)),1/len(train))
    weights += (x[held]-x[train].mean())[:,None]*xc/(xc@xc)
    matrix = np.zeros((len(held),len(x)))
    matrix[:,train] = weights
    matrix[np.arange(len(held)),held] = -1
    return matrix


def paired_bounds(E,F,y,r):
    """Sharp limits for MAE(E) - MAE(F) over error boxes shared by both fits."""
    limits = []
    for signs in itertools.product([-1,1],repeat=2*len(E)):
        s,t = np.reshape(signs,(2,-1))
        P,Q = s[:,None]*E,t[:,None]*F
        c = (P-Q).mean(axis=0)
        for direction in [-1,1]:
            res = linprog(direction*c,A_ub=-np.r_[P,Q],b_ub=np.zeros(len(signs)),
                          bounds=list(zip(np.maximum(0,y-r),np.minimum(100,y+r))),method='highs')
            if res.success:
                v = np.mean(abs(E@res.x)-abs(F@res.x))
                if abs(v-c@res.x)>1e-6:
                    raise ArithmeticError('Residual sign certificate failed')
                limits.append(float(v))
    return [min(limits),max(limits)]


def compare(depth, oxygen, y, se):
    E = residual_matrix(oxygen,TRAIN,HOLD)
    F = residual_matrix(depth,TRAIN,HOLD)
    raw = {'oxygen':E@y,'depth':F@y,'training_mean':y[TRAIN].mean()-y[HOLD]}
    for key,forecast in PAID.items():
        raw[key] = forecast-y[HOLD]
    result = {k:{'residual_pp':v.tolist(),'mae_pp':float(abs(v).mean())} for k,v in raw.items()}
    # Retrospective spatial sensitivity. Refit after holding out each consecutive
    # triple of internal bins, so adjacent target bins cannot appear in training.
    blocks = []
    for lo in range(1,4):
        held = list(range(lo,lo+3))
        train = [i for i in range(len(y)) if i not in held]
        gain = np.mean(abs(residual_matrix(depth,train,held)@y)-abs(residual_matrix(oxygen,train,held)@y))
        blocks.append({'held_bin_indices':held,'depth_MAE_minus_oxygen_MAE_pp':float(gain)})
    # Retrospective exclusion of the deepest calibration point (one viable sample).
    reduced = [0,1,4]
    deep = {k:abs(residual_matrix(z,reduced,HOLD)@y).tolist() for k,z in [('depth',depth),('oxygen',oxygen)]}
    return {
        'held_depth_intervals_um':[[int(DEPTH_EDGES[i]),int(DEPTH_EDGES[i+1])] for i in HOLD],
        'measured_held_pct':y[HOLD].tolist(),'results':result,
        'oxygen_wins_over_depth':int(np.sum(abs(raw['oxygen'])<abs(raw['depth']))),
        'chart_only_sharp_depth_MAE_minus_oxygen_MAE_pp':paired_bounds(F,E,y,np.ones(7)),
        'visible_SE_and_chart_sharp_depth_MAE_minus_oxygen_MAE_pp':
            paired_bounds(F,E,y,1+np.array([0 if s is None else s for s in se])),
        'post_reveal_block_tests':blocks,'post_reveal_omit_deepest_abs_errors_pp':deep,
        'measured_oxygen_and_depth_pearson_r':float(np.corrcoef(depth,oxygen)[0,1])}


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_pdf',type=Path)
    args = parser.parse_args()
    pdf = args.source_pdf.resolve()
    if hashlib.sha256(pdf.read_bytes()).hexdigest()!=PDF_SHA:
        raise SystemExit('Source PDF hash differs from the cited conference version')
    with tempfile.TemporaryDirectory() as temp:
        print(json.dumps(compare(*source_readings(pdf,Path(temp))),indent=2,allow_nan=False))
