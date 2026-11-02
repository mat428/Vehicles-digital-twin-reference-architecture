"""Additional inspection plot; leaves frozen pilot batch outputs unchanged."""
import csv
import gzip
import json
import math
from pathlib import Path
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle

root=Path(sys.argv[1]);destination=Path(sys.argv[2])
fig,axes=plt.subplots(2,2,figsize=(12,7))
for row,backend in enumerate(['f1tenth','metadrive']):
    for column,kind in enumerate(['detour','blocked']):
        ax=axes[row,column]
        for speed in [1,2]:
            folder=next(root.glob(f'*_{backend}_{kind}_v{speed}'))
            spec=json.loads((folder/'scenario.json').read_text());L=spec['wheelbase_m']
            with gzip.open(folder/'physics.csv.gz','rt') as f:
                states=list(csv.DictReader(f))
            ax.plot([float(s['x'])/L for s in states],[float(s['y'])/L for s in states],label=f'speed case {speed}')
            selected=(min(states,key=lambda s:float(s['swept_clearance_m'])) if kind=='detour' else states[-1])
            x,y,yaw=[float(selected[k]) for k in ['x','y','yaw']]
            length,width=spec['dimensions_m'];c,s=math.cos(yaw),math.sin(yaw)
            vertices=[((x+c*a-s*b)/L,(y+s*a+c*b)/L) for a,b in
                      [(length/2,width/2),(-length/2,width/2),(-length/2,-width/2),(length/2,-width/2)]]
            ax.add_patch(Polygon(vertices,fill=False,edgecolor='C'+str(speed-1),lw=1.5))
            if speed==1:
                a,b,c,d=[v/L for v in spec['obstacle_bounds']]
                ax.add_patch(Rectangle((a,b),c-a,d-b,color='tomato',alpha=.5,label='known obstacle'))
                ax.axhline(4,color='gray',ls='--');ax.axhline(-4,color='gray',ls='--')
        ax.set(xlim=(8,47) if kind=='detour' else (15,32),ylim=(-4.5,4.5),
               title=backend+' / '+kind,xlabel='x / wheelbase',ylabel='y / wheelbase')
        ax.grid(alpha=.2);ax.legend(fontsize=8,loc='lower left')
fig.suptitle('Native pilot trajectories; rectangles show body at closest approach or final stop')
fig.tight_layout();fig.savefig(destination,dpi=170)
