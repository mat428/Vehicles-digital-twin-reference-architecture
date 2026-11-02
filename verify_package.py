"""Verify packaged bytes and full run inventory using the Python standard library."""
from pathlib import Path
import csv,gzip,hashlib,json
ROOT=Path(__file__).resolve().parent

def main():
    manifest=ROOT/'MANIFEST_SHA256.csv'
    if manifest.exists():
        listed=set()
        for row in csv.DictReader(manifest.open()):
            rel=row['path'];p=ROOT/rel;listed.add(rel)
            assert p.is_file(),f'Missing {rel}'
            assert p.stat().st_size==int(row['bytes']),f'Size changed: {rel}'
            assert hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256'],f'Hash changed: {rel}'
        actual={str(p.relative_to(ROOT)) for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='MANIFEST_SHA256.csv'}
        assert actual==listed,{'unlisted':sorted(actual-listed),'missing':sorted(listed-actual)}
    else:raise AssertionError('MANIFEST_SHA256.csv is missing')
    freeze=json.loads((ROOT/'docs/design_freeze.json').read_text())
    for name,digest in freeze['files'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,f'Frozen file changed: {name}'
    counts={'evaluation':0,'calibration':0,'timestep':0,'fresh_environment':0}
    control=observations=0
    for path in (ROOT/'results').rglob('*.json'):
        obj=json.loads(path.read_text())
        if not isinstance(obj,dict) or 'raw_file' not in obj or 'observations_file' not in obj:continue
        if 'campaign' in path.parts:category='evaluation'
        elif 'calibration' in path.parts:category='calibration'
        elif 'numerical_sensitivity' in path.parts:category='timestep'
        elif 'install_smoke' in path.parts:category='fresh_environment'
        else:raise AssertionError(f'Unclassified run: {path}')
        counts[category]+=1
        for field in ['raw','observations']:
            p=path.parent/obj[field+'_file']
            assert hashlib.sha256(p.read_bytes()).hexdigest()==obj[field+'_sha256'],f'Raw bytes changed: {p}'
            with gzip.open(p,'rt',newline='') as stream:
                reader=csv.reader(stream);headers=next(reader);n=sum(1 for _ in reader)
            expected=obj['control_records' if field=='raw' else 'observation_records']
            assert n==expected,(str(p),n,expected)
            assert len(headers)==(24 if field=='raw' else 14),(str(p),headers)
            if category=='evaluation':
                if field=='raw':control+=n
                else:observations+=n
    assert counts=={'evaluation':864,'calibration':24,'timestep':6,'fresh_environment':2},counts
    assert (control,observations)==(1009406,403901),(control,observations)
    total_upstream=0
    for entry in json.loads((ROOT/'docs/upstream_manifest.json').read_text()):
        p=ROOT/entry['path']
        if p.exists():
            assert hashlib.sha256(p.read_bytes()).hexdigest()==entry['sha256'],str(p)
            total_upstream+=1
    result={'all_checks_pass':True,'run_counts':counts,'evaluation_control_records':control,'evaluation_observation_records':observations,'unchanged_frozen_files':len(freeze['files']),'retained_upstream_files_verified':total_upstream,'manifest_payload_files':len(listed),'scope':'packaged bytes, stored raw-file hashes, actual CSV row counts, schema widths and inventory; no native physics rerun'}
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
