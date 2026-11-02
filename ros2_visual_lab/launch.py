"""Run two native plants in isolated processes with separate DDS controllers."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument('--fast', action='store_true')
parser.add_argument('--visual', action='store_true')
parser.add_argument('--rviz', action='store_true')
parser.add_argument('--native-render', action='store_true')
parser.add_argument('--duration', type=float, default=40)
parser.add_argument('--backend', choices=['both', 'f1tenth', 'metadrive'], default='both')
parser.add_argument('--label', required=True)
args = parser.parse_args()
output = Path('/lab/artifacts') / args.label
output.mkdir(parents=True, exist_ok=False)
children, handles = [], []


def start(name, command):
    f = (output / (name + '.log')).open('w')
    handles.append(f)
    p = subprocess.Popen(command, stdout=f, stderr=subprocess.STDOUT, start_new_session=True)
    children.append(p)
    return p


try:
    launched = time.monotonic()
    if args.visual:
        start('viewer', [sys.executable, '/lab/demo.py', 'viewer', '--duration', str(args.duration),
                         '--output', str(output/'live_view.png')])
    if args.rviz:
        start('frames', ['ros2', 'run', 'tf2_ros', 'static_transform_publisher',
                         '--frame-id', 'map', '--child-frame-id', 'lab_origin'])
        start('rviz', ['rviz2', '-d', '/lab/dual.rviz'])
    runners = []
    for backend in (['f1tenth', 'metadrive'] if args.backend == 'both' else [args.backend]):
        start(backend+'_controller', [sys.executable, '/lab/demo.py', 'controller', '--backend', backend])
        command = [sys.executable, '/lab/demo.py', 'runner', '--backend', backend,
                   '--output', str(output/backend)]
        if args.fast:
            command.append('--fast')
        if args.native_render:
            command.append('--native-render')
        runners.append(start(backend+'_runner', command))
    deadline = time.monotonic() + max(180, args.duration+60)
    while any(p.poll() is None for p in runners):
        if time.monotonic() > deadline:
            raise TimeoutError('Runner wall-time budget exceeded')
        time.sleep(.2)
    if any(p.returncode for p in runners):
        raise RuntimeError('A native runner failed; inspect per-process logs')
    if args.visual:
        viewers = children[0]
        viewers.wait(timeout=args.duration+10)
        if viewers.returncode:
            raise RuntimeError('Viewer failed; inspect viewer.log')
    elif args.rviz:
        remaining = args.duration - (time.monotonic()-launched)
        if remaining > 0:
            time.sleep(remaining)
    print('Completed:', output, flush=True)
finally:
    for p in children:
        if p.poll() is None:
            os.killpg(p.pid, signal.SIGTERM)
    for p in children:
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            p.wait()
    for f in handles:
        f.close()
