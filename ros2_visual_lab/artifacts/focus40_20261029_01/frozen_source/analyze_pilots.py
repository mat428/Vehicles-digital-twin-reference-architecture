"""Audit pilot outputs and build plots without running native physics."""
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys


def corners(x, y, yaw, length, width):
    c, s = math.cos(yaw), math.sin(yaw)
    return [(x+c*a-s*b, y+s*a+c*b) for a,b in
            [(length/2,width/2),(-length/2,width/2),(-length/2,-width/2),(length/2,-width/2)]]


def point_segment(p, a, b):
    dx,dy=b[0]-a[0],b[1]-a[1]
    fraction=max(0.,min(1.,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy)))
    return math.hypot(p[0]-a[0]-fraction*dx,p[1]-a[1]-fraction*dy)


def polygon_distance(first, second):
    separated=False
    for polygon in [first,second]:
        for a,b in zip(polygon,polygon[1:]+polygon[:1]):
            axis=(-(b[1]-a[1]),b[0]-a[0])
            p=[x*axis[0]+y*axis[1] for x,y in first]
            q=[x*axis[0]+y*axis[1] for x,y in second]
            if max(p)<min(q) or max(q)<min(p):
                separated=True
    if not separated:
        return 0.
    return min(point_segment(p,a,b) for vertices,edges in [(first,second),(second,first)]
               for p in vertices for a,b in zip(edges,edges[1:]+edges[:1]))


def obstacle_audit(folder):
    spec=json.loads((folder/'scenario.json').read_text())
    result=json.loads((folder/'result.json').read_text())
    lo,bot,hi,top=spec['obstacle_bounds']
    obstacle=[(lo,bot),(hi,bot),(hi,top),(lo,top)]
    length,width=spec['dimensions_m']
    minimum,road_minimum=math.inf,math.inf
    with gzip.open(folder/'physics.csv.gz','rt') as f:
        rows=list(csv.DictReader(f))
    previous=None
    for row in rows:
        current=[float(row[key]) for key in ['x','y','yaw']]
        samples=[current]
        if previous:
            angle=math.atan2(math.sin(current[2]-previous[2]),math.cos(current[2]-previous[2]))
            samples.append([(previous[0]+current[0])/2,(previous[1]+current[1])/2,previous[2]+angle/2])
        for x,y,yaw in samples:
            body=corners(x,y,yaw,length,width)
            lower_bound=max(0.,lo-max(p[0] for p in body),min(p[0] for p in body)-hi)
            if lower_bound < minimum:
                minimum=min(minimum,polygon_distance(body,obstacle))
            road_minimum=min(road_minimum,min(p[1]+spec['road_halfwidth_m'] for p in body),
                             min(spec['road_halfwidth_m']-p[1] for p in body))
        previous=current
    final=rows[-1]
    reached=float(final['x'])>=spec['goal_x_m']
    threshold=.03*math.sqrt(spec['wheelbase_m']/.3302)
    # Reconstruct sustained terminal stop from retained native samples.
    stop_start=None
    for row in reversed(rows):
        if abs(float(row['speed']))>=threshold or float(row['speed_target'])!=0:
            break
        stop_start=float(row['t'])
    stopped=stop_start is not None and float(final['t'])-stop_start>=.49
    expected=reached if spec['kind']=='detour' else stopped
    passed=minimum>=spec['clearance_required_m'] and road_minimum>=0 and expected
    audit=dict(method='stdlib SAT/segment distances; recorded native endpoints and interval midpoints',
               sampled_clearance_m=minimum, sampled_road_clearance_m=road_minimum,
               endpoint_and_midpoint_collision=minimum<=0, outcome_confirmed=bool(expected),passed=bool(passed),
               swept_score_is_conservative=minimum+1e-7>=result['minimum_swept_clearance_m'],
               limitation='Midpoint audit complements conservative swept score; no continuous native-contact dynamics claim.')
    (folder/'independent_audit.json').write_text(json.dumps(audit,indent=2))
    return audit,rows,spec


