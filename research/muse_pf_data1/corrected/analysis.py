"""Exploratory reanalysis of published subject-level values, not a biological validation."""
from pathlib import Path
import json, hashlib, csv, sys
import numpy as np
import pandas as pd
from scipy import stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent; BASE=ROOT.parent
def save(name,data): (ROOT/name).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def interval(x):
    n=len(x); sd=float(np.std(x,ddof=1)); se=sd/np.sqrt(n); m=float(np.mean(x)); t=stats.t.ppf(.975,n-1)
    return {'n':n,'mean':m,'sd':sd,'se':float(se),'mean_t95_ci':[float(m-t*se),float(m+t*se)]}
def fit(x,y,kind):
    X={'constant':np.ones((len(x),1)),'proportional':x[:,None],'affine':np.column_stack([np.ones(len(x)),x])}[kind]
    b=np.linalg.lstsq(X,y,rcond=None)[0]; r=y-X@b; n,p=X.shape; sse=float(r@r)
    cov=sse/(n-p)*np.linalg.inv(X.T@X); se=np.sqrt(np.diag(cov)); t=stats.t.ppf(.975,n-p)
    leverage=np.sum(X*(X@np.linalg.inv(X.T@X)),axis=1)
    k=p+1 # residual-variance parameter included; additive Gaussian constant omitted
    return {'coefficients_intercept_then_slope_if_affine':b.tolist(),'coefficient_se':se.tolist(),'coefficient_t95_ci':np.column_stack([b-t*se,b+t*se]).tolist(),'sse':sse,'aicc_omitting_common_constant':float(n*np.log(sse/n)+2*k+2*k*(k+1)/(n-k-1)),'loocv_mse':float(np.mean((r/(1-leverage))**2)),'n':n,'regression_parameters':p}
