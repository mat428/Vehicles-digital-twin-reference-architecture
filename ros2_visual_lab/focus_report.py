"""Post-campaign descriptive report; never changes the frozen batch or paper."""
from collections import Counter
import csv
import gzip
import json
from pathlib import Path
import sys

root=Path(sys.argv[1]);destination=Path(sys.argv[2]);summary=json.loads((root/'summary.json').read_text())
cases=summary['cases']
lines=['---','title: "Focused native simulation campaign: matched comparisons, DDS faults and operating boundary"',
       'date: "29 October 2026 — Europe/Tallinn"','lang: en-GB','---','',
       '# Outcome and scope','',
       f"Executed batch `{root.name}`: {summary['planned']} planned cases; {summary['audits_valid']} valid independent case audits.",
       '', 'The three questions were whether the planner changes task completion relative to stopping-only control, '
       'how asynchronous command delivery and expiry change outcomes, and where a fixed candidate planner rejects a narrower road. '
       'These are exploratory finite-case results, with two development seeds in the matched comparisons and one in the other groups. '
       'Adverse outcomes are retained. No real-world safety or statistical robustness claim is made.', '',
       '# Matched comparison results','',
       '| Backend | Task | Variant / transport | Goals | Stops | Other outcomes |',
       '| --- | --- | --- | ---: | ---: | --- |']
for backend in ['f1tenth','metadrive']:
    for task in ['detour','blocked']:
        for variant,transport in [('stop_only','inprocess'),('planner','inprocess'),('planner','async_dds')]:
            selected=[c for c in cases if c['group']=='matched' and c['backend']==backend and c['task']==task
                      and c['variant']==variant and c['transport']==transport]
            count=Counter(c.get('outcome','execution failure') for c in selected)
            other={k:v for k,v in count.items() if k not in ['goal_reached','stopped']}
            lines.append(f"| {backend} | {task} | {variant} / {transport} | {count['goal_reached']}/{len(selected)} | {count['stopped']}/{len(selected)} | {other or 'None'} |")
lines += ['', 'Goal completion and collision-free stopping are different outcomes. The stopping-only variant deliberately has no detour planner; '
          'it can correctly stop for a feasible obstacle while failing to reach the route goal. All variants share their respective '
          'map, speed setting, noise seed, tracking controller and stopping rule. The transport comparison uses the same planner and authority rules, '
          'but in-process execution is unpaced and asynchronous DDS execution is wall-paced. Differences cannot be attributed to isolated middleware latency alone.', '',
          '# Fault and command-policy results','',
          '| Backend | Fault | Policy | Outcome | Minimum clearance / L | Max command age, ms | Max start lag, ms |',
          '| --- | --- | --- | --- | ---: | ---: | ---: |']
for c in cases:
    if c['group']=='fault':
        lines.append(f"| {c['backend']} | {c['fault']} | {c['policy']} | {c.get('outcome','missing')} | {c.get('minimum_clearance_L',0):.4f} | {c.get('command_age_max_ms',0):.1f} | {1000*c.get('max_start_lag_s',0):.1f} |")
lines += ['', '![Command age during the two fault types; the dotted line is the 80 ms policy threshold.]('
          'focus40_command_age.png){width=16cm}', '',
          'The age shown is the latest controller command\'s age at arbitration, before the speed override. '
          'It is not the age of the supervisor\'s newly generated zero-speed decision. The corresponding native-speed response is shown below.', '',
          '![Native speed response under hold and expire-stop policies.](focus40_speed_response.png){width=16cm}', '',
          'Delayed replies receive 120 ms of added wall-time delay. The isolated controller process is paused with SIGSTOP and resumed '
          'with SIGCONT after one wall second. Faults begin when native progress reaches x=18L; that progress is an injection/scoring input '
          'and is not available to the controller. Command expiry is based on application monotonic time minus the source request time. '
          'Expire-stop latches a zero target speed once that age exceeds 80 ms; steering remains controller-selected. Hold continues '
          'using the latest accepted sequence-numbered command. A zero target is not an instantaneous physical stop. '
          'The 80 ms value applies to command-source age here; the original paper\'s 80 ms observation-freshness check is a different diagnostic. '
          'The fixed wall-time faults represent different travel distances in wheelbases across the plants, so their responses do not rank simulator quality.', '',
          '# Fixed-planner road-width boundary','',
          '| Backend | Road half-width / L | Planner requires stop | Outcome | Minimum clearance / L |',
          '| --- | ---: | --- | --- | ---: |']
