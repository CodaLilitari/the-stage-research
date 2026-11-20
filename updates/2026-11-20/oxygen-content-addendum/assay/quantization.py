"""Ask whether a displayed lattice alone could account for departures from individual proportionality."""
from pathlib import Path
import json
import numpy as np
from scipy.optimize import minimize_scalar
from score import data,assignments

def run():
    series=data();out={}
    for (instrument,observable),g in series.items():
        a,b=g[5][:,1],g[10][:,1];y=np.r_[a,b]
        # Widest common plotting increment consistent with both the distinct
        # spacings and the near-zero grid origin. Densely print-tested intervals
        # separate the visibly coarsely and finely quantized panels.
        fine=instrument.startswith('Abbott')
        floor,ceil=(.014,.023) if fine else (.145,.18)
        def obj(h):return np.max(abs(y-h*np.rint(y/h)))
        grid=np.linspace(floor,ceil,2001);q=grid[np.argmin([obj(h) for h in grid])]
        res=minimize_scalar(obj,bounds=(max(q-.00005,floor),min(q+.00005,ceil)),method='bounded',options={'xatol':1e-12});h=res.x
        residual=obj(h);assert residual<.00035
        ix=assignments(g[5][:,0],g[10][:,0],.005)
        diff=abs(2*a-b[ix]);maxdiff=diff.max(axis=1);chart_pad=3*.002
        needed=float(maxdiff.min())
        k=(diff>2*h+chart_pad).sum(axis=1);maxk=(diff>2*h-chart_pad).sum(axis=1)
        out[instrument+';'+observable]={'visible_step_g_dl':float(h),'max_marker_departure_from_step':float(residual),'max_error_best_matching':needed,'max_error_worst_matching':float(maxdiff.max()),'minimum_all_readings_rounding_increment_for_proportionality_at_best_matching':needed/2,'count_discrepant_with_rounding_and_chart_pad_range':[int(k.min()),int(maxk.max())],'n':len(a)}
    f=Path(__file__).parent/'quantization-qa.json';f.write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
if __name__=='__main__':run()
