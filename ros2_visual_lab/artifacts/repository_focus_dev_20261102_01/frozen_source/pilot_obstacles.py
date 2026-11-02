"""Map-based static-obstacle pilots with native plants and a DDS controller.

Geometric obstacles are common scored exclusion polygons, not native impact
models. No obstacle detector or asynchronous communication is claimed.
"""
import argparse
import csv
import gzip
import json
import math
from pathlib import Path
import time

import numpy as np
import rclpy
from rclpy.node import Node
from shapely.geometry import Polygon, box
from std_msgs.msg import String

from demo import CFG, QOS, ROOT, message  # Also installs the pinned MetaDrive import repair.
from plants import F1Plant, MetaPlant, PARAMS
import common

VERSION = 'static-map-pilot-v1'


def footprint(state, length, width):
    x, y, yaw = map(float, state[:3])
    corners = np.array([[length/2, width/2], [length/2, -width/2],
                        [-length/2, -width/2], [-length/2, width/2]])
    rotation = np.array([[math.cos(yaw), -math.sin(yaw)], [math.sin(yaw), math.cos(yaw)]])
    return Polygon(corners @ rotation.T + [x, y])


def swept(previous, current, length, width):
    hull = footprint(previous, length, width).union(footprint(current, length, width)).convex_hull
    angle = abs(common.wrap(float(current[2]-previous[2])))
    # Conservative cover of rotating corners for linear-centre/shortest-yaw interpolation.
    allowance = math.hypot(length/2, width/2)*(1-math.cos(angle/2)) + 1e-9
    return hull.buffer(allowance)


def scenario(L, kind):
    return dict(version=VERSION, kind=kind, wheelbase_m=L, road_halfwidth_m=4*L,
                obstacle_bounds=[27*L, (-4 if kind == 'blocked' else -.6)*L,
                                 29*L, (4 if kind == 'blocked' else .6)*L],
                goal_x_m=55*L, stop_x_m=20*L, clearance_required_m=.25*L,
                footprint_reference='native state/body centre, symmetric length/width rectangle',
                obstacle_source='known static map; no detector; geometric exclusion only')


def plan(spec, length, width):
    L = spec['wheelbase_m']
    obstacle = box(*spec['obstacle_bounds'])
    candidates = []
    for offset in [0., 1., -1., 1.5, -1.5, 2., -2., 2.5, -2.5]:
        x = np.arange(0, 62.001, .05)*L
        up = np.clip((x/L-10)/12, 0, 1)
        down = np.clip((x/L-34)/12, 0, 1)
        smooth = lambda u: 10*u**3-15*u**4+6*u**5
        y = offset*L*(smooth(up)-smooth(down))
        heading = np.arctan2(np.gradient(y), np.gradient(x))
        curvature = np.gradient(heading)/np.hypot(np.gradient(x), np.gradient(y))
        if max(abs(curvature))*L > math.tan(CFG['steering_limit_rad'])*.8:
            continue
        clear = min(footprint([a, b, h], length, width).distance(obstacle)
                    for a, b, h in zip(x[::4], y[::4], heading[::4]))
        road_clear = min(4*L-abs(b)-abs(math.sin(h))*length/2-abs(math.cos(h))*width/2
                         for b, h in zip(y, heading))
        valid = clear >= spec['clearance_required_m']+.15*L and road_clear >= .25*L
        candidates.append(dict(offset_L=offset, minimum_sampled_clearance_m=clear,
                               maximum_curvature_per_m=float(max(abs(curvature))), valid=bool(valid)))
        if valid:
            points = np.column_stack([x, y])
            return dict(points=points, heading=heading, spacing=.05*L,
                        length=float(np.hypot(np.diff(x), np.diff(y)).sum())), candidates
    # Blocked route: keep the original centreline and stop; never drive a rejected detour.
    if spec['kind'] != 'blocked':
        raise ValueError('No feasible candidate for detour scenario')
    x = np.arange(0, 62.001, .05)*L
    return dict(points=np.column_stack([x, x*0]), heading=x*0,
                spacing=.05*L, length=62*L), candidates


