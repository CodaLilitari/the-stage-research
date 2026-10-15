"""Independent arithmetic and scoped adversarial checks of received FL1-R bytes."""
from pathlib import Path
import csv,gzip,hashlib,json,math,sys,tempfile
ROOT=Path(__file__).resolve().parent
BASE=ROOT/'received_first_leaf/first_leaf'
cfg=json.loads((BASE/'inputs/protocol.json').read_text())
with gzip.open(BASE/'inputs/evaluation_fixtures.jsonl.gz','rt') as f:fixtures=[json.loads(l) for l in f]
fx=fixtures[0];assert fx['seed']==10000
checks=[]
def check(name,ok,detail=None):checks.append(dict(name=name,passed=bool(ok),detail=detail))
freeze=json.loads((BASE/'inputs/evaluation_freeze.json').read_text())
for name,sha in freeze['hashes'].items():
    check('evaluation freeze '+name,hashlib.sha256((BASE/name).read_bytes()).hexdigest()==sha)

max_errors={k:0. for k in ['position','velocity','distance','velocity_mse','body_model_error','sensor']}
count=0
for profile,profile_cfg in cfg['profiles'].items():
    receipts={(r['seed'],r['algorithm']):r for r in map(json.loads,(BASE/f'results/evaluation_{profile}_runs.jsonl').read_text().splitlines())}
    with (BASE/f'results/evaluation_{profile}_episodes.csv').open(newline='') as f:
        summaries={(int(r['seed']),r['algorithm'],int(r['episode'])):r for r in csv.DictReader(f)}
    for algorithm in cfg['algorithms']:
        path=BASE/f'results/evaluation_{profile}_{algorithm}_witness.jsonl.gz'
        raw=gzip.decompress(path.read_bytes());records=list(map(json.loads,raw.splitlines()))
        check('witness hash '+profile+'/'+algorithm,hashlib.sha256(raw).hexdigest()==receipts[(fx['seed'],algorithm)]['trace_sha256'])
        check('witness denominator '+profile+'/'+algorithm,len(records)==480)
        for ep in range(6):
            segment=records[ep*80:(ep+1)*80]
            is_b=cfg['body_schedule'][ep]=='B' and profile_cfg['change']
            mapping=fx['mapping_B'] if is_b else fx['mapping_A']
            gx,gy=(cfg['dynamics']['gain_B_x'],cfg['dynamics']['gain_B_y']) if is_b else (cfg['dynamics']['gain_A'],)*2
            cardinal=[[gx,0],[0,gy],[-gx,0],[0,-gy]]
            vectors=[cardinal[i] for i in mapping]+[[0,0]]
            p=[0.,0.];v=[0.,0.];states=[(p[:],v[:])];distances=[]
            for tick,r in enumerate(segment):
                assert (r['ep'],r['tick'])==(ep,tick)
                a=r['executed'];v=[.75*v[j]+vectors[a][j] for j in (0,1)];p=[p[j]+.1*v[j] for j in (0,1)]
                states.append((p[:],v[:]));d=math.hypot(p[0]-fx['goals'][ep][0],p[1]-fx['goals'][ep][1]);distances.append(d)
                errors={'position':max(abs(p[j]-r['true_p'][j]) for j in (0,1)),
                        'velocity':max(abs(v[j]-r['true_v'][j]) for j in (0,1)),
                        'distance':abs(d-r['distance']),
                        'velocity_mse':abs(sum((r['predicted_v'][j]-v[j])**2 for j in (0,1))/2-r['velocity_mse']),
                        'body_model_error':abs(sum(math.hypot(r['estimated_b'][i][0]-vectors[i][0],r['estimated_b'][i][1]-vectors[i][1]) for i in range(4))/4-r['body_model_error'])}
                source=max(0,tick-profile_cfg['delay']);sp,sv=states[source];noise=fx['unit_noise'][ep][source];scale=int(profile_cfg['noise'])
                errors['sensor']=max([abs(r['observation']['p'][j]-(sp[j]+scale*.01*noise[j])) for j in (0,1)]+[abs(r['observation']['v'][j]-(sv[j]+scale*.03*noise[j+2])) for j in (0,1)])
                assert r['sample_tick']==r['observation']['tick']==source
                for k,e in errors.items():max_errors[k]=max(max_errors[k],e)
                count+=1
            saved=summaries[(fx['seed'],algorithm,ep)]
            check('independent distance metrics '+profile+'/'+algorithm+'/'+str(ep),max(abs(sum(distances)/80-float(saved['mean_distance'])),abs(sum(distances[:32])/32-float(saved['early32_distance'])))<1e-12)
