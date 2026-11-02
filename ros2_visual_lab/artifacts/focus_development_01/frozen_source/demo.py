"""Separate DDS controller and native runner, reusing the unmodified study loop.

This is lockstep integration: simulation waits for the command. Measured wall
times are transport/application round trips, not simulated observation delay.
"""
import argparse
import csv
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import importlib.abc
import importlib.util

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from std_msgs.msg import String
from geometry_msgs.msg import Point
from visualization_msgs.msg import Marker, MarkerArray

import common
import run as experiment
from plants import F1Plant, MetaPlant

ROOT = Path('/evidence')
CFG = json.loads((ROOT / 'configs/protocol.json').read_text())
QOS = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)


class RestoredExamples(importlib.abc.MetaPathFinder):
    """Resolve only the omitted package using unchanged pinned upstream files."""
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'metadrive.examples':
            restored = Path('/lab/upstream_restore/examples')
            return importlib.util.spec_from_file_location(fullname, restored/'__init__.py',
                                                          submodule_search_locations=[str(restored)])


sys.meta_path.insert(0, RestoredExamples())


class RenderedMetaPlant(MetaPlant):
    """Add only visual geometry and a window to the original native adapter."""
    def __init__(self, cfg):
        import metadrive
        self.render_ticks = 0
        original = metadrive.MetaDriveEnv

        def rendered(config):
            config.update(use_render=True, show_terrain=False, show_skybox=False,
                          window_size=(1100, 760), camera_dist=14)
            config['vehicle_config'].update(show_navi_mark=False, show_dest_mark=False,
                                            show_line_to_dest=False, show_line_to_navi_mark=False)
            return original(config)

        metadrive.MetaDriveEnv = rendered
        try:
            super().__init__(cfg)
        finally:
            metadrive.MetaDriveEnv = original

    def reset(self, *args):
        state = super().reset(*args)
        from panda3d.core import CardMaker, LineSegs
        engine = self.env.engine
        engine.force_fps.disable()  # The outer runner paces simulation time.
        for block in self.env.current_map.blocks:
            block.origin.hide()
        floor = CardMaker('visual_only_flat_plane')
        floor.setFrame(-150, 150, -150, 150)
        node = engine.render.attachNewNode(floor.generate())
        node.setP(-90)
        node.setZ(-.02)
        node.setColor(.17, .23, .28, 1)
        node.setLightOff(100)
        node.setShaderOff(100)
        node.setTwoSided(True)
        path = common.track('circle', self.L)
        for side, color in [(0, (1., .8, .15, 1.)), (-.75, (.8, .8, .8, 1.)),
                             (.75, (.8, .8, .8, 1.))]:
            line = LineSegs('visual_reference_path')
            line.setThickness(3.)
            line.setColor(*color)
            points = path['points'].copy()
            points[:, 0] -= np.sin(path['heading'])*side*self.L
            points[:, 1] += np.cos(path['heading'])*side*self.L
            for i, point in enumerate(np.vstack([points, points[0]])):
                (line.moveTo if i == 0 else line.drawTo)(float(point[0]), float(point[1]), .025)
            line_node = engine.render.attachNewNode(line.create())
            line_node.setLightOff(100)
            line_node.setShaderOff(100)
        return state

    def step(self, *args):
        # Draw at 25 simulated frames/s; keep all native 5 ms physics steps.
        self.render_ticks += 1
        self.env.engine.win.setActive(self.render_ticks % 8 == 0)
        return super().step(*args)


def message(value):
    return String(data=json.dumps(value, allow_nan=False))


def configuration(backend, track_name='circle'):
    L = CFG[backend + '_wheelbase_m']
    return L, common.track(track_name, L)


def controller(backend, track_name='circle'):
    L, path = configuration(backend, track_name)
    node = Node(backend + '_controller')
    pub = node.create_publisher(String, '/' + backend + '/command', QOS)

    def receive(msg):
        received = time.monotonic_ns()
        request = json.loads(msg.data)
        delta, index = common.control(np.array(request['state']), path,
                                      request['previous'], L, CFG)
        pub.publish(message(dict(sequence=request['sequence'], delta=delta,
                                 index=index, received_ns=received,
                                 reply_ns=time.monotonic_ns())))

    node.create_subscription(String, '/' + backend + '/state_request', receive, QOS)
    print(backend, 'DDS controller ready', flush=True)
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()


