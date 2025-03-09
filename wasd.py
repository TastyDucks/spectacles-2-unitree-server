#!/usr/bin/env python3
"""
Unitree G1 Robot Control Script
This script provides keyboard-based control for the Unitree G1 robot using WASD keys.
"""

import sys
import termios
import time
import tty

from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.g1.loco.g1_loco_client import LocoClient

# Configuration constants
FORWARD_SPEED = 0.3  # Forward/backward speed in m/s
LATERAL_SPEED = 0.2  # Left/right speed in m/s
ROTATION_SPEED = 0.6  # Rotation speed in rad/s


def getch():
    """
    Get a single character from the user without requiring Enter key.
    Returns:
        str: Single character input from the user
    """
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch


def print_controls():
    """Display available control commands to the user."""
    print("\nUnitree G1 Robot Controls:")
    print("-------------------------")
    print("Movement:")
    print("  W: Move Forward")
    print("  S: Move Backward")
    print("  A: Move Left")
    print("  D: Move Right")
    print("  Q: Rotate Left")
    print("  E: Rotate Right")
    print("\nPosture Commands:")
    print("  F: Stand Up")
    print("  G: Sit Down")
    print("  H: High Stand")
    print("  L: Low Stand")
    print("  Z: Zero Torque")
    print("\nGesture Commands:")
    print("  V: Wave Hand")
    print("  B: Wave Hand with Turn")
    print("  N: Shake Hand")
    print("\nOther Commands:")
    print("  Space: Stop/Damp")
    print("  Esc: Quit")
    print("\nCurrent Status: Robot Ready")


def initialize_robot(network_interface):
    """
    Initialize the robot client for movement control.
    Args:
        network_interface (str): Network interface to use for robot communication
    Returns:
        LocoClient: Initialized robot client
    """
    # Initialize SDK
    try:
        ChannelFactoryInitialize(0, network_interface)
    except Exception as e:
        raise Exception(f"Failed to initialize SDK: {str(e)}")

    # Create and initialize client
    try:
        client = LocoClient()
        client.SetTimeout(10.0)
        client.Init()
        return client
    except Exception as e:
        raise Exception(f"Failed to initialize client: {str(e)}")


def handle_movement(key, client):
    """
    Handle movement commands based on key press.
    Args:
        key (str): The pressed key
        client (LocoClient): Robot client instance
    Returns:
        bool: True if should continue, False if should exit
    """
    x_vel = 0.0
    y_vel = 0.0
    yaw_vel = 0.0
    status = "Stopped          "

    if key == "w":
        x_vel = FORWARD_SPEED
        status = "Moving Forward    "
    elif key == "s":
        x_vel = -FORWARD_SPEED
        status = "Moving Backward   "
    elif key == "a":
        y_vel = LATERAL_SPEED
        status = "Moving Left       "
    elif key == "d":
        y_vel = -LATERAL_SPEED
        status = "Moving Right      "
    elif key == "q":
        yaw_vel = ROTATION_SPEED
        status = "Rotating Left     "
    elif key == "e":
        yaw_vel = -ROTATION_SPEED
        status = "Rotating Right    "
    elif key == "g":
        try:
            print("\nSitting down...")
            client.Sit()
            time.sleep(STARTUP_DELAY)
            status = "Sitting Down      "
        except Exception as e:
            print(f"\nError during sit down: {str(e)}")
    elif key == "f":
        try:
            print("\nStanding up...")
            client.StandUp()
            status = "Standing Up       "
        except Exception as e:
            print(f"\nError during stand up: {str(e)}")
            status = "Stand Up Failed   "
    elif key == "h":
        try:
            print("\nSwitching to high stand...")
            client.HighStand()
            time.sleep(STARTUP_DELAY)
            status = "High Stand        "
        except Exception as e:
            print(f"\nError during high stand: {str(e)}")
    elif key == "l":
        try:
            print("\nSwitching to low stand...")
            client.LowStand()
            time.sleep(STARTUP_DELAY)
            status = "Low Stand         "
        except Exception as e:
            print(f"\nError during low stand: {str(e)}")
    elif key == "z":
        try:
            print("\nSwitching to zero torque...")
            client.ZeroTorque()
            status = "Zero Torque       "
        except Exception as e:
            print(f"\nError during zero torque: {str(e)}")
    elif key == "v":
        try:
            print("\nWaving hand...")
            client.WaveHand()
            status = "Waving Hand       "
        except Exception as e:
            print(f"\nError during wave hand: {str(e)}")
    elif key == "b":
        try:
            print("\nWaving hand with turn...")
            client.WaveHand(True)
            status = "Waving With Turn  "
        except Exception as e:
            print(f"\nError during wave hand with turn: {str(e)}")
    elif key == "n":
        try:
            print("\nShaking hand...")
            client.ShakeHand()
            status = "Shaking Hand      "
        except Exception as e:
            print(f"\nError during shake hand: {str(e)}")
    elif key == " ":
        try:
            print("\nDamping motors...")
            client.Damp()
            status = "Damped            "
        except Exception as e:
            print(f"\nError during damp: {str(e)}")
    elif ord(key) == 27:  # Esc key
        print("\nExiting...")
        return False

    print(f"\rCurrent Status: {status}", end="")
    if key in [
        "w",
        "s",
        "a",
        "d",
        "q",
        "e",
    ]:  # Only send move command for movement keys
        client.Move(x_vel, y_vel, yaw_vel)
    sys.stdout.flush()
    return True


def main():
    """Main function to run the robot control program."""
    if len(sys.argv) < 2:
        print(f"Usage: python3 {sys.argv[0]} networkInterface")
        sys.exit(1)

    print("\nWARNING: Please ensure there are no obstacles around the robot.")
    print("IMPORTANT: Make sure the robot is NOT in debug mode!")
    print("         1. Do not use L2+R2, L2+A, L2+B on controller")
    print("         2. Use L1+A and L1+UP on controller to enable movement mode")
    print("         3. If in debug mode, reboot the robot to exit it")
    input("Press Enter when ready...")

    try:
        # Initialize robot
        client = initialize_robot(sys.argv[1])
        print_controls()

        # Main control loop
        while True:
            key = getch().lower()
            if not handle_movement(key, client):
                break

    except KeyboardInterrupt:
        print("\nProgram interrupted by user")
    except Exception as e:
        print(f"\nError occurred: {str(e)}")
    finally:
        # Ensure robot stops safely
        try:
            client.Move(0, 0, 0)
            print("\nRobot stopped safely")
        except Exception as e:
            print(f"\nError stopping robot: {str(e)}")


if __name__ == "__main__":
    main()
