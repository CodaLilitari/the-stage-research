"""Finite data constrain weighted integrals of curvature rather than the pointwise source."""
from pathlib import Path
import csv,json
import numpy as np
from scipy.optimize import linprog
ROOT=Path(__file__).parent
with (ROOT/'input/train.csv').open() as f:tab=list(csv.DictReader(f))
x,y,e,tol=np.array([[float(r[q]) for q in ('depth_um','oxygen_umol_per_l','se_umol_per_l','chart_tolerance_umol_per_l')] for r in tab]).T
n=len(x);h=x[1]-x[0];K=np.diff(np.eye(n),n=2,axis=0)
def lp(v,obj=None):
    return linprog(np.zeros(n) if obj is None else obj,A_ub=-K,b_ub=np.zeros(n-2),bounds=list(zip(y-v,y+v)),method='highs')
def uniform_epsilon():
    mat=np.vstack([np.c_[-K,np.zeros(n-2)],np.c_[np.eye(n),-np.ones(n)],np.c_[-np.eye(n),-np.ones(n)]])
    r=linprog(np.r_[np.zeros(n),1.],A_ub=mat,b_ub=np.r_[np.zeros(n-2),y,-y],bounds=[(None,None)]*n+[(0,None)],method='highs')
    assert r.success
    return r.x[-1],r.x[:n]
def effects(v):
    if not lp(v).success:return {'feasible':False}
    lower=np.zeros(n);upper=np.zeros(n);i,j=4,14
    lower[j]+=1/h;lower[j-1]-=1/h;lower[i+1]-=1/h;lower[i]+=1/h
    upper[j+1]+=1/h;upper[j]-=1/h;upper[i]-=1/h;upper[i-1]+=1/h
    lo=lp(v,lower);hi=lp(v,-upper)
    assert lo.success and hi.success
    # Work in micromolar per um. The extrema are sharp for these secant
    # comparisons; the derivative interval itself is an outer bound.
    return {'feasible':True,'outer_source_integral_400_to_1400_umol_L_per_um':[max(0,lo.fun),-hi.fun],'first_and_last_retained_secant_um':[300,1500]}
def constant_fit():
    # Find the smallest fraction of each printed SE-plus-reading band admitting one convex quadratic.
    z=x/x[-1];A=np.array([np.ones(n),z,z*z]).T;v=e+tol
    r=linprog([0,0,0,1],A_ub=np.r_[np.c_[A,-v],np.c_[-A,-v]],b_ub=np.r_[y,-y],bounds=[(None,None),(None,None),(0,None),(0,None)],method='highs')
    assert r.success
    a,b,k=r.x[:3];q=2*k/x[-1]**2
    # The impulse-response update across a width h depends only on mass and first moment.
    baseline=a+b*z+k*z*z
    # Replace the source in [800,900] by a uniform compact peak centered in that interval.
    witnesses=[]
    for factor in [1,10,100]:
        mass=q*h;moment=mass*h/2
        after_slope=q*h;after_c=q*h*h/2
        # Uniform peak supported on the central subinterval.
        width=h/factor;height=q*factor;start=(h-width)/2
        assert abs(width*height-mass)<1e-12
        assert abs(width*height*(start+width/2)-moment)<1e-12
        c1=height*width*(h-start-width/2);assert abs(c1-after_c)<1e-10 and abs(height*width-after_slope)<1e-12
        witnesses.append({'peak_factor':factor,'width_um':width,'peak_curvature_umol_L_um2':height,'max_change_at_measured_nodes_umol_L':0.})
    continuous=[]
    for factor in [10,100]:
        # Symmetric end collars match q continuously to each neighboring cell.
        # A central triangular bump carries all remaining mass.
        collar=h/20;width=2*(h-collar)/factor;peak=factor*q
        xx=np.array([0,collar,(h-width)/2,h/2,(h+width)/2,h-collar,h])
        yy=np.array([q,0,0,peak,0,0,q]);assert np.all(np.diff(xx)>0)
        mass=np.trapezoid(yy,xx)
        # The first moment follows from symmetry and mass. Verify the exact
        # piecewise-linear integral of x*q(x) independently on each segment.
        moment=sum((r-l)/6*(yl*(2*l+r)+yr*(l+2*r)) for l,r,yl,yr in zip(xx[:-1],xx[1:],yy[:-1],yy[1:]))
        assert abs(mass-q*h)<1e-12 and abs(moment-q*h*h/2)<1e-10
        continuous.append({'factor':factor,'central_width_um':width,'collar_width_um':collar,'peak_umol_L_um2':peak,'max_node_change_umol_L':0.})
    return {'SE_plus_reading_band_fraction_needed':r.x[-1],'coefficients_in_normalized_depth_micromolar':[a,b,k],'curvature_umol_L_um2':q,'minimum_concentration_at_nodes_umol_L':min(baseline),'piecewise_constant_witnesses':witnesses,'continuous_witnesses':continuous}
def sharp_interior(v,lo_um,hi_um):
    # A nonnegative curvature distribution's contribution to measurements at the grid
    # nodes depends only on its mass and first moment inside each open grid cell.
    # Split each cell's mass between its two ends preserving this first moment.
    # These endpoint masses are closure variables for smooth densities supported
    # strictly inside the respective cells; endpoints shared by two cells may
    # carry mass from either side. A strictly feasible profile makes the extrema
    # approachable by continuous densities, while keeping all node bands.
    starts=np.repeat(np.arange(n-1),2);loc=starts+np.tile([0,1],n-1)
    index=x/h
    M=np.column_stack((np.ones(n),index,np.maximum(0,index[:,None]-loc)))
    cost=np.r_[0.,0.,((starts>=lo_um/h)&(starts<hi_um/h))/h]
    r=[]
    for sign in [1,-1]:
        fit=linprog(sign*cost,A_ub=np.r_[M,-M],b_ub=np.r_[y+v,-y+v],bounds=[(None,None)]*2+[(0,None)]*len(loc),method='highs')
        assert fit.success and max(abs(M@fit.x-y)-v)<1e-7
        value=float(cost@fit.x)
        dual_bound=sign*np.r_[y+v,-y+v]@fit.ineqlin.marginals
        assert abs(dual_bound-value)<1e-8
        r.append({'value_umol_L_per_um':value,'residual_dual_gap':abs(dual_bound-value),'nonzero_cell_endpoint_masses_in_scaled_units':[(int(starts[j]),int(loc[j]),float(fit.x[j+2])) for j in range(len(loc)) if fit.x[j+2]>1e-7]})
    return {'interval_um':[lo_um,hi_um],'infimum_and_supremum_umol_L_per_um':[rr['value_umol_L_per_um'] for rr in r],'primal_and_dual_checks':r}
eps,c=uniform_epsilon()
result={'min_uniform_adjustment_for_convex_profile_umol_L':eps,'convex_projection':c.tolist(),'reading_only':effects(tol),'SE_plus_reading_sensitivity':effects(e+tol),'constant_positive_source':constant_fit(),'sharp_conditional':{k:[sharp_interior(v,a,b) for a,b in [(400,1400),(200,1600),(600,1200)]] for k,v in [('reading',tol),('SE_plus_reading',e+tol)]}}
(ROOT/'stagnant-inverse.json').write_text(json.dumps(result,indent=2));print({k:[q['infimum_and_supremum_umol_L_per_um'] for q in vv] for k,vv in result['sharp_conditional'].items()})
