"""Run one native held-out case using the current installed environment."""
import argparse,json
from pathlib import Path
from plants import F1Plant,MetaPlant
from run import run_case,cases
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--backend',choices=['f1tenth','metadrive'],required=True);args=p.parse_args()
    cfg=json.loads((ROOT/'configs/protocol.json').read_text());model=json.loads((ROOT/'results'/args.backend/'monitor_model.json').read_text())
    case=next(c for c in cases(cfg,'A') if c['group']=='E0' and c['mode']=='timestamp' and c['track']=='circle' and c['speed_case']==2 and c['seed']==cfg['campaigns']['A']['seeds'][0])
    folder=ROOT/'results/install_smoke'/args.backend;folder.mkdir(parents=True,exist_ok=True)
    plant=(F1Plant if args.backend=='f1tenth' else MetaPlant)(cfg)
    try:run_case(plant,cfg,case,folder,model)
    finally:plant.close()
if __name__=='__main__':main()
