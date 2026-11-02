import unittest
from focus_model import arbitrate,accept_reply,make_spec,make_plan,EXPIRY_NS
from analyze_pilots import polygon_distance


class FocusRules(unittest.TestCase):
    def test_expired_command_stops_and_latches(self):
        command=dict(delta=.1,speed=2.,source_wall_ns=0,sequence=1)
        self.assertEqual(arbitrate(command,EXPIRY_NS,'expire_stop')[1],2.)
        self.assertEqual(arbitrate(command,EXPIRY_NS+1,'expire_stop')[1],0.)
        command['source_wall_ns']=EXPIRY_NS+2
        self.assertEqual(arbitrate(command,EXPIRY_NS+3,'expire_stop',True)[1],0.)

    def test_hold_and_sequence_rejection(self):
        command=dict(delta=.1,speed=2.,source_wall_ns=0,sequence=1)
        self.assertEqual(arbitrate(command,EXPIRY_NS*3,'hold')[1],2.)
        self.assertFalse(accept_reply(command,1,10))
        self.assertFalse(accept_reply(dict(command,source_wall_ns=20),0,10))
        self.assertTrue(accept_reply(command,0,10))

    def test_real_road_width_used_and_stopping_only_comparison(self):
        wide=make_spec(1.,'detour',4.)
        self.assertFalse(make_plan(wide,[1.8,.9])[1])
        self.assertTrue(make_plan(wide,[1.8,.9],False)[1])
        self.assertTrue(make_plan(make_spec(1.,'detour',1.8),[1.8,.9])[1])

    def test_independent_polygon_audit(self):
        a=[(0,0),(1,0),(1,1),(0,1)]
        self.assertAlmostEqual(polygon_distance(a,[(2,0),(3,0),(3,1),(2,1)]),1.)
        self.assertEqual(polygon_distance(a,[(.5,0),(2,0),(2,1),(.5,1)]),0.)


if __name__=='__main__':unittest.main()