def decide(state, previous, path, spec, cruise):
    L = spec['wheelbase_m']
    delta, index = common.control(np.asarray(state), path, previous, L, CFG)
    target = cruise
    reason = 'track_selected_detour'
    if spec['kind'] == 'blocked':
        remaining = spec['stop_x_m']-state[0]
        time_scale = math.sqrt(L/CFG['f1tenth_wheelbase_m'])
        target = min(cruise, max(0., remaining*1.2/time_scale))
        if remaining < .2*L:
            target = 0.
        reason = 'blocked_route_slow_or_stop'
    return dict(delta=float(delta), index=int(index), speed=float(target), reason=reason)


def controller(args):
    node = Node('pilot_obstacle_controller')
    publisher = node.create_publisher(String, '/pilot/command', QOS)
    cache = {}

    def receive(msg):
        request = json.loads(msg.data)
        received = time.monotonic_ns()
        if not cache:
            cache['spec'] = request['scenario']
            cache['path'], cache['candidates'] = plan(request['scenario'], *request['dimensions'])
        result = decide(request['estimate'], request['previous'], cache['path'],
                        cache['spec'], request['cruise'])
        result.update(sequence=request['sequence'], received_ns=received,
                      reply_ns=time.monotonic_ns())
        publisher.publish(message(result))
    node.create_subscription(String, '/pilot/request', receive, QOS)
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()


