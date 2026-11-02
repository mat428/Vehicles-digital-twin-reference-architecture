"""Execute the frozen native matrix sequentially; use a new project copy with empty results."""
import subprocess,json,datetime,sys
from pathlib import Path
r=Path(__file__).resolve().parents[1];py=sys.executable;timeline=[]
(r/'results/logs').mkdir(parents=True,exist_ok=True)
for backend in ['f1tenth','metadrive']:
 for phase,campaign in [('calibration','A'),('campaign','A'),('campaign','B')]:
  entry={'backend':backend,'phase':phase,'campaign':campaign,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()};timeline.append(entry)
  (r/'docs/execution_timeline.json').write_text(json.dumps(timeline,indent=2))
  with (r/'results/logs'/f'{backend}_{phase}_{campaign}.log').open('w') as f:
   result=subprocess.run([py,str(r/'src/run.py'),'--backend',backend,'--phase',phase,'--campaign',campaign],stdout=f,stderr=subprocess.STDOUT)
  entry.update(returncode=result.returncode,ended_utc=datetime.datetime.now(datetime.timezone.utc).isoformat());(r/'docs/execution_timeline.json').write_text(json.dumps(timeline,indent=2));print(entry,flush=True)
  if result.returncode:raise SystemExit(result.returncode)
