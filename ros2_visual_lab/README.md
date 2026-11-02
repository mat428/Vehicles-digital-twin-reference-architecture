# Native vehicle simulation with ROS 2/DDS and visualization

This is a separate development experiment, created 29 October 2026. The paper
and delivered experiment package were preserved during execution. This folder
contains the extension source and retained outputs. Start with the
[repository reproduction guide](../docs/ros2_dds/README.md) for dataset setup,
record verification, results and limitations. Set `EVIDENCE_DIR` to the extracted
primary reviewer package before invoking the Docker wrappers.

`CHANGELOG.md` and `EXPERIMENT_PLAN.md` are historical development documents;
proposed studies there are not all executed. The completed campaign manifests
and result reports identify what was actually run.

## Run the focused comparison, fault and difficulty campaign

The subsequent focused comparison/fault/difficulty campaign is available with:

```bash
bash ros2_visual_lab/run_focus.sh my_focus_batch_01
```

It runs 40 cases sequentially: 24 matched stopping-only/in-process-planner/
asynchronous-DDS-planner cases, eight delay/pause policy cases, and eight
road-width cases. Asynchronous cases advance native physics against monotonic
wall time without waiting for replies. They can take several minutes in total.
In-process cases are unpaced. The script uses Fast DDS on domain 75 and
preserves the original package read-only. Case failures/collisions are reported
as outcomes; process failures or invalid audits cause a nonzero wrapper exit.

The 80 ms source-command-age supervisor latches a zero speed target; it does
not stop native motion instantaneously. Hold-last-command is the comparison.
Delay injection is 120 ms of extra controller reply delay. Pause injection
uses SIGSTOP/SIGCONT on the isolated controller process for one wall second;
no other host process is signalled. Both start at native progress x>=18L for
scenario injection only. A case ending during the pause records censoring.
The protocol is in `focus_protocol.md` and copied into each frozen source
snapshot. Setup and DDS discovery occur before the measured epoch.

The focused output folder contains `manifest.json`, `frozen_source/`, per-case
source requests/replies, applied commands with both clocks, every native
physics step, observations, intervention/fault events, independent audits,
`summary.json`, `RESULTS.md`, plots and output hashes. `source_integrity.json`
checks that code remained fixed throughout execution. Image ID and console log
are saved next to the batch folder. Use a new label on every invocation.

Tests for the focused policy layer are in `test_focus.py`. Three separate
asynchronous F1TENTH development checks can be run with a fresh label and
`--dev`; these are not counted in the 40-case campaign.

## Run all 20 development pilots sequentially

From the project root:

```bash
bash ros2_visual_lab/run_pilots.sh my_pilot_batch_01
```

The script uses the existing image or builds it if absent, then runs 12
geometry cases (circle/ellipse/wavy, two speeds, two native backends) and eight
static-obstacle cases (detour/blocked route, two speeds, two native backends).
It uses Fast DDS, isolated domain 74, development seed 1001, headless native
physics and unpaced lockstep execution. It does not need a display or GPU.
Every native case has a separate controller process. Existing output labels
are refused; use a fresh label for each batch.

Outputs are under `artifacts/<label>/`. `RESULTS.md` and `pilot_summary.json`
summarise all planned cases, including failures. `geometry_trajectories.png`
and `obstacle_trajectories.png` show saved native trajectories. Each obstacle
case includes its static map, selected candidate path, every native physics
sample, observation records, command timing, outcome and an independent
clearance/outcome audit. The wrapper returns a nonzero status if a process or
pilot gate fails, after attempting the remaining cases and producing results.

The default 20-case matrix is captured before execution in `manifest.json`,
with source hashes; the wrapper records the Docker image ID. The analyzer
records output hashes. Keep code fixed throughout a batch; use a new batch
label and version after repairs. Development/debug batches remain separate.

Obstacle pilots use a **known static geometric exclusion map**, a smooth
candidate-detour planner and a speed-authorised blocked-route supervisor.
They do not enable native obstacle perception or model physical impacts.
The symmetric body rectangle uses each plant's native length and width.
The scorer conservatively checks swept footprints between retained native
steps under linear-centre/shortest-yaw interpolation; a separate standard-
library SAT/segment-distance audit checks endpoints and midpoints. Neither
is a claim of exact continuous physical contact dynamics.

The detour goal is 55 wheelbases forward on an open road of half-width 4L,
with an obstacle from x=27L to 29L and y=-0.6L to +0.6L. The blocked case spans
the full width and targets a stop at x=20L, well upstream of the obstacle.
Both require at least 0.25L body clearance. Detours are selected from lateral
offset candidates with smooth transitions and curvature screening. The
planner uses measured/estimated pose, not native truth. Native truth is used
only for initialization, synthetic measurements and scoring. The blocked
case tests an anticipated stop from a known map; it is not a sudden-emergency
braking or perception test. Original yaw/freshness diagnostic models are not
recalibrated or asserted to cover these new obstacle cases.

Subset commands for separate development labels:

```bash
bash ros2_visual_lab/run_pilots.sh my_geometry_01 --only geometry
bash ros2_visual_lab/run_pilots.sh my_obstacles_01 --only obstacles
```

`analyze_pilots.py` can regenerate summaries in the same image without running
physics. Freeze or archive the derived outputs if changing the analyzer.

## Run the sample

From the project root:

```bash
docker build -t f1tenth-ros2-visual:humble ros2_visual_lab
RMW_IMPLEMENTATION=rmw_fastrtps_cpp bash ros2_visual_lab/run.sh \
  --visual --rviz --native-render --duration 60 --label my_visual_sample
```

