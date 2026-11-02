"""Fixed map/planner and command-authority rules for the focused extension."""
import math
import numpy as np
from shapely.geometry import box
import common
from demo import CFG
from pilot_obstacles import footprint

VERSION = 'focused-extension-v1'
EXPIRY_NS = 80_000_000


def make_spec(L, task, halfwidth=4.):
    return dict(version=VERSION, kind=task, wheelbase_m=L, road_halfwidth_m=halfwidth*L,
                obstacle_bounds=[27*L, (-halfwidth if task=='blocked' else -.6)*L,
                                 29*L, (halfwidth if task=='blocked' else .6)*L],
                goal_x_m=55*L, stop_x_m=20*L, clearance_required_m=.25*L,
                expiry_wall_ms=80., obstacle_source='known static geometric map',
                interpolation='linear centre, shortest yaw, rotational swept allowance')


def make_plan(spec, dimensions, allow_detour=True):
    L=spec['wheelbase_m'];length,width=dimensions
    x=np.arange(0,62.001,.05)*L
    candidates=[]
    obstacle=box(*spec['obstacle_bounds'])
    for offset in ([0.,1.,-1.,1.5,-1.5,2.,-2.,2.5,-2.5] if allow_detour else [0.]):
        smooth=lambda u:10*u**3-15*u**4+6*u**5
        y=offset*L*(smooth(np.clip((x/L-10)/12,0,1))-smooth(np.clip((x/L-34)/12,0,1)))
        heading=np.arctan2(np.gradient(y),np.gradient(x))
        curvature=np.gradient(heading)/np.hypot(np.gradient(x),np.gradient(y))
        clear=min(footprint([a,b,h],length,width).distance(obstacle)
                  for a,b,h in zip(x[::4],y[::4],heading[::4]))
        edge=min(spec['road_halfwidth_m']-abs(b)-abs(math.sin(h))*length/2-abs(math.cos(h))*width/2
                 for b,h in zip(y,heading))
        valid=(max(abs(curvature))*L<=math.tan(CFG['steering_limit_rad'])*.8
               and clear>=.4*L and edge>=.25*L)
        candidates.append(dict(offset_L=offset,clearance_m=clear,road_margin_m=edge,valid=bool(valid)))
        if valid:
            return dict(points=np.column_stack([x,y]),heading=heading,spacing=.05*L,
                        length=float(np.hypot(np.diff(x),np.diff(y)).sum())),False,candidates
    return dict(points=np.column_stack([x,x*0]),heading=x*0,spacing=.05*L,length=62*L),True,candidates


def decide(state,previous,path,spec,cruise,must_stop):
    delta,index=common.control(np.asarray(state),path,previous,spec['wheelbase_m'],CFG)
    speed=cruise
    if must_stop:
        remaining=spec['stop_x_m']-state[0]
        scale=math.sqrt(spec['wheelbase_m']/CFG['f1tenth_wheelbase_m'])
        speed=min(cruise,max(0.,remaining*1.2/scale)) if remaining>=.2*spec['wheelbase_m'] else 0.
    return dict(delta=float(delta),index=int(index),speed=float(speed))


def accept_reply(reply,last_sequence,now_ns):
    return reply['sequence']>last_sequence and reply['source_wall_ns']<=now_ns


def arbitrate(command,now_ns,policy,latched=False):
    expired=now_ns-command['source_wall_ns']>EXPIRY_NS
    latch=latched or (expired and policy=='expire_stop')
    return command['delta'],0. if latch else command['speed'],latch,expired
