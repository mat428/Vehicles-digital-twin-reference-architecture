"""Sequential native campaign repetition; frozen protocol, paired observers, observation-only monitoring."""
import argparse,csv,gzip,json,math,time,hashlib,traceback,os,io
from collections import deque
from pathlib import Path
import numpy as np
from plants import F1Plant,MetaPlant
from common import track,nearest,control,propagate,correct,wrap
from monitor import Monitor
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
FIELDS=['t','x','y','yaw','speed','dt_x','dt_y','dt_yaw','dt_speed','naive_x','naive_y','pre_error_m','post_error_m','naive_error_m','cte_m','delta_intended_rad','delta_delivered_rad','source_age_s','yaw_alarm','age_alarm','progress_fraction','free_x','free_y','free_error_m']
OBS_FIELDS=['source_t','delivery_t','x_measured','y_measured','yaw_measured','speed_measured','dropped','q_cumulative','yaw_rate_measured','yaw_rate_reference','yaw_residual','yaw_alarm','window_start_t','qualified_yaw_alarm']

def write_gzip(path,fields,rows):
    stream=io.StringIO();writer=csv.writer(stream);writer.writerow(fields);writer.writerows(rows)
    data=gzip.compress(stream.getvalue().encode(),compresslevel=3,mtime=0);temp=path.with_suffix('.staged');temp.write_bytes(data);os.replace(temp,path)
    return hashlib.sha256(data).hexdigest()
def atomic_json(path,value):
    tmp=path.with_suffix('.staged');tmp.write_text(json.dumps(value,indent=2));os.replace(tmp,path)

