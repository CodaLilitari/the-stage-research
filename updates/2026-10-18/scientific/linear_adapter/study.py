"""Counted, persist-before-call AB-LA1 study. Invoked only by admitted supervisor."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,time,traceback
import adapter
HERE=Path(__file__).resolve().parent
def write(p,obj):
    temporary=p.with_suffix(p.suffix+'.tmp')
    temporary.write_text(json.dumps(obj,indent=2,sort_keys=True,allow_nan=False)+'\n',encoding='utf-8')
    temporary.replace(p)
def utc():return datetime.now(timezone.utc).isoformat()
def run(heartbeat):
    plan=json.loads((HERE/'cases.json').read_text());tol=json.loads((HERE/'tolerances.json').read_text())
    out=HERE/'run';out.mkdir(exist_ok=False);(out/'attempts').mkdir()
    ledger=dict(started_utc=utc(),status='running',planned_attempts=51,attempts=[])
    results={};assessments=[]
    def persist():write(out/'ledger.json',ledger)
    def attempt(spec):
        heartbeat()
        if len(ledger['attempts'])>=51:raise RuntimeError('51-attempt pre-call cap reached')
        if any(x['attempt_id']==spec['attempt_id'] for x in ledger['attempts']):raise RuntimeError('Duplicate attempt refused')
        entry=dict(attempt=len(ledger['attempts'])+1,attempt_id=spec['attempt_id'],input=spec,status='started',started_utc=utc())
        ledger['attempts'].append(entry);persist()
        path=out/'attempts'/(spec['attempt_id']+'.json')
        result=None;failure=None
        try:
            result=adapter.execute(spec,heartbeat)
            write(path,result)
            entry.update(status='production_completed',result_path=path.relative_to(out).as_posix(),result_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        except Exception as exc:
            failure=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc(),call_trace=getattr(exc,'adapter_trace',None))
            write(path,dict(input=spec,failure=failure))
            entry.update(status='production_exception',failure=failure,result_path=path.relative_to(out).as_posix(),result_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        finally:
            entry['finished_utc']=utc();persist()
        if failure:
            acceptable=spec['block']=='fault' and spec['fault'] in ('reverse_release','total_sink') and failure['type']=='ArithmeticError' and failure['message'] in (
              'Saturation bound failed; no clipping applied','Physical axial bracket failed','Segment conservation failed','Global conservation failed')
            assessment=dict(attempt_id=spec['attempt_id'],passed=acceptable,checks=[dict(name='expected_specific_physical_guard',passed=acceptable,failure=failure)])
        else:
            assessed=adapter.assess(spec,result,tol,results)
            if spec['block']=='fault':
                names={x['name'] for x in assessed['checks'] if not x['passed']}
                detected=bool(names & {'discrete_BE_path','discrete_BE_uptake','separate_total_and_bound_updates'})
                # Failure must be numerical discrimination, not a missing trace
                # or unrelated hydraulic bookkeeping issue.
                others=all(x['passed'] for x in assessed['checks'] if x['name'] not in ('discrete_BE_path','discrete_BE_uptake','separate_total_and_bound_updates'))
                assessment=dict(attempt_id=spec['attempt_id'],passed=detected and others,
                  checks=[dict(name='wrong_model_detected',passed=detected),dict(name='other_integrity_controls',passed=others)],wrong_model_assessment=assessed)
            else:
                assessment=dict(attempt_id=spec['attempt_id'],**assessed)
                results[spec['attempt_id']]={**assessed,'result':result}
        write(out/'attempts'/(spec['attempt_id']+'_assessment.json'),assessment)
        entry['acceptance_passed']=assessment['passed'];persist();assessments.append(assessment)
        if not assessment['passed']:raise ArithmeticError('Preserved verification failure: '+spec['attempt_id'])
        print(spec['attempt_id']+' '+entry['status']+' accepted',flush=True)
        heartbeat()
    try:
        positives=[s for s in plan['cases'] if s['block']!='fault']
        faults=[s for s in plan['cases'] if s['block']=='fault']
        if len(positives)!=47 or len(faults)!=4 or plan['planned_attempts']!=51:raise RuntimeError('Frozen plan count mismatch')
        for spec in positives:attempt(spec)
        conv=adapter.convergence(plan,results,tol);write(out/'convergence.json',conv)
        if not conv['passed']:raise ArithmeticError('Preserved positive convergence failure; mutants not run')
        for spec in faults:attempt(spec)
        ledger['status']='completed'
    except BaseException as exc:
        ledger.update(status='stopped_on_failure',error=type(exc).__name__+': '+str(exc))
        raise
    finally:
        ledger['finished_utc']=utc();persist()
        write(out/'summary.json',dict(status=ledger['status'],planned=51,attempted=len(ledger['attempts']),
          accepted=sum(a['passed'] for a in assessments),unattempted=[s['attempt_id'] for s in plan['cases'] if s['attempt_id'] not in {x['attempt_id'] for x in ledger['attempts']}],
          assessments=assessments,scientific_scope='Linear verification of actual production stepping; radial block separately specified; no empirical claim'))
