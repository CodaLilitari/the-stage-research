"""Rational, six-sample, nonnegative witnesses for the last Standl observation.

Shows what survives when the paired A-V summary and derived products are withheld.
"""
from fractions import Fraction as F
import json
def arr(s):return [F(v) for v in s.split()]
def avg(x):return sum(x)/len(x)
zz=arr('-1 -1 -1 -1 -1 5')
def make(params):
    qm,qe,am,ae,vm,ve=params
    q=[qm+qe*z for z in zz];a=[am+ae*z for z in zz];v=[vm+ve*z for z in zz]
    assert min(q)>0 and min(v)>=0 and all(aa>=vv for aa,vv in zip(a,v))
    for xs,m,s in [(q,qm,qe),(a,am,ae),(v,vm,ve)]:
        assert avg(xs)==m and sum((x-m)**2 for x in xs)/(6*5)==s*s
    return [[float(y) for y in xs] for xs in [q,a,v]],avg([x*(y-z)/100 for x,y,z in zip(q,a,v)])
# All values strictly interior to printed rounding boxes. Sign of SEM coefficient
# encodes covariance direction; the observed summary standard errors are positive.
hw,h=make(arr('99.501 -18.499 6.851 .649 3.249 -.649'))
rw,r=make(arr('112.499 16.499 8.749 .449 7.151 -.449'))
assert h<r
hb,h2=make(arr('100 18 6.9 .6 3.2 -.6'))
rb,r2=make(arr('112 -16 8.7 .4 7.2 -.4'))
assert h2>r2
low=((F('99.5')*(F('6.85')-F('3.25'))-5*F('18.5')*(F('.65')+F('.65')))-
    (F('112.5')*(F('8.75')-F('7.15'))+5*F('16.5')*(F('.45')+F('.45'))))/100
assert low==F('-.163')
def lower_gap(h_difference, r_difference, h_sem, r_sem):
    h_lower = F('99.5') * h_difference - 5 * F('18.5') * h_sem
    r_upper = F('112.5') * r_difference + 5 * F('16.5') * r_sem
    return (h_lower - r_upper) / 100

# Knowing the printed mean difference tightens its allowed endpoints.
# Until its SEM is also supplied, the worst covariance bound still uses the
# sum of the arterial and venous SEM limits in each group.
mean_only = lower_gap(F('3.65'), F('1.55'), F('.65') + F('.65'), F('.45') + F('.45'))
paired = lower_gap(F('3.65'), F('1.55'), F('.85'), F('.25'))
assert mean_only == F('-.057') and paired == F('.8955')
out={'nonnegative_synthetic_witnesses_only':True,'units':'mL O2/min for mean net uptake',
     'separate_marginal_rounding_lower_bound':float(low),
     'with_paired_difference_mean_only_lower_bound':float(mean_only),
     'with_reported_paired_difference_summary_lower_bound':float(paired),
     'witness_1':{'H_q_a_v':hw,'R_q_a_v':rw,'H_minus_R_uptake':float(h-r)},
     'witness_2':{'H_q_a_v':hb,'R_q_a_v':rb,'H_minus_R_uptake':float(h2-r2)}}
print(json.dumps(out,indent=2))