def run_case(plant,cfg,case,folder,model=None):
    L=plant.L;scale=L/cfg['f1tenth_wheelbase_m'];time_scale=math.sqrt(scale);speed=case['speed_case']*time_scale
    path=track(case['track'],L);seed=case['seed'];noise=np.random.default_rng(seed);drops=np.random.default_rng(seed+9999)
    lateral=float(np.random.default_rng(seed+5555).uniform(-.03,.03))*L
    # Set only the initial condition; settle forward from a point behind the reference start.
    state=plant.reset(seed,[-speed*cfg['settling_s'],lateral,0],speed)
    observer=state.copy();naive=state.copy();free=state.copy();held=state.copy();monitor=Monitor(cfg,model);history=deque(maxlen=100);queue=deque();records=[];obs_rows=[]
    index_true=0;index_control=0;delta=0.;qtotal=0.;last_packet=None;last_source=0.;yaw_count=0;yaw_alarm=False;first_alarm=None;first_age=None
    actual_steps=round((path['length']/speed*1.4+3*time_scale)/cfg['event_dt_s']);sample_every=round(cfg['observation_dt_s']/cfg['event_dt_s']);control_every=round(cfg['control_dt_s']/cfg['event_dt_s'])
    fault_time=round(cfg['fault_start_s']*time_scale/cfg['observation_dt_s'])*cfg['observation_dt_s'];fault=case.get('fault','none');mismatch=case.get('mismatch',0)/100;model_L=L*(1+mismatch)
    gain=model['gain'] if model else 1.;threshold=model['threshold_rad_s'] if model else cfg['yaw_residual_threshold_rad_s']
    boundary=False;complete=False;source_count=0;drop_count=0;firstfalse=0;pred_cum_last=0.;last_obs_source=None;last_obs_yaw=None;last_q=None;model_records=[];qualified_count=0
    delay=case.get('delay_ms',0)/1000;eligible_start=2*time_scale
    for tick in range(actual_steps):
        t=tick*cfg['event_dt_s'];active=t>=fault_time and fault!='none'
        # Source sampling occurs independently of delivery. Native state is never overwritten.
        if tick%sample_every==0:
            measurement=state+noise.normal(0,[cfg['position_noise_wheelbases']*L,cfg['position_noise_wheelbases']*L,cfg['yaw_noise_rad'],cfg['speed_noise_wheelbases_s']*L]);measurement[2]=wrap(measurement[2]);measurement[3]=max(0.,measurement[3])
            draw=drops.random()
            dropped=bool((active and fault=='dropout' and draw<case['magnitude']/100) or (active and fault=='burst' and t<fault_time+case['magnitude']-1e-9))
            source_count+=1;drop_count+=int(dropped)
            if not dropped:queue.append((t+delay,t,measurement,qtotal))
            obs_rows.append([t,float('nan'),*measurement,int(dropped),qtotal,float('nan'),float('nan'),float('nan'),0,float('nan'),0])
        pre_error=float(np.linalg.norm(observer[:2]-state[:2]))
        while queue and queue[0][0]<=t+1e-9:
            scheduled,source,measurement,qpacket=queue.popleft();held=measurement.copy();last_source=source
            replay=measurement.copy()
            for source_interval,command in history:
                if source_interval>=source-1e-9 and source_interval<t-1e-9:replay=propagate(replay,command,cfg['event_dt_s'],model_L,speed)
            observer=correct(observer,replay,cfg['correction_gain']);naive=correct(naive,measurement,cfg['correction_gain'])
            window_start,rate,reference_rate,residual,alarm=monitor.receive(source,measurement[2],measurement[3],qpacket)
            yaw_alarm=bool(alarm)
            if math.isfinite(rate) and window_start>=eligible_start:model_records.append((rate,reference_rate))
            qualified_count=qualified_count+1 if active and math.isfinite(residual) and window_start>=fault_time-1e-9 and abs(residual)>threshold else 0
            qualified=qualified_count>=cfg['persistent_measurements']
            if qualified and first_alarm is None:first_alarm=t-fault_time
            if yaw_alarm and t>=eligible_start and not active:firstfalse+=1
            row=obs_rows[round(source/cfg['observation_dt_s'])];row[1]=t;row[8]=rate;row[9]=reference_rate;row[10]=residual;row[11]=int(yaw_alarm);row[12]=window_start;row[13]=int(qualified)
        age=t-last_source;age_alarm=age>cfg['age_threshold_s']+1e-9
        if age_alarm and t>=fault_time and first_age is None:first_age=t-fault_time
        if tick%control_every==0:
            chosen={'direct':held,'timestamp':observer,'stale':naive}[case['mode']]
            delta,index_control=control(chosen,path,index_control,L,cfg)
            index_true,error=nearest(state,path,index_true);index_true=max(0,index_true)
            delivered=float(np.clip(delta+(math.radians(case['magnitude']) if active and fault=='steering' else 0),-cfg['steering_limit_rad'],cfg['steering_limit_rad']))
            records.append([t,*state,*observer,naive[0],naive[1],pre_error,float(np.linalg.norm(observer[:2]-state[:2])),float(np.linalg.norm(naive[:2]-state[:2])),error,delta,delivered,age,int(yaw_alarm),int(age_alarm),index_true/len(path['points']),free[0],free[1],float(np.linalg.norm(free[:2]-state[:2]))])
            if abs(error)>cfg['corridor_halfwidth_wheelbases']*L:boundary=True;break
            if index_true>=len(path['points']):complete=True;break
        delivered=float(np.clip(delta+(math.radians(case['magnitude']) if active and fault=='steering' else 0),-cfg['steering_limit_rad'],cfg['steering_limit_rad']))
        monitor.advance(t,delta,cfg['event_dt_s'],L)
        qtotal+=math.tan(delta)/L*cfg['event_dt_s'];history.append((t,delta))
        observer=propagate(observer,delta,cfg['event_dt_s'],model_L,speed);naive=propagate(naive,delta,cfg['event_dt_s'],model_L,speed)
        free=propagate(free,delta,cfg['event_dt_s'],model_L,speed)
        state=plant.step(delivered,speed,cfg['event_dt_s'])
    array=np.asarray(records);mask=array[:,0]>=eligible_start;post=array[:,0]>=fault_time
    stem=case['id'];raw=folder/(stem+'.csv.gz');observations=folder/(stem+'_observations.csv.gz')
    digest=write_gzip(raw,FIELDS,records);obs_digest=write_gzip(observations,OBS_FIELDS,obs_rows)
    summary=dict(**case,wheelbase_m=L,time_scale=time_scale,actual_target_speed_m_s=speed,fault_onset_s=fault_time,
        raw_file=raw.name,raw_sha256=digest,observations_file=observations.name,observations_sha256=obs_digest,
        control_records=len(records),observation_records=len(obs_rows),native_metadata=plant.metadata,
        completed=complete,boundary_violation=boundary,elapsed_s=float(array[-1,0]),measurement_drop_count=drop_count,
        track_rmse_m=float(np.sqrt(np.mean(array[mask,14]**2))),track_rmse_L=float(np.sqrt(np.mean(array[mask,14]**2)))/L,
        free_rmse_m=float(np.sqrt(np.mean(array[mask,23]**2))),metric_start_s=eligible_start,
        track_p95_m=float(np.quantile(abs(array[mask,14]),.95)),dt_pre_rmse_m=float(np.sqrt(np.mean(array[mask,11]**2))),
        dt_post_rmse_m=float(np.sqrt(np.mean(array[mask,12]**2))),naive_rmse_m=float(np.sqrt(np.mean(array[mask,13]**2))),
        first_yaw_alarm_delay_s=first_alarm,first_age_alarm_delay_s=first_age,pre_fault_yaw_alarm_deliveries=firstfalse,
        fault_detected=first_alarm is not None,within_1s_detected=first_alarm is not None and first_alarm<=1.,
        age_detected=first_age is not None,yaw_alarm_fraction=float(array[mask,18].mean()),age_alarm_fraction=float(array[mask,19].mean()),
        protocol_sha256=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest(),model=model)
    atomic_json(folder/(stem+'.json'),summary)
    print(stem,'complete' if complete else 'boundary' if boundary else 'timeout',len(records),flush=True)
    return summary,model_records

