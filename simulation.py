"""Franka Panda: physical grasp demo and interactive Cartesian control."""
import argparse
import time

import pybullet as p
import pybullet_data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gui', action='store_true', help='Open a desktop GUI')
    parser.add_argument('--manual', action='store_true', help='GUI sliders control the hand')
    args = parser.parse_args()
    if args.manual and not args.gui:
        parser.error('--manual requires --gui')
    p.connect(p.GUI if args.gui else p.DIRECT)
    try:
        p.setAdditionalSearchPath(pybullet_data.getDataPath())
        p.setGravity(0, 0, -9.81)
        p.setTimeStep(1 / 240)
        p.loadURDF('plane.urdf')
        robot = p.loadURDF('franka_panda/panda.urdf', useFixedBase=True)
        cube = p.loadURDF('cube_small.urdf', [0.5, 0, 0.025])
        p.changeDynamics(cube, -1, lateralFriction=1.5)
        for link in (9, 10):
            p.changeDynamics(robot, link, lateralFriction=1.5)
        home = [0, -0.4, 0, -2.4, 0, 2.0, 0.8]
        for joint, angle in enumerate(home):
            p.resetJointState(robot, joint, angle)
        for joint in (9, 10):
            p.resetJointState(robot, joint, 0.04)
        orientation = p.getQuaternionFromEuler([3.14159265, 0, 0])

        def move(target, opening, steps):
            angles = p.calculateInverseKinematics(robot, 11, target, orientation,
                                                 maxNumIterations=100)
            p.setJointMotorControlArray(robot, list(range(7)), p.POSITION_CONTROL,
                                       targetPositions=angles[:7], forces=[120]*7)
            p.setJointMotorControlArray(robot, [9, 10], p.POSITION_CONTROL,
                                       targetPositions=[opening]*2, forces=[40]*2)
            for _ in range(steps):
                p.stepSimulation()
                if args.gui:
                    time.sleep(1 / 240)

        if args.manual:
            sliders = [p.addUserDebugParameter(name, low, high, default)
                       for name, low, high, default in
                       [('x', .2, .7, .5), ('y', -.35, .35, 0),
                        ('z', .03, .65, .3), ('finger opening', 0, .04, .04)]]
            print('Use the GUI sliders. Close with Ctrl+C.')
            while p.isConnected():
                values = [p.readUserDebugParameter(s) for s in sliders]
                move(values[:3], values[3], 1)
        else:
            move([.5, 0, .3], .04, 480)
            move([.5, 0, .025], .04, 480)
            move([.5, 0, .025], 0, 240)
            move([.5, 0, .3], 0, 480)
            height = p.getBasePositionAndOrientation(cube)[0][2]
            print(f'Cube height after grasp: {height:.3f} m')
            if height < .15:
                raise RuntimeError('Grasp failed: cube did not lift')
            print('PASS: cube lifted using physical finger contact (no attachment constraint).')
            if args.gui:
                print('Demo complete. Close with Ctrl+C.')
                while p.isConnected():
                    move([.5, 0, .3], 0, 1)
    except KeyboardInterrupt:
        pass
    finally:
        if p.isConnected():
            p.disconnect()


if __name__ == '__main__':
    main()
