# Focused architectural extension — development protocol

Prepared before campaign execution on 29 October 2026. The article and original
data/code remain unchanged. This is a focused exploratory extension, not the
previously proposed 192-run formal study or a statistical power calculation.

The campaign contains 40 sequential cases at the original higher speed:

- 24 matched cases: two native backends × two known-map tasks (detour/blocked)
  × two development seeds (2001/2002) × three variants (stopping-only in-process,
  planner in-process, and the same planner over asynchronous DDS).
- Eight fault cases: two backends × two conditions (120 ms delayed replies or
  a one-wall-second controller-process pause) × two command policies (hold
  last command or latch zero target speed after 80 ms source-command age).
  These use the detour task and seed 2001.
- Eight difficulty cases: two backends × road half-widths 4, 2.5, 2.2 and 1.8
  wheelbases, using the in-process planner and seed 2001.

The known static map, obstacle dimensions, body dimensions, candidate offsets,
curvature screening and clearance thresholds follow the preceding obstacle
pilot. Road-width screening now uses the actual varied width. A rejected
detour yields a centreline anticipated stop at 20L; the obstacle starts at 27L.
Required geometric body clearance is 0.25L. Planning uses a 0.40L obstacle
margin and 0.25L road margin. No tuning on campaign outcomes is planned.

In-process cases advance as fast as computation permits. Asynchronous DDS
cases pace the same 5 ms event grid against host monotonic time; they process
replies without waiting and continue native physics when replies are absent.
The 20 ms controller request and 50 ms observation periods are logical-time
periods. Logs record source, receive, publish and application wall times,
simulation times, pacing lag and any overruns. Slow host execution must be
reported; logical deadlines alone cannot establish wall-time performance.

Expiry means application wall time exceeds the source request wall time by
more than 80 ms. The expire-stop policy latches zero target speed until the
case ends; steering remains controller-selected. It does not guarantee an
instantaneous physical stop. Hold-last-command retains the most recent
sequence-numbered response, including a delayed one. Old/duplicate sequence
numbers and future source timestamps are rejected.

Faults begin when native progress reaches x=18L, used only for scenario
injection/scoring and not passed to the controller. Added reply delay is 120 ms
thereafter. Controller pause uses SIGSTOP/SIGCONT on this campaign's isolated
controller process. The intended pause is one wall second; a collision or case
termination can censor it, which must be recorded. Setup/planning and DDS
discovery occur before the measured simulation epoch.

All native physics steps are retained. Whole-body swept geometry checks use
the previous documented interpolation assumption. A separate standard-library
audit reconstructs endpoint/midpoint clearance, terminal outcomes, command-age
expiry/latching and reply timestamp order. Geometry/control audit validity is
separate from route completion, successful stopping or collision outcomes.
All failures and incomplete tasks remain in the result register.

Geometry obstacles are exclusion regions, not native collision-impact models.
Planning is performed once from a known map; no perception or dynamic replanning
is evaluated. The old observation-only yaw monitor does not acquire command
authority in this extension. The new speed supervisor is explicitly separate.

Before the full campaign, run the unit checks and three F1TENTH asynchronous
development cases: nominal, pause/hold and pause/expiry. Preserve them outside
the 40-case batch. Freeze sources, matrix, image ID and policy definitions
before the full run. If implementation changes are required, retain old outputs
and start a new labelled batch; do not silently replace an adverse result.
