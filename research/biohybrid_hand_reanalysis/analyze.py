"""BH0: bounded descriptive reuse of two published, hash-verified CSV files."""
from pathlib import Path
import argparse, csv, datetime, hashlib, json, math, platform, statistics, sys

BASE=Path(__file__).resolve().parent
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def stats(values):
    return {'mean':statistics.mean(values),'sample_sd_ddof1':statistics.stdev(values),
            'count':len(values),'min':min(values),'max':max(values)}
def inputs():
    return {str(p.relative_to(BASE)):sha(p) for p in [BASE/'analyze.py',BASE/'source_extraction.txt',BASE/'data_receipt.json',BASE/'data/3A.csv',BASE/'data/3B.csv']}
def read(name):
    with (BASE/'data'/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.reader(f))
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--freeze',action='store_true'); ap.add_argument('--out',default='results'); args=ap.parse_args()
    freeze_path=BASE/'analysis_freeze.json'
    if args.freeze:
        if freeze_path.exists(): raise FileExistsError(freeze_path)
        plan={'frozen_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sha256':inputs(),
              'questions':['Reproduce 3A descriptive summaries without inventing sample independence or pairing.',
                           'Summarize 3B force and within-actuator force/count-one ratios across three samples.',
                           'Compare normalized force with count-proportional reference, with no fitted scaling law or extrapolation.'],
              'sample_unit':'3B: actuator, n=3; counts are repeated within actuator. 3A: unlabeled observations only.',
              'checks':['3A 15 numeric rows/condition','3B exactly 3 samples with counts 1..8',
                        '3B relative-force formula within 5e-8','3B duplicate block agrees within 5e-8',
                        '3A printed means agree within 1e-8','3A printed SD matches either ddof0 or ddof1 within 1e-8'],
              'no_inference':['No p-value, confidence interval, donor generalization, oxygen causal claim, biological replication, or extrapolation above eight tissues.']}
        freeze_path.write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8');print('Analysis frozen; no aggregate calculation run.');return
    plan=json.loads(freeze_path.read_text(encoding='utf-8'))
    if inputs()!=plan['sha256']: raise ValueError('Frozen inputs/source changed')
    out=BASE/args.out
    if out.exists():raise FileExistsError(out)
    out.mkdir()
    a=read('3A.csv'); b=read('3B.csv')
    assert a[0][:2]==['in sheet','in bundle']
    observations=[]
    for row in a[1:]:
        try:observations.append([float(row[0]),float(row[1])])
        except (ValueError,IndexError):break
    a_stats={label:stats([r[i] for r in observations]) for i,label in enumerate(a[0][:2])}
    av_row=next(i for i,r in enumerate(a) if r[0]=='average')+1
    sd_row=next(i for i,r in enumerate(a) if r[0]=='sd')+1
    print_means=list(map(float,a[av_row][:2]));print_sds=list(map(float,a[sd_row][:2]))
    mean_error=max(abs(a_stats[label]['mean']-print_means[i]) for i,label in enumerate(a[0][:2]))
    sd_errors={str(ddof):max(abs((statistics.stdev if ddof else statistics.pstdev)([r[i] for r in observations])-print_sds[i]) for i in range(2)) for ddof in [0,1]}
    samples={};label=None;stored={};duplicate={}
    for row in b[1:]:
        if row[0]:label=row[0];samples[label]={}
        if row[1]:
            n=int(row[1]);samples[label][n]=float(row[2]);stored[(label,n)]=float(row[4])
        if row[6]:duplicate.setdefault(int(row[6]),[]).append(float(row[7]))
    ratios={(s,n):f/samples[s][1] for s,series in samples.items() for n,f in series.items()}
    ratio_error=max(abs(ratios[k]-v) for k,v in stored.items())
    duplicate_error=max(abs(duplicate[n][i]-stored[(s,n)]) for n in range(1,9) for i,s in enumerate(samples))
    summary=[]
    for n in range(1,9):
        fs=stats([v[n] for v in samples.values()]);rs=stats([ratios[s,n] for s in samples]);es=stats([ratios[s,n]/n for s in samples])
        summary.append({'tissue_count':n,'force_mean_mN':fs['mean'],'force_sd_mN':fs['sample_sd_ddof1'],
                        'relative_mean':rs['mean'],'relative_sd':rs['sample_sd_ddof1'],
                        'relative_per_count_mean':es['mean'],'relative_per_count_sd':es['sample_sd_ddof1']})
    checks={'3A_row_counts':len(observations)==15,
            '3B_sample_count_and_coverage':len(samples)==3 and all(set(v)==set(range(1,9)) for v in samples.values()),
            'relative_formula':ratio_error<5e-8,'duplicate_block':duplicate_error<5e-8,
            'printed_3A_means':mean_error<1e-8,'printed_3A_sd_convention_identified':min(sd_errors.values())<1e-8}
    results={'source':'Dryad 10.5061/dryad.xd2547drh v7, article 10.1126/scirobotics.adr5512',
             'analysis_type':'descriptive reuse; no new biological experiment',
             '3A':{'observation_statistics_mN':a_stats,'group_mean_ratio_sheet_over_bundle':a_stats['in sheet']['mean']/a_stats['in bundle']['mean'],
                   'pairing':'not identified; no paired contrast computed','printed_mean_max_error':mean_error,'printed_sd_max_errors_by_ddof':sd_errors},
             '3B':{'sample_count':3,'observations':24,'samples_force_mN':samples,'summary':summary,
                   'within_actuator_8_over_1_ratios':{s:ratios[s,8] for s in samples},
                   'within_actuator_8_minus_7_mN':{s:v[8]-v[7] for s,v in samples.items()},
                   'relative_formula_max_abs_error':ratio_error,'duplicate_block_max_abs_error':duplicate_error},'checks':checks}
    (out/'results.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
    with (out/'force_by_count.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(summary[0]));writer.writeheader();writer.writerows(summary)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axs=plt.subplots(1,2,figsize=(11,4.8),layout='constrained')
    ns=list(range(1,9))
    for s,v in samples.items():
        axs[0].plot(ns,[v[n] for n in ns],'-o',label=s)
        axs[1].plot(ns,[ratios[s,n] for n in ns],'-o',label=s)
    axs[1].plot(ns,ns,'k--',label='Proportional reference')
    axs[0].set_ylabel('Contractile force (mN)');axs[1].set_ylabel('Force / same actuator force at count 1')
    for ax in axs:ax.set_xlabel('Number of muscle tissues');ax.set_xticks(ns);ax.grid(alpha=.2);ax.legend()
    fig.suptitle('BH0: published force measurements — three actuator samples, repeated counts')
    fig.savefig(out/'force_scaling.png',dpi=160);plt.close(fig)
    f8=summary[-1];f1=summary[0]
    lines=['BH0 — local Coda team descriptive data reanalysis',
           'Inputs match Dryad published SHA-256. README definitions read on landing page; original README download unavailable.',
           f"Checks: {sum(checks.values())}/{len(checks)} passed.",
           f"3A descriptive row means: in-sheet {a_stats['in sheet']['mean']:.6f} mN, in-bundle {a_stats['in bundle']['mean']:.6f} mN.",
           f"Ratio of group means: {results['3A']['group_mean_ratio_sheet_over_bundle']:.6f}. This is not a paired sample ratio.",
           '3A has 15 unlabeled observations/condition. No claim of 15 independent samples; no inferential test.',
           f"3B count 1: {f1['force_mean_mN']:.6f} +/- {f1['force_sd_mN']:.6f} mN (sample SD across 3 actuators).",
           f"3B count 8: {f8['force_mean_mN']:.6f} +/- {f8['force_sd_mN']:.6f} mN (sample SD across 3 actuators).",
           f"Mean within-actuator 8/1 ratio: {f8['relative_mean']:.6f} +/- {f8['relative_sd']:.6f} (sample SD).",
           f"3B relative formula maximum absolute error: {ratio_error:.3g}.",
           'Engineering inference: force increases strongly across the tested range, but samples differ and one falls slightly from seven to eight tissues.',
           'Model tissue count and measured actuator force separately; do not assume every added strand contributes an identical force.',
           'Keep culture geometry/transport and mechanical transmission as separate design variables. These force CSVs do not identify oxygen limitation.',
           'No extrapolation to whole-body strength, grip force, sustained operation, human donors or autonomous motion.',
           'Reproduce offline: python analyze.py --out results_recheck (requires matplotlib; frozen inputs must match).',
           'This is arithmetic/data consistency checking, not independent experimental replication.']
    (out/'report.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    receipt={'executed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'python':sys.version,'platform':platform.platform(),
             'freeze_sha256':sha(freeze_path),'input_sha256':inputs(),'outputs_sha256':{p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()}}
    (out/'execution_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print('\n'.join(lines))
    if not all(checks.values()):raise SystemExit(2)
if __name__=='__main__':main()
