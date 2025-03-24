import asyncio
import logging
import time
from collections import deque

import numpy as np
from PIL import Image

from ik.g1_controller import G1_29_ArmController, G1_29_JointArmIndex
from ik.g1_solver import G1_29_ArmIK


class HandMovement:
    type: str = "hand_movement"
    handType: str = ""
    wristTransform: np.ndarray
    fingerPositions: np.ndarray
    headRotQuat: np.ndarray
    timestamp: int = 0

    def __init__(self, data: dict):
        # Parse basic fields.
        self.handType = data.get("handType", "")
        self.timestamp = data.get("timestamp", 0)

        # The "transform" key is expected to be a list where:
        #   - The first element is the flattened 4x4 wrist transform.
        #   - Next elements are 3D finger positions.
        #   - Last element is a quaternion for head rotation
        transform = data.get("transform", [])
        if not transform or len(transform) < 1:
            msg = "Invalid data: missing transform information."
            raise ValueError(msg)

        # Convert the wrist transform back to a 4x4 NumPy array.
        self.wristTransform = np.array(transform[0]).reshape(4, 4)
        # Adjust from centimeters to meters.
        self.wristTransform[0:3, 3] /= 100.0

        # Remaining until last are fingers
        self.fingerPositions = np.array(transform[1:-1]).reshape(-1, 3)
        # Adjust from centimeters to meters.
        self.fingerPositions /= 100.0
        # Finally head rotation quat
        self.headRotQuat = np.array(transform[-1]).reshape(4)

class IK:
    def __init__(self, ik_solver, t: np.ndarray):
        """
        Initialize the IK transformer and solver.

        :param ik_solver: An instance of an IK solver that implements a method `solve_ik`.
        :param t: Transformation matrix from user head to robot base (waist).
        """
        self.ik_solver = ik_solver
        self.T_robotBase_from_userHead = t

    def transform_wrist(self, wrist_transform: np.ndarray):
        return np.dot(self.T_robotBase_from_userHead, wrist_transform)

    def compute_ik(self, left_wrist_transform: np.ndarray, right_wrist_transform: np.ndarray, current_q: np.ndarray, current_dq: np.ndarray):
        """
        Computes the IK solution with left and right wrist transforms.

        :param left_wrist_transform: 4x4 numpy array for the left wrist (Spectacles frame).
        :param right_wrist_transform: 4x4 numpy array for the right wrist (Spectacles frame).
        :param current_q: numpy array representing the current joint configuration.
        :param current_dq: numpy array representing the current joint velocities.
        :return: Tuple (q_sol, tauff_sol) from the IK solver.
        """
        # Transform both wrist transforms from the Spectacles (user head) frame into the robot base frame.
        left_robot_transform = self.transform_wrist(left_wrist_transform)
        right_robot_transform = self.transform_wrist(right_wrist_transform)

        # Call the IK solver using the transformed wrist targets.
        q_sol, tauff_sol = self.ik_solver.solve_ik(
            left_robot_transform, right_robot_transform, current_q, current_dq
        )
        return q_sol, tauff_sol


