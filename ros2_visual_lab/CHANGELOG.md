# Change and evidence log for later online-document transfer

Date: 29 October 2026, Europe/Tallinn.

## Preservation

No paper edits were made. `Paper/main.tex` was hashed before development and
verified unchanged afterwards; see `artifacts/manuscript_before.sha256`.
All container access to `Vehicle_Control_SIL_Data_Code` was read-only.
Its complete package verifier passed after the samples: 864 evaluation runs,
24 calibration runs, six timestep checks, two fresh-environment checks,
six unchanged frozen files, 1,347 verified upstream files and 4,116 payload
files. See `artifacts/package_verification.json`.

No online document was modified, no repository was published and no full
evaluation campaign was rerun. No host packages or NVIDIA drivers were changed.
A new Docker image, `f1tenth-ros2-visual:humble`, was built. All lab files are
inside `ros2_visual_lab/`.

## Implemented development changes

1. Added a ROS Humble/Python 3.10 Docker image with both native simulators,
   Fast DDS, Cyclone DDS, RViz and visualization dependencies. The environment
   is separate from the delivered Python 3.12 experiment environment.
2. Reused the original native adapters, protocol, monitor models, observer,
   and `run_case` loop. Redirected the controller call at runtime to a separate
   ROS process through DDS topics. Checked every returned steering value and
   path index against the shared local controller before applying it.
3. Added an explicit lockstep request/reply protocol with request sequence IDs,
   a five-second wall-time failure limit and raw monotonic timing records.
   Reliable/volatile depth-10 JSON/String messages are prototype interfaces.
4. Added live DDS plotting and a shared RViz display. Both plants run in
   separate native processes. The viewers show normalized reference paths,
   corridor boundaries, native truth and estimated state used by control.
5. Added optional native MetaDrive 3D rendering. Hid original road graphics
   and navigation markers and added non-colliding visual ground/path geometry
   corresponding to the experiment. Native collision/actuator dynamics remain
   those of the delivered adapter. F1TENTH uses external plotting/RViz rather
   than the Gym race renderer.
6. Decoupled native drawing from physics: enabled the MetaDrive window every
   eight native steps (25 drawn frames per simulated second), disabled its
   internal FPS limiter, and retained wall pacing in the outer runner. All
   5 ms physics updates remain. The engine's on-screen FPS counter describes
   task updates and can show 200 even though drawing occurs every eighth step.
7. Restored three omitted MetaDrive Python modules from the exact upstream
   commit in a separate import overlay. Source URLs and hashes are recorded.
   This repairs a demonstrated runtime import failure in the cleaned package.
8. Added launch/build instructions, raw reports, field comparisons, screenshots,
   package integrity verification and a plan for a larger DDS experiment.

## Environment actually verified

- Host: Ubuntu 22.04.5, Linux 6.8, Python 3.10.12, ROS Humble available.
- GPU: NVIDIA GeForce RTX 3080, 10 GB, driver 550.144.03.
- Docker: 27.5.1 with NVIDIA runtime.
- Container OpenGL: NVIDIA renderer, direct rendering, OpenGL 4.6.
- GUI: X11 display `:1`, authorization-file mount; no `xhost +` required.
- The initial sandbox could not access NVIDIA devices or Docker. Both worked
  when executed with the required tool-level access outside that sandbox.

## Completed sample checks

All successful samples use the existing high-speed E0 timestamp-aware circle,
seed 300. This matches delivered case `campaign/A/A_E0_0037`. These are new
development records, excluded from the article's original 864-run count.

| Check | F1TENTH | MetaDrive |
| --- | --- | --- |
| Fast DDS headless smoke (`smoke_fast_03`) | Complete | Complete |
| Cyclone DDS headless smoke (`smoke_cyclone_01`) | Complete | Complete |
| Fast DDS live plot + RViz (`visual_fastdds_01`) | Complete | Complete |
| Fast DDS initial native 3D (`native_render_01`) | Complete | Complete |
| Final combined visual sample (`visual_final_01`) | Complete | Complete |

