"""Native in-process/asynchronous DDS extension with both clock domains logged."""
import argparse
import csv
import gzip
import heapq
import json
import math
import os
from pathlib import Path
import signal
import time

import numpy as np
import rclpy
from rclpy.node import Node
from shapely.geometry import box
from std_msgs.msg import String
from demo import CFG,QOS,message
from plants import F1Plant,MetaPlant,PARAMS
from pilot_obstacles import swept
from focus_model import make_spec,make_plan,decide,arbitrate,accept_reply
import common


def controller():
    node=Node('focus_controller')
    pub=node.create_publisher(String,'/focus/reply',QOS)
    cache={};pending=[]

    def receive(msg):
        request=json.loads(msg.data);received=time.monotonic_ns()
        if request['sequence']==-1:
            cache['spec']=request['spec']
            cache['path'],cache['must_stop'],_=make_plan(request['spec'],request['dimensions'],request['allow_detour'])
        response=decide(request['estimate'],request['previous'],cache['path'],cache['spec'],
                        request['cruise'],cache['must_stop'])
        response.update(sequence=request['sequence'],source_wall_ns=request['source_wall_ns'],
                        controller_received_ns=received,controller_finished_ns=time.monotonic_ns())
        due=time.monotonic_ns()+int(request.get('delay_ms',0)*1e6)
        heapq.heappush(pending,(due,request['sequence'],response))

    def release():
        while pending and pending[0][0]<=time.monotonic_ns():
            _,_,response=heapq.heappop(pending)
            response['published_ns']=time.monotonic_ns()
            pub.publish(message(response))
    node.create_subscription(String,'/focus/request',receive,QOS)
    node.create_timer(.001,release)
    try:rclpy.spin(node)
    finally:node.destroy_node()


def write_rows(path,fields,rows):
    opener=gzip.open if path.suffix=='.gz' else open
    with opener(path,'wt') as stream:
        writer=csv.writer(stream);writer.writerow(fields);writer.writerows(rows)


