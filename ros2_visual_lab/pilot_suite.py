"""Sequential pilot orchestrator: records the matrix before execution."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import traceback

LAB = Path('/lab')
parser = argparse.ArgumentParser()
parser.add_argument('--label', required=True)
parser.add_argument('--only', choices=['all','geometry','obstacles','obstacle-dev'], default='all')
args = parser.parse_args()
output = LAB/'artifacts'/args.label
output.mkdir(parents=True, exist_ok=False)
matrix = []
for backend in ['f1tenth','metadrive']:
    if args.only in ['all','geometry']:
        for track in ['circle','ellipse','wavy']:
            for speed in [1.,2.]:
                matrix.append(dict(backend=backend, family='geometry', track=track, speed=speed, seed=1001))
    if args.only in ['all','obstacles','obstacle-dev']:
        for scenario in ['detour','blocked']:
            for speed in [1.,2.]:
                matrix.append(dict(backend=backend, family='obstacle', scenario=scenario, speed=speed, seed=1001))
if args.only == 'obstacle-dev':
    matrix = [case for case in matrix if case['backend'] == 'f1tenth']
for i, case in enumerate(matrix):
    case['id'] = f"{i+1:02d}_{case['backend']}_{case.get('track',case.get('scenario'))}_v{int(case['speed'])}"
manifest = dict(started_utc=datetime.now(timezone.utc).isoformat(), matrix=matrix,
    mode='sequential native pilots; lockstep ROS 2/DDS; headless, unpaced simulation',
    seed_scope='single development seed 1001; no independent statistical evaluation',
    middleware=os.environ.get('RMW_IMPLEMENTATION'),
    source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
                   [LAB/name for name in ['pilot_suite.py','pilot_obstacles.py','demo.py','analyze_pilots.py']]})
(output/'manifest.json').write_text(json.dumps(manifest,indent=2))
records = []
for case in matrix:
    print(f"[{len(records)+1}/{len(matrix)}] {case['id']}", flush=True)
    folder = output/case['id']
    controller_log = (output/(case['id']+'_controller.log')).open('w')
    runner_log = (output/(case['id']+'_runner.log')).open('w')
    script = '/lab/demo.py' if case['family'] == 'geometry' else '/lab/pilot_obstacles.py'
    options = ['--backend',case['backend']]
    options += ['--track',case['track']] if case['family']=='geometry' else ['--scenario',case['scenario']]
    ctrl = subprocess.Popen([sys.executable,script,'controller',*options],
                             stdout=controller_log,stderr=subprocess.STDOUT,start_new_session=True)
    command = [sys.executable,script,'runner',*options,'--speed',str(case['speed']),
               '--seed',str(case['seed']),'--output',str(folder)]
    if case['family']=='geometry':
        command.append('--fast')
    runner = None
    status = dict(**case)
    try:
        runner = subprocess.Popen(command,stdout=runner_log,stderr=subprocess.STDOUT,start_new_session=True)
        status['returncode'] = runner.wait(timeout=240)
        status['execution'] = 'completed' if status['returncode'] == 0 else 'failed'
    except Exception:
        status.update(execution='failed', error=traceback.format_exc())
    finally:
        for proc in [runner,ctrl]:
            if proc is not None and proc.poll() is None:
                os.killpg(proc.pid,signal.SIGTERM)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid,signal.SIGKILL);proc.wait()
        controller_log.close();runner_log.close()
    records.append(status)
    (output/'execution_status.json').write_text(json.dumps(records,indent=2))
    # Continue after a case failure; preserve a complete attempted-case inventory.
analysis = subprocess.run([sys.executable,'/lab/analyze_pilots.py',str(output)])
print('Pilot outputs:',output,flush=True)
sys.exit(1 if analysis.returncode or any(r['execution']!='completed' for r in records) else 0)
