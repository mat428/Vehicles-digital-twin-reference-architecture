# Map from the final article to supporting evidence

The final article is the separately supplied revised PDF, not an old manuscript from the original project archive. Its identity is recorded in `ARTICLE_LINKAGE.json`.

| Article item | Supporting files |
|---|---|
| Abstract / Section 6: 864 evaluation runs and 24 calibration runs | `results/{f1tenth,metadrive}/campaign/{A,B}/`, `results/{f1tenth,metadrive}/calibration/A/`, `results/validation.json` |
| Table 2: implementation and boundaries | `src/{plants,run,common,monitor}.py`, `configs/protocol.json`, `docs/EXPERIMENT_DESIGN.md` |
| Table 3: paired tracking medians and intervals | `results/paired_comparisons.json`, `results/run_summary.csv`, `src/analyze.py:paired_bootstrap` |
| Table 4: state-error medians | `results/article_values.json`, `results/run_summary.csv`, raw state histories |
| Table 5: detections, misses, freshness and one-second counts | `results/fault_summary.csv`, raw observation logs, `src/monitor.py`, attribution/scoring in `src/run.py` |
| Figure 10 | `figures/experimental_evidence.pdf`, `src/export_figures.py`, paired and per-run summaries |
| Figure 11 | `figures/native_trajectories.pdf`, campaign A / seed 300 / high-speed E0 timestamp runs, `src/common.py:track` |
| Figure 12 | `figures/fault_evidence.pdf`, `results/fault_summary.csv`, `src/export_figures.py` |
| Held-out wavy results | `results/geometry_transfer.csv`, raw records; calibration tracks in protocol |
| Calibrated yaw gains / thresholds | `results/{f1tenth,metadrive}/monitor_model.json`, `results/calibration_validation.json`, calibration logs |
| Six half-timestep checks | `results/numerical_sensitivity/`, `results/numerical_sensitivity.{csv,json}` |
| Two fresh-environment checks | `results/install_smoke/`, `results/install_smoke.{csv,json}`, environment locks/install logs |
| Source hashes and design freeze | `docs/design_freeze.json`, `docs/upstream_manifest.json`, `MANIFEST_SHA256.csv` |
| Original audits | `results/validation.json`, `results/independent_validation.json`, `results/calibration_validation.json` |
| Packaging-time equation recheck | `checks/independent_recheck.json` |

There are 896 recorded run sets: 864 evaluation + 24 calibration + 6 timestep + 2 fresh-environment. Each set consists of one JSON and two compressed CSV files. Small execution-status and monitor-model JSON files are metadata, not additional runs.

The separately supplied final article reports 1,009,406 control/state rows and 403,901 observation rows for evaluation runs only. Calibration/check rows must not be added to those article counts. NaNs in observation windows and undelivered packets are intentional; see DATA_DICTIONARY.md.
