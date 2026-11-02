"""Verify retained extension records; optionally recompute audits in temp copies."""
import argparse
from collections import Counter
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import shutil
import tempfile


LAB = Path(__file__).resolve().parent
REPO = LAB.parent


def read_json(path):
    return json.loads(path.read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_hashes(root, records):
    for record in records:
        path = root / record['path']
        require(path.resolve().is_relative_to(root.resolve()), f'Invalid path: {path}')
        require(path.is_file(), f'Missing: {path}')
        require(hashlib.sha256(path.read_bytes()).hexdigest() == record['sha256'],
                f'Hash mismatch: {path}')
    return len(records)


def recompute_pilots(root, cases):
    from analyze_pilots import obstacle_audit
    for case in cases:
        folder = root / case['id']
        if case['family'] == 'geometry':
            summary = read_json(folder / f"dds_{case['track']}.json")
            report = read_json(folder / 'dds_report.json')
            with gzip.open(folder / f"dds_{case['track']}.csv.gz", 'rt') as stream:
                rows = [r for r in csv.DictReader(stream)
                        if float(r['t']) >= summary['metric_start_s']]
            rmse = math.sqrt(sum(float(r['cte_m'])**2 for r in rows) / len(rows))
            require(abs(rmse-summary['track_rmse_m']) < 1e-10,
                    f'Geometry RMSE mismatch: {folder.name}')
            require(report['completed'] and not report['boundary_violation'],
                    f'Geometry outcome mismatch: {folder.name}')
        else:
            with tempfile.TemporaryDirectory(prefix='ros2-pilot-audit-') as tmp:
                work = Path(tmp) / 'case'
                shutil.copytree(folder, work)
                audit, _, _ = obstacle_audit(work)
                require(audit['passed'] and audit['swept_score_is_conservative'],
                        f'Obstacle audit failed: {folder.name}')


def recompute_focus(root, cases):
    from focus_analyze import audit
    for case in cases:
        folder = root / case['id']
        with tempfile.TemporaryDirectory(prefix='ros2-focus-audit-') as tmp:
            work = Path(tmp) / 'case'
            shutil.copytree(folder, work)
            result = read_json(work / 'result.json')
            check, _, _, _ = audit(work, result)
            require(check['valid'], f'Focused audit failed: {folder.name}')
            require(result['clearance_gate_met'] and result['collision_free'],
                    f'Focused clearance mismatch: {folder.name}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recompute', action='store_true',
                        help='Recompute case audits in temporary copies (no simulator).')
    args = parser.parse_args()
    records = read_json(LAB / 'EXTENSION_MANIFEST_SHA256.json')['files']
    print(f'Extension file hashes verified: {check_hashes(REPO, records)}', flush=True)
    for name in ['pilot20_20261029_01', 'focus40_20261029_01',
                 'focus_development_01', 'obstacle_development_01']:
        root = LAB / 'artifacts' / name
        count = check_hashes(root, read_json(root / 'output_hashes.json'))
        manifest = read_json(root / 'manifest.json')
        source = root / 'frozen_source' if (root / 'frozen_source').is_dir() else LAB
        check_hashes(source, [dict(path=p, sha256=s)
                             for p, s in manifest['source_hashes'].items()])
        print(f'{name}: {count} payload hashes and source hashes verified', flush=True)

    pilot = LAB / 'artifacts/pilot20_20261029_01'
    focused = LAB / 'artifacts/focus40_20261029_01'
    pilots = read_json(pilot / 'manifest.json')['matrix']
    cases = read_json(focused / 'manifest.json')['cases']
    ps = read_json(pilot / 'pilot_summary.json')
    fs = read_json(focused / 'summary.json')
    require(len(pilots) == ps['planned'] == ps['passed'] == 20, 'Pilot count mismatch')
    require(len(cases) == fs['planned'] == fs['audits_valid'] == 40, 'Focus count mismatch')
    require(Counter(c['group'] for c in cases) == {'matched': 24, 'fault': 8, 'width': 8},
            'Focused matrix mismatch')
    require({c['id'] for c in pilots} == {c['id'] for c in ps['cases']},
            'Pilot case IDs mismatch')
    require({c['id'] for c in cases} == {c['id'] for c in fs['cases']},
            'Focused case IDs mismatch')
    require(all(c['passed'] for c in ps['cases']), 'Recorded pilot gate failed')
    require(all(c['audit_valid'] and c['clearance_gate_met'] and c['collision_free']
                for c in fs['cases']), 'Recorded focused gate failed')
    outcomes = Counter(c['outcome'] for c in fs['cases'])
    require(outcomes == {'goal_reached': 17, 'stopped': 23}, 'Focused outcome mismatch')
    require(read_json(focused / 'source_integrity.json')['unchanged'],
            'Recorded campaign source-integrity check failed')
    print('Recorded campaigns: 20/20 pilot gates; 40/40 audits; 17 goals and 23 stops.', flush=True)
    if args.recompute:
        recompute_pilots(pilot, pilots)
        print('Recomputed 12 geometry RMSE checks and eight obstacle audits.', flush=True)
        recompute_focus(focused, cases)
        print('Recomputed 40 focused geometry, outcome and command-authority audits.', flush=True)
    print('PASS. Retained evidence was not modified.', flush=True)


if __name__ == '__main__':
    main()
