"""Freeze and sequentially execute the focused extension; retain negative outcomes."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import traceback

LAB=Path('/lab')
parser=argparse.ArgumentParser();parser.add_argument('--label',required=True);parser.add_argument('--dev',action='store_true')
args=parser.parse_args();root=LAB/'artifacts'/args.label;root.mkdir(parents=True,exist_ok=False)
matrix=[]
def add(group,backend,task,variant,transport,seed=2001,halfwidth=4.,fault='none',policy='expire_stop'):
    matrix.append(dict(group=group,backend=backend,task=task,variant=variant,transport=transport,
                       seed=seed,halfwidth_L=halfwidth,fault=fault,policy=policy,speed=2.))
for backend in ['f1tenth','metadrive']:
    for task in ['detour','blocked']:
        for seed in [2001,2002]:
            for variant,transport in [('stop_only','inprocess'),('planner','inprocess'),('planner','async_dds')]:
                add('matched',backend,task,variant,transport,seed)
    for fault in ['delay_120ms','pause_1s']:
        for policy in ['hold','expire_stop']:
            add('fault',backend,'detour','planner','async_dds',fault=fault,policy=policy)
    for width in [4.,2.5,2.2,1.8]:
        add('width',backend,'detour','planner','inprocess',halfwidth=width)
if args.dev:
    matrix=[dict(c) for c in matrix if c['backend']=='f1tenth' and
            ((c['group']=='matched' and c['task']=='detour' and c['seed']==2001 and c['transport']=='async_dds')
             or (c['group']=='fault' and c['fault']=='pause_1s'))]
for index,case in enumerate(matrix):case['id']=f"{index+1:02d}_{case['group']}_{case['backend']}_{case['task']}_{case['variant']}_{case['transport']}_{case['seed']}_{case['fault']}_{case['policy']}_w{case['halfwidth_L']:g}"
names=['focus_model.py','focus_run.py','focus_suite.py','focus_analyze.py','test_focus.py',
       'demo.py','pilot_obstacles.py','analyze_pilots.py']
snapshot=root/'frozen_source';snapshot.mkdir()
hashes={}
for name in names:
    path=LAB/name;hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest();shutil.copy2(path,snapshot/name)
manifest=dict(started_utc=datetime.now(timezone.utc).isoformat(),planned=len(matrix),cases=matrix,
              source_hashes=hashes,mode='fast in-process versus wall-paced asynchronous DDS',
              expiry_rule='80ms source-command age, wall monotonic clock; speed zero latched; steering remains controller-selected',
              fault_trigger='native progress x>=18L (injection/scoring only); 120ms response delay thereafter, or SIGSTOP/SIGCONT for 1 wall second',
              outcome_rule='No requirement that every case succeeds; process/audit validity is separate from task outcome.',
              repetition_scope='two development seeds for matched cases; one seed for faults and width sweep; exploratory',
              environment=dict(rmw=os.environ.get('RMW_IMPLEMENTATION'),domain=os.environ.get('ROS_DOMAIN_ID')))
(root/'manifest.json').write_text(json.dumps(manifest,indent=2))
(root/'cases').mkdir();statuses=[]
for i,case in enumerate(matrix):
    print(f"[{i+1}/{len(matrix)}] {case['id']}",flush=True)
    case_file=root/'cases'/(case['id']+'.json');case_file.write_text(json.dumps(case,indent=2))
    ctrl=None;runner=None
    ctrl_log=(root/(case['id']+'_controller.log')).open('w');run_log=(root/(case['id']+'_runner.log')).open('w')
    status=dict(id=case['id'])
    try:
        if case['transport']=='async_dds':
            ctrl=subprocess.Popen([sys.executable,'/lab/focus_run.py','controller'],stdout=ctrl_log,stderr=subprocess.STDOUT,start_new_session=True)
        cmd=[sys.executable,'/lab/focus_run.py','runner','--case',str(case_file),'--output',str(root/case['id'])]
        if ctrl:cmd+=['--controller-pid',str(ctrl.pid)]
        runner=subprocess.Popen(cmd,stdout=run_log,stderr=subprocess.STDOUT,start_new_session=True)
        status['returncode']=runner.wait(timeout=200)
    except Exception:status['error']=traceback.format_exc()
    finally:
        for process in [runner,ctrl]:
            if process and process.poll() is None:
                # A paused controller must be resumed before termination/cleanup.
                os.killpg(process.pid,signal.SIGCONT);os.killpg(process.pid,signal.SIGTERM)
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
        ctrl_log.close();run_log.close()
    statuses.append(status);(root/'execution_status.json').write_text(json.dumps(statuses,indent=2))
sources_unchanged=all(hashlib.sha256((LAB/name).read_bytes()).hexdigest()==sha for name,sha in hashes.items())
(root/'source_integrity.json').write_text(json.dumps(dict(unchanged=sources_unchanged),indent=2))
analysis=subprocess.run([sys.executable,'/lab/focus_analyze.py',str(root)])
print('Campaign finished:',root,flush=True)
sys.exit(1 if analysis.returncode or not sources_unchanged or any(s.get('returncode')!=0 for s in statuses) else 0)