def main():
    freeze=json.loads((BASE/'freeze.json').read_text())
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==freeze['sha256']['corrected/analysis.py']
    df=pd.read_csv(BASE/'raw/stuecker2002_table1.csv'); x=df.flux_norm_mlO2_min_m2.to_numpy(); y=df.occlusion_delta_mlO2_min_m2.to_numpy()
    young=df.age_years<30; older=df.age_years>=70
    age={'young':interval(x[young]),'older':interval(x[older]),'older_volunteers':df.volunteer[older].tolist(),'welch_p':float(stats.ttest_ind(x[young],x[older],equal_var=False).pvalue),'pooled_p':float(stats.ttest_ind(x[young],x[older],equal_var=True).pvalue),'original_strict_over_70_excludes':df.volunteer[df.age_years==70].tolist()}
    lin=stats.linregress(x,y); r=stats.pearsonr(x,y); rci=r.confidence_interval()
    models={kind:fit(x,y,kind) for kind in ['constant','proportional','affine']}
    reduced=df.flux_reduced_mlO2_min_m2.to_numpy(); pred=df.sspO2_reduced_Torr.to_numpy(); pnorm=df.sspO2_norm_Torr.to_numpy()
    p_slope=(x-reduced)/(pnorm-pred); p_intercept=reduced-p_slope*pred
    meanx=interval(x); lower,upper=meanx['mean_t95_ci']
    # Literature demand is a scenario range, not a posterior or measured per-subject covariate.
    qlo,qhi=1470.,2110.
    derived=pd.DataFrame({'volunteer':df.volunteer,'age_years':df.age_years,'normal_flux_ml_m2_min':x,'delta_flux_ml_m2_min':y,'percent_change':100*y/x,'consuming_depth_min_um':x/qhi*1e6,'consuming_depth_max_um':x/qlo*1e6,'total_depth_min_um':x/qhi*1e6+15,'total_depth_max_um':x/qlo*1e6+15,'two_point_pressure_slope':p_slope,'two_point_extrapolated_intercept':p_intercept})
    derived.to_csv(ROOT/'per_subject_corrected.csv',index=False)
    summary={'scope':'Exploratory analysis of 20 rounded published rows. Confidence intervals are conditional subject-sampling calculations, not total measurement or population-generalization uncertainty. No equivalence margin or mechanistic identification was prespecified.',
      'normal_flux':meanx,'occlusion_absolute':interval(y),'occlusion_relative_percent':interval(100*y/x),'occlusion_t_p':float(stats.ttest_1samp(y,0).pvalue),'age_groups':age,
      'association':{'pearson_r':float(r.statistic),'pearson_p':float(r.pvalue),'pearson_fisher95_ci':[float(rci.low),float(rci.high)],'slope_se':float(lin.stderr),'intercept_se':float(lin.intercept_stderr)},'candidate_models':models,
      'leave_v19_out_exploratory':{kind:fit(x[df.volunteer!=19],y[df.volunteer!=19],kind) for kind in models},
      'pressure':{'paired_normal_minus_reduced_flux':interval(x-reduced),'two_point_slopes':interval(p_slope),'two_point_extrapolated_intercepts':interval(p_intercept),'intercept_t_p':float(stats.ttest_1samp(p_intercept,0).pvalue),'limitation':'Two observations define each line exactly: these data cannot test individual linearity. A nonsignificant intercept test does not establish proportionality.'},
      'depth':{'consuming_mean_flux_scenario_range_um':[meanx['mean']/qhi*1e6,meanx['mean']/qlo*1e6],'total_including_15_um_mean_flux_scenario_range_um':[meanx['mean']/qhi*1e6+15,meanx['mean']/qlo*1e6+15],'conditional_mean_total_t95_by_demand':{str(q):[lower/q*1e6+15,upper/q*1e6+15] for q in [qlo,qhi]},'per_subject_total_scenario_extent_um':[float(derived.total_depth_min_um.min()),float(derived.total_depth_max_um.max())],'limitations':'T=J/q assumes compatible gas-volume reference conventions and homogeneous demand. The historical q range is not measured in these subjects. It is not a channel-spacing or safety threshold.'},
      'gas_reference_scenarios':{name:{'ml_per_mol_assumed':v,'q_observed_mol_m3_s_range':[qlo/(60*v),qhi/(60*v)]} for name,v in [('0C_1atm_ideal_gas',22414.),('25C_1atm_ideal_gas',24465.)]},
      'instrument_correction':'The membrane driving difference is external minus skin-surface PO2 within one condition; normal minus reduced skin-surface pressures is not that membrane difference.',
      'original_mc_interpretation':'Empirical subject-mixture and an independent analyst-chosen uniform demand scenario. Central 95% scenario interval, not confidence interval or posterior.'}
    save('summary.json',summary)
    fig,ax=plt.subplots(1,2,figsize=(11,4.7))
    ax[0].scatter(x,y,color='#176b87',s=35)
    xx=np.linspace(0,1.2,100)
    ax[0].plot(xx,np.repeat(models['constant']['coefficients_intercept_then_slope_if_affine'][0],len(xx)),label='constant mean',color='#d97706')
    ax[0].plot(xx,models['proportional']['coefficients_intercept_then_slope_if_affine'][0]*xx,label='proportional fit',ls='--',color='#834f9b')
    b=models['affine']['coefficients_intercept_then_slope_if_affine'];ax[0].plot(xx,b[0]+b[1]*xx,label='intercept + slope',color='#176b87')
    ax[0].set(xlabel='Normal surface flux (ml O2 / m² / min)',ylabel='Five-minute occlusion increase (same units)',title='Association and candidate descriptive fits')
    ax[0].legend(fontsize=8)
    for i,row in derived.iterrows(): ax[1].plot([row.total_depth_min_um,row.total_depth_max_um],[row.volunteer,row.volunteer],color='#167d65',lw=2)
    ax[1].set(xlabel='J / literature demand + 15 µm (µm)',ylabel='Volunteer',title='Demand-range scenarios for published flux',yticks=[1,5,10,15,20])
    for a in ax:a.grid(alpha=.2)
    fig.suptitle('PF-DATA1 correction | published observations, conditional inference',fontsize=12)
    fig.text(.5,.015,'Lines at right are parameter scenarios, not confidence intervals. Neither panel certifies tissue thickness or blood-supply mechanism.',ha='center',fontsize=8)
    fig.tight_layout(rect=[0,.05,1,.93]);fig.savefig(ROOT/'corrected_analysis.png',dpi=170);plt.close(fig)
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
