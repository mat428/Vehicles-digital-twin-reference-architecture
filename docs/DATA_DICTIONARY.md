# Data dictionary and time semantics

Backend + record category (campaign, calibration, numerical check or installation rerun) + folder/ID identifies a unique record set. Numerical and installation checks intentionally reuse the matched primary case ID in separate folders. Each run has a JSON summary, `<id>.csv.gz` control/state history and `<id>_observations.csv.gz` source history. Native states are recorded before the physics transition from t to t+5 ms. At a shared timestamp, source sampling precedes delivery and control; both plants have a native state at every event instant. Angles are radians unless a factor explicitly says degrees; x/y are metres, speed is m/s and time is seconds. The world convention is x-forward, y-left, yaw counterclockwise.

## Control/state columns (50 Hz)

| Field | Meaning |
|---|---|
| t | Logical control timestamp after any same-time observation deliveries |
| x, y, yaw, speed | Native ground truth for scoring; not passed to the shared path-following controller/monitor after initialization. The native target-speed regulator retains internal speed feedback |
| dt_x, dt_y, dt_yaw, dt_speed | Timestamp-aware corrected observer |
| naive_x, naive_y | Stale corrected observer position (name retained in code schema) |
| free_x, free_y | Predictor position with no measurement assimilation after reset |
| pre_error_m | Timestamp-aware position error before deliveries at this event |
| post_error_m, naive_error_m, free_error_m | Euclidean position errors against native truth |
| cte_m | Signed perpendicular error relative to nearest sampled reference tangent |
| delta_intended_rad | Pure-pursuit command before injected steering bias |
| delta_delivered_rad | Command after injected bias and clipping; native actuator dynamics then act on it |
| source_age_s | t minus source timestamp of newest delivered observation |
| yaw_alarm | Current persistent residual alarm after the most recent delivered packet |
| age_alarm | Whether source age exceeds 0.08 s |
| progress_fraction | Unwrapped reference-path index / number of sampled path points |

## Observation columns (20 Hz source rate)

| Field | Meaning |
|---|---|
| source_t | Timestamp when synthetic measurement is generated |
| delivery_t | Exact logical delivery timestamp; NaN for withheld or pending-tail packets |
| x_measured, y_measured, yaw_measured, speed_measured | Synthetic native-state measurement with specified independent noise |
| dropped | 1 for a withheld observation packet; generated payload is logged for audit but not delivered |
| q_cumulative | Command-only curvature integral Q=integral(tan(delta_intended)/L dt), units s/m; it does **not** include native truth speed |
| window_start_t | Oldest delivered source timestamp in five-packet diagnostic window |
| yaw_rate_measured | Wrapped heading change / delivered-source span, rad/s |
| yaw_rate_reference | Source-time integral of interpolated measured speed times held intended curvature, divided by window span, rad/s |
| yaw_residual | Measured rate minus frozen gain times reference rate |
| yaw_alarm | Persistent delivered residual decision |
| qualified_yaw_alarm | Three exceeding fully post-onset windows; zero for fault-free cases |

NaNs are intentional until a five-delivered-packet window with sufficient command history exists, for withheld packets and for packets scheduled after termination. They are not imputed. A missing delivery with dropped=0 must have scheduled source_t+delay after the terminal control time.

## JSON and summary tables

Group/mode/track/speed_case/seed/campaign identify the full case. `mismatch` changes observer wheelbase only. `magnitude` is signed degrees for steering, percentage for independent dropout and seconds for burst blackout. `wheelbase_m`, `time_scale`, `actual_target_speed_m_s`, `fault_onset_s` and `metric_start_s` describe the backend mapping. Both nominal metric start and planned fault onset are saved even when no fault is injected.

RMSE/p95 summaries use control rows after `metric_start_s`; normalized RMSE divides by native wheelbase. First yaw/freshness delays are logical first alarm time minus planned onset, with null for no alarm. `age_detected` describes age-threshold exceedance after the planned onset even in deliberately delayed E1 runs; it is not automatically evidence of an injected fault. `pre_fault_yaw_alarm_deliveries` counts eligible delivered alarms before actual injected onset, or all eligible alarms in unfaulted groups. It therefore includes model/closed-loop disagreement in E1/E2, not only E0 nominal tests. Observation windows overlap and monitor alarms may persist between deliveries.

SHA-256 fields authenticate stored compressed bytes. Run JSON contains the frozen monitor model and protocol hash, native metadata, completion/boundary outcomes and counts. Aggregate rows combine fixed conditions; they are not independent temporal observations. Campaign/seed blocks are the bootstrap resampling units. Fault results report observed counts and minimum/maximum fractions over six seed blocks; no binomial confidence interval is used because conditions sharing a seed are correlated. Paired tracking intervals are conditional, exploratory seed-block bootstraps, not universal coverage guarantees.

`qualified_yaw_alarm` (observation log): one when at least three consecutive residual windows exceed the frozen threshold and each window starts at or after the case's fault onset. Always zero for fault-free cases. This is separate from `yaw_alarm`, which remains a general persistent monitor output. Summary `fault_detected` and `first_yaw_alarm_delay_s` use this stricter attributed decision; delivery time, rather than the source timestamp, determines alarm availability. The yaw reference integrates interpolated measured speed times held intended curvature, rather than multiplying their window averages.

Known injection onset is used only for evaluation attribution (`qualified_yaw_alarm`, `fault_detected`, latency and within-one-second counts). The continuous `Monitor` has no onset input. Its general `yaw_alarm` may occur earlier, because a window crossing the injection boundary already contains fault response. Requiring wholly post-onset windows is a conservative scoring rule, not a deployable fault classifier or proof of the alarm's cause. Freshness also runs continuously; onset is used only when summarizing its response to an injected condition.
