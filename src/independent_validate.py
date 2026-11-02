"""Standard-library audit, independent of runtime Monitor/predictor and pandas analysis."""
import csv,gzip,hashlib,json,math,statistics,bisect
from pathlib import Path
from collections import deque
ROOT=Path(__file__).resolve().parents[1]

def read_csv(p):
    with gzip.open(p,'rt') as f:return [{k:float(v) for k,v in row.items()} for row in csv.DictReader(f)]
def wrap(x):return math.atan2(math.sin(x),math.cos(x))
def quantile(v,p):
    v=sorted(v);i=(len(v)-1)*p;a=math.floor(i);b=math.ceil(i)
    return v[a]+(v[b]-v[a])*(i-a)
def predict(s,delta,dt,L,target):
    x,y,yaw,speed=s;rate=speed*math.tan(delta)/L;mid=yaw+rate*dt/2
    return [x+speed*math.cos(mid)*dt,y+speed*math.sin(mid)*dt,wrap(yaw+rate*dt),speed+(target-speed)*min(dt/.2,1)]
def blend(s,m,gain):
    out=[a+gain*(b-a) for a,b in zip(s,m)];out[2]=wrap(s[2]+gain*wrap(m[2]-s[2]));return out

def geometry(name,L):
    points=[];arc=[0.]
    for i in range(4001):
        theta=i*(2*math.pi/4000)
        if name=='circle':x,y=8*math.sin(theta),8*(1-math.cos(theta))
        elif name=='ellipse':x,y=10*math.sin(theta),6*(1-math.cos(theta))
        else:
            r=8*(1+.15*math.cos(3*theta));x,y=r*math.sin(theta),9.2-r*math.cos(theta)
        if points:arc.append(arc[-1]+math.hypot(x-points[-1][0],y-points[-1][1]))
        points.append((x,y))
    sampled=[]
    for k in range(math.ceil(arc[-1]/.05)):
        position=k*.05;j=bisect.bisect_right(arc,position);j=min(len(arc)-1,j)
        fraction=(position-arc[j-1])/(arc[j]-arc[j-1])
        sampled.append(tuple(L*(points[j-1][axis]+fraction*(points[j][axis]-points[j-1][axis])) for axis in [0,1]))
    heading=[math.atan2(sampled[(i+1)%len(sampled)][1]-sampled[(i-1)%len(sampled)][1],sampled[(i+1)%len(sampled)][0]-sampled[(i-1)%len(sampled)][0]) for i in range(len(sampled))]
    return sampled,heading

def check_geometry(raw,s,cfg,cache):
    key=(s['track'],s['wheelbase_m'])
    if key not in cache:cache[key]=geometry(*key)
    points,heading=cache[key];n=len(points);previous=0;violated=False
    for r in raw:
        ids=range(max(0,previous-8),previous+60)
        index=min(ids,key=lambda i:(points[i%n][0]-r['x'])**2+(points[i%n][1]-r['y'])**2)
        dx=r['x']-points[index%n][0];dy=r['y']-points[index%n][1]
        error=-math.sin(heading[index%n])*dx+math.cos(heading[index%n])*dy
        previous=max(0,index)
        assert abs(error-r['cte_m'])<1e-8 and abs(previous/n-r['progress_fraction'])<1e-10
        violated=violated or abs(error)>cfg['corridor_halfwidth_wheelbases']*s['wheelbase_m']
    assert violated==s['boundary_violation']
    assert (not violated and previous>=n)==s['completed']

def monitor_rows(obs,cfg,model,raw,L,onset=None):
    window=deque(maxlen=cfg['monitor_window_packets']);count=0;rows=[];qualified=0
    for o in obs:
        if not math.isfinite(o['delivery_t']):continue
        window.append(o)
        if len(window)<window.maxlen:
            assert o['yaw_alarm']==0
            continue
        a,b=window[0],window[-1];span=b['source_t']-a['source_t']
        rate=wrap(b['yaw_measured']-a['yaw_measured'])/span
        integral=0.
        dt=cfg['event_dt_s']
        for i,j in zip(window,list(window)[1:]):
            start=i['source_t'];end=j['source_t']
            for tick in range(round(start/dt),round(end/dt)):
                lo=tick*dt;hi=lo+dt
                command=raw[min(len(raw)-1,int(round(lo/cfg['control_dt_s'],8)))]['delta_intended_rad']
                v0=i['speed_measured']+(j['speed_measured']-i['speed_measured'])*(lo-start)/(end-start)
                v1=i['speed_measured']+(j['speed_measured']-i['speed_measured'])*(hi-start)/(end-start)
                integral+=(hi-lo)*(v0+v1)/2*math.tan(command)/L
        ref=integral/span
        res=rate-model['gain']*ref;count=count+1 if abs(res)>model['threshold_rad_s'] else 0
        assert abs(rate-b['yaw_rate_measured'])<1e-9 and abs(ref-b['yaw_rate_reference'])<1e-9
        assert abs(res-b['yaw_residual'])<1e-9 and int(count>=cfg['persistent_measurements'])==b['yaw_alarm']
        assert abs(a['source_t']-b['window_start_t'])<1e-9
        qualified=qualified+1 if onset is not None and a['source_t']>=onset-1e-9 and abs(res)>model['threshold_rad_s'] else 0
        assert int(qualified>=cfg['persistent_measurements'])==b['qualified_yaw_alarm']
        rows.append((b,rate,ref))
    return rows

