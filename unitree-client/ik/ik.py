import asyncio
import logging
import time
from collections import deque
from enum import Enum

import numpy as np
from PIL import Image
from scipy.spatial.transform import Rotation as R

from ik.g1_controller import G1_29_ArmController, G1_29_JointArmIndex
from ik.g1_solver import G1_29_ArmIK

## Transformation matrix to flip axes from Spectacles to Robot space.
# T_xr_to_robot_space = np.array(
#   [
#       [0, 0, -1, 0],  # Robot x = -z
#       [-1, 0, 0, 0],  # Robot y = -x
#       [0, 1, 0, 0],  # Robot z = y
#       [0, 0, 0, 1],
#   ]
# )
#
## Transformation matrix to flip left wrist axes from Spectacles to Robot space.
# T_xr_left_wrist_to_robot_space = np.array(
#   [
#       [0, 0, -1, 0],  # Robot x = -z
#       [-1, 0, 0, 0],  # Robot y = y
#       [0, 1, 0, 0],  # Robot z = x
#       [0, 0, 0, 1],
#   ]
# )
#
## Transformation matrix to flip right wrist axes from Spectacles to Robot space.
# T_xr_right_wrist_to_robot_space = np.array(
#   [
#       [0, 0, -1, 0],  # Robot x = -z
#       [-1, 0, 0, 0],  # Robot y = -x
#       [0, 1, 0, 0],  # Robot z = y
#       [0, 0, 0, 1],
#   ]
# )

# Rotation from Spectacles frame (X Right, Y Up, Z Back) to Robot frame (X Front, Y Left, Z Up)
R_rw_sw = np.array([[0, 0, -1], [-1, 0, 0], [0, 1, 0]])
T_rw_sw = np.eye(4)
T_rw_sw[:3, :3] = R_rw_sw
# robot world -> spectacles world
T_rw_sw = np.linalg.inv(T_rw_sw)

R_wrists = R.from_euler("xyz", [np.pi / 2, 0, np.pi / 2])

# Rotation from Spectacles left wrist in head frame (X Right, Y Up, Z Back) to Robot left hand (X Front, Y Up, Z Right)
R_rlh_slw = R.from_matrix(np.array([[0, 0, -1], [0, 1, 0], [1, 0, 0]])) * R_wrists
T_rlh_slw = np.eye(4)
T_rlh_slw[:3, :3] = R_rlh_slw.as_matrix()
# spectacles left wrist -> robot left hand
T_slw_rlh = np.linalg.inv(T_rlh_slw)

# Rotation from Spectacles right wrist in head frame (X Right, Y Up, Z Back) to Robot right hand (X Front, Y Down, Z Left)
R_rrh_srw = R.from_matrix(np.array([[0, 0, -1], [0, -1, 0], [-1, 0, 0]])) * R_wrists
T_rrh_srw = np.eye(4)
T_rrh_srw[:3, :3] = R_rrh_srw.as_matrix()
# spectacles right wrist -> robot right hand
T_srw_rrh = np.linalg.inv(T_rrh_srw)

# For G1 initial position
const_right_wrist_default = np.array([[1, 0, 0, 0.15], [0, 1, 0, 1.13], [0, 0, 1, -0.3], [0, 0, 0, 1]])

# For G1 initial position
const_left_wrist_default = np.array([[1, 0, 0, -0.15], [0, 1, 0, 1.13], [0, 0, 1, -0.3], [0, 0, 0, 1]])

# Offset, in meters, from the robot's world origin (its waist) to the robot's head.
offset_rw_rh = np.array(
    [
        0.15,  # x = front
        0.0,  # y = left
        0.45,  # z = up
    ]
)


class RobotHandType(Enum):
    DEX3 = "./urdf/dex_hand/unitree_dex3.yml"
    INSPIRE = "./urdf/inspire_hand/inspire_hand.yml"


def fast_mat_inv(mat: np.ndarray) -> np.ndarray:
    """
    Fast matrix inversion for 4x4 matrices.
    """
    if mat.shape != (4, 4):
        msg = "Input matrix must be 4x4."
        raise ValueError(msg)
    ret = np.eye(4)
    ret[:3, :3] = mat[:3, :3].T
    ret[:3, 3] = -mat[:3, :3].T @ mat[:3, 3]
    return ret