No sampled corridor violation occurred in these samples. There were 413
command exchanges per F1TENTH circle and 1,119 per MetaDrive circle. All remote
steering values and path indices matched the local shared controller exactly.

For the **final combined visual sample**, actual application round-trip times:

| Backend | Median, ms | p95, ms | Maximum, ms | RTT over 20 ms |
| --- | ---: | ---: | ---: | ---: |
| F1TENTH | 0.711 | 0.888 | 1.075 | 0/413 |
| MetaDrive | 0.709 | 0.837 | 1.027 | 0/1119 |

These are descriptive same-host, same-container measurements for one selected
case per backend, including Python serialization/executor/application work.
They do not isolate DDS internal latency, prove deadlines, or justify ranking
middleware implementations. The DDS transport may use shared memory.

The final F1TENTH run advanced 8.24 simulated seconds in 8.26 wall seconds;
MetaDrive advanced 22.36 simulated seconds in 22.40 wall seconds. Wall durations
exclude initialization/settling and include run-output work. The earlier
MetaDrive 3D implementation took 45.54 wall seconds before drawing was decoupled.

The rendered and headless Fast DDS runs have **identical uncompressed native
control CSV data** for both backends. Against the delivered data, the checked
F1TENTH time/state/command fields match exactly. MetaDrive's maximum position
differences are about 3.8e-6 m, estimated-position differences about 4.0e-6 m,
and intended-steering differences about 1.5e-6 rad. This is a new environment,
so these are bounded comparisons, not a claim of cross-machine byte identity.
See `artifacts/comparison_with_delivered.json` for individual fields.

## What can be transferred to the online document now

The following is **draft wording for review**, not an edit to the manuscript:

> A supplementary development prototype exercised the controller interface
> through ROS 2 Humble and DDS using separate native-runner and controller
> processes. Both F1TENTH and MetaDrive completed a selected high-speed circle
> case with source-time observation correction retained in the runner. Every
> steering command returned through DDS matched the shared controller's local
> calculation. A common RViz display and live plot subscribed to native truth
> and estimated state; MetaDrive additionally supported its native 3D view.
> The prototype used lockstep execution, with simulation waiting for each
> returned command. Its same-host application round-trip measurements therefore
> demonstrate middleware integration for these samples, rather than
> asynchronous deadline performance or physical Digital Twin synchronization.

Before adding this to the article, agree its role (supplementary demonstration
versus a new formal experiment), freeze the extension design, and update the
implementation-boundary statements consistently. The current paper correctly
describes the original in-process study and should not be silently rewritten
to imply that its 864 runs used ROS 2.

## Still needed for publication-grade DDS evidence

See `EXPERIMENT_PLAN.md`: typed timestamped interfaces, separate observer and
monitor nodes, asynchronous timing and command-expiry policy, controlled
transport/QoS/load conditions, repetitions and independent reconstruction.
Network timing, physical synchronization, HIL and real-world safety remain
outside the completed samples.

## Baseline report and advanced-simulation plan added

The user requested a consolidated report and a plan for harder environments,
obstacle avoidance and a justified simulation count. Added the dated baseline
report under `reports/`, a machine-readable snapshot of completed DDS runs,
and editable/readable report exports. The report includes an additional
`my_demo_01` pair present in the workspace: the inventory now records 13
successful native DDS executions, all of the same selected circle condition.
These remain development samples, not 13 independent scenario conditions.

The report proposes approximately 20 recorded pilot cases, followed if useful
by a frozen 144-case comparison and 48 targeted asynchronous communication
stress cases. These counts are proposals rather than a sample-size guarantee.
Obstacle planning, full-footprint collision scoring, command arbitration and
asynchronous execution remain planned. No new simulation was launched while
preparing this report. The manuscript and original package remain untouched.

## Twenty-case pilot implementation and execution