for c in cases:
    if c['group']=='width':
        lines.append(f"| {c['backend']} | {c['halfwidth_L']:g} | {c.get('must_stop')} | {c.get('outcome')} | {c.get('minimum_clearance_L',0):.4f} |")
lines += ['', '![Task outcomes and clearance across the sampled road widths.]('
          'focus40_width_boundary.png){width=16cm}', '',
          'This is the boundary of the fixed candidate set and screening margins, not a proof that no other planner could pass. '
          'Road half-width is varied while obstacle size and native body geometry remain fixed within each backend. '
          'Body dimensions differ after wheelbase normalization, so a cross-backend decision difference does not rank simulator fidelity.', '',
          '# Implementation and independent checks','',
          'The campaign protocol was written before execution. A source snapshot and matrix were frozen in the batch folder. '
          'All native physics steps, synthetic observations, source requests, received replies, applied commands, fault events '
          'and both clock domains were retained. The original package was mounted read-only and the paper was not edited.', '',
          'A separate standard-library audit reconstructs body clearance with separating axes and segment distances at retained endpoints '
          'and interval midpoints. It checks terminal goals/stops, conservative swept clearance, reply timestamp order and injected-delay timing. '
          'It independently reconstructs every command-age expiry and latched zero-speed override. Online checks compare every DDS command '
          'with the shared controller evaluated at that request\'s recorded source estimate. This is command-transport equivalence, not '
          'an independent implementation of the planner.', '',
          'Four policy/geometry unit checks and three asynchronous F1TENTH development runs preceded the campaign. Their outputs are separate '
          'and excluded from the 40-case count. The development pause/hold case reached the goal while pause/expiry stopped; this informed '
          'the interpretation of intervention as a measured trade-off rather than an assumed universal improvement.', '',
          '# Timing limits and interpretation','']
async_cases=[c for c in cases if c['transport']=='async_dds' and 'max_start_lag_s' in c]
if async_cases:
    maximum=max(c['max_start_lag_s'] for c in async_cases)
    warnings=[c for c in async_cases if c['max_start_lag_s']>.020]
    lines += [f"Across the {len(async_cases)} asynchronous cases, maximum recorded event-start lag was {maximum*1000:.1f} ms. "
              f"{len(warnings)} cases had at least one event start more than 20 ms behind the requested simulation/wall-time schedule.", '']
lines += ['The runner continues physics without waiting for a reply; clock pacing is nevertheless limited by host scheduling and computation. '
          'Report the retained pacing lag and elapsed wall/simulation times before asserting a real-time deadline. '
          'This experiment measures an entire Python/ROS/application path, not isolated DDS transport performance, and does not compare middleware vendors.', '',
          'Obstacles are known static geometric exclusion regions. Candidate planning occurs once at setup. '
          'There is no native perception, online replanning, impact response or physical-vehicle counterpart. '
          'Initial stopped-state clearance is deliberately generous. These are not sudden-emergency braking tests. '
          'The finite sample sizes cannot support road-level collision probabilities or general robustness guarantees.', '',
          '# Evidence and next decisions','',
          f"The authoritative raw batch is `ros2_visual_lab/artifacts/{root.name}/`. See `manifest.json`, `frozen_source/`, "
          '`summary.json`, `RESULTS.md`, each `independent_audit.json`, raw compressed CSV files, `source_integrity.json` and `output_hashes.json`. '
          'The image ID and console output are stored alongside the batch folder. This narrative is a derived post-campaign report; '
          'the frozen case matrix and sources remain unchanged.', '',
          'Before paper transfer, review each outcome, check pacing exceptions, and decide whether the matched application comparisons '
          'are sufficient or whether a matched wall-paced in-process baseline is also needed. A formal repeated campaign should use '
          'new frozen seeds and explicit effect/uncertainty requirements. Do not tune on these cases and then describe the same outcomes as held-out validation.', '',
          'The original 864 runs remain the original in-process study. These new results require their own methods, scope, run counts '
          'and explicit speed-command authority. All manuscript text remains unchanged pending review.']
destination.write_text('\n'.join(lines)+'\n')
print(destination)