def replay_states(raw,obs,s,cfg):
    dt=cfg['event_dt_s'];L=s['wheelbase_m'];model_L=L*(1+s.get('mismatch',0)/100);target=s['actual_target_speed_m_s']
    first=raw[0];initial=[first[k] for k in ['x','y','yaw','speed']]
    corrected=initial[:];stale=initial[:];free=initial[:];history=deque(maxlen=100)
    deliveries={round(o['delivery_t']/dt):o for o in obs if math.isfinite(o['delivery_t'])}
    sources={round(o['source_t']/dt):o for o in obs};controls={round(r['t']/dt):r for r in raw}
    latest_source=0.;q=0.;delta=0.;max_difference=0.;yaw_alarm=False;first_yaw=None;first_age=None;false=0
    for tick in range(round(raw[-1]['t']/dt)+1):
        t=tick*dt
        if tick in sources:assert abs(sources[tick]['q_cumulative']-q)<1e-8
        if tick in controls:
            record=controls[tick]
            assert abs(math.hypot(corrected[0]-record['x'],corrected[1]-record['y'])-record['pre_error_m'])<1e-8
        if tick in deliveries:
            o=deliveries[tick];m=[o[k] for k in ['x_measured','y_measured','yaw_measured','speed_measured']];r=m[:]
            for source_tick,command in history:
                if round(o['source_t']/dt)<=source_tick<tick:r=predict(r,command,dt,model_L,target)
            corrected=blend(corrected,r,cfg['correction_gain']);stale=blend(stale,m,cfg['correction_gain'])
            latest_source=o['source_t'];yaw_alarm=bool(o['yaw_alarm'])
            active=s.get('fault','none')!='none' and t>=s['fault_onset_s']
            if yaw_alarm and t>=s['metric_start_s']:
                if active and o['qualified_yaw_alarm'] and first_yaw is None:first_yaw=t-s['fault_onset_s']
                if not active:false+=1
        age=t-latest_source;age_alarm=age>cfg['age_threshold_s']+1e-9
        if age_alarm and t>=s['fault_onset_s'] and first_age is None:first_age=t-s['fault_onset_s']
        if tick in controls:
            r=controls[tick]
            values=[(corrected,[r[k] for k in ['dt_x','dt_y','dt_yaw','dt_speed']]),(stale[:2],[r['naive_x'],r['naive_y']]),(free[:2],[r['free_x'],r['free_y']])]
            difference=max(abs(a-b) for first,second in values for a,b in zip(first,second));max_difference=max(max_difference,difference)
            assert difference<1e-8,(s['id'],t,difference)
            assert abs(age-r['source_age_s'])<1e-9 and int(age_alarm)==r['age_alarm'] and int(yaw_alarm)==r['yaw_alarm']
            delta=r['delta_intended_rad']
            expected=delta+(math.radians(s['magnitude']) if s.get('fault')=='steering' and t>=s['fault_onset_s'] else 0)
            expected=max(-cfg['steering_limit_rad'],min(cfg['steering_limit_rad'],expected))
            assert abs(expected-r['delta_delivered_rad'])<1e-9
        if tick==round(raw[-1]['t']/dt):break
        q+=math.tan(delta)/L*dt;history.append((tick,delta))
        corrected=predict(corrected,delta,dt,model_L,target);stale=predict(stale,delta,dt,model_L,target);free=predict(free,delta,dt,model_L,target)
    for actual,stored in [(first_yaw,s['first_yaw_alarm_delay_s']),(first_age,s['first_age_alarm_delay_s'])]:
        assert (actual is None and stored is None) or (actual is not None and stored is not None and abs(actual-stored)<1e-8)
    assert false==s['pre_fault_yaw_alarm_deliveries']
    assert s['fault_detected']==(first_yaw is not None)
    assert s['within_1s_detected']==(first_yaw is not None and first_yaw<=1.)
    assert s['age_detected']==(first_age is not None)
    return max_difference

