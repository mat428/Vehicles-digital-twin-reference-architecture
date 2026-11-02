# Supporting data and code: vehicle-control SIL experiments

This package supports **A Reference Architecture for Digital Twin–Based Co-Simulation and Verification of Intelligent Vehicle Control Systems**, by Matin Afshari and coauthors. It accompanies the separately supplied revised article, identified by its SHA-256 in `docs/ARTICLE\\\_LINKAGE.json`.

## Start here

1. Read `docs/ARTICLE\\\_DATA\\\_MAP.md` to locate evidence for each experimental table and figure.
2. Read `docs/DATA\\\_DICTIONARY.md` for columns, units, missing values and time semantics.
3. Read `docs/CONFIGURATION\\\_DETAILS.md` for exact paths, timeout calculation, adapter settings, fitted gains and bootstrap details.
4. Run `python verify\\\_package.py` to check all packaged file hashes and dataset inventory; this needs only Python's standard library.
5. To recompute the equations without installing simulators, run `python src/independent\\\_validate.py` **in a working copy**. It writes `results/independent\\\_validation.json`.
6. Follow `docs/REPRODUCIBILITY.md` for dependency installation, analysis, figure export or new native simulation runs.

## Contents retained

* **864 evaluation runs:** two native backends, two campaigns, three paths, two speeds and six evaluation seeds per backend. Each run retains a JSON record and compressed control/state and observation CSV files.
* **24 calibration runs:** circle/ellipse only; disjoint calibration seeds; frozen monitor models.
* **6 half-timestep checks and 2 fresh-environment checks:** stored separately; not counted as primary replicates.
* Full per-run metadata, raw measurements, summaries, calibration, original audit reports and relevant execution logs.
* Frozen protocol and core experiment code, native adapters, unit checks, map assets, pinned requirements and retained upstream runtime source/assets with licenses.
* Empirical figures corresponding to Figures 10–12 and a figure-only exporter.
* New packaging checks, evidence mapping and checksums.

The primary raw logs and frozen execution files are unchanged. The new documentation and exporter organize the existing evidence; they do not add experiments or alter reported results. Third-party documentation, examples, tests, unused ROS bridge code, old manuscripts, LaTeX files, template archives, architectural drawing scripts and article-building logs were removed. The original complete upstream manifest is historical; `MANIFEST\\\_SHA256.csv` lists exactly what is in this cleaned package.

## Scope

All measurements are simulated. No physical-vehicle, deployed ROS 2/DDS, HIL, native perception or real-world safety evidence is included. Audits check computational consistency; they are not an external safety assessment. This cleanup did not rerun all native simulations. See `checks/` for checks performed on supplied records.

## Rights

Upstream source/assets retain their supplied licenses; see `docs/THIRD\\\_PARTY\\\_NOTICES.md`. No new license for the authors' original code/data is imposed by this packaging step. Authors should choose appropriate reuse terms if depositing the package publicly.

