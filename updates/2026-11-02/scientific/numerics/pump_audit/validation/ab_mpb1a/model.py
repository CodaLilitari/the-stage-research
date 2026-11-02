# SPDX-License-Identifier: Apache-2.0
"""Synthetic prescribed-flow finite-site amount transport, AB-MPB1A.

No empirical fitting, viscosity/pumping layer, clipping, network or file I/O.
The callback integration entry is for explicit wrong-operator witnesses;
only solve() selects the admitted model operator.
"""
from dataclasses import dataclass
import math
MAX_STEPS=200000
def number(x,name,positive=False):
    if isinstance(x,bool) or not isinstance(x,(int,float)):
        raise ValueError(name+' must be a finite number')
    try:valid=math.isfinite(x)
    except OverflowError:valid=False
    if not valid or x<0 or (positive and x==0):raise ValueError(name+' is outside its finite domain')
    return float(x)
@dataclass(frozen=True)
class Config:
    reservoir_volume: float=2.0
    channel_volume: float=1.0
    wall_volume: float=.5
    channel_cells: int=3
    return_volume: float=0.0
    return_cells: int=0
    flow: float=.4
    exchange: float=.3
    kon: float=.5
    koff: float=.2
    sink: float=.15
    def __post_init__(self):
        for name in ('reservoir_volume','channel_volume','wall_volume'):number(getattr(self,name),name,True)
        for name in ('return_volume','flow','exchange','kon','koff','sink'):number(getattr(self,name),name)
        for name,lower in (('channel_cells',1),('return_cells',0)):
            value=getattr(self,name)
            if type(value) is not int or not lower<=value<=16:raise ValueError('Invalid '+name)
        if (self.return_cells==0)!=(self.return_volume==0):raise ValueError('Return cells and positive volume must occur together')
@dataclass(frozen=True)
class Model:
    config: Config
    volumes: tuple
    wall_volumes: tuple
    @property
    def n(self):return len(self.volumes)
    @property
    def size(self):return 3*self.n+len(self.wall_volumes)+1
def build(c):
    return Model(c,(c.reservoir_volume,)+(c.channel_volume/c.channel_cells,)*c.channel_cells+((c.return_volume/c.return_cells,)*c.return_cells if c.return_cells else ()),(c.wall_volume/c.channel_cells,)*c.channel_cells)
def checked_state(m,y):
    if len(y)!=m.size:raise ValueError('State size does not match layout')
    z=tuple(number(x,'state amount') for x in y)
    try:totals=inventories(m,z)
    except OverflowError:raise ValueError('Inventory exceeds finite arithmetic') from None
    if not all(math.isfinite(x) for x in totals):raise ValueError('Nonfinite total inventory')
    return z
def state(m,free,occupied,empty,wall,consumed=0):
    if any(len(x)!=n for x,n in ((free,m.n),(occupied,m.n),(empty,m.n),(wall,len(m.wall_volumes)))):raise ValueError('Species layout mismatch')
    return checked_state(m,tuple(free)+tuple(occupied)+tuple(empty)+tuple(wall)+(consumed,))
def uniform_state(m,free_concentration=.8,site_concentration=1,bound_fraction=.3,wall_concentration=0):
    for name,x in (('free concentration',free_concentration),('site concentration',site_concentration),('wall concentration',wall_concentration),('bound fraction',bound_fraction)):number(x,name)
    if bound_fraction>1:raise ValueError('Occupancy fraction exceeds one')
    return state(m,[v*free_concentration for v in m.volumes],[v*site_concentration*bound_fraction for v in m.volumes],[v*site_concentration*(1-bound_fraction) for v in m.volumes],[v*wall_concentration for v in m.wall_volumes])
def inventories(m,y):return (math.fsum(y[:2*m.n]+y[3*m.n:]),math.fsum(y[m.n:3*m.n]))
def _rhs(m,y):
    n=m.n;c=m.config;d=[0.0]*m.size
    for block in (0,n,2*n):
        for i,v in enumerate(m.volumes):
            flux=c.flow*y[block+i]/v;j=(i+1)%n
            d[block+i]-=flux;d[block+j]+=flux
    for i,v in enumerate(m.volumes):
        reaction=c.kon*(y[i]/v)*y[2*n+i]-c.koff*y[n+i]
        d[i]-=reaction;d[n+i]+=reaction;d[2*n+i]-=reaction
    conductance=c.exchange/c.channel_cells
    for j,w in enumerate(m.wall_volumes):
        channel=1+j;wall=3*n+j
        flux=conductance*(y[channel]/m.volumes[channel]-y[wall]/w)
        consumed=c.sink*y[wall]
        d[channel]-=flux;d[wall]+=flux-consumed;d[-1]+=consumed
    return d
def rhs(m,y):return tuple(_rhs(m,checked_state(m,y)))
def exit_bound(m,y):
    oxygen,sites=inventories(m,y);c=m.config;g=c.exchange/c.channel_cells;rates=[]
    for i,v in enumerate(m.volumes):
        adv=c.flow/v;wall=g/v if 1<=i<=c.channel_cells else 0
        rates.extend((adv+c.kon*sites/v+wall,adv+c.koff,adv+c.kon*oxygen/v))
    rates.extend(g/w+c.sink for w in m.wall_volumes)
    if not all(math.isfinite(x) for x in rates):raise ValueError('Exit-rate bound exceeds finite arithmetic')
    return max(rates)
def integrate(m,y,duration,dt,operator=None):
    duration=number(duration,'duration');dt=number(dt,'requested dt',True);y=checked_state(m,y)
    initial=inventories(m,y);rate=exit_bound(m,y)
    result={'amounts':y,'steps':0,'actual_dt':0.0,'exit_bound':rate,'minimum_seen':min(y),'max_oxygen_error':0.0,'max_site_error':0.0,'operator':'standard' if operator is None else 'custom_not_admitted'}
    if duration==0:return result
    cap=min(dt,.9/rate) if rate>0 else dt
    ratio=duration/cap
    if not math.isfinite(ratio) or ratio>MAX_STEPS:raise ValueError('Requested workload exceeds 200000 steps')
    steps=max(1,math.ceil(ratio));h=duration/steps
    fn=_rhs if operator is None else operator
    def inspect(z):
        if any(not math.isfinite(x) for x in z):raise ArithmeticError('Nonfinite numerical state')
        minimum=min(z);result['minimum_seen']=min(result['minimum_seen'],minimum)
        if minimum < -1e-14:raise ArithmeticError('Negative numerical amount; no clipping performed')
        totals=inventories(m,z)
        result['max_oxygen_error']=max(result['max_oxygen_error'],abs(totals[0]-initial[0]))
        result['max_site_error']=max(result['max_site_error'],abs(totals[1]-initial[1]))
    for _ in range(steps):
        d=fn(m,y);first=tuple(a+h*b for a,b in zip(y,d));inspect(first)
        d2=fn(m,first);y=tuple(.5*a+.5*(b+h*c) for a,b,c in zip(y,first,d2));inspect(y)
    result.update(amounts=y,steps=steps,actual_dt=h)
    return result
def solve(m,y,duration,dt):return integrate(m,y,duration,dt)
