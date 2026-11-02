# Digital Twin Reference Architecture for Intelligent Vehicles

Code and reproduction documentation supporting:

**A Reference Architecture for Digital Twin-Based Co-Simulation and Verification of Intelligent Vehicle Control Systems**

Matin Afshari, Mohsen Malayjerdi, Heiko Pikner, Andrei Rudz, Eduard Brindfeldt, and Raivo Sell.

Submitted to Vehicles. Manuscript ID: vehicles-4701946.

## Main contribution

The study proposes a six-layer reference architecture with explicit responsibilities, interfaces, state ownership, timing, command authority, and evidence management. The experimental implementations provide supporting evidence for selected architectural functions.

## Experiment availability

| Experiment | Current status |
| --- | --- |
| Primary software-in-the-loop study | Source code and documentation included. Dataset will be provided through GitHub Releases. |
| ROS 2/DDS extension | Will be added by a collaborating author. Not included in this version. |

## Primary study

The primary dataset contains:

- 864 evaluation runs using native F1TENTH and MetaDrive vehicle models.
- 24 separate calibration runs.
- Six half-timestep checks.
- Two fresh-environment checks.
- Control/state histories, observation records, per-run metadata, summaries, and computational audits.

All measurements are simulated. The study does not establish physical-vehicle validation.

## Repository contents

- `src/`: experiment runners, native plant adapters, analysis, and figure export.
- `configs/`: frozen experiment protocol.
- `maps/`: supplied map assets.
- `tests/`: checks of software contracts.
- `docs/`: data dictionary, configuration details, reproduction instructions, and manuscript evidence mapping.
- `checks/`: supplied historical audit reports.
- `figures/`: primary-study experimental figures.
- `requirements.txt` and `requirements.lock.txt`: dependency specifications.

Large datasets and bundled simulator distributions are excluded from Git history.

## Dataset downloads

Dataset archives will be attached to the repository's Releases page:

https://github.com/mat428/Vehicles-digital-twin-reference-architecture/releases

Until a dataset release is published, this repository alone is not a complete reproduction package.

## Reproduce the primary results

Download and extract a complete dataset archive from Releases. Open a terminal in the extracted directory containing `verify_package.py`, `src/`, and `results/`.

First verify the untouched archive:

```sh
python verify_package.py
```

Then use a working copy to run the independent computational check:

```sh
python src/independent_validate.py
```

For dependency installation, table recalculation, figure export, and optional new native simulation runs, follow the instructions supplied inside that archive.

Analysis scripts can overwrite derived reports. Preserve an untouched downloaded copy.

The repository's `MANIFEST_SHA256.csv` describes the original complete data package. It is not a checksum manifest for this Git checkout, which excludes results and simulator distributions and contains edited documentation.

## Documentation

- [Data dictionary](docs/DATA_DICTIONARY.md)
- [Configuration details](docs/CONFIGURATION_DETAILS.md)
- [Primary evidence map](docs/ARTICLE_DATA_MAP.md)
- [Original reproduction instructions](docs/REPRODUCIBILITY.md)

Some original documentation describes the complete downloadable package rather than this smaller Git checkout.

## Citation

If you use this code or dataset in research, please cite the repository release and the associated article by Matin Afshari and co-authors. Publication and DOI information will be added when available.

## Licensing

See `LICENSE` for the repository's software license. Third-party components retain their original licenses. Dataset licensing will be stated explicitly with the dataset release.
