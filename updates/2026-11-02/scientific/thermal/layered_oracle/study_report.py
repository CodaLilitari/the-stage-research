"""Reduce independent traces and execute nine bounded synthetic cases."""
import importlib.util
import json
import math
from pathlib import Path
import sys
import time

def summarize(result,checkpoint_times=(0.,600.,900.,3600.)):
    trace=result["trace"]
    peaks={}
    for field in ("H","S","surface"):
        candidates=[x for x in trace if x[field] is not None]
        if candidates:
            row=max(candidates,key=lambda x:x[field])
            peaks[field]=dict(value_C=row[field],time_s=row["time"])
        else:
            peaks[field]=None
    indexed={x["time"]:x for x in trace}
    out={key:result[key] for key in ("steps","injected_J","exported_front_J","exported_rear_J",
                                     "final_stored_energy_change_J","max_energy_residual_abs_J",
                                     "energy_tolerance_J","events")}
    out.update(peaks=peaks,final=trace[-1],checkpoints=[indexed[t] for t in checkpoint_times if t in indexed],
               missing_checkpoint_times_s=[t for t in checkpoint_times if t not in indexed],
               physical_validation=False)
    return out

if __name__=="__main__":
    here=Path(__file__).resolve().parent
    output=here/"study_results.json"
    if output.exists(): raise SystemExit("Refusing to overwrite study results")
    spec=importlib.util.spec_from_file_location("rc_transient",here/"rc_transient.py")
    model=importlib.util.module_from_spec(spec);sys.modules[spec.name]=model;spec.loader.exec_module(model)
    start=time.perf_counter()
    rows=[]
    for stack in ("H1","H2","H3"):
        p=model.nominal(stack)
        for name,loss,sensor in (("intact_sensor_on",False,.1),("rear_loss_sensor_on",True,.1),("rear_loss_sensor_off",True,0.)):
            gr=0. if loss else .5
            segments=[dict(duration=600.,p=5.,j=sensor),
                      dict(duration=300.,p=5.,j=sensor,gr=gr),
                      dict(duration=2700.,p=0.,j=sensor,gr=gr)]
            result=model.simulate(p,(25.,25.),segments,1.)
            row=summarize(result)
            row.update(case=name,stack=stack,dt_s=1.,parameters=p.__dict__,segments=segments)
            wanted={0.,599.,600.,601.,899.,900.,901.,3600.}
            wanted.update(x["time_s"] for x in row["peaks"].values() if x is not None)
            row["stored_samples"]=[x for x in result["trace"] if x["time"] in wanted or x["time"]%60==0]
            if row["max_energy_residual_abs_J"]>row["energy_tolerance_J"]:
                raise RuntimeError("Predeclared energy criterion failed: "+stack+" "+name)
            rows.append(row)

    # Independent one-node closed-form and coupled eigenmode targets.
    p=model.Parameters(ch=10.,cs=7.,g=0.,ga=1.,gr=.5,ambient=20.,reservoir=20.,rconv=.5)
    exact=26-6/math.e
    one=[]
    for dt in (1.,.5,.25):
        run=model.simulate(p,(20.,20.),[dict(duration=20.,p=3.,j=0.)],dt)
        one.append(dict(dt_s=dt,H_C=run["trace"][-1]["H"],absolute_error_K=abs(run["trace"][-1]["H"]-exact)))
    p2=model.Parameters(ch=1.,cs=1.,g=1.,ga=1.,gr=1.,ambient=0.,reservoir=0.,rconv=.5)
    expectedH=(math.exp(-1)+math.exp(-3))/2
    expectedS=(math.exp(-1)-math.exp(-3))/2
    coupled=[]
    for dt in (.1,.05,.025):
        run=model.simulate(p2,(1.,0.),[dict(duration=1.,p=0.,j=0.)],dt)
        last=run["trace"][-1]
        coupled.append(dict(dt_s=dt,H=last["H"],S=last["S"],
                            maximum_error_K=max(abs(last["H"]-expectedH),abs(last["S"]-expectedS))))
    p3=model.nominal("H1")
    seg=[dict(duration=600.,p=5.,j=.1),dict(duration=300.,p=5.,j=.1,gr=0.),dict(duration=2700.,p=0.,j=.1,gr=0.)]
    traces=[model.simulate(p3,(25.,25.),seg,dt)["trace"] for dt in (1.,.5,.25)]
    diffs=[]
    for coarse,fine in zip(traces,traces[1:]):
        diffs.append(max(abs(x[k]-fine[2*i][k]) for i,x in enumerate(coarse) for k in ("H","S")))
    result=dict(model="T0-LUMP2-1",contract_relation="Same T0-HYP-1 steady resistances; coarse redistributed storage.",
                physical_validation=False,api_calls=0,fable_response_read=False,case_count=len(rows),
                rows=rows,one_node_exact_H_C=exact,one_node_refinement=one,
                coupled_exact_H=expectedH,coupled_exact_S=expectedS,coupled_refinement=coupled,
                rear_loss_temporal_difference_K=diffs,
                trace_convention="p,j and flux at time t describe the step ending at t; events hold new segment sources at t.",
                trace_retention="All time steps evaluated; 60-second samples, event neighbors, peaks and final states persisted.",
                elapsed_seconds=time.perf_counter()-start)
    output.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps(dict(cases=len(rows),elapsed_seconds=result["elapsed_seconds"],
                          max_energy_residual_J=max(x["max_energy_residual_abs_J"] for x in rows),
                          one_node=one,coupled=coupled,rear_loss_temporal_difference_K=diffs)))