def run_case(args):
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    plant = (F1Plant if args.backend == 'f1tenth' else MetaPlant)(CFG)
    node = Node('pilot_obstacle_runner')
    publisher = node.create_publisher(String, '/pilot/request', QOS)
    reply = {}
    node.create_subscription(String, '/pilot/command', lambda msg: reply.update(json.loads(msg.data)), QOS)
    try:
        L = plant.L
        scale = math.sqrt(L/CFG['f1tenth_wheelbase_m'])
        cruise = args.speed*scale
        rng = np.random.default_rng(args.seed)
        state = plant.reset(args.seed, [-cruise*CFG['settling_s'], 0., 0.], cruise)
        dimensions = ([PARAMS['length'], PARAMS['width']] if args.backend == 'f1tenth'
                      else [float(plant.env.agent.LENGTH), float(plant.env.agent.WIDTH)])
        length, width = dimensions
        spec = scenario(L, args.scenario)
        path, candidates = plan(spec, length, width)
        (output/'scenario.json').write_text(json.dumps(dict(**spec, dimensions_m=dimensions,
                           planner_candidates=candidates, selected_path=path['points'].tolist()), indent=2))
        estimate = state.copy()
        delta, target, index, sequence = 0., cruise, 0, 0
        obstacle = box(*spec['obstacle_bounds'])
        minimum = math.inf
        road_minimum = math.inf
        stopped_for = 0.
        outcome = 'timeout'
        rows, observations, timings = [], [], []
        previous_state = state.copy()
        dt = CFG['event_dt_s']
        deadline = time.monotonic()+20
        while publisher.get_subscription_count() < 1 or node.count_publishers('/pilot/command') < 1:
            if time.monotonic() > deadline:
                raise TimeoutError('Obstacle DDS discovery failed')
            rclpy.spin_once(node, timeout_sec=.02)
        started = time.monotonic()
        # Allow the entire open route plus ample time for a sustained stop.
        for tick in range(round((85*L/cruise+8*scale)/dt)):
            t = tick*dt
            if tick % 10 == 0:
                measured = state+rng.normal(0, [CFG['position_noise_wheelbases']*L]*2+
                                            [CFG['yaw_noise_rad'], CFG['speed_noise_wheelbases_s']*L])
                measured[2] = common.wrap(measured[2])
                measured[3] = max(0., measured[3])
                estimate = common.correct(estimate, measured, CFG['correction_gain'])
                observations.append([t, *measured])
            if tick % 4 == 0:
                sent = time.monotonic_ns()
                publisher.publish(message(dict(sequence=sequence, estimate=estimate.tolist(),
                    previous=index, scenario=spec, dimensions=dimensions, cruise=cruise)))
                timeout = time.monotonic()+5
                while reply.get('sequence') != sequence:
                    if time.monotonic() > timeout:
                        raise TimeoutError('Obstacle command response timed out')
                    rclpy.spin_once(node, timeout_sec=.01)
                returned = time.monotonic_ns()
                expected = decide(estimate, index, path, spec, cruise)
                if any(abs(reply[key]-expected[key]) > 1e-12 for key in ['delta', 'speed', 'index']):
                    raise ValueError('DDS/local obstacle controller disagreement')
                delta, target, index = reply['delta'], reply['speed'], reply['index']
                timings.append([sequence, t, sent, reply['received_ns'], reply['reply_ns'],
                                returned, (returned-sent)/1e6])
                sequence += 1
            # Retain every native step, including the five F1TENTH substeps per event.
            native_dt = plant.dt
            collision = False
            for substep in range(round(dt/native_dt)):
                state = plant.step(delta, target, native_dt)
                region = swept(previous_state, state, length, width)
                clearance = region.distance(obstacle)
                minimum = min(minimum, clearance)
                road_clearance = min(region.bounds[1]+spec['road_halfwidth_m'],
                                     spec['road_halfwidth_m']-region.bounds[3])
                road_minimum = min(road_minimum, road_clearance)
                now = t+(substep+1)*native_dt
                rows.append([now, *state, *estimate, delta, target, clearance,
                             road_clearance, int(region.intersects(obstacle)),
                             math.hypot(estimate[0]-state[0], estimate[1]-state[1])])
                previous_state = state.copy()
                if region.intersects(obstacle) or road_clearance < 0:
                    collision = True
                    outcome = 'obstacle_collision' if region.intersects(obstacle) else 'road_departure'
                    break
            estimate = common.propagate(estimate, delta, dt, L, target)
            if collision:
                break
            if args.scenario == 'detour' and state[0] >= spec['goal_x_m']:
                outcome = 'goal_reached'
                break
            stopped_for = stopped_for+dt if abs(state[3]) < .03*scale and target == 0 else 0.
            if args.scenario == 'blocked' and stopped_for >= .5:
                outcome = 'stopped'
                break
        fields = ['t','x','y','yaw','speed','estimate_x','estimate_y','estimate_yaw','estimate_speed',
                  'steering_rad','speed_target','swept_clearance_m','swept_road_clearance_m',
                  'collision','estimate_error_m']
        with gzip.open(output/'physics.csv.gz', 'wt') as f:
            writer = csv.writer(f); writer.writerow(fields); writer.writerows(rows)
        with gzip.open(output/'observations.csv.gz', 'wt') as f:
            writer = csv.writer(f); writer.writerow(['source_t','x','y','yaw','speed']); writer.writerows(observations)
        with (output/'dds_timing.csv').open('w') as f:
            writer = csv.writer(f)
            writer.writerow(['sequence','sim_t','send_monotonic_ns','controller_receive_ns',
                             'controller_reply_ns','runner_receive_ns','round_trip_ms'])
            writer.writerows(timings)
        times = np.asarray([r[-1] for r in timings])
        valid = outcome == ('goal_reached' if args.scenario == 'detour' else 'stopped')
        valid = valid and minimum >= spec['clearance_required_m'] and road_minimum >= 0
        report = dict(backend=args.backend, scenario=args.scenario, speed_case=args.speed,
            seed=args.seed, version=VERSION, outcome=outcome, passed=bool(valid),
            simulated_elapsed_s=rows[-1][0], wall_elapsed_s=time.monotonic()-started,
            minimum_swept_clearance_m=minimum, minimum_road_clearance_m=road_minimum,
            clearance_required_m=spec['clearance_required_m'], exchanges=len(timings),
            round_trip_median_ms=float(np.median(times)), round_trip_p95_ms=float(np.quantile(times,.95)),
            round_trip_max_ms=float(max(times)), final_position_m=state[:2].tolist(),
            final_speed_m_s=float(state[3]), dimensions_m=dimensions,
            native_metadata=plant.metadata, command_equivalence_checked=True,
            boundary='known static map; symmetric body rectangles; lockstep DDS; no perception or impact response')
        (output/'result.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2), flush=True)
    finally:
        plant.close()
        node.destroy_node()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('role', choices=['controller', 'runner'])
    parser.add_argument('--backend', choices=['f1tenth','metadrive'], default='f1tenth')
    parser.add_argument('--scenario', choices=['detour','blocked'], default='detour')
    parser.add_argument('--speed', type=float, choices=[1.,2.], default=1.)
    parser.add_argument('--seed', type=int, default=1001)
    parser.add_argument('--output', default='/lab/artifacts/obstacle_dev')
    args = parser.parse_args()
    rclpy.init()
    try:
        controller(args) if args.role == 'controller' else run_case(args)
    finally:
        rclpy.shutdown()
