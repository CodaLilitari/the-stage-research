"""Small independent heat-flow reference. All cases synthetic; stdlib only."""
from fractions import Fraction as F
import hashlib
import json
import math
from pathlib import Path

def steady(a,b,r,P,J,ambient,reservoir,convection_resistance):
    """Solve in heat-flow variables, not by the Fable-requested nodal matrix."""
    c=convection_resistance
    for name,value in (("a",a),("P",P),("J",J),("ambient",ambient),("reservoir",reservoir)):
        if not math.isfinite(value): raise ValueError(name+" must be finite")
    if a<0 or P<0 or J<0: raise ValueError("Negative resistance/source outside reference")
    for name,value in (("b",b),("r",r)):
        if math.isnan(value) or value<=0: raise ValueError(name+" must be positive or +infinity")
    if math.isnan(c) or c<0 or (math.isfinite(b) and c>b):
        raise ValueError("Invalid convection resistance")
    a,P,J,ambient,reservoir=map(lambda x:F(str(x)),(a,P,J,ambient,reservoir))
    front_open=math.isfinite(b)
    rear_open=math.isfinite(r)
    if not front_open and not rear_open:
        return {"status":"no_finite_steady_state" if P+J>0 else "nonunique"}
    if front_open: b=F(str(b))
    if rear_open: r=F(str(r))
    if math.isfinite(c): c=F(str(c))
    if not rear_open:
        front=P+J
        rear=F(0)
        S=ambient+b*front
        H=S+a*P
    elif not front_open:
        front=F(0)
        rear=P+J
        H=reservoir+r*rear
        S=H+a*J
    else:
        front=((reservoir-ambient)+r*(P+J)+a*J)/(a+b+r)
        rear=P+J-front
        S=ambient+b*front
        H=S+a*(front-J)
    surface=ambient+c*front if front_open else None
    return {"status":"unique","H":H,"S":S,"surface":surface,"front":front,
            "rear":rear,"balance":P+J-front-rear}

def nominal(stack,body_power,blocked_rear=False):
    A=F("0.01")
    thickness={"H1":F("0.0005"),"H2":F("0.001"),"H3":F("0.002")}[stack]
    a=thickness/(F(".27")*A)+F(".00005")/(2*F(".20")*A)+F(".0002")/A
    c=1/(F(8)*A)
    x=steady(a,a+c,math.inf if blocked_rear else F(2),F(str(body_power)),F(".1"),25,25,c)
    x.update({"stack":stack,"a":a,"b":a+c,"convection_resistance":c,
              "body_power":F(str(body_power)),"sensor_power":F(".1"),
              "rear_blocked":blocked_rear})
    return x

def one_node(initial,bath,power,resistance,capacity,time):
    for x in (initial,bath,power,capacity,time):
        if not math.isfinite(x): raise ValueError("Nonfinite scalar input")
    if capacity<=0 or time<0 or power<0 or math.isnan(resistance) or resistance<=0:
        raise ValueError("Invalid scalar input")
    if math.isinf(resistance): return initial+power*time/capacity
    equilibrium=bath+power*resistance
    return initial+(equilibrium-initial)*(-math.expm1(-time/(resistance*capacity)))

def two_insulated(t1,t2,c1,c2,conductance,time):
    if not all(math.isfinite(x) for x in (t1,t2,c1,c2,conductance,time)):
        raise ValueError("Nonfinite two-node input")
    if c1<=0 or c2<=0 or conductance<0 or time<0: raise ValueError("Invalid two-node input")
    mean=(c1*t1+c2*t2)/(c1+c2)
    difference=(t1-t2)*math.exp(-conductance*(1/c1+1/c2)*time)
    return mean+c2*difference/(c1+c2),mean-c1*difference/(c1+c2)

def backward_euler(initial,bath,power,resistance,capacity,time,steps):
    one_node(initial,bath,power,resistance,capacity,time)  # input admission only
    if not isinstance(steps,int) or isinstance(steps,bool) or steps<=0:
        raise ValueError("steps must be positive integer")
    dt=time/steps
    g=0 if math.isinf(resistance) else 1/resistance
    temperature=initial
    net_energy=0.0
    for _ in range(steps):
        temperature=(capacity*temperature+dt*(power+g*bath))/(capacity+dt*g)
        net_energy+=dt*(power-g*(temperature-bath))
    return {"T":temperature,"energy_residual":capacity*(temperature-initial)-net_energy}

if __name__=="__main__":
    here=Path(__file__).resolve().parent
    output=here/"reference_results.json"
    if output.exists(): raise SystemExit("Refusing to overwrite prior reference results")
    rows=[]
    for stack in ("H1","H2","H3"):
        for power,blocked in ((1,False),(5,False),(10,False),(5,True)):
            x=nominal(stack,power,blocked)
            x["front_exact"]=str(x["front"])
            rows.append({k:float(v) if isinstance(v,F) else v for k,v in x.items()})
    exact=one_node(20,20,3,2,10,20)
    convergence=[]
    for steps in (20,40,80):
        x=backward_euler(20,20,3,2,10,20,steps)
        convergence.append({"steps":steps,"dt_s":20/steps,"T_C":x["T"],
                            "abs_error_K":abs(x["T"]-exact),"energy_residual_J":x["energy_residual"]})
    record={"contract":"T0-HYP-1","status":"executed_independent_synthetic_reference",
            "fable_response_read":False,"physical_validation":False,"rows":rows,
            "one_node_exact_C":exact,"backward_euler":convergence,
            "two_insulated_t_1_2_s":two_insulated(30,10,2,3,1,1.2),
            "source_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    output.write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"rows":len(rows),"output":str(output),"one_node_exact_C":exact,
                      "max_energy_residual_W":max(abs(x["balance"]) for x in rows),
                      "backward_euler":convergence}))
