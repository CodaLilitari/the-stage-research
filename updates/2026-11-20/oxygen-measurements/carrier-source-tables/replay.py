"""Acquire or use source originals and replay the published-data calculations. Python standard library + Poppler."""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import re
import shutil
from statistics import mean
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent


def acquire(cache, fetch, registry):
    cache.mkdir(parents=True, exist_ok=True)
    docs = {}
    for name, record in registry.items():
        path = cache / name
        if not path.is_file():
            if not fetch:
                raise FileNotFoundError(f'Add {name} from {record["url"]} to {cache}, or use --fetch.')
            with urllib.request.urlopen(record['url'], timeout=45) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != record['sha256']:
                raise ValueError(f'Download differs from verified edition of {name}; source review required.')
            path.write_bytes(data)
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != record['sha256']:
            raise ValueError(f'Unrecognized source edition of {name}. See sources.json.')
        docs[name] = data
    return docs


def pdf_page(data, page):
    command = shutil.which('pdftotext')
    if command:
        prefix = [command]
    elif sys.platform == 'win32' and shutil.which('wsl.exe'):
        prefix = ['wsl.exe', '-d', 'Ubuntu', '--', 'pdftotext']
    else:
        raise RuntimeError('Install Poppler pdftotext or provide it in WSL Ubuntu.')
    args = prefix + ['-layout', '-f', str(page), '-l', str(page), '-', '-']
    result = subprocess.run(args, input=data, capture_output=True, timeout=45, check=True)
    return result.stdout.decode('utf-8')


def text(element):
    return ' '.join(''.join(element.itertext()).split())


def laing(raw, matton):
    doc = ET.fromstring(raw)
    def table(num):
        t = next(x for x in doc.iter('table-wrap') if x.findtext('label') == 'Table '+str(num))
        return [[text(c) for c in row] for row in t.iter('tr')]
    tab = table(3)
    def row(prefix):
        return next(r[1:] for r in tab if r[0].startswith(prefix))
    e = list(map(float, row('Mean O2 ER per gram')))
    mass = list(map(float, row('Liver weight')))
    dt = row('Donor type')
    assert len(e) == len(dt) == len(mass) == 10
    organs = [a*b/1000 for a,b in zip(e,mass)]
    groups = range(10)
    def diff(ids):
        return mean(organs[i] for i in ids) - mean(organs[i] for i in groups if i not in ids)
    observed = diff(range(5,10))
    labels = list(itertools.combinations(groups,5))
    strata = [k for k in labels if sum(dt[i]=='DBD' for i in k)==1]
    def count(sample):
        return sum(abs(diff(k)) >= abs(observed)-1e-10 for k in sample)
    measures = {}
    for r in table(2):
        if r[0] in ['PO2 (kPa)','tHb (g/L)','O2Hb (%)','SO2 (%)']:
            measures[r[0]] = [[float(v) for v in re.fullmatch(r'([.\d]+) \(([.\d]+)-([.\d]+)\).*',cell).groups()] for cell in r[1:3]]
    mt = [text(x) for x in ET.fromstring(matton).iter('p')]
    provenance = next(x for x in mt if '0.0225' in x and '1.39' in x and '1.26' in x)
    assert 'kPa' in provenance and 'g/dL' in provenance
    envelopes = {}
    for kind in ['O2Hb (%)','SO2 (%)']:
        envelopes[kind] = {}
        for i,(g,c) in enumerate([('RBC',1.39),('HBOC',1.26)]):
            totals=[.0225*z+c*h/10*s/100 for z,h,s in zip(measures['PO2 (kPa)'][i],measures['tHb (g/L)'][i],measures[kind][i])]
            envelopes[kind][g]=dict(zip(['marginal_median_plugin','minimum','maximum'],totals))
    return {'mean_organ_extraction_percent':{'RBC':mean(organs[:5]),'HBOC':mean(organs[5:])},
            'HBOC_minus_RBC_pp':observed,'label_counts':[count(labels),len(labels),count(strata),len(strata)],
            'conditional_content_mL_per_dL':envelopes}


def freire(raw):
    page = pdf_page(raw,5)
    pattern = r'(?m)^([1-6])\s+([\d.]+)\s*±\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*±\s*([\d.]+)'
    rows = [tuple(map(float,m)) for m in re.findall(pattern, page)]
    assert [int(r[0]) for r in rows] == list(range(1,7))
    diagnostics = {}
    for method in ['component','pooled','within_pfc']:
        residuals=[]
        for i,r in enumerate(rows):
            training=[j for j in range(6) if j%3 != i%3]
            if method=='component': pred=r[3]
            elif method=='pooled': pred=mean(rows[j][1] for j in training)
            else: pred=mean(rows[j][1] for j in training if j//3==i//3)
            residuals.append(pred-r[1])
        diagnostics[method]={'MAE':mean(map(abs,residuals)),'RMSE':math.sqrt(mean(v*v for v in residuals))}
    return {'counts':[len(rows),3],'whole_interface_error_umol_per_mL':diagnostics,
            'matched_contrasts_umol_per_mL':[rows[i][1]-rows[i+3][1] for i in range(3)]}


def dias(raw2004,raw2003):
    p4=pdf_page(raw2004,3)
    # Restrict extraction to the first experimental table and use the PDF's left column.
    span=p4.split('C6 F14',1)[1].split('3.3. Thermodynamic functions',1)[0]
    def series(s):
        expr=r'(?m)^\s*(\d{3}\.\d{2})\s+(0\.\d+)\s*±\s*0\.\d+\s+(\d\.\d{2})\s*±'
        return [tuple(map(float,m)) for m in re.findall(expr,s)]
    c6=series(span.split('C7 F16')[0]);c10=series(span.split('C10 F18')[1])
    p3=pdf_page(raw2003,3)

    # Read only the perfluorohexane block after the hydrocarbon measurements.
    old=re.findall(r'\b(\d{3}\.\d{2})\s+(0\.\d{4})\s+(0\.\d{3})\s+(\d\.\d{2})\s+(\d{2}\.\d)\b',p3.split('n-C6F14',1)[1])
    old=[tuple(map(float,r)) for r in old]
    assert (len(c6),len(c10),len(old))==(5,7,9),(len(c6),len(c10),len(old))
    def secant(series,t,col):
        i=min(max(sum(r[0]<t for r in series)-1,0),len(series)-2)
        a,b=series[i:i+2];u=(t-a[0])/(b[0]-a[0])
        return a[col]*(1-u)+b[col]*u
    result={}
    for name,col,j in [('native_L',1,2),('standardized_1000x',2,3)]:
        errs=[100*(secant(c6,r[0],col)/r[j]-1) for r in old]
        result[name]={'N':len(errs),'individual_pass_2pct':sum(abs(e)<=2 for e in errs),
                      'mean_abs_relative_error_pct':mean(map(abs,errs))}
    result['dry_humid_310_2K_umol_per_mL']={}
    for name,data in [('C6F14',c6),('C10F18',c10)]:
        L=secant(data,310.2,1)
        result['dry_humid_310_2K_umol_per_mL'][name]=[L*.2095*(101325-w)/(8.31446261815324*310.2) for w in [0,6280]]
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source-dir',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--fetch',action='store_true')
    args=ap.parse_args()
    docs=acquire(args.source_dir,args.fetch,json.loads((HERE/'sources.json').read_text()))
    result={'Laing':laing(docs['laing.xml'],docs['matton.xml']),'Freire':freire(docs['freire.pdf']),
            'Dias':dias(docs['dias-2004.pdf'],docs['dias-2003.pdf'])}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(args.output)


if __name__=='__main__':
    main()
