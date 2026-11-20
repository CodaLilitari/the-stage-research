"""Post-disclosure interpolation audit of the four Navari 22 g/dL observations."""
import itertools
import json
import math
from pathlib import Path

import numpy as np
from scipy.optimize import linprog

P=np.array([50.,100.,150.,760.])
Y=np.array([.0040,.0090,.0143,.0797])
S=np.array([.0010,.0010,.0011,.0011])
# Each residual is a linear function of [y50, y100, y150, y760].
t=(P[1:3]-P[0])/(P[3]-P[0])
affine=np.array([[1-t[0],-1,0,t[0]],[1-t[1],0,-1,t[1]]])
origin=np.array([[0,-1,0,P[1]/P[3]],[0,0,-1,P[2]/P[3]]])
A=np.vstack((origin,affine))
def signed_gain(vals):
    abs_errors=abs(A@vals)
    return float((abs_errors[:2].sum()-abs_errors[2:].sum())/2)
def joint_bounds(halfwidth):
    """Exact extrema of paired MAE gain on an error box via its 16 sign regions."""
    bounds=list(zip(Y-halfwidth,Y+halfwidth))
    extrema=[]
    for signs in itertools.product((-1,1),repeat=4):
        # Within each region |r| = sign*r; enforce sign*r >= 0.
        sec=np.diag(signs)@A
        objective=(np.array([1.,1.,-1.,-1.])@sec)/2
        for mult in (-1.,1.):
            ans=linprog(mult*objective,A_ub=-sec,b_ub=np.zeros(4),bounds=bounds,method="highs")
            if ans.success: extrema.append(signed_gain(ans.x))
    return [min(extrema),max(extrema)]
def min_scale(with_offset):
    X=np.stack((P,np.ones(4)),axis=1) if with_offset else P[:,None]
    result=linprog([0]*X.shape[1]+[1],A_ub=np.vstack((np.c_[X,-S],np.c_[-X,-S])),
                   b_ub=np.r_[Y,-Y],bounds=[(None,None)]*X.shape[1]+[(0,None)],method="highs")
    assert result.success
    return result.x.tolist()


def main():
    r={}
    for name,mat in (("affine",affine),("origin",origin)):
        e=mat@Y
        r[name]={"predictions":list(e+Y[1:3]),"errors":list(e),"mae":float(abs(e).mean()),"rmse":float((e@e/2)**.5)}
    # Native cm^3 oxygen per cm^3 prepared dispersion.
    intercept=Y[0]-P[0]*(Y[3]-Y[0])/(P[3]-P[0])
    iwidth=(P[3]*S[0]+P[0]*S[3])/(P[3]-P[0])
    out={"points":P.tolist(),"native":Y.tolist(),"sd":S.tolist(),"results":r,
         "improvement":signed_gain(Y),"gain_rounding":joint_bounds(np.full(4,.00005)),"gain_1sd":joint_bounds(S),
         "minimum_sd_factor_for_any_origin_line":min_scale(False),
         "minimum_sd_factor_for_any_affine_line":min_scale(True),
         "apparent_intercept":float(intercept),"apparent_intercept_1sd_envelope":[intercept-iwidth,intercept+iwidth],
         "second_difference_50_100_150":float(Y[0]-2*Y[1]+Y[2]),"second_difference_1sd_halfwidth":float(S[0]+2*S[1]+S[2])}
    (Path(__file__).parent/"interior-results.json").write_text(json.dumps(out,indent=2))
    print(json.dumps(out,indent=2))
if __name__=="__main__": main()