class Bridge:
    def __init__(self, backend, plant, pace):
        self.backend, self.plant, self.pace = backend, plant, pace
        self.node = Node(backend + '_native_runner')
        self.publisher = self.node.create_publisher(String, '/' + backend + '/state_request', QOS)
        self.visual = self.node.create_publisher(String, '/' + backend + '/visual', QOS)
        self.markers = self.node.create_publisher(MarkerArray, '/lab/markers', QOS)
        self.reply = None
        self.node.create_subscription(String, '/' + backend + '/command', self.receive, QOS)
        self.sequence = 0
        self.rows = []
        self.t = 0.
        self.started = None
        self.max_difference = 0.
        self.trail = []

    def receive(self, msg):
        self.reply = json.loads(msg.data)

    def remote_control(self, state, path, previous, L, cfg):
        # DDS discovery is outside the measured control exchanges.
        deadline = time.monotonic() + 20
        while self.publisher.get_subscription_count() < 1 or self.node.count_publishers('/' + self.backend + '/command') < 1:
            if time.monotonic() > deadline:
                raise TimeoutError('DDS discovery failed')
            rclpy.spin_once(self.node, timeout_sec=.05)
        self.reply = None
        sent = time.monotonic_ns()
        self.publisher.publish(message(dict(sequence=self.sequence,
                                            state=state.tolist(), previous=int(previous))))
        deadline = time.monotonic() + 5
        while self.reply is None or self.reply['sequence'] != self.sequence:
            if time.monotonic() > deadline:
                raise TimeoutError('No matching DDS command within five wall seconds')
            rclpy.spin_once(self.node, timeout_sec=.01)
        returned = time.monotonic_ns()
        reply = self.reply
        expected, expected_index = common.control(state, path, previous, L, cfg)
        difference = abs(expected - reply['delta'])
        self.max_difference = max(self.max_difference, difference)
        if difference > 1e-12 or reply['index'] != expected_index:
            raise ValueError('Remote control does not match shared controller')
        self.rows.append([self.sequence, self.t, sent, reply['received_ns'],
                          reply['reply_ns'], returned, (returned-sent)/1e6])
        truth = self.plant.read()
        self.visual.publish(message(dict(t=self.t, truth=truth.tolist(), estimate=state.tolist(),
                                         L=L, backend=self.backend)))
        if self.sequence % 2 == 0 and self.markers.get_subscription_count():
            self.publish_markers(truth, state, path, L)
        self.sequence += 1
        return reply['delta'], reply['index']

    def publish_markers(self, truth, estimate, path, L):
        # Explicit wheelbase-normalized display, separate from SI control data.
        offset = 0 if self.backend == 'f1tenth' else 24
        result = MarkerArray()

        def marker(identity, kind, color):
            m = Marker()
            m.header.frame_id = 'map'
            m.ns = self.backend
            m.id = identity
            m.type = kind
            m.action = Marker.ADD
            m.pose.orientation.w = 1.
            m.color.r, m.color.g, m.color.b, m.color.a = color
            result.markers.append(m)
            return m

        for identity, side in [(0, 0), (1, -.75), (2, .75)]:
            m = marker(identity, Marker.LINE_STRIP, (.4, .5, .6, 1.))
            m.scale.x = .035
            for p, heading in zip(path['points'], path['heading']):
                m.points.append(Point(x=float(p[0]/L - math.sin(heading)*side + offset),
                                      y=float(p[1]/L + math.cos(heading)*side), z=0.))
            m.points.append(m.points[0])
        self.trail.append(Point(x=float(truth[0]/L + offset), y=float(truth[1]/L), z=.06))
        trail = marker(3, Marker.LINE_STRIP, (.1, .8, .9, 1.))
        trail.scale.x = .06
        trail.points = self.trail[-3000:]
        for identity, state, color in [(4, truth, (.1, .8, .9, 1.)),
                                        (5, estimate, (1., .55, .1, .8))]:
            m = marker(identity, Marker.ARROW, color)
            m.pose.position.x = float(state[0]/L + offset)
            m.pose.position.y = float(state[1]/L)
            m.pose.position.z = .18 if identity == 4 else .35
            m.pose.orientation.z = math.sin(float(state[2])/2)
            m.pose.orientation.w = math.cos(float(state[2])/2)
            m.scale.x, m.scale.y, m.scale.z = 1.5, .45, .35
        text = marker(6, Marker.TEXT_VIEW_FACING, (1., 1., 1., 1.))
        text.pose.position.x = float(offset)
        text.pose.position.y = -2.
        text.scale.z = .65
        text.text = f'{self.backend} | t={self.t:.2f}s | cyan: native, orange: estimate | units: L'
        self.markers.publish(result)

    def reset(self, *args):
        state = self.plant.reset(*args)
        self.started = time.monotonic()
        return state

    def step(self, delta, speed, dt):
        state = self.plant.step(delta, speed, dt)
        self.t += dt
        if self.pace:
            remaining = self.started + self.t - time.monotonic()
            if remaining > 0:
                time.sleep(remaining)
        return state

    def __getattr__(self, name):
        return getattr(self.plant, name)


