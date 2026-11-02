"""Independent control-age and geometric audits; retain adverse task outcomes."""
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys
from analyze_pilots import corners,polygon_distance


def read_csv(path):
    with gzip.open(path,'rt') as stream:return list(csv.DictReader(stream))


def audit(folder,result):
    spec=json.loads((folder/'scenario.json').read_text());L=spec['wheelbase_m']
    states=read_csv(folder/'physics.csv.gz');controls=read_csv(folder/'controls.csv.gz')
    events=json.loads((folder/'events.json').read_text())
    a,b,c,d=spec['obstacle_bounds'];obstacle=[(a,b),(c,b),(c,d),(a,d)]
    length,width=spec['dimensions_m'];minimum=math.inf;edge=math.inf;previous=None
    for row in states:
        current=[float(row[key]) for key in ['x','y','yaw']];samples=[current]
        if previous:
            angle=math.atan2(math.sin(current[2]-previous[2]),math.cos(current[2]-previous[2]))
            samples.append([(current[0]+previous[0])/2,(current[1]+previous[1])/2,previous[2]+angle/2])
        for x,y,yaw in samples:
            body=corners(x,y,yaw,length,width)
            lower=max(0.,a-max(p[0] for p in body),min(p[0] for p in body)-c)
            if lower<minimum:minimum=min(minimum,polygon_distance(body,obstacle))
            edge=min(edge,*[spec['road_halfwidth_m']-abs(p[1]) for p in body])
        previous=current
    latch=False;policy_valid=True;ages=[]
    for row in controls:
        age=(int(row['application_ns'])-int(row['source_wall_ns']))/1e6;ages.append(age)
        expired=age>80
        latch=latch or (expired and result['policy']=='expire_stop')
        expected_speed=0. if latch else float(row['requested_speed'])
        policy_valid &= (int(row['expired'])==int(expired) and int(row['expiry_latched'])==int(latch)
                         and abs(float(row['applied_speed'])-expected_speed)<1e-12
                         and abs(float(row['applied_delta'])-float(row['requested_delta']))<1e-12)
    final=states[-1];stop_start=None
    for row in reversed(states):
        if abs(float(row['speed']))>=.03*math.sqrt(L/.3302) or float(row['speed_target'])!=0:break
        stop_start=float(row['t'])
    stopped=stop_start is not None and float(final['t'])-stop_start>=.49
    outcome_valid=(result['outcome']=='goal_reached' and float(final['x'])>=spec['goal_x_m']
                   or result['outcome']=='stopped' and stopped
                   or result['outcome']=='obstacle_collision' and (minimum<=1e-6 or result['minimum_swept_clearance_m']==0)
                   or result['outcome']=='road_departure' and (edge<1e-6 or result['minimum_road_clearance_m']<0)
                   or result['outcome']=='timeout')
    requests={int(r['sequence']):r for r in read_csv(folder/'requests.csv.gz')}
    replies=read_csv(folder/'responses.csv.gz');reply_valid=True
    for reply in replies:
        request=requests[int(reply['sequence'])]
        reply_valid &= int(reply['source_wall_ns'])==int(request['source_wall_ns'])
        reply_valid &= int(reply['controller_received_ns'])<=int(reply['controller_finished_ns'])<=int(reply['published_ns'])<=int(reply['arrival_ns'])
        reply_valid &= int(reply['published_ns'])-int(reply['controller_finished_ns']) >= float(request['delay_ms'])*1e6-1e6
    starts=[e for e in events if e['event']=='fault_start'];resumes=[e for e in events if e['event']=='controller_resumed']
    fault_valid=True
    if result['fault']!='none':fault_valid=bool(starts)
    if result['fault']=='pause_1s':
        censored=any(e['event']=='controller_pause_censored_by_case_end' for e in events)
        fault_valid &= (bool(resumes) and resumes[0]['wall_ns']-starts[0]['wall_ns']>=1_000_000_000
                        or censored and result['outcome'] in ['obstacle_collision','road_departure','timeout'])
    record=dict(independent_policy_valid=bool(policy_valid),reply_timestamps_valid=bool(reply_valid),
                fault_execution_valid=bool(fault_valid),outcome_confirmed=bool(outcome_valid),
                sampled_clearance_m=minimum,sampled_road_clearance_m=edge,
                production_swept_clearance_conservative=minimum+1e-7>=result['minimum_swept_clearance_m'],
                command_age_max_ms=max(ages),command_age_p95_ms=sorted(ages)[int(.95*(len(ages)-1))],
                method='stdlib native endpoints/midpoints SAT and segment distances; independently reconstructed wall-time command-age authority')
    record['valid']=all(record[key] for key in ['independent_policy_valid','reply_timestamps_valid','fault_execution_valid',
                 'outcome_confirmed','production_swept_clearance_conservative'])
    (folder/'independent_audit.json').write_text(json.dumps(record,indent=2))
    return record,states,spec,controls


