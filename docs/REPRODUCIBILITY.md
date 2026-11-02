# Reproduction without a manuscript project

Work on a copy of this directory. Preserve the delivered package and its checksums. `docs/environment.json`, the two lock files and retained installation logs record the original Linux/Python 3.12 environment. Absolute editable-install paths in historical logs describe the original machine, not paths to use now.

## 1. Verify supplied bytes (no external dependencies)

From the package root:

```bash
python verify_package.py
python src/independent_validate.py
```

The second command uses the standard library and independently reconstructs calibration, observers, geometry and diagnostics for 864 evaluation runs. It overwrites its derived JSON report, so use a working copy. It does not run native physics. Original and packaging-time reports are distinguished under `results/` and `checks/`.

## 2. Recompute tables and figures from existing records

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock.txt
python -m unittest discover -s tests -v
python src/analyze.py
python src/independent_validate.py
python src/export_figures.py
```

`analyze.py` imports the adapter definitions but does not instantiate native plants; native simulator installation is needed only to generate new physics runs. It recomputes summaries and the primary audit. `export_figures.py` writes only the three empirical PDF figures under `figures/`. It does not recreate or edit an article. New files/derived outputs may change checksums; preserve the delivered copy.

The source `report.py` from the original project combined figure export with rewriting old article text; it was replaced by the figure-only exporter. `design_figures.py` and `package.py` were omitted because they concern the separate manuscript/LaTeX project. The six frozen files referenced by `docs/design_freeze.json` remain unchanged.

## 3. Generate new native runs (optional, substantially more work)

Install the bundled native implementations after the locked dependencies:

```bash
pip install --no-deps --no-build-isolation -e vendor/f1tenth_gym -e vendor/metadrive
```

Classic F1TENTH metadata pins old dependencies; `--no-deps` is deliberate after the provided lock. Internet access is required for dependency installation; this is not an offline wheel bundle. No GPU/rendering is required by this experiment. Other operating systems are untested.

In a second project copy, rename `results/` to `results_delivered/` and then run:

```bash
python src/run_all.py
python src/physics_check.py
```

The runner creates new `results/` data, runs F1TENTH calibration/A/B before MetaDrive calibration/A/B, and refuses to overwrite primary files. This is 864 evaluation plus 24 calibration runs, followed by six separate half-timestep checks. For fresh-environment checks, create a second venv using the same installation commands and run its Python on:

```bash
python src/smoke_check.py --backend f1tenth
python src/smoke_check.py --backend metadrive
```

Then recompute from the main analysis environment:

```bash
python src/compare_smoke.py
python src/analyze.py
python src/independent_validate.py
python src/export_figures.py
```

Retain new execution logs, lock files and numerical differences. Do not replace delivered results with newly generated results without distinguishing the new run environment. Native Bullet byte identity across machines is not promised.

## Source snapshots

F1TENTH Gym commit `4fdb9c7e6fb7c701290f4dc18377d07c1681724f`; MetaDrive commit `325d9e2f9c20e495bde66f30e0ef2b40efbce39c`. Runtime code and assets are retained. Unused upstream documentation, examples, tests and bridge directories were omitted. Retained files are unmodified; the removed-file inventory is in `PACKAGING_CHANGES.json`. The original upstream manifest covers the full original snapshot, while the package manifest covers this distribution.
