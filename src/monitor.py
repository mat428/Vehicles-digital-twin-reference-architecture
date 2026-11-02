"""Source-aligned monitor accepting only measured packets and command history."""
import math
from collections import deque
from common import wrap

class Monitor:
    def __init__(self,cfg,model=None):
        self.commands=deque(maxlen=400)
        self.window=deque(maxlen=cfg['monitor_window_packets'])
        self.gain=1. if model is None else model['gain']
        self.threshold=cfg['yaw_residual_threshold_rad_s'] if model is None else model['threshold_rad_s']
        self.persistence=cfg['persistent_measurements'];self.count=0;self.alarm=False
    def advance(self,t,delta,dt,L):
        self.commands.append((t,t+dt,math.tan(delta)/L))
    def receive(self,source_t,measured_yaw,measured_speed,curvature_integral):
        self.window.append((source_t,measured_yaw,measured_speed,curvature_integral))
        if len(self.window)<self.window.maxlen:return [math.nan]*4+[0]
        first,last=self.window[0],self.window[-1];duration=last[0]-first[0]
        rate=wrap(last[1]-first[1])/duration
        integral=0.
        if not self.commands or self.commands[0][0]>first[0]+1e-8:
            self.count=0;self.alarm=False
            return [first[0],rate,math.nan,math.nan,0]
        for a,b in zip(self.window,list(self.window)[1:]):
            for start,end,curvature in self.commands:
                lo=max(start,a[0]);hi=min(end,b[0])
                if hi<=lo:continue
                vlo=a[2]+(b[2]-a[2])*(lo-a[0])/(b[0]-a[0])
                vhi=a[2]+(b[2]-a[2])*(hi-a[0])/(b[0]-a[0])
                integral+=(vlo+vhi)*.5*(hi-lo)*curvature
        reference=integral/duration
        residual=rate-self.gain*reference
        self.count=self.count+1 if abs(residual)>self.threshold else 0
        self.alarm=self.count>=self.persistence
        return [first[0],rate,reference,residual,int(self.alarm)]