def runner(args):
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    plant_class = F1Plant if args.backend == 'f1tenth' else (RenderedMetaPlant if args.native_render else MetaPlant)
    plant = plant_class(CFG)
    bridge = Bridge(args.backend, plant, not args.fast)
    model = json.loads((ROOT / 'results' / args.backend / 'monitor_model.json').read_text())
    case = dict(id='dds_circle' if args.track == 'circle' else 'dds_'+args.track,
                campaign='demo', group='E0', track=args.track,
                speed_case=args.speed, seed=args.seed, mode='timestamp')
    if args.native_render and args.track != 'circle':
        raise ValueError('Native rendered overlay currently supports circle only; use pilot plot outputs for other paths')
    experiment.control = bridge.remote_control
    try:
        summary, _ = experiment.run_case(bridge, CFG, case, output, model)
        with (output / 'dds_timing.csv').open('w') as f:
            writer = csv.writer(f)
            writer.writerow(['sequence', 'sim_t', 'send_monotonic_ns', 'controller_receive_ns',
                             'controller_reply_ns', 'runner_receive_ns', 'round_trip_ms'])
            writer.writerows(bridge.rows)
        times = np.array([row[-1] for row in bridge.rows])
        report = dict(backend=args.backend, exchanges=len(times),
                      round_trip_median_ms=float(np.median(times)),
                      round_trip_p95_ms=float(np.quantile(times, .95)),
                      round_trip_max_ms=float(max(times)),
                      round_trips_over_20ms=int(sum(times > 20)),
                      maximum_steering_difference_rad=bridge.max_difference,
                      completed=summary['completed'], boundary_violation=summary['boundary_violation'],
                      wall_elapsed_s=time.monotonic()-bridge.started,
                      simulated_elapsed_s=summary['elapsed_s'],
                      rmw=os.environ.get('RMW_IMPLEMENTATION'),
                      mode='lockstep; DDS state request and command; observer/monitor in runner',
                      note='Same-host application RTT; simulation waits for reply; no deadline guarantee.')
        (output / 'dds_report.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2), flush=True)
        if args.native_render and args.backend == 'metadrive':
            from panda3d.core import Filename
            plant.env.engine.win.setActive(True)
            plant.env.engine.graphicsEngine.renderFrame()
            plant.env.engine.win.saveScreenshot(Filename(str(output/'native_metadrive.png')))
    finally:
        plant.close()
        bridge.node.destroy_node()


def viewer(args):
    import matplotlib
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation
    node = Node('native_visual_viewer')
    fig, axes = plt.subplots(1, 2, figsize=(13, 6))
    fig.suptitle('LIVE native physics over ROS 2/DDS | cyan: truth, orange: controller estimate')
    items = {}
    for backend, ax in zip(['f1tenth', 'metadrive'], axes):
        L, path = configuration(backend)
        points = path['points']/L
        ax.plot(points[:, 0], points[:, 1], '--', color='gray', lw=1)
        for side in [-.75, .75]:
            ax.plot(points[:, 0]-np.sin(path['heading'])*side,
                    points[:, 1]+np.cos(path['heading'])*side, color='lightgray', lw=1)
        trail, = ax.plot([], [], color='#10a9bb', lw=1.5)
        truth, = ax.plot([], [], 'o', color='#10a9bb', ms=9)
        estimate, = ax.plot([], [], 'x', color='#ed8d15', ms=9)
        ax.set(xlim=(-10, 10), ylim=(-3, 19), xlabel='x / wheelbase', ylabel='y / wheelbase')
        ax.set_aspect('equal')
        ax.grid(alpha=.2)
        items[backend] = dict(ax=ax, L=L, trail=trail, truth=truth, estimate=estimate,
                              x=[], y=[], latest=None)

        def receive(msg, backend=backend):
            data = json.loads(msg.data)
            item = items[backend]
            item['latest'] = data
            item['x'].append(data['truth'][0]/item['L'])
            item['y'].append(data['truth'][1]/item['L'])
        node.create_subscription(String, '/' + backend + '/visual', receive, QOS)

    start = time.monotonic()

    def update(_):
        for _ in range(100):
            rclpy.spin_once(node, timeout_sec=0.)
        for backend, item in items.items():
            data = item['latest']
            if data:
                item['trail'].set_data(item['x'], item['y'])
                item['truth'].set_data([data['truth'][0]/item['L']], [data['truth'][1]/item['L']])
                item['estimate'].set_data([data['estimate'][0]/item['L']], [data['estimate'][1]/item['L']])
                item['ax'].set_title(f"{backend}: simulation {data['t']:.2f}s")
        if args.duration and time.monotonic()-start > args.duration:
            fig.savefig(args.output, dpi=150)
            plt.close(fig)

    animation = FuncAnimation(fig, update, interval=40, cache_frame_data=False)
    plt.tight_layout()
    plt.show()
    node.destroy_node()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('role', choices=['controller', 'runner', 'viewer'])
    parser.add_argument('--backend', choices=['f1tenth', 'metadrive'], default='f1tenth')
    parser.add_argument('--output', default='/lab/artifacts/viewer.png')
    parser.add_argument('--duration', type=float, default=0)
    parser.add_argument('--fast', action='store_true')
    parser.add_argument('--native-render', action='store_true')
    parser.add_argument('--track', choices=['circle', 'ellipse', 'wavy'], default='circle')
    parser.add_argument('--speed', type=float, choices=[1., 2.], default=2.)
    parser.add_argument('--seed', type=int, default=300)
    args = parser.parse_args()
    rclpy.init()
    try:
        if args.role == 'controller':
            controller(args.backend, args.track)
        elif args.role == 'runner':
            runner(args)
        else:
            viewer(args)
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()