def runner(args):
    case=json.loads(Path(args.case).read_text());output=Path(args.output)
    output.mkdir(parents=True,exist_ok=False)
    (output/'case.json').write_text(json.dumps(case,indent=2))
    plant=(F1Plant if case['backend']=='f1tenth' else MetaPlant)(CFG)
    node=Node('focus_runner');received=[];paused=False
    pub=node.create_publisher(String,'/focus/request',QOS)
    node.create_subscription(String,'/focus/reply',lambda msg:received.append((time.monotonic_ns(),json.loads(msg.data))),QOS)
    requests=[];responses=[];controls=[];physics=[];observations=[];events=[]
    try:
        L=plant.L;scale=math.sqrt(L/CFG['f1tenth_wheelbase_m']);cruise=case['speed']*scale
        state=plant.reset(case['seed'],[-cruise*CFG['settling_s'],0,0],cruise)
        dimensions=([PARAMS['length'],PARAMS['width']] if case['backend']=='f1tenth'
                    else [float(plant.env.agent.LENGTH),float(plant.env.agent.WIDTH)])
        spec=make_spec(L,case['task'],case['halfwidth_L'])
        path,must_stop,candidates=make_plan(spec,dimensions,case['variant']!='stop_only')
        (output/'scenario.json').write_text(json.dumps(dict(**spec,dimensions_m=dimensions,
                  must_stop=must_stop,planner_candidates=candidates,selected_path=path['points'].tolist()),indent=2))
        estimate=state.copy();index=0;rng=np.random.default_rng(case['seed'])
        initial=decide(estimate,index,path,spec,cruise,must_stop)
        if case['transport']=='async_dds':
            deadline=time.monotonic()+20
            while pub.get_subscription_count()<1 or node.count_publishers('/focus/reply')<1:
                if time.monotonic()>deadline:raise TimeoutError('DDS discovery')
                rclpy.spin_once(node,timeout_sec=.01)
            pub.publish(message(dict(sequence=-1,source_wall_ns=time.monotonic_ns(),spec=spec,
                         dimensions=dimensions,allow_detour=case['variant']!='stop_only',
                         estimate=estimate.tolist(),previous=0,cruise=cruise)))
            while not received:
                if time.monotonic()>deadline:raise TimeoutError('DDS setup')
                rclpy.spin_once(node,timeout_sec=.01)
            initial=received.pop()[1]
            expected=decide(estimate,0,path,spec,cruise,must_stop)
            assert all(abs(initial[k]-expected[k])<1e-12 for k in ['delta','speed','index'])
        epoch=time.monotonic_ns()
        command=dict(initial,sequence=-1,source_wall_ns=epoch)
        dt=.005;last=state.copy();sequence=0;pending_requests={}
        latch=False;fault_wall=None;fault_sim=None;stop_for=0.;outcome='timeout'
        minimum=math.inf;road_min=math.inf;max_lag=0.;expired_steps=0;late_steps=0
        obstacle=box(*spec['obstacle_bounds']);length,width=dimensions
        for tick in range(round((85*L/cruise+8*scale)/dt)):
            t=tick*dt
            if case['transport']=='async_dds':
                remaining=(epoch+round(t*1e9)-time.monotonic_ns())/1e9
                if remaining>0:time.sleep(remaining)
                for _ in range(16):rclpy.spin_once(node,timeout_sec=0.)
            wall=time.monotonic_ns();lag=max(0.,(wall-epoch)/1e9-t) if case['transport']=='async_dds' else 0.
            max_lag=max(max_lag,lag);late_steps+=int(lag>.020)
            if fault_wall is None and case['fault']!='none' and state[0]>=18*L:
                fault_wall=wall;fault_sim=t
                events.append(dict(event='fault_start',sim_t=t,wall_ns=wall,source='scenario injection using native progress; unavailable to controller'))
                if case['fault']=='pause_1s':
                    os.kill(args.controller_pid,signal.SIGSTOP);paused=True
            if paused and wall-fault_wall>=1_000_000_000:
                os.kill(args.controller_pid,signal.SIGCONT);paused=False
                events.append(dict(event='controller_resumed',sim_t=t,wall_ns=wall))
            if tick%10==0:
                measured=state+rng.normal(0,[CFG['position_noise_wheelbases']*L]*2+
                                          [CFG['yaw_noise_rad'],CFG['speed_noise_wheelbases_s']*L])
                measured[2]=common.wrap(measured[2]);measured[3]=max(0.,measured[3])
                estimate=common.correct(estimate,measured,CFG['correction_gain'])
                observations.append([t,wall,*measured])
            # Validate every reply against its own recorded source state, not current truth.
            while received:
                arrival,response=received.pop(0)
                request=pending_requests[response['sequence']]
                expected=decide(request['estimate'],request['previous'],path,spec,cruise,must_stop)
                if any(abs(response[k]-expected[k])>1e-12 for k in ['delta','speed','index']):
                    raise ValueError('DDS command equivalence failure')
                accepted=accept_reply(response,command['sequence'],arrival)
                responses.append([response['sequence'],response['source_wall_ns'],response['controller_received_ns'],
                    response['controller_finished_ns'],response['published_ns'],arrival,int(accepted)])
                if accepted:command=response;index=response['index']
            if tick%4==0:
                request=dict(sequence=sequence,source_wall_ns=time.monotonic_ns(),estimate=estimate.tolist(),
                             previous=index,cruise=cruise,
                             delay_ms=120 if case['fault']=='delay_120ms' and fault_wall is not None else 0)
                pending_requests[sequence]=request
                requests.append([sequence,t,request['source_wall_ns'],*estimate,index,request['delay_ms']])
                if case['transport']=='async_dds':pub.publish(message(request))
                else:
                    command=dict(decide(estimate,index,path,spec,cruise,must_stop),sequence=sequence,
                                 source_wall_ns=request['source_wall_ns'])
                    index=command['index']
                sequence+=1
            application=time.monotonic_ns()
            delta,target,new_latch,expired=arbitrate(command,application,case['policy'],latch)
            if new_latch and not latch:
                events.append(dict(event='expiry_stop_latched',sim_t=t,wall_ns=application,
                                   command_source_wall_ns=command['source_wall_ns']))
            latch=new_latch;expired_steps+=int(expired)
            controls.append([t,application,command['sequence'],command['source_wall_ns'],
                command['delta'],command['speed'],delta,target,int(latch),int(expired),lag])
            collision=False
            for substep in range(round(dt/plant.dt)):
                state=plant.step(delta,target,plant.dt)
                region=swept(last,state,length,width)
                clearance=region.distance(obstacle)
                edge=min(region.bounds[1]+spec['road_halfwidth_m'],spec['road_halfwidth_m']-region.bounds[3])
                minimum=min(minimum,clearance);road_min=min(road_min,edge)
                sample_t=t+(substep+1)*plant.dt
                physics.append([sample_t,*state,delta,target,clearance,edge,int(region.intersects(obstacle))])
                last=state.copy()
                if region.intersects(obstacle) or edge<0:
                    outcome='obstacle_collision' if region.intersects(obstacle) else 'road_departure';collision=True;break
            estimate=common.propagate(estimate,delta,dt,L,target)
            if collision:break
            if state[0]>=spec['goal_x_m']:outcome='goal_reached';break
            stop_for=stop_for+dt if abs(state[3])<.03*scale and target==0 else 0.
            if stop_for>=.5 and not paused:outcome='stopped';break
        if paused:
            events.append(dict(event='controller_pause_censored_by_case_end',sim_t=physics[-1][0],wall_ns=time.monotonic_ns()))
        spec.update(dimensions_m=dimensions,must_stop=must_stop)
        report=dict(**case,outcome=outcome,goal_reached=outcome=='goal_reached',
            collision_free=minimum>0 and road_min>=0,clearance_gate_met=minimum>=.25*L and road_min>=0,
            minimum_swept_clearance_m=minimum,minimum_road_clearance_m=road_min,
            final_speed_m_s=float(state[3]),elapsed_sim_s=physics[-1][0],
            elapsed_wall_s=(time.monotonic_ns()-epoch)/1e9,max_start_lag_s=max_lag,
            event_starts_over_20ms_late=late_steps,expired_event_steps=expired_steps,
            expiry_latched=latch,fault_injected=fault_wall is not None,fault_sim_t=fault_sim,
            requests=len(requests),replies=len(responses),must_stop=must_stop,native_metadata=plant.metadata,
            command_equivalence_checked=True,
            scope='known static map; native dynamics; asynchronous DDS wall-paced or fast in-process; geometric impact score')
        (output/'result.json').write_text(json.dumps(report,indent=2))
        (output/'events.json').write_text(json.dumps(events,indent=2))
        write_rows(output/'physics.csv.gz',['t','x','y','yaw','speed','steering_rad','speed_target',
                    'swept_clearance_m','swept_road_clearance_m','collision'],physics)
        write_rows(output/'observations.csv.gz',['source_t','wall_ns','x','y','yaw','speed'],observations)
        write_rows(output/'requests.csv.gz',['sequence','sim_t','source_wall_ns','x','y','yaw','speed','previous_index','delay_ms'],requests)
        write_rows(output/'responses.csv.gz',['sequence','source_wall_ns','controller_received_ns','controller_finished_ns',
                    'published_ns','arrival_ns','accepted'],responses)
        write_rows(output/'controls.csv.gz',['sim_t','application_ns','sequence','source_wall_ns','requested_delta',
                    'requested_speed','applied_delta','applied_speed','expiry_latched','expired','start_lag_s'],controls)
        print(case['id'],outcome,'clearance/L',minimum/L,'max lag s',max_lag,flush=True)
    finally:
        if paused:os.kill(args.controller_pid,signal.SIGCONT)
        plant.close();node.destroy_node()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('role',choices=['controller','runner'])
    parser.add_argument('--case');parser.add_argument('--output');parser.add_argument('--controller-pid',type=int)
    args=parser.parse_args();rclpy.init()
    try:controller() if args.role=='controller' else runner(args)
    finally:rclpy.shutdown()
