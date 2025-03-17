# Spectacles-2-Unitree Coordination Server

Connects Snapchat Spectacles Lens client to a Unitree G1 robot client for XR teleop.

## Usage

### Development

1. Install Docker or a similar container engine like Orbstack. On MacOS with Homebrew:
   ```sh
   brew install docker # or brew install --cask orbstack
   ```
2. If using VS Code, install the [Remote Development extension pack](vscode:extension/ms-vscode-remote.vscode-remote-extensionpack). If you're using Cursor, you can grab that extension by following [these instructions](https://www.cursor.com/en/how-to-install-extension).
3. Reopen this project in a container: <kbd>⌘</kbd>+<kbd>Shift</kbd>+<kbd>P</kbd> -> "Dev Containers: Rebuild and Reopen in Container"
4. Fetch dependencies for the server:
   ```sh
   uv sync
   ```
5. Fetch dependencies for the Unitree G1 client:
   ```sh
   cd unitree-client && uv sync
   ```

Snapchat Spectacles will refuse localhost websocket connections, so the server **must** be run at a public IP address with a valid (not self-signed) SSL certificate. I used [Railway](https://railway.com) to automate deployments from the `main` branch.

The unitree client can be run locally for testing in "mock" mode. This will allow it to run without access to the robot, and will simply print out commands as they are received:
```sh
cd unitree-client && uv run . -- --mock --server wss://SERVER_HOST/ws
```

### Deployment

- Build the coordination server targeting `linux/amd64` (necessary for `robotpkg-py318-pinocchio`):
  ```sh
  docker buildx build --platform linux/amd64 -t coordination-server .
  ```
  You can do this inside the devcontainer as it mounts the Docker socket from the host via `/var/run/docker.sock`.
   > **NOTE**: If you are using Orbstack on an M-series Mac, you'll need to disable Rosetta while building the server's Docker image locally: Orbstack > Settings > System > Use Rosetta to run Intel code (uncheck this).

WIP. Basically, get the Unitree G1 client running on the robot's computer with access to the required dependencies, and the server running in the `Dockerfile` container on a public IP address with a valid SSL certificate. Port `80` should be exposed in the container and mapped to 443 for ingress and egress.

> **IMPORTANT**: The server should have the environment variable `DASHBOARD_PASSWORD` set to something with a decent amount of entropy. The default password is `admin`.

## Architecture

The server uses `aiohttp` and `jinja2` to serve a simple web interface for pairing together Spectacles and Unitree G1 clients on a first-come-first-serve basis and monitoring messages. The dashboard is served at the root `/`, and the WebSocket server is served at `/ws`.

The server also handles inverse kinematics calculations between Spectacles' wrist and hand keypoints and the robot's URDF model.

Clients are not authenticated currently, and messages are passed transparently between the two clients without modification.