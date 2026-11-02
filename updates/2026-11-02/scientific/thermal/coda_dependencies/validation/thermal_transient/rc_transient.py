"""T0-LUMP2-1: independent nonliving synthetic two-node RC model; stdlib only."""
from dataclasses import dataclass, replace
import math

MAX_STEPS=100_000
P_MAX_W=10.
J_MAX_W=.2

def finite_number(value,name):
    if type(value) not in (int,float) or not math.isfinite(value):
        raise ValueError(name+" must be a finite non-Boolean number")
    return float(value)

@dataclass(frozen=True)
class Parameters:
    ch: float
    cs: float
    g: float
    ga: float
    gr: float
    ambient: float
    reservoir: float
    rconv: float

    def __post_init__(self):
        for name in self.__dataclass_fields__:
            object.__setattr__(self,name,finite_number(getattr(self,name),name))
        if self.ch<=0 or self.cs<=0: raise ValueError("Capacities must be positive")
        if min(self.g,self.ga,self.gr,self.rconv)<0: raise ValueError("Negative passive parameter")
        if self.ga*self.rconv>1.+1e-12: raise ValueError("Convection resistance exceeds entire front branch")

def nominal(stack):
    if stack not in ("H1","H2","H3"): raise ValueError("Unknown reference stack")
    thick={"H1":.0005,"H2":.001,"H3":.002}[stack]
    area=.01
    a=thick/(.27*area)+.00005/(2*.20*area)+.0002/area
    c=1/(8*area)
    cs=1030*area*(2*thick)*1500+1420*area*.00005*1090
    return Parameters(ch=20.,cs=cs,g=1/a,ga=1/(a+c),gr=.5,ambient=25.,reservoir=25.,rconv=c)

def simulate(params,initial,segments,dt):
    """Backward Euler; each segment has constant bounded sources and optional rear conductance."""
    if not isinstance(params,Parameters): raise ValueError("Parameters required")
    dt=finite_number(dt,"dt")
    if dt<=0: raise ValueError("dt must be positive")
    if not isinstance(initial,(tuple,list)) or len(initial)!=2: raise ValueError("Two initial states required")
    H,S=[finite_number(v,"initial state") for v in initial]
    if not isinstance(segments,(list,tuple)) or not segments: raise ValueError("Nonempty segment list required")
    admitted=[]
    total_steps=0
    active=params
    total_duration=0.
    for segment in segments:
        if not isinstance(segment,dict) or set(segment)-{"duration","p","j","gr"}:
            raise ValueError("Unknown segment field")
        if not {"duration","p","j"}<=set(segment): raise ValueError("Missing segment field")
        duration=finite_number(segment["duration"],"duration")
        P=finite_number(segment["p"],"body power")
        J=finite_number(segment["j"],"sensor power")
        if duration<=0: raise ValueError("duration must be positive")
        if not 0<=P<=P_MAX_W or not 0<=J<=J_MAX_W: raise ValueError("Source outside bounded study envelope")
        if "gr" in segment: active=replace(active,gr=segment["gr"])
        ratio=duration/dt
        if not math.isfinite(ratio) or ratio>MAX_STEPS: raise ValueError("Step budget exceeded")
        count=math.ceil(ratio)
        total_steps+=count
        if total_steps>MAX_STEPS: raise ValueError("Step budget exceeded")
        total_duration+=duration
        if not math.isfinite(total_duration): raise ValueError("Nonfinite total horizon")
        admitted.append((duration,P,J,active,count))

    energy0=params.ch*H+params.cs*S
    if not math.isfinite(energy0): raise ValueError("Nonfinite initial energy")
    initial_H,initial_S=H,S
    time=0.
    injected=0.
    exported_front=0.
    exported_rear=0.
    absolute_throughput=0.
    maximum_residual=0.
    first=admitted[0][3]
    trace=[dict(time=0.,dt=0.,H=H,S=S,front=first.ga*(S-first.ambient),
                rear=first.gr*(H-first.reservoir),
                surface=first.ambient+first.rconv*first.ga*(S-first.ambient) if first.ga else None,
                p=admitted[0][1],j=admitted[0][2],energy_residual=0.)]
    events=[]
    previous_gr=params.gr
    for duration,P,J,active,count in admitted:
        start=time
        end=start+duration
        events.append(dict(time=start,before_state=[H,S],after_state=[H,S],
                           old_gr=previous_gr,new_gr=active.gr,p=P,j=J))
        previous_gr=active.gr
        for index in range(count):
            step=dt if index<count-1 else duration-(count-1)*dt
            if step<=0: raise ValueError("Nonpositive final step")
            A=active.ch/step+active.gr
            B=active.cs/step+active.ga
            determinant=A*B+active.g*(A+B)
            bh=active.ch*H/step+P+active.gr*active.reservoir
            bs=active.cs*S/step+J+active.ga*active.ambient
            new_H=(bh*(B+active.g)+active.g*bs)/determinant
            new_S=(bs*(A+active.g)+active.g*bh)/determinant
            front=active.ga*(new_S-active.ambient)
            rear=active.gr*(new_H-active.reservoir)
            if not all(math.isfinite(x) for x in (new_H,new_S,front,rear)):
                raise ValueError("Nonfinite numerical state/flux")
            H,S=new_H,new_S
            time=end if index==count-1 else start+(index+1)*dt
            injected+=step*(P+J)
            exported_front+=step*front
            exported_rear+=step*rear
            absolute_throughput+=step*(abs(P)+abs(J)+abs(front)+abs(rear))
            delta_energy=params.ch*(H-initial_H)+params.cs*(S-initial_S)
            residual=delta_energy-injected+exported_front+exported_rear
            maximum_residual=max(maximum_residual,abs(residual))
            trace.append(dict(time=time,dt=step,H=H,S=S,front=front,rear=rear,
                              surface=active.ambient+active.rconv*front if active.ga else None,
                              p=P,j=J,energy_residual=residual))
    return dict(model="T0-LUMP2-1",trace=trace,events=events,steps=total_steps,
                injected_J=injected,exported_front_J=exported_front,exported_rear_J=exported_rear,
                final_stored_energy_change_J=params.ch*(H-initial_H)+params.cs*(S-initial_S),
                max_energy_residual_abs_J=maximum_residual,
                energy_tolerance_J=1e-8+1e-10*absolute_throughput,
                physical_validation=False)