Use a **new label** for each run; existing output directories are not replaced.
The two native plants execute concurrently in separate Python processes. You
will see a live two-panel plot, RViz with both plants, and MetaDrive's native
3D window. The plot closes after the selected duration; the launcher stops its
other windows after the samples and plot finish. Each sample is one high-speed
circle, seed 300, with timestamp-aware observation correction.

F1TENTH uses its native RaceCar physics and the external plot/RViz viewers;
it does not open the original Gym race renderer. MetaDrive can additionally
open its native Panda3D/Bullet 3D window. Its visual ground and centerline
correspond to the experiment's flat plane rather than the original road map.
The plot and RViz use wheelbase-normalized positions and distinguish native
truth (cyan) and estimated state used by control (orange). Control data use SI.

This launcher requires Docker, NVIDIA Container Toolkit, and the current X11
display's authorization file. It uses your user ID for output ownership and
mounts the delivered data/code read-only. It neither installs host packages nor
changes host ROS settings. It uses Docker's isolated default networking and
ROS domain 73; no host network or privileged container is needed.

For the faster common visualization without the native 3D window:

```bash
RMW_IMPLEMENTATION=rmw_fastrtps_cpp bash ros2_visual_lab/run.sh \
  --visual --rviz --duration 40 --label my_rviz_sample
```

For a headless physics/DDS check:

```bash
RMW_IMPLEMENTATION=rmw_fastrtps_cpp bash ros2_visual_lab/run.sh --fast --label my_fastdds_check
RMW_IMPLEMENTATION=rmw_cyclonedds_cpp bash ros2_visual_lab/run.sh --fast --label my_cyclone_check
EVIDENCE_DIR="$EVIDENCE_DIR" python3 ros2_visual_lab/compare_results.py
```

`--backend f1tenth` or `--backend metadrive` selects one native plant. Specify
`RMW_IMPLEMENTATION` explicitly to make the middleware choice unambiguous.
The host environment here selected Cyclone DDS by default.

## What passes through DDS

```text
native plant + original observations, observer and monitors
    -> /<backend>/state_request -> separate pure-pursuit controller process
    <- /<backend>/command       <- steering and reference-path index
    -> /<backend>/visual        -> live plot
    -> /lab/markers             -> RViz
```

The original `run_case` loop is reused without editing it. The lab redirects
its controller call to a synchronous DDS exchange. Every returned command is
checked against the local shared controller calculation before it is applied.
Both native adapters retain their original physics step sizes and actuator
semantics. The corrected observer state, rather than native truth, is sent to
the controller. Native truth goes to visualization/scoring only.

The prototype uses reliable, volatile, depth-10 `std_msgs/String` messages
containing JSON. Messages carry request sequence IDs; stale replies are not
accepted as a current command. A missing response fails the run after five
wall seconds. Production interfaces should use typed messages with explicit
source/delivery timestamps, frames, units and validity intervals.

**This sample and the 20 pilots are lockstep:** simulation waits for each command. ROS transport wall
time is measured separately from simulated time. DDS delay in these lockstep runs does not
increase the simulated observation age. The observer and fault monitors are
still inside the native-runner process. Consequently this is a control-path
integration demonstration, not a complete distributed twin or asynchronous
timing/safety experiment. Same-container processes may use DDS shared memory;
there is no claim of measured physical-network latency.

Native MetaDrive rendering is limited to one frame every eight native steps
(25 frames per simulated second); physics still advances every 5 ms. The
runner controls pacing. Rendering load can still slow execution; compare wall
and simulation durations in each report.

## Evidence

- `artifacts/visual_fastdds_01/live_view.png`: saved live DDS plot.
- `artifacts/rviz_uncovered.png`: RViz window captured during native execution.
- `artifacts/native_render_01/metadrive/native_metadrive.png`: first native 3D sample.
- `artifacts/visual_final_01/`: combined demo after rendering refinement.
- `artifacts/*/<backend>/dds_report.json`: completion, command checks and RTT summaries.
- `artifacts/*/<backend>/dds_timing.csv`: per-exchange monotonic timestamps.
- `artifacts/*/<backend>/dds_circle*`: new native control/observation records.
- `artifacts/comparison_with_delivered.json`: field-wise comparison against matched delivered records.
- `artifacts/container-environment.txt`, `opengl.txt`, `docker-build.log`: environment evidence.
- `artifacts/package_verification.json`: post-experiment integrity check of the original package.

The prototype uses ROS Humble/Python 3.10 with a separate demo dependency set.
It does not reproduce the paper's Python 3.12 dependency lock. Installed Python
versions are recorded in `container-environment.txt`; base image/build details
are in `docker-build.log`.

## MetaDrive packaging repair

The cleaned package omits `metadrive.examples`, but its manual-control import
chain requires that package even when manual control is disabled. Three
unchanged source files from the exact pinned upstream commit are retained in
`upstream_restore/`, with source URLs and SHA-256 hashes in `provenance.json`.
A narrow import resolver supplies the missing package only. No fake dynamics,
replacement expert, or changes to the delivered files are used. Expert model
weights are not included; expert/manual takeover is outside this demo. These
files retain MetaDrive's upstream Apache-2.0 licensing.

The first failed attempts and their logs are preserved. `smoke_fast_01` failed
because ROS logging defaulted to an unwritable home directory; `smoke_fast_02`
then exposed the missing MetaDrive imports. Later successful runs apply both
repairs. RViz can report inability to create `//.rviz2` under this unregistered
container user; its supplied configuration still loads and renders. No home
directory or host permissions were changed to suppress this cosmetic message.
