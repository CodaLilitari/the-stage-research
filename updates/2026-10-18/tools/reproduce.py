"""New public reproduction adapters; not the historical execution harnesses.
No computation by default. Explicit --run, budget and a NEW external output
directory are required. No network or reading from unrelated local directories.
These adapters are statically checked, not scientifically rerun during curation.
"""
import argparse,hashlib,importlib.util,json,os,shutil,socket,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[name]='1'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,obj):
    text=json.dumps(obj,indent=2,allow_nan=False)+'\n'
    temp=p.with_suffix(p.suffix+'.tmp');temp.write_text(text,encoding='utf-8');os.replace(temp,p)
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m
def copy_files(src,dest,names):
    dest.mkdir(parents=True,exist_ok=True)
    for name in names:
        (dest/name).parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(src/name,dest/name)
class Guard:
    def __init__(self,out,cap,seconds):
        self.out,self.cap,self.seconds=out,cap,seconds;self.start=time.monotonic();self.events=[]
    def tick(self,**ignored):
        if time.monotonic()-self.start>self.seconds:raise TimeoutError('Explicit wall budget exhausted')
        total=0
        for p in self.out.rglob('*'):
            try:
                if p.is_file():total+=p.stat().st_size
            except FileNotFoundError:
                # A writer may atomically replace its .tmp file between listing
                # and stat. Other I/O errors still stop the watchdog.
                continue
        if total>250*1024**2:raise RuntimeError('250 MiB output budget exhausted')
    def evaluate(self,label,fn):
        self.tick()
        if len(self.events)>=self.cap:raise RuntimeError('Explicit evaluation budget exhausted')
        item=dict(number=len(self.events)+1,label=label,status='started');self.events.append(item);self.save()
        try:
            result=fn();item['status']='completed';return result
        except SystemExit as e:
            if e.code in (None,0):item['status']='completed';return None
            item.update(status='failed',error='SystemExit: '+str(e.code));raise
        except BaseException as e:
            item.update(status='failed',error=type(e).__name__+': '+str(e));raise
        finally:self.save()
    def save(self):write(self.out/'PUBLIC_REPRODUCTION_LEDGER.json',dict(cap=self.cap,events=self.events,seconds=time.monotonic()-self.start))

def ab_ct0(out,guard):
    source=ROOT/'scientific/ab_ct0/source'
    model=load(source/'model.py','public_ab_model');analysis=load(source/'analysis.py','public_ab_analysis')
    cfg=read(source/'config.json');primary=read(source/'primary_cases.json');controls=read(source/'controls.json')
    reference=read(source/'saved_reference.json');saved={};(out/'profiles').mkdir()
    def solve(case,role):
        result=guard.evaluate(case['case_id']+':'+role,lambda:model.solve(case,cfg,guard.tick))
        saved[case['case_id']]=result;write(out/'profiles'/(case['case_id']+'.json'),result)
    def checked(name,value):
        write(out/(name+'.json'),value)
        if not value['passed']:raise ArithmeticError(name+' failed; preserved without retry')
    anchors=analysis.anchor_ids(primary)
    for c in controls:solve(c,'control')
    checked('controls_initial',analysis.check_controls(saved,primary,cfg,reference,False))
    for cid in sorted(anchors.values()):solve(next(c for c in primary if c['case_id']==cid),'primary_anchor')
    checked('controls_complete',analysis.check_controls(saved,primary,cfg,reference))
    for c in primary:
        if c['case_id'] not in saved:solve(c,'primary')
    checked('primary_checks',analysis.check_primary(saved,primary,cfg))
    selection=analysis.select_refinement(saved,primary,cfg);write(out/'refinement_selection.json',selection)
    for cid in selection['selected_case_ids']:
        base=next(c for c in primary if c['case_id']==cid)
        for i,(ny,nz) in enumerate(cfg['refinement_grids'],1):
            solve({**base,'case_id':cid+f'-R{i}','ny':ny,'nz':nz,'parent_case_id':cid},'refinement')
    write(out/'decisions.json',analysis.refined_decisions(saved,selection,cfg))