def cases(cfg,campaign):
    settings=cfg['campaigns'][campaign];out=[]
    def add(group,name,speed,seed,**kw):out.append(dict(id=f'{campaign}_{group}_{len(out):04d}',campaign=campaign,group=group,track=name,speed_case=speed,seed=seed,**kw))
    for name in cfg['tracks']:
        for speed in cfg['speeds_f1_m_s']:
            for seed in settings['seeds']:
                for mode in ['direct','timestamp','stale']:add('E0',name,speed,seed,mode=mode)
                for delay in cfg['delays_ms']:add('E1',name,speed,seed,mode='timestamp',delay_ms=delay)
                add('E1',name,speed,seed,mode='stale',delay_ms=max(cfg['delays_ms']))
                for mismatch in cfg['mismatch_pct']:add('E2',name,speed,seed,mode='timestamp',mismatch=mismatch)
                for magnitude in cfg['steering_bias_deg']:add('E3',name,speed,seed,mode='timestamp',fault='steering',magnitude=magnitude)
                for magnitude in cfg['dropout_pct']:add('E3',name,speed,seed,mode='timestamp',fault='dropout',magnitude=magnitude)
                add('E3',name,speed,seed,mode='timestamp',fault='burst',magnitude=cfg['burst_dropout_s'])
    assert len(out)==216;return out

def main():
    p=argparse.ArgumentParser();p.add_argument('--backend',choices=['f1tenth','metadrive'],required=True);p.add_argument('--phase',choices=['pilot','calibration','campaign'],required=True);p.add_argument('--campaign',choices=['A','B'],default='A');args=p.parse_args()
    cfg=json.loads((ROOT/'configs/protocol.json').read_text());folder=ROOT/'results'/args.backend/args.phase/args.campaign;folder.mkdir(parents=True,exist_ok=True)
    if list(folder.glob('*.csv.gz')):raise RuntimeError('Refusing to overwrite raw data; use a new project copy')
    started=datetime.now(timezone.utc).isoformat()
    plant=(F1Plant if args.backend=='f1tenth' else MetaPlant)(cfg);summaries=[];fit_samples=[];status='running';model_file=ROOT/'results'/args.backend/'monitor_model.json'
    try:
        model=json.loads(model_file.read_text()) if args.phase=='campaign' else None
        if model and model['protocol_sha256']!=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest():raise ValueError('Protocol changed: recalibrate before campaign')
        matrix=cases(cfg,args.campaign)
        if args.phase=='pilot':matrix=[dict(id=f'pilot_{name}',campaign='pilot',group='pilot',track=name,speed_case=2.,seed=100,mode='timestamp') for name in cfg['tracks']]
        if args.phase=='calibration':matrix=[dict(id=f'cal_{name}_{speed}_{seed}',campaign='calibration',group='calibration',track=name,speed_case=speed,seed=seed,mode='timestamp') for name in cfg['calibration_tracks'] for speed in cfg['speeds_f1_m_s'] for seed in cfg['calibration_seeds']]
        for case in matrix:
            summary,samples=run_case(plant,cfg,case,folder,model);summaries.append(summary);fit_samples.extend(samples)
        if args.phase=='calibration':
            fit=np.asarray(fit_samples);gain=float(np.dot(fit[:,0],fit[:,1])/np.dot(fit[:,1],fit[:,1]));res=fit[:,0]-gain*fit[:,1]
            model=dict(gain=gain,threshold_rad_s=max(cfg['yaw_residual_threshold_rad_s'],float(np.quantile(abs(res),cfg['calibration_quantile']))),samples=len(fit),calibration_runs=len(matrix),protocol_sha256=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest(),calibration=[dict(id=s['id'],raw_sha256=s['raw_sha256'],observations_sha256=s['observations_sha256']) for s in summaries])
            atomic_json(model_file,model)
        status='completed'
    except Exception as exc:status='failed';print(traceback.format_exc());atomic_json(folder/'failure.json',dict(error=str(exc),traceback=traceback.format_exc()))
    finally:plant.close();atomic_json(folder/'execution_status.json',dict(status=status,backend=args.backend,phase=args.phase,campaign=args.campaign,completed_runs=len(summaries),started_utc=started,ended_utc=datetime.now(timezone.utc).isoformat()))
    if status=='failed':raise SystemExit(2)
if __name__=='__main__':main()
