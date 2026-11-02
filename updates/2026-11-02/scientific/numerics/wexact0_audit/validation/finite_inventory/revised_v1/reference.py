"""FINITE-L0: synthetic linear oxygen AMOUNT network; stdlib only.

Units: amount umol, volume mL, time s, Q/G mL/s, rates 1/s.
Linear binding is unsaturated and is NOT a finite-site or tissue model.
No source-tree imports, API calls, or execution at import.
"""
from dataclasses import dataclass
import math


def nonnegative(x, name, *, positive=False):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        raise ValueError(f'{name} must be a finite number')
    if x < 0 or (positive and x == 0):
        raise ValueError(f'{name} has an invalid sign')


@dataclass(frozen=True)
class Config:
    reservoir_volume: float = 2.0
    channel_volume: float = 1.0
    wall_volume: float = .5
    channel_cells: int = 1
    return_volume: float = 0.0
    return_cells: int = 0
    flow: float = .4
    exchange: float = .3
    binding: float = .2
    release: float = .1
    sink: float = .3
    source: float = 0.0
    length_m: float = .25  # Metadata: total volumes and conductance set rates.

    def validate(self):
        for name in ('reservoir_volume','channel_volume','wall_volume','length_m'):
            nonnegative(getattr(self,name),name,positive=True)
        for name in ('flow','exchange','binding','release','sink','source','return_volume'):
            nonnegative(getattr(self,name),name)
        for name,lower in [('channel_cells',1),('return_cells',0)]:
            v=getattr(self,name)
            if type(v) is not int or not lower <= v <= 64:
                raise ValueError(f'Invalid {name}')
        if (self.return_cells == 0) != (self.return_volume == 0):
            raise ValueError('Return volume is positive exactly when return cells exist')


@dataclass(frozen=True)
class Model:
    config: Config
    labels: tuple
    liquid_volumes: tuple
    wall_volumes: tuple
    matrix: tuple  # (destination row, source column, coefficient per second)
    source: tuple  # Constant external amount input rates.

    def index(self,label):
        return self.labels.index(label)

    @property
    def maximum_exit_rate(self):
        diag=[0.0]*len(self.labels)
        for row,col,rate in self.matrix:
            if row == col: diag[row] += rate
        return max((-x for x in diag),default=0.0)


def build(cfg):
    cfg.validate()
    n=cfg.channel_cells
    liquid=[('R',cfg.reservoir_volume)]
    liquid += [(f'C{i}',cfg.channel_volume/n) for i in range(n)]
    if cfg.return_cells:
        liquid += [(f'D{i}',cfg.return_volume/cfg.return_cells) for i in range(cfg.return_cells)]
    wall=[(f'W{i}',cfg.wall_volume/n) for i in range(n)]
    labels=tuple([name+'.'+species for name,_ in liquid for species in ('free','bound')]
                 +[name+'.free' for name,_ in wall]+['loss'])
    idx={name:i for i,name in enumerate(labels)}
    coefficients={}

    def transfer(src,dst,rate):
        if rate == 0: return
        i,j=idx[src],idx[dst]
        coefficients[i,i]=coefficients.get((i,i),0.0)-rate
        coefficients[j,i]=coefficients.get((j,i),0.0)+rate

    # An amount leaves each fixed-volume liquid compartment as Q * amount/V.
    for k,(name,volume) in enumerate(liquid):
        next_name=liquid[(k+1)%len(liquid)][0]
        for species in ('free','bound'):
            transfer(name+'.'+species,next_name+'.'+species,cfg.flow/volume)
        transfer(name+'.free',name+'.bound',cfg.binding)
        transfer(name+'.bound',name+'.free',cfg.release)
    # Total wall conductance G is split across cells; each flux is G_j*(c_j-c_wj).
    for i in range(n):
        transfer(f'C{i}.free',f'W{i}.free',(cfg.exchange/n)/(cfg.channel_volume/n))
        transfer(f'W{i}.free',f'C{i}.free',(cfg.exchange/n)/(cfg.wall_volume/n))
        transfer(f'W{i}.free','loss',cfg.sink)
    source=[0.0]*len(labels)
    source[idx['R.free']]=cfg.source
    matrix=tuple((row,col,value) for (row,col),value in sorted(coefficients.items()) if value)
    return Model(cfg,labels,tuple(liquid),tuple(wall),matrix,tuple(source))


def initial_amounts(model, amounts):
    unknown=set(amounts)-set(model.labels)
    if unknown: raise ValueError(f'Unknown amount labels: {sorted(unknown)}')
    result=[]
    for label in model.labels:
        value=amounts.get(label,0.0)
        nonnegative(value,label)
        result.append(float(value))
    return tuple(result)


def rhs(model, amounts):
    derivative=list(model.source)
    for row,col,rate in model.matrix:
        derivative[row] += rate*amounts[col]
    return derivative


@dataclass(frozen=True)
class Solution:
    amounts: tuple
    time: float
    steps: int
    actual_dt: float
    minimum_seen: float


def solve(model, amounts, duration, dt):
    """Positivity-limited SSPRK2 in physical time; no negative-value clipping."""
    nonnegative(duration,'duration')
    nonnegative(dt,'dt',positive=True)
    if len(amounts) != len(model.labels): raise ValueError('State length differs from model')
    for value in amounts: nonnegative(value,'initial amount')
    state=tuple(float(v) for v in amounts)
    if duration == 0: return Solution(state,0.0,0,0.0,min(state))
    steps=math.ceil(duration/dt)
    if steps > 200000: raise ValueError('Bounded-reference step limit exceeded')
    h=duration/steps
    if h*model.maximum_exit_rate > 1+1e-14:
        raise ValueError('dt exceeds the explicit positivity bound; reduce dt')
    minimum=min(state)
    scale=max(1.0,math.fsum(state)+duration*math.fsum(model.source))
    for _ in range(steps):
        first=rhs(model,state)
        stage=[x+h*d for x,d in zip(state,first)]
        second=rhs(model,stage)
        new=tuple(.5*(x+z+h*d) for x,z,d in zip(state,stage,second))
        minimum=min(minimum,min(stage),min(new))
        if not all(math.isfinite(v) for v in new) or minimum < -1e-12*scale:
            raise ArithmeticError('Nonfinite/negative amount detected; no clipping performed')
        state=new
    return Solution(state,float(duration),steps,h,minimum)
