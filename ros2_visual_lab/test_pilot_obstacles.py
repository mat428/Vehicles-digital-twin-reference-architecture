import unittest
from shapely.geometry import box
from pilot_obstacles import footprint, swept, scenario, plan, decide


class CollisionAndPlanning(unittest.TestCase):
    def test_body_corner_collision_with_clear_centre(self):
        self.assertTrue(footprint([0,0,0],2,1).intersects(box(.8,.3,1.1,.7)))

    def test_swept_crossing_of_thin_obstacle(self):
        obstacle=box(.95,-.3,1.05,.3)
        self.assertFalse(footprint([0,0,0],.4,.4).intersects(obstacle))
        self.assertFalse(footprint([2,0,0],.4,.4).intersects(obstacle))
        self.assertTrue(swept([0,0,0],[2,0,0],.4,.4).intersects(obstacle))

    def test_detour_selection_and_blocked_stop(self):
        spec=scenario(1.,'detour')
        path,candidates=plan(spec,1.8,.9)
        self.assertTrue(candidates[-1]['valid'])
        self.assertGreater(max(path['points'][:,1]),1)
        blocked=scenario(1.,'blocked')
        path,candidates=plan(blocked,1.8,.9)
        self.assertFalse(any(c['valid'] for c in candidates))
        result=decide([20,0,0,1],0,path,blocked,2.)
        self.assertEqual(result['speed'],0.)

    def test_rotating_swept_footprint_covers_midpoint(self):
        import math
        region=swept([0,0,0],[0,0,math.pi/2],2.,1.)
        self.assertTrue(region.covers(footprint([0,0,math.pi/4],2.,1.)))


if __name__=='__main__':
    unittest.main()
