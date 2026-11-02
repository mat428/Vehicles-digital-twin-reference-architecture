"""Presentation figures from frozen data; do not modify campaign payloads."""
import csv,gzip,json,math
from pathlib import Path
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root=Path(sys.argv[1]);out=Path(sys.argv[2]);cases=json.loads((root/'summary.json').read_text())['cases']
widthfig,widthaxes=plt.subplots(1,2,figsize=(11,4))
agefig,ageaxes=plt.subplots(2,2,figsize=(12,7))
speedfig,speedaxes=plt.subplots(2,2,figsize=(12,7))
for case in cases:
    row=['f1tenth','metadrive'].index(case['backend'])
    if case['group']=='width':
        ax=widthaxes[row];stop=case['must_stop']
        ax.scatter(case['halfwidth_L'],case['minimum_clearance_L'],marker='s' if stop else 'o',color='C1' if stop else 'C0')
        ax.annotate('stop' if stop else 'goal',(case['halfwidth_L'],case['minimum_clearance_L']),xytext=(0,8),textcoords='offset points',ha='center')
        ax.set(title=case['backend'],xlabel='road half-width / L',ylabel='minimum swept body clearance / L',ylim=(0,7.2));ax.grid(alpha=.2)
    if case['group']!='fault':continue
    column=['delay_120ms','pause_1s'].index(case['fault']);folder=root/case['id']
    with gzip.open(folder/'controls.csv.gz','rt') as f:controls=list(csv.DictReader(f))
    with gzip.open(folder/'physics.csv.gz','rt') as f:states=list(csv.DictReader(f))
    spec=json.loads((folder/'scenario.json').read_text());cruise=case['speed']*math.sqrt(spec['wheelbase_m']/.3302)
    ax=ageaxes[row,column]
    ax.plot([float(r['sim_t']) for r in controls],[(int(r['application_ns'])-int(r['source_wall_ns']))/1e6 for r in controls],label=case['policy'])
    ax.set(title=case['backend']+' / '+case['fault'],xlabel='simulation time, s',ylabel='controller-command age, ms')
    ax.legend(fontsize=8);ax.grid(alpha=.2)
    ax=speedaxes[row,column];stride=max(1,len(states)//3000)
    ax.plot([float(r['t']) for r in states[::stride]],[float(r['speed'])/cruise for r in states[::stride]],label=case['policy'])
    ax.set(title=case['backend']+' / '+case['fault'],xlabel='simulation time, s',ylabel='native speed / cruise speed',ylim=(-.05,1.1))
    ax.legend(fontsize=8);ax.grid(alpha=.2)
for ax in ageaxes.flat:ax.axhline(80,color='gray',ls=':',lw=.8)
for fig,name in [(widthfig,'focus40_width_boundary.png'),(agefig,'focus40_command_age.png'),(speedfig,'focus40_speed_response.png')]:
    fig.tight_layout();fig.savefig(out/name,dpi=160);plt.close(fig)
