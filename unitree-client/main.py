#!/usr/bin/env python3
import argparse
import asyncio
import json
import logging
import signal
import sys
import time
from typing import Dict, List

import websockets
from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.g1.loco.g1_loco_client import LocoClient

# Configuration constants
FORWARD_SPEED = 0.3  # Forward/backward speed in m/s
LATERAL_SPEED = 0.2  # Left/right speed in m/s
ROTATION_SPEED = 0.6  # Rotation speed in rad/s

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("robot_client")

# Client statuses
STATUS_DISCONNECTED = "disconnected"
STATUS_WAITING = "waiting"
STATUS_PAIRED = "paired"


class RobotClient:
    def __init__(self, server_url: str, mock: bool = True):
        self.server_url = server_url
        self.ws = None
        self.client_id = None
        self.paired_with = None
        self.status = STATUS_DISCONNECTED
        self.running = False
        self.reconnect_delay = 1  # Start with 1 second delay
        self.max_reconnect_delay = 30  # Max 30 seconds between reconnects
        self.gesture_data_queue = asyncio.Queue()  # Queue for received gesture data
        self.robot: LocoClient | None = None

        if not mock:
            # Initialize Unitree robot client
            try:
                ChannelFactoryInitialize(0, "eth0")
            except Exception as e:
                logger.error(f"Failed to initialize ChannelFactory: {e}")
                self.running = False
            try:
                self.robot = LocoClient()
                self.robot.SetTimeout(10.0)
                self.robot.Init()
            except Exception as e:
                logger.error(f"Failed to initialize robot client: {e}")
                self.running = False
            finally:
                self.running = True
        else:
            self.robot = None
            self.running = True

    async def connect(self):
        """Connect to the server and identify as a robot client"""
        try:
            logger.info(f"Connecting to {self.server_url}")
            self.ws = await websockets.connect(self.server_url)

            # Identify as robot
            await self.ws.send(json.dumps({"type": "robot"}))
            logger.info("Connected and identified as robot client")

            # Reset reconnect delay on successful connection
            self.reconnect_delay = 1

            return True
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    async def handle_messages(self):
        """Process incoming messages from the server"""
        try:
            while self.running and self.ws:
                message = await self.ws.recv()

                try:
                    data = json.loads(message)
                    await self.process_message(data)
                except json.JSONDecodeError:
                    logger.warning(f"Received non-JSON message: {message}")
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"Connection closed: {e}")
            self.status = STATUS_DISCONNECTED
            self.paired_with = None
        except Exception as e:
            logger.error(f"Error handling messages: {e}")

    async def process_message(self, data: Dict):
        """Process different types of messages"""
        if data.get("type") == "status_update":
            await self.handle_status_update(data)
        elif data.get("type") == "ping":
            await self.handle_ping(data)
        elif "hand" in data and "origin" in data and "direction" in data:
            await self.handle_gesture_data(data)
        elif data.get("type") == "walk":
            await self.handle_walk(data)
        elif data.get("type") in [
            "stand",
            "stand_low",
            "stand_high",
            "sit",
            "wave",
            "wave_turn",
            "shake_hand",
            "zero_torque",
            "damp",
        ]:
            await self.handle_action(data)
        else:
            logger.info(f"Received message: {data}")

    async def handle_status_update(self, data: Dict):
        """Handle status update messages from the server"""
        old_status = self.status
        self.status = data.get("status")
        # Always reset the movement to zero when the status changes.
        if self.robot:
            self.robot.Move(0, 0, 0)
        if self.status == STATUS_PAIRED:
            self.paired_with = data.get("paired_with", {})
            logger.info(
                f"Paired with {self.paired_with.get('type')} client (ID: {self.paired_with.get('id')})"
            )
        elif old_status == STATUS_PAIRED and self.status == STATUS_WAITING:
            logger.info(f"Unpairing: {data.get('message')}")
            self.paired_with = None
        elif self.status == STATUS_WAITING:
            if "client_id" in data:
                self.client_id = data.get("client_id")
            logger.info(f"Waiting for pair: {data.get('message')}")
        elif self.status == STATUS_DISCONNECTED:
            logger.info(f"Disconnected: {data.get('message')}")

    async def handle_ping(self, data: Dict):
        """Respond to ping messages for latency measurement"""
        timestamp = data.get("timestamp")
        if timestamp:
            await self.ws.send(
                json.dumps({"type": "pong", "ping_timestamp": timestamp})
            )

    async def handle_gesture_data(self, data: Dict):
        """Process gesture data received from paired spectacles client"""
        # Add to queue for processing by the robot control system
        await self.gesture_data_queue.put(data)

        # Print information about the gesture
        hand = data.get("hand", "unknown")
        origin = data.get("origin", [0, 0, 0])
        direction = data.get("direction", [0, 0, 0])

        logger.info(f"Gesture: Hand={hand}, Origin={origin}, Direction={direction}")

        # Here you would add code to control the Unitree robot based on the gesture data
        # For example:
        await self.process_robot_command(hand, origin, direction)

    async def handle_action(self, data: Dict):
        action_type = data.get("type", "")

        if action_type == "stand":
            self.robot.StandUp()
        elif action_type == "stand_low":
            self.robot.LowStand()
        elif action_type == "stand_high":
            self.robot.HighStand()
        elif action_type == "sit":
            self.robot.Sit()
        elif action_type == "wave":
            self.robot.WaveHand()
        elif action_type == "wave_turn":
            self.robot.WaveHand(True)
        elif action_type == "shake_hand":
            self.robot.ShakeHand()
        elif action_type == "zero_torque":
            self.robot.ZeroTorque()
        elif action_type == "damp":
            self.robot.Damp()
        else:
            logger.warning(f"Unknown action: {data}")

    async def handle_walk(self, data: Dict):
        # Clamp speed values to the configured limits
        x_vel = max(min(data.get("long", 0.0), FORWARD_SPEED), -FORWARD_SPEED)
        y_vel = max(min(data.get("lat", 0.0), LATERAL_SPEED), -LATERAL_SPEED)
        yaw_vel = max(min(data.get("yaw", 0.0), ROTATION_SPEED), -ROTATION_SPEED)
        self.robot.Move(x_vel, y_vel, yaw_vel)

    async def process_robot_command(
        self, hand: str, origin: List[float], direction: List[float]
    ):
        """Convert gesture data to robot commands"""
        # This is a placeholder for actual robot control logic
        # You would implement your specific control logic here

        # Example: Simple mapping of gesture direction to movement
        x_dir = direction[0]
        y_dir = direction[1]
        z_dir = direction[2]

        # Example logic:
        if abs(x_dir) > abs(y_dir) and abs(x_dir) > abs(z_dir):
            # Primarily left/right motion
            if x_dir > 0.5:
                logger.info("Robot command: Turn right")
                # robot.turn_right(magnitude=x_dir)
            elif x_dir < -0.5:
                logger.info("Robot command: Turn left")
                # robot.turn_left(magnitude=abs(x_dir))
        elif abs(y_dir) > abs(x_dir) and abs(y_dir) > abs(z_dir):
            # Primarily up/down motion
            if y_dir > 0.5:
                logger.info("Robot command: Look up")
                # robot.look_up(magnitude=y_dir)
            elif y_dir < -0.5:
                logger.info("Robot command: Look down")
                # robot.look_down(magnitude=abs(y_dir))
        elif abs(z_dir) > abs(x_dir) and abs(z_dir) > abs(y_dir):
            # Primarily forward/backward motion
            if z_dir > 0.5:
                logger.info("Robot command: Move backward")
                # robot.move_backward(magnitude=z_dir)
            elif z_dir < -0.5:
                logger.info("Robot command: Move forward")
                # robot.move_forward(magnitude=abs(z_dir))

    async def send_status(self):
        """Send periodic status updates to the spectacles client if paired"""
        if self.status == STATUS_PAIRED and self.ws:
            try:
                await self.ws.send(
                    json.dumps(
                        {
                            "type": "robot_status",
                            "timestamp": time.time(),
                            "battery": 85,  # Example value
                            "position": [0, 0, 0],  # Example position
                            "orientation": [0, 0, 0, 1],  # Example quaternion
                        }
                    )
                )
            except Exception as e:
                logger.error(f"Error sending status: {e}")

    async def run(self):
        """Main run loop with automatic reconnection"""
        while self.running:
            connected = await self.connect()

            if connected:
                # Start message handler
                message_task = asyncio.create_task(self.handle_messages())

                # Status update loop
                while self.running and self.ws:
                    if self.status == STATUS_PAIRED:
                        await self.send_status()
                    await asyncio.sleep(1)

                # Wait for message handler to complete
                await message_task

            if self.running:
                # Implement exponential backoff for reconnection
                logger.info(f"Reconnecting in {self.reconnect_delay} seconds...")
                await asyncio.sleep(self.reconnect_delay)
                self.reconnect_delay = min(
                    self.reconnect_delay * 1.5, self.max_reconnect_delay
                )

    async def stop(self):
        """Stop the client gracefully"""
        self.running = False
        if self.ws:
            await self.ws.close()
        logger.info("Robot client stopped")


async def main():
    parser = argparse.ArgumentParser(
        description="Unitree Robot Client for Spectacles Coordination"
    )
    parser.add_argument(
        "--server",
        default="wss://spectaclexr.com/ws",
        help="Coordination server WebSocket URL",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        default=False,
        help="Run in mock mode for testing purposes",
    )
    args = parser.parse_args()

    client = RobotClient(args.server, mock=args.mock)

    # Handle Ctrl+C gracefully
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(client)))

    await client.run()


async def shutdown(client):
    """Graceful shutdown"""
    logger.info("Shutting down...")
    await client.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Exiting...")
        sys.exit(0)
