# Exact configuration details recovered from the supplied project

These notes document the existing experiment; they do not change its protocol or fill missing information by estimation.

## Bootstrap (Table 3)

`src/analyze.py:paired_bootstrap` uses **5,000 replicates**, `numpy.random.default_rng(seed=765)`, and samples six complete `(campaign, seed)` blocks with replacement for each replicate. It flattens the sampled blocks, calculates the median paired difference, and takes the **2.5th and 97.5th empirical quantiles** using NumPy's default quantile method (linear). This is a percentile interval, conditional on the finite geometry/speed matrix. Each block retains its six path/speed combinations. Individual time samples are not resampled. Dependencies are pinned in `requirements.lock.txt`.

## Fitted monitor factors

| Backend | Fitted gain g-hat (stored model) | Residual threshold, rad/s | Eligible calibration windows | Calibration runs |
|---|---:|---:|---:|---:|
| F1TENTH | 0.9692712357550437 | 0.11612173182916574 | 2449 | 12 |
| MetaDrive | 0.9870621863737121 | 0.07265803750143132 | 6730 | 12 |

Sources: `results/f1tenth/monitor_model.json`, `results/metadrive/monitor_model.json`. Independent refits agree within floating-point tolerance; see `checks/independent_recheck.json`. These factors are distinct from the observer correction gain 0.65.

## Path definitions

`src/common.py:track` constructs dimensionless coordinates for theta in [0,2*pi] using 4,001 source points, then resamples by numerical arc length at **0.05 wheelbase** spacing and multiplies coordinates by native wheelbase L:

- Circle: x/L = 8*sin(theta); y/L = 8*(1-cos(theta)).
- Ellipse: x/L = 10*sin(theta); y/L = 6*(1-cos(theta)).
- Wavy: r = 8*(1+0.15*cos(3*theta)); x/L = r*sin(theta); y/L = 9.2-r*cos(theta).

The endpoint is not duplicated by arc-length resampling. Heading uses centered neighboring point differences with wraparound. The controller knows the centerline; this is not image-based lane detection.

## Run timeouts

The timeout is **computed per backend/path/speed case**, not one universal number. With time_scale=sqrt(L/L_F1) and v_target=speed_case*time_scale, `src/run.py:run_case` uses:

```
N = round((1.4*path_length/v_target + 3*time_scale)/event_dt)
event_dt = 0.005 seconds
```

It iterates ticks 0 through N-1, so the budget is N*event_dt and the last possible event time is (N-1)*event_dt. A circuit completion or sampled corridor violation can terminate earlier. Exact calculated budgets for all 12 backend/path/speed combinations are in `RUN_LIMITS.csv`. Control records occur every 0.020 s and may end before the final event tick.

## Native adapters and shared controller

- Shared pure pursuit: lookahead 2L; steering clipped to +/-0.4189 rad; controller every 0.020 s; source sampling every 0.050 s; event grid 0.005 s.
- F1TENTH: native RaceCar, RK4, 0.001 s physics, wheelbase lf+lr=0.15875+0.17145=0.3302 m, native steering buffer set to 0.020 s. Intended steering and target speed pass to native `update_pose`, which uses its own speed regulation. The complete native parameter dictionary is `src/plants.py:PARAMS` and each run's `native_metadata.params`.
- MetaDrive: native StaticDefaultVehicle/Bullet, 0.005 s physics, wheelbase 2.46894 m, no traffic/perception, original road surfaces replaced by flat Bullet planes. Native action steering is delta/radians(max_steering); throttle/brake is clip(0.5*(target_speed-native_speed),-1,1). See `src/plants.py:MetaPlant` for reset, actuator conventions and environmental configuration.
- Observer: correction gain 0.65; between observations, speed relaxes toward the target with a 0.20 s time constant. Timestamp-aware correction replays intended command history from source time.
- Monitor: five delivered packets, three successive threshold exceedances, two-second command history, freshness age >0.080 s; full residual and scoring definitions are in `DATA_DICTIONARY.md`.

## 0.30-second response

The strong-bias credited response equals the earliest time admitted by five wholly post-onset packet windows and three consecutive exceedances. It is a logical scoring delay, not measured processor latency. The continuous monitor does not receive the injection time; attribution is performed separately for evaluation.
