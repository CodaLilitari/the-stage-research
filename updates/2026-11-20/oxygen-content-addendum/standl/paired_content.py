"""Reproduce the final-occasion sample-product bounds in Standl et al., Tables I–III."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

SOURCE_SHA256 = "917ce2a3397fb5359ea2792902d3a0638f0814ef8a7e991839cfcca13b49df4e"
# Mean and SEM for the reported flow, arterial content and within-animal content gradient.
# Flow in mL/min; oxygen content in mL O2/dL. Six animals in each group.
GROUPS = {
    "HBOC-201": ((100., 18.), (6.9, .6), (3.7, .8)),
    "stored red cells": ((112., 16.), (8.7, .4), (1.5, .2)),
}


def read_source(pdf, pdftotext):
    assert hashlib.sha256(pdf.read_bytes()).hexdigest() == SOURCE_SHA256
    result = subprocess.run([pdftotext, "-layout", "-enc", "UTF-8", str(pdf), "-"],
                            check=True, capture_output=True, timeout=30)
    lines = result.stdout.decode("utf-8").splitlines()
    pair = re.compile(r"([-\d.]+)\s*⫾\s*([\d.]+)")

    def rows(label):
        start = next(i for i, s in enumerate(lines) if s.startswith(label))
        records = [s for s in lines[start:] if re.match(r"\s*(?:Baseline|Time [1-4])\s", s)][:10]
        return [[(float(a),float(b)) for a,b in pair.findall(records[idx])] for idx in (4,9)]

    flow, gases, muscle = (rows(label) for label in ("Table I. Hemodynamic", "Table II. Arterial",
                                                      "Table III. Muscular"))
    for i, key in enumerate(GROUPS):
        assert (flow[i][2],muscle[i][2],muscle[i][4]) == GROUPS[key]
    return {
        key: {"pressure_gradient_mmHg": gases[i][0][0] - gases[i][3][0],
              "arterial_and_venous_content": [muscle[i][2][0],muscle[i][3][0]],
              "published_mean_delivery_and_uptake": [muscle[i][5][0],muscle[i][6][0]]}
        for i,key in enumerate(GROUPS)
    }


def outer(flow, content):
    # For n=6, |mean(q*x)-mean(q)*mean(x)| <= (n-1)*SEM(q)*SEM(x).
    # The monotone endpoints below widen all printed means and SEMs by half a last digit.
    q, sq = flow
    x, sx = content
    max_cross_term = 5 * (sq + .5) * (sx + .05)
    low = ((q - .5) * (x - .05) - max_cross_term) / 100
    high = ((q + .5) * (x + .05) + max_cross_term) / 100
    return [low, high]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-pdf",type=Path,help="Optionally confirm printed inputs from the original PDF.")
    parser.add_argument("--pdftotext",default="pdftotext",help="Poppler pdftotext executable.")
    args=parser.parse_args()
    results={}
    for key,(flow,arterial,difference) in GROUPS.items():
        results[key]={"delivery_mL_per_min": outer(flow,arterial),
                      "uptake_mL_per_min": outer(flow,difference)}
    h,r=results.values()
    out={"sample_mean_product_outer_bounds":results,
         "minimum_HBOC_minus_RBC_uptake_mL_per_min":h["uptake_mL_per_min"][0]-r["uptake_mL_per_min"][1],
         "minimum_RBC_minus_HBOC_delivery_mL_per_min":r["delivery_mL_per_min"][0]-h["delivery_mL_per_min"][1]}
    if args.source_pdf:
        out["verified_from_original"]=read_source(args.source_pdf,args.pdftotext)
    print(json.dumps(out,indent=2))


if __name__=="__main__":
    main()