def analyze(root):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    manifest=json.loads((root/'manifest.json').read_text())
    records=[]
    geometry_fig,geometry_axes=plt.subplots(2,3,figsize=(13,8))
    obstacle_fig,obstacle_axes=plt.subplots(2,2,figsize=(12,7))
    for case in manifest['matrix']:
        folder=root/case['id']
        row=dict(**case,passed=False)
        try:
            if case['family']=='geometry':
                result=json.loads((folder/'dds_report.json').read_text())
                summary=json.loads(next(folder.glob('dds_*.json')).read_text())
                # Select the actual run summary explicitly, avoiding dds_report.json.
                summary=json.loads((folder/('dds_'+case['track']+'.json')).read_text())
                with gzip.open(folder/('dds_'+case['track']+'.csv.gz'),'rt') as f:
                    states=list(csv.DictReader(f))
                selected=[r for r in states if float(r['t'])>=summary['metric_start_s']]
                rmse=math.sqrt(sum(float(r['cte_m'])**2 for r in selected)/len(selected))
                verified=abs(rmse-summary['track_rmse_m'])<1e-10
                row.update(outcome='completed' if result['completed'] else 'failed',
                           passed=result['completed'] and not result['boundary_violation'] and verified,
                           tracking_rmse_L=rmse/summary['wheelbase_m'], rmse_recomputed=verified,
                           round_trip_p95_ms=result['round_trip_p95_ms'])
                ax=geometry_axes[['f1tenth','metadrive'].index(case['backend']),['circle','ellipse','wavy'].index(case['track'])]
                L=summary['wheelbase_m']
                ax.plot([float(r['x'])/L for r in states],[float(r['y'])/L for r in states],label=f"speed {case['speed']:g}")
                ax.set_title(case['backend']+' / '+case['track'])
            else:
                result=json.loads((folder/'result.json').read_text())
                audit,states,spec=obstacle_audit(folder)
                row.update(outcome=result['outcome'],passed=result['passed'] and audit['passed'] and audit['swept_score_is_conservative'],
                           minimum_clearance_L=result['minimum_swept_clearance_m']/spec['wheelbase_m'],
                           independent_clearance_L=audit['sampled_clearance_m']/spec['wheelbase_m'],
                           round_trip_p95_ms=result['round_trip_p95_ms'])
                ax=obstacle_axes[['f1tenth','metadrive'].index(case['backend']),['detour','blocked'].index(case['scenario'])]
                L=spec['wheelbase_m']
                ax.plot([float(r['x'])/L for r in states],[float(r['y'])/L for r in states],label=f"speed {case['speed']:g}")
                if case['speed']==1:
                    from matplotlib.patches import Rectangle
                    a,b,c,d=[v/L for v in spec['obstacle_bounds']]
                    ax.add_patch(Rectangle((a,b),c-a,d-b,color='tomato',alpha=.5))
                    ax.axhline(4,color='gray',ls='--');ax.axhline(-4,color='gray',ls='--')
                    ax.plot([p[0]/L for p in spec['selected_path']],[p[1]/L for p in spec['selected_path']],ls=':',color='gray',label='selected path')
                ax.set_title(case['backend']+' / '+case['scenario']);ax.set_ylim(-5,5)
        except Exception as exc:
            row['error']=repr(exc)
        records.append(row)
        print(case['id'],'PASS' if row['passed'] else 'FAIL',row.get('outcome',row.get('error')),flush=True)
    for figure,axes,name in [(geometry_fig,geometry_axes,'geometry_trajectories.png'),
                              (obstacle_fig,obstacle_axes,'obstacle_trajectories.png')]:
        for ax in axes.flat:
            ax.set_aspect('equal',adjustable='datalim');ax.set_xlabel('x / L');ax.set_ylabel('y / L');ax.grid(alpha=.2)
            if ax.lines:ax.legend(fontsize=8)
        figure.tight_layout();figure.savefig(root/name,dpi=160);plt.close(figure)
    report=dict(planned=len(records),passed=sum(r['passed'] for r in records),cases=records,
                scope='single-seed development pilots; lockstep DDS; map-based obstacle geometry')
    (root/'pilot_summary.json').write_text(json.dumps(report,indent=2))
    lines=['# Pilot result summary','',f"Passed: {report['passed']}/{report['planned']}.",'',
           '| Case | Outcome | Pilot gate |','| --- | --- | --- |']
    lines += [f"| {r['id']} | {r.get('outcome',r.get('error'))} | {'PASS' if r['passed'] else 'FAIL'} |" for r in records]
    lines += ['', 'These are one-seed development results. Obstacles are known static geometric exclusion regions; no perception, physical impact, asynchronous DDS or safety claim is established.']
    (root/'RESULTS.md').write_text('\n'.join(lines)+'\n')
    payload=[]
    for path in sorted(root.rglob('*')):
        if path.is_file() and path.name!='output_hashes.json':
            payload.append(dict(path=str(path.relative_to(root)),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    (root/'output_hashes.json').write_text(json.dumps(payload,indent=2))
    return 0 if report['passed']==report['planned'] else 1


if __name__=='__main__':
    sys.exit(analyze(Path(sys.argv[1])))
