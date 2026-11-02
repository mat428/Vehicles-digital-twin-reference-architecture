"""Recompute all summaries from frozen native records and audit primary inputs."""
from pathlib import Path
import json,math,hashlib
import numpy as np
import pandas as pd
from run import cases
from monitor import Monitor
ROOT=Path(__file__).resolve().parents[1]

def paired_bootstrap(frame,value_a,value_b,seed=765):
    differences=frame[value_a]-frame[value_b]
    blocks=[g.to_numpy() for _,g in differences.groupby(level=['campaign','seed'])]
    block=np.stack(blocks);rng=np.random.default_rng(seed)
    boot=np.median(block[rng.integers(0,len(blocks),size=(5000,len(blocks)))].reshape(5000,-1),axis=1)
    return dict(n=len(differences),seed_blocks=len(blocks),median_difference=float(np.median(differences)),
                bootstrap95_low=float(np.quantile(boot,.025)),bootstrap95_high=float(np.quantile(boot,.975)),
                resampling_unit='complete campaign/seed blocks; exploratory finite-matrix interval')

def main():
    cfg=json.loads((ROOT/'configs/protocol.json').read_text());ph=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest()
    freeze=json.loads((ROOT/'docs/design_freeze.json').read_text());assert ph==freeze['protocol_sha256']
    audit=[];summaries=[]
    for backend in ['f1tenth','metadrive']:
        model=json.loads((ROOT/'results'/backend/'monitor_model.json').read_text())
        assert model['protocol_sha256']==ph
        for campaign in ['A','B']:
            folder=ROOT/'results'/backend/'campaign'/campaign
            expected={c['id']:c for c in cases(cfg,campaign)}
            actual={p.stem for p in folder.glob('*.json') if p.stem not in ['execution_status','failure']}
            assert actual==set(expected),(backend,campaign,len(actual))
            assert json.loads((folder/'execution_status.json').read_text())['status']=='completed'
            for case_id,case in expected.items():
                s=json.loads((folder/(case_id+'.json')).read_text());raw=folder/s['raw_file'];obs_file=folder/s['observations_file']
                d=pd.read_csv(raw);o=pd.read_csv(obs_file);checks={}
                checks['matrix']=all(s[k]==v for k,v in case.items())
                checks['frozen_protocol']=s['protocol_sha256']==ph;checks['frozen_monitor']=s['model']==model
                checks['raw_hash']=hashlib.sha256(raw.read_bytes()).hexdigest()==s['raw_sha256']
                checks['observation_hash']=hashlib.sha256(obs_file.read_bytes()).hexdigest()==s['observations_sha256']
                checks['finite_controls']=bool(np.isfinite(d.to_numpy()).all())
                checks['finite_sensors']=bool(np.isfinite(o[['x_measured','y_measured','yaw_measured','speed_measured']].to_numpy()).all())
                checks['control_clock']=bool(np.allclose(np.diff(d.t),cfg['control_dt_s'],atol=1e-10))
                checks['source_clock']=bool(np.allclose(np.diff(o.source_t),cfg['observation_dt_s'],atol=1e-10))
                delivered=o.delivery_t.notna();delay=s.get('delay_ms',0)/1000
                checks['exact_delay']=bool(np.allclose(o.loc[delivered,'delivery_t']-o.loc[delivered,'source_t'],delay,atol=1e-10))
                checks['dropout']=bool(o.loc[o.dropped==1,'delivery_t'].isna().all()) and int(o.dropped.sum())==s['measurement_drop_count']
                checks['complete_packet_accounting']=bool(((~delivered)&(o.dropped==0)).sum()==((o.source_t+delay>d.t.iloc[-1]+1e-9)&(o.dropped==0)).sum())
                checks['raw_counts']=len(d)==s['control_records'] and len(o)==s['observation_records']
                checks['bounded_actuation']=bool((d.delta_delivered_rad.abs()<=cfg['steering_limit_rad']+1e-10).all())
                L=s['wheelbase_m'];eligible=d.t>=s['metric_start_s']
                errors={'post_error_m':np.hypot(d.dt_x-d.x,d.dt_y-d.y),
                        'naive_error_m':np.hypot(d.naive_x-d.x,d.naive_y-d.y),
                        'free_error_m':np.hypot(d.free_x-d.x,d.free_y-d.y)}
                checks['error_formulas']=all(np.allclose(d[k],v,atol=1e-10) for k,v in errors.items())
                if delay==0:checks['zero_delay_observer_identity']=bool(np.allclose(d.dt_x,d.naive_x,atol=1e-12,rtol=0) and np.allclose(d.dt_y,d.naive_y,atol=1e-12,rtol=0))
                metrics={'track_rmse_m':'cte_m','dt_post_rmse_m':'post_error_m','naive_rmse_m':'naive_error_m','free_rmse_m':'free_error_m'}
                checks['rmse_recomputed']=all(abs(s[k]-float(np.sqrt(np.mean(d.loc[eligible,column]**2))))<1e-10 for k,column in metrics.items())
                checks['normalized_tracking']=abs(s['track_rmse_L']-s['track_rmse_m']/L)<1e-12
                checks['alarm_fractions']=abs(s['yaw_alarm_fraction']-float(d.loc[eligible,'yaw_alarm'].mean()))<1e-12 and abs(s['age_alarm_fraction']-float(d.loc[eligible,'age_alarm'].mean()))<1e-12
                checks['tracking_p95']=abs(s['track_p95_m']-float(np.quantile(abs(d.loc[eligible,'cte_m']),.95)))<1e-10
                checks['native_timestep']=s['native_metadata']['physics_dt_s']==cfg[backend+'_physics_dt_s']
                native_L=sum(s['native_metadata']['params'][k] for k in ['lf','lr']) if backend=='f1tenth' else s['native_metadata']['wheelbase_m']
                checks['native_wheelbase']=abs(L-native_L)<1e-10
                mon=Monitor(cfg,model);equal=True;cursor=0;commands=d.delta_intended_rad.to_numpy()
                for row in o[delivered].itertuples():
                    while cursor*cfg['event_dt_s']<row.delivery_t-1e-9:
                        timepoint=cursor*cfg['event_dt_s'];command=float(commands[min(len(commands)-1,int(round(timepoint/cfg['control_dt_s'],8)))])
                        mon.advance(timepoint,command,cfg['event_dt_s'],L);cursor+=1
                    out=mon.receive(row.source_t,row.yaw_measured,row.speed_measured,row.q_cumulative)
                    values=[row.window_start_t,row.yaw_rate_measured,row.yaw_rate_reference,row.yaw_residual,row.yaw_alarm]
                    equal &= all((math.isnan(a) and math.isnan(b)) or abs(a-b)<1e-9 for a,b in zip(out,values))
                checks['monitor_replay']=bool(equal)
                audit.append(dict(backend=backend,campaign=campaign,id=case_id,checks=checks))
                s['backend']=backend
                for name in ['dt_post','naive','free']:s[name+'_rmse_L']=s[name+'_rmse_m']/L
                s['delay_ms']=s.get('delay_ms',0);s['fault']=s.get('fault','none');s['mismatch']=s.get('mismatch',0)
                summaries.append(s)
    table=pd.DataFrame(summaries);table.drop(columns=['model','native_metadata']).to_csv(ROOT/'results/run_summary.csv',index=False)
    aggregates=[]
    for keys,d in table.groupby(['backend','campaign','group','speed_case','mode','delay_ms','mismatch','fault','magnitude'],dropna=False):
        out=dict(zip(['backend','campaign','group','speed_case','mode','delay_ms','mismatch','fault','magnitude'],keys))
        out.update(n=len(d),completed=int(d.completed.sum()),boundary_failures=int(d.boundary_violation.sum()),
                   tracking_median_L=float(d.track_rmse_L.median()),corrected_median_L=float(d.dt_post_rmse_L.median()),
                   stale_median_L=float(d.naive_rmse_L.median()),free_median_L=float(d.free_rmse_L.median()),
                   yaw_detections=int(d.fault_detected.sum()),freshness_detections=int(d.age_detected.sum()))
        aggregates.append(out)
    pd.DataFrame(aggregates).to_csv(ROOT/'results/condition_summary.csv',index=False)
    geometry=table.groupby(['backend','track','group','mode','delay_ms','mismatch','fault','magnitude'],dropna=False).agg(n=('id','size'),completed=('completed','sum'),boundary_failures=('boundary_violation','sum'),tracking_median_L=('track_rmse_L','median'),yaw_detections=('fault_detected','sum')).reset_index()
    geometry['calibration_geometry']=geometry.track.isin(cfg['calibration_tracks']);geometry.to_csv(ROOT/'results/geometry_transfer.csv',index=False)
    pairs=[];diagnostics=[];zero_pairs=[]
    for backend in ['f1tenth','metadrive']:
        t=table[table.backend==backend];index=['campaign','seed','track','speed_case']
        e0=t[t.group=='E0'].pivot(index=index,columns='mode',values='track_rmse_L')
        pairs.append(dict(backend=backend,comparison='nominal timestamp minus direct tracking',**paired_bootstrap(e0,'timestamp','direct')))
        e1=t[(t.group=='E1')&(t.delay_ms==75)].pivot(index=index,columns='mode',values='track_rmse_L')
        pairs.append(dict(backend=backend,comparison='75ms timestamp minus stale closed-loop tracking',**paired_bootstrap(e1,'timestamp','stale')))
        shadow=t[(t.group=='E1')&(t.delay_ms==75)&(t['mode']=='timestamp')].set_index(index)
        pairs.append(dict(backend=backend,comparison='75ms corrected minus stale shadow position',**paired_bootstrap(shadow,'dt_post_rmse_L','naive_rmse_L')))
        for (fault,magnitude),d in t[t.group=='E3'].groupby(['fault','magnitude']):
            k=int(d.fault_detected.sum());a=int(d.age_detected.sum());n=len(d)
            blocks=d.groupby(['campaign','seed']).fault_detected.mean()
            diagnostics.append(dict(backend=backend,fault=fault,magnitude=float(magnitude),n=n,yaw_detections=k,
                                    freshness_detections=a,within_1s_detections=int(d.within_1s_detected.sum()),seed_blocks=len(blocks),
                                    min_seed_block_yaw_fraction=float(blocks.min()),max_seed_block_yaw_fraction=float(blocks.max()),
                                    median_yaw_delay_s=None if not k else float(d.loc[d.fault_detected,'first_yaw_alarm_delay_s'].median()),
                                    min_yaw_delay_s=None if not k else float(d.loc[d.fault_detected,'first_yaw_alarm_delay_s'].min()),
                                    max_yaw_delay_s=None if not k else float(d.loc[d.fault_detected,'first_yaw_alarm_delay_s'].max()),
                                    median_freshness_delay_s=None if not a else float(d.loc[d.age_detected,'first_age_alarm_delay_s'].median())))
        # At zero delay both corrected modes should produce identical closed loops.
        for _,d in t[t.group=='E0'].groupby(index):
            a=d[d['mode']=='timestamp'].iloc[0];b=d[d['mode']=='stale'].iloc[0]
            zero_pairs.append(dict(backend=backend,timestamp_case=a.id,stale_case=b.id,separate_native_tracking_difference_L=float(a.track_rmse_L-b.track_rmse_L)))
    (ROOT/'results/zero_delay_consistency.json').write_text(json.dumps(dict(note='Within-run zero-delay observers are identical; separate native Bullet resets are compared numerically rather than required to be byte-identical',pairs=zero_pairs),indent=2))
    (ROOT/'results/paired_comparisons.json').write_text(json.dumps(pairs,indent=2))
    pd.DataFrame(diagnostics).to_csv(ROOT/'results/fault_summary.csv',index=False)
    validation=dict(primary_runs=len(table),calibration_runs=24,control_records=int(table.control_records.sum()),
                    observation_records=int(table.observation_records.sum()),completed_circuits=int(table.completed.sum()),
                    boundary_failures=int(table.boundary_violation.sum()),all_checks_pass=all(all(a['checks'].values()) for a in audit),
                    eligible_nominal_prefault_yaw_alarm_deliveries=int(table.pre_fault_yaw_alarm_deliveries.sum()),audit=audit)
    (ROOT/'results/validation.json').write_text(json.dumps(validation,indent=2))
    print({k:v for k,v in validation.items() if k!='audit'})
    if not validation['all_checks_pass']:raise SystemExit(1)
if __name__=='__main__':main()