class HandMovement:
    type: str = "hand_movement"
    # The hand, either "left" or "right"
    handType: str = ""
    # Spectacles data.
    _rawWristTransform: np.ndarray
    # Spectacles data. These are already relative to the wrists.
    _rawFingerPositions: np.ndarray
    # Spectacles data.
    _rawHeadTransform: np.ndarray
    timestamp: int = 0
    # Head pose in Robot space
    headMat: np.ndarray = np.eye(4)
    # Left wrist position and rotation in robot space
    leftWristMat: np.ndarray = np.copy(const_left_wrist_default)
    # Right wrist position and rotation in robot space
    rightWristMat: np.ndarray = np.copy(const_right_wrist_default)
    # Left hand finger positions in left-wrist space.
    leftHandFingerPos: np.ndarray | None = None
    # Right hand finger positions in right-wrist space.
    rightHandFingerPos: np.ndarray | None = None

    def __init__(self, data: dict, robot_hand_type=RobotHandType.INSPIRE):
        self.handType = data.get("handType", "")
        self.timestamp = data.get("timestamp", 0)

        # The "transform" key is expected to be a list where:
        #   - The first element is the flattened 4x4 wrist transform.
        #   - Next elements are 3D finger positions.
        #   - Last element is a 4x4 for head transform
        transform = data.get("transform", [])
        if not transform or len(transform) < 3:
            msg = "Invalid data: missing transform information."
            raise ValueError(msg)

        #
        # Extract and scale.
        #

        # Head transform
        self.headMat = np.array(transform[-1]).reshape(4, 4)

        # Wrist transform
        self._rawWristTransform = np.array(transform[0]).reshape(4, 4)
        self._rawWristTransform[0:3, 3] /= 100.0  # cm -> m

        # Finger positions are relative to the wrist.
        self._rawFingerPositions = np.array(transform[1:-1]).reshape(-1, 3)
        self._rawFingerPositions /= 100.0  # cm -> m

        #
        # Convert from Spectacles AR coordinate space to Robot space
        #

        T_rw_sh = T_rw_sw @ self.headMat

        # Head pose in Robot world space
        self.headMat = np.eye(4)

        # Spectacles wrist pose relative to the head
        T_sh_swrist = self._rawWristTransform

        if self.handType == "left":
            T_rw_slw = T_rw_sh @ T_sh_swrist
            self.leftWristMat = T_rw_slw @ T_slw_rlh
            self.leftWristMat[0:3, 3] += offset_rw_rh
            R_rlh_slw_mat = T_rlh_slw[:3, :3]
            self.leftHandFingerPos = (R_rlh_slw_mat @ self._rawFingerPositions.T).T
        elif self.handType == "right":
            T_rw_srw = T_rw_sh @ T_sh_swrist
            self.rightWristMat = T_rw_srw @ T_srw_rrh
            self.rightWristMat[0:3, 3] += offset_rw_rh
            R_rrh_srw_mat = T_rrh_srw[:3, :3]
            self.rightHandFingerPos = (R_rrh_srw_mat @ self._rawFingerPositions.T).T
        else:
            msg = f"Invalid hand type: {self.handType}, expected 'left' or 'right'."
            raise ValueError(msg)


class IK:
    def __init__(self, ik_solver):
        """
        Initialize the IK transformer and solver.

        :param ik_solver: An instance of an IK solver that implements a method `solve_ik`.
        :param t: Transformation matrix from user head to robot base (waist).
        """
        self.ik_solver = ik_solver

    def compute_ik(self, left: np.ndarray, right: np.ndarray, current_q: np.ndarray, current_dq: np.ndarray):
        """
        Computes the IK solution with left and right wrist and hand matrices.

        :param left: numpy array representing the left wrist and hand matrices.
        :param right: numpy array representing the right wrist and hand matrices.
        :param current_q: numpy array representing the current joint configuration.
        :param current_dq: numpy array representing the current joint velocities.
        :return: Tuple (q_sol, tauff_sol) from the IK solver.
        """
        # Transform both wrist transforms from the Spectacles (user head) frame into the robot base frame.

        # Call the IK solver using the transformed wrist targets.
        q_sol, tauff_sol = self.ik_solver.solve_ik(left, right, current_q, current_dq)
        return q_sol, tauff_sol


class ArmsAndHands:
    def __init__(self, ik_solver=None, arm_controller=None, mock=False):
        """
        Initialize the Arms and Hands controller.

        If no controller is provided and mock is False, it will attempt to create a new controller instance.

        :param ik_solver: An instance of an IK solver.
        :param arm_controller: An instance of the robot's low-level arm controller.
        """
        if ik_solver is None:
            ik_solver = G1_29_ArmIK(Unit_Test=mock, Visualization=True)
        if arm_controller is None:
            if not mock:
                try:
                    self.controller = G1_29_ArmController()
                except Exception as e:
                    logging.exception(f"Failed to initialize default robot controller, falling back to mock.")
                    mock = True
                    self.controller = None
            else:
                self.controller = None
        else:
            self.controller = arm_controller
        self.ik = IK(ik_solver)
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
        self.processing_times = deque(maxlen=30)  # Store last 30 processing times
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
            self.left_wrist_transform = movement.leftWristMat
        elif movement.handType == "right":
            self.right_wrist_transform = movement.rightWristMat

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
