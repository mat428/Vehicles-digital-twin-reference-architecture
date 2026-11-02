# ROS 2/DDS simulation extension

This extension was executed on 29 October 2026 and added to the repository on
2 November 2026. It complements the primary 864 evaluation runs; those runs
remain a separate in-process study. The manuscript is maintained separately.

## Recorded results

| Campaign | Design | Recorded outcome |
| --- | --- | --- |
| 20 pilots | Two native plants; circle, ellipse and wavy paths at two speeds; known-map detour and blocked-route tasks | 12 geometry circuits completed, four detour goals, four stops; 20/20 pilot gates |
| 40 focused cases | 24 matched comparisons, eight delay/pause policy cases, eight road-width cases | 17 goals, 23 stops; 40/40 valid independent audits; all met the 0.25-wheelbase clearance gate |

Read the [pilot results](PILOT20_RESULTS_2026-10-29.md),
[focused results](FOCUSED_CAMPAIGN_RESULTS_2026-10-29.md) and
[protocol](FOCUSED_CAMPAIGN_PROTOCOL_2026-10-29.md) for methods, numerical results
and interpretation. These reports were written at execution time; statements
about paper transfer describe that historical stage.

The planner enabled the selected detours while stopping-only control stopped.
The nominal asynchronous implementation matched local task outcomes. Under the
tested faults, expiry-stop intervened and hold also completed the routes; these
cases do not demonstrate that expiry prevented a collision caused by hold.

## Inspect and verify without Docker or a dataset download

From the repository root, using Python 3.10 or later:

```bash
python3 ros2_visual_lab/verify_extension.py
python3 ros2_visual_lab/verify_extension.py --recompute
```

Both commands use the standard library. The first verifies the extension
file manifest, original batch output hashes, source snapshots and recorded
case counts. The second also recomputes geometry tracking RMSE and the eight
pilot-obstacle and 40 focused case audits from raw records. Audits write into
temporary copies; the retained evidence is untouched. These checks do not
rerun native physics or independently reimplement the planner/controller.

The repository's root `verify_package.py` and `MANIFEST_SHA256.csv` describe
the downloadable primary package, not this Git checkout or this extension.

## Prepare new native runs

The tested environment is Linux, Docker, ROS 2 Humble and Python 3.10 inside
the container. No host ROS installation is required. Headless runs need no
GPU. The optional visual example requires NVIDIA Container Toolkit and an
accessible X11 display. A Windows-native extension workflow has not been tested;
the separate Windows guide concerns the primary experiment.