check('all independent witness equations and sensor alignment',max(max_errors.values())<1e-12,max_errors)
check('witness transitions checked',count==15360,count)

sys.path.insert(0,str(BASE/'src'))
from interface import Gateway
import relay
def request(rid='a',action='k0'):
    return json.dumps(dict(schema='stage.action.v1',request_id=rid,session_id='qa',body_revision='planar-v1',sequence=0,observation_id='o0',expires_tick=2,action=action)).encode()
g=Gateway('qa');a=g.admit(request('a'));b=g.admit(request('b'));g.record_execution('a','k0');g.record_execution('b','k0')
two_pending={'two_same_sequence_admissions':a['dispatch'] and b['dispatch'],'sequence_after_both_executed':g.sequence}
g=Gateway('qa');g.admit(request('a'));g.admit(request('s','stop'));g.record_execution('a','k0')
post_stop={'stopped':g.stopped,'pending_command_executed_after_stop':g.cache['a']['execution_status']=='verified_simulator_transition'}
with tempfile.TemporaryDirectory(dir=ROOT,prefix='adversarial_relay_') as d:
    folder=Path(d);relay.init(folder,20001,'independent synthetic audit')
    before=(folder/'private_state.json').read_bytes();error=None
    try:relay.transact(folder,b'{"x":'+b'['*6000+b'0'+b']'*6000+b'}')
    except Exception as exc:error=type(exc).__name__
    malformed={'depth':6000,'bytes':12007,'exception':error,'state_unchanged':before==(folder/'private_state.json').read_bytes(),'lock_removed':not (folder/'writer.lock').exists()}
check('deep malformed request counterexample is observed',malformed['exception']=='RecursionError' and malformed['state_unchanged'] and malformed['lock_removed'])
findings=[{'id':'gateway-pending-sequence','severity':'medium for reuse; no effect on scored FL1','evidence':two_pending,'interpretation':'Standalone Gateway allows two distinct IDs at the same sequence before either is recorded, then records both. The serialized file relay does not expose this interleaving; reserve one pending slot or revalidate the sequence at commit before async reuse.'},
{'id':'gateway-stop-pending','severity':'medium for reuse; no effect on scored FL1','evidence':post_stop,'interpretation':'Standalone Gateway can record an already-admitted command after stop is latched. Its current relay commits admission/execution in one locked transaction, so this is a primitive contract limitation, not evidence of physical execution.'},
{'id':'relay-nested-json','severity':'low; fail-closed robustness','evidence':malformed,'interpretation':'A size-valid deeply nested request raises uncaught RecursionError rather than writing a rejection receipt. State remains unchanged and lock is released. Catch parser depth errors at the relay boundary in a future version.'}]
report=dict(scope='Independent equations over32 retained witnesses; code reuse explicitly limited to adversarial interface calls',checks=checks,passed=sum(c['passed'] for c in checks),total=len(checks),witness_transitions=count,max_errors=max_errors,findings=findings,initial_audit_correction='attempt01 was preserved. Depth1100 parsed on Python3.12 and received a proper rejection event; its inferred RecursionError description was wrong and was not reported externally. Depth6000 is the executed counterexample reported here, with an explicit diagnostic assertion.',source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
(ROOT/'independent_witness_report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['passed','total','witness_transitions','max_errors','findings']},indent=2))
if report['passed']!=report['total']:raise SystemExit(1)
