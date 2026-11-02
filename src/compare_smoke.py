"""Compare separately installed native reruns with matched primary records."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
def main():
    rows=[]
    for backend in ['f1tenth','metadrive']:
        folder=ROOT/'results/install_smoke'/backend
        p=next(folder.glob('*_E0_*.json'));s=json.loads(p.read_text());base_folder=ROOT/'results'/backend/'campaign/A'
        base=json.loads((base_folder/p.name).read_text());a=pd.read_csv(base_folder/base['raw_file']);b=pd.read_csv(folder/s['raw_file'])
        n=min(len(a),len(b));assert abs(len(a)-len(b))<=1 and np.allclose(a.t.iloc[:n],b.t.iloc[:n])
        errors=np.hypot(a.x.iloc[:n].to_numpy()-b.x.iloc[:n].to_numpy(),a.y.iloc[:n].to_numpy()-b.y.iloc[:n].to_numpy())
        assert bool(s['completed'])==bool(base['completed']) and bool(s['boundary_violation'])==bool(base['boundary_violation'])
        assert float(errors.max())/s['wheelbase_m']<0.01, 'Fresh-environment disagreement exceeds 0.01 wheelbase' 
        rows.append(dict(backend=backend,baseline_records=len(a),fresh_install_records=len(b),comparison_records=n,terminal_time_difference_s=float(b.t.iloc[-1]-a.t.iloc[-1]),completed=s['completed'],
                         maximum_position_difference_m=float(errors.max()),rms_position_difference_m=float(np.sqrt(np.mean(errors**2))),
                         raw_hash_identical=base['raw_sha256']==s['raw_sha256'],observation_hash_identical=base['observations_sha256']==s['observations_sha256']))
    result=dict(extra_native_runs=2,scope='freshly created venv with pinned lock and bundled sources; same machine only',records=rows)
    (ROOT/'results/install_smoke.json').write_text(json.dumps(result,indent=2));pd.DataFrame(rows).to_csv(ROOT/'results/install_smoke.csv',index=False);print(result)
if __name__=='__main__':main()