1. Download and extract `Vehicle_Control_SIL_Reviewer_Package_v1.zip` from
   the primary dataset link in the [repository README](../../README.md#dataset-downloads).
2. Set `EVIDENCE_DIR` to the extracted directory containing `src/`, `vendor/`,
   `configs/` and `results/`, not to the ZIP or its enclosing download folder.
3. Verify that package using its own verifier before running new experiments.

```bash
export EVIDENCE_DIR="/absolute/path/to/extracted/Vehicle_Control_SIL_Data_Code"
python3 "$EVIDENCE_DIR/verify_package.py"
docker build -t f1tenth-ros2-visual:humble ros2_visual_lab
```

The wrappers accept any extracted folder name through `EVIDENCE_DIR`. Without
that variable they look for `Vehicle_Control_SIL_Data_Code/` in this checkout.
The package is mounted read-only at `/evidence`; new outputs go to
`ros2_visual_lab/artifacts/<new-label>/`. Existing labels are refused.
The primary runner, plant adapters, common functions and protocol in the
repository match the local package used for the extension byte for byte.

Run either complete campaign sequentially:

```bash
bash ros2_visual_lab/run_pilots.sh my_pilot20_01
bash ros2_visual_lab/run_focus.sh my_focus40_01
```

For a smaller smoke check or optional visualization:

```bash
RMW_IMPLEMENTATION=rmw_fastrtps_cpp bash ros2_visual_lab/run.sh --fast --label my_smoke_01
RMW_IMPLEMENTATION=rmw_cyclonedds_cpp bash ros2_visual_lab/run.sh --fast --label my_cyclone_01
RMW_IMPLEMENTATION=rmw_fastrtps_cpp bash ros2_visual_lab/run.sh \
  --visual --rviz --native-render --duration 60 --label my_visual_01
```

The visual example runs both plants concurrently in separate processes;
the campaigns run cases sequentially. F1TENTH uses native physics with external
plot/RViz visualization; MetaDrive can open its native 3D window.

Run the eight policy/geometry unit checks in the same image:

```bash
docker run --rm --init \
  -e ROS_LOG_DIR=/tmp/ros_logs -e XDG_CACHE_HOME=/tmp/cache \
  -v "$EVIDENCE_DIR:/evidence:ro" -v "$PWD/ros2_visual_lab:/lab:ro" \
  f1tenth-ros2-visual:humble \
  python3 -m unittest test_pilot_obstacles test_focus -v
```

Docker base/apt packages are not locked to an immutable image digest. Python
dependencies are pinned separately in `requirements-demo.txt`; historical image
IDs and environment records are retained. Rebuilds may change numerical or
timing results. Do not substitute the primary Python 3.12 dependency lock.

## Evidence map

Paths below are relative to `ros2_visual_lab/`:

| Location | Contents |
| --- | --- |
| `artifacts/pilot20_20261029_01/` | Frozen 20-case matrix, compressed native/observation logs, DDS timing, independent audits, summary, plots and payload hashes |
| `artifacts/focus40_20261029_01/` | 40-case matrix, frozen sources, native/observation/request/reply/control logs, events, clock records, audits, outcomes and hashes |
| `artifacts/focus_development_01/` | Three preliminary asynchronous checks, including the nominal 31 ms scheduling-lag observation; excluded from 40 |
| `artifacts/obstacle_development_01/` | Four preliminary native obstacle checks; excluded from 20 |
| `artifacts/repository_smoke_20261102_01/`, `repository_focus_dev_20261102_01/` | Two native smoke runs and three asynchronous reproduction checks of the repository launchers; excluded from both campaign counts |
| Other named `artifacts/` folders | Initial Fast DDS/Cyclone DDS and visualization samples, including failed setup attempts; excluded from both campaign counts |
| `artifacts/*_image.txt`, `*_console.log` | Historical image identifiers and sequential campaign logs |
| `artifacts/comparison_with_delivered.json` | Selected state/command comparison against the primary circle case |
| `artifacts/container-environment.txt`, `opengl.txt` | Recorded dependency/GPU information |
| `upstream_restore/` | Three pinned MetaDrive import files, source URLs, hashes and Apache-2.0 license |

`EXTENSION_MANIFEST_SHA256.json` covers the added extension files. Original
batch manifests remain byte-identical. The focused batch contains its own
frozen source snapshot; the pilot manifest's four source hashes match the
retained top-level Python files. Repository packaging changed only launch
wrappers, the comparison utility, and documentation;
the recorded simulation, planner and analyzer Python sources were preserved.
New output labels are ignored by Git unless deliberately selected for a later
release. Cached bytecode and large XWD screen captures were omitted.

The comparison utility now selects only circle records matching the primary
reference's seed/speed/mode and refuses to overwrite an existing report.
Its default output is `artifacts/comparison_current.json`; the historical
`comparison_with_delivered.json` remains unchanged. Reproduction checks for
this addition are listed in [the validation record](REPOSITORY_VALIDATION_2026-11-02.json).

## Interpretation limits

- The pilots are unpaced lockstep exchanges. The focused asynchronous cases
  advance physics against wall time without waiting for replies. The local
  focused baseline is unpaced, so it does not isolate DDS overhead.
- ROS nodes run as separate processes in one container on one host. DDS may
  use shared memory; no physical-network latency is established.
- The 80 ms rule measures controller request-source age at arbitration and
  latches a zero speed target. It is distinct from observation freshness and
  does not stop motion instantaneously.
- Obstacles are known static geometric exclusion regions. Planning selects
  a candidate once at setup. There is no perception, moving obstacle, online
  replanning, native impact response or physical vehicle experiment.
- All 40 audits passed, but stops and goals are different outcomes. These
  development cases do not establish statistical robustness, real-time
  guarantees or real-world safety. The separate 31 ms development lag remains
  visible alongside the final asynchronous batch's 6.9 ms maximum.

Author software follows the repository license. The restored MetaDrive files
retain their Apache-2.0 license. Dataset reuse terms remain governed by the
repository's stated dataset policy; this addition assigns no new data license.