def nua(out,guard):
    module=ROOT/'scientific/nua_pf_kdata1'
    copy_files(module/'original/inputs',out/'inputs',['o2_offloading_exp.csv'])
    (out/'outputs').mkdir();(out/'notes').mkdir()
    write(out/'notes/fit_ledger.json',dict(budget_max_calls=12,calls_used=0,calls=[]))
    fit=load(module/'replay/fit_k.py','public_nua_fit')
    fit.BASE=str(out);fit.LEDGER=str(out/'notes/fit_ledger.json')
    upstream=fit.curve_fit
    class StopFit(BaseException):pass
    def counted(*a,**k):
        try:return guard.evaluate('curve_fit:'+a[0].__name__,lambda:upstream(*a,**k))
        except Exception as e:raise StopFit(str(e)) from e
    fit.curve_fit=counted
    fit.main()
    if any(x['status']!='completed' for x in guard.events):raise RuntimeError('An optimizer failed; no scientific acceptance')

def lily(out,guard,portable):
    source=ROOT/'scientific/lily_ab_lfr1/original'
    # Execute copied code so output cannot modify the historical artifacts.
    names=['benchmark.py','test_portable.py','GOLDEN_STATES.json','FROZEN_CASES.json','FREEZE.json','run_benchmark.py']
    copy_files(source,out/'source',names);sys.path.insert(0,str(out/'source'))
    import runpy
    if portable:
        sys.argv=[str(out/'source/test_portable.py')]
        guard.evaluate('portable_suite_with_198_point_subcases',lambda:runpy.run_path(sys.argv[0],run_name='__main__'))
    else:
        sys.argv=[str(out/'source/run_benchmark.py'),'--output',str(out/'results')]
        guard.evaluate('full_22_case_instrument_with_176_BE_mesh_runs',lambda:runpy.run_path(sys.argv[0],run_name='__main__'))

def red(out,guard):
    module=ROOT/'scientific/red_transport'
    names=['stage_transport.py','al1_scan.py','al1_config.json','al1_inputs.csv','al1_freeze.json']
    copy_files(module/'original',out/'source',names);sys.path.insert(0,str(out/'source'))
    scan=load(out/'source/al1_scan.py','public_red_al1')
    guard.evaluate('frozen_AL1_2520_configurations_17640_rows',scan.do_run)

def wren(out,guard):
    source=ROOT/'scientific/wren_linear/coda_recovery'
    copy_files(source,out/'source',['proposed_cases.json','recovery_candidate.py','wren_fixed_unexecuted.py'])
    sys.path.insert(0,str(out/'source'))
    candidate=load(out/'source/recovery_candidate.py','public_wren_recovery')
    sys.argv=[str(out/'source/recovery_candidate.py'),'--execute-reviewed','--output',str(out/'results')]
    # Candidate itself reserves exactly 16 method/case evaluations and persists
    # each result; outer invocation is explicitly not another science case.
    candidate.main()

def linear_adapter(out,guard):
    source=ROOT/'scientific/linear_adapter'
    names=['adapter.py','study.py','cases.json','tolerances.json',
      'pinned_sources/ab_ct0_model.py','pinned_sources/ab_ct0_config.json','pinned_sources/lily_benchmark.py']
    copy_files(source,out/'source',names)
    # The unchanged study owns order, early stopping, persistence and expected
    # fault semantics. Only source/output location and outer call accounting differ.
    module=load(out/'source/adapter.py','adapter')
    original=module.execute
    def counted(spec,heartbeat):
        return guard.evaluate(spec['attempt_id'],lambda:original(spec,heartbeat))
    module.execute=counted
    study=load(out/'source/study.py','public_linear_study')
    study.run(guard.tick)
    if len(guard.events)!=51:raise RuntimeError('Frozen 51-attempt accounting mismatch')

