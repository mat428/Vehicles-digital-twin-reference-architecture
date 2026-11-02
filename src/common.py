import math
import numpy as np

def wrap(x):return math.atan2(math.sin(x),math.cos(x))
def track(name,L,spacing_L=.05):
    theta=np.linspace(0,2*np.pi,4001)
    if name=='circle':x=8*np.sin(theta);y=8*(1-np.cos(theta))
    elif name=='ellipse':x=10*np.sin(theta);y=6*(1-np.cos(theta))
    elif name=='wavy':
        r=8*(1+.15*np.cos(3*theta));x=r*np.sin(theta);y=9.2-r*np.cos(theta)
    else:raise ValueError(name)
    arc=np.r_[0,np.cumsum(np.hypot(np.diff(x),np.diff(y)))];length=arc[-1];sample=np.arange(0,length,spacing_L)
    points=np.column_stack([np.interp(sample,arc,x),np.interp(sample,arc,y)])*L
    tangent=np.roll(points,-1,axis=0)-np.roll(points,1,axis=0);heading=np.arctan2(tangent[:,1],tangent[:,0])
    return dict(points=points,heading=heading,spacing=spacing_L*L,length=length*L)
def nearest(state,path,previous):
    points=path['points'];n=len(points);ids=np.arange(max(0,previous-8),previous+60);local=points[ids%n]
    q=int(np.argmin(np.sum((local-state[:2])**2,axis=1)));index=int(ids[q]);d=state[:2]-local[q];yaw=path['heading'][index%n]
    error=-math.sin(yaw)*d[0]+math.cos(yaw)*d[1]
    return index,float(error)
def control(state,path,previous,L,cfg):
    index,_=nearest(state,path,previous);new=max(previous,index)
    j=(new+round(cfg['lookahead_wheelbases']*L/path['spacing']))%len(path['points']);d=path['points'][j]-state[:2]
    alpha=wrap(math.atan2(d[1],d[0])-state[2]);delta=math.atan2(2*L*math.sin(alpha),max(float(np.linalg.norm(d)),.05*L))
    return float(np.clip(delta,-cfg['steering_limit_rad'],cfg['steering_limit_rad'])),new

def propagate(state,delta,dt,L,speed_target):
    s=state.copy();r=s[3]*math.tan(delta)/L;mid=s[2]+r*dt/2
    s[0]+=s[3]*math.cos(mid)*dt;s[1]+=s[3]*math.sin(mid)*dt;s[2]=wrap(s[2]+r*dt)
    # Measured speed is corrected; between measurements relax gently toward target.
    s[3]+=(speed_target-s[3])*min(dt/.2,1);return s

def correct(state,measurement,gain):
    out=state+gain*(measurement-state);out[2]=wrap(state[2]+gain*wrap(measurement[2]-state[2]));return out