def main():
    cfg=json.loads((ROOT/'configs/protocol.json').read_text());freeze=json.loads((ROOT/'docs/design_freeze.json').read_text())
    ph=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest();assert ph==freeze['protocol_sha256']
    for name in ['configs/protocol.json','docs/EXPERIMENT_DESIGN.md','src/run.py','src/plants.py','src/common.py','src/monitor.py']:
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==freeze['files'][name]
    audits=[];refits=[];total=0;maximum=0.;geometry_cache={}
    for backend in ['f1tenth','metadrive']:
        model=json.loads((ROOT/'results'/backend/'monitor_model.json').read_text());samples=[]
        cal=ROOT/'results'/backend/'calibration/A'
        for entry in model['calibration']:
            s=json.loads((cal/(entry['id']+'.json')).read_text());o=read_csv(cal/s['observations_file'])
            # Calibration logs were generated with gain 1 / initial floor.
            refit_model={'gain':1.,'threshold_rad_s':cfg['yaw_residual_threshold_rad_s']}
            for packet,rate,ref in monitor_rows(o,cfg,refit_model,read_csv(cal/s['raw_file']),s['wheelbase_m']):
                if packet['window_start_t']>=s['metric_start_s']:samples.append((rate,ref))
            for field in ['raw','observations']:
                assert hashlib.sha256((cal/s[field+'_file']).read_bytes()).hexdigest()==entry[field+'_sha256']
        gain=sum(a*b for a,b in samples)/sum(b*b for a,b in samples)
        threshold=max(cfg['yaw_residual_threshold_rad_s'],quantile([abs(a-gain*b) for a,b in samples],cfg['calibration_quantile']))
        assert len(samples)==model['samples'] and abs(gain-model['gain'])<1e-10 and abs(threshold-model['threshold_rad_s'])<1e-10
        refits.append(dict(backend=backend,gain=gain,threshold_rad_s=threshold,samples=len(samples),runs=len(model['calibration'])))
        for campaign in ['A','B']:
            folder=ROOT/'results'/backend/'campaign'/campaign
            for p in sorted(folder.glob('*.json')):
                if p.stem in ['execution_status','failure']:continue
                s=json.loads(p.read_text());raw=read_csv(folder/s['raw_file']);obs=read_csv(folder/s['observations_file'])
                for field in ['raw','observations']:assert hashlib.sha256((folder/s[field+'_file']).read_bytes()).hexdigest()==s[field+'_sha256']
                assert s['protocol_sha256']==ph and s['model']==model
                monitor_rows(obs,cfg,model,raw,s['wheelbase_m'],s['fault_onset_s'] if s.get('fault','none')!='none' else None);maxdiff=replay_states(raw,obs,s,cfg);maximum=max(maximum,maxdiff)
                check_geometry(raw,s,cfg,geometry_cache)
                eligible=[r for r in raw if r['t']>=s['metric_start_s']]
                for field,column in [('track_rmse_m','cte_m'),('dt_post_rmse_m','post_error_m'),('naive_rmse_m','naive_error_m'),('free_rmse_m','free_error_m')]:
                    metric=math.sqrt(sum(r[column]**2 for r in eligible)/len(eligible));assert abs(metric-s[field])<1e-10
                for r in raw:
                    for prefix,field in [('dt','post_error_m'),('naive','naive_error_m'),('free','free_error_m')]:
                        assert abs(math.hypot(r[prefix+'_x']-r['x'],r[prefix+'_y']-r['y'])-r[field])<1e-9
                total+=1;audits.append(dict(backend=backend,campaign=campaign,id=s['id'],passed=True,max_observer_replay_difference=maxdiff))
    assert total==864
    result=dict(all_checks_pass=True,primary_runs=total,calibration_refits=refits,
                max_observer_replay_difference=maximum,independence='standard-library CSV, own equations; no runtime Monitor/predictor imports',audit=audits)
    (ROOT/'results/independent_validation.json').write_text(json.dumps(result,indent=2));print({k:v for k,v in result.items() if k!='audit'})
if __name__=='__main__':main()
