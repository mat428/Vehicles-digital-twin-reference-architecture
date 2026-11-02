# Reviewer reproduction guide: Windows

## Scope

Recorded-data verification, independent calculations, seven software tests, primary analysis, and Figures 10-12 were tested successfully on Windows with Python 3.12.10.

One new F1TENTH case and one new MetaDrive case were also executed and compared with the supplied baseline. A complete 864-run Windows campaign was not rerun.

This package covers the primary SIL study. The ROS 2/DDS extension is supplied separately when available.

## 1. Verify the delivered package

Extract the archive to a short path, such as C:\sil-review. Open PowerShell in the extracted project folder containing verify_package.py.

```powershell
python verify_package.py
```

Expected: all_checks_pass is true, with 864 evaluation runs, 24 calibration runs, six timestep checks and two fresh-environment checks.

Run this before installing editable packages or modifying files.

## 2. Create a working copy

Copy the complete project folder to a separate location, such as C:\sil-work. Run the remaining commands from that working copy. Keep the verified delivery unchanged.

## 3. Reproduce calculations and figures

Create an analysis environment outside the project folder:

```powershell
py -3.12 -m venv ..\sil-analysis-venv
..\sil-analysis-venv\Scripts\python.exe -m pip install -r docs\sil-analysis-environment.txt
..\sil-analysis-venv\Scripts\python.exe src\independent_validate.py
..\sil-analysis-venv\Scripts\python.exe -m unittest discover -s tests -v
..\sil-analysis-venv\Scripts\python.exe src\analyze.py
..\sil-analysis-venv\Scripts\python.exe src\export_figures.py
```

The independent checker requires only Python's standard library. Analysis and figure export require the installed dependencies.

Expected: independent and primary checks pass, seven tests pass, and experimental_evidence.pdf, native_trajectories.pdf and fault_evidence.pdf are exported under figures/.

These operations overwrite derived reports in the working copy.

## 4. Test new native simulation runs

Use a separate environment:

```powershell
py -3.12 -m venv ..\sil-native-venv
..\sil-native-venv\Scripts\python.exe -m pip install -r requirements.txt
..\sil-native-venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e vendor\f1tenth_gym -e vendor\metadrive
```

The restored MetaDrive examples package is required during imports. Its 27 files were verified against the recorded upstream commit; see METADRIVE_RUNTIME_RESTORATION.json.

Preserve the supplied installation-check records before running the following commands. Rename this folder only once:

```powershell
Rename-Item results\install_smoke install_smoke_supplied
..\sil-native-venv\Scripts\python.exe src\smoke_check.py --backend f1tenth
..\sil-native-venv\Scripts\python.exe src\smoke_check.py --backend metadrive
..\sil-native-venv\Scripts\python.exe src\compare_smoke.py
```

Both selected cases completed in the Windows test. Record counts and terminal times matched the supplied baseline. Maximum position differences were approximately 1.11e-16 m for F1TENTH and 2.02e-5 m for MetaDrive. Both passed the script's 0.01-wheelbase threshold. Compressed-file hashes were not identical.

The comparison script's historical "same machine only" wording does not describe this Windows-versus-delivered-baseline test. Native physics byte identity across platforms is not guaranteed.

## Environment records and limitations

sil-analysis-environment.txt records the successfully tested analysis dependencies.

sil-native-environment.txt records the native environment, including machine-specific editable-install paths. It is a provenance record; do not install it directly with pip. Use requirements.txt and the relative editable-install commands above.

The original Linux reproduction instructions remain in REPRODUCIBILITY.md. Consult them for the complete campaign workflow. Only the two selected native cases were rerun during this Windows check.
