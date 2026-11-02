"""Export empirical Figures 10--12 without reading or writing a manuscript.
Derived from the supplied report.py; plotting calculations are retained.
"""
from pathlib import Path
import json,math
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'figures'
COLORS={'f1tenth':'#167C80','metadrive':'#B77824'}
LABELS={'f1tenth':'F1TENTH','metadrive':'MetaDrive'}
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.labelsize':10,'axes.titlesize':10.5,
                     'pdf.fonttype':42,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False})

FIGURE_QA=[]

def save(fig,name):
    fig.canvas.draw();renderer=fig.canvas.get_renderer()
    legend_hits=[]
    for legend in fig.legends:
        bounds=legend.get_window_extent(renderer)
        for i,axis in enumerate(fig.axes):
            if bounds.overlaps(axis.get_window_extent(renderer)):legend_hits.append(i)
    out_of_bounds=[];tick_overlaps=[]
    for axis in fig.axes:
        xt=[label for label in axis.get_xticklabels() if axis.get_xlim()[0]<=label.get_position()[0]<=axis.get_xlim()[1]]
        yt=[label for label in axis.get_yticklabels() if axis.get_ylim()[0]<=label.get_position()[1]<=axis.get_ylim()[1]]
        for left,right in zip(xt,xt[1:]):
            if left.get_window_extent(renderer).overlaps(right.get_window_extent(renderer)):tick_overlaps.append([left.get_text(),right.get_text()])
        for label in [axis.title,axis.xaxis.label,axis.yaxis.label]+xt+yt:
            if label.get_visible() and label.get_text():
                b=label.get_window_extent(renderer)
                if b.x0<0 or b.y0<0 or b.x1>fig.bbox.x1 or b.y1>fig.bbox.y1:out_of_bounds.append(label.get_text())
    FIGURE_QA.append(dict(figure=name,legend_overlaps_data_axes=legend_hits,out_of_canvas_text=out_of_bounds,adjacent_tick_label_overlaps=tick_overlaps))
    for ext in ['pdf']:fig.savefig(OUT/(name+'.'+ext),dpi=300,facecolor='white')
    plt.close(fig)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    validation=json.loads((ROOT/'results/validation.json').read_text())
    independent=json.loads((ROOT/'results/independent_validation.json').read_text())
    assert validation['all_checks_pass'] and independent['all_checks_pass']
    t=pd.read_csv(ROOT/'results/run_summary.csv');fault=pd.read_csv(ROOT/'results/fault_summary.csv')
    pairs=json.loads((ROOT/'results/paired_comparisons.json').read_text());cfg=json.loads((ROOT/'configs/protocol.json').read_text())
    numeric=pd.read_csv(ROOT/'results/numerical_sensitivity.csv');install=json.loads((ROOT/'results/install_smoke.json').read_text())
    fig,axes=plt.subplots(2,2,figsize=(7.0,6.6));fig.subplots_adjust(left=.12,right=.97,bottom=.16,top=.93,hspace=.55,wspace=.38)
    for j,backend in enumerate(['f1tenth','metadrive']):
        d=t[t.backend==backend]
        ax=axes[0,j];xs=[0,75];aware=[];stale=[]
        for delay in xs:
            sub=d[(d.group==('E0' if delay==0 else 'E1'))&(d['mode']=='timestamp')&(d.delay_ms==delay)&(d.speed_case==2)]
            aware.append(sub.dt_post_rmse_L.median());stale.append(sub.naive_rmse_L.median())
        ax.plot(xs,aware,'o-',color=COLORS[backend],label='Source-time replay')
        ax.plot(xs,stale,'s--',color='#6B7E8B',label='Stale shadow')
        ax.set(title=f'({chr(97+j)}) {LABELS[backend]}: shared trajectory',xlabel='Observation delay (ms)',ylabel='Position RMSE / wheelbase',xticks=xs)
        ax.grid(alpha=.2);ax.set_ylim(bottom=0)
        ax=axes[1,j]
        delay=d[(d.group=='E1')&(d.delay_ms==75)]
        e=delay.pivot(index=['campaign','seed','track','speed_case'],columns='mode',values='track_rmse_L')
        for _,row in e.iterrows():ax.plot([0,1],[row.timestamp,row.stale],color=COLORS[backend],alpha=.3,lw=.7)
        ax.scatter(np.zeros(len(e)),e.timestamp,s=11,color=COLORS[backend]);ax.scatter(np.ones(len(e)),e.stale,s=11,color=COLORS[backend])
        ax.set(title=f'({chr(99+j)}) {LABELS[backend]}: closed-loop pairs',xticks=[0,1],xticklabels=['Replay control','Stale control'],ylabel='Tracking RMSE / wheelbase',xlim=(-.25,1.25))
        ax.grid(axis='y',alpha=.2)
    handles,labels=axes[0,0].get_legend_handles_labels();fig.legend(handles,labels,loc='lower center',ncol=2,bbox_to_anchor=(.5,.025),frameon=False)
    save(fig,'experimental_evidence')

    fig,axes=plt.subplots(1,2,figsize=(7,3.6));fig.subplots_adjust(left=.09,right=.97,bottom=.25,top=.84,wspace=.35)
    labels=['−8°','−2°','+2°','+8°','20%\nloss','0.20 s\nburst']
    for ax,backend in zip(axes,['f1tenth','metadrive']):
        d=fault[fault.backend==backend];rows=[]
        for typ,mag in [('steering',-8),('steering',-2),('steering',2),('steering',8),('dropout',20),('burst',.2)]:rows.append(d[(d.fault==typ)&np.isclose(d.magnitude,mag)].iloc[0])
        x=np.array([0.,1.,2.,3.,4.5,6.]);width=.33
        yaw=np.array([r.yaw_detections/r.n for r in rows]);age=np.array([r.freshness_detections/r.n for r in rows])
        ax.bar(x-width/2,yaw,width,color=COLORS[backend],label='Yaw residual')
        ax.bar(x+width/2,age,width,color='#6B7E8B',label='Freshness')
        ax.set(title=LABELS[backend],xticks=x,xticklabels=labels,ylim=(-.03,1.10),yticks=[0,.5,1],ylabel='Observed detection fraction');ax.grid(axis='y',alpha=.15)
    handles,legend_labels=axes[0].get_legend_handles_labels();fig.legend(handles,legend_labels,loc='lower center',ncol=2,bbox_to_anchor=(.5,.01),frameon=False)
    save(fig,'fault_evidence')

    from common import track
    fig,axes=plt.subplots(2,3,figsize=(7,5.4))
    fig.subplots_adjust(left=.08,right=.98,bottom=.15,top=.91,hspace=.38,wspace=.25)
    for row,backend in enumerate(['f1tenth','metadrive']):
        for col,name in enumerate(cfg['tracks']):
            selected=t[(t.backend==backend)&(t.group=='E0')&(t['mode']=='timestamp')&(t.track==name)&(t.speed_case==2)&(t.campaign=='A')&(t.seed==cfg['campaigns']['A']['seeds'][0])].iloc[0]
            raw=pd.read_csv(ROOT/'results'/backend/'campaign'/'A'/selected.raw_file);L=selected.wheelbase_m
            reference=track(name,L)['points']/L;ax=axes[row,col]
            ax.plot(reference[:,0],reference[:,1],color='#6B7E8B',ls='--',lw=1.4,label='Known centerline')
            ax.plot(raw.x/L,raw.y/L,color=COLORS[backend],lw=.9,label=LABELS[backend])
            ax.set(title=LABELS[backend]+' / '+name.capitalize(),xlim=(-11,11),ylim=(-1,19),xticks=[-10,0,10],yticks=[0,8,16])
            ax.set_aspect('equal',adjustable='box');ax.grid(alpha=.15)
            if row==1:ax.set_xlabel('x / wheelbase')
            if col==0:ax.set_ylabel('y / wheelbase')
    from matplotlib.lines import Line2D
    handles=[Line2D([0],[0],color='#6B7E8B',ls='--',label='Known centerline')]+[Line2D([0],[0],color=COLORS[b],label=LABELS[b]) for b in ['f1tenth','metadrive']]
    fig.legend(handles=handles,loc='lower center',ncol=3,bbox_to_anchor=(.5,.015),frameon=False)
    save(fig,'native_trajectories')

    print("Exported Figures 10--12 to figures/; no manuscript files were created or modified.")

if __name__=="__main__": main()
