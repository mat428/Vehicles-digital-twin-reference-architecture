"""Native plant components; shared world frame is x-forward/y-left/CCW and SI."""
import math
import numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PARAMS={'mu':1.0489,'C_Sf':4.718,'C_Sr':5.4562,'lf':.15875,'lr':.17145,'h':.074,'m':3.74,'I':.04712,'s_min':-.4189,'s_max':.4189,'sv_min':-3.2,'sv_max':3.2,'v_switch':7.319,'a_max':9.51,'v_min':-5.,'v_max':20.,'width':.31,'length':.58}
class F1Plant:
    def __init__(self,cfg):
        import pyglet
        pyglet.options['headless']=True
        from f110_gym.envs.base_classes import RaceCar,Integrator
        self.cfg=cfg;self.L=cfg['f1tenth_wheelbase_m'];self.dt=cfg['f1tenth_physics_dt_s'];self.RaceCar=RaceCar
        # 16 native laser beams; scans are not used for control/verification. Dynamics are unchanged.
        self.car=RaceCar(PARAMS.copy(),0,time_step=self.dt,num_beams=16,integrator=Integrator.RK4)
        self.car.set_map(str(ROOT/'maps/laboratory.yaml'),'.png')
        self.metadata=dict(component='official F1TENTH Gym RaceCar',params=PARAMS,physics_dt_s=self.dt,integrator='native RK4',laser_beams=16,scans_used_for_control=False,corridor_checks='shared geometry, not Gym collision or race scoring')
    def reset(self,seed,pose,speed):
        self.car.seed=seed;self.car.reset(np.array(pose,dtype=float));self.car.steer_buffer_size=round(.02/self.dt);self.car.state[3]=speed
        for _ in range(round(self.cfg['settling_s']/self.dt)):self.car.update_pose(0,speed)
        return self.read()
    def read(self):
        s=self.car.state;return np.array([s[0],s[1],math.atan2(math.sin(s[4]),math.cos(s[4])),s[3]])
    def step(self,delta,speed,dt):
        for _ in range(round(dt/self.dt)):self.car.update_pose(delta,speed)
        return self.read()
    def close(self):pass

class MetaPlant:
    def __init__(self,cfg):
        from metadrive import MetaDriveEnv
        self.cfg=cfg;self.L=cfg['metadrive_wheelbase_m'];self.dt=cfg['metadrive_physics_dt_s']
        self.env=MetaDriveEnv(dict(use_render=False,map='SSS',traffic_density=0,num_scenarios=3000,start_seed=0,
            decision_repeat=1,physics_world_step_size=self.dt,horizon=20000,out_of_road_done=False,crash_vehicle_done=False,crash_object_done=False,
            vehicle_config=dict(vehicle_model='static_default',lidar=dict(num_lasers=0),side_detector=dict(num_lasers=0),lane_line_detector=dict(num_lasers=0))))
        self.ground_nodes=[]
    def reset(self,seed,pose,speed):
        from panda3d.bullet import BulletRigidBodyNode,BulletPlaneShape
        from panda3d.core import Vec3,BitMask32
        # Remove the previous custom plane before the engine resets its native vehicle/map.
        for world,node,np_node in self.ground_nodes:world.removeRigidBody(node);np_node.removeNode()
        self.ground_nodes=[]
        self.env.reset(seed=seed)
        self.pending_s=0.
        vehicle=self.env.agent;worlds=[self.env.engine.physics_world.dynamic_world,self.env.engine.physics_world.static_world]
        # Replace arena ground/map collision surfaces, never vehicle dynamics.
        for world in worlds:
            for body in list(world.getRigidBodies()):
                if body!=vehicle.body:world.removeRigidBody(body)
            for ghost in list(world.getGhosts()):world.removeGhost(ghost)
            ground=BulletRigidBodyNode('experiment_flat_ground');ground.addShape(BulletPlaneShape(Vec3(0,0,1),0));ground.setIntoCollideMask(BitMask32.allOn())
            np_node=self.env.engine.worldNP.attachNewNode(ground);world.attachRigidBody(ground);self.ground_nodes.append((world,ground,np_node))
        vehicle.set_position(np.array(pose[:2]),height=.6);vehicle.set_heading_theta(pose[2]);vehicle.set_velocity([math.cos(pose[2]),math.sin(pose[2])],value=speed)
        for _ in range(round(self.cfg['settling_s']/self.dt)):self.step(0,speed,self.dt)
        self.metadata=dict(component='native MetaDrive StaticDefaultVehicle/Bullet',mass_kg=float(vehicle.MASS),wheelbase_m=float(vehicle.FRONT_WHEELBASE+vehicle.REAR_WHEELBASE),physics_dt_s=self.dt,arena='flat native Bullet plane; original road surfaces removed',native_sensor_models_used=False,corridor_checks='shared geometry, not native road-network score')
        return self.read()
    def read(self):
        v=self.env.agent;return np.array([*v.position,math.atan2(math.sin(v.heading_theta),math.cos(v.heading_theta)),v.speed])
    def step(self,delta,speed,dt):
        v=self.env.agent;u=float(np.clip(.5*(speed-v.speed),-1,1))
        self.pending_s+=dt
        while self.pending_s>=self.dt-1e-10:
            self.env.step([delta/math.radians(v.max_steering),u]);self.pending_s-=self.dt
        return self.read()
    def close(self):self.env.close()
