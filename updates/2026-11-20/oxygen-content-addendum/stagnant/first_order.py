"""Profile identification with a shared pair of boundary values and monotone hyperbolic weights."""
from pathlib import Path
import csv,json
import numpy as np
from scipy.optimize import linprog,brentq
ROOT=Path(__file__).parent
with (ROOT/'input/train.csv').open() as f:v=list(csv.DictReader(f))
x,y,se,chart=np.array([[float(q[k]) for k in ['depth_um','oxygen_umol_per_l','se_umol_per_l','chart_tolerance_umol_per_l']] for q in v]).T
D=x[-1]
def weights(k):
    u=np.column_stack((D-x,x))
    if k==0:return u/D
    return np.sinh(k*u)/np.sinh(k*D)
def region(err):
    low=y-err;high=y+err;ends=[(low[i],high[i]) for i in (0,-1)];outer=[0.,.02]
    for i in range(1,len(y)-1):
        def mincurve(k):return weights(k)[i]@low[[0,-1]]-high[i]
        def maxcurve(k):return weights(k)[i]@high[[0,-1]]-low[i]
        if mincurve(0)>0:outer[0]=max(outer[0],brentq(mincurve,0,.02))
        if maxcurve(.02)<0:outer[1]=min(outer[1],brentq(maxcurve,0,.02))
    def feasible(l,r):
        A=weights(l)[1:-1];B=weights(r)[1:-1]
        rr=linprog([0,0],A_ub=np.r_[A,-B],b_ub=np.r_[high[1:-1]-.0000001,-low[1:-1]-.0000001],bounds=ends,method='highs')
        if not rr.success:return None
        assert max(A@rr.x-high[1:-1])<1e-7 and max(low[1:-1]-B@rr.x)<1e-7
        return rr.x.tolist()
    # If one pair fits a cell's left upper and right lower constraints, that same
    # strictly positive pair fits every interior k by monotonicity. Test a dense
    # finite k lattice and declare only cells with such checked witnesses.
    if outer[1]<outer[0]:return {'necessary_outer_inverse_um':outer,'feasible_cell_ranges':[]}
    grid=np.linspace(*outer,201);runs=[];active=None;witness=[]
    for a,b in zip(grid,grid[1:]):
        z=feasible(a,b)
        if z is None:
            active=None;continue
        witness.append([float(a),float(b),z])
        if active is None:active=[float(a),float(b)];runs.append(active)
        else:active[1]=float(b)
    return {'necessary_outer_inverse_um':outer,'feasible_cell_ranges':runs,'common_boundary_witnesses':witness}
out={k:region(e) for k,e in [('chart_only',chart),('SE_plus_chart',chart+se)]}
(ROOT/'first-order-range.json').write_text(json.dumps(out,indent=2))
print({k:(v['necessary_outer_inverse_um'],v['feasible_cell_ranges']) for k,v in out.items()})