def analyze(root):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    manifest=json.loads((root/'manifest.json').read_text());records=[]
    width_fig,width_axes=plt.subplots(1,2,figsize=(11,4))
    fault_fig,fault_axes=plt.subplots(2,2,figsize=(12,7))
    for case in manifest['cases']:
        folder=root/case['id'];record=dict(**case,audit_valid=False)
        try:
            result=json.loads((folder/'result.json').read_text());check,states,spec,controls=audit(folder,result)
            record.update(outcome=result['outcome'],goal_reached=result['goal_reached'],
                collision_free=result['collision_free'],clearance_gate_met=result['clearance_gate_met'],
                audit_valid=check['valid'],must_stop=result['must_stop'],expiry_latched=result['expiry_latched'],
                max_start_lag_s=result['max_start_lag_s'],command_age_max_ms=check['command_age_max_ms'],
                minimum_clearance_L=result['minimum_swept_clearance_m']/spec['wheelbase_m'],
                elapsed_sim_s=result['elapsed_sim_s'],elapsed_wall_s=result['elapsed_wall_s'])
            if case['group']=='width':
                ax=width_axes[['f1tenth','metadrive'].index(case['backend'])]
                ax.scatter(case['halfwidth_L'],record['minimum_clearance_L'],marker='s' if result['must_stop'] else 'o',
                           color='C1' if result['must_stop'] else 'C0')
                ax.annotate('stop' if result['must_stop'] else 'goal' if result['goal_reached'] else result['outcome'],
                            (case['halfwidth_L'],record['minimum_clearance_L']),xytext=(0,7),textcoords='offset points',ha='center',fontsize=8)
                ax.set(title=case['backend'],xlabel='road half-width / L',ylabel='minimum swept clearance / L')
                ax.grid(alpha=.2)
            if case['group']=='fault':
                ax=fault_axes[['f1tenth','metadrive'].index(case['backend']),['delay_120ms','pause_1s'].index(case['fault'])]
                ax.plot([float(r['sim_t']) for r in controls],[(int(r['application_ns'])-int(r['source_wall_ns']))/1e6 for r in controls],label=case['policy'])
                ax.axhline(80,color='gray',ls=':',lw=.7);ax.set(title=case['backend']+' / '+case['fault'],xlabel='simulation time, s',ylabel='applied command age, ms')
                ax.legend(fontsize=8);ax.grid(alpha=.2)
        except Exception as exc:record['error']=repr(exc)
        records.append(record)
        print(case['id'],record.get('outcome',record.get('error')),'audit',record['audit_valid'],flush=True)
    for fig,name in [(width_fig,'width_boundary.png'),(fault_fig,'command_age.png')]:
        fig.tight_layout();fig.savefig(root/name,dpi=160);plt.close(fig)
    summary=dict(planned=len(records),audits_valid=sum(r['audit_valid'] for r in records),cases=records,
                 interpretation='Task failures are measured outcomes, separate from execution/audit failures. Development sample sizes do not imply robustness probabilities.')
    (root/'summary.json').write_text(json.dumps(summary,indent=2))
    lines=['# Focused campaign outcomes','',f"Valid audits: {summary['audits_valid']}/{len(records)}.",'',
           '| Case | Outcome | Clearance/L | Audit |','| --- | --- | ---: | --- |']
    lines += [f"| {r['id']} | {r.get('outcome',r.get('error'))} | {r.get('minimum_clearance_L',float('nan')):.4f} | {r['audit_valid']} |" for r in records]
    (root/'RESULTS.md').write_text('\n'.join(lines)+'\n')
    hashes=[dict(path=str(p.relative_to(root)),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
            for p in sorted(root.rglob('*')) if p.is_file() and p.name!='output_hashes.json']
    (root/'output_hashes.json').write_text(json.dumps(hashes,indent=2))
    return int(summary['audits_valid']!=len(records))


if __name__=='__main__':sys.exit(analyze(Path(sys.argv[1])))