class ArmsAndHands:
    def __init__(self, t: np.ndarray = None, ik_solver = None, arm_controller = None, mock = False):
        """
        Initialize the Arms and Hands controller.

        If no controller is provided

        :param t: Transformation matrix from user head to robot base (waist).
        :param ik_solver: An instance of an IK solver.
        :param arm_controller: An instance of the robot's low-level arm controller.
        """
        if ik_solver is None:
            ik_solver = G1_29_ArmIK(Unit_Test=mock, Visualization=True)
        if arm_controller is None:
            if not mock:
                pass
                # self.controller = G1_29_ArmController()
            else:
                self.controller = None
        else:
            self.controller = arm_controller
        if t is None:
            t = np.eye(4)  # Default to identity transformation
        self.ik = IK(ik_solver, t)
        self.current_q = np.array([0.0 for i in G1_29_JointArmIndex])
        self.current_dq = np.array([0.0 for i in G1_29_JointArmIndex])
        self.q_sol = None
        self.tauff_sol = None
        self.left_wrist_transform = np.eye(4)
        self.right_wrist_transform = np.eye(4)
        self.computing_ik_lock = asyncio.Lock()

        # Add timing tracking for performance monitoring
        self.logger = logging.getLogger("ArmsAndHands")
        self.message_timestamps = deque(maxlen=30)  # Store last 30 message timestamps
        self.processing_times = deque(maxlen=30)    # Store last 30 processing times
        self.last_log_time = 0
        self.log_interval = 5.0  # Log performance stats every 5 seconds

    async def move(self, movement: HandMovement, mock: bool = False):
        """
        Move the arms and hands based on the provided movement data.
        This method is debounced - if it's called while a previous IK computation
        is in progress, the new call will be skipped.

        :param movement: An instance of HandMovement containing wrist and finger data.
        :param mock: If True, the function will not send commands to the robot but will still run the IK solver.
        :return: Boolean indicating whether the movement was processed or skipped.
        """
        # Track incoming message timestamp
        current_time = time.time()
        self.message_timestamps.append(current_time)

        # Update the target wrist transforms regardless of whether we'll compute IK
        if movement.handType == "left":
            self.left_wrist_transform = movement.wristTransform
        elif movement.handType == "right":
            self.right_wrist_transform = movement.wristTransform

        # Try to acquire the lock without blocking
        if self.computing_ik_lock.locked():
            # Lock is already held, skip this update
            return False

        async with self.computing_ik_lock:
            start_time = time.time()

            # Get current joint positions and velocities
            self.current_q = self.controller.get_current_dual_arm_q() if not mock else self.current_q
            self.current_dq = self.controller.get_current_dual_arm_dq() if not mock else self.current_dq

            # Compute IK solution
            self.q_sol, self.tauff_sol = self.ik.compute_ik(
                self.left_wrist_transform,
                self.right_wrist_transform,
                self.current_q,
                self.current_dq,
            )

            # Apply the solution
            if not mock:
                self.controller.ctrl_dual_arm(self.q_sol, self.tauff_sol)
            else:
                # Update current q and dq for mock mode
                self.current_q = self.q_sol
                self.current_dq = self.tauff_sol

            # Calculate and store processing time
            end_time = time.time()
            processing_time = end_time - start_time
            self.processing_times.append(processing_time)

            # Log performance stats periodically
            if end_time - self.last_log_time >= self.log_interval and len(self.message_timestamps) > 1:
                self.last_log_time = end_time

                # Calculate incoming message rate (messages per second)
                if len(self.message_timestamps) >= 2:
                    time_span = self.message_timestamps[-1] - self.message_timestamps[0]
                    msg_rate = (len(self.message_timestamps) - 1) / time_span if time_span > 0 else 0
                else:
                    msg_rate = 0

                # Calculate average processing time
                avg_processing_time = sum(self.processing_times) / len(self.processing_times) if self.processing_times else 0

                # Calculate real-time ratio (processing time / message interval)
                real_time_ratio = avg_processing_time * msg_rate if msg_rate > 0 else 0

                self.logger.info(
                    f"IK Performance: Avg processing time: {avg_processing_time:.4f}s, "
                    f"Message rate: {msg_rate:.2f} msg/s, Real-time ratio: {real_time_ratio:.2f} "
                )

            return True

    def reset(self):
        """
        Reset the arm and hand controller to its initial state.
        """
        self.controller.ctrl_dual_arm_go_home()
        self.left_wrist_transform = np.eye(4)
        self.right_wrist_transform = np.eye(4)
        self.current_q = None
        self.current_dq = None
        self.q_sol = None
        self.tauff_sol = None

    def render(self, x=0, y=0, z=0, w=1) -> Image:
        """
        Render image of movement via meshcat
        """
        return self.ik.ik_solver.capture_frame(x, y, z, w)