def kinetic_mapping(out,guard):
    source=ROOT/'scientific/kinetic_mapping'
    plan=read(source/'diagnostic_cases.json');expected=read(source/'expected_outputs.json')
    if len(plan['cases'])!=12 or plan['budget']['attempts_including_failures']!=12:
        raise RuntimeError('Frozen diagnostic case count changed')
    core=load(source/'analytic_functions.py','public_kinetic_functions')
    results=[]
    for case in plan['cases']:
        actual=guard.evaluate(case['id'],lambda:core.evaluate(case,plan['times_s']))
        checks=core.compare(actual,expected[case['id']]);passed=all(c['passed'] for c in checks)
        results.append(dict(id=case['id'],actual=actual,checks=checks,passed=passed))
        core.write_json(out/'results.json',results)
        if not passed:raise ArithmeticError('Preserved expected-output failure: '+case['id'])
    write(out/'summary.json',dict(case_records=len(results),checks=sum(len(r['checks']) for r in results),
      passed_checks=sum(c['passed'] for r in results for c in r['checks']),empirical_fits=0,integrations=0,
      scope='New public harness of exact extracted pure functions and twelve original records; not the historical execution'))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('study',choices=['ab-ct0','nua-fits','lily-portable','lily-full','red-al1','wren-recovery','linear-adapter','kinetic-mapping'])
    p.add_argument('--run',action='store_true');p.add_argument('--output',type=Path)
    p.add_argument('--max-evaluations',type=int);p.add_argument('--wall-seconds',type=int,default=600)
    a=p.parse_args();required={'ab-ct0':78,'nua-fits':12,'lily-portable':1,'lily-full':1,'red-al1':1,'wren-recovery':16,'linear-adapter':51,'kinetic-mapping':12}[a.study]
    if not a.run:
        print(json.dumps(dict(study=a.study,required_budget=required,status='plan_only',note='See REPRODUCING.md for internal case counts, retained failures and dependencies')));return
    if a.output is None or a.max_evaluations!=required or not 1<=a.wall_seconds<=1800:p.error('Supply a NEW --output, exact documented --max-evaluations and 1..1800 wall seconds')
    out=a.output.resolve()
    if out.is_relative_to(ROOT):p.error('Output must be outside the immutable release directory')
    out.mkdir(parents=True,exist_ok=False)
    verifier=load(ROOT/'verify_release.py','public_release_verifier');check=verifier.verify(ROOT)
    if not check['passed']:raise RuntimeError('Public source manifest verification failed: '+str(check['errors']))
    def no_network(*args,**kwargs):raise RuntimeError('Network disabled in public reproduction')
    socket.socket=no_network;socket.create_connection=no_network
    guard=Guard(out,required,a.wall_seconds)
    import threading
    done=threading.Event()
    def watchdog():
        while not done.wait(.1):
            try:guard.tick()
            except BaseException as exc:
                write(out/'STOP.json',dict(reason=str(exc),phase='watchdog'));os._exit(124)
    threading.Thread(target=watchdog,daemon=True).start()
    write(out/'REPRODUCTION_CONTEXT.json',dict(study=a.study,adapter='new public adapter; not historical execution',manifest_sha256=hashlib.sha256((ROOT/'MANIFEST.json').read_bytes()).hexdigest(),python=sys.version,budget=required,wall_seconds=a.wall_seconds))
    try:
        {'ab-ct0':ab_ct0,'nua-fits':nua,'lily-portable':lambda o,g:lily(o,g,True),'lily-full':lambda o,g:lily(o,g,False),'red-al1':red,'wren-recovery':wren,'linear-adapter':linear_adapter,'kinetic-mapping':kinetic_mapping}[a.study](out,guard)
    finally:done.set()
if __name__=='__main__':main()
