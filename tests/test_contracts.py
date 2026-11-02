import unittest,sys,json,math
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from run import cases,FIELDS,OBS_FIELDS
from common import track,control,propagate,correct
from monitor import Monitor

class Contracts(unittest.TestCase):
    def setUp(self):self.cfg=json.loads((ROOT/'configs/protocol.json').read_text())
    def test_matrix_and_holdout(self):
        from collections import Counter
        self.assertEqual(Counter(c['group'] for c in cases(self.cfg,'A')),dict(E0=54,E1=36,E2=18,E3=108))
        sets=[set(self.cfg['calibration_seeds'])]+[set(c['seeds']) for c in self.cfg['campaigns'].values()]
        self.assertTrue(all(not (a&b) for i,a in enumerate(sets) for b in sets[i+1:]))
    def test_clock_and_tail(self):
        for t in [.02,.05,.025,.075,.20]:self.assertAlmostEqual(round(t/.005)*.005,t)
        self.assertLess(max(self.cfg['delays_ms'])/1000,.5)
    def test_monitor_source_time_and_measured_speed(self):
        m=Monitor(self.cfg,dict(gain=1.,threshold_rad_s=.05))
        for j in range(400):m.advance(j*.005,math.atan(.1),.005,1.)
        for i in range(12):
            # Exact curvature .1 /m, measured speed 2m/s -> yaw rate .2 rad/s.
            result=m.receive(i*.05,i*.01,2.,i*.005)
        self.assertAlmostEqual(result[1],.2);self.assertAlmostEqual(result[2],.2)
        self.assertFalse(m.alarm)
        for i in range(12,20):m.receive(i*.05,.12+(i-12)*.04,2.,i*.005)
        self.assertTrue(m.alarm)
    def test_monitor_dropout_intervals(self):
        m=Monitor(self.cfg,dict(gain=1.,threshold_rad_s=.05))
        for j in range(400):m.advance(j*.005,math.atan(.1),.005,1.)
        for t in [0,.05,.15,.20,.35,.40,.50]:out=m.receive(t,.2*t,2.,.1*t)
        self.assertAlmostEqual(out[3],0.,places=12);self.assertFalse(m.alarm)
    def test_covarying_speed_and_curvature_integral(self):
        m=Monitor(self.cfg,dict(gain=1.,threshold_rad_s=100.))
        # v(t)=1+t, curvature 1 before .1s and 2 afterwards.
        # Integral = .105 + 2*.115 = .335, mean = 1.675.
        for j in range(40):
            t=j*.005;m.advance(t,math.atan(1 if t<.1 else 2),.005,1.)
        for t in [0,.05,.1,.15,.2]:out=m.receive(t,0.,1+t,0.)
        self.assertAlmostEqual(out[2],1.675,places=12)
        self.assertNotAlmostEqual(out[2],1.1*1.5,places=6)
    def test_scale_and_wrap(self):
        c=[]
        for L in [.3302,2.46894]:c.append(control(np.array([0,.05*L,0,1]),track('circle',L),0,L,self.cfg)[0])
        self.assertAlmostEqual(*c,places=12)
        a=np.array([0,0,math.pi-.01,1]);b=np.array([0,0,-math.pi+.01,1])
        self.assertGreater(abs(correct(a,b,.5)[2]),3.)
    def test_field_contract(self):
        self.assertEqual(len(FIELDS),24);self.assertEqual(len(OBS_FIELDS),14)
        self.assertEqual(FIELDS[23],'free_error_m');self.assertEqual(OBS_FIELDS[12],'window_start_t')
if __name__=='__main__':unittest.main()