Implemented `run_pilots.sh`, a sequential Docker wrapper, plus the pilot
orchestrator, known-static-map obstacle path selection/speed supervision,
raw native-step logging and independent results analysis. Extended the demo
controller/runner with path, speed and seed selection for the geometry cases.
The paper and original package were not edited.

Four meaningful collision/planning tests passed, covering corner overlap,
thin-obstacle crossing between samples, rotation and blocked-route behaviour.
Four preliminary F1TENTH obstacle native cases passed in
`artifacts/obstacle_development_01`; these are development checks outside the
20-case batch.

Executed `bash ros2_visual_lab/run_pilots.sh pilot20_20261029_01`.
All 20 cases passed: 12 geometry circuits, four detours and four stops. Source
hashes were frozen before execution; output hashes and source hashes verified
after completion. Eight obstacle cases passed independent clearance/outcome
audits. No simulated collision or road departure was scored in these cases.
The manuscript checksum remained unchanged. New result reports are under
`reports/`, with the baseline report updated by a clearly labelled addendum.

This pilot is headless, unpaced, single-seed and lockstep. Obstacles are known
geometric map regions. Candidate paths are selected once at startup; there is
no native obstacle perception, online replanning or impact response model.
Stops are anticipated, not sudden-emergency braking tests. No claim of
asynchronous timing, controller superiority or real-world safety is made.

## Focused matched/asynchronous/fault/difficulty extension

The user authorised further experiments and documentation. Added a new,
separate implementation and pre-execution protocol for 24 matched component/
transport cases, eight fault-policy cases and eight fixed-planner road-width
cases. Added `run_focus.sh`, timestamped asynchronous native execution,
80 ms controller-command-age expiry with latched zero target speed, sequence
rejection and actual isolated controller SIGSTOP/SIGCONT injection. The
original 20-case sources/results were preserved.

Four policy/geometry unit checks passed. Three preliminary asynchronous
F1TENTH cases passed their independent audits in `focus_development_01` and
are separate from the full batch. Ran the frozen sequential 40-case batch
`focus40_20261029_01`; all native processes completed, source integrity stayed
unchanged and all 40 independent audits were valid. Outcomes were 17 goals
and 23 stops. No collision/departure was scored and all clearance gates held.

The expiry rule stopped all four fault cases; hold completed all four. Record
this as a policy/progress trade-off, not a collision-prevention superiority
claim. The width sweep identified different fixed-planner rejection points
for the two native body geometries. Maximum recorded asynchronous event-start
lag was 6.9 ms; this is not a full deadline guarantee. A source-age policy
audit, native geometry audit, requests/replies, applied commands and fault
events support those conclusions.

The separate nominal F1TENTH development run recorded 31.0 ms maximum start
lag; that exception remains in the reports and raw development outputs, outside
the 40-case campaign. The report therefore does not infer a general deadline
guarantee from the lower lag measured in the final batch.

Added the focused protocol and results report with presentation plots and
proposed later manuscript wording, plus a labelled update to the baseline
report. Presentation plots are separate derived artifacts; frozen batch files
and hashes remain untouched. The original package verifier passed again and
the manuscript checksum remained unchanged. The larger 192-run formal study,
perception, dynamic replanning and physical validation remain unexecuted.

## Separate highlighted manuscript revision

The user authorised editing a new TeX file while preserving `Paper/main.tex`.
Created `Paper/main_revised_experiments.tex`, integrated the 20/40-case evidence
throughout the article, added three tables and five separately packaged vector
figures, and produced highlighted/clean PDFs from the same source. Prepared
an upload-only ZIP and exact transfer instructions. The original bibliography
block, all 46 entries, all 63 citation groups and original quantitative result
table bodies are unchanged. The original main-file checksum still matches.

The detailed scope, checks, remaining author reviews and output paths are in
`reports/PAPER_REVISION_LOG_2026-10-29.md`. No online project was modified.
