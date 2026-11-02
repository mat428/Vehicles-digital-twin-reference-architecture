"""Inspect new runs against the delivered matching case using only stdlib."""
import argparse
import csv
import gzip
import json
import os
from pathlib import Path

LAB = Path(__file__).resolve().parent
EVIDENCE = Path(os.environ.get('EVIDENCE_DIR', str(LAB.parent/'Vehicle_Control_SIL_Data_Code')))
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=LAB/'artifacts/comparison_current.json')
args = parser.parse_args()
reports = []
for report_file in sorted((LAB/'artifacts').glob('*/*/dds_report.json')):
    folder = report_file.parent
    metadata_file = folder/'dds_circle.json'
    if not metadata_file.exists():
        continue
    metadata = json.loads(metadata_file.read_text())
    if (metadata['seed'], metadata['speed_case'], metadata['mode']) != (300, 2., 'timestamp'):
        continue  # Pilot cases have different conditions from the delivered reference.
    report = json.loads(report_file.read_text())
    backend = report['backend']
    original = EVIDENCE/'results'/backend/'campaign/A/A_E0_0037.csv.gz'
    new = folder/'dds_circle.csv.gz'
    with gzip.open(original, 'rt') as f:
        old_rows = list(csv.DictReader(f))
    with gzip.open(new, 'rt') as f:
        new_rows = list(csv.DictReader(f))
    if len(old_rows) != len(new_rows):
        raise ValueError(f'{folder}: row count changed')
    columns = ['t', 'x', 'y', 'yaw', 'speed', 'dt_x', 'dt_y', 'delta_intended_rad']
    differences = {column: max(abs(float(a[column])-float(b[column]))
                              for a, b in zip(old_rows, new_rows)) for column in columns}
    reports.append(dict(run=str(folder.relative_to(LAB)), middleware=report['rmw'],
                        completed=report['completed'], row_count=len(new_rows),
                        differences_against_delivered=differences,
                        compressed_control_bytes_equal=new.read_bytes() == original.read_bytes(),
                        original_case='campaign/A/A_E0_0037'))
target = args.output
if target.exists():
    raise FileExistsError(f'Use a fresh comparison output path: {target}')
target.write_text(json.dumps(reports, indent=2))
for report in reports:
    print(report['run'], 'max state/command difference:',
          max(report['differences_against_delivered'].values()))
