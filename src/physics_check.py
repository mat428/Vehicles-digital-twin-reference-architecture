"""Separate same-case timestep checks; never replace primary runs."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from plants import F1Plant,MetaPlant
from run import run_case,cases,atomic_json
ROOT=Path(__file__).resolve().parents[1]
def main():
    cfg=json.loads((ROOT/'configs/protocol.json').read_text());rows=[]
    for backend in ['f1tenth','metadrive']:
        finer=cfg.copy();finer[backend+'_physics_dt_s']/=2
        plant=(F1Plant if backend=='f1tenth' else MetaPlant)(finer)
        model=json.loads((ROOT/'results'/backend/'monitor_model.json').read_text())
        folder=ROOT/'results/numerical_sensitivity'/backend;folder.mkdir(parents=True,exist_ok=True)
        try:
            for name in cfg['tracks']:
                case=next(c for c in cases(cfg,'A') if c['group']=='E0' and c['mode']=='timestamp' and c['track']==name and c['speed_case']==2 and c['seed']==cfg['campaigns']['A']['seeds'][0])
                base_folder=ROOT/'results'/backend/'campaign/A';base=json.loads((base_folder/(case['id']+'.json')).read_text())
                s,_=run_case(plant,finer,case,folder,model)
                a=pd.read_csv(base_folder/base['raw_file']);b=pd.read_csv(folder/s['raw_file']);n=min(len(a),len(b));assert np.allclose(a.t.iloc[:n],b.t.iloc[:n])
                delta=np.hypot(a.x.iloc[:n].to_numpy()-b.x.iloc[:n].to_numpy(),a.y.iloc[:n].to_numpy()-b.y.iloc[:n].to_numpy())
                rows.append(dict(backend=backend,track=name,base_physics_dt_s=cfg[backend+'_physics_dt_s'],fine_physics_dt_s=finer[backend+'_physics_dt_s'],comparison_records=n,position_difference_rms_m=float(np.sqrt(np.mean(delta**2))),position_difference_rms_L=float(np.sqrt(np.mean(delta**2)))/s['wheelbase_m'],base_completed=base['completed'],fine_completed=s['completed'],base_tracking_rmse_L=base['track_rmse_L'],fine_tracking_rmse_L=s['track_rmse_L']))
        finally:plant.close()
    pd.DataFrame(rows).to_csv(ROOT/'results/numerical_sensitivity.csv',index=False)
    atomic_json(ROOT/'results/numerical_sensitivity.json',dict(extra_native_runs=6,scope='two-step sensitivity, not convergence proof',records=rows))
if __name__=='__main__':main()
